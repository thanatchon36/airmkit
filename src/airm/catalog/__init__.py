"""The MAS-AIRM clause catalogue: a machine-readable index of the Guidelines.

Serves MAS-AIRM §1.1-§1.8 (scope, definitions and effective dates) by making every paragraph
addressable, taggable and dateable, so that controls, reports and the docs site can cite clauses
instead of restating them.

The data file is ``mas_airm_2026.yaml`` inside this package. Paragraph *summaries* are the
authors' paraphrase (<= 40 words) and are never the regulatory text; read the primary PDF
(``docs/sources/mas_airm_guidelines_2026-10-07.pdf``) before relying on a clause.
"""

from __future__ import annotations

import datetime as dt
import functools
from dataclasses import dataclass, field
from importlib import resources
from typing import Any, Literal

import yaml

__all__ = [
    "CITATION_PREFIX",
    "Catalogue",
    "Footnote",
    "Item",
    "Paragraph",
    "Section",
    "cite",
    "load_catalogue",
]

CITATION_PREFIX = "MAS-AIRM"

ParagraphKind = Literal["expectation", "guidance", "definition", "scope", "context"]
"""Classification of what a paragraph does.

``expectation`` is a supervisory expectation ("an FI should ..."); ``guidance`` and ``context``
are explanatory; ``definition`` defines a term; ``scope`` sets application boundaries.
"""


def cite(paragraph_id: str, item: str | None = None, footnote: int | None = None) -> str:
    """Return a citation string for a Guidelines paragraph.

    Serves MAS-AIRM §1.1: every claim this toolkit makes must point at a paragraph.

    Args:
        paragraph_id: Paragraph id such as ``"4.7"``.
        item: Optional lettered item such as ``"a"``.
        footnote: Optional footnote number.

    Returns:
        A citation such as ``"MAS-AIRM §4.7"``, ``"MAS-AIRM §5.23(d)"`` or
        ``"MAS-AIRM §4.8 fn25"``.

    Examples:
        >>> cite("4.7")
        'MAS-AIRM §4.7'
        >>> cite("5.23", item="d")
        'MAS-AIRM §5.23(d)'
        >>> cite("4.8", footnote=25)
        'MAS-AIRM §4.8 fn25'
    """
    out = f"{CITATION_PREFIX} §{paragraph_id}"
    if item:
        out += f"({item})"
    if footnote is not None:
        out += f" fn{footnote}"
    return out


@dataclass(frozen=True)
class Item:
    """A lettered sub-item of a paragraph, e.g. MAS-AIRM §4.12(a)."""

    id: str
    summary: str

    @property
    def label(self) -> str:
        """Return the bare item label, e.g. ``"a"``."""
        return self.id


@dataclass(frozen=True)
class Footnote:
    """A footnote of the Guidelines.

    Footnotes matter because several carry requirements rather than references: footnote 22
    (shadow-AI technical controls), footnote 25 (agent inventory attributes), footnote 46
    (Generative AI failure modes) and footnote 13 (human review of assistive outputs).
    """

    id: int
    anchored_to: str
    page: int
    kind: ParagraphKind
    summary: str
    tags: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()

    @property
    def citation(self) -> str:
        """Return a citation such as ``"MAS-AIRM §4.8 fn25"``."""
        return cite(self.anchored_to, footnote=self.id)

    @property
    def is_normative(self) -> bool:
        """Whether the footnote carries an expectation or a scoping rule, not just a reference."""
        return self.kind in ("expectation", "scope", "definition")


@dataclass(frozen=True)
class Paragraph:
    """A numbered paragraph of the Guidelines."""

    id: str
    section: str
    heading: str
    page: int
    kind: ParagraphKind
    applies_to: tuple[str, ...]
    effective: dt.date
    summary: str
    tags: tuple[str, ...] = ()
    items: tuple[Item, ...] = ()
    footnote_ids: tuple[int, ...] = ()
    attributes: tuple[str, ...] = ()
    high_materiality_only: bool = False

    @property
    def citation(self) -> str:
        """Return a citation such as ``"MAS-AIRM §4.7"``."""
        return cite(self.id)

    @property
    def is_expectation(self) -> bool:
        """Whether this paragraph states a supervisory expectation."""
        return self.kind == "expectation"

    @property
    def sort_key(self) -> tuple[int, int]:
        """Return a numeric sort key so that §4.10 follows §4.9 rather than §4.1."""
        major, minor = self.id.split(".")
        return (int(major), int(minor))

    def item(self, item_id: str) -> Item:
        """Return the lettered item with this id.

        Raises:
            KeyError: If the paragraph has no such item.
        """
        for candidate in self.items:
            if candidate.id == item_id:
                return candidate
        raise KeyError(f"{self.citation} has no item ({item_id})")

    def has_tag(self, *tags: str) -> bool:
        """Whether the paragraph carries any of the given tags."""
        return any(tag in self.tags for tag in tags)


