# airmkit

**Operationalise the MAS Guidelines on AI Risk Management for LLM and agentic AI systems.**

!!! warning "Not affiliated with MAS. Not legal or regulatory advice."
    Independent open-source project. Every interpretation and every threshold is the authors';
    MAS declines to prescribe materiality formulae, metrics or testing methodologies (Response to
    Feedback §7.19, §10.28, §10.66). See [DISCLAIMER](https://github.com/thanatchon36/airmkit/blob/main/DISCLAIMER.md).

The Monetary Authority of Singapore issued its Guidelines on Artificial Intelligence Risk
Management on 7 October 2026. **Sections 3-4 take effect 7 October 2027** (oversight,
identification, inventory, risk materiality assessment) and **Sections 5-6 on 7 October 2028**
(lifecycle controls and capability), per §1.8.

`airmkit` turns 30 pages of principles into artefacts an engineer can produce and an auditor can
read: a machine-readable clause index, an AI inventory schema with first-class support for agents,
a transparent risk-materiality rubric, a control catalogue where every control cites a paragraph,
evidence records that cannot be quietly edited, and an audit pack.

## Install

```bash
pip install airmkit                 # core
pip install "airmkit[evals]"        # adapters for inspect-ai, deepeval, ragas, garak
pip install "airmkit[report,docs]"  # DOCX output and this site
```

Python 3.11+. No GPU, no API key and no network access needed for the core.

## Three commands

```bash
airm init --institution "Merlion Commercial Bank"   # scaffold a register and rubric
airm scan . --out candidates.yaml                   # find AI already in your code and configs
airm report --register ai-inventory.yaml --out audit-pack/
```

## Where to go next

- **[Concepts](concepts.md)** — the five objects the toolkit works with, and why a `semi` control
  never reports PASS.
- **[CLI reference](cli.md)** — every command, its exit codes and the clauses it serves.
- **[Cookbook](cookbook.md)** — gate a pipeline on control failures, audit an agent's tool scope,
  map an eval harness result to a control, fork the rubric.
- **[Clause index](clause-index.md)** — every paragraph of the Guidelines and what implements it,
  generated from the catalogue.
- **[The paper](paper.md)** — the full study, or the
  [PDF](https://github.com/thanatchon36/airmkit/raw/main/paper/paper.pdf) (22 pages).
- **[Executive summary](EXEC_SUMMARY.md)** — one page for a CRO: the deadlines, what a tool can
  check, and the four findings worth acting on.

## What the study found

The repository is also a reproducible study of how far these Guidelines can be machine-checked.
Five questions with thresholds fixed in advance; of 17 hypotheses, 7 were refuted and all of them
are reported.

| | Finding |
|---|---|
| **Automatability** | 45.1% of expectations admit a fully automated check. Section 4 is 84.6% automatable; Section 3 is 0%. |
| **Autonomy** | Moving a use case up the autonomy ladder adds controls monotonically but rarely moves its tier: tier is dominated by consequence. |
| **Guardrails** | The patterns that suppress attacks also refuse ~50% of benign in-scope requests. No pattern met both pre-registered thresholds. |
| **Crosswalk** | The ISO 42001 + NIST AI RMF + EU AI Act union leaves 35.3% of expectations with no full mapping — governance machinery, not the agent clauses. |
| **Cost** | Evidence volume is flat across tiers; proportionality scales rigour. 93.1% of estimated effort is attestation and documentation. |

Numbers here are quoted from [`results/summary.json`](https://github.com/thanatchon36/airmkit/blob/main/results/summary.json);
the paper and its threats to validity are in
[`paper/`](https://github.com/thanatchon36/airmkit/tree/main/paper).
