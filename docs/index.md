# airmkit

**Operationalise the MAS Guidelines on AI Risk Management for LLM and agentic AI systems — and
measure how far that is possible.**

!!! warning "Not affiliated with MAS. Not legal or regulatory advice."
    Independent open-source project. Every interpretation and every threshold is the authors';
    MAS declines to prescribe materiality formulae, metrics or testing methodologies (Response to
    Feedback §7.19, §10.28, §10.66). See the
    [disclaimer](https://github.com/thanatchon36/airmkit/blob/main/DISCLAIMER.md).

The Monetary Authority of Singapore issued its *Guidelines on Artificial Intelligence Risk
Management* on 7 October 2026. Sections 3–4 — oversight, identification, inventory and risk
materiality — bind from **7 October 2027**; Sections 5–6 — lifecycle controls and capability —
from **7 October 2028** (§1.8). The text is thirty pages of principles, and the regulator is
explicit that it prescribes no formula, metric or threshold.

`airmkit` turns those principles into artefacts an engineer can produce and an auditor can read:
a machine-readable clause catalogue, an AI inventory schema with first-class support for agents,
a transparent risk-materiality rubric whose every signal cites a paragraph, a control catalogue
in which every control cites the paragraph it serves, evidence records that cannot be quietly
edited, and an audit pack. The same repository is a pre-registered study of how much of the
Guidelines can be machine-checked, with every refutation reported.

## Read the study

<div class="grid cards" markdown>

- :material-book-open-page-variant: **[The paper, on the web](https://thanatchon36.github.io/airmkit/paper/)**

    One reading column, the abstract, every pre-registered verdict, the full text with figures
    and references. Written by Claude Fable 5.1 from the author's results.

- :material-file-pdf-box: **[The paper as PDF](https://github.com/thanatchon36/airmkit/raw/main/paper/paper.pdf)**

    Typeset with Typst from the same Markdown. Every number injected from `results/summary.json`.

- :material-account-tie: **[One page for a CRO](EXEC_SUMMARY.md)**

    The deadlines, what a tool can check, four findings to act on, and what to do next quarter.

- :material-table-search: **[Clause index](clause-index.md)**

    Every paragraph of the Guidelines and what in the toolkit implements it, generated from the
    catalogue.

</div>

## Install and run

```bash
pip install airmkit                 # core
pip install "airmkit[evals]"        # adapters for inspect-ai, deepeval, ragas, garak
pip install "airmkit[report,docs]"  # DOCX output and this site
```

```bash
airm init --institution "Merlion Commercial Bank"   # scaffold a register and rubric
airm scan . --out candidates.yaml                   # find AI already in your code and configs
airm report --register ai-inventory.yaml --out audit-pack/
```

Python 3.11+. No GPU, no API key and no network access are needed for the core, and
`make reproduce` rebuilds the whole study on a laptop without a hosted model.

## What the study found

Five questions with thresholds fixed before the experiments ran. Of 17 hypotheses, 10 held and 7
were refuted; all of them are reported with the thresholds they failed.

| | Finding |
|---|---|
| **Automatability** | 45.1% of expectations admit a fully automated check — 84.6% in Section 4 (inventory, materiality) and 0% in Section 3 (governance). Counted per control, the semi-automatable class dominates. |
| **Autonomy** | Moving a use case up a six-rung autonomy ladder adds controls monotonically but rarely moves its tier: tier is dominated by consequence, autonomy shows in the control set. |
| **Guardrails** | The patterns that suppress attacks also refuse 50% of benign in-scope requests. No pattern met both pre-registered thresholds; a truncation bug that produced a perfect 0% attack rate is disclosed. |
| **Crosswalk** | The ISO 42001 + NIST AI RMF + EU AI Act union leaves 35.3% of expectations with no full mapping — governance machinery and Singapore-specific proportionality, not the agent clauses. |
| **Cost** | Evidence volume is flat across tiers; proportionality scales rigour. 93.1% of estimated effort is attestation and documentation. |

The numbers above are quoted from
[`results/summary.json`](https://github.com/thanatchon36/airmkit/blob/main/results/summary.json);
the paper's threats-to-validity section says what they do and do not support.

## Where to go next

- **[Concepts](concepts.md)** — the five objects the toolkit works with, and why a `semi` control
  never reports PASS.
- **[CLI reference](cli.md)** — every command, its exit codes and the clauses it serves.
- **[Cookbook](cookbook.md)** — gate a pipeline on control failures, audit an agent's tool scope,
  map a harness result to a control, fork the rubric.
- **[What changed from the consultation](WHAT_CHANGED.md)** — 36 substantive changes with a
  paragraph concordance.
- **[Interpretations](INTERPRETATIONS.md)** — eleven ambiguous readings, the stricter one
  implemented by default.