@dataclass(frozen=True)
class Section:
    """A top-level section of the Guidelines, e.g. Section 5 AI Life Cycle Controls."""

    id: str
    title: str
    pages: tuple[int, int]
    effective: dt.date


@dataclass(frozen=True)
class Catalogue:
    """The whole clause index, loaded from ``mas_airm_2026.yaml``.

    Serves MAS-AIRM §1.8 (effective dates) and the docs-site clause index requirement by holding
    paragraphs, footnotes and sections in one queryable object.
    """

    meta: dict[str, Any]
    sections: tuple[Section, ...]
    paragraphs: tuple[Paragraph, ...]
    footnotes: tuple[Footnote, ...]
    _by_id: dict[str, Paragraph] = field(default_factory=dict, repr=False, compare=False)
    _fn_by_id: dict[int, Footnote] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Build the id lookup tables."""
        self._by_id.update({p.id: p for p in self.paragraphs})
        self._fn_by_id.update({f.id: f for f in self.footnotes})

    # -- lookup ----------------------------------------------------------------

    def paragraph(self, paragraph_id: str) -> Paragraph:
        """Return the paragraph with this id.

        Args:
            paragraph_id: Paragraph id such as ``"5.19"``.

        Raises:
            KeyError: If no such paragraph exists.
        """
        try:
            return self._by_id[paragraph_id]
        except KeyError:
            raise KeyError(f"no such MAS-AIRM paragraph: {paragraph_id}") from None

    def footnote(self, footnote_id: int) -> Footnote:
        """Return the footnote with this number.

        Raises:
            KeyError: If no such footnote exists.
        """
        try:
            return self._fn_by_id[footnote_id]
        except KeyError:
            raise KeyError(f"no such MAS-AIRM footnote: {footnote_id}") from None

    def section(self, section_id: str) -> Section:
        """Return the section with this id.

        Raises:
            KeyError: If no such section exists.
        """
        for candidate in self.sections:
            if candidate.id == section_id:
                return candidate
        raise KeyError(f"no such MAS-AIRM section: {section_id}")

    def __contains__(self, paragraph_id: object) -> bool:
        """Whether a paragraph id is in the catalogue."""
        return isinstance(paragraph_id, str) and paragraph_id in self._by_id

    def __len__(self) -> int:
        """Number of paragraphs in the catalogue."""
        return len(self.paragraphs)

    # -- queries ---------------------------------------------------------------

    def expectations(self) -> tuple[Paragraph, ...]:
        """Return every paragraph that states a supervisory expectation."""
        return tuple(p for p in self.paragraphs if p.is_expectation)

    def by_section(self, section_id: str) -> tuple[Paragraph, ...]:
        """Return the paragraphs of one section, in document order."""
        return tuple(p for p in self.paragraphs if p.section == section_id)

    def by_tag(self, *tags: str) -> tuple[Paragraph, ...]:
        """Return the paragraphs carrying any of these tags.

        Useful for the LLM- and agent-specific views: ``by_tag("agent")`` gives the clauses an
        agentic use case must satisfy beyond the general ones.
        """
        return tuple(p for p in self.paragraphs if p.has_tag(*tags))

    def footnotes_of(self, paragraph_id: str) -> tuple[Footnote, ...]:
        """Return the footnotes anchored to a paragraph."""
        para = self.paragraph(paragraph_id)
        return tuple(self.footnote(i) for i in para.footnote_ids)

    def normative_footnotes(self) -> tuple[Footnote, ...]:
        """Return footnotes that carry a requirement, scope rule or definition.

        These are the footnotes the toolkit treats as binding, such as footnote 22 (shadow-AI
        technical controls) and footnote 25 (agent inventory attributes).
        """
        return tuple(f for f in self.footnotes if f.is_normative)

    def inventory_attributes(self) -> tuple[str, ...]:
        """Return the inventory attributes named in MAS-AIRM §4.7."""
        return self.paragraph("4.7").attributes

    def agent_attributes(self) -> tuple[str, ...]:
        """Return the agent-specific inventory attributes named in MAS-AIRM §4.8 fn25."""
        return self.footnote(25).attributes

    def genai_failure_modes(self) -> tuple[str, ...]:
        """Return the Generative AI failure modes named in MAS-AIRM §5.15 fn46."""
        return self.footnote(46).failure_modes

    def effective_date(self, paragraph_id: str) -> dt.date:
        """Return the date by which an FI should meet a paragraph.

        Implements MAS-AIRM §1.8 as clarified by the Response to Feedback §13.5: Sections 3-4 from
        7 October 2027, Sections 5-6 by 7 October 2028. See ``docs/INTERPRETATIONS.md`` I-1.
        """
        return self.paragraph(paragraph_id).effective

    def high_materiality_clauses(self) -> tuple[Paragraph, ...]:
        """Return the clauses that bind only for high-materiality use cases.

        MAS-AIRM §5.3 (contingency plans), §5.19 (formal independent validation) and the
        high-risk limbs of §5.23(b) and §5.24. Per Response to Feedback §7.21 these trigger on
        *inherent* risk materiality (``docs/INTERPRETATIONS.md`` I-3).
        """
        return tuple(p for p in self.paragraphs if p.high_materiality_only)

    def tag_vocabulary(self) -> tuple[str, ...]:
        """Return the closed tag vocabulary declared in the data file."""
        return tuple(self.meta.get("tag_vocabulary", ()))


def _as_date(value: object) -> dt.date:
    """Coerce a YAML scalar to a date."""
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        return dt.date.fromisoformat(value)
    raise TypeError(f"expected a date, got {value!r}")


def _parse_paragraph(raw: dict[str, Any]) -> Paragraph:
    """Build a Paragraph from its YAML mapping."""
    return Paragraph(
        id=str(raw["id"]),
        section=str(raw["section"]),
        heading=str(raw["heading"]),
        page=int(raw["page"]),
        kind=raw["kind"],
        applies_to=tuple(raw.get("applies_to", ())),
        effective=_as_date(raw["effective"]),
        summary=" ".join(str(raw["summary"]).split()),
        tags=tuple(raw.get("tags", ())),
        items=tuple(
            Item(id=str(i["id"]), summary=" ".join(str(i["summary"]).split()))
            for i in raw.get("items", ())
        ),
        footnote_ids=tuple(int(f) for f in raw.get("footnotes", ())),
        attributes=tuple(raw.get("attributes", ())),
        high_materiality_only=bool(raw.get("high_materiality_only", False)),
    )


def _parse_footnote(raw: dict[str, Any]) -> Footnote:
    """Build a Footnote from its YAML mapping."""
    return Footnote(
        id=int(raw["id"]),
        anchored_to=str(raw["anchored_to"]),
        page=int(raw["page"]),
        kind=raw["kind"],
        summary=" ".join(str(raw["summary"]).split()),
        tags=tuple(raw.get("tags", ())),
        attributes=tuple(raw.get("attributes", ())),
        failure_modes=tuple(raw.get("failure_modes", ())),
    )


@functools.lru_cache(maxsize=1)
def load_catalogue() -> Catalogue:
    """Load and cache the MAS-AIRM clause catalogue shipped with the package.

    Serves MAS-AIRM §1.1-§1.8. The result is immutable and cached, so callers may treat it as a
    constant.

    Returns:
        The parsed :class:`Catalogue`.

    Examples:
        >>> cat = load_catalogue()
        >>> cat.paragraph("4.12").kind
        'expectation'
        >>> "impact" in cat.paragraph("4.12").item("a").summary.lower()
        True
    """
    text = (
        resources.files("airm.catalog").joinpath("mas_airm_2026.yaml").read_text(encoding="utf-8")
    )
    raw: dict[str, Any] = yaml.safe_load(text)
    paragraphs = tuple(sorted((_parse_paragraph(p) for p in raw["paragraphs"]), key=lambda p: p.sort_key))
    sections = tuple(
        Section(
            id=str(s["id"]),
            title=str(s["title"]),
            pages=(int(s["pages"][0]), int(s["pages"][1])),
            effective=_as_date(s["effective"]),
        )
        for s in raw["sections"]
    )
    footnotes = tuple(sorted((_parse_footnote(f) for f in raw["footnotes"]), key=lambda f: f.id))
    return Catalogue(meta=raw["meta"], sections=sections, paragraphs=paragraphs, footnotes=footnotes)
