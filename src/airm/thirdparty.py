"""Third-party AI assessment records.

Serves MAS-AIRM §5.10-§5.11. The Guidelines put primary accountability on the FI (§5.11), require
that transparency gaps be closed by *independent* certification or assessment rather than vendor
self-attestation (§5.11(a), Response to Feedback §9.9), and expect the FI to limit, suspend or
replace a service whose residual risk cannot be brought within appetite (§5.11).

This module records those decisions in a form a reviewer can check: the eight considerations of
§5.11(a)-(h) each get a status and an evidence pointer, and the final decision is an explicit
field, not an inference.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from airm.catalog import cite

__all__ = [
    "Assurance",
    "Consideration",
    "ConsiderationStatus",
    "Decision",
    "VendorAssessment",
    "VendorRegister",
]


class Consideration(StrEnum):
    """The eight third-party considerations MAS-AIRM §5.11 lists.

    Response to Feedback §9.5 confirms each "may be met to varying degrees depending on the nature
    and risk materiality of the AI use case", which is why each carries a status rather than a
    pass/fail.
    """

    TRANSPARENCY = "transparency"
    SUPPLY_CHAIN = "supply_chain"
    CONCENTRATION = "concentration"
    CHANGE_MANAGEMENT = "change_management"
    CONTINGENCY = "contingency"
    LEGAL_AGREEMENTS = "legal_agreements"
    CAPABILITIES = "capabilities"
    COMPLEXITY = "complexity"

    @property
    def citation(self) -> str:
        """Return the citation for this consideration's limb of MAS-AIRM §5.11."""
        return cite("5.11", item=_CONSIDERATION_ITEMS[self])

    @property
    def description(self) -> str:
        """Return a short description of what the limb asks for."""
        return _CONSIDERATION_DESCRIPTIONS[self]


_CONSIDERATION_ITEMS: dict[Consideration, str] = {
    Consideration.TRANSPARENCY: "a",
    Consideration.SUPPLY_CHAIN: "b",
    Consideration.CONCENTRATION: "c",
    Consideration.CHANGE_MANAGEMENT: "d",
    Consideration.CONTINGENCY: "e",
    Consideration.LEGAL_AGREEMENTS: "f",
    Consideration.CAPABILITIES: "g",
    Consideration.COMPLEXITY: "h",
}

_CONSIDERATION_DESCRIPTIONS: dict[Consideration, str] = {
    Consideration.TRANSPARENCY: (
        "Whether provider disclosures let the FI assess that lifecycle controls were applied; "
        "independent certifications or external assessments may substitute, "
        "self-attestations may not"
    ),
    Consideration.SUPPLY_CHAIN: (
        "Whether models, datasets and dependencies have had supply chain risk assessment, "
        "including provenance, training data integrity and known vulnerabilities."
    ),
    Consideration.CONCENTRATION: (
        "Whether use of this provider contributes to concentration risk, directly or indirectly"
    ),
    Consideration.CHANGE_MANAGEMENT: (
        "Whether the FI can receive notification of post-deployment updates and assess their impact"
    ),
    Consideration.CONTINGENCY: (
        "Whether contingency plans address provider failure, unexpected behaviour or "
        "discontinued vendor support."
    ),
    Consideration.LEGAL_AGREEMENTS: (
        "Whether agreements set performance guarantees, data protection, audit rights and "
        "notification or consent before AI is introduced or updated."
    ),
    Consideration.CAPABILITIES: (
        "Whether staff procuring, developing, deploying and using the third-party AI are capable"
    ),
    Consideration.COMPLEXITY: (
        "Whether the assessment is deeper for complex third-party AI the FI has less "
        "experience with."
    ),
}


class ConsiderationStatus(StrEnum):
    """How far a §5.11 consideration has been met."""

    MET = "met"
    PARTIALLY_MET = "partially_met"
    NOT_MET = "not_met"
    NOT_RELEVANT = "not_relevant"

    @property
    def is_gap(self) -> bool:
        """Whether this status leaves a gap needing a compensating control."""
        return self in (ConsiderationStatus.PARTIALLY_MET, ConsiderationStatus.NOT_MET)


