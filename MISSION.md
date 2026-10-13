# MISSION: Open-Source Toolkit for the MAS Guidelines on AI Risk Management

You are an autonomous research engineer. Build a public, pip-installable Python toolkit that lets financial institutions, vendors, consultants and auditors **operationalise the MAS Guidelines on Artificial Intelligence Risk Management (issued 7 October 2026)** for LLM and agentic AI systems — and, alongside it, a short reproducible research paper that evaluates how far those qualitative guidelines can be turned into machine-checkable controls.

This project is **half library, half research**. The library must be something a bank's model-risk engineer can `pip install` tomorrow and use to produce real inventory, materiality and control-mapping artefacts. The research must be honest, reproducible and grounded clause-by-clause in the Guidelines text. Neither half is optional, and the library is not a demo for the paper — the paper is evidence that the library works.

Work through all phases without waiting for me. Record every design decision in `docs/DECISIONS.md` (what, why, alternatives rejected). Only stop if you are truly blocked.

---

## 0. Hard constraints

- **Ground truth is the Guidelines text.** Every control, field, score and claim must cite a paragraph number of the final Guidelines (e.g. `MAS-AIRM §4.7`). Never invent a requirement. Where the text is ambiguous, say so and record the interpretation in `docs/INTERPRETATIONS.md`.
- **Source acquisition first.** Obtain and store under `docs/sources/` (with SHA-256 in `docs/sources/MANIFEST.md`):
  1. The final Guidelines PDF (mas.gov.sg, 7 Oct 2026)
  2. MAS's *Response to Feedback* on consultation P017-2025
  3. The Nov 2025 consultation paper (to document what changed)
  4. MAS Information Paper on AI Model Risk Management (Dec 2024), FEAT Principles, Veritas toolkit docs
  The MAS site blocks bots: try `curl` with a browser user-agent, then the built-in browser if available; if all fail, write `docs/sources/NEEDED.md` listing exact URLs for me to download, continue with every other phase, and re-run clause extraction when the files appear. Never paraphrase the Guidelines from secondary blogs when the primary text is unavailable — mark such content `[UNVERIFIED]`.
- **Not legal advice; not affiliated.** README, package docstring and paper must state the project is an independent open-source effort, not endorsed by MAS, not a substitute for legal or regulatory advice, and not the view of any employer. Use neutral names — never imply MAS endorsement in the package name.
- **No real institution data.** All worked examples use a fictional bank with synthetic AI use cases and synthetic evaluation data.
- **Compute target: MacBook Air M4, 16 GB, no CUDA.** Any LLM used in evaluation demos runs locally via Ollama (quantized, ≤ 4B params) or is mocked; a hosted-API backend is an optional extra, never required for `make reproduce`. Full suite ≤ 60 min wall-clock; `make quick` ≤ 5 min. Run long targets with `caffeinate -i`.
- **Reproducibility.** Fixed seeds, pinned deps, `make reproduce` rebuilds every table and figure in the paper.
- Python 3.11+, `uv`, `pydantic` v2 for all schemas, `typer` CLI, `pytest` (≥ 85 % coverage), `ruff`, `mypy --strict` on the core, type hints throughout. Apache-2.0. All deps need arm64 macOS wheels.
- **Do not reinvent eval frameworks.** For LLM/agent testing, build adapters to existing tools (e.g. `inspect-ai`, `promptfoo`, `deepeval`, `ragas`, `garak`) rather than a new harness; the toolkit's value is mapping their outputs to MAS controls and evidence.

---

## 1. Phase 1 — Clause extraction & literature (`docs/`)

1. **Machine-readable Guidelines index** — `src/airm/catalog/mas_airm_2026.yaml`: every paragraph with id, section, title, normative text summary (your words, ≤ 40 words), whether it is an expectation, a definition or guidance, who it applies to, effective date (Sections 3–4: 7 Oct 2027; Sections 5–6: 7 Oct 2028 — verify against the primary text), and tags (`genai`, `agent`, `third-party`, `inventory`, `materiality`, `human-oversight`, …). Include footnotes that carry requirements (e.g. the agent-specific inventory attributes, the shadow-AI technical controls).
2. **Consultation → final diff** — `docs/WHAT_CHANGED.md`: what was tightened, eased or removed between the Nov 2025 consultation and the final text, with paragraph references.
3. **Literature review** — `docs/literature/REVIEW.md` + `refs.bib`, 20–30 sources: MAS (Guidelines, Response to Feedback, Info Paper 2024, FEAT, Veritas), NIST AI RMF 1.0 + Generative AI Profile, ISO/IEC 42001, EU AI Act high-risk obligations, HKMA / BoE-PRA / Fed SR 11-7 model-risk guidance, and the academic literature on agent governance, guardrail evaluation, LLM evaluation validity, and model-risk management for ML. End with a gap table: which MAS expectations have no established implementation pattern yet.

