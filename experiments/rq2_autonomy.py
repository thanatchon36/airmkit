"""RQ2: how does autonomy change risk materiality and the set of binding controls?

Holding purpose, data and model family fixed, each selected use case is rewritten at five autonomy
levels and re-scored. Tests the thresholds fixed in docs/RESEARCH_QUESTIONS.md:

  H2(a)  the applicable control count is monotone non-decreasing across autonomy levels;
  H2(b)  at least 3 of 4 use cases gain a tier at the human-in-the-loop -> autonomous step;
  H2(c)  the largest jump in applicable controls is at that step.

The ladder is assistive -> human-in-the-loop -> human-over-the-loop -> autonomous decisioning ->
autonomous agent -> multi-agent. Only the autonomy field and the minimum agent scaffolding needed
to make an agentic variant valid are changed; everything else is held constant, so the deltas are
attributable to autonomy alone.
"""

from __future__ import annotations

from typing import Any

from _common import TIER_COLOURS, banner, new_figure, save_figure, verdict, write_result

from airm.controls import Scope, filter_by_use_case, load_controls
from airm.inventory import AgentExtension, AutonomyLevel, Guardrail, Register, UseCase
from airm.materiality import Dimension, Rubric, Tier, assess, load_rubric

LADDER = [
    AutonomyLevel.ASSISTIVE,
    AutonomyLevel.HUMAN_IN_THE_LOOP,
    AutonomyLevel.HUMAN_OVER_THE_LOOP,
    AutonomyLevel.AUTONOMOUS_DECISIONING,
    AutonomyLevel.AUTONOMOUS_AGENT,
    AutonomyLevel.MULTI_AGENT,
]
STEP_OF_INTEREST = (AutonomyLevel.HUMAN_IN_THE_LOOP, AutonomyLevel.AUTONOMOUS_AGENT)
SUBJECTS = [
    "credit-decision-model",
    "aml-alert-triage",
    "customer-service-chatbot",
    "policy-rag-assistant",
]


def variant(base: UseCase, level: AutonomyLevel) -> UseCase:
    """Return the use case rewritten at one autonomy level, changing nothing else.

    An agentic variant needs an agent extension to be a valid inventory entry at all (MAS-AIRM
    §4.8 fn25). The scaffolding is deliberately minimal and identical across subjects, so it adds
    a constant rather than a per-subject effect: one approved tool, one component, one tested
    guardrail, and no external action capability.
    """
    agent = None
    if level.is_agentic:
        agent = AgentExtension(
            agent_identifier=f"AGT-{base.id[:12].upper()}",
            approved_tools=["lookup"],
            systems_accessible=["system_of_record"],
            permissions=["read:records"],
            components=(
                ["planner"]
                if level is AutonomyLevel.AUTONOMOUS_AGENT
                else ["planner", "critic", "writer"]
            ),
            guardrails=[
                Guardrail(
                    name="tool allowlist",
                    kind="tool_allowlist",
                    tested=True,
                    evidence_ref="EV-RQ2",
                )
            ],
            human_checkpoints=[],
            max_steps=20,
            can_initiate_external_actions=False,
            trace_logging=False,
        )
    # Rebuilt in one construction: the model validates agent/autonomy consistency on every
    # assignment, so mutating the two fields in sequence would always pass through an invalid state.
    fields = base.model_dump()
    fields["autonomy"] = level
    fields["agent"] = agent.model_dump() if agent is not None else None
    return UseCase.model_validate(fields)


def ladder_for(base: UseCase, rubric: Rubric) -> list[dict[str, Any]]:
    """Score one use case at every autonomy level."""
    controls = load_controls()
    rows: list[dict[str, Any]] = []
    previous: set[str] = set()
    for level in LADDER:
        candidate = variant(base, level)
        assessment = rubric.assess(candidate)
        applicable = {
            c.id for c in filter_by_use_case(candidate, assessment=assessment, catalogue=controls)
        }
        rows.append(
            {
                "autonomy": level.value,
                "rank": level.rank,
                "impact": assessment.level(Dimension.IMPACT).value,
                "complexity": assessment.level(Dimension.COMPLEXITY).value,
                "reliance": assessment.level(Dimension.RELIANCE).value,
                "inherent": assessment.inherent_tier.value,
                "residual": assessment.residual_tier.value,
                "applicable": len(applicable),
                "newly_binding": sorted(applicable - previous),
                "no_longer_binding": sorted(previous - applicable),
            }
        )
        previous = applicable
    return rows


def kendall_tau(xs: list[int], ys: list[int]) -> float:
    """Return Kendall's tau-b between two small sequences.

    Written out rather than imported so the experiment has no scipy dependency: the sequences are
    six elements long and the formula is three lines.
    """
    concordant = discordant = tied_x = tied_y = 0
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            product = dx * dy
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
            else:
                if dx == 0:
                    tied_x += 1
                if dy == 0:
                    tied_y += 1
    n0 = len(xs) * (len(xs) - 1) / 2
    denominator = ((n0 - tied_x) * (n0 - tied_y)) ** 0.5
    return round((concordant - discordant) / denominator, 4) if denominator else 0.0


