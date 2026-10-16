"""Draw the paper's five figures from the committed result files.

Each figure is a pure function of one ``results/<rq>.json``, so it can be redrawn without
rerunning the experiment behind it (RQ3 needs a live model). The experiment scripts call
``render`` after writing their result; ``python experiments/figures.py`` redraws all five.

House style, chosen to sit inside the Typst PDF rather than beside it:

* Width is the PDF text block (16.4 cm), so text drawn at 8 pt prints at 8 pt. Nothing is scaled.
* Libertinus Serif, the body face, vendored in ``experiments/fonts`` (SIL OFL) so the output does
  not depend on the machine's fonts.
* No title in the image: the caption names the figure. Legends sit above the plotting area, never
  on the data.
* Ordered categories (automatability, coverage, tier) use one-hue ramps, dark for "more", so the
  order survives greyscale printing and colour-vision deficiency. Palettes were checked with the
  dataviz validator (ordinal: monotone lightness, light end at least 2:1 on white).
* PNG at 300 dpi for the web reader and docs; SVG with text as paths for the PDF.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator

from _common import FIGURES as FIGURE_DIR
from _common import read_result

FONTS = Path(__file__).resolve().parent / "fonts"
FONT_FAMILY = "Libertinus Serif"
# A4 minus the 2.3 cm side margins in paper/airmkit.typ.
TEXT_WIDTH_IN = 16.4 / 2.54

INK = "#1a1a1a"
INK_SOFT = "#555555"
RULE = "#3a3a3a"
GRID = "#e4e4e4"
LINE = "#a0a0a0"

# Ordinal blue, light to dark: the darker the bar, the more the machine (or the other framework)
# does. Validated as an ordinal ramp on white.
BLUE_RAMP = ("#86b6ef", "#2a78d6", "#0d366b")
CLASS_COLOURS = {"doc": BLUE_RAMP[0], "semi": BLUE_RAMP[1], "auto": BLUE_RAMP[2]}
COVERAGE_COLOURS = {"none": BLUE_RAMP[0], "partial": BLUE_RAMP[1], "full": BLUE_RAMP[2]}
# Ordinal orange-brown for the inherent tier, Low to Critical. Validated as an ordinal ramp.
TIER_COLOURS = {"Low": "#e99a62", "Medium": "#d4683a", "High": "#a9401b", "Critical": "#62200c"}
# Guardrail patterns are nominal. The unguarded baseline is neutral grey on purpose; the other
# four are categorical slots in an order that passes the adjacent-pair CVD check.
PATTERN_COLOURS = {
    "none": "#898781",
    "system_prompt": "#2a78d6",
    "filter": "#eb6834",
    "llm_judge": "#1baf7a",
    "layered": "#6250d6",
}
PATTERN_MARKERS = {
    "none": "o",
    "system_prompt": "s",
    "filter": "D",
    "llm_judge": "^",
    "layered": "v",
}
ON_DARK = {BLUE_RAMP[1], BLUE_RAMP[2]}

PATTERN_LABELS = {
    "none": "none",
    "system_prompt": "system prompt",
    "filter": "filter",
    "llm_judge": "LLM judge",
    "layered": "layered",
}
FAMILY_LABELS = {
    "direct_jailbreak": "Direct jailbreak",
    "indirect_injection": "Indirect injection",
    "pii_leakage": "PII leakage",
    "policy_evasion": "Policy evasion",
}
AUTONOMY_LABELS = {
    "assistive": "Assistive",
    "human_in_the_loop": "Human in\nthe loop",
    "human_over_the_loop": "Human over\nthe loop",
    "autonomous_decisioning": "Autonomous\ndecisioning",
    "autonomous_agent": "Autonomous\nagent",
    "multi_agent": "Multi-\nagent",
}
FRAMEWORK_LABELS = {
    "iso_42001": "ISO/IEC 42001",
    "nist_ai_rmf": "NIST AI RMF",
    "nist_genai_profile": "NIST AI 600-1 (GenAI)",
    "eu_ai_act": "EU AI Act",
    "mas_feat": "MAS FEAT (2018)",
    "mas_info_paper_2024": "MAS info paper (2024)",
}


def _style() -> None:
    """Register the vendored typeface and set the house rcParams."""
    for path in sorted(FONTS.glob("*.ttf")):
        font_manager.fontManager.addfont(str(path))
    plt.rcParams.update(
        {
            "font.family": FONT_FAMILY,
            "font.size": 8.5,
            "axes.labelsize": 8.5,
            "axes.labelcolor": INK,
            "axes.edgecolor": RULE,
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.axisbelow": True,
            "axes.titlesize": 8.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "xtick.color": RULE,
            "ytick.color": RULE,
            "xtick.labelcolor": INK,
            "ytick.labelcolor": INK,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "legend.fontsize": 8,
            "legend.frameon": False,
            "legend.handlelength": 1.2,
            "legend.handleheight": 0.8,
            "legend.columnspacing": 1.4,
            "legend.borderaxespad": 0.2,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "svg.fonttype": "path",
            "svg.hashsalt": "airmkit",
            "figure.dpi": 100,
            "savefig.facecolor": "white",
        }
    )


def _figure(height_in: float) -> tuple[Any, Any]:
    """Return a figure exactly one text block wide, laid out by matplotlib's constrained engine."""
    _style()
    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, height_in), layout="constrained")
    fig.get_layout_engine().set(w_pad=0.04, h_pad=0.04)
    return fig, ax


