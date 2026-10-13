"""Bidirectional crosswalk between MAS-AIRM and other AI governance frameworks.

Maps MAS-AIRM paragraphs to ISO/IEC 42001:2023, the NIST AI Risk Management Framework 1.0 with
its Generative AI Profile, the EU AI Act, and MAS' own FEAT principles and Information Paper on AI
Model Risk Management (2024).

**Mapping is interpretive and asymmetric.** ISO 42001 is a management-system standard, the EU AI
Act is product law with conformity assessment, and NIST AI RMF is voluntary function and
subcategory guidance. A paragraph can therefore be "covered" in substance and uncovered in legal
effect. Every row carries a ``justification`` and a ``confidence`` so a reader can disagree row by
row rather than with the table as a whole. This is the data behind RQ4.

The crosswalk is also the answer to a practical question an already-certified institution asks:
having done ISO 42001, what is left? :func:`residual_work` answers it.
"""

from __future__ import annotations

import functools
from collections.abc import Iterable
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from airm.catalog import load_catalogue

__all__ = [
    "Coverage",
    "Crosswalk",
    "Framework",
    "Mapping",
    "coverage_summary",
    "load_crosswalk",
    "residual_work",
]


class Framework(StrEnum):
    """Frameworks the crosswalk maps to."""

    ISO_42001 = "iso_42001"
    NIST_AI_RMF = "nist_ai_rmf"
    NIST_GENAI = "nist_genai_profile"
    EU_AI_ACT = "eu_ai_act"
    FEAT = "mas_feat"
    MAS_INFO_PAPER = "mas_info_paper_2024"

    @property
    def full_title(self) -> str:
        """Return the framework's full title.

        Named ``full_title`` rather than ``title`` because :class:`str` already defines ``title``
        and a ``StrEnum`` member must not shadow it.
        """
        return _TITLES[self]

    @property
    def is_binding_law(self) -> bool:
        """Whether the framework is binding law rather than guidance or a standard.

        Matters for RQ4: an obligation that exists in the EU AI Act is legally enforceable in the
        EU, while an ISO control is only enforceable through a certification scheme the
        institution chose to enter.
        """
        return self is Framework.EU_AI_ACT


_TITLES: dict[Framework, str] = {
    Framework.ISO_42001: "ISO/IEC 42001:2023 Artificial intelligence management system",
    Framework.NIST_AI_RMF: "NIST AI Risk Management Framework 1.0 (NIST AI 100-1)",
    Framework.NIST_GENAI: "NIST AI RMF Generative AI Profile (NIST AI 600-1)",
    Framework.EU_AI_ACT: "Regulation (EU) 2024/1689 (Artificial Intelligence Act)",
    Framework.FEAT: "MAS FEAT Principles (2018)",
    Framework.MAS_INFO_PAPER: "MAS Information Paper on AI Model Risk Management (Dec 2024)",
}


class Coverage(StrEnum):
    """How far another framework covers a MAS-AIRM expectation."""

    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"

    @property
    def rank(self) -> int:
        """Ordinal rank: 2 full, 1 partial, 0 none."""
        return {"full": 2, "partial": 1, "none": 0}[self.value]


class _Model(BaseModel):
    """Base model forbidding unknown fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Mapping(_Model):
    """One mapping row: a MAS-AIRM paragraph to a framework's provisions."""

    clause: str = Field(description="MAS-AIRM paragraph id, e.g. '5.19'.")
    framework: Framework
    refs: list[str] = Field(
        default_factory=list, description="Provision references in the other framework."
    )
    coverage: Coverage
    justification: str = Field(
        description="Why this coverage level, so a reader can disagree with the row."
    )
    confidence: str = Field(
        default="medium", description="'high', 'medium' or 'low' confidence in the mapping."
    )
    gap: str | None = Field(
        default=None, description="What MAS-AIRM requires that the other framework does not."
    )

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        """A non-``none`` coverage needs a reference; a non-``full`` coverage needs a gap note."""
        if self.coverage is not Coverage.NONE and not self.refs:
            raise ValueError(
                f"{self.clause}/{self.framework.value}: coverage {self.coverage.value} with no "
                f"reference to point at"
            )
        if self.coverage is not Coverage.FULL and not self.gap:
            raise ValueError(
                f"{self.clause}/{self.framework.value}: coverage {self.coverage.value} must say "
                f"what the gap is"
            )
        return self


