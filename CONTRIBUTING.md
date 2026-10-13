# Contributing

This repository exists so that the work of turning the MAS Guidelines into checkable controls is
done once, in public, and argued with. Disagreement is the most useful contribution: if you read a
paragraph differently, say which paragraph.

By contributing you agree your contribution is licensed under Apache-2.0.

## The rules that are not negotiable

These come from `MISSION.md` and keep the project usable by an auditor:

1. **Every control, field, score and claim cites a paragraph.** `MAS-AIRM §5.19`, `§4.8 fn25`. A
   control with no clause reference will not be merged. Never invent a requirement.
2. **Never paraphrase the Guidelines as if they were quoting them.** Summaries are the authors'
   words and are labelled as such. The primary text is the ground truth.
3. **MAS prescribes no materiality formula, metric or testing threshold** (Response to Feedback
   §7.19, §10.28-§10.29, §10.66). Any number of that kind is labelled as a proposal, in the code
   and in the output.
4. **Not legal advice, not affiliated with MAS.** The disclaimer stays in the README, the package
   docstring, every generated document and the paper.
5. **No real institution data.** Examples use the fictional Merlion Commercial Bank and synthetic
   evaluation data.
6. **Where a paragraph reads two ways**, implement the stricter reading as the default, expose the
   lenient one as configuration, and document both in `docs/INTERPRETATIONS.md`.
7. **Local models only.** Anything in `make reproduce` runs on a laptop with no hosted API.

## Setup

```bash
git clone https://github.com/thanatchon36/airmkit && cd airmkit
make setup            # uv venv -p 3.11 + editable install with all extras
make quick            # lint, fast tests, worked example — under 5 minutes
```

Before every commit: `make quick`. Before a release: `make reproduce`.

## What is most useful to contribute

### A crosswalk to another regulator

The clearest contribution. HKMA, BNM, Bank of Thailand, APRA CPS 230/234, RBI, the EU AI Act GPAI
chapter, ISO/IEC 42005. Add rows to the data files under `src/airm/crosswalk/`, with:

- the MAS-AIRM paragraph and the other framework's provision, both cited precisely;
- a coverage judgement of `full`, `partial` or `none`;
- a confidence of `high`, `medium` or `low`;
- a one-line note saying *why* — especially for `partial`, where the usual reasons are narrower
  scope, optionality, or a different legal character.

Count an unmapped expectation against coverage. Do not drop it from the denominator.

### A new eval adapter

`airm.evals` maps existing harness output to controls; it is not a harness. An adapter takes a
file a tool already writes, returns an `EvalResult`, records the model, digest, seed and
temperature (§5.17), and maps failures to the fn46 failure modes. Treat the input as untrusted
data: no imports, no `exec`, size caps, secrets redacted.

### A control, or a challenge to one

A new control needs: an id, its clause references, applicability by tier and scope, the evidence
items it requires, an automatability class with a written justification, and a check if the class
is `auto` or `semi`. Remember that **a `semi` control never reports `PASS`** — a passing automated
check becomes `NEEDS_ATTESTATION`, by design.

A challenge to an existing control is equally welcome. Open an issue titled with the paragraph
(`§5.19: validator independence test is too strict`) and say what the control asserts, what you
think the paragraph requires, and what evidence would settle it.

### A rubric variant

Institution-specific rubrics are expected. If yours is general enough to be useful to others, add
it under the rubric directory with a short note on what it changes and why, keeping a `clause` on
every signal.

## Code standards

- Python 3.11+, `pydantic` v2 schemas, `typer` CLI, type hints throughout.
- `ruff check`, `ruff format --check` and `mypy --strict` must pass (`make lint`).
- Tests for every change; the suite is at 96% coverage and should stay above 85%.
- Every public function's docstring names the MAS paragraph(s) it serves.
- Enum care: `Coverage`, `Level` and `Tier` are `StrEnum`s — never `max()` them directly
  (alphabetically `"full" < "partial"`, which silently understates coverage). Use
  `max(..., key=lambda c: c.rank)`. And a `StrEnum` member must not shadow a `str` method.
- `.zenodo.json` is the metadata Zenodo reads when it archives a release. Bump `version` there in
  the same commit as `airm.__version__`, `CITATION.cff` and `CHANGELOG.md`.
- Generated files are generated: `schemas/`, `results/summary.json`, `paper/paper.md`,
  `paper/paper.pdf`, `docs/paper/index.html`, `docs/EXEC_SUMMARY.md`, `docs/posts/*.md` and
  `docs/clause-index.md` are build artefacts with staleness tests. Edit the source (`*.md.in`,
  the models, the experiments), then run `make schemas paper docs`. The PDF and the web reader
  need pandoc 3.x on the system; the `typst` wheel in the `paper` extra bundles the compiler.

## Changing an experiment

The research half is pre-registered. Hypotheses, metrics and thresholds are in
`docs/RESEARCH_QUESTIONS.md` and were fixed before the experiments ran.

- Do not retune a threshold to change a verdict. If an implementation detail forces a change to a
  pre-registered construct, report the original hypothesis as refuted **on its original wording**,
  label the revision as not pre-registered, and record why in the result file's
  `post_hoc_disclosure`. RQ2 is the worked example of this.
- Keep refutations. Seven of seventeen hypotheses are refuted and all of them are published; a
  pull request that quietly drops one will be declined.
- Calibrate instruments on the control condition only, never on the condition whose result you
  care about. RQ3's `detector_calibration` block explains why.
- Record every threat to validity you notice in the result file. The paper assembles its Threats
  section from them.

## Reporting a security issue

`airm.scan` reads untrusted repositories and `airm.evals` parses untrusted tool output. If you
find a path traversal, an arbitrary-execution route, a secret leaking into output or a resource
exhaustion, please open a private security advisory on GitHub rather than a public issue.

## Pull requests

Small, tested, one topic. In the description, name the paragraph(s) your change serves, say
whether any generated file was regenerated, and paste the `make quick` result. If your change
affects a number in the paper, run `make paper` and commit the regenerated output in the same
pull request so the prose and the results never disagree.
