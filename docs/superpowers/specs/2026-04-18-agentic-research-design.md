# Agentic Research Agent for Compliance Evaluation

**Date:** 2026-04-18
**Status:** Approved

## Problem

The current compliance evaluation pipeline uses single-shot RAG: two fixed pgvector queries (product context + FDA context) followed by one LLM call. This limits the depth and breadth of evidence the system gathers. The agent cannot pursue follow-up questions, cross-reference external sources, or adapt its research strategy based on intermediate findings.

## Solution

Replace `_rag_evaluation()` in `src/compliance/evaluate.py` with a multi-round research agent built on DeepAgents (LangChain's agent harness on LangGraph). The agent autonomously decides what to search, reads results, and iterates until it has enough evidence for a confident verdict.

## Architecture

### Agent Core — Tool-Use Loop

A new module `src/compliance/research_agent.py` with a `research_substitution()` function:

1. Receives the same inputs as `evaluate_substitution()`: original component (with requirements), substitute candidate, product SKU, company name.
2. Constructs a system prompt with the substitution context: "Research whether this substitution is safe. Use tools to gather evidence. Stop when you have enough to make a confident verdict."
3. Provides five tools as plain Python functions (DeepAgents auto-generates tool schemas).
4. Runs a loop: LLM call -> tool_use -> execute tools -> append results -> repeat until the model returns a final answer.
5. Returns structured evidence rows (compatible with the SQLite Evidence table schema) plus a verdict.
6. Safety valve: 20-round max (configurable via `RESEARCH_MAX_ROUNDS`) to prevent runaway costs.

### Agent Tools

Five tools available to the agent:

1. **`search_documents`** — Queries the pgvector store via `vector_store.retrieve()`. Input: query string, optional `n_results`. Returns ranked text chunks with source metadata. Used for product label data, FDA guidance, any ingested documents.

2. **`query_database`** — Read-only queries against SQLite via predefined query types (no raw SQL). Available query types:
   - `product_bom(product_id: int)` — BOM components for a product
   - `supplier_products(product_id: int)` — suppliers for a raw material product
   - `ingredient_aliases(ingredient_name: str)` — alias/canonical mappings for an ingredient
   - `portfolio_usage(ingredient_names: list[str])` — which finished products use given ingredients
   - `ingredient_facts(ingredient_name: str)` — cached facts from `scraper/cache.py`

   Input: `query_type` string + typed parameters as above.

3. **`web_search`** — General web search via Brave Search API. Input: search query string. Returns top results with titles, snippets, URLs. For regulatory guidance, ingredient safety data, or labeling precedent not in local docs.

4. **`pubchem_lookup`** — Queries PubChem REST API for compound information. Input: compound name or CID. Returns chemical identity, synonyms, molecular formula, safety/hazard data. For verifying chemical equivalence between original and substitute.

5. **`fda_lookup`** — Queries openFDA API (dietary supplements, adverse events, labeling). Input: ingredient name + endpoint type (`dsld`, `adverse_events`, `labeling`). Returns structured FDA data.

Each tool returns `{"status": "ok"|"error", "data": ...}`. No external content is persisted to pgvector; the pgvector store stays as-is (scraped product docs and FDA docs from the sync pipeline).

### Integration with Evaluate Pipeline

**Current flow:**
```
evaluate_substitution()
  -> _blocker_evaluation()    # deterministic: allergens, certs, vegan checks
  -> _rag_evaluation()        # single-shot: 2 retrieve() calls + 1 LLM call
  -> merge results
```

**New flow:**
```
evaluate_substitution()
  -> _blocker_evaluation()           # unchanged
  -> research_substitution()         # replaces _rag_evaluation()
  -> merge results + persist evidence
```

Key integration points:

- **`_blocker_evaluation()` stays unchanged.** Fast, deterministic, catches hard blockers without an LLM.
- **`research_substitution()` replaces `_rag_evaluation()`.** Returns the same shape: `{"facts": [...], "rules": [...], "inference": "...", "caveats": [...], "kb_sources": [...]}` plus an `"evidence_rows"` list matching the Evidence table schema.
- **Evidence persistence:** After the agent returns, `evaluate_substitution()` calls `replace_opportunity_evidence()` to persist findings alongside existing BOM/supplier evidence. Each tool call becomes a traceable evidence row with `source_type`, `source_uri`, `fact_type`, and `quality_score`.
- **Graceful fallback:** If the research agent fails, `evaluate_substitution()` falls back to `_rag_evaluation()` with a warning log. The blocker engine verdict is never affected.
- **`evaluate_all_candidates()` and `build_all_opportunities()` unchanged.** They call `evaluate_substitution()` which internally uses the agent.

### DeepAgents Implementation

Uses DeepAgents with `ChatBedrockConverse` from `langchain-aws`:

```python
from langchain_aws import ChatBedrockConverse
from deepagents import create_deep_agent
from pydantic import BaseModel

class SubstitutionVerdict(BaseModel):
    facts: list[str]
    rules: list[str]
    inference: str
    caveats: list[str]
    evidence_rows: list[dict]

llm = ChatBedrockConverse(
    model=os.environ.get("RESEARCH_MODEL_ID", "us.anthropic.claude-sonnet-4-6-v1:0"),
    provider="anthropic",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
)

agent = create_deep_agent(
    model=llm,
    tools=[search_documents, query_database, web_search, pubchem_lookup, fda_lookup],
    system_prompt=RESEARCH_SYSTEM_PROMPT,
    response_format=SubstitutionVerdict,
)
```

Design decisions:
- **Bedrock via `ChatBedrockConverse`** with `provider="anthropic"` — same AWS credentials and region as the rest of the app.
- **Structured output** via `response_format=SubstitutionVerdict` — typed Pydantic object, no fragile JSON parsing.
- **Plain function tools** with type hints and docstrings — DeepAgents auto-generates schemas.
- **Safety valve** via LangGraph `recursion_limit` set to 40 steps (~20 tool-use rounds).
- **No subagents** — single agent with 5 tools is sufficient. Built-in planning handles research decomposition.
- **Existing `bedrock.py` unchanged** — blocker engine, document sync, other pipelines continue using `invoke_model`.

### Configuration & Error Handling

New environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `RESEARCH_MODEL_ID` | `us.anthropic.claude-sonnet-4-6-v1:0` | Bedrock model for the research agent |
| `RESEARCH_MAX_ROUNDS` | `20` | Safety valve for agent loop |
| `BRAVE_API_KEY` | (required for web search) | Brave Search API key |
| `RESEARCH_ENABLED` | `true` | Kill switch — set `false` to fall back to `_rag_evaluation()` |

Error handling:

1. **Individual tool failures** — tools return `{"status": "error", "message": "..."}`. The agent sees the error and tries alternatives.
2. **Agent-level failure** — `evaluate_substitution()` catches exceptions, logs warning, falls back to `_rag_evaluation()`.
3. **Missing API keys** — tools with missing keys are excluded from the agent's tool list at initialization. The agent always has at least `search_documents` and `query_database`.
4. **Recursion limit** — agent forced to return whatever evidence it has gathered rather than erroring out.

### CLI Research Script

A script `scripts/research.py` for triggering research from the terminal.

**Usage:**
```bash
python scripts/research.py --product-sku FG-iherb-10421 --original vitamin-d3
```

Both arguments are required. The script:

1. Looks up the product and finds all substitution candidates for the specified original ingredient (exact + alias + hypothesis matches) via `find_candidates_for_component()`.
2. Runs `research_substitution()` for each candidate.
3. Prints a summary per candidate — verdict, confidence, key facts, rules, caveats, sources — with ANSI color-coded verdicts (green/orange/red/gray).
4. Persists evidence rows to the SQLite Evidence table.

Reuses existing functions — no duplicate logic.

## New Dependencies

- `deepagents`
- `langchain-aws`

Added to `requirements.txt`. Existing `boto3` handles AWS auth.

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/compliance/research_agent.py` | Create — agent core, tools, system prompt |
| `src/compliance/evaluate.py` | Modify — replace `_rag_evaluation()` call with `research_substitution()` |
| `scripts/research.py` | Create — CLI entry point |
| `requirements.txt` | Modify — add `deepagents`, `langchain-aws` |
