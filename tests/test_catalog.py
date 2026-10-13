"""The clause catalogue is the ground truth; these tests guard its integrity."""

from __future__ import annotations

import datetime as dt

import pytest

from airm.catalog import CITATION_PREFIX, cite, load_catalogue

EXPECTED_IDS = (
    [f"1.{i}" for i in range(1, 13)]
    + [f"2.{i}" for i in range(1, 6)]
    + [f"3.{i}" for i in range(1, 7)]
    + [f"4.{i}" for i in range(1, 14)]
    + [f"5.{i}" for i in range(1, 27)]
    + [f"6.{i}" for i in range(1, 4)]
)


def test_every_paragraph_present():
    """Every paragraph of the Guidelines 1.1 to 6.3 must be indexed, with no extras."""
    catalogue = load_catalogue()
    assert [p.id for p in catalogue.paragraphs] == EXPECTED_IDS


def test_summaries_within_forty_words():
    """MISSION: normative text summaries are at most 40 words, in the authors' own words."""
    for paragraph in load_catalogue().paragraphs:
        assert len(paragraph.summary.split()) <= 40, paragraph.id


def test_item_summaries_are_short():
    for paragraph in load_catalogue().paragraphs:
        for item in paragraph.items:
            assert len(item.summary.split()) <= 40, f"{paragraph.id}({item.id})"


def test_all_fifty_one_footnotes_indexed():
    catalogue = load_catalogue()
    assert sorted(f.id for f in catalogue.footnotes) == list(range(1, 52))


def test_footnotes_anchor_to_real_paragraphs():
    catalogue = load_catalogue()
    for footnote in catalogue.footnotes:
        assert footnote.anchored_to in catalogue


def test_paragraph_footnote_ids_resolve():
    catalogue = load_catalogue()
    for paragraph in catalogue.paragraphs:
        for footnote_id in paragraph.footnote_ids:
            assert catalogue.footnote(footnote_id).id == footnote_id


def test_tags_come_from_the_closed_vocabulary():
    catalogue = load_catalogue()
    allowed = set(catalogue.tag_vocabulary())
    for paragraph in catalogue.paragraphs:
        assert set(paragraph.tags) <= allowed, paragraph.id
    for footnote in catalogue.footnotes:
        assert set(footnote.tags) <= allowed, footnote.id


def test_effective_dates_follow_section_1_8():
    """MAS-AIRM 1.8: Sections 3-4 from 2027-10-07, Sections 5-6 by 2028-10-07."""
    catalogue = load_catalogue()
    for paragraph in catalogue.paragraphs:
        expected = dt.date(2028, 10, 7) if paragraph.section in ("5", "6") else dt.date(2027, 10, 7)
        assert paragraph.effective == expected, paragraph.id


def test_expectation_count_is_stable():
    """The RQ1 denominator. A change here changes every reported share, so it is pinned."""
    assert len(load_catalogue().expectations()) == 51


def test_inventory_attributes_match_paragraph_4_7():
    attributes = load_catalogue().inventory_attributes()
    assert "risk_materiality_rating" in attributes
    assert "model_review_status" in attributes
    assert len(attributes) == 10


def test_agent_attributes_match_footnote_25():
    assert load_catalogue().agent_attributes() == (
        "agent_identifier",
        "tools_and_systems_accessible",
        "components",
        "guardrails",
    )


def test_genai_failure_modes_match_footnote_46():
    modes = load_catalogue().genai_failure_modes()
    assert set(modes) == {
        "hallucination",
        "undesirable_content",
        "bias",
        "data_leakage",
        "adversarial_vulnerability",
    }


def test_high_materiality_clauses():
    """5.3 contingency and 5.19 independent validation bind only at high materiality."""
    ids = {p.id for p in load_catalogue().high_materiality_clauses()}
    assert ids == {"5.3", "5.19"}


def test_by_tag_finds_agent_clauses():
    ids = {p.id for p in load_catalogue().by_tag("agent")}
    assert {"1.11", "4.8", "5.15", "5.23"} <= ids


def test_normative_footnotes_include_the_important_ones():
    """fn22 shadow AI, fn25 agent attributes, fn46 GenAI failure modes carry requirements."""
    ids = {f.id for f in load_catalogue().normative_footnotes()}
    assert {13, 22, 24, 25, 28, 46} <= ids


def test_citation_formats():
    assert cite("4.7") == f"{CITATION_PREFIX} §4.7"
    assert cite("5.23", item="d") == f"{CITATION_PREFIX} §5.23(d)"
    assert cite("4.8", footnote=25) == f"{CITATION_PREFIX} §4.8 fn25"


def test_paragraph_lookup_errors_are_clear():
    catalogue = load_catalogue()
    with pytest.raises(KeyError, match="no such MAS-AIRM paragraph"):
        catalogue.paragraph("9.9")
    with pytest.raises(KeyError, match="no such MAS-AIRM footnote"):
        catalogue.footnote(999)
    with pytest.raises(KeyError, match="no such MAS-AIRM section"):
        catalogue.section("9")


def test_item_lookup():
    paragraph = load_catalogue().paragraph("4.12")
    assert "impact" in paragraph.item("a").summary.lower()
    with pytest.raises(KeyError, match="has no item"):
        paragraph.item("z")


def test_sections_and_container_protocol():
    catalogue = load_catalogue()
    assert len(catalogue) == 65
    assert "5.19" in catalogue
    assert 5 not in catalogue
    assert catalogue.section("5").title == "AI Life Cycle Controls"
    assert len(catalogue.by_section("5")) == 26


def test_catalogue_is_cached():
    assert load_catalogue() is load_catalogue()


def test_source_hash_recorded():
    """The catalogue pins the SHA-256 of the PDF it was built from, so drift is detectable."""
    meta = load_catalogue().meta
    assert meta["source_sha256"] == (
        "d9a4095569da34078e2cd597cc992910e63cf88471c59cb654c0413dbaed5c6d"
    )
