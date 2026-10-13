"""Hash-chained audit trail and incident log: MAS-AIRM 5.17, 5.23(d), 3.5 fn20."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from airm.monitor import (
    GENESIS_HASH,
    AuditTrail,
    ChainError,
    EventType,
    Evidence,
    Incident,
    IncidentStatus,
    Severity,
    new_evidence,
)


@pytest.fixture
def trail(tmp_path) -> AuditTrail:
    return AuditTrail(tmp_path / "trail.jsonl")


class TestEventTypes:
    def test_every_event_type_has_a_citation(self):
        for event in EventType:
            assert event.citation.startswith("MAS-AIRM")

    def test_incident_event_cites_5_23_b(self):
        assert EventType.INCIDENT.citation == "MAS-AIRM §5.23(b)"


class TestChain:
    def test_empty_trail(self, trail):
        assert len(trail) == 0
        assert trail.last() is None
        assert trail.verify()

    def test_first_record_chains_to_genesis(self, trail):
        record = trail.append(EventType.ASSESSMENT, actor="ci", summary="s")
        assert record.seq == 0
        assert record.prev_hash == GENESIS_HASH
        assert record.is_intact

    def test_records_chain_in_order(self, trail):
        first = trail.append(EventType.ASSESSMENT, actor="ci", summary="a")
        second = trail.append(EventType.EVALUATION, actor="ci", summary="b")
        assert second.seq == 1
        assert second.prev_hash == first.record_hash
        assert trail.verify()

    def test_tampering_with_content_is_detected(self, trail):
        trail.append(EventType.ASSESSMENT, actor="ci", summary="original")
        trail.append(EventType.EVALUATION, actor="ci", summary="second")
        lines = trail.path.read_text().splitlines()
        lines[0] = lines[0].replace('"summary":"original"', '"summary":"altered"')
        trail.path.write_text("\n".join(lines) + "\n")
        with pytest.raises(ChainError, match="has been altered"):
            trail.verify()

    def test_removing_a_record_is_detected(self, trail):
        trail.append(EventType.ASSESSMENT, actor="ci", summary="a")
        trail.append(EventType.EVALUATION, actor="ci", summary="b")
        trail.append(EventType.REVIEW, actor="ci", summary="c")
        lines = trail.path.read_text().splitlines()
        trail.path.write_text("\n".join([lines[0], lines[2]]) + "\n")
        with pytest.raises(ChainError, match="out of sequence"):
            trail.verify()

    def test_broken_prev_hash_is_detected(self, trail):
        trail.append(EventType.ASSESSMENT, actor="ci", summary="a")
        second = trail.append(EventType.EVALUATION, actor="ci", summary="b")
        lines = trail.path.read_text().splitlines()
        lines[1] = lines[1].replace(second.prev_hash, "0" * 64)
        trail.path.write_text("\n".join(lines) + "\n")
        with pytest.raises(ChainError, match="does not match"):
            trail.verify()

    def test_blank_lines_are_tolerated(self, trail):
        trail.append(EventType.ASSESSMENT, actor="ci", summary="a")
        with trail.path.open("a") as handle:
            handle.write("\n\n")
        assert trail.verify()

    def test_hash_is_reproducible(self, trail):
        record = trail.append(EventType.ASSESSMENT, actor="ci", summary="a")
        assert record.compute_hash() == record.record_hash


class TestQueries:
    def test_filter_by_use_case_and_type(self, trail):
        trail.append(EventType.ASSESSMENT, actor="ci", summary="a", use_case_id="x")
        trail.append(EventType.EVALUATION, actor="ci", summary="b", use_case_id="y")
        trail.append(EventType.EVALUATION, actor="ci", summary="c", use_case_id="x")
        assert len(trail.for_use_case("x")) == 2
        assert len(trail.of_type(EventType.EVALUATION)) == 2

    def test_evidence_map_feeds_the_control_checks(self, trail, tmp_path):
        path = tmp_path / "report.md"
        path.write_text("synthetic")
        trail.append(
            EventType.GUARDRAIL_TEST,
            actor="ci",
            summary="probes",
            use_case_id="x",
            evidence=[new_evidence("guardrail_test_report", path)],
        )
        assert trail.evidence_map("x") == {"guardrail_test_report": str(path)}

    def test_later_evidence_supersedes_earlier(self, trail):
        trail.append(
            EventType.REVIEW,
            actor="ci",
            summary="first",
            use_case_id="x",
            evidence=[Evidence(item="report", ref="old.md")],
        )
        trail.append(
            EventType.REVIEW,
            actor="ci",
            summary="second",
            use_case_id="x",
            evidence=[Evidence(item="report", ref="new.md")],
        )
        assert trail.evidence_map("x")["report"] == "new.md"

    def test_default_clauses_come_from_the_event_type(self, trail):
        record = trail.append(EventType.GUARDRAIL_TEST, actor="ci", summary="s")
        assert record.clauses == ["MAS-AIRM §5.15"]


class TestEvidence:
    def test_digest_recorded_for_a_local_file(self, tmp_path):
        path = tmp_path / "e.md"
        path.write_text("content")
        evidence = Evidence.from_file("item", path)
        assert evidence.digest and len(evidence.digest) == 64
        assert evidence.verify() is True

    def test_changed_file_fails_verification(self, tmp_path):
        path = tmp_path / "e.md"
        path.write_text("content")
        evidence = Evidence.from_file("item", path)
        path.write_text("changed")
        assert evidence.verify() is False

    def test_non_local_reference_is_not_checkable(self):
        assert Evidence(item="i", ref="https://example.invalid/x").verify() is None

    def test_no_digest_is_not_checkable(self, tmp_path):
        path = tmp_path / "e.md"
        path.write_text("x")
        assert Evidence(item="i", ref=str(path)).verify() is None

    def test_new_evidence_hashes_when_it_can(self, tmp_path):
        path = tmp_path / "e.md"
        path.write_text("x")
        assert new_evidence("i", path).digest is not None
        assert new_evidence("i", "not-a-file").digest is None

    def test_verify_evidence_across_the_trail(self, trail, tmp_path):
        path = tmp_path / "e.md"
        path.write_text("x")
        trail.append(EventType.REVIEW, actor="ci", summary="s", evidence=[new_evidence("i", path)])
        assert trail.verify_evidence() == {str(path): True}
        path.write_text("tampered")
        assert trail.verify_evidence() == {str(path): False}


class TestIncidents:
    def test_incident_round_trips_through_the_trail(self, trail):
        incident = Incident(
            id="INC-1",
            use_case_id="x",
            opened=dt.datetime(2026, 7, 22, 8, 0, tzinfo=dt.UTC),
            severity=Severity.BREACH,
            title="Elevated block rate",
            description="Circuit breaker triggered.",
            detected_by="monitoring",
            kill_switch_activated=True,
        )
        trail.append_incident(incident, actor="ops")
        assert trail.incidents()[0].id == "INC-1"
        assert trail.open_incidents()[0].id == "INC-1"

    def test_resolved_incident_is_not_open(self, trail):
        incident = Incident(
            id="INC-2",
            use_case_id="x",
            opened=dt.datetime(2026, 7, 22, tzinfo=dt.UTC),
            severity=Severity.WARNING,
            status=IncidentStatus.RESOLVED,
            title="t",
            description="d",
            detected_by="monitoring",
            closed=dt.datetime(2026, 7, 23, tzinfo=dt.UTC),
        )
        trail.append_incident(incident, actor="ops")
        assert trail.open_incidents() == []

    def test_closed_timestamp_requires_a_terminal_status(self):
        with pytest.raises(ValidationError, match="closed timestamp set"):
            Incident(
                id="INC-3",
                use_case_id="x",
                opened=dt.datetime(2026, 7, 22, tzinfo=dt.UTC),
                severity=Severity.INFO,
                status=IncidentStatus.OPEN,
                title="t",
                description="d",
                detected_by="monitoring",
                closed=dt.datetime(2026, 7, 23, tzinfo=dt.UTC),
            )

    def test_age_in_days(self):
        incident = Incident(
            id="INC-4",
            use_case_id="x",
            opened=dt.datetime(2026, 7, 22, tzinfo=dt.UTC),
            severity=Severity.INFO,
            status=IncidentStatus.RESOLVED,
            title="t",
            description="d",
            detected_by="monitoring",
            closed=dt.datetime(2026, 7, 25, tzinfo=dt.UTC),
        )
        assert incident.age_days == 3

    def test_incident_cites_the_definition_footnote(self):
        incident = Incident(
            id="INC-5",
            use_case_id="x",
            opened=dt.datetime(2026, 7, 22, tzinfo=dt.UTC),
            severity=Severity.INFO,
            title="t",
            description="d",
            detected_by="monitoring",
        )
        assert "MAS-AIRM §3.5 fn20" in incident.clauses

    def test_open_statuses(self):
        assert IncidentStatus.OPEN.is_open
        assert IncidentStatus.ESCALATED.is_open
        assert not IncidentStatus.CLOSED_NO_ACTION.is_open


def test_example_trail_verifies():
    """The shipped worked example's trail must stay intact in version control."""
    from tests.conftest import EXAMPLE_DIR

    trail = AuditTrail(EXAMPLE_DIR / "evidence" / "trail.jsonl")
    assert trail.verify()
    assert len(trail) > 10
    assert len(trail.incidents()) == 2


class TestLargeEvidenceFiles:
    def test_digest_is_chunked_and_matches_hashlib(self, tmp_path):
        """Evidence files can be large; hashing must not load the whole file into memory."""
        import hashlib

        from airm.monitor import Evidence

        target = tmp_path / "big.bin"
        payload = b"x" * (3 * (1 << 20) + 17)  # spans several 1 MiB chunks
        target.write_bytes(payload)

        item = Evidence.from_file("dataset", target)
        assert item.digest == hashlib.sha256(payload).hexdigest()
        assert item.verify() is True

        target.write_bytes(payload + b"!")
        assert item.verify() is False
