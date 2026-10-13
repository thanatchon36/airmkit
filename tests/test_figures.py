"""Tests for experiments/figures.py, which draws the paper's five figures from results/.

A figure is drawn from the committed result file alone, so it can be redrawn without rerunning
an experiment (RQ3 needs a live model). The layout tests exist because the first published
figures had legends sitting on bars and labels printed on top of each other: those defects are
checked mechanically here rather than by eye.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")
figures = pytest.importorskip("figures")

REPO = Path(__file__).resolve().parents[1]
COMMITTED = REPO / "results" / "figures"
NAMES = sorted(figures.FIGURES)


@pytest.fixture(scope="module", params=NAMES)
def drawn(request: pytest.FixtureRequest):
    """One figure drawn from its committed result file and laid out as it will be saved."""
    name = request.param
    fig, caption = figures.draw(name)
    fig.canvas.draw()
    yield name, fig, caption
    import matplotlib.pyplot as plt

    plt.close(fig)


def _texts(fig):
    """Every visible, non-empty text artist in the figure, with its rendered extent."""
    renderer = fig.canvas.get_renderer()
    from matplotlib.text import Text

    found = []
    seen: set[int] = set()
    for text in fig.findobj(Text):
        # findobj reaches some artists by more than one path; count each once.
        if id(text) in seen or not text.get_visible() or not text.get_text().strip():
            continue
        seen.add(id(text))
        found.append((text.get_text(), text.get_window_extent(renderer)))
    return found


def test_five_figures_are_registered() -> None:
    assert NAMES == [
        "rq1_automatability_by_section",
        "rq2_autonomy_controls",
        "rq3_guardrail_effectiveness",
        "rq4_crosswalk_coverage",
        "rq5_effort_by_use_case",
    ]


def test_figure_spans_the_paper_text_width(drawn) -> None:
    _, fig, _ = drawn
    assert fig.get_figwidth() == pytest.approx(figures.TEXT_WIDTH_IN)


def test_no_title_inside_the_figure(drawn) -> None:
    """The caption names the figure; a title in the image repeats it at a different size."""
    _, fig, _ = drawn
    assert fig._suptitle is None
    for ax in fig.axes:
        assert not ax.get_title(loc="left") and not ax.get_title() and not ax.get_title("right")


def test_no_two_labels_overlap(drawn) -> None:
    name, fig, _ = drawn
    texts = _texts(fig)
    clashes = [
        (a, b)
        for (a, box_a), (b, box_b) in combinations(texts, 2)
        if box_a.overlaps(box_b) and box_a.intersection(box_a, box_b).width > 0.5
    ]
    assert not clashes, f"{name}: overlapping labels {clashes}"


def test_legend_sits_clear_of_the_data(drawn) -> None:
    name, fig, _ = drawn
    renderer = fig.canvas.get_renderer()
    for ax in fig.axes:
        legend = ax.get_legend() or (fig.legends[0] if fig.legends else None)
        if legend is None:
            continue
        box = legend.get_window_extent(renderer)
        plot = ax.get_window_extent(renderer)
        assert not box.overlaps(plot), f"{name}: legend overlaps the plotting area"


def test_text_uses_the_paper_typeface(drawn) -> None:
    name, fig, _ = drawn
    for text in fig.findobj(lambda a: hasattr(a, "get_fontname")):
        if text.get_visible() and text.get_text().strip():
            assert text.get_fontname() == figures.FONT_FAMILY, (name, text.get_text())


def test_caption_matches_the_committed_caption(drawn) -> None:
    """The paper reads the caption from the .txt beside the PNG; it must not be stale."""
    name, _, caption = drawn
    committed = (COMMITTED / f"{name}.txt").read_text(encoding="utf-8")
    assert committed == caption.strip() + "\n"


@pytest.mark.parametrize("name", NAMES)
def test_vector_copy_exists_for_the_pdf(name: str) -> None:
    assert (COMMITTED / f"{name}.svg").is_file()
    assert (COMMITTED / f"{name}.png").is_file()


def test_svg_output_is_deterministic(tmp_path: Path) -> None:
    """Fixed hash salt and no timestamp, so a redraw with no data change leaves git clean."""
    first = figures.render("rq1_automatability_by_section", tmp_path / "a")
    second = figures.render("rq1_automatability_by_section", tmp_path / "b")
    assert first.with_suffix(".svg").read_bytes() == second.with_suffix(".svg").read_bytes()


def test_pdf_build_swaps_in_the_vector_figures() -> None:
    build_paper = pytest.importorskip("build_paper")
    source = '#figure(image("../results/figures/rq1_automatability_by_section.png"),\n'
    swapped = build_paper.vector_figures(source)
    assert 'image("../results/figures/rq1_automatability_by_section.svg")' in swapped


def test_pdf_build_keeps_a_png_with_no_vector_copy() -> None:
    build_paper = pytest.importorskip("build_paper")
    source = '#figure(image("../results/figures/not_a_figure.png"),\n'
    assert build_paper.vector_figures(source) == source