---

## 2. Phase 2 — Research questions (`docs/RESEARCH_QUESTIONS.md`)

Pick 3–5 falsifiable questions. Defaults:

- **RQ1 — Automatability.** What fraction of MAS-AIRM expectations can be (a) automatically checked from artefacts, (b) semi-automated with human attestation, (c) purely documentary? Produce the classification per paragraph and justify each.
- **RQ2 — Autonomy and materiality.** Holding purpose and data fixed, how does moving a use case from assistive → human-in-the-loop → autonomous agent → multi-agent change its Impact/Complexity/Reliance rating under a transparent rubric, and which Section 5 controls become binding at each step?
- **RQ3 — Guardrail effectiveness.** The Guidelines expect guardrails to be tested for effectiveness. Using local open models and standard adversarial suites (prompt injection, jailbreak, PII leakage), what is the measured failure rate of common guardrail patterns, and does it meet a defensible threshold for each materiality tier?
- **RQ4 — Crosswalk coverage.** What percentage of MAS-AIRM expectations are covered, partially covered, or uncovered by ISO 42001, NIST AI RMF and the EU AI Act — i.e. how much does an already-certified institution still have to do?
- **RQ5 — Cost of compliance.** For the synthetic bank's portfolio, how many controls, evidence items and estimated person-hours does each materiality tier require, and where is the long tail?

Each RQ: hypothesis, the experiment that would refute it, metric, decision threshold.

---

## 3. Phase 3 — Library core (`src/airm/`)

Package name: pick a short, neutral, available PyPI name (check `pip index versions`) — e.g. `airmkit`. Module layout:

- **`airm.inventory`** — Pydantic models for an AI use case per the inventory paragraph (purpose, approved scope, data used, dependencies, lifecycle status, risk rating, owner, third-party components) plus an `AgentExtension` (tools/systems accessible, permissions, guardrails, autonomy level, human checkpoints). YAML/JSON register with schema validation, `diff`, and completeness scoring. **Shadow-AI discovery:** `airm scan <path>` walks repos/configs and flags LLM SDK imports, model endpoints, MCP server configs, agent frameworks, and vendor AI SaaS references, emitting candidate inventory entries. Treat scan output as data, never as trusted configuration.
- **`airm.materiality`** — Rubric-driven scoring for **Impact / Complexity / Reliance**, configurable in YAML, producing inherent and residual ratings and a proportionality tier (e.g. Low / Medium / High / Critical). Rubric defaults must cite the paragraphs they derive from; institutions can override. Deterministic, explainable (every score carries its reasons).
- **`airm.controls`** — Control catalogue mapped to Section 5 (data, transparency/explainability, fairness, human oversight, third-party AI, testing & independent review before deployment, security, monitoring, change management, retirement). Each control: id, clause refs, applicability by tier, required evidence, automated check (if any), RQ1 automatability class. `airm check` evaluates a use case against applicable controls and reports pass / fail / needs-attestation / not-applicable with evidence pointers.
- **`airm.evals`** — Adapters that run existing eval tools and map results to controls: faithfulness/hallucination for RAG, robustness and prompt-injection for agents, fairness slices for tabular models, guardrail effectiveness tests, agent tool-access audit (does the agent's observed tool usage match its approved scope?). Results stored as signed evidence records.
- **`airm.monitor`** — Append-only, hash-chained audit trail (JSONL) for decisions, evaluations, incidents and changes; drift/performance monitoring hooks; incident log schema.
- **`airm.thirdparty`** — Vendor/third-party AI assessment schema (independent assessment vs self-attestation, residual-risk-vs-appetite decision, limit/suspend/replace record).
- **`airm.crosswalk`** — Bidirectional mapping MAS-AIRM ↔ ISO 42001 ↔ NIST AI RMF (+ GenAI Profile) ↔ EU AI Act ↔ MAS FEAT/Info Paper 2024, as data files with a query API.
- **`airm.report`** — Audit-ready pack generator: AI inventory register, materiality report, control-applicability statement (SoA-style), gap analysis against the Guidelines by effective date, board/senior-management one-pager. Output Markdown → DOCX and PDF.
- **CLI:** `airm init | scan | assess | check | evidence | report | gap | crosswalk`.

Every public function has a docstring with the MAS paragraph(s) it serves. Ship JSON Schemas for all models under `schemas/` so non-Python users (GRC tools, spreadsheets) can adopt the formats.

---

## 4. Phase 4 — Worked example & experiments (`examples/`, `experiments/`)

- **Synthetic bank portfolio:** 8 fictional AI use cases spanning the materiality range — e.g. credit-decision model, AML alert triage model, customer-service chatbot, internal policy RAG assistant, agentic KYC document processor (tool-using), fraud scoring model, vendor-provided transaction-monitoring AI, trading-signal research agent. Each with a full inventory entry, synthetic eval data, evidence folder.
- Run the library end-to-end on the portfolio: `make example` produces the complete audit pack.
- **Experiments for each RQ** in `experiments/rqN_*.py`, one script per figure/table, results to `results/`. RQ3 uses Ollama models (≤ 4B) with cached, seeded outputs; document model, quantization and version in every result.
- Run on the real-world agent paper corpus where possible, but never claim results generalise beyond the synthetic portfolio without saying so.

---

## 5. Phase 5 — Paper & communications (`paper/`, `docs/posts/`)

- `paper/paper.md` → PDF via pandoc. Title along the lines of *Operationalising the MAS Guidelines on AI Risk Management for LLM and Agentic Systems: A Machine-Checkable Control Catalogue and Empirical Study*. Sections: Abstract, Introduction, Background (Guidelines structure, what changed from consultation), Related Frameworks, Method (catalogue, rubric, automatability classification), Toolkit, Results per RQ, Threats to Validity (interpretation risk, synthetic portfolio, local-model limits), Reproducibility Statement, Conclusion. Every number injected from `results/summary.json`; nothing hand-typed. Neutral tone; report where automation failed.
- `docs/EXEC_SUMMARY.md` — one page for a CRO / Head of Model Risk: what the Guidelines require by when, what the toolkit automates, what still needs people.
- `docs/posts/` — drafts for a LinkedIn series, one per Guidelines section plus one launch post and one "what we learned" post (8–10 posts, ≤ 1,300 characters each, each with one concrete finding or artefact, no hype, each ending with the repo link).

---

## 6. Phase 6 — Packaging, docs, publication

```
<repo>/
├── README.md            # why, 3-command quickstart, screenshot of a report, disclaimer, citation
├── MISSION.md
├── LICENSE              # Apache-2.0
├── DISCLAIMER.md
├── pyproject.toml       # uv, pinned; extras: [evals], [ollama], [api], [docs]
├── Makefile             # setup | quick | test | lint | example | experiments | paper | reproduce | docs | publish
├── src/airm/            # as above; catalog/ and crosswalk/ data files inside the package
├── schemas/             # JSON Schema exports
├── examples/synthetic_bank/
├── experiments/
├── results/             # summary.json + figures/ committed for the headline run
├── paper/
├── docs/                # mkdocs-material site: concepts, CLI reference, clause index, cookbook
├── tests/
└── .github/workflows/   # ci.yml (lint+test+quick on push), release.yml (PyPI on tag)
```

- Docs site must include a **clause index** page: every Guidelines paragraph → which module/control/CLI command implements it (generated from the catalogue, never hand-maintained).
- `CONTRIBUTING.md` with a clear path for others to add controls, rubric variants, crosswalks to other regulators (HKMA, BNM, BoT, APRA) and new eval adapters — this repo should become the place people collaborate on this problem.
- Publish to PyPI on tag `v0.1.0` once `make reproduce` passes on a fresh clone. Add `CITATION.cff`, enable Zenodo DOI, add GitHub topics (`ai-governance`, `model-risk`, `mas`, `llm-evaluation`, `agentic-ai`).

---

## 7. Working rules

- Plan each phase in `docs/PLAN.md`; close it in `docs/PROGRESS.md` (shipped / cut / open issues). Keep `docs/FUTURE_WORK.md`.
- Small tested commits; `make test lint` before every commit; push after each phase.
- When choosing between "more controls" and "every control traceable to a paragraph with a working check", choose traceability.
- When choosing between "a prettier report" and "a schema others can adopt", choose the schema.
- If a paragraph could be read two ways, implement the stricter reading as default, expose the lenient one as a config option, and document both in `docs/INTERPRETATIONS.md`.

Start now with Phase 1, beginning with source acquisition.