def _legend_above(ax: Any, handles: list[Any], ncols: int) -> None:
    """Put the legend in a row above the plotting area, left-aligned with it."""
    ax.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.02),
        ncols=ncols,
        borderaxespad=0.0,
    )


def _segment_label(ax: Any, x: float, y: float, text: str, fill: str) -> None:
    """Write a value inside a bar segment, in white on dark fills and ink on light ones."""
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=7.5,
        color="white" if fill in ON_DARK else INK,
    )


# --------------------------------------------------------------------------- RQ1


def draw_rq1(result: dict[str, Any]) -> tuple[Any, str]:
    """Stacked 100% bars: automatability class by section of the Guidelines."""
    by_section = result["by_section"]
    sections = list(by_section)
    fig, ax = _figure(2.75)
    width = 0.5
    bottoms = [0.0] * len(sections)
    for klass in ("auto", "semi", "doc"):
        values = [by_section[s][klass] * 100 for s in sections]
        ax.bar(
            range(len(sections)),
            values,
            bottom=bottoms,
            width=width,
            color=CLASS_COLOURS[klass],
            edgecolor="white",
            linewidth=0.8,
        )
        for index, (value, bottom) in enumerate(zip(values, bottoms, strict=True)):
            if value >= 12:
                _segment_label(ax, index, bottom + value / 2, f"{value:.0f}%", CLASS_COLOURS[klass])
        bottoms = [b + v for b, v in zip(bottoms, values, strict=True)]
    ax.set_xticks(
        range(len(sections)),
        [f"§{s}\nn = {by_section[s]['total']}" for s in sections],
    )
    ax.tick_params(axis="x", length=0, pad=4)
    ax.set_xlim(-0.55, len(sections) - 0.45)
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 25))
    ax.set_ylabel("Share of expectation paragraphs (%)")
    ax.set_xlabel("Section of the Guidelines")
    ax.grid(axis="y")
    _legend_above(
        ax,
        [Patch(facecolor=CLASS_COLOURS[k], label=k) for k in ("auto", "semi", "doc")],
        ncols=3,
    )
    caption = (
        "Automatability of MAS-AIRM expectation paragraphs by section, as implemented by this "
        "toolkit. auto: a deterministic function of the inventory entry and its evidence "
        "decides pass/fail. semi: presence and currency of the artefact is machine-checkable "
        "but adequacy needs human attestation. doc: organisational or judgemental, with no "
        "artefact the toolkit inspects. Classification is the authors' judgement relative to "
        "this implementation, not a MAS classification."
    )
    return fig, caption


# --------------------------------------------------------------------------- RQ2


def _spread(positions: list[float], gap: float) -> list[float]:
    """Push sorted label positions apart until neighbours are at least ``gap`` apart."""
    order = sorted(range(len(positions)), key=lambda i: positions[i])
    placed = [positions[i] for i in order]
    for i in range(1, len(placed)):
        placed[i] = max(placed[i], placed[i - 1] + gap)
    # Recentre so the block of labels stays centred on the points it labels.
    shift = (sum(placed) - sum(positions[i] for i in order)) / len(placed)
    placed = [p - shift for p in placed]
    for i in range(1, len(placed)):
        placed[i] = max(placed[i], placed[i - 1] + gap)
    result = [0.0] * len(positions)
    for slot, i in enumerate(order):
        result[i] = placed[slot]
    return result