class Assurance(StrEnum):
    """What kind of assurance the FI holds about the provider.

    MAS-AIRM §5.11(a) accepts "certifications or external assessments of the AI provider performed
    by independent and competent parties (i.e. not self-attestations)". Response to Feedback §9.9
    is explicit that self-attestation unsupported by evidence "would generally not be considered as
    effective". :meth:`is_independent` encodes exactly that line.
    """

    NONE = "none"
    SELF_ATTESTATION = "self_attestation"
    INDEPENDENT_ASSESSMENT = "independent_assessment"
    CERTIFICATION = "certification"
    FI_OWN_TESTING = "fi_own_testing"

    @property
    def is_independent(self) -> bool:
        """Whether this assurance satisfies the independence requirement of §5.11(a)."""
        return self in (Assurance.INDEPENDENT_ASSESSMENT, Assurance.CERTIFICATION)


class Decision(StrEnum):
    """The onboarding or continuation decision.

    MAS-AIRM §5.11: where residual risk materiality cannot be kept within appetite, "the FI should
    consider limiting or suspending the third-party AI service, or replacing the relevant
    third-party provider".
    """

    ONBOARD = "onboard"
    ONBOARD_WITH_CONDITIONS = "onboard_with_conditions"
    LIMIT = "limit"
    SUSPEND = "suspend"
    REPLACE = "replace"
    REJECT = "reject"

    @property
    def permits_use(self) -> bool:
        """Whether the decision allows the service to be used."""
        return self in (Decision.ONBOARD, Decision.ONBOARD_WITH_CONDITIONS, Decision.LIMIT)


class _Model(BaseModel):
    """Base model forbidding unknown fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ConsiderationRecord(_Model):
    """The FI's finding on one §5.11 consideration."""

    consideration: Consideration
    status: ConsiderationStatus
    finding: str = Field(description="What the FI found, in its own words.")
    evidence_ref: str | None = None
    compensating_controls: list[str] = Field(
        default_factory=list,
        description=(
            "Controls applied where the consideration is not fully met, e.g. additional testing "
            "on the FI's own data or greater human oversight (MAS-AIRM §5.11(a), Response §9.10)."
        ),
    )

    @property
    def citation(self) -> str:
        """Return the citation for the limb this record addresses."""
        return self.consideration.citation

    @model_validator(mode="after")
    def _gaps_need_mitigation(self) -> Self:
        """A gap with no compensating control is allowed but must be visible.

        MAS-AIRM §5.2 expects risks from practical constraints to be identified and mitigated, so
        the model keeps the gap explicit rather than rejecting it: the control catalogue reports
        it, which is the behaviour an FI needs when a vendor simply will not disclose.
        """
        return self


