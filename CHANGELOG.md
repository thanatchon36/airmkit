# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[semantic versioning](https://semver.org/).

## [0.1.0] — 2026-10-13

First public release: the library, the worked example and the study behind it.

### Library

- **`airm.catalog`** — all 65 paragraphs of the MAS Guidelines on Artificial Intelligence Risk
  Management (7 October 2026) as data, with 51 footnotes (29 of them normative), tags, effective
  dates and the source SHA-256.
- **`airm.inventory`** — Pydantic v2 models for an AI use case per §4.7 and fn24, with an
  `AgentExtension` carrying the fn25 agent attributes; register load/save, diff and completeness
  scoring.
- **`airm.scan`** — shadow-AI discovery over a repository (§4.2 fn21, §4.4 fn22) across 36
  signals, emitting candidate inventory entries. Scan output is treated as untrusted data.
- **`airm.materiality`** — a YAML rubric scoring Impact, Complexity and Reliance (§4.12) from 23
  signals, each citing its paragraph, producing inherent and residual tiers with reasons.
- **`airm.controls`** — 65 controls over 53 paragraphs in 20 families, with applicability by tier
  and scope, required evidence, 21 automated checks and an automatability class.
- **`airm.evals`** — adapters for `inspect-ai`, `promptfoo`, `garak`, `ragas` and `deepeval`, a
  fairness disparity check, an agent tool-scope audit (§5.23(a)) and a 20-probe guardrail suite
  with mock and Ollama backends (§5.15 fn46).
- **`airm.monitor`** — append-only hash-chained JSONL audit trail with tamper detection and
  evidence digests (§5.23(d)); incident schema per fn20.
- **`airm.thirdparty`** — vendor assessments over the eight §5.11 considerations, with the
  limit/suspend/replace decision record.
- **`airm.crosswalk`** — 224 mapping rows to ISO/IEC 42001, the NIST AI RMF and its Generative AI
  Profile, the EU AI Act, MAS FEAT and the MAS Information Paper (2024), with a query API.
- **`airm.report`** — the audit pack: board one-pager, inventory register, materiality report,
  control applicability statement, gap analysis by effective date, crosswalk coverage, clause
  index, third-party report and `summary.json`; Markdown with DOCX output.
- **`airm.schemas`** — 20 JSON Schemas so non-Python tools can adopt the formats.
- **CLI** — `airm version | init | scan | assess | check | evidence | report | gap | crosswalk |
  clauses | schemas`, with meaningful exit codes for pipelines.

### Worked example

- `examples/synthetic_bank/` — the fictional Merlion Commercial Bank: 8 synthetic use cases from
  Medium to Critical, 3 vendor assessments, 266 synthetic evidence files and a 14-record
  hash-chained trail. No real institution data anywhere in this project.

### Research

- `docs/RESEARCH_QUESTIONS.md` — RQ1-RQ5 with hypotheses, metrics and thresholds fixed before the
  experiments ran.
- `experiments/` and `results/` — five experiments, five figures, `summary.json`. Of 17
  pre-registered hypotheses, 10 held and 7 were refuted; all are reported, including the RQ2
  post-hoc ladder change and the two RQ3 measurement defects.
- `paper/paper.md` — the study, rendered from `results/summary.json` with no number typed by hand.
- `docs/EXEC_SUMMARY.md`, `docs/posts/` — a one-page summary for risk leaders and ten drafts.
- `docs/literature/REVIEW.md` — 51 sources with a gap table; `docs/WHAT_CHANGED.md` — 36 changes
  from the November 2025 consultation draft with a full paragraph concordance;
  `docs/INTERPRETATIONS.md` — 11 ambiguous readings, stricter one implemented by default.

### Known limitations

- The automatability classification and the crosswalk are single-annotator judgements; no
  inter-rater agreement is available. 18 of 224 crosswalk rows are flagged low confidence.
- RQ3 is measured on one small local model with 16 attack trials per pattern: a demonstration that
  the measurement is possible, not an estimate of guardrail effectiveness in general.
- The portfolio is synthetic and was written by the same person as the rubric, so no result
  generalises to a real portfolio without restating it as a hypothesis.
- Person-hour figures are the authors' estimates from a published table, not measurements.
- Under the default rubric no generative-AI use case can be rated Low; reported as a finding.

[0.1.0]: https://github.com/thanatchon36/airmkit/releases/tag/v0.1.0
