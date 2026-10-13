"""Tests for experiments/collect.py, the merge step that feeds the paper.

The paper quotes no number that is not in results/summary.json, so these tests check two things:
that the merge is structurally complete (every RQ, every verdict, every figure), and that each
headline figure equals the value in the per-RQ file it came from. A test that recomputed the
figure instead of reading it would only be testing arithmetic twice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

collect = pytest.importorskip("collect")

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"


@pytest.fixture(scope="module")
def rqs() -> dict[str, dict]:
    """The five committed per-RQ result files."""
    return collect.load_rq_results(RESULTS)


@pytest.fixture(scope="module")
def summary(rqs: dict[str, dict]) -> dict:
    """The merged summary, built from the committed files and the shipped portfolio."""
    return collect.collate(rqs, collect.example_pack_summary())


def test_rq_sources_cover_five_questions() -> None:
    assert sorted(collect.RQ_SOURCES) == ["rq1", "rq2", "rq3", "rq4", "rq5"]


def test_load_rq_results_reads_every_file(rqs: dict[str, dict]) -> None:
    assert sorted(rqs) == ["rq1", "rq2", "rq3", "rq4", "rq5"]
    for key, payload in rqs.items():
        assert payload["question"], f"{key} has no question text"
        assert payload["provenance"]["airmkit_version"]
        assert payload["verdicts"]


def test_load_rq_results_names_the_script_when_a_file_is_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="rq1_automatability"):
        collect.load_rq_results(tmp_path)


def test_verdict_table_flattens_every_verdict(rqs: dict[str, dict]) -> None:
    table = collect.verdict_table(rqs)
    assert len(table) == sum(len(payload["verdicts"]) for payload in rqs.values())
    assert {row["rq"] for row in table} == set(rqs)
    for row in table:
        assert set(row) == {"rq", "hypothesis", "holds", "detail"}
        assert isinstance(row["holds"], bool)


def test_verdict_table_keeps_the_refuted_hypotheses(rqs: dict[str, dict]) -> None:
    """Refuted hypotheses are the paper's main contribution; the merge must not drop them."""
    table = collect.verdict_table(rqs)
    refuted = [row for row in table if not row["holds"]]
    assert len(refuted) >= 5
    hypotheses = " ".join(row["hypothesis"] for row in refuted)
    for label in ("H2(b)", "H2(c)", "H3(b)", "H3(d)", "H4(c)", "H5(a)"):
        assert label in hypotheses


def test_collate_carries_the_structural_sections(summary: dict) -> None:
    for key in (
        "provenance",
        "catalogue",
        "controls",
        "portfolio",
        "questions",
        "verdicts",
        "numbers",
        "figures",
        "threats_to_validity",
        "disclosures",
        "disclaimer",
    ):
        assert key in summary, key


def test_collate_counts_verdicts(summary: dict) -> None:
    held = sum(1 for row in summary["verdicts"] if row["holds"])
    refuted = sum(1 for row in summary["verdicts"] if not row["holds"])
    assert summary["verdict_counts"] == {
        "total": held + refuted,
        "held": held,
        "refuted": refuted,
    }


def test_catalogue_section_matches_the_packaged_catalogue(summary: dict) -> None:
    from airm.catalog import load_catalogue

    catalogue = load_catalogue()
    assert summary["catalogue"]["paragraphs"] == len(catalogue)
    assert summary["catalogue"]["expectations"] == len(catalogue.expectations())


def test_numbers_are_scalars_the_paper_can_substitute(summary: dict) -> None:
    assert summary["numbers"]
    for key, value in summary["numbers"].items():
        assert isinstance(key, str) and key
        assert isinstance(value, str | int | float), f"{key} is {type(value).__name__}"
        assert not isinstance(value, bool), f"{key} is a bool; the paper needs a printable value"


def test_numbers_agree_with_the_rq_files(summary: dict, rqs: dict[str, dict]) -> None:
    numbers = summary["numbers"]
    assert numbers["rq1.expectations"] == rqs["rq1"]["paragraph_totals"]["n"]
    assert numbers["rq1.auto_count"] == rqs["rq1"]["paragraph_totals"]["counts"]["auto"]
    assert numbers["rq1.controls"] == rqs["rq1"]["control_totals"]["n"]
    assert numbers["rq3.asr_none"] == collect.pct(rqs["rq3"]["results"]["none"]["overall_asr"])
    assert numbers["rq3.model"] == rqs["rq3"]["backend"]["model"]
    assert numbers["rq4.best_single_framework_share"] == collect.pct(
        max(row["full_share"] for row in rqs["rq4"]["per_framework"].values())
    )
    assert numbers["rq5.first_time_hours"] == rqs["rq5"]["totals"]["first_time_hours"]
    assert numbers["rq5.gini"] == rqs["rq5"]["totals"]["gini_across_use_cases"]


def test_percentages_are_rendered_once_and_consistently(summary: dict) -> None:
    assert collect.pct(0.451) == "45.1%"
    assert collect.pct(0.0) == "0.0%"
    assert collect.pct(1.0) == "100.0%"
    for key, value in summary["numbers"].items():
        if key.endswith("_ci"):
            assert isinstance(value, str) and value.count("%") == 2, key
        elif key.endswith("_share") or key.endswith("_pct") or key.startswith("rq3.asr"):
            assert isinstance(value, str) and value.endswith("%"), key


def test_figures_carry_their_committed_captions(summary: dict) -> None:
    assert len(summary["figures"]) == 5
    for row in summary["figures"]:
        assert set(row) == {"rq", "file", "caption"}
        assert (RESULTS / "figures" / row["file"]).is_file()
        assert row["caption"].strip()


def test_threats_to_validity_are_kept_per_rq(summary: dict, rqs: dict[str, dict]) -> None:
    for key, payload in rqs.items():
        assert summary["threats_to_validity"][key] == payload["threats_to_validity"]


def test_disclosures_keep_the_rq2_and_rq3_caveats(summary: dict) -> None:
    """Both were found during implementation and MISSION requires they stay visible."""
    disclosures = summary["disclosures"]
    assert "AUTONOMOUS_DECISIONING" in disclosures["rq2_post_hoc_ladder_change"]
    calibration = disclosures["rq3_detector_calibration"]
    assert "DJ-01" in calibration
    assert "none" in calibration
    assert "qwen3.5" in disclosures["rq3_backend"]
    assert disclosures["rq3_is_mock"] is False


def test_portfolio_section_comes_from_the_audit_pack(summary: dict) -> None:
    portfolio = summary["portfolio"]
    assert portfolio["use_cases"] == 8
    assert portfolio["institution"].startswith("Merlion")
    assert "fictional" in portfolio["institution"].lower()
    assert sum(portfolio["tier_counts"].values()) == 8
    assert portfolio["outcomes"]["needs_attestation"] > 0


def test_provenance_records_how_the_merge_was_produced(summary: dict, rqs: dict[str, dict]) -> None:
    provenance = summary["provenance"]
    assert provenance["airmkit_version"]
    assert provenance["git_revision"]
    assert provenance["merged_from"] == {
        key: payload["provenance"]["generated_at"] for key, payload in rqs.items()
    }


def test_disclaimer_is_present_and_names_mas(summary: dict) -> None:
    assert "Monetary Authority of Singapore" in summary["disclaimer"]
    assert "legal" in summary["disclaimer"].lower()


def test_main_writes_summary_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "summary.json"
    monkeypatch.setattr(collect, "SUMMARY", target)
    collect.main()
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["numbers"]["rq1.expectations"] == 51
    assert written["figures"]