class VendorAssessment(_Model):
    """An assessment of one third-party AI provider or component.

    Serves MAS-AIRM §5.10-§5.11. The assessment is per provider-component-use-case triple, because
    §5.10 requires testing "in the context of the FI's use cases (including using the FI's own
    data)": the same model assessed for one use case is not thereby assessed for another.
    """

    id: str
    provider: str
    component: str
    version: str | None = None
    use_case_ids: list[str] = Field(
        default_factory=list, description="Use cases this assessment covers."
    )
    assessed_on: dt.date = Field(default_factory=dt.date.today)
    assessed_by: str = ""
    embedded: bool = Field(
        default=False, description="AI inside a service not marketed as AI (MAS-AIRM §4.2 fn21)."
    )
    material_provider: bool = Field(
        default=False,
        description="Material third-party service provider per the FI's own register (§4.2).",
    )
    assurance: Assurance = Assurance.NONE
    assurance_scope: str | None = Field(
        default=None,
        description=(
            "Which AI risks the certification or external assessment covers. §5.11(a) expects "
            "coverage of key risks; a certificate of unknown scope is not assurance."
        ),
    )
    assurance_body: str | None = Field(
        default=None, description="Who performed the assessment, for the independence test."
    )
    fi_testing_done: bool = Field(
        default=False,
        description="FI tested the component on its own data and use case (MAS-AIRM §5.10).",
    )
    fi_testing_ref: str | None = None
    considerations: list[ConsiderationRecord] = Field(default_factory=list)
    residual_within_appetite: bool | None = Field(
        default=None, description="Per MAS-AIRM §5.11; the FI's own determination."
    )
    decision: Decision = Decision.ONBOARD_WITH_CONDITIONS
    decision_rationale: str = ""
    decision_by: str | None = None
    review_due: dt.date | None = None
    clauses: list[str] = Field(default_factory=lambda: [cite("5.10"), cite("5.11")])

    @model_validator(mode="after")
    def _decision_consistency(self) -> Self:
        """A permitted use with residual risk outside appetite contradicts MAS-AIRM §5.11.

        §5.11 requires that the FI "ensure that the residual risk materiality of the use case which
        uses or depends on third-party AI is within the FI's risk appetite; where this cannot be
        achieved, the FI should consider limiting or suspending the third-party AI service, or
        replacing the relevant third-party provider". Recording "outside appetite" alongside a
        plain onboard decision would make the record internally inconsistent, so it is rejected.
        Limiting the service remains available, since that is one of the remedies §5.11 names.
        """
        if self.residual_within_appetite is False and self.decision in (
            Decision.ONBOARD,
            Decision.ONBOARD_WITH_CONDITIONS,
        ):
            raise ValueError(
                f"assessment {self.id}: residual risk is outside appetite but the decision is "
                f"{self.decision.value!r}; MAS-AIRM §5.11 expects the service to be limited or "
                f"suspended, or the provider replaced"
            )
        return self

    # -- derived views ---------------------------------------------------------

    @property
    def has_independent_assurance(self) -> bool:
        """Whether independent assurance is held, with a stated scope (§5.11(a))."""
        return self.assurance.is_independent and bool(self.assurance_scope)

    @property
    def relies_on_self_attestation(self) -> bool:
        """Whether the only assurance is a vendor self-attestation.

        Response to Feedback §9.9 treats this as generally ineffective for closing a transparency
        gap, so the control catalogue reports it as a finding.
        """
        return self.assurance is Assurance.SELF_ATTESTATION

    def gaps(self) -> tuple[ConsiderationRecord, ...]:
        """Return the considerations that are not fully met."""
        return tuple(c for c in self.considerations if c.status.is_gap)

    def unmitigated_gaps(self) -> tuple[ConsiderationRecord, ...]:
        """Return gaps with no compensating control recorded (MAS-AIRM §5.2, §5.11(a))."""
        return tuple(c for c in self.gaps() if not c.compensating_controls)

    def missing_considerations(self) -> tuple[Consideration, ...]:
        """Return the §5.11 limbs the assessment does not address at all."""
        addressed = {c.consideration for c in self.considerations}
        return tuple(c for c in Consideration if c not in addressed)

    def coverage(self) -> float:
        """Share of the eight §5.11 considerations the assessment addresses."""
        return len({c.consideration for c in self.considerations}) / len(Consideration)

    def is_overdue(self, *, as_of: dt.date | None = None) -> bool:
        """Whether the assessment's review date has passed (MAS-AIRM §5.24)."""
        if self.review_due is None:
            return False
        return (as_of or dt.date.today()) > self.review_due

    def findings(self) -> list[str]:
        """Return the findings a reviewer should see, each citing its paragraph.

        Serves MAS-AIRM §5.18-§5.21: the reviewer needs the gaps and the compensating controls,
        not the whole record.
        """
        out: list[str] = []
        if not self.fi_testing_done:
            out.append(
                f"{cite('5.10')}: no record of testing this component in the FI's own use case "
                f"context with the FI's own data"
            )
        if self.relies_on_self_attestation:
            out.append(
                f"{cite('5.11', item='a')}: assurance is a vendor self-attestation, which the "
                f"Response to Feedback §9.9 treats as generally ineffective"
            )
        if self.assurance.is_independent and not self.assurance_scope:
            out.append(
                f"{cite('5.11', item='a')}: independent assurance held but its scope is not "
                f"recorded, so coverage of key AI risks cannot be assessed"
            )
        for gap in self.unmitigated_gaps():
            out.append(
                f"{gap.citation}: {gap.consideration.value} is {gap.status.value} with no "
                f"compensating control recorded"
            )
        for missing in self.missing_considerations():
            out.append(f"{missing.citation}: {missing.value} not addressed by the assessment")
        if self.embedded and self.material_provider and not self.has_independent_assurance:
            out.append(
                f"{cite('4.2', footnote=21)}: embedded AI from a material provider with no "
                f"independent assurance"
            )
        if self.is_overdue():
            out.append(f"{cite('5.24')}: assessment review was due {self.review_due}")
        return out


