"""RQ5: what does compliance cost, and where is the long tail?

Counts applicable controls and required evidence items per use case and per materiality tier for
the synthetic bank portfolio, then applies a published per-item effort table to produce an
estimate. Tests the thresholds fixed in docs/RESEARCH_QUESTIONS.md:

  H5(a) Critical-tier use cases require more than twice the evidence items of Low-tier ones;
  H5(b) more than half of total effort sits in the semi and doc classes;
  H5(c) the largest single effort category is documentation and review, not evaluation and testing.

The person-hour figures are ESTIMATES, not measurements. The estimate table is in this file, is
editable, and is reported in full alongside every number derived from it. docs/FUTURE_WORK.md
records that measuring them would need a user study.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from _common import (
    CLASS_COLOURS,
    EXAMPLE,
    NEUTRAL,
    TIER_COLOURS,
    banner,
    new_figure,
    save_figure,
    share,
    verdict,
    write_result,
)

from airm.controls import Automatability, Scope, check_institution, load_controls
from airm.inventory import Register
from airm.materiality import Tier, assess_register

# Authors' estimates of first-time effort to produce one evidence item, in person-hours, by the
# automatability class of the control requiring it. A semi item costs more than an auto item
# because someone must judge whether the artefact is adequate; a doc item costs most because the
# artefact has to be written rather than exported. These are assumptions, not findings.
EFFORT_PER_ITEM = {"auto": 1.0, "semi": 3.0, "doc": 6.0}

# Tier multiplier on first-time effort: a Critical use case attracts deeper review of the same
# artefact. Also an assumption.
TIER_MULTIPLIER = {"Low": 0.6, "Medium": 0.8, "High": 1.0, "Critical": 1.3}

# Annual recurring effort as a fraction of first-time effort, reflecting monitoring, re-validation
# and change management (MAS-AIRM 5.23-5.25).
RECURRING_FRACTION = 0.35

FAMILY_GROUPS = {
    "documentation_and_review": {
        "documentation",
        "review",
        "governance",
        "inventory",
        "materiality",
        "identification",
    },
    "evaluation_and_testing": {"evaluation", "security"},
    "operational_controls": {
        "monitoring",
        "change_management",
        "contingency",
        "retirement",
        "lifecycle",
    },
    "data_and_fairness": {"data", "fairness", "transparency"},
    "people_and_third_party": {"capability", "human_oversight", "third_party", "selection"},
}


def group_of(family: str) -> str:
    """Return the effort category a control family belongs to."""
    for group, families in FAMILY_GROUPS.items():
        if family in families:
            return group
    return "other"


def gini(values: list[float]) -> float:
    """Return the Gini coefficient of a list of non-negative values.

    Used as a concentration measure: how unevenly the portfolio's effort falls across use cases.
    """
    if not values or sum(values) == 0:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    cumulative = sum((index + 1) * value for index, value in enumerate(ordered))
    return round((2 * cumulative) / (n * sum(ordered)) - (n + 1) / n, 4)


def main() -> None:
    banner("RQ5 - Cost of compliance for the synthetic portfolio")
    register = Register.load(EXAMPLE / "ai-inventory.yaml")
    controls = load_controls()
    portfolio = assess_register(register)

    per_use_case: dict[str, dict[str, Any]] = {}
    group_effort: dict[str, float] = defaultdict(float)
    class_effort: dict[str, float] = defaultdict(float)

    for use_case in register.use_cases:
        assessment = portfolio.assessments[use_case.id]
        tier = assessment.inherent_tier
        multiplier = TIER_MULTIPLIER[tier.value]
        applicable = [
            control
            for control in controls.controls
            if control.scope is Scope.USE_CASE and control.applies_to(use_case, assessment)[0]
        ]
        evidence_items = {item for control in applicable for item in control.evidence}
        class_counts = Counter(c.automatability.value for c in applicable)

        hours = 0.0
        for control in applicable:
            per_item = EFFORT_PER_ITEM[control.automatability.value]
            control_hours = per_item * len(control.evidence) * multiplier
            hours += control_hours
            group_effort[group_of(control.family)] += control_hours
            class_effort[control.automatability.value] += control_hours

        per_use_case[use_case.id] = {
            "tier": tier.value,
            "residual": assessment.residual_tier.value,
            "applicable_controls": len(applicable),
            "evidence_items": len(evidence_items),
            "evidence_item_instances": sum(len(c.evidence) for c in applicable),
            "by_class": dict(class_counts),
            "first_time_hours": round(hours, 1),
            "recurring_hours_per_year": round(hours * RECURRING_FRACTION, 1),
        }

    institution = check_institution(register)
    institution_controls = [c for c in controls.controls if c.scope is Scope.INSTITUTION]
    institution_hours = sum(
        EFFORT_PER_ITEM[c.automatability.value] * len(c.evidence) for c in institution_controls
    )
    for control in institution_controls:
        control_hours = EFFORT_PER_ITEM[control.automatability.value] * len(control.evidence)
        group_effort[group_of(control.family)] += control_hours
        class_effort[control.automatability.value] += control_hours

    print(f"\n  {'use case':26} {'tier':9} {'controls':>8} {'evidence':>9} {'hours':>8} {'/yr':>7}")
    for use_case_id, row in per_use_case.items():
        print(
            f"  {use_case_id:26} {row['tier']:9} {row['applicable_controls']:8} "
            f"{row['evidence_items']:9} {row['first_time_hours']:8.0f} "
            f"{row['recurring_hours_per_year']:7.0f}"
        )
    print(
        f"  {'(institution-level)':26} {'-':9} {len(institution_controls):8} "
        f"{len({i for c in institution_controls for i in c.evidence}):9} "
        f"{institution_hours:8.0f} {institution_hours * RECURRING_FRACTION:7.0f}"
    )

    # Per-tier aggregates.
    by_tier: dict[str, dict[str, Any]] = {}
    for tier in Tier:
        members = [r for r in per_use_case.values() if r["tier"] == tier.value]
        if not members:
            by_tier[tier.value] = {"use_cases": 0}
            continue
        by_tier[tier.value] = {
            "use_cases": len(members),
            "mean_controls": round(
                sum(r["applicable_controls"] for r in members) / len(members), 1
            ),
            "mean_evidence_items": round(
                sum(r["evidence_items"] for r in members) / len(members), 1
            ),
            "mean_first_time_hours": round(
                sum(r["first_time_hours"] for r in members) / len(members), 1
            ),
        }
    print(
        f"\n  {'tier':10} {'n':>3} {'mean controls':>14} {'mean evidence':>14} {'mean hours':>11}"
    )
    for tier_name, row in by_tier.items():
        if not row["use_cases"]:
            print(f"  {tier_name:10} {0:3} {'-':>14} {'-':>14} {'-':>11}")
            continue
        print(
            f"  {tier_name:10} {row['use_cases']:3} {row['mean_controls']:14} "
            f"{row['mean_evidence_items']:14} {row['mean_first_time_hours']:11}"
        )

    total_hours = sum(r["first_time_hours"] for r in per_use_case.values()) + institution_hours
    class_shares = {k: share(int(v), int(total_hours)) for k, v in class_effort.items()}
    group_shares = {
        k: share(int(v), int(total_hours))
        for k, v in sorted(group_effort.items(), key=lambda kv: -kv[1])
    }
    print(f"\n  total first-time effort estimate: {total_hours:.0f} person-hours")
    print(f"  recurring: {total_hours * RECURRING_FRACTION:.0f} person-hours per year")
    print("\n  effort by automatability class")
    for klass in ("auto", "semi", "doc"):
        print(f"    {klass:5} {class_effort[klass]:7.0f}h  {class_shares.get(klass, 0):6.1%}")
    print("\n  effort by category")
    for group, hours in sorted(group_effort.items(), key=lambda kv: -kv[1]):
        print(f"    {group:26} {hours:7.0f}h  {group_shares[group]:6.1%}")

    concentration = gini([r["first_time_hours"] for r in per_use_case.values()])
    print(f"\n  Gini of effort across the {len(per_use_case)} use cases: {concentration}")

    # Hypotheses. The portfolio has no Low-tier use case, so H5(a) is tested against the lowest
    # tier present and the substitution is recorded rather than passed over.
    tiers_present = [t for t in Tier if by_tier[t.value]["use_cases"]]
    lowest = tiers_present[0]
    critical_evidence = by_tier[Tier.CRITICAL.value]["mean_evidence_items"]
    lowest_evidence = by_tier[lowest.value]["mean_evidence_items"]
    ratio = round(critical_evidence / lowest_evidence, 3) if lowest_evidence else 0.0

    semi_doc_share = class_shares.get("semi", 0) + class_shares.get("doc", 0)
    top_group = next(iter(group_shares))

    verdicts = [
        verdict(
            f"H5(a) Critical requires more than twice the evidence of the lowest tier present "
            f"({lowest.value})",
            ratio > 2.0,
            f"Critical mean {critical_evidence} evidence items vs {lowest.value} mean "
            f"{lowest_evidence}; ratio {ratio}. The portfolio contains no Low-tier use case, so "
            f"{lowest.value} is substituted for Low and the hypothesis is weaker than written.",
        ),
        verdict(
            "H5(b) more than half of total effort sits in the semi and doc classes",
            semi_doc_share > 0.50,
            f"semi {class_shares.get('semi', 0):.1%} + doc {class_shares.get('doc', 0):.1%} = "
            f"{semi_doc_share:.1%}",
        ),
        verdict(
            "H5(c) documentation and review is the largest effort category",
            top_group == "documentation_and_review",
            f"largest category is {top_group} at {group_shares[top_group]:.1%}; "
            f"evaluation_and_testing is "
            f"{group_shares.get('evaluation_and_testing', 0):.1%}",
        ),
    ]

    # Figure: effort by use case, stacked by automatability class, tier shown on the label.
    fig, ax = new_figure(7.8, 4.4)
    ids = list(per_use_case)
    bottoms = [0.0] * len(ids)
    for klass in ("auto", "semi", "doc"):
        values = []
        for use_case_id in ids:
            row = per_use_case[use_case_id]
            multiplier = TIER_MULTIPLIER[row["tier"]]
            use_case = register.get(use_case_id)
            assessment = portfolio.assessments[use_case_id]
            hours = sum(
                EFFORT_PER_ITEM[klass] * len(c.evidence) * multiplier
                for c in controls.controls
                if c.scope is Scope.USE_CASE
                and c.automatability.value == klass
                and c.applies_to(use_case, assessment)[0]
            )
            values.append(hours)
        ax.bar(
            ids,
            values,
            bottom=bottoms,
            color=CLASS_COLOURS[klass],
            label=klass,
            width=0.62,
            edgecolor="white",
            linewidth=0.8,
        )
        bottoms = [a + b for a, b in zip(bottoms, values, strict=True)]
    ax.set_ylabel("estimated first-time person-hours", fontsize=9)
    ax.set_xticks(range(len(ids)))
    ax.set_xticklabels(
        [f"{i}\n{per_use_case[i]['tier']}" for i in ids], fontsize=7.5, rotation=30, ha="right"
    )
    for index, use_case_id in enumerate(ids):
        tier = per_use_case[use_case_id]["tier"]
        ax.get_xticklabels()[index].set_color(TIER_COLOURS[tier])
    ax.set_title(
        "Estimated compliance effort by use case and automatability class",
        fontsize=11,
        loc="left",
        pad=12,
    )
    ax.legend(frameon=False, fontsize=8.5, ncols=3, loc="upper right")
    ax.text(
        len(ids) - 0.5,
        -max(bottoms) * 0.33,
        "person-hours are the authors' estimates, not measurements",
        fontsize=7.5,
        color=NEUTRAL,
        ha="right",
    )
    figure = save_figure(
        fig,
        "rq5_effort_by_use_case",
        caption=(
            "Estimated first-time compliance effort for the synthetic bank portfolio, by use case "
            "and by the automatability class of the control requiring each evidence item. "
            "Person-hour figures are the authors' estimates from the table in "
            "experiments/rq5_cost.py, not measurements; the shape of the distribution is the "
            "claim, not the absolute values. Use case labels are coloured by inherent tier."
        ),
    )
    print(f"\n  figure: {figure.name}")

    path = write_result(
        "rq5_cost",
        {
            "question": (
                "How many controls, evidence items and estimated person-hours does each "
                "materiality tier require, and where is the long tail?"
            ),
            "method": (
                "Applicable controls and their evidence items are counted per use case from the "
                "control catalogue, then multiplied by a per-item effort estimate that varies "
                "with the control's automatability class and a tier multiplier. Institution-level "
                "controls are counted once."
            ),
            "estimates": {
                "effort_per_item_hours": EFFORT_PER_ITEM,
                "tier_multiplier": TIER_MULTIPLIER,
                "recurring_fraction": RECURRING_FRACTION,
                "note": (
                    "These are assumptions, not measurements. They are published so that a "
                    "reader can substitute their own and recompute. Measuring them would need a "
                    "user study; see docs/FUTURE_WORK.md."
                ),
            },
            "per_use_case": per_use_case,
            "institution_level": {
                "controls": len(institution_controls),
                "evidence_items": len({i for c in institution_controls for i in c.evidence}),
                "first_time_hours": round(institution_hours, 1),
                "outcomes": institution.counts,
            },
            "by_tier": by_tier,
            "totals": {
                "first_time_hours": round(total_hours, 1),
                "recurring_hours_per_year": round(total_hours * RECURRING_FRACTION, 1),
                "effort_by_class": {k: round(v, 1) for k, v in class_effort.items()},
                "effort_share_by_class": class_shares,
                "effort_by_category": {k: round(v, 1) for k, v in group_effort.items()},
                "effort_share_by_category": group_shares,
                "gini_across_use_cases": concentration,
            },
            "verdicts": verdicts,
            "threats_to_validity": [
                "Person-hours are not measured. They are a transparent assumption set, reported "
                "in full, and every derived number moves with them.",
                "The portfolio is synthetic and deliberately spans the tier range, so its mix is "
                "not representative of any real institution's AI estate.",
                "The portfolio contains no Low-tier use case, because under the default rubric a "
                "Generative AI use case cannot be rated Low: GenAI sets Complexity to High and "
                "the impact gate permits one level above Impact. H5(a) is therefore tested "
                "against Medium rather than Low and is weaker than written.",
                "Effort is counted per evidence item, which treats a one-line attestation and a "
                "full validation report as comparable units within a class.",
                "Reuse across use cases is ignored: a data lineage document covering one dataset "
                "serves every use case that uses it, so the portfolio total overstates marginal "
                "cost.",
            ],
            "figures": [figure.name],
        },
    )
    print(f"  result: {path.name}")


if __name__ == "__main__":
    main()
