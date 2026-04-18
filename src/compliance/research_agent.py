import json
import logging
import os

from botocore.config import Config as BotoConfig
from deepagents import create_deep_agent
from langchain_aws import ChatBedrockConverse
from pydantic import BaseModel

from src.compliance.tools.fda_lookup import fda_lookup
from src.compliance.tools.pubchem_lookup import pubchem_lookup
from src.compliance.tools.query_database import query_database
from src.compliance.tools.search_documents import search_documents
from src.compliance.tools.search_tds import search_tds
from src.compliance.tools.web_search import web_search

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM_PROMPT = """\
You are an FDA dietary supplement compliance research agent. Your job is to \
thoroughly research whether a proposed ingredient substitution is safe and \
compliant before issuing a verdict.

You have tools to search a local document store (scraped product labels, FDA \
docs), query a structured database (BOMs, suppliers, ingredient aliases), \
search the web, look up compounds on PubChem, and query the openFDA API.

Research strategy:
1. Start by searching the local document store for the product and ingredient.
2. Check the database for ingredient aliases, supplier data, and portfolio usage.
3. If local evidence is insufficient, search the web, PubChem, or FDA for \
   external data on the ingredient pair.
4. Stop when you have enough evidence to make a confident verdict.

IMPORTANT:
- Only state facts you can support with evidence from your tools.
- If evidence is missing, say "insufficient evidence" for that aspect.
- Never guess about compliance — flag uncertainty explicitly.

When researching a substitution, also search for Technical Data Sheets (TDS), \
Certificates of Analysis (CoA), and fact sheets for both the original ingredient \
and the proposed substitute. The same substance from different suppliers can have \
different specifications (purity, heavy metals, particle size, etc.).

For each ingredient:
1. Look up which suppliers provide it (query_database with supplier_products).
2. For each supplier, search for TDS/spec data (search_tds with supplier_name).
3. Extract specification key-value pairs from the results.
4. Include spec differences across suppliers in your evidence and caveats.

Important: the same supplier can offer the same substance under different product \
SKUs with different specifications (e.g., different purity grades). Treat each \
supplier-product combination as a distinct spec source, not just each supplier.

When reporting evidence_rows for TDS/spec findings, use:
- source_type: "tds"
- fact_type: "spec:<key>" (e.g., "spec:purity", "spec:heavy_metals_lead")
- fact_value: the extracted value with unit (e.g., "99.5%", "< 0.5 ppm")
- source_label: include supplier name and product SKU (e.g., "ADM TDS for RM-vitamin-c-123")

Your final response will be automatically parsed into a structured format. \
Populate every field: facts (list of factual findings), rules (applicable \
regulations), inference (your overall compliance verdict), caveats (uncertainties \
or limitations), and evidence_rows (source citations with quality scores 0-1). \
For evidence_rows use source_type values like: pgvector, sqlite, web-search, \
pubchem, fda-api, or tds.
"""


class EvidenceRow(BaseModel):
    source_type: str
    source_label: str
    source_uri: str
    fact_type: str
    fact_value: str
    quality_score: float
    snippet: str


class SubstitutionVerdict(BaseModel):
    facts: list[str]
    rules: list[str]
    inference: str
    caveats: list[str]
    evidence_rows: list[EvidenceRow]


def _build_tools():
    tools = [search_documents, query_database, pubchem_lookup, fda_lookup, search_tds]
    if os.environ.get("BRAVE_API_KEY"):
        tools.append(web_search)
    return tools


def _build_agent():
    model_id = os.environ.get("RESEARCH_MODEL_ID", "us.anthropic.claude-sonnet-4-6-v1:0")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    llm = ChatBedrockConverse(
        model=model_id,
        provider="anthropic",
        region_name=region,
        config=BotoConfig(read_timeout=1000, connect_timeout=10, retries={"max_attempts": 3, "mode": "adaptive"}),
    )

    max_rounds = int(os.environ.get("RESEARCH_MAX_ROUNDS", "12"))

    return create_deep_agent(
        model=llm,
        tools=_build_tools(),
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        response_format=SubstitutionVerdict,
    ), max_rounds


def _parse_verdict(raw) -> SubstitutionVerdict:
    if isinstance(raw, list):
        raw = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw
        )
    text = str(raw)
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in agent response: {text[:200]}")
    return SubstitutionVerdict.model_validate(json.loads(text[start:end]))


