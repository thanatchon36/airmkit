"""Shared helpers for the research-question experiments.

Every experiment writes its results to ``results/`` as JSON plus, where there is a figure, a PNG
and the data behind it. Nothing in the paper is hand-typed: ``experiments/collect.py`` merges the
per-RQ files into ``results/summary.json`` and ``paper/paper.md`` reads its numbers from there.

Determinism is a MISSION requirement. These scripts take no arguments that change the result, use
fixed seeds, and read only the committed synthetic portfolio.
"""

from __future__ import annotations

import datetime as dt
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
FIGURES = RESULTS / "figures"
EXAMPLE = REPO / "examples" / "synthetic_bank"
SEED = 20261013

# Brand-neutral, colour-blind-safe palette. Tiers run cool to warm so the ordering is visible
# without relying on hue discrimination alone.
TIER_COLOURS = {
    "Low": "#4C78A8",
    "Medium": "#54A24B",
    "High": "#E4A03A",
    "Critical": "#C4453C",
}
CLASS_COLOURS = {
    "auto": "#4C78A8",
    "semi": "#E4A03A",
    "doc": "#8D8D8D",
}
NEUTRAL = "#4C4C4C"
GRID = "#D9D9D9"


def git_revision() -> str:
    """Return the current git revision, or 'unknown' outside a repository."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def provenance() -> dict[str, Any]:
    """Return the reproducibility metadata every result file carries.

    Serves MAS-AIRM §5.17 in spirit: a reader should be able to tell which code, on which
    platform, produced a number.
    """
    from airm import __version__

    return {
        "airmkit_version": __version__,
        "git_revision": git_revision(),
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.machine()}",
        "seed": SEED,
        "generated_at": dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds"),
    }


def write_result(name: str, payload: dict[str, Any]) -> Path:
    """Write one experiment's result file to ``results/``.

    Args:
        name: File stem, e.g. ``"rq1_automatability"``.
        payload: The result data; provenance is added automatically.

    Returns:
        The path written.
    """
    RESULTS.mkdir(parents=True, exist_ok=True)
    target = RESULTS / f"{name}.json"
    body = {"provenance": provenance(), **payload}
    target.write_text(json.dumps(body, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return target


def read_result(name: str) -> dict[str, Any]:
    """Read one experiment's result file.

    Raises:
        FileNotFoundError: With a message naming the script that produces it.
    """
    target = RESULTS / f"{name}.json"
    if not target.is_file():
        raise FileNotFoundError(
            f"{target} not found; run `python experiments/{name}.py` first (or `make experiments`)"
        )
    return json.loads(target.read_text(encoding="utf-8"))


def new_figure(width: float = 7.0, height: float = 4.0) -> Any:
    """Return a matplotlib figure and axes with the project's plot style applied.

    Raises:
        RuntimeError: If matplotlib is not installed.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("figures need matplotlib: install airmkit[experiments]") from exc

    fig, ax = plt.subplots(figsize=(width, height))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=NEUTRAL, labelsize=9, length=0)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for label in (*ax.get_xticklabels(), *ax.get_yticklabels()):
        label.set_color(NEUTRAL)
    return fig, ax


def save_figure(fig: Any, name: str, *, caption: str) -> Path:
    """Save a figure as PNG and write its caption alongside.

    The caption is written to a sibling ``.txt`` so that the paper can include it without the
    text being duplicated in two places and drifting.
    """
    FIGURES.mkdir(parents=True, exist_ok=True)
    target = FIGURES / f"{name}.png"
    fig.tight_layout()
    fig.savefig(target, dpi=200, bbox_inches="tight", facecolor="white")
    (FIGURES / f"{name}.txt").write_text(caption.strip() + "\n", encoding="utf-8")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return target


def share(numerator: int, denominator: int) -> float:
    """Return a share rounded to four places, or 0.0 for an empty denominator."""
    return round(numerator / denominator, 4) if denominator else 0.0


def banner(title: str) -> None:
    """Print a consistent experiment header."""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def verdict(label: str, holds: bool, detail: str) -> dict[str, Any]:
    """Return a recorded hypothesis verdict, and print it.

    Thresholds were fixed in ``docs/RESEARCH_QUESTIONS.md`` before the experiments ran, so the
    verdict is mechanical rather than a judgement made after seeing the data.
    """
    mark = "HOLDS" if holds else "REFUTED"
    print(f"  [{mark:7}] {label}: {detail}")
    return {"hypothesis": label, "holds": holds, "detail": detail}
