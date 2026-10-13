"""RQ1: what fraction of MAS-AIRM expectations can be automatically checked?

Classifies every expectation paragraph and every control as `auto`, `semi` or `doc` and tests the
two inequalities fixed in docs/RESEARCH_QUESTIONS.md before the experiment ran:

  H1(a)  auto < 50% of expectation paragraphs, and the majority are semi.
  H1(b)  Section 4 has a higher auto share than Section 3.

A paragraph's class is the *best* class among the controls implementing it: if any control can
decide the paragraph automatically, the paragraph is at least partly automatable. Paragraphs with
no implementing control are counted as `doc`, which is the honest treatment since this toolkit
offers no way to check them.
"""

from __future__ import annotations

from collections import Counter

from _common import banner, share, verdict, write_result
from airm.catalog import load_catalogue
from airm.controls import Scope, load_controls
from figures import render

FIGURE = "rq1_automatability_by_section"

CLASS_ORDER = ["auto", "semi", "doc"]
RANK = {"auto": 2, "semi": 1, "doc": 0}


def classify_paragraphs() -> dict[str, dict[str, object]]:
    """Return expectation paragraph id to its automatability class and the controls behind it."""
    catalogue = load_catalogue()
    controls = load_controls()
    out: dict[str, dict[str, object]] = {}
    for paragraph in catalogue.expectations():
        implementing = controls.by_clause(paragraph.id)
        if not implementing:
            out[paragraph.id] = {
                "section": paragraph.section,
                "heading": paragraph.heading,
                "klass": "doc",
                "controls": [],
                "justification": (
                    "No control in this catalogue implements the paragraph, so this toolkit "
                    "offers no way to check it."
                ),
            }
            continue
        best = max(implementing, key=lambda c: RANK[c.automatability.value])
        out[paragraph.id] = {
            "section": paragraph.section,
            "heading": paragraph.heading,
            "klass": best.automatability.value,
            "controls": [c.id for c in implementing],
            "justification": best.automatability_rationale.strip(),
        }
    return out


def main() -> None:
    banner("RQ1 - Automatability of the MAS-AIRM expectations")
    catalogue = load_catalogue()
    controls = load_controls()

    paragraphs = classify_paragraphs()
    total = len(paragraphs)
    counts = Counter(str(row["klass"]) for row in paragraphs.values())
    shares = {k: share(counts.get(k, 0), total) for k in CLASS_ORDER}

    print(f"\n  {total} expectation paragraphs")
    for klass in CLASS_ORDER:
        print(f"    {klass:5} {counts.get(klass, 0):3}  {shares[klass]:6.1%}")

    # per-section view
    by_section: dict[str, Counter[str]] = {}
    for row in paragraphs.values():
        by_section.setdefault(str(row["section"]), Counter())[str(row["klass"])] += 1
    section_shares = {
        section: {
            "total": sum(c.values()),
            **{k: share(c.get(k, 0), sum(c.values())) for k in CLASS_ORDER},
        }
        for section, c in sorted(by_section.items())
    }
    print("\n  by section (auto share)")
    for section, row in section_shares.items():
        title = catalogue.section(section).title
        print(f"    Section {section} {title[:38]:40} n={row['total']:2}  auto={row['auto']:6.1%}")

    # control-level view
    control_counts = controls.automatability_counts()
    control_shares = {k: share(control_counts[k], len(controls)) for k in CLASS_ORDER}
    print(f"\n  {len(controls)} controls")
    for klass in CLASS_ORDER:
        print(f"    {klass:5} {control_counts[klass]:3}  {control_shares[klass]:6.1%}")

    # family view: where is automation concentrated?
    family_rows = {}
    for family in controls.families():
        members = controls.by_family(family)
        family_counter = Counter(c.automatability.value for c in members)
        family_rows[family] = {
            "total": len(members),
            **{k: family_counter.get(k, 0) for k in CLASS_ORDER},
            "auto_share": share(family_counter.get("auto", 0), len(members)),
        }

    verdicts = [
        verdict(
            "H1(a) auto share is below 50% of expectation paragraphs",
            shares["auto"] < 0.50,
            f"auto = {shares['auto']:.1%} ({counts.get('auto', 0)}/{total})",
        ),
        verdict(
            "H1(a) semi is the largest class",
            counts.get("semi", 0) > counts.get("auto", 0)
            and counts.get("semi", 0) > counts.get("doc", 0),
            f"semi = {counts.get('semi', 0)}, auto = {counts.get('auto', 0)}, "
            f"doc = {counts.get('doc', 0)}",
        ),
        verdict(
            "H1(b) Section 4 auto share exceeds Section 3",
            section_shares["4"]["auto"] > section_shares["3"]["auto"],
            f"Section 4 = {section_shares['4']['auto']:.1%}, "
            f"Section 3 = {section_shares['3']['auto']:.1%}",
        ),
    ]

    path = write_result(
        "rq1_automatability",
        {
            "question": (
                "What fraction of MAS-AIRM expectations can be automatically checked from "
                "artefacts, semi-automated with human attestation, or only documented?"
            ),
            "method": (
                "Each of the 51 expectation paragraphs takes the best automatability class among "
                "the controls implementing it; paragraphs with no implementing control count as "
                "doc. Classes and their justifications are in src/airm/controls/controls.yaml."
            ),
            "paragraph_totals": {"n": total, "counts": dict(counts), "shares": shares},
            "by_section": section_shares,
            "control_totals": {
                "n": len(controls),
                "counts": control_counts,
                "shares": control_shares,
                "use_case_scope": sum(1 for c in controls.controls if c.scope is Scope.USE_CASE),
                "institution_scope": sum(
                    1 for c in controls.controls if c.scope is Scope.INSTITUTION
                ),
            },
            "by_family": family_rows,
            "per_paragraph": paragraphs,
            "uncovered_expectations": list(controls.uncovered_expectations()),
            "verdicts": verdicts,
            "threats_to_validity": [
                "The classification is the authors' judgement, not MAS'. Each row carries a "
                "written justification so it can be disputed individually.",
                "A clause is auto *relative to this implementation*: it depends on what the "
                "toolkit ingests. A richer integration would move some semi clauses to auto.",
                "Single annotator, so no inter-rater agreement is available. The full table is "
                "published for challenge.",
                "Taking the best class per paragraph flatters automatability: a paragraph with "
                "one auto and four doc controls counts as auto.",
            ],
            "figures": [f"{FIGURE}.png"],
        },
    )
    print(f"  result: {path.relative_to(path.parents[1])}")
    print(f"  figure: {render(FIGURE).name}")


if __name__ == "__main__":
    main()