def draw_rq2(result: dict[str, Any]) -> tuple[Any, str]:
    """Applicable controls against autonomy, one line per use case, tier as marker fill."""
    ladder = result["ladder"]
    ladders: dict[str, list[dict[str, Any]]] = result["ladders"]
    # Use cases with identical trajectories share one line and one label.
    groups: dict[tuple[tuple[int, str], ...], list[str]] = {}
    for uc_id, rows in ladders.items():
        key = tuple((int(r["applicable"]), str(r["inherent"])) for r in rows)
        groups.setdefault(key, []).append(uc_id)

    fig, ax = _figure(3.0)
    tiers_seen: set[str] = set()
    ends: list[tuple[float, str]] = []
    for key, members in groups.items():
        xs = list(range(len(key)))
        ys = [applicable for applicable, _ in key]
        ax.plot(xs, ys, color=LINE, linewidth=1.0, zorder=1)
        for x, (applicable, tier) in zip(xs, key, strict=True):
            tiers_seen.add(tier)
            ax.scatter(
                [x],
                [applicable],
                s=34,
                color=TIER_COLOURS[tier],
                edgecolor="white",
                linewidth=0.8,
                zorder=2,
            )
        ends.append((float(ys[-1]), "\n".join(members)))

    ax.set_xticks(range(len(ladder)), [AUTONOMY_LABELS[level] for level in ladder])
    ax.tick_params(axis="x", length=0, pad=4)
    ax.set_xlim(-0.35, len(ladder) - 0.65)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylabel("Applicable controls")
    ax.set_xlabel("Autonomy level")
    ax.grid(axis="y")
    ax.margins(y=0.12)

    # Label each line at its right end, outside the plotting area, spread so labels never touch.
    fig.canvas.draw()
    to_display = ax.transData.transform
    pixel_ys = [to_display((0, y))[1] for y, _ in ends]
    line_px = 8 * fig.dpi / 72 * 1.25
    heights = [line_px * label.count("\n") + line_px for _, label in ends]
    gap = max(heights) + 2
    spread = _spread(pixel_ys, gap)
    x_end = len(ladder) - 1
    for (y, label), target in zip(ends, spread, strict=True):
        ax.annotate(
            label,
            xy=(x_end, y),
            xytext=(12, (target - to_display((0, y))[1]) * 72 / fig.dpi),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=7.5,
            color=INK,
            linespacing=1.15,
            annotation_clip=False,
            arrowprops={"arrowstyle": "-", "color": LINE, "linewidth": 0.5, "shrinkA": 0},
        )

    order = [t for t in ("Low", "Medium", "High", "Critical") if t in tiers_seen]
    handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="none",
            markersize=5.5,
            markerfacecolor=TIER_COLOURS[t],
            markeredgecolor="white",
            label=t,
        )
        for t in order
    ]
    ax.legend(
        handles=handles,
        title="Inherent tier",
        title_fontsize=8,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.02),
        ncols=len(handles) + 1,
        borderaxespad=0.0,
        alignment="left",
    )
    caption = (
        "Applicable MAS-AIRM controls as a use case moves up the autonomy ladder, holding "
        "purpose, data and model family fixed. Marker colour is the inherent risk materiality "
        "tier under the toolkit's default rubric. Use cases with identical trajectories share a "
        "line. Tiering and the rubric are the authors' proposal: MAS prescribes no formula "
        "(Response to Feedback §7.19)."
    )
    return fig, caption


# --------------------------------------------------------------------------- RQ3


