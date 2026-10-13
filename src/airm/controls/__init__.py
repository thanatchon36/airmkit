"""Control catalogue mapped to the MAS-AIRM life cycle controls, with automated checks.

Serves MAS-AIRM Section 5 (§5.1-§5.26) plus the Section 4 process controls (§4.3-§4.13). Each
control carries:

* the paragraph(s) it implements, so nothing in the catalogue is untraceable;
* applicability by risk materiality tier, implementing the proportionality of §5.2;
* the evidence it requires, so a reviewer under §5.18-§5.21 knows what to ask for;
* an **automatability class** (``auto`` / ``semi`` / ``doc``) which is the RQ1 classification; and
* an optional check function that decides the outcome from the inventory entry and its evidence.

Outcomes follow the MISSION: ``pass``, ``fail``, ``needs_attestation``, ``not_applicable``. A
control whose automatability class is ``semi`` can at best reach ``needs_attestation`` from
artefacts alone, because a machine can see that an artefact exists but not that it is adequate.
A ``doc`` control is always ``needs_attestation`` when applicable.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from airm.catalog import load_catalogue
from airm.inventory import LifecycleStatus, Register, ReviewStatus, UseCase
from airm.materiality import Assessment, Tier, assess

__all__ = [
    "Automatability",
    "InstitutionReport",
    "Scope",
    "check_institution",
    "CheckResult",
    "Control",
    "ControlCatalogue",
    "Outcome",
    "UseCaseReport",
    "check_register",
    "check_use_case",
    "load_controls",
    "register_check",
]


class Outcome(StrEnum):
    """Result of evaluating a control against a use case."""

    PASS = "pass"
    FAIL = "fail"
    NEEDS_ATTESTATION = "needs_attestation"
    NOT_APPLICABLE = "not_applicable"

    @property
    def is_adverse(self) -> bool:
        """Whether the outcome needs action before the control can be relied on."""
        return self in (Outcome.FAIL, Outcome.NEEDS_ATTESTATION)


class Scope(StrEnum):
    """Whether a control is evaluated per use case or once for the institution.

    MAS-AIRM mixes the two: §5.15 is about a use case's guardrails, while §3.3 and §4.1 are about
    the institution's framework. Evaluating institution-level clauses once avoids reporting the
    same organisational gap eight times.
    """

    USE_CASE = "use_case"
    INSTITUTION = "institution"


class Automatability(StrEnum):
    """How far a control can be checked without human judgement (RQ1 classification).

    ``AUTO``
        A deterministic function of the inventory entry and its evidence decides pass/fail.
    ``SEMI``
        A machine can detect whether the required artefact exists and is current, but a human must
        attest that it is adequate.
    ``DOC``
        Compliance is an organisational or judgemental fact with no artefact the toolkit inspects.

    See ``docs/DECISIONS.md`` D-6. The classification is the authors' judgement relative to this
    implementation, not a MAS classification.
    """

    AUTO = "auto"
    SEMI = "semi"
    DOC = "doc"

    @property
    def best_outcome(self) -> Outcome:
        """The best outcome this class can reach from artefacts alone."""
        return Outcome.PASS if self is Automatability.AUTO else Outcome.NEEDS_ATTESTATION


class _Model(BaseModel):
    """Base model forbidding unknown fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CheckResult(_Model):
    """The outcome of one control for one use case, with its reason and evidence pointers."""

    control_id: str
    outcome: Outcome
    reason: str
    clauses: list[str] = Field(default_factory=list)
    automatability: Automatability = Automatability.DOC
    evidence_required: list[str] = Field(default_factory=list)
    evidence_found: list[str] = Field(default_factory=list)
    evidence_missing: list[str] = Field(default_factory=list)
    effective_by: dt.date | None = Field(
        default=None, description="Date the underlying clause must be met (MAS-AIRM §1.8)."
    )

    @property
    def is_adverse(self) -> bool:
        """Whether this result needs action."""
        return self.outcome.is_adverse


CheckFn = Callable[[UseCase, Assessment, "Control"], tuple[Outcome, str]]
"""Signature of a control check: given the use case, its assessment and the control, decide."""

_CHECKS: dict[str, CheckFn] = {}


def register_check(name: str) -> Callable[[CheckFn], CheckFn]:
    """Register a named check function so a YAML control can reference it.

    Keeping checks in code and controls in data means an institution can add controls without
    writing Python, and can add checks without rewriting the catalogue.

    Args:
        name: The ``check`` value used in ``controls.yaml``.

    Returns:
        A decorator registering the function.
    """

    def decorator(fn: CheckFn) -> CheckFn:
        _CHECKS[name] = fn
        return fn

    return decorator


