"""Tests for experiments/render_paper.py and for the rendered paper itself.

Two jobs. First, the renderer must fail loudly: a placeholder that names nothing is the only
protection against a stale number surviving in the prose after a result changes. Second, the
committed paper/paper.md must be the render of the committed template and summary, so a reader
of the repository cannot be shown numbers that the results no longer support.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

collect = pytest.importorskip("collect")
render_paper = pytest.importorskip("render_paper")

REPO = Path(__file__).resolve().parents[1]
SUMMARY_PATH = REPO / "results" / "summary.json"
TEMPLATE_PATH = REPO / "paper" / "paper.md.in"
PAPER_PATH = REPO / "paper" / "paper.md"


@pytest.fixture(scope="module")
def summary() -> dict:
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def paper(template: str, summary: dict) -> str:
    rendered, _ = render_paper.render(template, summary)
    return rendered


def test_resolve_substitutes_a_number(summary: dict) -> None:
    used: set[str] = set()
    assert render_paper.resolve("rq1.expectations", summary, used) == "51"
    assert used == {"rq1.expectations"}


def test_resolve_rejects_an_unknown_number_and_suggests_a_near_match(summary: dict) -> None:
    with pytest.raises(KeyError, match="did you mean"):
        render_paper.resolve("rq1.expectation", summary, set())


def test_resolve_rejects_an_unknown_table(summary: dict) -> None:
    with pytest.raises(KeyError, match="unknown table"):
        render_paper.resolve("table:nonesuch", summary, set())


def test_resolve_rejects_an_unknown_kind(summary: dict) -> None:
    with pytest.raises(KeyError, match="unknown placeholder kind"):
        render_paper.resolve("chart:rq1", summary, set())


def test_resolve_rejects_an_unknown_figure(summary: dict) -> None:
    with pytest.raises(KeyError, match="no figure named"):
        render_paper.resolve("figure:rq9_nonesuch", summary, set())


def test_resolve_returns_a_disclosure_verbatim(summary: dict) -> None:
    text = render_paper.resolve("text:rq2_post_hoc_ladder_change", summary, set())
    assert text == summary["disclosures"]["rq2_post_hoc_ladder_change"]
    assert render_paper.resolve("text:disclaimer", summary, set()) == summary["disclaimer"]


def test_every_table_renders_as_markdown(summary: dict) -> None:
    for name, builder in render_paper.TABLES.items():
        table = builder(summary)
        lines = table.splitlines()
        assert len(lines) >= 3, name
        assert lines[1].startswith("|---"), name
        width = lines[0].count("|")
        for line in lines:
            assert line.count("|") == width, f"{name} has a ragged row: {line}"


def test_every_list_renders_bullets(summary: dict) -> None:
    for name, builder in render_paper.LISTS.items():
        assert "- " in builder(summary), name


def test_verdict_table_marks_the_refutations(summary: dict) -> None:
    table = render_paper.table_verdicts(summary)
    assert table.count("**refuted**") == summary["verdict_counts"]["refuted"]


def test_verdict_details_are_prose_not_python_reprs(summary: dict) -> None:
    """A verdict detail is printed in the paper, so it must not be a dict or list repr."""
    for row in summary["verdicts"]:
        assert "{'" not in row["detail"], row["hypothesis"]
        assert "['" not in row["detail"], row["hypothesis"]


def test_render_leaves_no_placeholder_behind(paper: str) -> None:
    assert not render_paper.PLACEHOLDER.search(paper)


def test_template_uses_only_known_placeholders(template: str, summary: dict) -> None:
    for match in render_paper.PLACEHOLDER.finditer(template):
        render_paper.resolve(match.group(1), summary, set())


def test_paper_has_every_section_mission_requires(paper: str) -> None:
    for heading in (
        "abstract:",
        "# 1. Introduction",
        "# 2. Background",
        "# 3. Related frameworks",
        "# 4. Method",
        "# 5. The toolkit",
        "# 7. Results",
        "# 8. Threats to validity",
        "# 9. Reproducibility statement",
        "# 10. Conclusion",
    ):
        assert heading in paper, heading
    for rq in ("RQ1", "RQ2", "RQ3", "RQ4", "RQ5"):
        assert rq in paper


def test_paper_carries_the_disclaimer(paper: str) -> None:
    assert "not affiliated with or endorsed by the Monetary Authority of Singapore" in paper
    assert "not legal, regulatory or compliance advice" in paper


def test_paper_labels_the_authors_proposals(paper: str) -> None:
    """MAS prescribes no formula or threshold; the paper must not imply otherwise."""
    assert "our proposal, not a MAS methodology" in paper
    assert "not a MAS threshold" in paper
    assert "the authors' estimates" in paper


def test_paper_keeps_the_refutations_and_disclosures(paper: str) -> None:
    for label in ("H1(a)", "H2(b)", "H2(c)", "H3(b)", "H3(d)", "H4(c)", "H5(a)"):
        assert label in paper, label
    assert "autonomous_decisioning" in paper
    assert "not pre-registered" in paper
    assert "DJ-01" in paper


def test_paper_embeds_all_five_figures(paper: str) -> None:
    for name in (
        "rq1_automatability_by_section",
        "rq2_autonomy_controls",
        "rq3_guardrail_effectiveness",
        "rq4_crosswalk_coverage",
        "rq5_effort_by_use_case",
    ):
        assert f"../results/figures/{name}.png" in paper, name


def test_committed_paper_matches_the_template_and_results(paper: str) -> None:
    """The committed paper is a build artefact; a stale one would mislead a reader."""
    date_line = re.compile(r'^date: ".*"$', re.MULTILINE)
    committed = date_line.sub('date: ""', PAPER_PATH.read_text(encoding="utf-8"))
    assert committed == date_line.sub('date: ""', paper)


POSTS = sorted((REPO / "docs" / "posts").glob("*.md.in"))


def test_there_are_eight_to_ten_posts() -> None:
    """MISSION asks for 8-10 drafts: one per Guidelines section, plus launch and retrospective."""
    assert 8 <= len(POSTS) <= 10


@pytest.mark.parametrize("template_path", POSTS, ids=lambda p: p.name)
def test_each_post_fits_linkedin_and_ends_with_the_repo_link(
    template_path: Path, summary: dict
) -> None:
    rendered, _ = render_paper.render(template_path.read_text(encoding="utf-8"), summary)
    assert len(rendered) <= 1300, f"{template_path.name} is {len(rendered)} characters"
    assert rendered.rstrip().endswith("https://github.com/thanatchon36/airmkit")
    assert not render_paper.PLACEHOLDER.search(rendered)


@pytest.mark.parametrize("template_path", POSTS, ids=lambda p: p.name)
def test_each_post_is_committed_as_rendered(template_path: Path, summary: dict) -> None:
    rendered, _ = render_paper.render(template_path.read_text(encoding="utf-8"), summary)
    assert template_path.with_suffix("").read_text(encoding="utf-8") == rendered


def test_exec_summary_is_committed_as_rendered(summary: dict) -> None:
    template_path = REPO / "docs" / "EXEC_SUMMARY.md.in"
    rendered, _ = render_paper.render(template_path.read_text(encoding="utf-8"), summary)
    rendered = rendered.replace("{{DATE}}", "")
    committed = template_path.with_suffix("").read_text(encoding="utf-8")
    assert re.sub(r"Generated \S+ from", "Generated  from", committed) == re.sub(
        r"Generated \S+ from", "Generated  from", rendered
    )


def test_committed_summary_matches_the_committed_results(summary: dict) -> None:
    """results/summary.json is a build artefact of the five RQ files."""
    fresh = collect.collate(collect.load_rq_results(), collect.example_pack_summary())
    assert fresh["numbers"] == summary["numbers"]
    assert fresh["verdicts"] == summary["verdicts"]
