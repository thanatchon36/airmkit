"""AI inventory models and register.

Serves MAS-AIRM §4.5-§4.9: an accurate inventory of AI use cases, systems or models, capturing the
attributes of §4.7 at appropriate granularity, with linkages to other registers (§4.6 fn23) and a
design that is reviewed for newer AI technologies including the agent attributes of §4.8 fn25.

The models are deliberately permissive about *content* and strict about *shape*: MAS does not
prescribe a minimum attribute set (Response to Feedback §6.15-§6.16), so missing attributes are
reported by :meth:`UseCase.completeness` as gaps rather than rejected. See
``docs/INTERPRETATIONS.md`` I-5 and I-6.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Iterator
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from airm.catalog import cite, load_catalogue

__all__ = [
    "AgentExtension",
    "AutonomyLevel",
    "Completeness",
    "Dependency",
    "Guardrail",
    "LifecycleStatus",
    "RegisterDiff",
    "Register",
    "ReviewStatus",
    "Role",
    "ThirdPartyComponent",
    "UseCase",
]

_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$"


class LifecycleStatus(StrEnum):
    """Lifecycle status of an AI use case.

    Serves MAS-AIRM §4.7 ("lifecycle status") and §5.1 fn27, which defines the life cycle as
    running from inception to retirement or decommissioning. ``pilot`` is included because the
    Response to Feedback §2.9 confirms pilots and proof-of-concept deployments are in scope, and
    §5.2 fn28 governs partial deployments.
    """

    PROPOSED = "proposed"
    IN_DEVELOPMENT = "in_development"
    PILOT = "pilot"
    DEPLOYED = "deployed"
    SUSPENDED = "suspended"
    RETIRED = "retired"

    @property
    def is_live(self) -> bool:
        """Whether the use case is exposed to users, and so needs Section 5 runtime controls."""
        return self in (LifecycleStatus.PILOT, LifecycleStatus.DEPLOYED)


class ReviewStatus(StrEnum):
    """Model review status.

    Serves MAS-AIRM §4.7 ("model review status"), §5.18-§5.21 (pre-deployment reviews) and §5.24
    (re-validation). ``independent_validation`` is the formal independent validation that §5.19
    expects for high-materiality use cases; ``peer_review`` is the §5.20 alternative.
    """

    NOT_REVIEWED = "not_reviewed"
    IN_REVIEW = "in_review"
    PEER_REVIEW = "peer_review"
    INDEPENDENT_VALIDATION = "independent_validation"
    REVALIDATION_DUE = "revalidation_due"

    @property
    def is_independent(self) -> bool:
        """Whether the review on record is a formal independent validation (MAS-AIRM §5.19)."""
        return self is ReviewStatus.INDEPENDENT_VALIDATION


class AutonomyLevel(StrEnum):
    """How much the use case relies on the AI to act without a human.

    Not a MAS taxonomy. It operationalises the Reliance dimension of MAS-AIRM §4.12(c) ("the
    extent of autonomy granted to the AI system or model and the degree of human involvement") and
    the agent risks of §1.11. Response to Feedback §7.18 contrasts automated trade execution
    (higher) with staff reviewing every recommendation (lower), which is the gradient below.
    """

    ASSISTIVE = "assistive"
    HUMAN_IN_THE_LOOP = "human_in_the_loop"
    HUMAN_OVER_THE_LOOP = "human_over_the_loop"
    AUTONOMOUS_AGENT = "autonomous_agent"
    MULTI_AGENT = "multi_agent"

    @property
    def rank(self) -> int:
        """Ordinal rank, 0 (assistive) to 4 (multi-agent), for rubric scoring."""
        return _AUTONOMY_RANK[self]

    @property
    def is_agentic(self) -> bool:
        """Whether this level is agentic, triggering MAS-AIRM §1.11, §4.8 fn25 and §5.23(a)."""
        return self in (AutonomyLevel.AUTONOMOUS_AGENT, AutonomyLevel.MULTI_AGENT)


_AUTONOMY_RANK: dict[AutonomyLevel, int] = {
    AutonomyLevel.ASSISTIVE: 0,
    AutonomyLevel.HUMAN_IN_THE_LOOP: 1,
    AutonomyLevel.HUMAN_OVER_THE_LOOP: 2,
    AutonomyLevel.AUTONOMOUS_AGENT: 3,
    AutonomyLevel.MULTI_AGENT: 4,
}


class _Model(BaseModel):
    """Base model: forbid unknown fields so that typos in a register are errors, not silence."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False, validate_assignment=True)


class Role(_Model):
    """A named person or function accountable for part of the use case.

    Serves MAS-AIRM §4.7 ("key roles and responsibilities (e.g., owners, developers)"), §5.1
    (assign roles across units) and §5.23(c) (an accountable person for monitoring).
    """

    role: str = Field(description="Role name, e.g. 'owner', 'developer', 'validator', 'monitor'.")
    party: str = Field(description="Person, team or function holding the role.")
    function: str | None = Field(
        default=None,
        description="Control function or business unit, used to test independence (MAS-AIRM §5.19).",
    )


class Dependency(_Model):
    """A dependency of the use case on another system, model or dataset.

    Serves MAS-AIRM §4.7 ("dependencies") and §4.10 fn26, which requires dependencies between AI
    systems or models to be considered where they affect the use case's risk profile. The
    ``identifier`` field carries the shared key that §4.6 fn23 expects for linking the AI inventory
    to data and third-party registers.
    """

    kind: str = Field(description="One of 'model', 'system', 'dataset', 'service', 'use_case'.")
    name: str
    identifier: str | None = Field(
        default=None,
        description="Shared identifier linking to another register (MAS-AIRM §4.6 fn23).",
    )
    affects_risk_profile: bool = Field(
        default=False,
        description="Whether this dependency changes the use case's risk profile (§4.10 fn26).",
    )


class ThirdPartyComponent(_Model):
    """A third-party AI component the use case relies on.

    Serves MAS-AIRM §1.10 fn10 (definition of third-party AI), §4.2 fn21 (embedded AI in
    third-party services) and §5.10-§5.11 (third-party AI management). ``embedded`` marks AI inside
    a service not marketed as AI, which §4.2 requires to be identified at least for material
    providers.
    """

    provider: str
    component: str = Field(description="Model, service or tool name.")
    version: str | None = None
    embedded: bool = Field(
        default=False,
        description="AI incorporated within a service not sold as AI (MAS-AIRM §4.2 fn21).",
    )
    material_provider: bool = Field(
        default=False,
        description=(
            "Whether the FI's third-party register marks this a material provider. Not inferred; "
            "see docs/INTERPRETATIONS.md I-11 (MAS-AIRM §4.2)."
        ),
    )
    fine_tuned_by_fi: bool = Field(
        default=False,
        description="FI modified or fine-tuned the component, engaging §5.10 fn38.",
    )
    independent_assessment: bool = Field(
        default=False,
        description=(
            "An independent certification or external assessment exists (MAS-AIRM §5.11(a)); "
            "vendor self-attestations do not count (Response to Feedback §9.9)."
        ),
    )
    change_notification: bool = Field(
        default=False,
        description="Contractual visibility of post-deployment changes (MAS-AIRM §5.11(d)).",
    )


class Guardrail(_Model):
    """A guardrail imposed on the use case.

    Serves MAS-AIRM §4.8 fn25 ("the guardrails imposed to manage risk") and §5.15, which expects
    the *effectiveness* of guardrails to be tested for Generative AI and agents. ``tested`` and
    ``evidence_ref`` are what makes that expectation checkable.
    """

    name: str
    kind: str = Field(
        description="e.g. 'input_filter', 'output_filter', 'system_prompt', 'tool_allowlist', "
        "'rate_limit', 'human_checkpoint', 'kill_switch', 'llm_judge'.",
    )
    description: str | None = None
    tested: bool = Field(
        default=False, description="Effectiveness has been tested (MAS-AIRM §5.15)."
    )
    evidence_ref: str | None = Field(
        default=None, description="Evidence id or path for the effectiveness test."
    )


class AgentExtension(_Model):
    """Agent-specific inventory attributes.

    Implements MAS-AIRM §4.8 footnote 25 directly: "for AI agents, relevant attributes may include
    agent-specific identifiers, information on the tools and systems the agent can access, its
    components, and the guardrails imposed to manage risk". ``human_checkpoints`` serves §5.9(c)
    (design for oversight, with escalation when predefined conditions are met) and
    ``approved_tools`` makes the §5.23(a) tool-usage monitoring checkable against approved scope.
    """

    agent_identifier: str = Field(description="Agent-specific identifier (MAS-AIRM §4.8 fn25).")
    approved_tools: list[str] = Field(
        default_factory=list,
        description="Tools and systems the agent may access (MAS-AIRM §4.8 fn25).",
    )
    systems_accessible: list[str] = Field(
        default_factory=list, description="Internal or external systems reachable by the agent."
    )
    permissions: list[str] = Field(
        default_factory=list,
        description="Permissions granted, e.g. 'read:crm', 'write:ticket'. Supports §5.16(b).",
    )
    components: list[str] = Field(
        default_factory=list,
        description="Sub-agents, planners, retrievers and other components (MAS-AIRM §4.8 fn25).",
    )
    guardrails: list[Guardrail] = Field(default_factory=list)
    human_checkpoints: list[str] = Field(
        default_factory=list,
        description="Points at which a human must approve or can intervene (MAS-AIRM §5.9(c)).",
    )
    max_steps: int | None = Field(
        default=None, description="Cap on autonomous steps per task, a §5.2 mitigant."
    )
    can_initiate_external_actions: bool = Field(
        default=False,
        description="Whether the agent can act on systems of record or third parties (§1.11).",
    )
    trace_logging: bool = Field(
        default=False,
        description="Reasoning, actions and tools are logged (MAS-AIRM §5.23(a) and (d)).",
    )

    @property
    def untested_guardrails(self) -> tuple[str, ...]:
        """Names of guardrails whose effectiveness has not been tested (MAS-AIRM §5.15)."""
        return tuple(g.name for g in self.guardrails if not g.tested)


class Completeness(_Model):
    """Result of scoring an inventory entry against the attributes MAS-AIRM names."""

    score: float = Field(ge=0.0, le=1.0, description="Share of expected attributes present.")
    present: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    agent_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Share of §4.8 fn25 agent attributes present."
    )
    agent_missing: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """Whether every expected attribute, including agent attributes where relevant, is present."""
        return not self.missing and not self.agent_missing