class Control(_Model):
    """One control in the catalogue.

    Every control must cite at least one MAS-AIRM paragraph: the MISSION requires traceability over
    coverage, so a control with no clause reference is a validation error.
    """

    id: str
    title: str
    family: str = Field(description="Control family, e.g. 'data', 'human_oversight', 'security'.")
    scope: Scope = Field(
        default=Scope.USE_CASE,
        description="Whether the control is evaluated per use case or once for the institution.",
    )
    clauses: list[str] = Field(
        min_length=1, description="MAS-AIRM paragraph ids, e.g. ['5.15'] or ['5.23.a']."
    )
    intent: str = Field(description="What outcome the control is trying to secure.")
    applies_from_tier: Tier = Field(
        default=Tier.LOW, description="Lowest tier at which the control applies (MAS-AIRM §5.2)."
    )
    high_materiality_only: bool = Field(
        default=False,
        description="Applies only to High/Critical inherent tiers (MAS-AIRM §5.3, §5.19).",
    )
    requires_tags: list[str] = Field(
        default_factory=list,
        description="Only applies if the use case carries any of these tags (genai, agent, ...).",
    )
    requires_live: bool = Field(
        default=False, description="Only applies to piloted or deployed use cases."
    )
    requires_third_party: bool = Field(default=False)
    requires_fairness: bool = Field(default=False)
    automatability: Automatability = Automatability.DOC
    automatability_rationale: str = Field(
        default="", description="Why this class, for the RQ1 classification table."
    )
    evidence: list[str] = Field(
        default_factory=list, description="Evidence items a reviewer should expect."
    )
    check: str | None = Field(
        default=None, description="Name of a registered check function, if any."
    )
    guidance: str = ""

    @model_validator(mode="after")
    def _known_check(self) -> Self:
        """A named check must exist, and only `auto`/`semi` controls may have one."""
        institution_checks = {"control_functions_designated", "register_linkages_declared"}
        if self.check is not None and self.check not in _CHECKS:
            if not (self.scope is Scope.INSTITUTION and self.check in institution_checks):
                raise ValueError(f"control {self.id}: unknown check {self.check!r}")
        if self.check is None and self.automatability is Automatability.AUTO:
            raise ValueError(
                f"control {self.id}: automatability 'auto' requires a check function"
            )
        return self

    @property
    def citations(self) -> list[str]:
        """Return the clause citations in display form, e.g. ``MAS-AIRM §5.23(d)``."""
        return [_format_clause(c) for c in self.clauses]

    def effective_by(self) -> dt.date | None:
        """Return the latest effective date among the clauses this control implements.

        Implements MAS-AIRM §1.8: a control implementing a Section 5 clause is not due until
        7 October 2028, while a Section 4 clause is due 7 October 2027.
        """
        catalogue = load_catalogue()
        dates = []
        for clause in self.clauses:
            paragraph_id = clause.split(".fn")[0].rsplit(".", 1)[0] if _has_item(clause) else clause
            paragraph_id = paragraph_id.split("fn")[0].strip(".")
            if paragraph_id in catalogue:
                dates.append(catalogue.effective_date(paragraph_id))
        return max(dates) if dates else None

    def applies_to(self, use_case: UseCase, assessment: Assessment) -> tuple[bool, str]:
        """Whether this control applies to a use case, and why not if it does not.

        Implements the proportionality of MAS-AIRM §5.2 and the high-materiality triggers, which
        key on *inherent* materiality per Response to Feedback §7.21.

        Args:
            use_case: The inventory entry.
            assessment: Its risk materiality assessment.

        Returns:
            ``(applies, reason)``. When ``applies`` is False the reason explains the exclusion, as
            MAS-AIRM §5.2 expects practical constraints and non-relevance to be identified.
        """
        if self.high_materiality_only and not assessment.is_high_materiality:
            return False, (
                f"applies only to high risk materiality; inherent tier is "
                f"{assessment.inherent_tier.value}"
            )
        if assessment.inherent_tier.rank < self.applies_from_tier.rank:
            return False, (
                f"applies from tier {self.applies_from_tier.value}; inherent tier is "
                f"{assessment.inherent_tier.value}"
            )
        if self.requires_tags and not set(self.requires_tags).intersection(
            use_case.catalogue_tags
        ):
            return False, f"applies only to use cases tagged {sorted(self.requires_tags)}"
        if self.requires_live and not use_case.lifecycle_status.is_live:
            return False, (
                f"applies to piloted or deployed AI; status is {use_case.lifecycle_status.value}"
            )
        if self.requires_third_party and not use_case.uses_third_party_ai:
            return False, "no third-party AI component recorded"
        if self.requires_fairness and not use_case.is_fairness_relevant:
            return False, "fairness considerations assessed as not relevant (MAS-AIRM §5.8)"
        return True, "applicable"

    def evaluate(
        self,
        use_case: UseCase,
        assessment: Assessment,
        evidence: dict[str, str] | None = None,
    ) -> CheckResult:
        """Evaluate this control against a use case.

        Args:
            use_case: The inventory entry.
            assessment: Its risk materiality assessment.
            evidence: Optional map of evidence item name to a pointer (path, id or URL).

        Returns:
            A :class:`CheckResult`. Controls classed ``doc`` always return
            ``needs_attestation`` when applicable, because there is no artefact to inspect.
        """
        evidence = evidence or {}
        applies, reason = self.applies_to(use_case, assessment)
        found = [item for item in self.evidence if item in evidence]
        missing = [item for item in self.evidence if item not in evidence]
        base = {
            "control_id": self.id,
            "clauses": self.citations,
            "automatability": self.automatability,
            "evidence_required": list(self.evidence),
            "evidence_found": found,
            "evidence_missing": missing,
            "effective_by": self.effective_by(),
        }
        if not applies:
            return CheckResult(outcome=Outcome.NOT_APPLICABLE, reason=reason, **base)

        if self.check is not None:
            outcome, detail = _CHECKS[self.check](use_case, assessment, self)
            if outcome is Outcome.PASS and self.automatability is Automatability.SEMI:
                return CheckResult(
                    outcome=Outcome.NEEDS_ATTESTATION,
                    reason=f"{detail}; adequacy needs human attestation",
                    **base,
                )
            return CheckResult(outcome=outcome, reason=detail, **base)

        kind = "documentary" if self.automatability is Automatability.DOC else "semi-automated"
        if missing:
            return CheckResult(
                outcome=Outcome.NEEDS_ATTESTATION,
                reason=f"{kind} control; evidence not supplied: {', '.join(missing)}",
                **base,
            )
        return CheckResult(
            outcome=Outcome.NEEDS_ATTESTATION,
            reason=f"{kind} control; evidence supplied, adequacy needs attestation",
            **base,
        )


