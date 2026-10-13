# Design decisions

Format: **D-n — decision.** What / why / alternatives rejected. Newest at the bottom.

**D-1 — Package name `airmkit`, import `airm`, CLI `airm`.** Neutral (no "MAS" in the name), available on PyPI (404 on 2026-10-13). Rejected: `masairm` (implies endorsement), `airg` (collides with the consultation's own abbreviation).

**D-2 — Primary sources are vendored as PDFs with SHA-256.** Lets every citation be checked offline and lets `make reproduce` re-extract text. Rejected: URLs only (MAS site blocks default curl; links rot).

**D-3 — Catalogue is a hand-authored YAML, not auto-parsed.** The PDF text extraction is reliable, but the paragraph structure (lettered items, footnotes that attach to sub-items) needs judgement. A hand-built file reviewed against the PDF is the ground truth; a test asserts that every paragraph id 1.1–6.3 is present and that every summary is ≤40 words. Rejected: regex parser (brittle, would drift on the next MAS revision).

**D-4 — Effective dates taken from §1.8 as clarified by Response §13.5.** See INTERPRETATIONS I-1.

**D-5 — Materiality rubric: three dimensions, four levels, max-with-gate combination.** MAS does not prescribe combination (Response §7.19). "Max" is the strictest common reading; the gate (Complexity/Reliance cannot lift the tier more than one level above Impact) implements Response §7.9 (Complexity is not standalone) and §7.5 (anchor on consequences of failure). Alternatives rejected: weighted sum (hides a single critical dimension), Impact-only (ignores §4.12(b)(c)).

**D-6 — Automatability classes (RQ1): `auto`, `semi`, `doc`.** `auto` = a machine can decide pass/fail from artefacts the toolkit ingests; `semi` = a machine can detect presence/absence but a human must attest adequacy; `doc` = purely documentary/organisational. Used by `airm check` to decide between pass/fail and needs-attestation.

**D-7 — Evidence records are hash-chained JSONL, not a database.** Append-only, diffable, works in git and in a GRC upload. Rejected: SQLite (harder to audit by eye), Merkle tree (overkill for v0.1).

**D-8 — Eval adapters wrap existing tools; the toolkit never ships its own LLM harness.** MISSION constraint. v0.1 ships adapters for `inspect-ai` log format, `promptfoo` JSON output, `deepeval`/`ragas` result dicts, `garak` report JSONL, plus a built-in *guardrail probe runner* that only orchestrates prompts against an Ollama/mock backend and records outcomes (it is an evidence recorder, not an eval framework).

**D-9 — Local model for RQ3 is `qwen3.5:0.8b` via Ollama.** Already present on the target machine, ≤4B, fast on an M4 Air. Outputs cached under `results/cache/` with seed and model digest so CI uses the cache and never calls Ollama.

**D-10 — One repository, `src/` layout, `uv` lockfile committed.** Standard for reproducibility.