def draw_rq3(result: dict[str, Any]) -> tuple[Any, str]:
    """Dot-and-whisker: attack success rate by probe family and pattern, with Wilson intervals.

    Points rather than bars, because several rates are exactly zero and a zero-height bar is
    invisible; each pattern also has its own marker shape, so the figure survives greyscale.
    """
    rows: dict[str, Any] = result["results"]
    patterns = list(PATTERN_COLOURS)
    families = list(FAMILY_LABELS)
    limit = result["proposed_thresholds"]["asr_by_tier"]["High"] * 100

    fig, ax = _figure(3.0)
    step = 0.15
    for index, pattern in enumerate(patterns):
        cells = [rows[pattern]["by_family"][f] for f in families]
        xs = [f + (index - (len(patterns) - 1) / 2) * step for f in range(len(families))]
        values = [c["asr"] * 100 for c in cells]
        lower = [max(0.0, (c["asr"] - c["ci_lower"]) * 100) for c in cells]
        upper = [max(0.0, (c["ci_upper"] - c["asr"]) * 100) for c in cells]
        ax.errorbar(
            xs,
            values,
            yerr=[lower, upper],
            fmt=PATTERN_MARKERS[pattern],
            markersize=5,
            markerfacecolor=PATTERN_COLOURS[pattern],
            markeredgecolor="white",
            markeredgewidth=0.6,
            ecolor=PATTERN_COLOURS[pattern],
            elinewidth=0.9,
            capsize=0,
            label=PATTERN_LABELS[pattern],
            zorder=3,
            clip_on=False,
        )
    for boundary in range(1, len(families)):
        ax.axvline(boundary - 0.5, color=GRID, linewidth=0.6, zorder=0)
    ax.axhline(limit, color=INK, linestyle=(0, (4, 2)), linewidth=0.8, zorder=4)
    ax.set_xticks(range(len(families)), [FAMILY_LABELS[f] for f in families])
    ax.tick_params(axis="x", length=0, pad=4)
    ax.set_xlim(-0.5, len(families) - 0.5)
    ax.set_ylim(-4, 104)
    ax.set_yticks(range(0, 101, 25))
    ax.spines["bottom"].set_position(("data", -4))
    ax.set_ylabel("Attack success rate (%)")
    ax.grid(axis="y")
    handles = [
        Line2D(
            [],
            [],
            marker=PATTERN_MARKERS[p],
            linestyle="none",
            markersize=5,
            markerfacecolor=PATTERN_COLOURS[p],
            markeredgecolor="white",
            label=PATTERN_LABELS[p],
        )
        for p in patterns
    ] + [
        Line2D(
            [],
            [],
            color=INK,
            linestyle=(0, (4, 2)),
            linewidth=0.8,
            label=f"proposed High-tier limit ({limit:.0f}%)",
        )
    ]
    _legend_above(ax, handles, ncols=6)

    backend = result["backend"]
    trials = min(cell["trials"] for row in rows.values() for cell in row["by_family"].values())
    stub = " (deterministic stub, not a measurement)" if result["is_mock"] else ""
    caption = (
        "Attack success rate of five guardrail patterns against four probe families on "
        f"{result['probe_count']} probes, backend {backend['backend']}{stub}. Lower is better. "
        f"Points are observed rates; whiskers are Wilson 95% intervals over the {trials} probes "
        "in each family, which is why they are wide. The dashed line is the toolkit's proposed "
        "High-tier limit, not a MAS threshold: MAS sets no performance thresholds (Response to "
        "Feedback 10.29). Four benign control probes measure over-refusal, reported in the table "
        "rather than this figure."
    )
    return fig, caption


# --------------------------------------------------------------------------- RQ4


def draw_rq4(result: dict[str, Any]) -> tuple[Any, str]:
    """Horizontal stacked bars: coverage of the expectations by each framework and the union."""
    n = int(result["expectations"])
    per_framework = result["per_framework"]
    keys = list(per_framework)
    labels = [FRAMEWORK_LABELS.get(k, k) for k in keys] + ["All six combined"]
    data = [per_framework[k] for k in keys] + [result["union_all"]]

    fig, ax = _figure(2.9)
    ys = [*range(len(keys)), len(keys) + 0.35]
    lefts = [0.0] * len(data)
    for level in ("full", "partial", "none"):
        values = [float(row[level]) for row in data]
        ax.barh(
            ys,
            values,
            left=lefts,
            height=0.66,
            color=COVERAGE_COLOURS[level],
            edgecolor="white",
            linewidth=0.8,
        )
        for y, value, left in zip(ys, values, lefts, strict=True):
            if value >= 3:
                _segment_label(ax, left + value / 2, y, f"{value:.0f}", COVERAGE_COLOURS[level])
        lefts = [a + b for a, b in zip(lefts, values, strict=True)]
    ax.axhline(len(keys) - 0.5 + 0.175, color=RULE, linewidth=0.5, xmin=0, xmax=1)
    ax.set_yticks(ys, labels)
    ax.get_yticklabels()[-1].set_fontweight("semibold")
    ax.tick_params(axis="y", length=0, pad=4)
    ax.invert_yaxis()
    ax.set_xlim(0, n)
    ax.set_xticks(range(0, n + 1, 10))
    ax.set_xlabel(f"MAS-AIRM expectation paragraphs (of {n})")
    ax.spines["left"].set_visible(False)
    _legend_above(
        ax,
        [Patch(facecolor=COVERAGE_COLOURS[k], label=k) for k in ("full", "partial", "none")],
        ncols=3,
    )
    caption = (
        f"Coverage of the {n} MAS-AIRM expectation paragraphs by other AI governance "
        "frameworks. full: the other framework imposes an equivalent obligation. partial: "
        "related but narrower, differently scoped or optional. none: no mapping asserted. "
        "Mapping is interpretive and asymmetric, since ISO/IEC 42001 is a management-system "
        "standard, the EU AI Act is product law and the NIST AI RMF is voluntary guidance, so "
        "a paragraph can be covered in substance and uncovered in legal effect."
    )
    return fig, caption