class VendorRegister(_Model):
    """A collection of vendor assessments.

    Supports the concentration view MAS-AIRM §5.11(c) and §3.4 footnote 18 ask for, across
    providers rather than within one use case.
    """

    institution: str
    as_of: dt.date = Field(default_factory=dt.date.today)
    assessments: list[VendorAssessment] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        """Assessment ids must be unique."""
        seen: set[str] = set()
        for assessment in self.assessments:
            if assessment.id in seen:
                raise ValueError(f"duplicate vendor assessment id: {assessment.id!r}")
            seen.add(assessment.id)
        return self

    def __len__(self) -> int:
        """Number of assessments."""
        return len(self.assessments)

    def get(self, assessment_id: str) -> VendorAssessment:
        """Return an assessment by id.

        Raises:
            KeyError: If no such assessment exists.
        """
        for assessment in self.assessments:
            if assessment.id == assessment_id:
                return assessment
        raise KeyError(f"no such vendor assessment: {assessment_id!r}")

    def for_use_case(self, use_case_id: str) -> tuple[VendorAssessment, ...]:
        """Return the assessments covering one use case."""
        return tuple(a for a in self.assessments if use_case_id in a.use_case_ids)

    def by_provider(self) -> dict[str, list[VendorAssessment]]:
        """Group assessments by provider."""
        out: dict[str, list[VendorAssessment]] = {}
        for assessment in self.assessments:
            out.setdefault(assessment.provider, []).append(assessment)
        return dict(sorted(out.items()))

    def concentration(self) -> dict[str, int]:
        """Return provider to number of use cases depending on it (MAS-AIRM §5.11(c))."""
        out: dict[str, int] = {}
        for provider, assessments in self.by_provider().items():
            use_cases = {uc for a in assessments for uc in a.use_case_ids}
            out[provider] = len(use_cases)
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    def self_attested_only(self) -> tuple[VendorAssessment, ...]:
        """Return assessments whose only assurance is a vendor self-attestation."""
        return tuple(a for a in self.assessments if a.relies_on_self_attestation)

    def overdue(self, *, as_of: dt.date | None = None) -> tuple[VendorAssessment, ...]:
        """Return assessments past their review date (MAS-AIRM §5.24)."""
        return tuple(a for a in self.assessments if a.is_overdue(as_of=as_of))

    def all_findings(self) -> dict[str, list[str]]:
        """Return assessment id to findings, for the audit pack."""
        return {a.id: a.findings() for a in self.assessments if a.findings()}

    @classmethod
    def load(cls, path: str | Path) -> VendorRegister:
        """Load a vendor register from YAML or JSON. The file is data, never code."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a mapping at the top level")
        return cls.model_validate(data)

    def save(self, path: str | Path) -> Path:
        """Write the vendor register to YAML."""
        target = Path(path)
        target.write_text(
            yaml.safe_dump(
                self.model_dump(mode="json", exclude_none=True), sort_keys=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
        return target
