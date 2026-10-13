"""Append-only, hash-chained audit trail and incident log.

Serves MAS-AIRM §5.17 (documentation enabling reproducibility and auditability), §5.23(d) (clear
records of monitoring activities, results, issues and remediation, with access controlled and
logged) and §5.21 (review findings reported and actioned).

The trail is a JSONL file in which each record carries the hash of the previous record, so a
record cannot be altered or removed without breaking the chain. That is deliberately weaker than
signing: it makes silent edits detectable by anyone holding a later hash, which is what an auditor
needs, without requiring key management. ``docs/DECISIONS.md`` D-7 records the choice and
``docs/FUTURE_WORK.md`` the path to signatures.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from airm.catalog import cite

__all__ = [
    "AuditTrail",
    "ChainError",
    "EventType",
    "Evidence",
    "Incident",
    "IncidentSeverity",
    "IncidentStatus",
    "Record",
    "Severity",
    "new_evidence",
]

GENESIS_HASH = "0" * 64
"""Previous-hash value of the first record in a chain."""


class EventType(StrEnum):
    """What kind of thing the record attests to.

    The set covers the activities MAS-AIRM expects to be recorded: assessments (§4.13),
    evaluations and tests (§5.14-§5.15), reviews and validations (§5.18-§5.21), monitoring results
    and incidents (§5.23), changes and approvals (§5.25) and decommissioning (§5.26).
    """

    ASSESSMENT = "assessment"
    EVALUATION = "evaluation"
    GUARDRAIL_TEST = "guardrail_test"
    FAIRNESS_ASSESSMENT = "fairness_assessment"
    REVIEW = "review"
    INDEPENDENT_VALIDATION = "independent_validation"
    APPROVAL = "approval"
    ATTESTATION = "attestation"
    MONITORING = "monitoring"
    DRIFT_ALERT = "drift_alert"
    INCIDENT = "incident"
    CHANGE = "change"
    THIRD_PARTY_ASSESSMENT = "third_party_assessment"
    TOOL_SCOPE_AUDIT = "tool_scope_audit"
    DECOMMISSION = "decommission"
    SCAN = "scan"

    @property
    def citation(self) -> str:
        """Return the MAS-AIRM paragraph this event type primarily evidences."""
        return _EVENT_CITATIONS.get(self, cite("5.17"))


_EVENT_CITATIONS: dict[EventType, str] = {
    EventType.ASSESSMENT: cite("4.11"),
    EventType.EVALUATION: cite("5.14"),
    EventType.GUARDRAIL_TEST: cite("5.15"),
    EventType.FAIRNESS_ASSESSMENT: cite("5.8"),
    EventType.REVIEW: cite("5.18"),
    EventType.INDEPENDENT_VALIDATION: cite("5.19"),
    EventType.APPROVAL: cite("5.21"),
    EventType.ATTESTATION: cite("4.13"),
    EventType.MONITORING: cite("5.23"),
    EventType.DRIFT_ALERT: cite("5.23", item="a"),
    EventType.INCIDENT: cite("5.23", item="b"),
    EventType.CHANGE: cite("5.25"),
    EventType.THIRD_PARTY_ASSESSMENT: cite("5.11"),
    EventType.TOOL_SCOPE_AUDIT: cite("5.23", item="a"),
    EventType.DECOMMISSION: cite("5.26"),
    EventType.SCAN: cite("4.4"),
}


class Severity(StrEnum):
    """Severity of a monitoring or incident record."""

    INFO = "info"
    WARNING = "warning"
    BREACH = "breach"
    CRITICAL = "critical"


IncidentSeverity = Severity
"""Alias: MAS-AIRM §5.23(b) leaves severity classification to the FI (Response §10.69)."""


class IncidentStatus(StrEnum):
    """Lifecycle of an AI incident.

    MAS-AIRM §3.5 fn20 defines an AI incident as "incidents that involve a failure, malfunction, or
    poor performance of the underlying AI system(s) or model(s)". Response to Feedback §10.69
    confirms MAS sets no AI-specific severity framework or reporting regime, so the statuses here
    are an ordinary workflow, not a regulatory taxonomy.
    """

    OPEN = "open"
    INVESTIGATING = "investigating"
    ESCALATED = "escalated"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"
    CLOSED_NO_ACTION = "closed_no_action"

    @property
    def is_open(self) -> bool:
        """Whether the incident still needs action."""
        return self in (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING, IncidentStatus.ESCALATED)


class _Model(BaseModel):
    """Base model forbidding unknown fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Evidence(_Model):
    """A piece of evidence attached to a record.

    ``digest`` is the SHA-256 of the referenced file when the file was available at record time.
    Recording the digest rather than the file keeps the trail small while still letting a reviewer
    detect that an evidence file has changed since it was attested (MAS-AIRM §5.17).
    """

    item: str = Field(description="Evidence item name, matching a control's evidence list.")
    ref: str = Field(description="Path, URL or external id of the evidence.")
    digest: str | None = Field(default=None, description="SHA-256 of the file, if available.")
    note: str | None = None

    @classmethod
    def from_file(cls, item: str, path: str | Path, note: str | None = None) -> Evidence:
        """Build an evidence entry from a local file, recording its SHA-256 digest.

        Args:
            item: Evidence item name.
            path: Path to the evidence file.
            note: Optional note.

        Returns:
            The evidence entry with its digest filled in.
        """
        target = Path(path)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        return cls(item=item, ref=str(target), digest=digest, note=note)

    def verify(self) -> bool | None:
        """Re-hash the referenced file and compare with the recorded digest.

        Returns:
            True if the digest matches, False if it does not, None if there is nothing to check
            (no digest recorded, or the reference is not a readable local file).
        """
        if self.digest is None:
            return None
        target = Path(self.ref)
        if not target.is_file():
            return None
        return hashlib.sha256(target.read_bytes()).hexdigest() == self.digest


