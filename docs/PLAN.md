# Plan

Phase-by-phase plan for the MISSION. Closed items move to `PROGRESS.md`.

## Phase 1 — Clause extraction & literature
1. Acquire primary sources (Guidelines, Response to Feedback, consultation paper, Info Paper 2024, FEAT, Veritas) → `docs/sources/`, `MANIFEST.md` with SHA-256.
2. Extract text with PyMuPDF, keep page markers → `docs/sources/text/`.
3. Hand-build `src/airm/catalog/mas_airm_2026.yaml`: every paragraph 1.1–6.3, lettered items, and footnotes that carry requirements. Fields: id, section, heading, page, kind, applies_to, effective, summary (≤40 words), tags, items, footnotes.
4. `docs/WHAT_CHANGED.md`: consultation → final diff, paragraph-referenced, cross-checked against the Response to Feedback.
5. `docs/literature/REVIEW.md` + `refs.bib` (20–30 sources) with a gap table.
6. Commit + push.

## Phase 2 — Research questions
- `docs/RESEARCH_QUESTIONS.md`: RQ1–RQ5 with hypothesis, refuting experiment, metric, threshold.

## Phase 3 — Library core
- `uv init`, pyproject (pydantic v2, typer, pyyaml, jsonschema, rich), ruff, mypy --strict, pytest ≥85 %.
- Modules in this order (each with tests): `catalog` → `inventory` → `materiality` → `controls` → `monitor` → `thirdparty` → `crosswalk` → `evals` → `scan` → `report` → `cli`.
- `schemas/` JSON Schema export via `airm schema export` (checked in CI for drift).

## Phase 4 — Worked example & experiments
- `examples/synthetic_bank/` 8 use cases (YAML inventory, rubric, evidence folders).
- `experiments/rq1..rq5_*.py` → `results/summary.json` + `results/figures/`.
- RQ3 via Ollama `qwen3.5:0.8b` (local, ≤4B) with cached seeded outputs; mock backend for CI.

## Phase 5 — Paper & comms
- `paper/paper.md` with numbers injected from `results/summary.json` via a template step; pandoc → PDF.
- `docs/EXEC_SUMMARY.md`, `docs/posts/*.md`.

## Phase 6 — Packaging, docs, publication
- mkdocs-material site with generated clause index; CI (lint+test+quick); release workflow (PyPI trusted publishing on tag); CITATION.cff; topics; v0.1.0.
