"""Render paper/paper.md from paper/paper.md.in and results/summary.json.

MISSION Phase 5: every number in the paper is injected, nothing hand-typed. The template holds
the prose and placeholders; this script holds no prose and no arithmetic. Three placeholder forms
are supported:

``{{rq1.auto_share}}``
    A scalar from ``summary["numbers"]``, already print-ready.
``{{table:verdicts}}``
    A Markdown table built from the summary by one of the functions in :data:`TABLES`.
``{{figure:rq1_automatability_by_section}}``
    A pandoc figure with the caption the experiment wrote beside the PNG.
``{{list:threats}}``
    A bullet list built by one of the functions in :data:`LISTS`.
``{{text:rq3_detector_calibration}}``
    A disclosure recorded by an experiment, quoted verbatim.

An unknown placeholder is an error, so a renamed key cannot silently leave a hole in the prose,
and a number present in the summary but never used is reported at the end so that a dropped
finding is visible.

Run with ``PYTHONPATH=experiments .venv/bin/python experiments/render_paper.py``, or ``make paper``.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from difflib import get_close_matches
from pathlib import Path
from typing import Any

from _common import REPO, RESULTS, banner

PAPER_DIR = REPO / "paper"
DOCS_DIR = REPO / "docs"
TEMPLATE = PAPER_DIR / "paper.md.in"
OUTPUT = PAPER_DIR / "paper.md"
SUMMARY = RESULTS / "summary.json"


def templates() -> list[Path]:
    """Return every ``*.md.in`` template, paper first.

    The paper, the executive summary and the LinkedIn drafts all quote results, so they are all
    rendered from the same summary by the same substitution rules. A draft that quotes a number
    by hand would drift from the paper the first time an experiment is re-run.
    """
    found = [TEMPLATE, DOCS_DIR / "EXEC_SUMMARY.md.in"]
    found.extend(sorted((DOCS_DIR / "posts").glob("*.md.in")))
    return [path for path in found if path.is_file()]


PLACEHOLDER = re.compile(r"\{\{([a-z0-9_.:]+)\}\}")

RQ_TITLES = {
    "rq1": "RQ1 Automatability",
    "rq2": "RQ2 Autonomy and materiality",
    "rq3": "RQ3 Guardrail effectiveness",
    "rq4": "RQ4 Crosswalk coverage",
    "rq5": "RQ5 Cost of compliance",
}

FRAMEWORK_ORDER = (
    "iso_42001",
    "nist_ai_rmf",
    "nist_genai_profile",
    "eu_ai_act",
    "mas_feat",
    "mas_info_paper_2024",
)


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    """Return a GitHub-flavoured Markdown table."""
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(out)


def _pct(share: float, places: int = 1) -> str:
    return f"{share * 100:.{places}f}%"


def table_verdicts(summary: dict[str, Any]) -> str:
    """Every pre-registered hypothesis with its verdict, held or refuted."""
    rows = [
        [
            row["rq"].upper(),
            row["hypothesis"],
            "holds" if row["holds"] else "**refuted**",
            row["detail"],
        ]
        for row in summary["verdicts"]
    ]
    return _md_table(["RQ", "Hypothesis", "Verdict", "Evidence"], rows)


def table_rq1_sections(summary: dict[str, Any]) -> str:
    """Automatability shares of expectation paragraphs by Guidelines section."""
    by_section = summary["rq"]["rq1"]["by_section"]
    rows = [
        [
            f"Section {section}",
            str(row["total"]),
            _pct(row["auto"]),
            _pct(row["semi"]),
            _pct(row["doc"]),
        ]
        for section, row in sorted(by_section.items())
    ]
    totals = summary["rq"]["rq1"]["paragraph_totals"]
    rows.append(
        [
            "**All**",
            f"**{totals['n']}**",
            f"**{_pct(totals['shares']['auto'])}**",
            f"**{_pct(totals['shares']['semi'])}**",
            f"**{_pct(totals['shares']['doc'])}**",
        ]
    )
    return _md_table(["Section", "Expectations", "auto", "semi", "doc"], rows)


def table_rq1_classes(summary: dict[str, Any]) -> str:
    """Control counts per automatability class, with what each class means."""
    meanings = {
        "auto": "a deterministic function of the inventory entry and its evidence decides "
        "the outcome",
        "semi": "presence and currency of the artefact is machine-checkable; adequacy needs "
        "human attestation",
        "doc": "organisational or judgemental; no artefact the toolkit inspects",
    }
    controls = summary["rq"]["rq1"]["control_totals"]
    paragraphs = summary["rq"]["rq1"]["paragraph_totals"]
    rows = [
        [
            f"`{cls}`",
            meanings[cls],
            f"{paragraphs['counts'][cls]} ({_pct(paragraphs['shares'][cls])})",
            f"{controls['counts'][cls]} ({_pct(controls['shares'][cls])})",
        ]
        for cls in ("auto", "semi", "doc")
    ]
    return _md_table(["Class", "Meaning", "Expectations", "Controls"], rows)


def table_rq2_ladder(summary: dict[str, Any]) -> str:
    """Applicable controls and inherent tier at each rung of the autonomy ladder."""
    ladders = summary["rq"]["rq2"]["ladders"]
    subjects = summary["rq"]["rq2"]["subjects"]
    levels = summary["rq"]["rq2"]["ladder"]
    rows = []
    for index, level in enumerate(levels):
        row = [f"`{level}`"]
        for subject in subjects:
            step = ladders[subject][index]
            row.append(f"{step['applicable']} ({step['inherent']})")
        rows.append(row)
    header = ["Autonomy level", *(s.replace("-", " ") for s in subjects)]
    return _md_table(header, rows)


def table_rq3_patterns(summary: dict[str, Any]) -> str:
    """Attack success and over-refusal for each guardrail pattern."""
    rq3 = summary["rq"]["rq3"]
    rows = []
    for pattern, result in rq3["results"].items():
        tiers = ", ".join(result["meets_tiers"]) or "none"
        rows.append(
            [
                f"`{pattern}`",
                f"{_pct(result['overall_asr'])} ({result['successes']}/{result['trials']})",
                f"[{_pct(result['ci_lower'])}, {_pct(result['ci_upper'])}]",
                f"{_pct(result['over_refusal'])} "
                f"({result['over_refusals']}/{result['over_refusal_trials']})",
                tiers,
            ]
        )
    return _md_table(
        ["Pattern", "Attack success", "95% CI", "Over-refusal (benign)", "Tiers met"], rows
    )


def table_rq3_families(summary: dict[str, Any]) -> str:
    """Attack success rate per probe family under each guardrail pattern."""
    results = summary["rq"]["rq3"]["results"]
    patterns = list(results)
    families = list(results[patterns[0]]["by_family"])
    rows = []
    for family in families:
        row = [family.replace("_", " ")]
        for pattern in patterns:
            entry = results[pattern]["by_family"][family]
            row.append(f"{_pct(entry['asr'])} ({entry['successes']}/{entry['trials']})")
        rows.append(row)
    return _md_table(["Probe family", *(f"`{p}`" for p in patterns)], rows)


def table_rq4_frameworks(summary: dict[str, Any]) -> str:
    """Per-framework coverage of the MAS-AIRM expectation paragraphs."""
    per_framework = summary["rq"]["rq4"]["per_framework"]
    rows = []
    for key in FRAMEWORK_ORDER:
        row = per_framework[key]
        rows.append(
            [
                row["title"],
                "yes" if row["binding_law"] else "no",
                str(row["full"]),
                str(row["partial"]),
                str(row["none"]),
                _pct(row["full_share"]),
            ]
        )
    union = summary["rq"]["rq4"]["union_international"]
    rows.append(
        [
            "**Union of ISO 42001, NIST AI RMF, EU AI Act**",
            "—",
            f"**{union['full']}**",
            f"**{summary['rq']['rq4']['expectations'] - union['full']}**",
            "**0**",
            f"**{_pct(union['full_share'])}**",
        ]
    )
    return _md_table(["Framework", "Binding law", "full", "partial", "none", "full share"], rows)


def table_rq4_residue(summary: dict[str, Any]) -> str:
    """The expectations with no full mapping in any crosswalked framework.

    ``predicted`` records whether docs/RESEARCH_QUESTIONS.md named the clause before the
    crosswalk was scored, which is what H4(c) was tested on.
    """
    residue = summary["rq"]["rq4"]["residue_all_frameworks"]
    rows = [
        [
            f"§{clause}",
            row["heading"],
            row["best_coverage"],
            "yes" if row["predicted"] else "no",
        ]
        for clause, row in residue.items()
    ]
    return _md_table(["Expectation", "Heading", "Best coverage", "Pre-registered as residue"], rows)


def table_rq5_tiers(summary: dict[str, Any]) -> str:
    """Controls, evidence items and estimated effort per materiality tier."""
    by_tier = summary["rq"]["rq5"]["by_tier"]
    rows = []
    for tier, row in by_tier.items():
        if not row["use_cases"]:
            rows.append([tier, "0", "—", "—", "—"])
            continue
        rows.append(
            [
                tier,
                str(row["use_cases"]),
                f"{row['mean_controls']:.1f}",
                f"{row['mean_evidence_items']:.1f}",
                f"{row['mean_first_time_hours']:.1f}",
            ]
        )
    institution = summary["rq"]["rq5"]["institution_level"]
    rows.append(
        [
            "Institution-level",
            "—",
            str(institution["controls"]),
            str(institution["evidence_items"]),
            f"{institution['first_time_hours']:.1f}",
        ]
    )
    return _md_table(
        [
            "Inherent tier",
            "Use cases",
            "Mean applicable controls",
            "Mean evidence items",
            "Mean first-time hours",
        ],
        rows,
    )


def table_rq5_use_cases(summary: dict[str, Any]) -> str:
    """Per-use-case effort estimate for the synthetic portfolio."""
    rows = []
    for use_case, row in summary["rq"]["rq5"]["per_use_case"].items():
        rows.append(
            [
                f"`{use_case}`",
                row["tier"],
                str(row["applicable_controls"]),
                str(row["evidence_items"]),
                f"{row['first_time_hours']:.1f}",
                f"{row['recurring_hours_per_year']:.1f}",
            ]
        )
    return _md_table(
        [
            "Use case",
            "Inherent tier",
            "Controls",
            "Evidence items",
            "First-time hours",
            "Recurring hours/year",
        ],
        rows,
    )


def table_rq5_effort(summary: dict[str, Any]) -> str:
    """Estimated effort by automatability class and by control category."""
    totals = summary["rq"]["rq5"]["totals"]
    rows = [
        [f"`{cls}`", f"{hours:.1f}", _pct(totals["effort_share_by_class"][cls])]
        for cls, hours in totals["effort_by_class"].items()
    ]
    rows.append(["", "", ""])
    by_category = totals["effort_share_by_category"]
    rows.extend(
        [category.replace("_", " "), f"{hours:.1f}", _pct(by_category[category])]
        for category, hours in sorted(totals["effort_by_category"].items(), key=lambda kv: -kv[1])
    )
    return _md_table(["Class or category", "Estimated hours", "Share"], rows)


def table_portfolio(summary: dict[str, Any]) -> str:
    """The synthetic bank portfolio as the toolkit rates it."""
    rows = []
    for use_case, row in summary["rq"]["rq5"]["per_use_case"].items():
        rows.append(
            [
                f"`{use_case}`",
                row["tier"],
                row["residual"],
                str(row["applicable_controls"]),
                str(row["by_class"]["auto"]),
                str(row["by_class"]["semi"]),
                str(row["by_class"]["doc"]),
            ]
        )
    return _md_table(
        ["Use case", "Inherent", "Residual", "Applicable controls", "auto", "semi", "doc"], rows
    )


def table_outcomes(summary: dict[str, Any]) -> str:
    """Control outcomes across the portfolio, including the institution-level controls."""
    outcomes = summary["portfolio"]["outcomes"]
    total = sum(outcomes.values())
    rows = [
        [label.replace("_", " "), str(count), _pct(count / total if total else 0.0)]
        for label, count in outcomes.items()
    ]
    return _md_table(["Outcome", "Checks", "Share"], rows)


def list_threats(summary: dict[str, Any]) -> str:
    """Every threat to validity recorded by an experiment, grouped by RQ."""
    out: list[str] = []
    for key, threats in summary["threats_to_validity"].items():
        out.append(f"**{RQ_TITLES[key]}.**\n")
        out.extend(f"- {threat}" for threat in threats)
        out.append("")
    return "\n".join(out).strip()


def list_questions(summary: dict[str, Any]) -> str:
    """The five research questions as asked, with the method used to answer each."""
    out: list[str] = []
    for key, question in summary["questions"].items():
        out.append(f"- **{RQ_TITLES[key]}.** {question} *Method:* {summary['methods'][key]}")
    return "\n".join(out)


def list_refuted(summary: dict[str, Any]) -> str:
    """The refuted hypotheses, which are the paper's substantive findings."""
    return "\n".join(
        f"- **{row['hypothesis']}** — {row['detail']}"
        for row in summary["verdicts"]
        if not row["holds"]
    )