def main() -> None:
    banner("RQ2 - Autonomy, materiality and the set of binding controls")
    register = Register.load(
        __import__("_common", fromlist=["EXAMPLE"]).EXAMPLE / "ai-inventory.yaml"
    )
    rubric = load_rubric()
    sensitivity_rubric = rubric.model_copy(deep=True)
    sensitivity_rubric.combination = "weighted"

    ladders = {uc_id: ladder_for(register.get(uc_id), rubric) for uc_id in SUBJECTS}
    sensitivity = {uc_id: ladder_for(register.get(uc_id), sensitivity_rubric) for uc_id in SUBJECTS}

    print(f"\n  {len(SUBJECTS)} use cases x {len(LADDER)} autonomy levels\n")
    header = f"  {'use case':26} " + " ".join(f"{level.value[:11]:>12}" for level in LADDER)
    print(header)
    for uc_id, rows in ladders.items():
        cells = " ".join(f"{r['inherent'][:4]:>5}/{r['applicable']:<6}" for r in rows)
        print(f"  {uc_id:26} {cells}")
    print("\n  (inherent tier / count of applicable controls)")

    monotone = {}
    tier_gain = {}
    biggest_step = {}
    taus = {}
    for uc_id, rows in ladders.items():
        counts = [int(r["applicable"]) for r in rows]
        monotone[uc_id] = all(b >= a for a, b in zip(counts, counts[1:], strict=False))
        taus[uc_id] = kendall_tau([int(r["rank"]) for r in rows], counts)
        by_level = {r["autonomy"]: r for r in rows}
        before = by_level[STEP_OF_INTEREST[0].value]
        after = by_level[STEP_OF_INTEREST[1].value]
        tier_gain[uc_id] = Tier(after["inherent"]).rank - Tier(before["inherent"]).rank
        deltas = {
            f"{a['autonomy']}->{b['autonomy']}": int(b["applicable"]) - int(a["applicable"])
            for a, b in zip(rows, rows[1:], strict=False)
        }
        biggest_step[uc_id] = max(deltas, key=lambda k: deltas[k])

    newly_binding_at_agent = sorted(
        {
            control
            for rows in ladders.values()
            for row in rows
            if row["autonomy"] == AutonomyLevel.AUTONOMOUS_AGENT.value
            for control in row["newly_binding"]
        }
    )
    print(f"\n  controls that first bind at autonomous_agent: {len(newly_binding_at_agent)}")
    for control in newly_binding_at_agent:
        clauses = ", ".join(load_controls().get(control).citations)
        print(f"    {control:36} {clauses}")

    target_step = f"{STEP_OF_INTEREST[0].value}->{STEP_OF_INTEREST[1].value}"
    agentic_boundary = (
        f"{AutonomyLevel.AUTONOMOUS_DECISIONING.value}->{AutonomyLevel.AUTONOMOUS_AGENT.value}"
    )
    ceiling = {uc_id: rows[1]["inherent"] == Tier.CRITICAL.value for uc_id, rows in ladders.items()}
    verdicts = [
        verdict(
            "H2(a) applicable control count is monotone non-decreasing in autonomy",
            all(monotone.values()),
            f"monotone for {sum(monotone.values())}/{len(monotone)} use cases; "
            f"Kendall tau = {taus}",
        ),
        verdict(
            "H2(b) at least 3 of 4 gain a tier from human-in-the-loop to autonomous agent",
            sum(1 for gain in tier_gain.values() if gain >= 1) >= 3,
            f"tier gains {tier_gain}",
        ),
        verdict(
            "H2(c) the largest control delta is at the human-in-the-loop to agent step",
            sum(1 for step in biggest_step.values() if step == target_step) >= 3,
            f"largest step per use case: {biggest_step}",
        ),
        verdict(
            "H2(c-revised) the largest control delta is at the agentic boundary",
            sum(1 for step in biggest_step.values() if step == agentic_boundary) >= 3,
            f"the autonomous_decisioning to autonomous_agent step is largest for "
            f"{sum(1 for s in biggest_step.values() if s == agentic_boundary)}/"
            f"{len(biggest_step)} use cases; not pre-registered, see post_hoc_disclosure",
        ),
    ]

    # Why H2(b) failed, per use case. Not a pre-registered hypothesis, so it is recorded as a
    # diagnosis rather than given a pass/fail verdict: inventing a threshold after seeing the
    # data is exactly what pre-registration is meant to prevent.
    diagnosis: dict[str, str] = {}
    for uc_id, rows in ladders.items():
        at_hitl = next(r for r in rows if r["autonomy"] == AutonomyLevel.HUMAN_IN_THE_LOOP.value)
        at_agent = next(r for r in rows if r["autonomy"] == AutonomyLevel.AUTONOMOUS_AGENT.value)
        if tier_gain[uc_id] >= 1:
            diagnosis[uc_id] = f"gained a tier ({at_hitl['inherent']} to {at_agent['inherent']})"
        elif at_hitl["inherent"] == Tier.CRITICAL.value:
            diagnosis[uc_id] = (
                "already Critical at human-in-the-loop, so the tier scale has no headroom; "
                "the applicable control count still rose"
            )
        else:
            diagnosis[uc_id] = (
                f"held at {at_hitl['inherent']} by the impact gate: Impact is "
                f"{at_agent['impact']} and the default rubric lets Complexity and Reliance raise "
                f"the tier at most one level above Impact (Response to Feedback 7.9)"
            )
    print("\n  why the tier did or did not move at the agentic step")
    for uc_id, reason in diagnosis.items():
        print(f"    {uc_id:26} {reason}")

    # Figure: control count against autonomy, one line per use case, tier shown by marker colour.
    fig, ax = new_figure(7.4, 4.2)
    for uc_id, rows in ladders.items():
        xs = [int(r["rank"]) for r in rows]
        ys = [int(r["applicable"]) for r in rows]
        ax.plot(xs, ys, color="#BFBFBF", linewidth=1.4, zorder=1)
        ax.scatter(
            xs,
            ys,
            c=[TIER_COLOURS[str(r["inherent"])] for r in rows],
            s=58,
            zorder=2,
            edgecolor="white",
            linewidth=1.0,
        )
        ax.annotate(
            uc_id,
            (xs[-1], ys[-1]),
            textcoords="offset points",
            xytext=(8, -3),
            fontsize=8,
            color="#4C4C4C",
        )
    ax.set_xticks([level.rank for level in LADDER])
    ax.set_xticklabels([level.value.replace("_", "\n") for level in LADDER], fontsize=8)
    ax.set_ylabel("applicable controls", fontsize=9)
    ax.set_xlim(-0.4, len(LADDER) - 0.2 + 1.6)
    ax.set_title(
        "Autonomy raises the number of binding controls; colour shows the inherent tier",
        fontsize=11,
        loc="left",
        pad=12,
    )
    handles = [
        ax.scatter([], [], c=colour, s=58, label=tier, edgecolor="white", linewidth=1.0)
        for tier, colour in TIER_COLOURS.items()
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, ncols=4, loc="upper left")
    figure = save_figure(
        fig,
        "rq2_autonomy_controls",
        caption=(
            "Applicable MAS-AIRM controls as a use case moves up the autonomy ladder, holding "
            "purpose, data and model family fixed. Marker colour is the inherent risk materiality "
            "tier under the toolkit's default rubric. Tiering and the rubric are the authors' "
            "proposal: MAS prescribes no formula (Response to Feedback §7.19)."
        ),
    )
    print(f"\n  figure: {figure.name}")

    path = write_result(
        "rq2_autonomy",
        {
            "question": (
                "Holding purpose and data fixed, how does autonomy change Impact/Complexity/"
                "Reliance and which Section 5 controls become binding?"
            ),
            "method": (
                "Each of 4 portfolio use cases is rewritten at 6 autonomy levels; only the "
                "autonomy field and the minimal agent scaffolding needed for validity change. "
                "Applicable controls are those the catalogue selects for the variant."
            ),
            "ladder": [level.value for level in LADDER],
            "subjects": SUBJECTS,
            "ladders": ladders,
            "sensitivity_weighted_rubric": sensitivity,
            "monotone": monotone,
            "kendall_tau": taus,
            "tier_gain_at_agent_step": tier_gain,
            "largest_step": biggest_step,
            "controls_first_binding_at_autonomous_agent": {
                control: load_controls().get(control).citations
                for control in newly_binding_at_agent
            },
            "verdicts": verdicts,
            "post_hoc_disclosure": (
                "docs/RESEARCH_QUESTIONS.md pre-registered the ladder as assistive, "
                "human-in-the-loop, autonomous agent, multi-agent, and framed H2(b) and H2(c) on "
                "the human-in-the-loop to autonomous step. While implementing the library an "
                "AUTONOMOUS_DECISIONING level was added, distinct from AUTONOMOUS_AGENT, because "
                "a model that acts without human review of each decision (a real-time fraud "
                "block) is fully autonomous under MAS-AIRM 4.12(c) but has no tools, so the agent "
                "attributes of 4.8 fn25 do not apply to it. That change moved the step the "
                "hypotheses named. H2(b) and H2(c) are reported as refuted on their original "
                "wording. H2(c-revised) tests the same underlying claim on the revised ladder and "
                "is reported separately so a reader can see which test was pre-registered and "
                "which was not."
            ),
            "tier_saturation": ceiling,
            "tier_movement_diagnosis": diagnosis,
            "threats_to_validity": [
                "The rubric is the toolkit's proposal; MAS declines to prescribe one (Response "
                "to Feedback §7.19). The result describes this rubric's behaviour.",
                "An agentic variant needs an agent extension to be a valid entry, so part of the "
                "step at autonomous_agent is the scaffolding, not autonomy as such. The "
                "scaffolding is identical across subjects to keep it a constant.",
                "A weighted-sum rubric is run as a sensitivity check and recorded alongside.",
                "Four use cases is a small sample; the direction is the claim, not the magnitude.",
            ],
            "figures": [figure.name],
        },
    )
    print(f"  result: {path.name}")


if __name__ == "__main__":
    main()
