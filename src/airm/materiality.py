"""Risk materiality assessment: Impact, Complexity and Reliance.

Serves MAS-AIRM §4.10-§4.13. The Guidelines require a consistent, use-case-anchored methodology
covering at minimum the three dimensions of §4.12, assessed both inherent (pre-control) and
residual (post-control) per §4.11, with a designated control function arbitrating ratings (§4.13).

**MAS does not prescribe how to score or combine the dimensions.** Response to Feedback §7.19 is
explicit: "MAS does not intend to prescribe a uniform or formulaic approach for combining
individual assessments of Impact, Complexity and Reliance into an overall risk materiality rating,
nor to define a universal threshold for 'high' risk materiality." Everything quantitative in this
module is therefore the toolkit's **proposal**, shipped as an editable YAML rubric so that an
institution can substitute its own. The defaults are documented in ``docs/DECISIONS.md`` D-5 and
``docs/INTERPRETATIONS.md`` I-4.

Every score carries its reasons, because §4.13 expects assessments to be "clearly documented" and
an arbitrating control function needs to see why a rating came out as it did.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from airm.catalog import cite
from airm.inventory import AutonomyLevel, Register, UseCase

__all__ = [
    "Assessment",
    "Dimension",
    "DimensionScore",
    "Level",
    "PortfolioAssessment",
    "Rubric",
    "Tier",
    "assess",
    "assess_register",
    "load_rubric",
]


class Level(StrEnum):
    """Level of a single risk dimension.

    Four levels, not a MAS taxonomy. Response to Feedback §7.18 gives only relative illustrations
    ("higher vs lower Impact, Complexity or Reliance") and declines absolute ratings.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Ordinal rank, 0 (low) to 3 (critical)."""
        return _LEVEL_RANK[self]

    @classmethod
    def from_rank(cls, rank: int) -> Level:
        """Return the level for an ordinal rank, clamped to the valid range."""
        return _RANK_LEVEL[max(0, min(3, rank))]


_LEVEL_RANK: dict[Level, int] = {Level.LOW: 0, Level.MEDIUM: 1, Level.HIGH: 2, Level.CRITICAL: 3}
_RANK_LEVEL: dict[int, Level] = {v: k for k, v in _LEVEL_RANK.items()}


class Tier(StrEnum):
    """Overall risk materiality tier of a use case.

    The tier is what Section 5 controls are calibrated against (MAS-AIRM §5.2). ``HIGH`` and
    ``CRITICAL`` both count as "high risk materiality" for the clauses that bind only at that
    level (§5.3 contingency plans, §5.19 formal independent validation, §5.23(b) kill switches,
    §5.24 independent re-validation). Per Response to Feedback §7.21 those triggers key on
    *inherent* materiality; see ``docs/INTERPRETATIONS.md`` I-3.
    """

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

    @property
    def rank(self) -> int:
        """Ordinal rank, 0 (Low) to 3 (Critical)."""
        return _TIER_RANK[self]

    @property
    def is_high_materiality(self) -> bool:
        """Whether the tier counts as "high risk materiality" under MAS-AIRM Section 5."""
        return self in (Tier.HIGH, Tier.CRITICAL)

    @classmethod
    def from_rank(cls, rank: int) -> Tier:
        """Return the tier for an ordinal rank, clamped to the valid range."""
        return _RANK_TIER[max(0, min(3, rank))]


_TIER_RANK: dict[Tier, int] = {Tier.LOW: 0, Tier.MEDIUM: 1, Tier.HIGH: 2, Tier.CRITICAL: 3}
_RANK_TIER: dict[int, Tier] = {v: k for k, v in _TIER_RANK.items()}


class Dimension(StrEnum):
    """The three risk dimensions MAS-AIRM §4.12 requires at minimum."""

    IMPACT = "impact"
    COMPLEXITY = "complexity"
    RELIANCE = "reliance"

    @property
    def citation(self) -> str:
        """Return the citation for this dimension's limb of MAS-AIRM §4.12."""
        return cite("4.12", item={"impact": "a", "complexity": "b", "reliance": "c"}[self.value])


