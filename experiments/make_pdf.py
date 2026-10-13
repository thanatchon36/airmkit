"""Build paper/paper.pdf (and paper/paper.html) from paper/paper.md.

MISSION Phase 5 asks for the paper as a PDF via pandoc. The build machine has no LaTeX engine, so
this script takes the HTML route: pandoc renders the Markdown with ``paper/print.css``, and
WeasyPrint turns that into a paginated PDF. The result is a plain working paper with numbered
pages, a table of contents and the figures at their committed resolution.

``make paper`` prefers a LaTeX or typst engine where one is installed and falls back to this.

macOS note: WeasyPrint loads Pango and GObject through ``ctypes``, which searches
``DYLD_FALLBACK_LIBRARY_PATH``. A shell cannot export that variable into a child process (System
Integrity Protection strips ``DYLD_*``), so the Homebrew library directory is added to the
environment here, before WeasyPrint is imported.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from _common import REPO, banner

PAPER_DIR = REPO / "paper"
MARKDOWN = PAPER_DIR / "paper.md"
HTML = PAPER_DIR / "paper.html"
PDF = PAPER_DIR / "paper.pdf"
CSS = PAPER_DIR / "print.css"

# Homebrew's library directory on Apple silicon and on Intel, plus the common Linux locations.
_LIBRARY_DIRS = ("/opt/homebrew/lib", "/usr/local/lib")


def _ensure_library_path() -> None:
    """Put Homebrew's libraries where ctypes will find them, before WeasyPrint is imported."""
    if sys.platform != "darwin":
        return
    existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    parts = [part for part in existing.split(":") if part]
    for directory in _LIBRARY_DIRS:
        if Path(directory).is_dir() and directory not in parts:
            parts.append(directory)
    # The default fallback list is lost once the variable is set, so restore its usual entries.
    for default in (str(Path.home() / "lib"), "/usr/local/lib", "/usr/lib"):
        if default not in parts:
            parts.append(default)
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(parts)


def build_html() -> Path:
    """Render paper/paper.md to a standalone HTML file with the print stylesheet.

    Returns:
        The path written.

    Raises:
        FileNotFoundError: If pandoc or the rendered Markdown is missing.
        subprocess.CalledProcessError: If pandoc fails.
    """
    pandoc = shutil.which("pandoc")
    if pandoc is None:
        raise FileNotFoundError("pandoc not found; install pandoc (brew install pandoc)")
    if not MARKDOWN.is_file():
        raise FileNotFoundError(f"{MARKDOWN} not found; run `python experiments/render_paper.py`")
    subprocess.run(
        [
            pandoc,
            MARKDOWN.name,
            "-o",
            HTML.name,
            "--standalone",
            "--toc",
            "--toc-depth=2",
            f"--css={CSS.name}",
            "--metadata",
            "lang=en-GB",
        ],
        cwd=PAPER_DIR,
        check=True,
    )
    return HTML


def build_pdf() -> Path:
    """Convert the rendered HTML to a paginated PDF.

    Returns:
        The path written.

    Raises:
        RuntimeError: If WeasyPrint is not installed or cannot load its native libraries.
    """
    _ensure_library_path()
    try:
        from weasyprint import HTML as WeasyprintHTML  # noqa: N811 (upstream class name)
    except (ImportError, OSError) as exc:  # OSError: native libraries missing
        raise RuntimeError(
            "PDF needs weasyprint and its Pango/cairo libraries: "
            "`uv pip install weasyprint` and, on macOS, `brew install pango cairo`. "
            "paper/paper.html was still written."
        ) from exc

    # base_url resolves ../results/figures/*.png relative to the paper directory, so the figures
    # are not duplicated into the HTML.
    WeasyprintHTML(filename=str(HTML), base_url=str(PAPER_DIR)).write_pdf(str(PDF))
    return PDF


def main() -> None:
    """Build the HTML and then the PDF, reporting what was written."""
    banner("make_pdf: paper/paper.md -> paper/paper.html -> paper/paper.pdf")
    html = build_html()
    print(f"  {html.relative_to(REPO)}: {html.stat().st_size // 1024} KiB")
    pdf = build_pdf()
    print(f"  {pdf.relative_to(REPO)}: {pdf.stat().st_size // 1024} KiB")


if __name__ == "__main__":
    main()