# --------------------------------------------------------------------------- RQ5


def draw_rq5(result: dict[str, Any]) -> tuple[Any, str]:
    """Horizontal stacked bars: estimated first-time effort per use case, by class."""
    per_use_case: dict[str, Any] = result["per_use_case"]
    ids = sorted(per_use_case, key=lambda i: -per_use_case[i]["first_time_hours"])

    fig, ax = _figure(3.1)
    ys = range(len(ids))
    lefts = [0.0] * len(ids)
    for klass in ("auto", "semi", "doc"):
        values = [float(per_use_case[i]["hours_by_class"][klass]) for i in ids]
        ax.barh(
            list(ys),
            values,
            left=lefts,
            height=0.66,
            color=CLASS_COLOURS[klass],
            edgecolor="white",
            linewidth=0.8,
        )
        lefts = [a + b for a, b in zip(lefts, values, strict=True)]
    for y, total in zip(ys, lefts, strict=True):
        ax.text(total + 6, y, f"{total:.0f}", va="center", ha="left", fontsize=7.5, color=INK)
    ax.set_yticks(list(ys), [f"{i} ({per_use_case[i]['tier']})" for i in ids])
    ax.tick_params(axis="y", length=0, pad=4)
    ax.invert_yaxis()
    ax.set_xlim(0, max(lefts) * 1.1)
    ax.set_xlabel("Estimated first-time effort (person-hours)")
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x")
    _legend_above(
        ax,
        [Patch(facecolor=CLASS_COLOURS[k], label=k) for k in ("auto", "semi", "doc")],
        ncols=3,
    )
    caption = (
        "Estimated first-time compliance effort for the synthetic bank portfolio, by use case "
        "and by the automatability class of the control requiring each evidence item, with the "
        "inherent tier in brackets and the total at the end of each bar. Person-hour figures "
        "are the authors' estimates from the table in experiments/rq5_cost.py, not "
        "measurements; the shape of the distribution is the claim, not the absolute values."
    )
    return fig, caption


# --------------------------------------------------------------------------- registry

FIGURES: dict[str, tuple[str, Callable[[dict[str, Any]], tuple[Any, str]]]] = {
    "rq1_automatability_by_section": ("rq1_automatability", draw_rq1),
    "rq2_autonomy_controls": ("rq2_autonomy", draw_rq2),
    "rq3_guardrail_effectiveness": ("rq3_guardrails", draw_rq3),
    "rq4_crosswalk_coverage": ("rq4_crosswalk", draw_rq4),
    "rq5_effort_by_use_case": ("rq5_cost", draw_rq5),
}


def draw(name: str, result: dict[str, Any] | None = None) -> tuple[Any, str]:
    """Return one figure and its caption, drawn from its committed result file by default."""
    source, drawer = FIGURES[name]
    return drawer(result if result is not None else read_result(source))


def render(name: str, out_dir: Path = FIGURE_DIR) -> Path:
    """Draw one figure and write its PNG, SVG and caption. Returns the PNG path."""
    fig, caption = draw(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = out_dir / f"{name}.png"
    fig.savefig(png, dpi=300, metadata={"Software": None})
    fig.savefig(png.with_suffix(".svg"), metadata={"Date": None, "Creator": None})
    png.with_suffix(".txt").write_text(caption.strip() + "\n", encoding="utf-8")
    plt.close(fig)
    return png


def main(names: list[str]) -> None:
    for name in names or FIGURES:
        print(f"  figure: {render(name).relative_to(FIGURE_DIR.parents[1])}")


if __name__ == "__main__":
    main(sys.argv[1:])