class _Model(BaseModel):
    """Base model forbidding unknown fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class DimensionScore(_Model):
    """The assessed level of one dimension, with the reasons that produced it."""

    dimension: Dimension
    level: Level
    score: float = Field(description="Weighted signal score before banding.")
    reasons: list[str] = Field(
        default_factory=list, description="Human-readable reasons, each naming its signal."
    )
    citation: str = Field(description="The MAS-AIRM paragraph the dimension derives from.")

    @property
    def rank(self) -> int:
        """Ordinal rank of the assessed level."""
        return self.level.rank


class Assessment(_Model):
    """A complete risk materiality assessment of one use case.

    Serves MAS-AIRM §4.11 (inherent and residual) and §4.13 (documented, arbitrable). The
    ``approved_by`` and ``approved_on`` fields exist because §4.13 makes a designated control
    function the arbitrator or approver of the rating; the toolkit computes, it does not approve.
    """

    use_case_id: str
    rubric_id: str
    rubric_version: str
    assessed_on: dt.date = Field(default_factory=dt.date.today)
    dimensions: dict[Dimension, DimensionScore]
    inherent_tier: Tier
    residual_tier: Tier
    mitigation_notes: list[str] = Field(default_factory=list)
    within_risk_appetite: bool | None = Field(
        default=None,
        description=(
            "Whether residual materiality meets the FI's risk appetite (MAS-AIRM §4.11). The "
            "toolkit cannot know an FI's appetite; set it from the FI's own appetite statement."
        ),
    )
    approved_by: str | None = Field(
        default=None, description="Designated control function approving the rating (§4.13)."
    )
    approved_on: dt.date | None = None
    citations: list[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default=(
            "Tiering and thresholds are this toolkit's proposal, not a MAS requirement: MAS "
            "declines to prescribe a formula or a universal 'high' threshold (Response to "
            "Feedback §7.19)."
        )
    )

    @property
    def is_high_materiality(self) -> bool:
        """Whether Section 5's high-materiality clauses bind.

        Keyed on *inherent* materiality per Response to Feedback §7.21
        (``docs/INTERPRETATIONS.md`` I-3).
        """
        return self.inherent_tier.is_high_materiality

    def level(self, dimension: Dimension) -> Level:
        """Return the assessed level of one dimension."""
        return self.dimensions[dimension].level

    def explain(self) -> list[str]:
        """Return every reason across all dimensions, each prefixed by its dimension."""
        out: list[str] = []
        for dimension in (Dimension.IMPACT, Dimension.COMPLEXITY, Dimension.RELIANCE):
            score = self.dimensions[dimension]
            out.extend(f"{dimension.value}: {reason}" for reason in score.reasons)
        return out


class PortfolioAssessment(_Model):
    """Assessments for every use case in a register, plus portfolio-level views.

    The aggregate view supports MAS-AIRM §3.4(b) and §3.4 fn18, which give "number of material AI
    use cases with dependencies on a single provider" as an example quantitative risk-appetite
    measure, and §3.5(f) reporting to the board.
    """

    institution: str
    rubric_id: str
    assessed_on: dt.date = Field(default_factory=dt.date.today)
    assessments: dict[str, Assessment] = Field(default_factory=dict)

    @property
    def tier_counts(self) -> dict[str, int]:
        """Count of use cases per inherent tier."""
        counts = dict.fromkeys((t.value for t in Tier), 0)
        for assessment in self.assessments.values():
            counts[assessment.inherent_tier.value] += 1
        return counts

    @property
    def high_materiality_ids(self) -> tuple[str, ...]:
        """Ids of use cases whose inherent tier is High or Critical."""
        return tuple(
            sorted(uc for uc, a in self.assessments.items() if a.is_high_materiality)
        )

    def provider_concentration(self, register: Register) -> dict[str, int]:
        """Return provider -> number of high-materiality use cases depending on it.

        Serves MAS-AIRM §5.11(c) (concentration risk) and the §3.4 fn18 example measure.
        """
        high = set(self.high_materiality_ids)
        out: dict[str, int] = {}
        for provider, use_cases in register.third_party_providers().items():
            count = len(high.intersection(use_cases))
            if count:
                out[provider] = count
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


# --------------------------------------------------------------------------- rubric


class Rubric(_Model):
    """A configurable scoring rubric for the three MAS-AIRM §4.12 dimensions.

    A rubric is a set of *signals* per dimension. Each signal reads one field of the use case,
    matches it against configured values, and contributes a level with a reason. The dimension's
    level is the maximum level any of its signals raised (a conservative choice: one critical
    signal is enough), and the overall tier combines the three dimension levels by the configured
    method.

    Combination methods:

    ``max_with_impact_gate`` (default)
        Tier rank is the maximum of the three dimension ranks, but Complexity and Reliance may
        raise it at most ``gate_headroom`` levels above Impact. This implements Response to
        Feedback §7.9 (Complexity is not to be assessed in isolation or determine materiality on a
        standalone basis) and §7.5 (anchor on the consequences of failure), while keeping the
        strictest reading of §4.12's "minimally covering" all three.

    ``max``
        Plain maximum of the three ranks.

    ``impact_primary``
        Tier equals the Impact rank, raised one level if either other dimension is Critical. This
        is the lenient variant Response to Feedback §7.16 reports some respondents asking for.

    ``weighted``
        Weighted mean of the three ranks, banded by ``weighted_bands``. Used as the RQ2
        sensitivity check.
    """

    id: str = "default-v1"
    version: str = "1"
    title: str = "airmkit default MAS-AIRM risk materiality rubric"
    description: str = ""
    combination: str = "max_with_impact_gate"
    gate_headroom: int = Field(
        default=1,
        ge=0,
        le=3,
        description="How many levels Complexity/Reliance may lift the tier above Impact.",
    )
    weights: dict[Dimension, float] = Field(
        default_factory=lambda: {
            Dimension.IMPACT: 0.5,
            Dimension.COMPLEXITY: 0.2,
            Dimension.RELIANCE: 0.3,
        }
    )
    weighted_bands: list[float] = Field(
        default_factory=lambda: [0.5, 1.5, 2.5],
        description="Upper bounds separating Low/Medium/High/Critical for the weighted method.",
    )
    signals: dict[Dimension, list[dict[str, Any]]] = Field(default_factory=dict)
    residual_credits: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Control-based reductions applied to the inherent tier to obtain residual materiality "
            "(MAS-AIRM §4.11). MAS prescribes no residual methodology (Response §7.22)."
        ),
    )
    residual_floor: str = Field(
        default="one_level",
        description=(
            "How far controls may reduce the tier: 'one_level' (default, strict), 'two_levels', "
            "or 'none' for no reduction."
        ),
    )
    citations: list[str] = Field(
        default_factory=lambda: [cite("4.10"), cite("4.11"), cite("4.12"), cite("4.13")]
    )

    @model_validator(mode="after")
    def _known_combination(self) -> Self:
        """Reject unknown combination methods early rather than silently defaulting."""
        allowed = {"max_with_impact_gate", "max", "impact_primary", "weighted"}
        if self.combination not in allowed:
            raise ValueError(
                f"unknown combination method {self.combination!r}; expected one of {sorted(allowed)}"
            )
        if self.residual_floor not in {"one_level", "two_levels", "none"}:
            raise ValueError(f"unknown residual_floor {self.residual_floor!r}")
        return self

    # -- scoring ---------------------------------------------------------------

    def score_dimension(self, use_case: UseCase, dimension: Dimension) -> DimensionScore:
        """Score one dimension of one use case.

        Args:
            use_case: The inventory entry to score.
            dimension: Which of the MAS-AIRM §4.12 dimensions to score.

        Returns:
            A :class:`DimensionScore` whose level is the highest level any signal raised, and
            whose reasons record each signal that fired.
        """
        level = Level.LOW
        reasons: list[str] = []
        total = 0.0
        for signal in self.signals.get(dimension, []):
            fired, detail = _evaluate_signal(signal, use_case)
            if not fired:
                continue
            signal_level = Level(signal["level"])
            weight = float(signal.get("weight", 1.0))
            total += weight * (signal_level.rank + 1)
            reasons.append(f"{detail} -> {signal_level.value} [{signal['id']}]")
            if signal_level.rank > level.rank:
                level = signal_level
        if not reasons:
            reasons.append("no signal fired; defaulting to low")
        return DimensionScore(
            dimension=dimension,
            level=level,
            score=round(total, 3),
            reasons=reasons,
            citation=dimension.citation,
        )

    def combine(self, levels: dict[Dimension, Level]) -> tuple[Tier, str]:
        """Combine three dimension levels into an inherent tier.

        Args:
            levels: The assessed level of each dimension.

        Returns:
            The tier and a one-line explanation of how it was derived.
        """
        impact = levels[Dimension.IMPACT].rank
        complexity = levels[Dimension.COMPLEXITY].rank
        reliance = levels[Dimension.RELIANCE].rank

        if self.combination == "max":
            rank = max(impact, complexity, reliance)
            how = f"max(impact={impact}, complexity={complexity}, reliance={reliance})"
        elif self.combination == "impact_primary":
            rank = impact + (1 if max(complexity, reliance) == Level.CRITICAL.rank else 0)
            how = f"impact={impact} raised by critical secondary dimension" if rank > impact else f"impact={impact}"
        elif self.combination == "weighted":
            mean = (
                self.weights[Dimension.IMPACT] * impact
                + self.weights[Dimension.COMPLEXITY] * complexity
                + self.weights[Dimension.RELIANCE] * reliance
            ) / sum(self.weights.values())
            rank = sum(1 for bound in self.weighted_bands if mean > bound)
            how = f"weighted mean {mean:.2f} banded by {self.weighted_bands}"
        else:  # max_with_impact_gate
            raw = max(impact, complexity, reliance)
            rank = min(raw, impact + self.gate_headroom)
            how = (
                f"max(impact={impact}, complexity={complexity}, reliance={reliance})={raw}, "
                f"capped at impact+{self.gate_headroom}={impact + self.gate_headroom}"
            )
        return Tier.from_rank(rank), how

    def residual(self, use_case: UseCase, inherent: Tier) -> tuple[Tier, list[str]]:
        """Reduce the inherent tier by the credits the use case's controls earn.

        Serves MAS-AIRM §4.11, which requires residual materiality after controls, and Response to
        Feedback §7.22, which leaves the methodology to the FI. The default is deliberately
        conservative: controls may reduce the tier by at most one level, and only credits whose
        conditions are met count.

        Args:
            use_case: The inventory entry.
            inherent: The inherent tier.

        Returns:
            The residual tier and the notes explaining each credit applied.
        """
        if self.residual_floor == "none":
            return inherent, ["residual_floor=none: controls do not reduce the tier"]
        max_drop = 1 if self.residual_floor == "one_level" else 2
        credit = 0.0
        notes: list[str] = []
        for rule in self.residual_credits:
            fired, detail = _evaluate_signal(rule, use_case)
            if fired:
                credit += float(rule.get("credit", 0.5))
                notes.append(f"{detail} -> credit {rule.get('credit', 0.5)} [{rule['id']}]")
        drop = min(int(credit), max_drop)
        if not notes:
            notes.append("no mitigating control credits recorded")
        if drop:
            notes.append(f"inherent {inherent.value} reduced by {drop} level(s)")
        return Tier.from_rank(inherent.rank - drop), notes

    def assess(self, use_case: UseCase) -> Assessment:
        """Produce a full assessment of one use case.

        Serves MAS-AIRM §4.10-§4.13.

        Args:
            use_case: The inventory entry to assess.

        Returns:
            An :class:`Assessment` carrying dimension levels with reasons, the inherent tier and
            the residual tier.
        """
        scores = {d: self.score_dimension(use_case, d) for d in Dimension}
        levels = {d: s.level for d, s in scores.items()}
        inherent, how = self.combine(levels)
        residual, notes = self.residual(use_case, inherent)
        return Assessment(
            use_case_id=use_case.id,
            rubric_id=self.id,
            rubric_version=self.version,
            dimensions=scores,
            inherent_tier=inherent,
            residual_tier=residual,
            mitigation_notes=[f"combination: {how}", *notes],
            citations=list(self.citations),
        )

    # -- persistence -----------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path | None = None) -> Rubric:
        """Load a rubric from YAML, or the packaged default if no path is given.

        Args:
            path: Path to a rubric YAML file, or None for the packaged default.

        Returns:
            The validated rubric.
        """
        if path is None:
            text = (
                resources.files("airm.catalog")
                .joinpath("materiality_rubric_default.yaml")
                .read_text(encoding="utf-8")
            )
        else:
            text = Path(path).read_text(encoding="utf-8")
        data: Any = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("rubric file must contain a mapping at the top level")
        return cls.model_validate(data)

    def save(self, path: str | Path) -> Path:
        """Write the rubric to a YAML file so an institution can edit and version it."""
        target = Path(path)
        target.write_text(
            yaml.safe_dump(
                self.model_dump(mode="json", exclude_none=True), sort_keys=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
        return target


def _get_field(use_case: UseCase, field: str) -> Any:
    """Read a field or dotted sub-field from a use case, returning None if absent.

    Supports ``agent.can_initiate_external_actions`` style paths and the derived properties the
    inventory module exposes (``is_generative``, ``uses_third_party_ai``, ...).
    """
    current: Any = use_case
    for part in field.split("."):
        if current is None:
            return None
        current = getattr(current, part, None)
    return current


def _evaluate_signal(signal: dict[str, Any], use_case: UseCase) -> tuple[bool, str]:
    """Evaluate one rubric signal against a use case.

    A signal is a mapping with ``id``, ``field``, a comparison, and a ``reason`` template. The
    comparisons are deliberately few and declarative so that a rubric stays data, never code:

    ``equals``, ``in``, ``not_in``, ``is_true``, ``is_false``, ``gte``, ``lte``,
    ``contains_any``, ``nonempty``, ``empty``, ``autonomy_at_least``.

    Returns:
        A ``(fired, detail)`` pair where ``detail`` describes what was observed.
    """
    field = signal.get("field", "")
    value = _get_field(use_case, field) if field else None
    reason = signal.get("reason", field or signal.get("id", "signal"))

    def observed(val: Any) -> str:
        if isinstance(val, StrEnum):
            return str(val.value)
        if isinstance(val, (list, tuple)):
            if not val:
                return "(empty)"
            parts = [
                str(getattr(v, "name", None) or getattr(v, "id", None) or v) for v in val
            ]
            return ", ".join(parts)
        return str(val)

    if "equals" in signal:
        fired = observed(value) == str(signal["equals"])
    elif "in" in signal:
        fired = observed(value) in {str(v) for v in signal["in"]}
    elif "not_in" in signal:
        fired = observed(value) not in {str(v) for v in signal["not_in"]}
    elif "is_true" in signal:
        fired = bool(value) is bool(signal["is_true"])
    elif "is_false" in signal:
        fired = bool(value) is (not bool(signal["is_false"]))
    elif "gte" in signal:
        fired = value is not None and float(value) >= float(signal["gte"])
    elif "lte" in signal:
        fired = value is not None and float(value) <= float(signal["lte"])
    elif "contains_any" in signal:
        haystack = {str(v).lower() for v in (value or [])}
        fired = bool(haystack.intersection({str(v).lower() for v in signal["contains_any"]}))
    elif "nonempty" in signal:
        fired = bool(value) is bool(signal["nonempty"])
    elif "empty" in signal:
        fired = (not value) is bool(signal["empty"])
    elif "autonomy_at_least" in signal:
        threshold = AutonomyLevel(signal["autonomy_at_least"]).rank
        fired = isinstance(value, AutonomyLevel) and value.rank >= threshold
    else:
        raise ValueError(f"rubric signal {signal.get('id')!r} has no comparison clause")

    if not fired:
        return False, ""
    return True, f"{reason} (observed: {observed(value)})"


def assess(use_case: UseCase, rubric: Rubric | None = None) -> Assessment:
    """Assess the risk materiality of one use case.

    Serves MAS-AIRM §4.10-§4.13. Deterministic: the same use case and rubric always produce the
    same assessment, so a rating can be reproduced by a reviewer or an auditor (§5.17).

    Args:
        use_case: The inventory entry to assess.
        rubric: The rubric to use; the packaged default if omitted.

    Returns:
        The assessment.

    Examples:
        >>> from airm.inventory import UseCase
        >>> uc = UseCase(id="chatbot", name="Chatbot", purpose="answer queries")
        >>> assess(uc).inherent_tier.value in {"Low", "Medium", "High", "Critical"}
        True
    """
    return (rubric or load_rubric()).assess(use_case)


def assess_register(register: Register, rubric: Rubric | None = None) -> PortfolioAssessment:
    """Assess every use case in a register.

    Serves MAS-AIRM §4.10 ("applied consistently to perform risk materiality assessments for each
    AI use case in the FI") and supports the portfolio views §3.4(b) and §3.5(f) rely on.

    Args:
        register: The AI inventory register.
        rubric: The rubric to use; the packaged default if omitted.

    Returns:
        A :class:`PortfolioAssessment` keyed by use case id.
    """
    active = rubric or load_rubric()
    return PortfolioAssessment(
        institution=register.institution,
        rubric_id=active.id,
        assessments={uc.id: active.assess(uc) for uc in register.use_cases},
    )


def load_rubric(path: str | Path | None = None) -> Rubric:
    """Load a rubric, or the packaged default.

    The default rubric's signals each cite the MAS-AIRM paragraph they derive from, per the
    MISSION requirement that rubric defaults be traceable.
    """
    return Rubric.load(path)
