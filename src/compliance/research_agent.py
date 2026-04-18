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

When you have completed your research, respond with ONLY a JSON object (no \
markdown fences, no preamble) matching this exact schema:
{
  "facts": ["string", ...],
  "rules": ["string", ...],
  "inference": "string",
  "caveats": ["string", ...],
  "evidence_rows": [
    {
      "source_type": "pgvector|sqlite|web-search|pubchem|fda-api",
      "source_label": "string",
      "source_uri": "string",
      "fact_type": "string",
      "fact_value": "string",
      "quality_score": 0.0-1.0,
      "snippet": "string"
    }
  ]
}
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
    tools = [search_documents, query_database, pubchem_lookup, fda_lookup]
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

    max_rounds = int(os.environ.get("RESEARCH_MAX_ROUNDS", "20"))

    return create_deep_agent(
        model=llm,
        tools=_build_tools(),
        system_prompt=RESEARCH_SYSTEM_PROMPT,
    ), max_rounds


def _parse_verdict(text: str) -> SubstitutionVerdict:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in agent response: {text[:200]}")
    return SubstitutionVerdict.model_validate(json.loads(text[start:end]))


def research_substitution(original, substitute, product_sku, company_name):
    sub_name = substitute.get("current_match_name", "unknown")
    logger.info(
        "Starting research: %s → %s for %s / %s",
        original["original_ingredient"], sub_name, company_name, product_sku,
    )

    agent, max_rounds = _build_agent()
    logger.debug("Agent built with max_rounds=%d", max_rounds)

    user_message = (
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

    logger.debug("Streaming agent for %s → %s", original["original_ingredient"], sub_name)
    result = None
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"recursion_limit": max_rounds * 2},
        stream_mode="updates",
    ):
        result = chunk

    if result is None:
        raise RuntimeError(f"Agent stream produced no output for {original['original_ingredient']} → {sub_name}")

    messages = result.get("messages", [])
    if not messages:
        raise RuntimeError(f"No messages in agent output for {original['original_ingredient']} → {sub_name}")

    final_text = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
    verdict = _parse_verdict(final_text)

    logger.info(
        "Research complete: %s → %s — %d facts, %d rules, %d evidence rows",
        original["original_ingredient"], sub_name,
        len(verdict.facts), len(verdict.rules), len(verdict.evidence_rows),
    )
    return {
        "facts": verdict.facts,
        "rules": verdict.rules,
        "inference": verdict.inference,
        "caveats": verdict.caveats,
        "evidence_rows": [row.model_dump() for row in verdict.evidence_rows],
        "kb_sources": [],
    }