class UseCase(_Model):
    """An AI use case as recorded in the AI inventory.

    Implements the attribute list of MAS-AIRM §4.7 (purpose and description, approved scope of use,
    model type, data used, dependencies, lifecycle status, assigned risk materiality rating, model
    review status, key roles and responsibilities, links to essential documentation), plus the
    fields the rest of the toolkit needs to evaluate Section 5 controls: autonomy and human
    oversight (§4.12(c), §5.9), third-party components (§5.10-§5.11), guardrails (§5.15) and the
    agent extension of §4.8 fn25.

    The entry is the unit of risk materiality assessment, which MAS-AIRM §4.10 and Response to
    Feedback §7.5 anchor on the *use case* rather than the system or model.
    """

    id: Annotated[str, Field(pattern=_ID_PATTERN)] = Field(
        description="Stable slug, e.g. 'credit-decision-model'."
    )
    name: str
    purpose: str = Field(description="Purpose and description (MAS-AIRM §4.7).")
    business_function: str | None = Field(
        default=None, description="Business line or function, supporting §3.5(d) role assignment."
    )
    approved_scope: str | None = Field(
        default=None,
        description="Approved scope of use including jurisdiction (MAS-AIRM §4.7).",
    )
    jurisdictions: list[str] = Field(default_factory=list)
    model_type: str | None = Field(
        default=None,
        description="e.g. 'gradient_boosting', 'llm_rag', 'llm_agent' (MAS-AIRM §4.7, §1.3 fn6).",
    )
    data_used: list[str] = Field(
        default_factory=list, description="Datasets or data categories used (MAS-AIRM §4.7)."
    )
    data_classification: str | None = Field(
        default=None,
        description="Highest data classification processed (MAS-AIRM §5.4(d), §4.12(a)).",
    )
    processes_personal_data: bool = Field(
        default=False, description="Engages §5.4(f) data privacy and raises Impact (§4.12(a))."
    )
    dependencies: list[Dependency] = Field(default_factory=list)
    lifecycle_status: LifecycleStatus = LifecycleStatus.PROPOSED
    risk_materiality_rating: str | None = Field(
        default=None,
        description="Assigned rating (MAS-AIRM §4.7); set by airm.materiality, not by hand.",
    )
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED
    roles: list[Role] = Field(default_factory=list)
    documentation: list[str] = Field(
        default_factory=list, description="Links to essential documentation (MAS-AIRM §4.7)."
    )
    third_party: list[ThirdPartyComponent] = Field(default_factory=list)
    guardrails: list[Guardrail] = Field(default_factory=list)
    agent: AgentExtension | None = Field(
        default=None, description="Agent attributes (MAS-AIRM §4.8 fn25)."
    )
    autonomy: AutonomyLevel = AutonomyLevel.ASSISTIVE
    human_oversight: str | None = Field(
        default=None, description="How human oversight is implemented (MAS-AIRM §5.9, fn37)."
    )
    affects_individuals: bool = Field(
        default=False,
        description=(
            "Whether outputs affect customers or individuals. Drives fairness and transparency "
            "relevance (MAS-AIRM §5.6-§5.8); see docs/INTERPRETATIONS.md I-7."
        ),
    )
    fairness_relevant: bool | None = Field(
        default=None,
        description="Explicit override of fairness relevance (MAS-AIRM §5.8).",
    )
    contingency_plan: str | None = Field(
        default=None, description="Fallback options for high-risk use cases (MAS-AIRM §5.3)."
    )
    kill_switch: bool = Field(
        default=False, description="Kill switch or override exists (MAS-AIRM §5.3 fn29, §5.23(b))."
    )
    auto_updates: bool = Field(
        default=False,
        description="AI is designed to update automatically, engaging MAS-AIRM §5.25(c).",
    )
    tags: list[str] = Field(default_factory=list)
    owner_attestation_date: dt.date | None = None
    last_reviewed: dt.date | None = Field(
        default=None, description="Last inventory review (MAS-AIRM §4.5, §4.8)."
    )
    notes: str | None = None

    @field_validator("id")
    @classmethod
    def _lower_id(cls, value: str) -> str:
        """Ids are lowercase slugs so that paths and report anchors are stable."""
        return value.lower()

    @model_validator(mode="after")
    def _agent_consistency(self) -> Self:
        """Agentic autonomy requires the agent extension, and vice versa.

        MAS-AIRM §4.8 fn25 ties agent attributes to agent use cases; recording one without the
        other would leave the inventory unable to support the §5.23(a) monitoring expectation.
        """
        if self.autonomy.is_agentic and self.agent is None:
            raise ValueError(
                f"use case {self.id!r} has autonomy {self.autonomy.value!r} but no agent "
                f"extension; {cite('4.8', footnote=25)} expects agent attributes"
            )
        if self.agent is not None and not self.autonomy.is_agentic:
            raise ValueError(
                f"use case {self.id!r} has an agent extension but autonomy "
                f"{self.autonomy.value!r}; set autonomy to autonomous_agent or multi_agent"
            )
        return self

    # -- derived views ---------------------------------------------------------

    @property
    def uses_third_party_ai(self) -> bool:
        """Whether the use case relies on third-party AI (MAS-AIRM §1.10 fn10, §5.10)."""
        return bool(self.third_party)

    @property
    def has_embedded_ai(self) -> bool:
        """Whether any third-party component is embedded AI (MAS-AIRM §4.2 fn21)."""
        return any(c.embedded for c in self.third_party)

    @property
    def is_generative(self) -> bool:
        """Whether the use case is Generative AI, engaging MAS-AIRM §1.10, §5.15 fn46.

        Inferred from the model type, the declared tags and agentic autonomy, since agents in the
        Guidelines' sense "leverage Generative AI" (consultation paper §2.3).
        """
        hints = ("llm", "genai", "generative", "gpt", "transformer", "diffusion")
        model_type = (self.model_type or "").lower()
        return (
            any(h in model_type for h in hints)
            or any(t in ("genai", "generative", "llm") for t in self.tags)
            or self.autonomy.is_agentic
        )

    @property
    def all_guardrails(self) -> tuple[Guardrail, ...]:
        """Guardrails on the use case and on its agent extension (MAS-AIRM §5.15, §4.8 fn25)."""
        agent_rails = tuple(self.agent.guardrails) if self.agent else ()
        return tuple(self.guardrails) + agent_rails

    @property
    def has_tested_guardrail(self) -> bool:
        """Whether at least one guardrail has a recorded effectiveness test (MAS-AIRM §5.15)."""
        return any(g.tested for g in self.all_guardrails)

    @property
    def untested_guardrails(self) -> tuple[str, ...]:
        """Names of guardrails with no recorded effectiveness test (MAS-AIRM §5.15, fn46)."""
        return tuple(g.name for g in self.all_guardrails if not g.tested)

    @property
    def has_explainability_evidence(self) -> bool:
        """Whether documentation that could evidence explainability analysis is linked.

        Serves MAS-AIRM §5.5-§5.6 and §5.17(e). A link is weak evidence, so controls that depend
        on this are classed ``semi`` and require attestation of adequacy.
        """
        hints = ("explain", "shap", "lime", "interpret", "model-card", "model_card", "feature")
        return any(any(h in doc.lower() for h in hints) for doc in self.documentation)

    @property
    def catalogue_tags(self) -> tuple[str, ...]:
        """Clause tags relevant to this use case, for selecting applicable catalogue paragraphs."""
        tags: set[str] = set()
        if self.is_generative:
            tags.add("genai")
        if self.autonomy.is_agentic:
            tags.add("agent")
        if self.uses_third_party_ai:
            tags.add("third-party")
        if self.processes_personal_data:
            tags.add("privacy")
        if self.is_fairness_relevant:
            tags.add("fairness")
        return tuple(sorted(tags))

    @property
    def is_fairness_relevant(self) -> bool:
        """Whether fairness controls apply (MAS-AIRM §5.7-§5.8).

        Default (strict) reading per ``docs/INTERPRETATIONS.md`` I-7: relevant whenever the use
        case affects individuals or is tagged as a customer-outcome domain that §5.7 singles out.
        An explicit ``fairness_relevant`` on the entry overrides this.
        """
        if self.fairness_relevant is not None:
            return self.fairness_relevant
        domains = {"credit", "insurance", "underwriting", "advisory", "hr", "claims"}
        return self.affects_individuals or bool(domains.intersection(self.tags))

    def role_party(self, role: str) -> str | None:
        """Return the party holding a role, or None (MAS-AIRM §4.7, §5.1)."""
        for entry in self.roles:
            if entry.role.lower() == role.lower():
                return entry.party
        return None

    def has_independent_validator(self) -> bool:
        """Whether a validator independent of development and deployment is on record.

        Serves MAS-AIRM §5.19 and §5.20 fn48, which requires independence from both initial and
        ongoing deployment. Default strict reading: the validator must differ from the owner,
        developer and deployer parties (``docs/INTERPRETATIONS.md`` I-8).
        """
        validator = self.role_party("validator")
        if not validator:
            return False
        conflicted = {
            self.role_party(r) for r in ("owner", "developer", "deployer", "operator")
        } - {None}
        return validator not in conflicted

    def completeness(self, *, require_agent_attributes: bool = True) -> Completeness:
        """Score the entry against the attributes MAS-AIRM §4.7 and §4.8 fn25 name.

        Serves MAS-AIRM §4.7 and §4.9: the designated control function must be able to see whether
        the inventory is accurate and complete. Missing attributes are gaps, not validation
        failures, because §4.7 fn24 permits documented omissions.

        Args:
            require_agent_attributes: Whether to also score the §4.8 fn25 agent attributes for
                agentic use cases. See ``docs/INTERPRETATIONS.md`` I-6.

        Returns:
            A :class:`Completeness` with the score, the present and missing attribute names and
            the citations the score derives from.

        Examples:
            >>> uc = UseCase(id="demo", name="Demo", purpose="p")
            >>> uc.completeness().score < 1.0
            True
        """
        checks: dict[str, bool] = {
            "purpose_and_description": bool(self.purpose),
            "approved_scope_of_use": bool(self.approved_scope or self.jurisdictions),
            "model_type": bool(self.model_type),
            "data_used": bool(self.data_used),
            "dependencies": bool(self.dependencies) or bool(self.third_party),
            "lifecycle_status": True,
            "risk_materiality_rating": bool(self.risk_materiality_rating),
            "model_review_status": self.review_status is not ReviewStatus.NOT_REVIEWED,
            "key_roles_and_responsibilities": bool(self.roles),
            "links_to_documentation": bool(self.documentation),
        }
        present = sorted(k for k, ok in checks.items() if ok)
        missing = sorted(k for k, ok in checks.items() if not ok)
        citations = [cite("4.7")]

        agent_score: float | None = None
        agent_missing: list[str] = []
        if self.agent is not None and require_agent_attributes:
            agent_checks = {
                "agent_identifier": bool(self.agent.agent_identifier),
                "tools_and_systems_accessible": bool(
                    self.agent.approved_tools or self.agent.systems_accessible
                ),
                "components": bool(self.agent.components),
                "guardrails": bool(self.agent.guardrails),
            }
            agent_missing = sorted(k for k, ok in agent_checks.items() if not ok)
            agent_score = sum(agent_checks.values()) / len(agent_checks)
            citations.append(cite("4.8", footnote=25))

        return Completeness(
            score=len(present) / len(checks),
            present=present,
            missing=missing,
            agent_score=agent_score,
            agent_missing=agent_missing,
            citations=citations,
        )


