# airmkit

**Operationalise the MAS Guidelines on AI Risk Management for LLM and agentic AI systems.**

[![CI](https://github.com/thanatchon36/airmkit/actions/workflows/ci.yml/badge.svg)](https://github.com/thanatchon36/airmkit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/airmkit.svg)](https://pypi.org/project/airmkit/)
[![Python](https://img.shields.io/pypi/pyversions/airmkit.svg)](https://pypi.org/project/airmkit/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

The Monetary Authority of Singapore issued its [Guidelines on Artificial Intelligence Risk
Management](https://www.mas.gov.sg/-/media/mas-media-library/regulation/guidelines/bd/guidelines-on-artificial-intelligence-risk-management-for-financial-institutions/guidelines-on-artificial-intelligence-risk-management.pdf)
on 7 October 2026. They take effect on **7 October 2027** for oversight, identification,
inventory and risk materiality assessment, and on **7 October 2028** for life cycle controls and
capability (§1.8, as clarified by the Response to Feedback §13.5).

The Guidelines are 30 pages of principles. `airmkit` turns them into artefacts an engineer can
produce and an auditor can read: a machine-readable clause index, an AI inventory schema with
first-class support for agents, a transparent risk-materiality rubric, a control catalogue where
every control cites a paragraph, evidence records that cannot be quietly edited, and an audit pack.

**[Read the paper on the web](https://thanatchon36.github.io/airmkit/paper/)** ·
**[PDF](paper/paper.pdf)** · **[Docs](https://thanatchon36.github.io/airmkit/)** ·
**[One page for a CRO](docs/EXEC_SUMMARY.md)**

> **Not affiliated with MAS. Not legal or regulatory advice.** Independent open-source project.
> Every interpretation and every threshold is the authors'; MAS declines to prescribe materiality
> formulae, metrics or testing methodologies (Response to Feedback §7.19, §10.28, §10.66).
> See [DISCLAIMER.md](DISCLAIMER.md).

## Why

Most AI governance tooling stops at a spreadsheet of policies. The hard part of these Guidelines is
not writing the policy, it is answering three questions per use case, repeatedly, with evidence:

1. **What AI do we actually have?** Including AI embedded in SaaS the vendor does not call AI
   (§4.2 fn21), and shadow AI staff adopted without asking (§4.4 fn22).
2. **How material is it?** On Impact, Complexity and Reliance (§4.12), where moving a use case from
   "staff reviews every suggestion" to "the agent calls the tool itself" changes the answer.
3. **Which controls bind, and can we show they work?** Including the expectation that guardrails be
   tested for *effectiveness*, not merely present (§5.15 fn46).

`airmkit` answers all three from files in your repository, and prints the paragraph behind every
answer.

## Install

```bash
pip install airmkit                 # core
pip install "airmkit[evals]"        # adapters for inspect-ai, deepeval, ragas, garak
pip install "airmkit[report,docs]"  # DOCX output and the docs site
```

Python 3.11+. No GPU, no API key and no network access required for the core or for
`make reproduce`.

## Three-command quickstart

```bash
airm init --institution "Merlion Commercial Bank"   # scaffold a register and rubric
airm scan . --out candidates.yaml                   # find AI already in your code and configs
airm report --register ai-inventory.yaml --out audit-pack/
```

The third command writes the audit pack: an inventory register, a materiality report, a
control-applicability statement, a gap analysis by effective date and a one-page board summary.

```console
$ airm assess --register examples/synthetic_bank/ai-inventory.yaml

  Use case                     Impact      Complexity  Reliance    Inherent   Residual
 ─────────────────────────────────────────────────────────────────────────────────────────
  credit-decision-model        critical    medium      high        Critical   High
  aml-alert-triage             high        medium      medium      High       Medium
  kyc-document-agent           high        critical    high        Critical   High
  policy-rag-assistant         low         medium      low         Medium     Low
  ...
  Rubric: default-v1 · dimensions MAS-AIRM §4.12(a)-(c) · tiering is this toolkit's proposal
```

```console
$ airm check --register examples/synthetic_bank/ai-inventory.yaml --use-case kyc-document-agent

  FAIL  AIRM-5.15-GUARDRAIL-EFFECTIVENESS   guardrail 'injection filter' has no effectiveness test
        MAS-AIRM §5.15, §5.15 fn46 · auto
  ATTEST AIRM-5.19-INDEPENDENT-VALIDATION    validator must be independent of dev and deployment
        MAS-AIRM §5.19 · semi · inherent tier Critical
  PASS  AIRM-4.8-FN25-AGENT-ATTRIBUTES      agent identifier, tools, components, guardrails present
        MAS-AIRM §4.8 fn25 · auto
```

## What is in the box

| Module | Serves | What it does |
|---|---|---|
| `airm.catalog` | §1.1–§1.8 | 65 paragraphs and 51 footnotes as data: tags, effective dates, agent attributes, GenAI failure modes |
| `airm.inventory` | §4.5–§4.9, fn25 | Pydantic models for use cases, with an `AgentExtension` for tools, permissions, components and guardrails; register diff and completeness scoring |
| `airm.materiality` | §4.10–§4.13 | Impact / Complexity / Reliance scoring from a YAML rubric; inherent and residual tiers; every score carries its reasons |
| `airm.controls` | Section 5 | Control catalogue with applicability by tier, required evidence, automated checks and an automatability class |
| `airm.evals` | §5.14–§5.15 | Adapters that read `inspect-ai`, `promptfoo`, `deepeval`, `ragas` and `garak` output and map it to controls; agent tool-scope audit |
| `airm.monitor` | §5.17, §5.23 | Hash-chained JSONL evidence and incident log |
| `airm.thirdparty` | §5.10–§5.11 | Vendor assessment records, independent-assessment vs self-attestation, limit/suspend/replace decision |
| `airm.crosswalk` | — | MAS-AIRM ↔ ISO/IEC 42001, NIST AI RMF (+ GenAI Profile), EU AI Act, FEAT |
| `airm.scan` | §4.2, §4.4 | Shadow-AI discovery: LLM SDK imports, model endpoints, MCP server configs, agent frameworks, vendor AI SaaS |
| `airm.report` | — | Markdown → DOCX/PDF audit pack |

JSON Schemas for every model live in [`schemas/`](schemas/), so a GRC platform or a spreadsheet can
adopt the formats without Python — regenerate them with `airm schemas`.

Full documentation, including a concepts guide, the CLI reference and a cookbook, is at
**<https://thanatchon36.github.io/airmkit/>** (`make docs` builds it locally).

## The paper

*Operationalising the MAS Guidelines on AI Risk Management for LLM and Agentic Systems: A
Machine-Checkable Control Catalogue and Empirical Study.*

| | |
|---|---|
| 📄 **Read it on the web** | **<https://thanatchon36.github.io/airmkit/paper/>** |
| ⬇️ **Download the PDF** (22 pp) | **[`paper/paper.pdf`](paper/paper.pdf)** — [direct download](https://github.com/thanatchon36/airmkit/raw/main/paper/paper.pdf) |
| 📝 Markdown source | [`paper/paper.md`](paper/paper.md), rendered from [`paper/paper.md.in`](paper/paper.md.in) |
| 🔢 Every number in it | injected from [`results/summary.json`](results/summary.json); nothing is typed by hand |
| 📋 One page for a CRO | [`docs/EXEC_SUMMARY.md`](docs/EXEC_SUMMARY.md) |

## Research

The repository is also a reproducible study of how far these Guidelines can be machine-checked.
Five questions, thresholds fixed in advance, in [`docs/RESEARCH_QUESTIONS.md`](docs/RESEARCH_QUESTIONS.md):
automatability of each expectation, how autonomy changes materiality, measured guardrail failure
rates on a local model, crosswalk coverage, and the shape of the compliance workload.

Of 17 pre-registered hypotheses, 10 held and **7 were refuted** — including that the guardrail
patterns which suppress attacks also refuse half of benign in-scope requests, and that what an
ISO 42001 + NIST-aligned institution still owes is governance machinery rather than the agent
clauses. All of them are reported, with the thresholds they failed.

```bash
make reproduce     # rebuilds every table and figure in paper/paper.md
make quick         # under 5 minutes, no model calls
```

Results are in [`results/summary.json`](results/summary.json), the figures in
[`results/figures/`](results/figures/) with their captions, and the write-up in
[`paper/paper.md`](paper/paper.md) ([PDF](paper/paper.pdf),
[web](https://thanatchon36.github.io/airmkit/paper/)). `make paper` rebuilds all three.

## Clause index

Every paragraph of the Guidelines maps to the module, control and CLI command that implements it.
The table is generated from the catalogue, never hand-maintained:

```bash
airm clauses --format markdown        # or: make docs
```

## Development

```bash
make setup      # uv venv -p 3.11 and an editable install with every extra
make quick      # lint, fast tests and the worked example — under 5 minutes
make test lint  # full suite with coverage; ruff + mypy --strict
make help       # every target
```

Generated files (`schemas/`, `results/summary.json`, `paper/paper.md`, `docs/EXEC_SUMMARY.md`,
`docs/posts/*.md`, `docs/clause-index.md`) have staleness tests: edit the source, then run
`make schemas paper docs`.

## Contributing

The most useful contributions are new crosswalks (HKMA, BNM, Bank of Thailand, APRA), new eval
adapters, and challenges to the interpretations in
[`docs/INTERPRETATIONS.md`](docs/INTERPRETATIONS.md) — if you read a paragraph differently, open an
issue and say which paragraph. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Citation

```bibtex
@software{airmkit,
  author  = {Chongmankhong, Thanatchon},
  title   = {airmkit: Operationalising the MAS Guidelines on AI Risk Management
             for LLM and Agentic Systems},
  year    = {2026},
  url     = {https://github.com/thanatchon36/airmkit},
  version = {0.1.0}
}
```

See [CITATION.cff](CITATION.cff). Release notes are in [CHANGELOG.md](CHANGELOG.md).

## Licence

Apache-2.0. The MAS documents reproduced under `docs/sources/` remain MAS copyright and are
included only so that every citation in this repository can be verified offline.
