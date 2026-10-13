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

## Phase 4 — Worked example & experiments — **shipped**
- `examples/synthetic_bank/` with 8 fictional use cases spanning Medium to Critical, 3 vendor
  assessments, 266 synthetic evidence files and a 14-record audit trail. `airm report` produces
  9 documents; outcomes across use-case and institution controls are 70 pass, 30 fail,
  277 needs-attestation, 94 not-applicable.
- `experiments/rq1..rq5_*.py` with `_common.py`; five figures with committed captions; each
  result file carries `provenance`, `verdicts` and `threats_to_validity`.
- Of 17 pre-registered hypotheses, 10 held and 7 were refuted. RQ2 carries a `post_hoc_disclosure`
  for the autonomy-ladder change; RQ3 carries `detector_calibration` for two measurement defects
  (an empty-completion bug that produced a false 0% attack success rate, and five mis-calibrated
  detectors). Both stay disclosed in the paper.

## Phase 5 — Paper & communications — **shipped**
- `experiments/collect.py` merges the five RQ files and `AuditPack.summary_json()` into
  `results/summary.json`: 101 headline numbers, 17 verdicts, 5 figures, per-RQ threats and the
  disclosures. It computes nothing of its own; percentages are rendered once, in `pct()`.
- `paper/paper.md.in` plus `experiments/render_paper.py`: the paper is a build artefact with every
  number, table, figure caption and disclosure injected. An unknown placeholder raises, and a test
  asserts the committed paper is the render of the committed template and results. ~8,100 words.
- `docs/EXEC_SUMMARY.md` (one page, CRO audience) and `docs/posts/` (10 drafts, each ≤1,300
  characters, ending with the repo link) render from the same summary. Tests enforce the limit.
- `paper/paper.pdf` (22 pages) is committed and linked from the README. No LaTeX engine is
  installed on the build machine, so `experiments/make_pdf.py` takes the HTML route: pandoc with
  `paper/print.css` (A4, numbered pages, table-of-contents page) then WeasyPrint. `make paper`
  still prefers tectonic, xelatex, pdflatex or typst where one exists. The PDF build needs the
  `paper` extra and system pango and cairo, so CI does not build it; a test asserts the committed
  file exists and is a plausible PDF.
- `docs/paper.md` is a web-readable copy of the paper for the docs site, written by
  `render_paper.py`: the pandoc front matter becomes ordinary Markdown and the figures are copied
  to `docs/figures/` so they resolve under mkdocs. Live at
  <https://thanatchon36.github.io/airmkit/paper/>.

## Phase 6 — Packaging, docs, publication — **shipped**
- `Makefile`: `setup quick test lint format schemas example experiments collect paper docs
  reproduce clean publish`. Long targets run under `caffeinate -i`; `make reproduce` ends with a
  `git diff --stat` of the generated artefacts so a fresh clone can prove it reproduces the run.
- `schemas/`: 20 JSON Schemas exported by `airm schemas` from `src/airm/schemas.py`, each carrying
  the clauses it serves and the disclaimer. Tests validate the worked example, the vendor register
  and every trail record against them, and fail on a stale file.
- `mkdocs.yml` with a generated clause-index page, concepts, CLI reference and cookbook. Every
  cookbook snippet was run against the shipped example. MAS source PDFs are excluded from the
  built site (MAS copyright); they stay in the repository for offline citation checking.
- `.github/workflows/ci.yml` (lint; tests on 3.11-3.13 and macOS with an 85% coverage floor; a job
  that regenerates every artefact and fails if one is stale; a build check) and `release.yml`
  (tag-gated lint/tests, tag-vs-`__version__` check, PyPI trusted publishing, GitHub release,
  docs deploy).
- `CONTRIBUTING.md`, `CITATION.cff`, `CHANGELOG.md`; README gained development and docs sections.
- `collect.py` and `render_paper.py` keep the committed provenance block and date the paper from
  the results run, so re-rendering unchanged results is a no-op and the CI staleness gate is
  meaningful rather than always red.
- Tests: 475, coverage 96%.

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

## Phase 5-6 open issues
- The git credential helper on the build machine lacks the `workflow` OAuth scope, so pushes that
  touch `.github/workflows/` need `git push https://x-access-token:$(gh auth token)@...`.
- `paper/paper.pdf` is not committed (no LaTeX engine locally); `paper/paper.md` and the DOCX are
  the published artefacts.
- The RQ3 figure and the paper's RQ3 section quote one small local model at 16 attack trials per
  pattern. Raising n is in `docs/FUTURE_WORK.md`.

## After v0.1.0 — manuscript rewritten by Claude Fable 5.1, Typst PDF, web reader
- `paper/paper.md.in` rewritten at full academic register (~11,800 words): background on the
  Guidelines and the consultation diff, related work with citations into the 51-source review
  (IEEE numeric style via `paper/ieee.csl`), a method section covering source acquisition, the
  interpretation protocol, the automatability scheme, the rubric and the pre-registration and
  analysis protocol, results per RQ with the point-prediction/refutation-criterion distinction
  made explicit for H1, threats to validity organised by construct, internal, external and
  conclusion validity, and an authorship note. Every number is still injected;
  `results/summary.json` gained 45 further figures the text quotes (146 in all).
- `paper/paper.pdf` typeset with Typst via pandoc (`paper/airmkit.typ`): single column,
  Libertinus Serif, numbered sections, captions above tables with content-proportional column
  widths, running head, 20 pages. The `typst` wheel bundles the compiler and fonts; only pandoc
  is a system dependency.
- `docs/paper/index.html`: a self-contained web reader generated by `experiments/build_paper.py`
  from `paper/reader.html` — masthead, abstract, the strip of all 17 verdicts, two-column
  contents, embedded figures, references, colophon with the authorship disclosure. Served at
  <https://thanatchon36.github.io/airmkit/paper/>; replaces the `docs/paper.md` copy.
- README, `docs/EXEC_SUMMARY.md.in`, `docs/index.md`, `docs/concepts.md` and all ten
  `docs/posts/*.md.in` rewritten. Posts remain ≤1,300 characters, tested.
- Removed: the WeasyPrint route (`experiments/make_pdf.py`, `paper/print.css`), `docs/paper.md`,
  `docs/figures/`. DECISIONS D-11 (typesetting) and D-12 (AI authorship disclosure).

## Release status — v0.1.0 published

- Tagged `v0.1.0` and pushed; `release.yml` ran green on all four jobs (build, pypi,
  github-release, docs).
- **PyPI:** <https://pypi.org/project/airmkit/0.1.0/>, published by trusted publishing with no
  stored token. Verified by installing `airmkit` from PyPI into a clean venv and running the CLI
  against the packaged catalogue.
- **GitHub release:** <https://github.com/thanatchon36/airmkit/releases/tag/v0.1.0> with the sdist
  and wheel attached.
- **Docs:** <https://thanatchon36.github.io/airmkit/>, including the paper at
  <https://thanatchon36.github.io/airmkit/paper/>.
- **Paper PDF:** committed at `paper/paper.pdf` and linked from the README.

- **Zenodo:** GitHub integration enabled; the v0.1.0 release was re-published (same tag, notes
  and byte-identical assets) to trigger archiving. Concept DOI 10.5281/zenodo.23341671 (all versions), version DOI
  10.5281/zenodo.23341672 — <https://zenodo.org/records/23341672>. Future releases archive automatically.

Still manual: branch protection on `main`.