class UseCaseReport(_Model):
    """All control results for one use case, plus counts."""

    use_case_id: str
    inherent_tier: Tier
    residual_tier: Tier
    results: list[CheckResult] = Field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        """Count of results per outcome."""
        counts = dict.fromkeys((o.value for o in Outcome), 0)
        for result in self.results:
            counts[result.outcome.value] += 1
        return counts

    @property
    def applicable(self) -> tuple[CheckResult, ...]:
        """Results for controls that apply to this use case."""
        return tuple(r for r in self.results if r.outcome is not Outcome.NOT_APPLICABLE)

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        """Results that failed an automated check."""
        return tuple(r for r in self.results if r.outcome is Outcome.FAIL)

    @property
    def attestations(self) -> tuple[CheckResult, ...]:
        """Results awaiting human attestation."""
        return tuple(r for r in self.results if r.outcome is Outcome.NEEDS_ATTESTATION)

    def by_effective_date(self) -> dict[str, list[str]]:
        """Group adverse control ids by the date their clause becomes effective (MAS-AIRM §1.8)."""
        out: dict[str, list[str]] = {}
        for result in self.results:
            if result.is_adverse and result.effective_by:
                out.setdefault(result.effective_by.isoformat(), []).append(result.control_id)
        return {k: sorted(v) for k, v in sorted(out.items())}