class Record(_Model):
    """One immutable record in the audit trail.

    Serves MAS-AIRM §5.23(d). The record is hashed over its canonical JSON form excluding its own
    ``record_hash``, so the hash is reproducible by anyone holding the record.
    """

    seq: int = Field(ge=0, description="Position in the chain, starting at 0.")
    timestamp: dt.datetime
    event: EventType
    use_case_id: str | None = Field(default=None, description="None for institution-level records.")
    actor: str = Field(description="Who or what created the record.")
    summary: str
    clauses: list[str] = Field(
        default_factory=list, description="MAS-AIRM citations this record evidences."
    )
    severity: Severity = Severity.INFO
    outcome: str | None = Field(
        default=None, description="e.g. 'pass', 'fail', 'needs_attestation'."
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Structured payload: metrics, thresholds, diffs."
    )
    evidence: list[Evidence] = Field(default_factory=list)
    prev_hash: str = Field(description="SHA-256 of the previous record, or the genesis hash.")
    record_hash: str = Field(default="", description="SHA-256 over this record's canonical form.")

    def canonical(self) -> str:
        """Return the canonical JSON form used for hashing (excludes ``record_hash``)."""
        payload = self.model_dump(mode="json", exclude={"record_hash"})
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def compute_hash(self) -> str:
        """Compute this record's SHA-256 over its canonical form."""
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()

    def sealed(self) -> Record:
        """Return a copy with ``record_hash`` set."""
        return self.model_copy(update={"record_hash": self.compute_hash()})

    @property
    def is_intact(self) -> bool:
        """Whether the stored hash matches a recomputation of the record."""
        return bool(self.record_hash) and self.record_hash == self.compute_hash()


