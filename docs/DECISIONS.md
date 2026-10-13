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

**D-11 — The paper is typeset with Typst via pandoc, and the web reader is generated from the same Markdown.** `paper/paper.md.in` renders to `paper/paper.md` (every number injected from `results/summary.json`); pandoc converts that once to Typst (`paper/airmkit.typ`: single column, Libertinus Serif, numbered sections, IEEE references through `paper/ieee.csl`) and once to HTML (`paper/reader.html`: one reading column, masthead, verdict strip built from the summary, two-column contents, embedded figures). The `typst` wheel bundles the compiler and its fonts, so the build needs only pandoc from the system. Rejected: LaTeX (no engine on the build machine, heavy install, no better output for a working paper); WeasyPrint (needs system pango/cairo and gave plain output); hand-maintaining a second HTML copy of the prose (it drifted within a day).

**D-12 — The manuscript was written by Claude Fable 5.1 and says so.** The prose of `paper/paper.md.in`, the executive summary and the post drafts were written by the model from the author's catalogue, experiments and result files, under the standing constraints: every number injected, every refutation and instrument defect reported, the rubric and thresholds labelled as proposals, the disclaimer everywhere. The author reviewed and is responsible for the content. The disclosure is in the paper's acknowledgements, the reader page's colophon and the README. Rejected: silent assistance (a reader of a pre-registered study is owed the provenance of its prose as much as of its numbers).

**D-13 — Figures are drawn from result files, at the PDF text width, in the body typeface.** `experiments/figures.py` holds every figure and its caption as a function of one `results/*.json`; the experiment scripts call it after writing their result. Width is the Typst text block (16.4 cm) so 8 pt in the figure prints at 8 pt; Libertinus Serif is vendored so output does not depend on the machine; the PDF gets SVG (text as paths), the reader PNG. Ordered categories use validated one-hue ramps rather than red/amber/green, which fails for deuteranopes and in greyscale. Rejected: drawing inside each experiment (RQ3 could not be redrawn without a live model); `bbox_inches="tight"` (changes the saved width, so Typst rescales the text); matplotlib's DejaVu Sans (mismatched the body face).
