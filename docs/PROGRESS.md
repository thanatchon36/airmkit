# Progress

Status of each MISSION phase. Update before compacting context so work can resume from here.

## Phase 1 — Clause extraction & literature — **shipped**
- All primary sources acquired from mas.gov.sg with a browser user-agent (default curl is blocked).
  11 files under `docs/sources/` with SHA-256 in `MANIFEST.md` and `SHA256SUMS`. Text extracts
  under `docs/sources/text/` carry page markers so every citation is traceable.
- `src/airm/catalog/mas_airm_2026.yaml`: 65 paragraphs (51 expectations), 51 footnotes, closed tag
  vocabulary, effective dates per §1.8 and Response §13.5.
- `docs/WHAT_CHANGED.md`: 36 consultation-to-final changes plus a full paragraph concordance.
- `docs/literature/REVIEW.md` + `refs.bib`: 51 sources, gap table of 13 expectations with no
  established implementation pattern.

## Phase 2 — Research questions — **shipped**
- `docs/RESEARCH_QUESTIONS.md`: RQ1 automatability, RQ2 autonomy and materiality, RQ3 guardrail
  effectiveness, RQ4 crosswalk coverage, RQ5 cost of compliance. Each with hypothesis, refuting
  experiment, metric and a threshold fixed before running.

## Phase 3 — Library core — **shipped**
- `airm.catalog` typed clause index; `airm.inventory` with `AgentExtension` (§4.8 fn25), register
  diff and change-significance classes; `airm.materiality` 23-signal rubric with inherent and
  residual tiers; `airm.controls` 65 controls (20 auto / 24 semi / 21 doc) over 53 paragraphs, use
  case and institution scope, 21 check functions; `airm.monitor` hash-chained trail with tamper
  detection; `airm.thirdparty` over the eight §5.11 considerations; `airm.scan` 36 signals;
  `airm.evals` adapters for inspect-ai, promptfoo, garak, ragas, deepeval plus fairness disparity
  and agent tool-scope audit; `airm.evals.probes` 20-probe guardrail suite with mock and Ollama
  backends; `airm.crosswalk` 192 mapping rows; `airm.report` audit pack; `airm.cli` nine commands.
- `ruff` clean, `mypy --strict` clean on the whole package.
- Only §2.2 has no implementing control, and that is deliberate: it is the roll-up clause that
  says Sections 3-6 apply unless §2.3 does, so it is satisfied by the catalogue as a whole.

## Phase 4 — Worked example & experiments — **in progress**
- Shipped: `examples/synthetic_bank/` with 8 fictional use cases spanning Medium to Critical,
  3 vendor assessments, 266 synthetic evidence files and a 14-record audit trail. `airm report`
  produces 9 documents; outcomes are 68 pass, 30 fail, 272 needs-attestation, 94 not-applicable.
- Open: `experiments/rq1..rq5_*.py`, `results/summary.json`, figures, `make` targets.

## Phase 5 — Paper & communications — open
## Phase 6 — Packaging, docs, publication — open
- `pyproject.toml`, `README.md`, `LICENSE`, `DISCLAIMER.md` shipped. Open: tests, CI, mkdocs site,
  `CONTRIBUTING.md`, `CITATION.cff`, release workflow, `Makefile`.

## Decisions taken while building (see DECISIONS.md for the full list)
- Added `AutonomyLevel.AUTONOMOUS_DECISIONING` distinct from `AUTONOMOUS_AGENT`. A fraud model
  that blocks without human review is fully autonomous under §4.12(c) but has no tools, so the
  §4.8 fn25 agent attributes do not apply to it. Conflating the two would demand tool allowlists
  from a scoring model and understate the distinct agent risk of §1.11.
- Impact signals are gated on `regulated_domain_exposure` rather than on a domain tag alone.
  Domain adjacency is not consequence: an internal research assistant with analyst sign-off does
  not carry the impact of the model that prices a customer's loan (§4.12(a), §2.2 fn12).
- Under the default rubric no Generative AI use case can be rated Low, because GenAI sets
  Complexity to High and the impact gate permits one level above Impact. Reported as a finding
  rather than engineered away.

## Open issues
- The `semi` automatability class means a passing automated check still reports
  `needs_attestation`. Correct by design but it dominates the counts; the board summary now
  distinguishes a genuine FAIL from an attestation.
- `AIRM-5.19` independent-validation independence test relies on role parties being named
  distinctly; an FI that records roles loosely will get a false negative.