TABLES = {
    "verdicts": table_verdicts,
    "rq1_sections": table_rq1_sections,
    "rq1_classes": table_rq1_classes,
    "rq2_ladder": table_rq2_ladder,
    "rq3_patterns": table_rq3_patterns,
    "rq3_families": table_rq3_families,
    "rq4_frameworks": table_rq4_frameworks,
    "rq4_residue": table_rq4_residue,
    "rq5_tiers": table_rq5_tiers,
    "rq5_use_cases": table_rq5_use_cases,
    "rq5_effort": table_rq5_effort,
    "portfolio": table_portfolio,
    "outcomes": table_outcomes,
}

LISTS = {
    "threats": list_threats,
    "questions": list_questions,
    "refuted": list_refuted,
}


def figure(summary: dict[str, Any], name: str) -> str:
    """Return the pandoc figure for one experiment figure, with its committed caption.

    Raises:
        KeyError: If no experiment produced a figure with that stem.
    """
    for row in summary["figures"]:
        if Path(row["file"]).stem == name:
            caption = row["caption"].replace("\n", " ").strip()
            return f"![{caption}](../results/figures/{row['file']})\n"
    known = ", ".join(sorted(Path(row["file"]).stem for row in summary["figures"]))
    raise KeyError(f"no figure named {name!r}; the summary has: {known}")


