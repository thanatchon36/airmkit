"""RQ4: how much of MAS-AIRM does an already-certified institution still have to do?

Computes per-framework and union coverage of the 51 MAS-AIRM expectation paragraphs and tests the
thresholds fixed in docs/RESEARCH_QUESTIONS.md:

  H4(a) no single framework fully covers more than 60% of expectations;
  H4(b) the union of ISO 42001, NIST AI RMF and the EU AI Act leaves at least 10% with no full
        mapping;
  H4(c) the residue is concentrated in the Singapore-specific and agent-specific clauses.

Mapping is interpretive and asymmetric, so every row in src/airm/crosswalk/ carries its own
justification, confidence and gap note. The point of publishing the table is that a reader can
disagree with a row rather than with the conclusion.
"""

from __future__ import annotations

from collections import Counter

from _common import NEUTRAL, banner, new_figure, save_figure, share, verdict, write_result
from airm.catalog import load_catalogue
from airm.crosswalk import Coverage, Framework, load_crosswalk, residual_work

COVERAGE_COLOURS = {"full": "#54A24B", "partial": "#E4A03A", "none": "#C4453C"}
# The three frameworks an internationally active institution is most likely to already hold or
# follow. FEAT and the MAS Information Paper are MAS' own material and are reported separately.
INTERNATIONAL = [Framework.ISO_42001, Framework.NIST_AI_RMF, Framework.EU_AI_ACT]

# Clauses RQ4(c) predicted would form the residue, named before the mapping was scored.
PREDICTED_RESIDUE = {
    "1.2": "group basis application",
    "3.6": "local senior management accountability",
    "4.2": "embedded AI identification",
    "4.3": "designated control function for identification",
    "4.4": "shadow AI residual risk",
    "4.9": "designated control function for inventory",
    "4.12": "Impact / Complexity / Reliance assessment",
    "4.13": "designated control function for materiality",
    "4.8": "inventory design incl. agent attributes",
}