class ControlCatalogue(_Model):
    """The control catalogue, loaded from ``controls.yaml`` inside this package."""

    id: str = "airmkit-default"
    version: str = "1"
    description: str = ""
    controls: list[Control] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_and_cited(self) -> Self:
        """Control ids must be unique and every clause must exist in the clause catalogue."""
        catalogue = load_catalogue()
        seen: set[str] = set()
        for control in self.controls:
            if control.id in seen:
                raise ValueError(f"duplicate control id: {control.id}")
            seen.add(control.id)
            for clause in control.clauses:
                paragraph_id = _paragraph_of(clause)
                if paragraph_id not in catalogue:
                    raise ValueError(
                        f"control {control.id} cites unknown paragraph {paragraph_id!r}"
                    )
        return self

    def __iter__(self) -> Any:  # type: ignore[override]
        """Iterate over controls."""
        return iter(self.controls)

    def __len__(self) -> int:
        """Number of controls."""
        return len(self.controls)

    def get(self, control_id: str) -> Control:
        """Return a control by id.

        Raises:
            KeyError: If no such control exists.
        """
        for control in self.controls:
            if control.id == control_id:
                return control
        raise KeyError(f"no such control: {control_id!r}")

    def families(self) -> tuple[str, ...]:
        """Return the control families present, in catalogue order."""
        seen: list[str] = []
        for control in self.controls:
            if control.family not in seen:
                seen.append(control.family)
        return tuple(seen)

    def by_family(self, family: str) -> tuple[Control, ...]:
        """Return the controls in one family."""
        return tuple(c for c in self.controls if c.family == family)

    def by_clause(self, paragraph_id: str) -> tuple[Control, ...]:
        """Return the controls implementing a MAS-AIRM paragraph.

        This is what generates the docs-site clause index: paragraph to implementing control.
        """
        return tuple(
            c for c in self.controls if any(_paragraph_of(x) == paragraph_id for x in c.clauses)
        )

    def automatability_counts(self) -> dict[str, int]:
        """Count controls per automatability class (the RQ1 headline numbers)."""
        counts = dict.fromkeys((a.value for a in Automatability), 0)
        for control in self.controls:
            counts[control.automatability.value] += 1
        return counts

    def covered_paragraphs(self) -> tuple[str, ...]:
        """Return the MAS-AIRM paragraph ids at least one control implements."""
        return tuple(sorted({_paragraph_of(c) for ctl in self.controls for c in ctl.clauses}))

    def uncovered_expectations(self) -> tuple[str, ...]:
        """Return expectation paragraphs no control implements.

        Serves the gap analysis: the MISSION prefers a traceable catalogue to a complete-looking
        one, so the uncovered set is published rather than hidden.
        """
        covered = set(self.covered_paragraphs())
        return tuple(p.id for p in load_catalogue().expectations() if p.id not in covered)

    @classmethod
    def load(cls, path: str | Path | None = None) -> ControlCatalogue:
        """Load the control catalogue from YAML, or the packaged default."""
        if path is None:
            text = (
                resources.files("airm.controls")
                .joinpath("controls.yaml")
                .read_text(encoding="utf-8")
            )
        else:
            text = Path(path).read_text(encoding="utf-8")
        data: Any = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("control catalogue file must contain a mapping at the top level")
        return cls.model_validate(data)


def _has_item(clause: str) -> bool:
    """Whether a clause reference carries a lettered item, e.g. ``5.23.d``."""
    parts = clause.split(".")
    return len(parts) == 3 and parts[2].isalpha() and not parts[2].startswith("fn")


def _paragraph_of(clause: str) -> str:
    """Return the paragraph id of a clause reference such as ``5.23.d`` or ``4.8.fn25``."""
    parts = clause.split(".")
    return ".".join(parts[:2])


def _format_clause(clause: str) -> str:
    """Format a clause reference for display, e.g. ``5.23.d`` -> ``MAS-AIRM §5.23(d)``."""
    parts = clause.split(".")
    paragraph = ".".join(parts[:2])
    if len(parts) == 3 and parts[2].startswith("fn"):
        return f"MAS-AIRM §{paragraph} {parts[2]}"
    if len(parts) == 3:
        return f"MAS-AIRM §{paragraph}({parts[2]})"
    return f"MAS-AIRM §{paragraph}"


def load_controls(path: str | Path | None = None) -> ControlCatalogue:
    """Load the control catalogue, or the packaged default."""
    return ControlCatalogue.load(path)


def check_use_case(
    use_case: UseCase,
    *,
    assessment: Assessment | None = None,
    catalogue: ControlCatalogue | None = None,
    evidence: dict[str, str] | None = None,
) -> UseCaseReport:
    """Evaluate every control against one use case.

    Serves MAS-AIRM §5.2 (proportionate application of relevant controls) and the review
    expectations of §5.18-§5.21, by producing the pass / fail / needs-attestation /
    not-applicable statement a reviewer works from.

    Args:
        use_case: The inventory entry.
        assessment: Its materiality assessment; computed with the default rubric if omitted.
        catalogue: The control catalogue; the packaged default if omitted.
        evidence: Map of evidence item name to pointer.

    Returns:
        A :class:`UseCaseReport`.

    Examples:
        >>> from airm.inventory import UseCase
        >>> uc = UseCase(id="demo", name="Demo", purpose="p")
        >>> report = check_use_case(uc)
        >>> report.counts["not_applicable"] > 0
        True
    """
    active_assessment = assessment or assess(use_case)
    active_catalogue = catalogue or load_controls()
    return UseCaseReport(
        use_case_id=use_case.id,
        inherent_tier=active_assessment.inherent_tier,
        residual_tier=active_assessment.residual_tier,
        results=[
            control.evaluate(use_case, active_assessment, evidence)
            for control in active_catalogue.controls
            if control.scope is Scope.USE_CASE
        ],
    )