class Incident(_Model):
    """An AI incident, as defined by MAS-AIRM §3.5 footnote 20.

    Serves §5.23(b) (reporting, tracking, escalating and resolving) and §3.5(e) (internal
    escalation for material risks and exceptions). MAS introduces no AI-specific reporting
    requirement (Response to Feedback §10.69); existing technology-risk and business-continuity
    reporting obligations continue to apply, which is why ``reported_externally`` is a plain field
    rather than a workflow.
    """

    id: str
    use_case_id: str
    opened: dt.datetime
    severity: Severity
    status: IncidentStatus = IncidentStatus.OPEN
    title: str
    description: str
    detected_by: str = Field(description="e.g. 'monitoring', 'user_report', 'review', 'incident'.")
    failure_mode: str | None = Field(
        default=None,
        description=(
            "For Generative AI, one of the MAS-AIRM §5.15 fn46 modes: hallucination, "
            "undesirable_content, bias, data_leakage, adversarial_vulnerability."
        ),
    )
    impact: str | None = None
    escalated_to: str | None = Field(default=None, description="Per MAS-AIRM §3.5(e).")
    resolution: str | None = Field(
        default=None,
        description="e.g. retraining, adjustment, redevelopment, decommissioning (§5.23(b)).",
    )
    near_miss: bool = Field(
        default=False, description="Near misses are reviewable under MAS-AIRM §5.9(d)."
    )
    kill_switch_activated: bool = Field(default=False, description="Per MAS-AIRM §5.23(b).")
    reported_externally: bool = Field(
        default=False,
        description="Whether reported to a regulator under existing obligations (Response §10.69).",
    )
    closed: dt.datetime | None = None
    clauses: list[str] = Field(
        default_factory=lambda: [cite("5.23", item="b"), cite("3.5", footnote=20)]
    )

    @model_validator(mode="after")
    def _closed_consistency(self) -> Self:
        """A closed timestamp requires a terminal status, so the log cannot contradict itself."""
        terminal = {
            IncidentStatus.RESOLVED,
            IncidentStatus.CLOSED_NO_ACTION,
            IncidentStatus.MITIGATED,
        }
        if self.closed is not None and self.status not in terminal:
            raise ValueError(
                f"incident {self.id}: closed timestamp set but status is {self.status.value}"
            )
        return self

    @property
    def age_days(self) -> int:
        """Days the incident has been open, to the close date or to now."""
        end = self.closed or dt.datetime.now(tz=self.opened.tzinfo)
        return (end - self.opened).days


class ChainError(RuntimeError):
    """Raised when an audit trail's hash chain does not verify."""