class RegisterDiff(_Model):
    """Difference between two versions of a register.

    Serves MAS-AIRM §4.5 (reflecting new, updated or decommissioned AI) and §5.25(a), which
    expects a framework to evaluate the significance of changes. The toolkit reports changed fields
    and flags those its default change-significance classes treat as significant
    (``docs/INTERPRETATIONS.md`` I-10).
    """

    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    changed: dict[str, list[str]] = Field(
        default_factory=dict, description="Use case id -> changed field names."
    )
    significant: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Use case id -> changed fields the default framework deems significant.",
    )
    citations: list[str] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Whether the two registers are identical."""
        return not (self.added or self.removed or self.changed)


SIGNIFICANT_CHANGE_FIELDS: frozenset[str] = frozenset(
    {
        "purpose",
        "approved_scope",
        "jurisdictions",
        "model_type",
        "data_used",
        "autonomy",
        "agent",
        "third_party",
        "guardrails",
        "lifecycle_status",
        "risk_materiality_rating",
        "auto_updates",
        "processes_personal_data",
    }
)
"""Fields whose change the default framework treats as significant.

Implements the default change-significance classes of ``docs/INTERPRETATIONS.md`` I-10, derived
from MAS-AIRM §5.25(a) and its footnote 49 (training data, model or system architecture, key
assumptions, scope of use, downstream impact), extended for LLM and agentic systems with model
provider/version, guardrails and the tools granted to an agent.
"""


class Register(_Model):
    """A collection of AI inventory entries, loadable from and savable to YAML or JSON.

    Serves MAS-AIRM §4.5-§4.6: an FI may enhance an existing inventory or keep a dedicated one; in
    either case the register carries linkage identifiers to other registers (§4.6 fn23) and a
    review date (§4.5, §4.8).
    """

    institution: str = Field(description="Institution name. Use a fictional name in examples.")
    register_id: str = "ai-inventory"
    version: str = "1"
    as_of: dt.date = Field(default_factory=dt.date.today)
    linked_registers: dict[str, str] = Field(
        default_factory=dict,
        description="Register name -> identifier scheme, per MAS-AIRM §4.6 fn23.",
    )
    control_functions: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Process -> designated control function for 'identification', 'inventory' and "
            "'materiality' (MAS-AIRM §4.3, §4.9, §4.13)."
        ),
    )
    use_cases: list[UseCase] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def _unique_ids(self) -> Self:
        """Use case ids must be unique: the register is a lookup table for every other module."""
        seen: set[str] = set()
        for uc in self.use_cases:
            if uc.id in seen:
                raise ValueError(f"duplicate use case id: {uc.id!r}")
            seen.add(uc.id)
        return self

    def __iter__(self) -> Iterator[UseCase]:  # type: ignore[override]
        """Iterate over use cases."""
        return iter(self.use_cases)

    def __len__(self) -> int:
        """Number of use cases in the register."""
        return len(self.use_cases)

    def __contains__(self, use_case_id: object) -> bool:
        """Whether a use case id is in the register."""
        return isinstance(use_case_id, str) and any(uc.id == use_case_id for uc in self.use_cases)

    def get(self, use_case_id: str) -> UseCase:
        """Return a use case by id.

        Raises:
            KeyError: If the register has no such use case.
        """
        for uc in self.use_cases:
            if uc.id == use_case_id:
                return uc
        raise KeyError(f"no such use case in register: {use_case_id!r}")

    def live(self) -> tuple[UseCase, ...]:
        """Return deployed or piloted use cases, which need Section 5 runtime controls."""
        return tuple(uc for uc in self.use_cases if uc.lifecycle_status.is_live)

    def agentic(self) -> tuple[UseCase, ...]:
        """Return agentic use cases (MAS-AIRM §1.11, §4.8 fn25)."""
        return tuple(uc for uc in self.use_cases if uc.autonomy.is_agentic)

    def third_party_providers(self) -> dict[str, list[str]]:
        """Return provider -> use case ids, for concentration risk (MAS-AIRM §5.11(c), §3.4 fn18).

        MAS-AIRM §3.4 fn18 gives "number of material AI use cases with dependencies on a single
        provider" as an example quantitative risk-appetite measure; this is its input.
        """
        out: dict[str, list[str]] = {}
        for uc in self.use_cases:
            for component in uc.third_party:
                out.setdefault(component.provider, []).append(uc.id)
        return {k: sorted(set(v)) for k, v in sorted(out.items())}

    def completeness(self) -> dict[str, Completeness]:
        """Score every entry against MAS-AIRM §4.7 and §4.8 fn25."""
        return {uc.id: uc.completeness() for uc in self.use_cases}

    def missing_control_functions(self) -> tuple[str, ...]:
        """Return the processes with no designated control function.

        Serves MAS-AIRM §4.3, §4.9 and §4.13, each of which expects a designated control function
        with independent oversight of identification, inventory and materiality assessment.
        """
        required = ("identification", "inventory", "materiality")
        return tuple(p for p in required if not self.control_functions.get(p))

    def diff(self, other: Register) -> RegisterDiff:
        """Compare this register (old) with another (new).

        Serves MAS-AIRM §4.5 (inventory reflects new, updated and decommissioned AI) and §5.25(a)
        (grade the significance of changes). Fields in :data:`SIGNIFICANT_CHANGE_FIELDS` are
        reported separately as significant.

        Args:
            other: The newer register.

        Returns:
            A :class:`RegisterDiff`.
        """
        old_ids = {uc.id for uc in self.use_cases}
        new_ids = {uc.id for uc in other.use_cases}
        changed: dict[str, list[str]] = {}
        significant: dict[str, list[str]] = {}
        for use_case_id in sorted(old_ids & new_ids):
            before = self.get(use_case_id).model_dump(mode="json")
            after = other.get(use_case_id).model_dump(mode="json")
            fields = sorted(k for k in before if before[k] != after.get(k))
            if fields:
                changed[use_case_id] = fields
                sig = [f for f in fields if f in SIGNIFICANT_CHANGE_FIELDS]
                if sig:
                    significant[use_case_id] = sig
        return RegisterDiff(
            added=sorted(new_ids - old_ids),
            removed=sorted(old_ids - new_ids),
            changed=changed,
            significant=significant,
            citations=[cite("4.5"), cite("5.25", item="a")],
        )

    # -- persistence -----------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> Register:
        """Load a register from a YAML or JSON file.

        The file is treated as data, never as code: it is parsed with ``yaml.safe_load`` and
        validated by the model, and unknown fields are rejected.

        Args:
            path: Path to a ``.yaml``, ``.yml`` or ``.json`` file.

        Returns:
            The validated register.
        """
        text = Path(path).read_text(encoding="utf-8")
        data: Any = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: expected a mapping at the top level of the register")
        return cls.model_validate(data)

    def save(self, path: str | Path) -> Path:
        """Write the register to YAML or JSON, inferred from the suffix.

        Args:
            path: Destination path.

        Returns:
            The path written.
        """
        target = Path(path)
        payload = self.model_dump(mode="json", exclude_none=True)
        if target.suffix == ".json":
            target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        else:
            target.write_text(
                yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )
        return target

    @classmethod
    def from_use_cases(cls, institution: str, use_cases: Iterable[UseCase]) -> Register:
        """Build a register from an iterable of use cases."""
        return cls(institution=institution, use_cases=list(use_cases))


def expected_attributes() -> tuple[str, ...]:
    """Return the inventory attributes MAS-AIRM §4.7 names, from the clause catalogue."""
    return load_catalogue().inventory_attributes()


def expected_agent_attributes() -> tuple[str, ...]:
    """Return the agent attributes MAS-AIRM §4.8 fn25 names, from the clause catalogue."""
    return load_catalogue().agent_attributes()