class InstitutionReport(_Model):
    """Institution-level control results, evaluated once rather than per use case.

    Serves the clauses that are about the FI's framework rather than a single use case: §2.5
    (basic AI governance policies), §3.2-§3.3 (board and senior management oversight), §3.6 (local
    senior management accountability), §4.1 (the framework encompassing identification,
    inventorisation and materiality) and §1.7 (regular review against AI developments).
    """

    institution: str
    results: list[CheckResult] = Field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        """Count of results per outcome."""
        counts = dict.fromkeys((o.value for o in Outcome), 0)
        for result in self.results:
            counts[result.outcome.value] += 1
        return counts

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        """Institution-level controls that failed an automated check."""
        return tuple(r for r in self.results if r.outcome is Outcome.FAIL)


def check_institution(
    register: Register, *, catalogue: ControlCatalogue | None = None,
    evidence: dict[str, str] | None = None,
) -> InstitutionReport:
    """Evaluate the institution-level controls once against a register.

    Serves MAS-AIRM §2.5, §3.2-§3.3, §3.6, §4.1 and §1.7, which are expectations on the FI's
    framework rather than on any single use case.

    Args:
        register: The AI inventory register, whose metadata carries the designated control
            functions (MAS-AIRM §4.3, §4.9, §4.13) and register linkages (§4.6 fn23).
        catalogue: The control catalogue; the packaged default if omitted.
        evidence: Map of evidence item name to pointer.

    Returns:
        An :class:`InstitutionReport`.
    """
    active = catalogue or load_controls()
    evidence = evidence or {}
    results: list[CheckResult] = []
    for control in active.controls:
        if control.scope is not Scope.INSTITUTION:
            continue
        found = [i for i in control.evidence if i in evidence]
        missing = [i for i in control.evidence if i not in evidence]
        base: dict[str, Any] = {
            "control_id": control.id,
            "clauses": control.citations,
            "automatability": control.automatability,
            "evidence_required": list(control.evidence),
            "evidence_found": found,
            "evidence_missing": missing,
            "effective_by": control.effective_by(),
        }
        if control.check == "control_functions_designated":
            missing_fns = register.missing_control_functions()
            if missing_fns:
                results.append(
                    CheckResult(
                        outcome=Outcome.FAIL,
                        reason=(
                            f"no control function designated for: {', '.join(missing_fns)} "
                            f"(MAS-AIRM §4.3, §4.9, §4.13)"
                        ),
                        **base,
                    )
                )
            else:
                results.append(
                    CheckResult(
                        outcome=Outcome.PASS,
                        reason=(
                            "control functions designated for identification, inventory and "
                            "materiality assessment"
                        ),
                        **base,
                    )
                )
            continue
        if control.check == "register_linkages_declared":
            if not register.linked_registers:
                results.append(
                    CheckResult(
                        outcome=Outcome.FAIL,
                        reason="no linkages declared to other registers (MAS-AIRM §4.6 fn23)",
                        **base,
                    )
                )
            else:
                results.append(
                    CheckResult(
                        outcome=Outcome.PASS,
                        reason=(
                            f"linked registers: {', '.join(sorted(register.linked_registers))}"
                        ),
                        **base,
                    )
                )
            continue
        kind = "documentary" if control.automatability is Automatability.DOC else "semi-automated"
        reason = (
            f"{kind} control; evidence not supplied: {', '.join(missing)}"
            if missing
            else f"{kind} control; evidence supplied, adequacy needs attestation"
        )
        results.append(CheckResult(outcome=Outcome.NEEDS_ATTESTATION, reason=reason, **base))
    return InstitutionReport(institution=register.institution, results=results)


def check_register(
    register: Register,
    *,
    catalogue: ControlCatalogue | None = None,
    evidence: dict[str, dict[str, str]] | None = None,
) -> dict[str, UseCaseReport]:
    """Evaluate every control against every use case in a register.

    Args:
        register: The AI inventory register.
        catalogue: The control catalogue; the packaged default if omitted.
        evidence: Map of use case id to its evidence map.

    Returns:
        Use case id to :class:`UseCaseReport`.
    """
    active_catalogue = catalogue or load_controls()
    evidence = evidence or {}
    return {
        uc.id: check_use_case(
            uc, catalogue=active_catalogue, evidence=evidence.get(uc.id, {})
        )
        for uc in register.use_cases
    }