class Crosswalk(_Model):
    """The whole crosswalk, loaded from the YAML data files in this package."""

    version: str = "1"
    description: str = ""
    mappings: list[Mapping] = Field(default_factory=list)

    @model_validator(mode="after")
    def _known_clauses(self) -> Self:
        """Every mapped clause must exist in the MAS-AIRM catalogue."""
        catalogue = load_catalogue()
        for row in self.mappings:
            if row.clause not in catalogue:
                raise ValueError(f"crosswalk references unknown MAS-AIRM paragraph {row.clause!r}")
        return self

    def __len__(self) -> int:
        """Number of mapping rows."""
        return len(self.mappings)

    def frameworks(self) -> tuple[Framework, ...]:
        """Return the frameworks present in the crosswalk."""
        return tuple(sorted({row.framework for row in self.mappings}, key=lambda f: f.value))

    # -- forward direction: MAS-AIRM to others ---------------------------------

    def for_clause(self, clause: str) -> tuple[Mapping, ...]:
        """Return every mapping for one MAS-AIRM paragraph."""
        return tuple(row for row in self.mappings if row.clause == clause)

    def coverage_of(self, clause: str, framework: Framework) -> Coverage:
        """Return how far one framework covers one paragraph.

        An absent row means no mapping was asserted, which is reported as
        :attr:`Coverage.NONE` rather than silently skipped: a missing row and an asserted gap have
        the same consequence for the institution.
        """
        for row in self.mappings:
            if row.clause == clause and row.framework is framework:
                return row.coverage
        return Coverage.NONE

    def best_coverage(self, clause: str) -> tuple[Coverage, tuple[Framework, ...]]:
        """Return the best coverage any framework offers for a paragraph, and which ones.

        This is the union view RQ4 part (b) asks for: what is left after an institution has done
        everything the other frameworks require.
        """
        rows = self.for_clause(clause)
        if not rows:
            return Coverage.NONE, ()
        # Compare by rank, not by the enum's string value: alphabetically "full" < "partial",
        # which would silently understate the union coverage.
        best = max((row.coverage for row in rows), key=lambda c: c.rank)
        return best, tuple(
            sorted({r.framework for r in rows if r.coverage is best}, key=lambda f: f.value)
        )

    # -- reverse direction: others to MAS-AIRM ---------------------------------

    def for_framework(self, framework: Framework) -> tuple[Mapping, ...]:
        """Return every mapping for one framework, in clause order."""
        catalogue = load_catalogue()
        rows = [row for row in self.mappings if row.framework is framework]
        return tuple(sorted(rows, key=lambda r: catalogue.paragraph(r.clause).sort_key))

    def for_ref(self, framework: Framework, ref: str) -> tuple[Mapping, ...]:
        """Return the MAS-AIRM paragraphs a provision of another framework maps to.

        This is the reverse lookup: "we already evidence ISO 42001 A.6.2.4, what does that buy us
        under MAS-AIRM?"
        """
        needle = ref.lower()
        return tuple(
            row
            for row in self.mappings
            if row.framework is framework and any(needle in r.lower() for r in row.refs)
        )

    # -- summaries -------------------------------------------------------------

    def coverage_counts(self, framework: Framework) -> dict[str, int]:
        """Count expectations at each coverage level for one framework.

        Denominator is the number of MAS-AIRM *expectation* paragraphs, not the number of mapped
        rows, so an unmapped expectation counts against coverage instead of being excluded.
        """
        expectations = [p.id for p in load_catalogue().expectations()]
        counts = {c.value: 0 for c in Coverage}
        for clause in expectations:
            counts[self.coverage_of(clause, framework).value] += 1
        return counts

    def union_counts(self) -> dict[str, int]:
        """Count expectations at each coverage level across all frameworks combined."""
        expectations = [p.id for p in load_catalogue().expectations()]
        counts = {c.value: 0 for c in Coverage}
        for clause in expectations:
            counts[self.best_coverage(clause)[0].value] += 1
        return counts

    def uncovered(self) -> tuple[str, ...]:
        """Return expectations with no ``full`` mapping in any framework (RQ4 part b)."""
        return tuple(
            p.id
            for p in load_catalogue().expectations()
            if self.best_coverage(p.id)[0] is not Coverage.FULL
        )

    def unmapped(self) -> tuple[str, ...]:
        """Return expectations with no mapping row at all, in any framework."""
        mapped = {row.clause for row in self.mappings}
        return tuple(p.id for p in load_catalogue().expectations() if p.id not in mapped)

    @classmethod
    def load(cls, paths: Iterable[str | Path] | None = None) -> Crosswalk:
        """Load the crosswalk from YAML files, or the packaged data.

        Args:
            paths: Explicit YAML files to load and merge; the packaged files if omitted.

        Returns:
            The merged, validated crosswalk.
        """
        rows: list[dict[str, Any]] = []
        description = ""
        version = "1"
        if paths is None:
            package = resources.files("airm.crosswalk")
            texts = [
                package.joinpath(name).read_text(encoding="utf-8")
                for name in sorted(
                    entry.name for entry in package.iterdir() if entry.name.endswith(".yaml")
                )
            ]
        else:
            texts = [Path(p).read_text(encoding="utf-8") for p in paths]
        for text in texts:
            data = yaml.safe_load(text)
            if not isinstance(data, dict):
                continue
            rows.extend(data.get("mappings", []) or [])
            description = description or str(data.get("description", ""))
            version = str(data.get("version", version))
        return cls.model_validate(
            {"version": version, "description": description, "mappings": rows}
        )