def text(summary: dict[str, Any], name: str) -> str:
    """Return one prose disclosure, quoted verbatim.

    The disclosures and the disclaimer are prose, not numbers, so they are not in
    ``summary["numbers"]``; they are still injected rather than retyped, so that a caveat cannot
    be softened in the paper while the result file says something else.

    Raises:
        KeyError: If the summary carries no such text.
    """
    if name == "disclaimer":
        return str(summary["disclaimer"])
    if name == "version":
        return str(summary["provenance"]["airmkit_version"])
    if name == "git_revision":
        return str(summary["provenance"]["git_revision"])
    disclosures = summary["disclosures"]
    if name not in disclosures:
        known = ", ".join(["disclaimer", "version", "git_revision", *sorted(disclosures)])
        raise KeyError(f"unknown text {name!r}; known: {known}")
    return str(disclosures[name])


def resolve(token: str, summary: dict[str, Any], used: set[str]) -> str:
    """Resolve one placeholder token to its replacement text.

    Args:
        token: The text between the braces, e.g. ``rq1.auto_share`` or ``table:verdicts``.
        summary: The parsed ``results/summary.json``.
        used: Mutated to record which number keys the template consumed.

    Returns:
        The replacement text.

    Raises:
        KeyError: If the token names nothing in the summary. The message suggests near matches,
            because the usual cause is a renamed key in ``collect.py``.
    """
    if ":" in token:
        kind, name = token.split(":", 1)
        if kind == "table":
            if name not in TABLES:
                raise KeyError(f"unknown table {name!r}; known: {', '.join(sorted(TABLES))}")
            return TABLES[name](summary)
        if kind == "list":
            if name not in LISTS:
                raise KeyError(f"unknown list {name!r}; known: {', '.join(sorted(LISTS))}")
            return LISTS[name](summary)
        if kind == "figure":
            return figure(summary, name)
        if kind == "text":
            return text(summary, name)
        raise KeyError(f"unknown placeholder kind {kind!r} in {{{{{token}}}}}")

    numbers = summary["numbers"]
    if token not in numbers:
        hint = get_close_matches(token, numbers, n=3)
        suggestion = f"; did you mean {', '.join(hint)}?" if hint else ""
        raise KeyError(f"{token!r} is not in results/summary.json numbers{suggestion}")
    used.add(token)
    return str(numbers[token])


