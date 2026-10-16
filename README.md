# airmkit

**Operationalise the MAS Guidelines on AI Risk Management for LLM and agentic AI systems — and
measure how far that is possible.**

[![CI](https://github.com/thanatchon36/airmkit/actions/workflows/ci.yml/badge.svg)](https://github.com/thanatchon36/airmkit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/airmkit.svg)](https://pypi.org/project/airmkit/)
[![Python](https://img.shields.io/pypi/pyversions/airmkit.svg)](https://pypi.org/project/airmkit/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23341671.svg)](https://doi.org/10.5281/zenodo.23341671)

📄 **[Read the paper on the web](https://thanatchon36.github.io/airmkit/paper/)** ·
⬇️ **[Download the PDF](https://github.com/thanatchon36/airmkit/raw/main/paper/paper.pdf)** ·
📚 **[Documentation](https://thanatchon36.github.io/airmkit/)** ·
📋 **[One page for a CRO](docs/EXEC_SUMMARY.md)**

The Monetary Authority of Singapore issued its [Guidelines on Artificial Intelligence Risk
Management](https://www.mas.gov.sg/-/media/mas-media-library/regulation/guidelines/bd/guidelines-on-artificial-intelligence-risk-management-for-financial-institutions/guidelines-on-artificial-intelligence-risk-management.pdf)
on 7 October 2026. Sections 3–4 — oversight, identification, inventory and risk materiality —
bind from **7 October 2027**; Sections 5–6 — lifecycle controls and capability — from
**7 October 2028** (§1.8, as clarified by the Response to Feedback §13.5).

The Guidelines are thirty pages of principles, and the regulator is explicit that they
prescribe no formula, metric or threshold. `airmkit` turns the principles into artefacts an
engineer can produce and an auditor can read: a machine-readable clause catalogue, an AI
inventory schema with first-class support for agents, a transparent risk-materiality rubric
whose every signal cites a paragraph, a control catalogue in which every control cites the
paragraph it serves, evidence records that cannot be quietly edited, and an audit pack. The
same repository is a pre-registered study of how much of the Guidelines can be machine-checked,
with every refutation reported.

> **Not affiliated with MAS. Not legal or regulatory advice.** Independent open-source project.
> Every interpretation and every threshold is the authors'; MAS declines to prescribe
> materiality formulae, metrics or testing methodologies (Response to Feedback §7.19, §10.28,
> §10.66). See [DISCLAIMER.md](DISCLAIMER.md).

## Why

Most AI-governance tooling stops at a spreadsheet of policies. The hard part of these Guidelines
is not writing the policy; it is answering three questions per use case, repeatedly, with
evidence a supervisor can inspect:

1. **What AI do we actually have?** Including AI embedded in SaaS the vendor does not call AI
   (§4.2 fn21), and the shadow AI that staff adopted without asking (§4.4 fn22).
2. **How material is it?** On Impact, Complexity and Reliance (§4.12), where moving a use case
   from "staff review every suggestion" to "the agent calls the tool itself" changes the answer.
3. **Which controls bind, and can we show they work?** Including the expectation that guardrails
   be tested for *effectiveness*, not merely present (§5.15 fn46).

`airmkit` answers all three from files in your repository, and prints the paragraph behind
every answer.

## Install

```bash
pip install airmkit                 # core
pip install "airmkit[evals]"        # adapters for inspect-ai, deepeval, ragas, garak
pip install "airmkit[report,docs]"  # DOCX output and the docs site
```

Python 3.11+. No GPU, no API key and no network access are needed for the core or for
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

A `semi` control never reports `PASS`: when its automated check succeeds, the outcome is
`NEEDS_ATTESTATION`, because the toolkit has confirmed that the artefact exists and is current
but cannot judge whether it is adequate. Read that count as a work queue, not a failure count;
`airm check` exits non-zero only on a genuine `FAIL`.

## What is in the box

| Module | Serves | What it does |
|---|---|---|
| `airm.catalog` | §1.1–§1.8 | 65 paragraphs and 51 footnotes as data: tags, effective dates, agent attributes, GenAI failure modes |
| `airm.inventory` | §4.5–§4.9, fn25 | Pydantic models for use cases, with an `AgentExtension` for tools, permissions, components and guardrails; register diff and completeness scoring |
| `airm.materiality` | §4.10–§4.13 | Impact / Complexity / Reliance scoring from a YAML rubric; inherent and residual tiers; every score carries its reasons |
| `airm.controls` | Section 5 | 65 controls with applicability by tier, required evidence, automated checks and an automatability class |
| `airm.evals` | §5.14–§5.15 | Adapters that read `inspect-ai`, `promptfoo`, `deepeval`, `ragas` and `garak` output and map it to controls; agent tool-scope audit; 20-probe guardrail runner |
| `airm.monitor` | §5.17, §5.23 | Hash-chained JSONL evidence and incident log |
| `airm.thirdparty` | §5.10–§5.11 | Vendor assessment records, independent assessment vs self-attestation, limit/suspend/replace decision |
| `airm.crosswalk` | — | MAS-AIRM ↔ ISO/IEC 42001, NIST AI RMF (+ GenAI Profile), EU AI Act, FEAT, Info Paper 2024: 224 rows |
| `airm.scan` | §4.2, §4.4 | Shadow-AI discovery: LLM SDK imports, model endpoints, MCP server configs, agent frameworks, vendor AI SaaS |
| `airm.report` | — | Markdown → DOCX audit pack and `summary.json` |
| `airm.schemas` | — | 20 JSON Schemas so a GRC platform or spreadsheet can adopt the formats without Python |

Full documentation — a concepts guide, the CLI reference, a cookbook and the generated clause
index — is at **<https://thanatchon36.github.io/airmkit/>** (`make docs` builds it locally).

## The paper

*Operationalising the MAS Guidelines on AI Risk Management for LLM and Agentic Systems: A
Machine-Checkable Control Catalogue and Pre-registered Empirical Study.*

| | |
|---|---|
| 📄 **Read it on the web** | **<https://thanatchon36.github.io/airmkit/paper/>** — one reading column, the abstract, every pre-registered verdict, figures and references |
| ⬇️ **Download the PDF** | **[`paper/paper.pdf`](paper/paper.pdf)** — [direct download](https://github.com/thanatchon36/airmkit/raw/main/paper/paper.pdf); typeset with Typst |
| 📝 Markdown source | [`paper/paper.md`](paper/paper.md), rendered from [`paper/paper.md.in`](paper/paper.md.in) |
| 🔢 Every number in it | injected from [`results/summary.json`](results/summary.json); nothing is typed by hand |
| 📋 One page for a CRO | [`docs/EXEC_SUMMARY.md`](docs/EXEC_SUMMARY.md) |

The manuscript was written by Claude Fable 5.1 from the author's catalogue, experiments and
result files, under the constraint that every number is injected and every refutation and
instrument defect is reported; the author reviewed it and is responsible for its content (see
the paper's acknowledgements).

### What it found

Five research questions, thresholds fixed in [`docs/RESEARCH_QUESTIONS.md`](docs/RESEARCH_QUESTIONS.md)
before the experiments ran. Of 17 hypotheses, 10 held and **7 were refuted**; all of them are
reported with the thresholds they failed.

- **Automatability stops at the governance boundary.** 45.1% of expectations admit a fully
  automated check: 84.6% in Section 4 (inventory, materiality) and 0% in Section 3
  (governance). Counted per control, the semi-automatable class dominates. The obligations that
  bind first are the ones tooling can carry.
- **An agent raises the control set, not the tier.** Up a six-rung autonomy ladder, applicable
  controls grow monotonically, but only 1 of 4 use cases changed tier: tier is dominated by
  consequence. A review keyed on tier will miss the agent step.
- **Guardrails that are effective and unusable.** On a local model, attack success fell from 75%
  to 6% with a layered defence — which also refused 50% of benign in-scope requests. No pattern
  met both pre-registered thresholds. A truncation bug that produced a perfect 0% attack rate
  is disclosed.
- **What remains after certification is governance, not agents.** The ISO 42001 + NIST AI RMF +
  EU AI Act union leaves 35.3% of expectations with no full mapping, and the residue is the
  applicability regime, board duties, shadow AI, materiality arbitration and third-party
  accountability — not the agent clauses.
- **Proportionality scales rigour, not volume.** Evidence items are flat across tiers (91.4 at
  Critical, 92.0 at Medium); 93.1% of estimated effort is attestation and documentation.

```bash
make reproduce     # rebuilds every table and figure from the committed sources, no hosted API
make quick         # under 5 minutes, no model calls
```

Results are in [`results/summary.json`](results/summary.json), the figures in
[`results/figures/`](results/figures/) with their captions, and `make paper` rebuilds the
Markdown, the PDF and the web reader together, so the three cannot disagree.

## Clause index

Every paragraph of the Guidelines maps to the module, control and CLI command that implements
it. The table is generated from the catalogue, never hand-maintained:

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

Generated files (`schemas/`, `results/summary.json`, `paper/paper.md`, `paper/paper.pdf`,
`docs/paper/index.html`, `docs/EXEC_SUMMARY.md`, `docs/posts/*.md`, `docs/clause-index.md`)
have staleness tests: edit the source, then run `make schemas paper docs`.

## Contributing

The most useful contributions are crosswalks to other regulators (HKMA, BNM, Bank of Thailand,
APRA), eval adapters, and challenges to the interpretations in
[`docs/INTERPRETATIONS.md`](docs/INTERPRETATIONS.md) — if you read a paragraph differently, open
an issue and say which paragraph. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Citation

```bibtex
@software{airmkit,
  author  = {Chongmankhong, Thanatchon},
  title   = {airmkit: Operationalising the MAS Guidelines on AI Risk Management
             for LLM and Agentic Systems},
  year    = {2026},
  url     = {https://github.com/thanatchon36/airmkit},
  doi     = {10.5281/zenodo.23341671},
  version = {0.1.0}
}
```

The DOI above is the concept DOI (always resolves to the latest version); v0.1.0 is [10.5281/zenodo.23341672](https://doi.org/10.5281/zenodo.23341672). See [CITATION.cff](CITATION.cff). Release notes are in [CHANGELOG.md](CHANGELOG.md).

## Licence

Apache-2.0. The MAS documents reproduced under `docs/sources/` remain MAS copyright and are
included only so that every citation in this repository can be verified offline.