@functools.lru_cache(maxsize=1)
def load_crosswalk() -> Crosswalk:
    """Load and cache the packaged crosswalk."""
    return Crosswalk.load()


def coverage_summary(crosswalk: Crosswalk | None = None) -> dict[str, dict[str, int]]:
    """Return per-framework and union coverage counts.

    This is the RQ4 headline table.

    Returns:
        Framework name (plus ``"union"``) to coverage level counts.
    """
    active = crosswalk or load_crosswalk()
    out = {f.value: active.coverage_counts(f) for f in active.frameworks()}
    out["union"] = active.union_counts()
    return out


def residual_work(
    frameworks: Iterable[Framework], *, crosswalk: Crosswalk | None = None
) -> dict[str, list[str]]:
    """Return what MAS-AIRM still requires of an institution already meeting other frameworks.

    Answers the question RQ4 is really about: an institution that holds ISO/IEC 42001 and follows
    NIST AI RMF still has work to do under MAS-AIRM. This returns that work, grouped by
    whether the existing frameworks cover it partially or not at all.

    Args:
        frameworks: The frameworks the institution already meets.
        crosswalk: The crosswalk to use; the packaged one if omitted.

    Returns:
        A mapping with keys ``"uncovered"`` (no coverage from any named framework) and
        ``"partial"`` (covered in part, so a delta remains), each a list of MAS-AIRM paragraph ids.

    Examples:
        >>> work = residual_work([Framework.ISO_42001])
        >>> "4.12" in work["uncovered"] or "4.12" in work["partial"]
        True
    """
    active = crosswalk or load_crosswalk()
    held = set(frameworks)
    uncovered: list[str] = []
    partial: list[str] = []
    for paragraph in load_catalogue().expectations():
        levels = [active.coverage_of(paragraph.id, f) for f in held]
        best = max(levels, key=lambda c: c.rank) if levels else Coverage.NONE
        if best is Coverage.NONE:
            uncovered.append(paragraph.id)
        elif best is Coverage.PARTIAL:
            partial.append(paragraph.id)
    return {"uncovered": uncovered, "partial": partial}