def main() -> None:
    banner("RQ4 - Crosswalk coverage and residual work")
    crosswalk = load_crosswalk()
    catalogue = load_catalogue()
    expectations = [p.id for p in catalogue.expectations()]
    n = len(expectations)

    per_framework = {}
    print(f"\n  coverage of {n} MAS-AIRM expectation paragraphs\n")
    print(f"  {'framework':24} {'full':>6} {'partial':>8} {'none':>6} {'full share':>11}")
    for framework in Framework:
        counts = crosswalk.coverage_counts(framework)
        per_framework[framework.value] = {
            **counts,
            "full_share": share(counts["full"], n),
            "title": framework.full_title,
            "binding_law": framework.is_binding_law,
        }
        print(
            f"  {framework.value:24} {counts['full']:6} {counts['partial']:8} "
            f"{counts['none']:6} {share(counts['full'], n):10.1%}"
        )
    union = crosswalk.union_counts()
    print(
        f"  {'UNION (all frameworks)':24} {union['full']:6} {union['partial']:8} "
        f"{union['none']:6} {share(union['full'], n):10.1%}"
    )

    # Union restricted to the three international frameworks, which is what H4(b) is about.
    international_full = 0
    international_rows = {}
    for clause in expectations:
        levels = [crosswalk.coverage_of(clause, f) for f in INTERNATIONAL]
        best = max(levels, key=lambda c: c.rank)
        international_rows[clause] = best.value
        if best is Coverage.FULL:
            international_full += 1
    international_residue = [c for c, v in international_rows.items() if v != "full"]
    print(
        f"\n  union of {', '.join(f.value for f in INTERNATIONAL)}: "
        f"{international_full}/{n} full ({share(international_full, n):.1%}), "
        f"{len(international_residue)} clauses with no full mapping"
    )

    residue = list(crosswalk.uncovered())
    print(f"\n  residue after ALL frameworks ({len(residue)} clauses)")
    for clause in residue:
        paragraph = catalogue.paragraph(clause)
        predicted = " [predicted]" if clause in PREDICTED_RESIDUE else ""
        print(f"    §{clause:5} {paragraph.heading[:44]:46}{predicted}")

    work = {
        "iso_only": residual_work([Framework.ISO_42001]),
        "iso_nist": residual_work([Framework.ISO_42001, Framework.NIST_AI_RMF]),
        "international": residual_work(INTERNATIONAL),
        "all": residual_work(list(Framework)),
    }
    print("\n  residual work for an institution already meeting...")
    for label, rows in work.items():
        print(
            f"    {label:14} no coverage: {len(rows['uncovered']):2}   "
            f"partial, delta remains: {len(rows['partial']):2}"
        )

    confidence = Counter(row.confidence for row in crosswalk.mappings)
    low_confidence = [
        f"{row.clause}/{row.framework.value}"
        for row in crosswalk.mappings
        if row.confidence == "low"
    ]

    predicted_hits = [c for c in PREDICTED_RESIDUE if c in set(residue)]
    verdicts = [
        verdict(
            "H4(a) no single framework fully covers more than 60% of expectations",
            all(row["full_share"] <= 0.60 for row in per_framework.values()),
            "highest single-framework full coverage is "
            + max(
                (f"{k} at {v['full_share']:.1%}" for k, v in per_framework.items()),
                key=lambda s: float(s.rsplit(" at ", 1)[1].rstrip("%")),
            ),
        ),
        verdict(
            "H4(b) the international union leaves at least 10% with no full mapping",
            share(len(international_residue), n) >= 0.10,
            f"{len(international_residue)}/{n} = {share(len(international_residue), n):.1%} of "
            f"expectations have no full mapping in ISO 42001, NIST AI RMF or the EU AI Act",
        ),
        verdict(
            "H4(c) the residue is concentrated in the predicted clauses",
            len(predicted_hits) >= len(residue) / 2,
            f"{len(predicted_hits)} of {len(residue)} residual clauses were predicted: "
            f"{', '.join('§' + c for c in predicted_hits)}. Not predicted: "
            f"{', '.join('§' + c for c in residue if c not in PREDICTED_RESIDUE)}",
        ),
    ]

    # Figure: horizontal stacked bars, one per framework plus the union.
    fig, ax = new_figure(7.6, 4.4)
    labels = [*[f.value for f in Framework], "UNION"]
    data = [*[per_framework[f.value] for f in Framework], union]
    y = range(len(labels))
    lefts = [0.0] * len(labels)
    for level in ("full", "partial", "none"):
        values = [row[level] for row in data]
        ax.barh(
            list(y),
            values,
            left=lefts,
            color=COVERAGE_COLOURS[level],
            label=level,
            height=0.62,
            edgecolor="white",
            linewidth=0.8,
        )
        lefts = [a + b for a, b in zip(lefts, values, strict=True)]
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel(f"MAS-AIRM expectation paragraphs (of {n})", fontsize=9)
    ax.set_xlim(0, n)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color="#D9D9D9", linewidth=0.8)
    ax.set_title(
        "How much of the MAS Guidelines other frameworks already require",
        fontsize=11,
        loc="left",
        pad=12,
    )
    ax.legend(frameon=False, fontsize=8.5, ncols=3, loc="lower right")
    ax.text(
        n,
        len(labels) - 0.2,
        "mapping is interpretive; every row carries its justification",
        fontsize=7.5,
        color=NEUTRAL,
        ha="right",
    )
    figure = save_figure(
        fig,
        "rq4_crosswalk_coverage",
        caption=(
            f"Coverage of the {n} MAS-AIRM expectation paragraphs by other AI governance "
            "frameworks. full: the other framework imposes an equivalent obligation. partial: "
            "related but narrower, differently scoped or optional. none: no mapping asserted. "
            "Mapping is interpretive and asymmetric, since ISO/IEC 42001 is a management-system "
            "standard, the EU AI Act is product law and the NIST AI RMF is voluntary guidance, so "
            "a paragraph can be covered in substance and uncovered in legal effect."
        ),
    )
    print(f"\n  figure: {figure.name}")

    path = write_result(
        "rq4_crosswalk",
        {
            "question": (
                "What share of MAS-AIRM expectations is covered, partially covered or uncovered "
                "by ISO/IEC 42001, NIST AI RMF and the EU AI Act, and what residual work does an "
                "already-certified institution face?"
            ),
            "method": (
                f"{len(crosswalk)} hand-authored mapping rows over {n} expectation paragraphs. "
                "The denominator is the expectation count, not the mapped-row count, so an "
                "unmapped expectation counts against coverage rather than being excluded."
            ),
            "expectations": n,
            "per_framework": per_framework,
            "union_all": union,
            "union_international": {
                "frameworks": [f.value for f in INTERNATIONAL],
                "full": international_full,
                "full_share": share(international_full, n),
                "residue": international_residue,
                "per_clause": international_rows,
            },
            "residue_all_frameworks": {
                clause: {
                    "heading": catalogue.paragraph(clause).heading,
                    "summary": catalogue.paragraph(clause).summary,
                    "predicted": clause in PREDICTED_RESIDUE,
                    "best_coverage": crosswalk.best_coverage(clause)[0].value,
                }
                for clause in residue
            },
            "residual_work": {
                label: {k: list(v) for k, v in rows.items()} for label, rows in work.items()
            },
            "mapping_confidence": dict(confidence),
            "low_confidence_rows": low_confidence,
            "verdicts": verdicts,
            "threats_to_validity": [
                "Mapping is interpretive and performed by one annotator. Every row carries a "
                "justification, a confidence flag and a gap note so it can be disputed "
                "individually rather than only in aggregate.",
                "The comparison is asymmetric by nature: ISO 42001 certifies a management system, "
                "the EU AI Act regulates products through conformity assessment, and the NIST AI "
                "RMF is voluntary. 'Full' coverage means an equivalent obligation exists, not "
                "that holding one discharges the other.",
                "EU AI Act obligations attach to a system's risk classification, so a mapping may "
                "be full for an Annex III high-risk use and irrelevant for everything else.",
                f"{confidence.get('low', 0)} rows are flagged low confidence and are the first "
                "place a reader should look to disagree.",
                "The MAS Information Paper predates the Guidelines and reports observed practice "
                "rather than imposing expectations, so its high 'full' count says the Guidelines "
                "codified existing practice, not that an institution can rely on it.",
            ],
            "figures": [figure.name],
        },
    )
    print(f"  result: {path.name}")


if __name__ == "__main__":
    main()
