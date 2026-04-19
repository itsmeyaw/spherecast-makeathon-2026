# Agnes: Sourcing Decision-Support for Supplement Raw Materials

<p align="center">
  <img src="docs/img/product_research.gif" alt="UI" />
</p>

**Built on the Spherecast challenge database.**

**Stack:** Python, LangGraph, Streamlit, SQLAlchemy, PubChem, OpenFDA

**Scope:** US & EU dietary supplements (Demoed via Vitamin C).

[Core Idea](#the-core-idea) · [Hero Scenario](#hero-scenario) · [Architecture](#architecture-three-reasoning-layers) · [Output](#output-tiered-candidate-groups) · [Key Learning](#key-learning) · [Vision](#vision-the-product-roadmap)

## The Core Idea
Most AI sourcing tools just pick the cheapest supplier and call it a day. Agnes does the opposite: it uses a three-layer reasoning system to produce **tiered candidate groups** and never makes up data it doesn't have.

Every claim is traceable. Critical documents like TDSs, CoAs, and GMO statements are rarely public. Agnes treats that as a real problem to solve, not sweep under the rug.

## Hero Scenario
A brand needs to swap out a key raw material (say, Vitamin C for an effervescent powder) because their current supplier is out of stock. A simple price comparison won't cut it here. Agnes finds a substitute that is:
1. ⁠**Legally compliant** (e.g., US 21 CFR 111 + EU 2002/46/EC).
2. ⁠**Physically compatible** with the manufacturing process.
3. **Backed by verifiable evidence**.
4. **Strategically viable** (e.g., consolidating volume with an existing portfolio supplier).

---

## Architecture: Three Reasoning Layers

<p align="center">
  <img src="docs/img/graph.png" alt="Graph" />
</p>


### Layer 1: Identity and Compliance (Deterministic Gate) using Domain Expert Annotation
An automated legal and chemical gate, nothing gets through without passing these checks.
- ⁠**Canonical Vocabulary:** Anchors ingredients to global registries (e.g., PubChem CID, CAS).
- ⁠**Legal Whitelists:** Rejects non-permitted chemical forms based on target market regulations.
- ⁠**Purity Thresholds:** Enforces pharmacopoeia standards (USP / Ph. Eur.) for assay percentages, heavy metals, and elemental impurities (per ICH Q3D).

### Layer 2: Evidence-Weighted Enrichment (The Epistemic Core)
Ranks candidates by how trustworthy their data actually is (e.g., Authoritative Registry = 0.95, Supplier Website = 0.70, LLM Inference = 0.20).
- **Contrapositive Inference:** Supplier documents are usually private, so Agnes infers raw material properties from Finished Goods (FG). If a tightly regulated CPG brand claims "Non-GMO" on their label, Agnes infers their mapped supplier provides a Non-GMO grade. Missing evidence counts as zero. It's never silently ignored.

### Layer 3: Strategic Reasoning (Business Logic)
Decides what to do with the verified data.
- **Country-Tier Scoring:** Uses calibrated priors from FDA/EU import alerts and export history to assess geographic risk, overridable by strong supplier-specific signals.
- **Consolidation Bonus:** Boosts scores for suppliers already used by other portfolio brands to improve MOQ and pricing leverage.
- **Substitution-Delta Risk:** Measures the real impact of a swap (e.g., switching from a crystalline to a coated form means costly reformulation; changing countries shifts tariff exposure).

---

## Output: Tiered Candidate Groups
Agnes groups results into tiers that match how procurement teams actually work. Every candidate carries a full reasoning trace and re-ranks automatically when variables change.
- **Preferred:** Clears all purity gates, has authoritative evidence, low country risk, and offers strategic consolidation.
- **Acceptable:** Passes legal gates but comes with minor strategic trade-offs (e.g., higher baseline country risk, offset by a strong individual track record).
- **Flagged:** Promising but missing critical private evidence. Queues the acquisition agent.
- **Unknown:** Could not provide a good decision based on the current evidences due to limited knowledge and information.

---

## Key Learning
 
During this project, we concluded the following points:
- Regulation and many documents does not change so much often, it is **better to use a document embedding database** to make query faster, more predictable, and cheaper. 
  - For embedding, we propose semantic embedding with section-based chunking, with Claude Haiku 4.5 as feature extractor and AWS Titan Embedding v2 as embedding model.
  - For vector storage, we propose using PostgreSQL with pgVector extension and tsvector for text searching.
- LLM usage with **Langgraph is a good middle ground** to provide a equivalent good result with fewer token usage than using Deepagents. However, **DeepAgents offers better flexibility** when faced with less predictable case, for example when data provided is not as complete as others.
- Since this task is an open-ended task, it is important to **limit agent loop**, such as tool usage, thinking, etc.
- Most of the **heavy lifting in this project comes from document outsourcing**, which are not publicly available. Given enough time to collect data, especially from manufacturer. Even with few data, our agent is able to query even complex information. 

We also face the following problems:

- We tried to use AWS OpenSearch as vector store, with the hope to have a managed service from AWS. However, the **setup is too complex** due to AWS IAM. We moved then to use a Postgres, which provides equivalent good result.
- **Most key decision documents are not publicly available**, such as technical sheets. Implementing this system is very easy, collecting the data is much harder. We suggest to use automated document acquisition agent, explained later. It is also worth it to allow user upload the document they collected from their supplier.


---

## Vision: The Product Roadmap

1. ⁠**Automated Document Acquisition Agent:** Automates the manual procurement loop. If a supplier is in the "Flagged Tier," an outreach agent drafts a context-aware email requesting the missing TDS or CoA, parses the supplier's reply, processes the extracted information, and automatically updates the supplier's score.
2. **Component Vector Database:** Embeds the ingredient items themselves into a vector database based on multi-dimensional key properties (not just raw text). By semantically clustering similar raw materials, future supplier queries and compatibility checks become significantly faster and cheaper to execute.
3. ⁠**Deterministic Linear Problem Solver:** Procurement isn't just about finding a match; it's an optimization problem. Agnes will construct the abstract parameters (MOQ, capacity, lead time, price) and feed them into a linear programming solver to find the mathematically optimal substitution. This provides stronger, deterministic confidence for enterprise clients.
4. ⁠**Full Knowledge-Graph Evidence Engine:** Expands inference into a multi-hop graph (Suppliers ↔️ Raw Materials ↔️ Finished Goods ↔️ Certifications) to enable counterfactual reasoning, determining exactly which missing document would reduce procurement risk the most.
5. **Reformulation Aware Substitution:** Shifts the ranking metric from per-kg price to Total Cost of Substitution (Price Delta + Reformulation Overhead + Market Impact).
6. ⁠**Learned Weights & Priors:** Transitions evidence weights and country risk scores from hand-specified logic to machine learning, trained on historical procurement audit successes and failures.
7. ⁠**Multi-Market Regulatory Substrate:** Scales the architecture to cover every supplement ingredient, across every global market, pharmacopoeia, and claim regime.
8. **Adversarial Quality Gate:** In addition to the research agent, it is worth it to create a subagent which points out fallacy in the proposal. This allows research agent to provide better argumentation to client. Usually, 1 quality check passthrough is enough.

---
*Sources & Acknowledgements:* Database and framing by Spherecast. Canonical chemistry via PubChem (NIH). Regulatory thresholds cross-verified against EUR-Lex, EDQM, FDA, and public supplier TDSs. Risk priors informed by FDA Import Alerts and EU RASFF.

*Team:* Yudhis, Sebastian, Janet, Heona, Si-Hoon