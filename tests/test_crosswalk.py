"""Crosswalk to other frameworks (RQ4 data)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from airm.catalog import load_catalogue
from airm.crosswalk import (
    Coverage,
    Crosswalk,
    Framework,
    Mapping,
    coverage_summary,
    load_crosswalk,
    residual_work,
)


class TestFrameworks:
    def test_each_framework_has_a_title(self):
        for framework in Framework:
            assert framework.full_title

    def test_only_the_eu_ai_act_is_binding_law(self):
        assert Framework.EU_AI_ACT.is_binding_law
        assert not Framework.ISO_42001.is_binding_law
        assert not Framework.NIST_AI_RMF.is_binding_law

    def test_coverage_ranks(self):
        assert Coverage.FULL.rank > Coverage.PARTIAL.rank > Coverage.NONE.rank


class TestMappingValidation:
    def test_coverage_needs_a_reference(self):
        with pytest.raises(ValidationError, match="no reference to point at"):
            Mapping(
                clause="5.19",
                framework=Framework.ISO_42001,
                refs=[],
                coverage=Coverage.FULL,
                justification="j",
            )

    def test_non_full_coverage_needs_a_gap(self):
        """A partial mapping that does not say what is missing is not usable."""
        with pytest.raises(ValidationError, match="must say what the gap is"):
            Mapping(
                clause="5.19",
                framework=Framework.ISO_42001,
                refs=["9.2"],
                coverage=Coverage.PARTIAL,
                justification="j",
            )

    def test_unknown_clause_rejected(self):
        with pytest.raises(ValidationError, match="unknown MAS-AIRM paragraph"):
            Crosswalk(
                mappings=[
                    {
                        "clause": "9.9",
                        "framework": "iso_42001",
                        "refs": ["x"],
                        "coverage": "full",
                        "justification": "j",
                    }
                ]
            )


class TestPackagedCrosswalk:
    def test_loads_and_is_cached(self):
        assert load_crosswalk() is load_crosswalk()
        assert len(load_crosswalk()) > 150

    def test_all_five_frameworks_present(self):
        assert set(load_crosswalk().frameworks()) == set(Framework)

    def test_every_row_carries_a_justification_and_confidence(self):
        """Mapping is interpretive, so every row must be arguable on its own terms."""
        for row in load_crosswalk().mappings:
            assert row.justification.strip()
            assert row.confidence in {"low", "medium", "high"}

    def test_every_gap_row_states_the_gap(self):
        for row in load_crosswalk().mappings:
            if row.coverage is not Coverage.FULL:
                assert row.gap

    def test_no_duplicate_clause_framework_pairs(self):
        pairs = [(r.clause, r.framework) for r in load_crosswalk().mappings]
        assert len(pairs) == len(set(pairs))

    def test_every_expectation_is_mapped(self):
        assert load_crosswalk().unmapped() == ()


class TestQueries:
    def test_forward_lookup(self):
        rows = load_crosswalk().for_clause("5.19")
        assert rows
        assert all(r.clause == "5.19" for r in rows)

    def test_coverage_of_an_unmapped_pair_is_none(self):
        """A missing row and an asserted gap have the same consequence."""
        assert load_crosswalk().coverage_of("5.26", Framework.FEAT) is Coverage.NONE

    def test_best_coverage_compares_by_rank_not_string(self):
        """Alphabetically 'full' < 'partial', which would understate the union."""
        crosswalk = Crosswalk(
            mappings=[
                {
                    "clause": "5.19",
                    "framework": "iso_42001",
                    "refs": ["9.2"],
                    "coverage": "partial",
                    "justification": "j",
                    "gap": "g",
                },
                {
                    "clause": "5.19",
                    "framework": "nist_ai_rmf",
                    "refs": ["MEASURE 1.3"],
                    "coverage": "full",
                    "justification": "j",
                },
            ]
        )
        best, frameworks = crosswalk.best_coverage("5.19")
        assert best is Coverage.FULL
        assert frameworks == (Framework.NIST_AI_RMF,)

    def test_best_coverage_of_an_unmapped_clause(self):
        assert Crosswalk().best_coverage("5.19") == (Coverage.NONE, ())

    def test_reverse_lookup(self):
        rows = load_crosswalk().for_ref(Framework.ISO_42001, "A.6.2.4")
        assert rows
        assert all(any("A.6.2.4" in ref for ref in r.refs) for r in rows)

    def test_reverse_lookup_is_case_insensitive(self):
        assert load_crosswalk().for_ref(Framework.NIST_AI_RMF, "measure 2.11")

    def test_for_framework_is_in_document_order(self):
        rows = load_crosswalk().for_framework(Framework.ISO_42001)
        catalogue = load_catalogue()
        keys = [catalogue.paragraph(r.clause).sort_key for r in rows]
        assert keys == sorted(keys)


class TestCoverageSummary:
    def test_denominator_is_the_expectation_count(self):
        summary = coverage_summary()
        expectations = len(load_catalogue().expectations())
        for counts in summary.values():
            assert sum(counts.values()) == expectations

    def test_union_is_at_least_as_good_as_any_single_framework(self):
        summary = coverage_summary()
        union_full = summary["union"]["full"]
        for name, counts in summary.items():
            if name != "union":
                assert counts["full"] <= union_full

    def test_no_single_framework_fully_covers_more_than_sixty_percent(self):
        """RQ4 hypothesis H4(a)."""
        summary = coverage_summary()
        expectations = len(load_catalogue().expectations())
        for name, counts in summary.items():
            if name != "union":
                assert counts["full"] / expectations < 0.6, name

    def test_union_leaves_a_residue(self):
        """RQ4 hypothesis H4(b): at least 10% has no full mapping anywhere."""
        crosswalk = load_crosswalk()
        residue = crosswalk.uncovered()
        expectations = len(load_catalogue().expectations())
        assert len(residue) / expectations >= 0.10

    def test_residue_includes_the_singapore_and_agent_specific_clauses(self):
        """RQ4 hypothesis H4(c)."""
        residue = set(load_crosswalk().uncovered())
        assert "3.6" in residue  # local senior management accountability
        assert "4.4" in residue  # shadow AI
        assert "4.8" in residue  # inventory design incl. agent attributes


class TestResidualWork:
    def test_iso_alone_leaves_work(self):
        work = residual_work([Framework.ISO_42001])
        assert work["uncovered"] or work["partial"]

    def test_adding_frameworks_never_increases_uncovered(self):
        iso = residual_work([Framework.ISO_42001])
        both = residual_work([Framework.ISO_42001, Framework.NIST_AI_RMF])
        assert len(both["uncovered"]) <= len(iso["uncovered"])

    def test_local_accountability_is_uncovered_by_the_international_frameworks(self):
        """MAS-AIRM 3.6 has no counterpart in ISO 42001 or the NIST AI RMF."""
        work = residual_work([Framework.ISO_42001, Framework.NIST_AI_RMF])
        assert "3.6" in work["uncovered"]

    def test_no_frameworks_held_means_everything_is_uncovered(self):
        work = residual_work([])
        assert len(work["uncovered"]) == len(load_catalogue().expectations())