class AuditTrail:
    """An append-only, hash-chained JSONL audit trail.

    Serves MAS-AIRM §5.23(d) and §5.17. Records are appended, never rewritten; verification walks
    the chain and reports the first break.

    Examples:
        >>> import tempfile, pathlib
        >>> with tempfile.TemporaryDirectory() as d:
        ...     trail = AuditTrail(pathlib.Path(d) / "trail.jsonl")
        ...     _ = trail.append(EventType.ASSESSMENT, actor="ci", summary="assessed",
        ...                      use_case_id="demo")
        ...     _ = trail.append(EventType.EVALUATION, actor="ci", summary="evaluated",
        ...                      use_case_id="demo")
        ...     trail.verify()
        True
    """

    def __init__(self, path: str | Path) -> None:
        """Open (and create if needed) a trail at this path."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    # -- reading ---------------------------------------------------------------

    def __iter__(self) -> Iterator[Record]:
        """Iterate over the records in the trail, in order."""
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield Record.model_validate_json(line)

    def __len__(self) -> int:
        """Number of records in the trail."""
        return sum(1 for _ in self)

    def records(self) -> list[Record]:
        """Return all records as a list."""
        return list(self)

    def last(self) -> Record | None:
        """Return the last record, or None if the trail is empty."""
        last: Record | None = None
        for record in self:
            last = record
        return last

    def for_use_case(self, use_case_id: str) -> list[Record]:
        """Return the records for one use case."""
        return [r for r in self if r.use_case_id == use_case_id]

    def of_type(self, event: EventType) -> list[Record]:
        """Return the records of one event type."""
        return [r for r in self if r.event is event]

    def evidence_map(self, use_case_id: str) -> dict[str, str]:
        """Return evidence item to reference for one use case.

        This is what ``airm check`` feeds to the control catalogue: the evidence a use case has
        accumulated in the trail becomes the evidence its controls are evaluated against
        (MAS-AIRM §5.18-§5.21).
        """
        out: dict[str, str] = {}
        for record in self.for_use_case(use_case_id):
            for item in record.evidence:
                out[item.item] = item.ref
        return out

    # -- writing ---------------------------------------------------------------

    def append(
        self,
        event: EventType,
        *,
        actor: str,
        summary: str,
        use_case_id: str | None = None,
        clauses: list[str] | None = None,
        severity: Severity = Severity.INFO,
        outcome: str | None = None,
        data: dict[str, Any] | None = None,
        evidence: list[Evidence] | None = None,
        timestamp: dt.datetime | None = None,
    ) -> Record:
        """Append a record, chaining it to the current last record.

        Serves MAS-AIRM §5.23(d): a clear, auditable record of activities, results, issues and
        remediation.

        Args:
            event: What kind of event this is.
            actor: Who or what is recording it.
            summary: One-line human-readable summary.
            use_case_id: The use case, or None for institution-level records.
            clauses: MAS-AIRM citations; defaults to the event type's primary citation.
            severity: Severity of the record.
            outcome: Optional outcome string.
            data: Structured payload.
            evidence: Evidence entries.
            timestamp: Record time; defaults to now in UTC.

        Returns:
            The sealed record as written.
        """
        previous = self.last()
        record = Record(
            seq=0 if previous is None else previous.seq + 1,
            timestamp=timestamp or dt.datetime.now(tz=dt.UTC),
            event=event,
            use_case_id=use_case_id,
            actor=actor,
            summary=summary,
            clauses=clauses if clauses is not None else [event.citation],
            severity=severity,
            outcome=outcome,
            data=data or {},
            evidence=evidence or [],
            prev_hash=GENESIS_HASH if previous is None else previous.record_hash,
        ).sealed()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")
        return record

    def append_incident(self, incident: Incident, *, actor: str) -> Record:
        """Append an incident to the trail.

        Serves MAS-AIRM §5.23(b) and §3.5(e).
        """
        return self.append(
            EventType.INCIDENT,
            actor=actor,
            summary=f"{incident.severity.value}: {incident.title}",
            use_case_id=incident.use_case_id,
            clauses=incident.clauses,
            severity=incident.severity,
            outcome=incident.status.value,
            data=incident.model_dump(mode="json"),
            timestamp=incident.opened,
        )

    # -- integrity -------------------------------------------------------------

    def verify(self) -> bool:
        """Verify the hash chain.

        Returns:
            True if the chain is intact.

        Raises:
            ChainError: With the sequence number and nature of the first break found.
        """
        expected_prev = GENESIS_HASH
        for expected_seq, record in enumerate(self):
            if record.seq != expected_seq:
                raise ChainError(f"record {record.seq}: out of sequence, expected {expected_seq}")
            if record.prev_hash != expected_prev:
                raise ChainError(
                    f"record {record.seq}: prev_hash {record.prev_hash[:12]}... does not match "
                    f"previous record hash {expected_prev[:12]}..."
                )
            if not record.is_intact:
                raise ChainError(
                    f"record {record.seq}: contents do not match its recorded hash; the record "
                    f"has been altered"
                )
            expected_prev = record.record_hash
        return True

    def verify_evidence(self) -> dict[str, bool | None]:
        """Re-hash every evidence file referenced in the trail.

        Returns:
            Evidence reference to True (matches), False (changed) or None (not checkable).
        """
        out: dict[str, bool | None] = {}
        for record in self:
            for item in record.evidence:
                out[item.ref] = item.verify()
        return out

    def incidents(self) -> list[Incident]:
        """Return the incidents recorded in the trail."""
        return [Incident.model_validate(r.data) for r in self.of_type(EventType.INCIDENT)]

    def open_incidents(self) -> list[Incident]:
        """Return incidents that still need action (MAS-AIRM §5.23(b))."""
        return [i for i in self.incidents() if i.status.is_open]


def new_evidence(item: str, ref: str | Path, *, note: str | None = None) -> Evidence:
    """Build an evidence entry, hashing the file if it exists locally.

    Args:
        item: Evidence item name, matching a control's evidence list.
        ref: Path, URL or external id.
        note: Optional note.

    Returns:
        The evidence entry.
    """
    candidate = Path(ref)
    if candidate.is_file():
        return Evidence.from_file(item, candidate, note=note)
    return Evidence(item=item, ref=str(ref), note=note)
