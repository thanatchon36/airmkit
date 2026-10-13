"""Typeset paper/paper.md into paper/paper.pdf and the web reader docs/paper/index.html.

Two outputs from one source. ``paper/paper.md`` (itself rendered from ``paper/paper.md.in`` by
``render_paper.py``, with every number injected from ``results/summary.json``) is converted by
pandoc twice:

* to Typst with ``paper/airmkit.typ`` and compiled to PDF by the ``typst`` package (single
  column, Libertinus Serif, numbered sections, IEEE references via ``paper/ieee.csl``);
* to HTML with ``paper/reader.html``, a single reading column with a masthead, the abstract, the
  strip of pre-registered verdicts, a two-column contents list, the article and the references,
  with the figures embedded so the page is one self-contained file.

The verdict strip, the masthead metadata and the colophon are built here from the summary, not
typed, for the same reason the paper's numbers are injected: a refutation that was quietly
dropped from the page would be invisible to a reader.

Run with ``PYTHONPATH=experiments .venv/bin/python experiments/build_paper.py`` or ``make paper``.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from _common import REPO, RESULTS, banner

PAPER_DIR = REPO / "paper"
MARKDOWN = PAPER_DIR / "paper.md"
TYPST_SOURCE = PAPER_DIR / "paper.typ"
PDF = PAPER_DIR / "paper.pdf"
TYPST_TEMPLATE = PAPER_DIR / "airmkit.typ"
HTML_TEMPLATE = PAPER_DIR / "reader.html"
READER = REPO / "docs" / "paper" / "index.html"
BIBLIOGRAPHY = REPO / "docs" / "literature" / "refs.bib"
CSL = PAPER_DIR / "ieee.csl"
SUMMARY = RESULTS / "summary.json"

REPO_URL = "https://github.com/thanatchon36/airmkit"
PDF_URL = f"{REPO_URL}/raw/main/paper/paper.pdf"
WRITER_NOTE = (
    "Manuscript written by Claude Fable 5.1 (Anthropic) from the author's catalogue, controls, "
    "pre-registered experiments and results; the author is responsible for the content."
)

_HYPOTHESIS = re.compile(r"^(H\d\([^)]*\))\s*(.*)$")


def _pandoc() -> str:
    """Return the pandoc executable, or raise with the install hint."""
    found = shutil.which("pandoc")
    if found is None:
        raise FileNotFoundError("pandoc not found; install pandoc 3.x (brew install pandoc)")
    return found


def _common_args() -> list[str]:
    """Pandoc arguments shared by the PDF and HTML builds."""
    return [
        "--from=markdown+smart",
        "--citeproc",
        f"--bibliography={BIBLIOGRAPHY}",
        f"--csl={CSL}",
        "--number-sections",
        "--wrap=none",
        "--metadata=link-citations:true",
        "--metadata=reference-section-title:References",
    ]


def build_pdf() -> Path:
    """Convert the paper to Typst and compile it.

    Returns:
        The PDF written.

    Raises:
        FileNotFoundError: If pandoc or the rendered Markdown is missing.
        subprocess.CalledProcessError: If pandoc fails.
    """
    if not MARKDOWN.is_file():
        raise FileNotFoundError(f"{MARKDOWN} not found; run `python experiments/render_paper.py`")
    subprocess.run(
        [
            _pandoc(),
            MARKDOWN.name,
            "--to=typst",
            f"--template={TYPST_TEMPLATE.name}",
            "--output",
            TYPST_SOURCE.name,
            *_common_args(),
        ],
        cwd=PAPER_DIR,
        check=True,
    )
    import typst

    typst.compile(str(TYPST_SOURCE), output=str(PDF), root=str(REPO))
    return PDF


def _verdict_items(summary: dict[str, Any]) -> str:
    """Return the verdict strip as list items, one per pre-registered hypothesis."""
    items: list[str] = []
    for row in summary["verdicts"]:
        match = _HYPOTHESIS.match(row["hypothesis"])
        label, text = (match.group(1), match.group(2)) if match else ("", row["hypothesis"])
        kind = "kept" if row["holds"] else "refuted"
        tag = "holds" if row["holds"] else "refuted"
        detail = row["detail"]
        items.append(
            f'<li class="v v-{kind}"><span class="v-id">{html.escape(label)}</span>'
            f'<span class="v-text">{html.escape(text)}'
            f"<small>{html.escape(detail)}</small></span>"
            f'<span class="v-tag">{tag}</span></li>'
        )
    return "\n".join(items)


def _meta_line(summary: dict[str, Any]) -> str:
    """Return the masthead metadata line, every figure from the summary."""
    numbers = summary["numbers"]
    provenance = summary["provenance"]
    counts = summary["verdict_counts"]
    parts = [
        f"airmkit v{provenance['airmkit_version']}",
        f"{numbers['catalogue.paragraphs']} paragraphs · {numbers['controls.total']} controls "
        f"· {numbers['rq4.mapping_rows']} crosswalk rows",
        f"<b>{counts['total']}</b> pre-registered hypotheses, <b>{counts['held']}</b> held, "
        f"<b>{counts['refuted']}</b> refuted",
        f"results run {str(provenance['generated_at'])[:10]} at {provenance['git_revision']}",
    ]
    return " · ".join(parts)


def _actions() -> str:
    links = [
        (PDF_URL, "Download PDF"),
        (f"{REPO_URL}/blob/main/paper/paper.md", "Markdown source"),
        (f"{REPO_URL}/blob/main/results/summary.json", "results/summary.json"),
        ("https://pypi.org/project/airmkit/", "pip install airmkit"),
    ]
    return "".join(f'<li><a href="{href}">{html.escape(text)}</a></li>' for href, text in links)


def _colophon(summary: dict[str, Any]) -> str:
    provenance = summary["provenance"]
    return (
        f"<p>{html.escape(WRITER_NOTE)}</p>"
        "<p>Every number, table, figure caption and disclosure on this page is injected from "
        f'<a href="{REPO_URL}/blob/main/results/summary.json">results/summary.json</a> by '
        "<code>experiments/render_paper.py</code>; nothing is typed by hand. The PDF is typeset "
        "with Typst from the same Markdown. <code>make reproduce</code> rebuilds every result "
        "from the committed sources on a laptop with no hosted API.</p>"
        f"<p>{html.escape(summary['disclaimer'])}</p>"
        f"<p>airmkit {provenance['airmkit_version']} · {provenance['git_revision']} · "
        f"Python {provenance['python']} on {provenance['platform']} · "
        f'Apache-2.0 · <a href="{REPO_URL}">{REPO_URL.removeprefix("https://")}</a></p>'
    )


def build_html() -> Path:
    """Convert the paper to the self-contained web reader.

    Returns:
        The HTML written.
    """
    if not SUMMARY.is_file():
        raise FileNotFoundError(f"{SUMMARY} not found; run `python experiments/collect.py` first")
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    rendered = subprocess.run(
        [
            _pandoc(),
            MARKDOWN.name,
            "--to=html5",
            "--standalone",
            f"--template={HTML_TEMPLATE.name}",
            "--toc",
            "--toc-depth=2",
            "--section-divs",
            "--embed-resources",
            *_common_args(),
        ],
        cwd=PAPER_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    numbers = summary["numbers"]
    fills = {
        "<!--KICKER-->": (
            "Reproducible study · MAS Guidelines on AI Risk Management · "
            f"{numbers['portfolio.use_cases']} synthetic use cases"
        ),
        "<!--META-->": _meta_line(summary),
        "<!--ACTIONS-->": _actions(),
        "<!--DISCLAIMER-->": f"<b>Disclaimer.</b> {html.escape(summary['disclaimer'])}",
        "<!--VERDICT-NOTE-->": (
            "Hypotheses, metrics and thresholds were fixed in "
            "<code>docs/RESEARCH_QUESTIONS.md</code> before the experiments ran. A verdict is "
            "mechanical against the recorded threshold; refutations are reported as found."
        ),
        "<!--VERDICTS-->": _verdict_items(summary),
        "<!--COLOPHON-->": _colophon(summary),
    }
    for token, value in fills.items():
        if token not in rendered:
            raise RuntimeError(f"{HTML_TEMPLATE.name} no longer contains {token}")
        rendered = rendered.replace(token, value)
    READER.parent.mkdir(parents=True, exist_ok=True)
    READER.write_text(rendered, encoding="utf-8")
    return READER


def main() -> None:
    """Build the PDF and the web reader, reporting sizes."""
    banner("build_paper: paper/paper.md -> paper/paper.pdf and docs/paper/index.html")
    pdf = build_pdf()
    print(f"  {pdf.relative_to(REPO)}: {pdf.stat().st_size // 1024} KiB")
    page = build_html()
    print(f"  {page.relative_to(REPO)}: {page.stat().st_size // 1024} KiB")


if __name__ == "__main__":
    main()