# --------------------------------------------------------------------------- checks
#
# Each check is a deterministic function of the inventory entry and its assessment. Checks never
# consult the network and never execute anything from the register, which is untrusted data.


@register_check("inventory_completeness")
def _check_inventory_completeness(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §4.7: inventory captures the named attributes at appropriate granularity."""
    completeness = use_case.completeness()
    if completeness.is_complete:
        return Outcome.PASS, "all §4.7 attributes recorded"
    return Outcome.FAIL, (
        f"missing §4.7 attributes: {', '.join(completeness.missing)}"
        if completeness.missing
        else f"missing §4.8 fn25 agent attributes: {', '.join(completeness.agent_missing)}"
    )


@register_check("agent_attributes")
def _check_agent_attributes(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §4.8 fn25: agent identifiers, tools and systems, components, guardrails."""
    if use_case.agent is None:
        return Outcome.NOT_APPLICABLE, "not an agentic use case"
    missing = use_case.completeness().agent_missing
    if missing:
        return Outcome.FAIL, f"missing agent attributes: {', '.join(missing)}"
    return Outcome.PASS, "agent identifier, tools/systems, components and guardrails recorded"


@register_check("guardrail_effectiveness")
def _check_guardrail_effectiveness(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.15 and fn46: guardrail effectiveness is tested, not merely present."""
    rails = use_case.all_guardrails
    if not rails:
        return Outcome.FAIL, "no guardrails recorded for a Generative AI or agentic use case"
    untested = use_case.untested_guardrails
    if untested:
        return Outcome.FAIL, (
            f"guardrails with no recorded effectiveness test: {', '.join(untested)}"
        )
    without_evidence = [g.name for g in rails if g.tested and not g.evidence_ref]
    if without_evidence:
        return Outcome.FAIL, (
            f"guardrails marked tested but with no evidence pointer: "
            f"{', '.join(without_evidence)}"
        )
    return Outcome.PASS, f"{len(rails)} guardrail(s) tested with evidence pointers"


@register_check("independent_validation")
def _check_independent_validation(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.19: formal independent validation for high-materiality use cases."""
    if use_case.review_status is not ReviewStatus.INDEPENDENT_VALIDATION:
        return Outcome.FAIL, (
            f"review status is {use_case.review_status.value}; §5.19 expects formal independent "
            f"validation for high risk materiality"
        )
    if not use_case.has_independent_validator():
        return Outcome.FAIL, (
            "no validator recorded who is independent of the owner, developer, deployer and "
            "operator (§5.19, §5.20 fn48)"
        )
    return Outcome.PASS, (
        f"independent validation by {use_case.role_party('validator')}, independent of "
        f"development and deployment"
    )


@register_check("documented_review")
def _check_documented_review(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.18 and §5.20: a documented review by parties not involved in development."""
    if use_case.review_status in (ReviewStatus.NOT_REVIEWED, ReviewStatus.IN_REVIEW):
        return Outcome.FAIL, f"review status is {use_case.review_status.value}"
    return Outcome.PASS, f"review on record: {use_case.review_status.value}"


@register_check("contingency_plan")
def _check_contingency_plan(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.3: contingency plans with fallback options for high-risk use cases."""
    if not use_case.contingency_plan:
        return Outcome.FAIL, "no contingency plan or fallback option recorded"
    return Outcome.PASS, f"fallback recorded: {use_case.contingency_plan}"


@register_check("kill_switch")
def _check_kill_switch(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.3 fn29 and §5.23(b): kill switch or override for high-risk AI."""
    if not use_case.kill_switch:
        return Outcome.FAIL, "no kill switch or override mechanism recorded"
    return Outcome.PASS, "kill switch or override mechanism recorded"


@register_check("human_oversight_recorded")
def _check_human_oversight(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.9: controls ensuring appropriate human oversight across the life cycle."""
    if not use_case.human_oversight:
        return Outcome.FAIL, "no human oversight arrangement recorded"
    return Outcome.PASS, f"oversight arrangement recorded: {use_case.human_oversight}"


@register_check("agent_human_checkpoints")
def _check_agent_checkpoints(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.9(c): design for oversight, escalating when predefined conditions are met."""
    if use_case.agent is None:
        return Outcome.NOT_APPLICABLE, "not an agentic use case"
    if not use_case.agent.human_checkpoints:
        return Outcome.FAIL, (
            "no human checkpoints recorded for an agent; §5.9(c) expects mechanisms to escalate "
            "for human review where pre-defined conditions are met"
        )
    return Outcome.PASS, (
        f"{len(use_case.agent.human_checkpoints)} human checkpoint(s) recorded"
    )


@register_check("agent_tool_scope")
def _check_agent_tool_scope(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §4.8 fn25 with §5.16(b): the agent's approved tool scope is declared.

    The observed-versus-approved comparison itself lives in ``airm.evals.tool_scope_audit``,
    which needs a trace; this control checks that an approved scope exists to compare against.
    """
    if use_case.agent is None:
        return Outcome.NOT_APPLICABLE, "not an agentic use case"
    agent = use_case.agent
    if not agent.approved_tools and not agent.systems_accessible:
        return Outcome.FAIL, "no approved tools or systems recorded, so scope cannot be monitored"
    if agent.can_initiate_external_actions and not agent.permissions:
        return Outcome.FAIL, (
            "agent can initiate external actions but no permissions are recorded (§5.16(b))"
        )
    return Outcome.PASS, (
        f"{len(agent.approved_tools)} approved tool(s), "
        f"{len(agent.permissions)} permission(s) recorded"
    )


@register_check("agent_trace_logging")
def _check_agent_trace_logging(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.23(a) and (d): monitor reasoning, actions and tools; enhanced logging."""
    if use_case.agent is None:
        return Outcome.NOT_APPLICABLE, "not an agentic use case"
    if not use_case.agent.trace_logging:
        return Outcome.FAIL, (
            "reasoning, actions and tool use are not logged; §5.23(a) expects these to be "
            "monitored where relevant"
        )
    return Outcome.PASS, "reasoning, actions and tool use are logged"


@register_check("third_party_transparency")
def _check_third_party_transparency(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.11(a): independent assessment, not vendor self-attestation."""
    without = [
        f"{c.provider}/{c.component}" for c in use_case.third_party if not c.independent_assessment
    ]
    if without:
        return Outcome.FAIL, (
            f"no independent certification or external assessment recorded for: "
            f"{', '.join(without)}; Response to Feedback §9.9 rejects self-attestations"
        )
    return Outcome.PASS, "independent assessment recorded for every third-party component"


@register_check("third_party_change_notification")
def _check_third_party_changes(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.11(d) with §5.25(a): visibility of vendor-driven changes."""
    without = [
        f"{c.provider}/{c.component}" for c in use_case.third_party if not c.change_notification
    ]
    if without:
        return Outcome.FAIL, (
            f"no contractual change notification recorded for: {', '.join(without)}; "
            f"§5.25(a) then expects compensating controls such as enhanced monitoring"
        )
    return Outcome.PASS, "change notification recorded for every third-party component"


@register_check("embedded_ai_identified")
def _check_embedded_ai(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §4.2 with fn21: identify embedded AI in material third-party services."""
    embedded = [c for c in use_case.third_party if c.embedded]
    if not embedded:
        return Outcome.NOT_APPLICABLE, "no embedded third-party AI recorded"
    unassessed = [f"{c.provider}/{c.component}" for c in embedded if c.material_provider and not c.independent_assessment]
    if unassessed:
        return Outcome.FAIL, (
            f"embedded AI from material providers with no independent assessment: "
            f"{', '.join(unassessed)}"
        )
    return Outcome.PASS, f"{len(embedded)} embedded AI component(s) identified in the inventory"


@register_check("dynamic_update_controls")
def _check_dynamic_updates(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.25(c): enhanced controls for AI designed to update automatically."""
    if not use_case.auto_updates:
        return Outcome.NOT_APPLICABLE, "AI is not designed to update automatically"
    has_monitoring = bool(use_case.agent and use_case.agent.trace_logging) or bool(
        use_case.guardrails
    )
    if not has_monitoring:
        return Outcome.FAIL, (
            "automatic updates are enabled but no stricter monitoring or guardrail is recorded"
        )
    return Outcome.PASS, "automatic updates are paired with recorded monitoring or guardrails"


@register_check("materiality_assessed")
def _check_materiality_assessed(
    use_case: UseCase, assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §4.11 and §4.13: inherent and residual ratings, documented and approved."""
    if use_case.risk_materiality_rating is None:
        return Outcome.FAIL, (
            "no risk materiality rating recorded in the inventory (§4.7); run `airm assess`"
        )
    if use_case.risk_materiality_rating != assessment.inherent_tier.value:
        return Outcome.FAIL, (
            f"recorded rating {use_case.risk_materiality_rating!r} does not match the rubric's "
            f"inherent tier {assessment.inherent_tier.value!r}"
        )
    return Outcome.PASS, (
        f"inherent {assessment.inherent_tier.value}, residual {assessment.residual_tier.value}"
    )


@register_check("risk_appetite_confirmed")
def _check_risk_appetite(
    use_case: UseCase, assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §4.11: residual materiality must meet risk appetite before deployment."""
    if assessment.within_risk_appetite is None:
        return Outcome.FAIL, (
            "residual materiality has not been confirmed against the FI's risk appetite; the "
            "toolkit cannot infer an appetite statement"
        )
    if not assessment.within_risk_appetite:
        return Outcome.FAIL, (
            f"residual tier {assessment.residual_tier.value} is outside the FI's stated risk "
            f"appetite; §5.11 then expects the third-party service to be limited, suspended or "
            f"replaced where third-party AI is involved"
        )
    return Outcome.PASS, f"residual {assessment.residual_tier.value} confirmed within appetite"


@register_check("documentation_linked")
def _check_documentation(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.17: documentation enabling reproducibility and auditability."""
    if not use_case.documentation:
        return Outcome.FAIL, "no documentation linked in the inventory (§4.7, §5.17)"
    return Outcome.PASS, f"{len(use_case.documentation)} documentation link(s) recorded"


@register_check("roles_assigned")
def _check_roles(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §4.7 and §5.1: key roles and responsibilities are assigned."""
    required = ("owner", "developer")
    missing = [r for r in required if not use_case.role_party(r)]
    if missing:
        return Outcome.FAIL, f"no party recorded for role(s): {', '.join(missing)}"
    return Outcome.PASS, f"{len(use_case.roles)} role(s) assigned"


@register_check("monitoring_accountable_person")
def _check_monitoring_owner(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.23(c): an accountable person for monitoring and incidents."""
    if not use_case.role_party("monitor") and not use_case.role_party("accountable_person"):
        return Outcome.FAIL, (
            "no accountable person recorded for ongoing monitoring and incident management"
        )
    return Outcome.PASS, "accountable person recorded for monitoring"


@register_check("retirement_controls")
def _check_retirement(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.26: retirement controls considering dependencies and data retention."""
    if use_case.lifecycle_status is not LifecycleStatus.RETIRED:
        return Outcome.NOT_APPLICABLE, (
            f"use case is {use_case.lifecycle_status.value}, not retired"
        )
    if not use_case.notes:
        return Outcome.FAIL, (
            "retired use case with no decommissioning record (dependencies, data retention, "
            "secure removal, stakeholder notification)"
        )
    return Outcome.PASS, "decommissioning record present"


@register_check("pilot_guardrails")
def _check_pilot_guardrails(
    use_case: UseCase, _assessment: Assessment, _control: Control
) -> tuple[Outcome, str]:
    """MAS-AIRM §5.2 fn28 and §5.15 fn45: controls and guardrails governing partial deployments."""
    if use_case.lifecycle_status is not LifecycleStatus.PILOT:
        return Outcome.NOT_APPLICABLE, "use case is not a pilot or partial deployment"
    rails = use_case.all_guardrails
    has_limit = bool(use_case.agent and use_case.agent.max_steps) or any(
        g.kind in ("rate_limit", "human_checkpoint", "tool_allowlist") for g in rails
    )
    if not rails or not has_limit:
        return Outcome.FAIL, (
            "pilot with no recorded guardrail limiting scope, users, rate or steps "
            "(§5.2 fn28 expects time and user limits and close monitoring)"
        )
    return Outcome.PASS, f"pilot guardrails recorded: {', '.join(g.name for g in rails)}"


def available_checks() -> tuple[str, ...]:
    """Return the names of registered check functions."""
    return tuple(sorted(_CHECKS))


def evidence_items(catalogue: ControlCatalogue | None = None) -> tuple[str, ...]:
    """Return every distinct evidence item the catalogue asks for.

    Serves MAS-AIRM §5.18-§5.21: this is the list a reviewer or independent validator can request
    up front, and the input to the RQ5 effort estimate.
    """
    active = catalogue or load_controls()
    return tuple(sorted({item for control in active.controls for item in control.evidence}))


def filter_by_use_case(
    use_case: UseCase,
    *,
    assessment: Assessment | None = None,
    catalogue: ControlCatalogue | None = None,
) -> tuple[Control, ...]:
    """Return the controls applicable to one use case (MAS-AIRM §5.2).

    Used by the control-applicability statement in the audit pack, which is the SoA-style document
    a reviewer reads first.
    """
    active_assessment = assessment or assess(use_case)
    active_catalogue = catalogue or load_controls()
    return tuple(
        c
        for c in active_catalogue.controls
        if c.applies_to(use_case, active_assessment)[0]
    )


def iter_controls(
    catalogue: ControlCatalogue | None = None,
) -> Iterable[Control]:
    """Iterate over the controls of a catalogue, defaulting to the packaged one."""
    return iter((catalogue or load_controls()).controls)