def render(template: str, summary: dict[str, Any]) -> tuple[str, set[str]]:
    """Substitute every placeholder in the template.

    Returns:
        The rendered text and the set of number keys the template used.
    """
    used: set[str] = set()
    rendered = PLACEHOLDER.sub(lambda m: resolve(m.group(1), summary, used), template)
    return rendered, used


def summary_date(summary: dict[str, Any]) -> str:
    """Return the date of the run the summary describes, for ``{{DATE}}``.

    Deliberately not today's date: the paper is dated by the results it reports, so re-rendering
    an unchanged summary produces an unchanged paper and CI can detect a stale artefact.
    """
    generated = str(summary["provenance"]["generated_at"])
    return generated[:10] if len(generated) >= 10 else dt.date.today().isoformat()


def render_file(path: Path, summary: dict[str, Any]) -> tuple[Path, str, set[str]]:
    """Render one template to its sibling without the ``.in`` suffix.

    Returns:
        The path written, the rendered text and the number keys it used.
    """
    rendered, used = render(path.read_text(encoding="utf-8"), summary)
    rendered = rendered.replace("{{DATE}}", summary_date(summary))
    target = path.with_suffix("")
    target.write_text(rendered, encoding="utf-8")
    return target, rendered, used


def main() -> None:
    """Render every template from results/summary.json and report any unused numbers."""
    banner("render_paper: injecting results/summary.json into the paper and communications")
    if not SUMMARY.is_file():
        raise FileNotFoundError(f"{SUMMARY} not found; run `python experiments/collect.py` first")
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    used: set[str] = set()
    for path in templates():
        target, rendered, consumed = render_file(path, summary)
        used |= consumed
        print(f"  {target.relative_to(REPO)}: {len(rendered.split())} words")

    unused = sorted(set(summary["numbers"]) - used)
    print(f"  {len(used)} of {len(summary['numbers'])} numbers used")
    if unused:
        print(f"  not quoted anywhere ({len(unused)}): {', '.join(unused)}")


if __name__ == "__main__":
    main()
