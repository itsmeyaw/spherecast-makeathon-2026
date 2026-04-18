import logging
import os

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

For your final answer, provide:
- facts: concrete facts you found from any source
- rules: applicable FDA rules or regulatory requirements
- inference: your reasoning connecting facts to rules
- caveats: limitations, uncertainties, or missing evidence
- evidence_rows: structured evidence for each significant finding, each with \
  source_type (pgvector, sqlite, web-search, pubchem, fda-api), source_label, \
  source_uri, fact_type, fact_value, quality_score (0.0-1.0), and snippet.

IMPORTANT:
- Only state facts you can support with evidence from your tools.
- If evidence is missing, say "insufficient evidence" for that aspect.
- Never guess about compliance — flag uncertainty explicitly.
"""


class SubstitutionVerdict(BaseModel):
    facts: list[str]
    rules: list[str]
    inference: str
    caveats: list[str]
    evidence_rows: list[dict]


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
    )

    max_rounds = int(os.environ.get("RESEARCH_MAX_ROUNDS", "20"))

    return create_deep_agent(
        model=llm,
        tools=_build_tools(),
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        response_format=SubstitutionVerdict,
    ), max_rounds


def research_substitution(original, substitute, product_sku, company_name):
    agent, max_rounds = _build_agent()

    user_message = (
        f"Research this ingredient substitution for compliance:\n\n"
        f"PRODUCT: {company_name} — {product_sku}\n"
        f"ORIGINAL INGREDIENT: {original['original_ingredient']} "
        f"(canonical: {original['group']['canonical_name']}, "
        f"function: {original['group']['function']})\n"
        f"PROPOSED SUBSTITUTE: {substitute.get('current_match_name', 'unknown')} "
        f"(match type: {substitute.get('match_type', 'unknown')})\n\n"
        f"Investigate whether this substitution is safe, compliant with FDA "
        f"regulations, and functionally equivalent. Check for allergen conflicts, "
        f"labeling implications, certification issues, and bioavailability differences."
    )

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"recursion_limit": max_rounds * 2},
    )

    verdict = result["structured_response"]
    return {
        "facts": verdict.facts,
        "rules": verdict.rules,
        "inference": verdict.inference,
        "caveats": verdict.caveats,
        "evidence_rows": verdict.evidence_rows,
        "kb_sources": [],
    }