def _make_user_message(original, substitute, product_sku, company_name):
    sub_name = substitute.get("current_match_name", "unknown")
    return (
        f"Research this ingredient substitution for compliance:\n\n"
        f"PRODUCT: {company_name} — {product_sku}\n"
        f"ORIGINAL INGREDIENT: {original['original_ingredient']} "
        f"(canonical: {original['group']['canonical_name']}, "
        f"function: {original['group']['function']})\n"
        f"PROPOSED SUBSTITUTE: {sub_name} "
        f"(match type: {substitute.get('match_type', 'unknown')})\n\n"
        f"Investigate whether this substitution is safe, compliant with FDA "
        f"regulations, and functionally equivalent. Check for allergen conflicts, "
        f"labeling implications, certification issues, and bioavailability differences."
    )


def _extract_tool_calls(messages):
    """Extract tool call info from a list of messages."""
    calls = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                calls.append({"name": tc.get("name", "unknown"), "args": tc.get("args", {})})
    return calls


def _extract_tool_results(messages):
    """Extract tool result snippets from a list of messages."""
    results = []
    for msg in messages:
        if hasattr(msg, "content") and getattr(msg, "type", None) == "tool":
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            results.append({"name": getattr(msg, "name", "tool"), "snippet": content[:200]})
    return results


def _extract_text(messages):
    """Extract assistant text content from messages."""
    texts = []
    for msg in messages:
        if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
            if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                texts.append(msg.content)
    return texts


def research_substitution_stream(original, substitute, product_sku, company_name):
    """Generator that yields (event_type, data) tuples during research.

    Event types:
      - ("tool_call", {"name": ..., "args": ...})
      - ("tool_result", {"name": ..., "snippet": ...})
      - ("thinking", str)  — assistant text between tool rounds
      - ("result", dict)   — final verdict dict
    """
    sub_name = substitute.get("current_match_name", "unknown")
    logger.info(
        "Starting research: %s → %s for %s / %s",
        original["original_ingredient"], sub_name, company_name, product_sku,
    )

    agent, max_rounds = _build_agent()
    user_message = _make_user_message(original, substitute, product_sku, company_name)

    last_model_messages = None
    verdict = None
    chunk_keys_seen = set()
    try:
        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": user_message}]},
            config={"recursion_limit": max_rounds * 5},
            stream_mode="updates",
        ):
            chunk_keys_seen.update(chunk.keys())

            if "model" in chunk and "messages" in chunk["model"]:
                msgs = chunk["model"]["messages"]
                last_model_messages = msgs
                for tc in _extract_tool_calls(msgs):
                    yield ("tool_call", tc)
                for text in _extract_text(msgs):
                    yield ("thinking", text)

                sr = chunk["model"].get("structured_response")
                if sr is not None:
                    verdict = sr if isinstance(sr, SubstitutionVerdict) else SubstitutionVerdict.model_validate(sr)

            if "tools" in chunk and "messages" in chunk["tools"]:
                for tr in _extract_tool_results(chunk["tools"]["messages"]):
                    yield ("tool_result", tr)
    except Exception:
        logger.exception("Stream error during research: %s → %s (chunks seen: %s)", original["original_ingredient"], sub_name, chunk_keys_seen)
        if verdict is None and last_model_messages:
            logger.info("Attempting to parse verdict from last model messages before stream error")
        else:
            raise

    if verdict is None and last_model_messages:
        final_msg = last_model_messages[-1]
        final_content = final_msg.content if hasattr(final_msg, "content") else str(final_msg)
        verdict = _parse_verdict(final_content)

    if verdict is None:
        raise RuntimeError(f"Agent produced no output for {original['original_ingredient']} → {sub_name} (chunk keys seen: {chunk_keys_seen})")

    logger.info(
        "Research complete: %s → %s — %d facts, %d rules, %d evidence rows",
        original["original_ingredient"], sub_name,
        len(verdict.facts), len(verdict.rules), len(verdict.evidence_rows),
    )
    result = {
        "facts": verdict.facts,
        "rules": verdict.rules,
        "inference": verdict.inference,
        "caveats": verdict.caveats,
        "evidence_rows": [row.model_dump() for row in verdict.evidence_rows],
        "kb_sources": [],
    }
    yield ("result", result)


def research_substitution(original, substitute, product_sku, company_name):
    result = None
    for event_type, data in research_substitution_stream(original, substitute, product_sku, company_name):
        if event_type == "result":
            result = data
    if result is None:
        raise RuntimeError("research_substitution_stream did not yield a result")
    return result
