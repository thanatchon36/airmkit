"""Merge the five per-RQ result files and the worked example into results/summary.json.

MISSION Phase 5 requires every number in the paper to be injected from one file, with nothing
hand-typed. This script produces that file. It computes nothing of its own: each figure is read
from the per-RQ result file that measured it, or from ``AuditPack.summary_json()`` for the
portfolio-level counts, and only formatting (percentages, counts) happens here.

``summary["numbers"]`` is the flat, dotted-key map the paper template substitutes from. Keys there
are print-ready: shares are rendered as percentage strings exactly once, in :func:`pct`, so the
same share cannot appear with two roundings in two sections.

Run with ``PYTHONPATH=experiments .venv/bin/python experiments/collect.py`` (or ``make paper``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _common import EXAMPLE, FIGURES, RESULTS, banner, git_revision, provenance

SUMMARY = RESULTS / "summary.json"

# Logical name to result file stem. The stems name the scripts that produce them, which is what
# the FileNotFoundError below tells the reader to run.
RQ_SOURCES = {
    "rq1": "rq1_automatability",
    "rq2": "rq2_autonomy",
    "rq3": "rq3_guardrails",
    "rq4": "rq4_crosswalk",
    "rq5": "rq5_cost",
}


def pct(share: float, places: int = 1) -> str:
    """Render a 0-1 share as a percentage string.

    Every percentage in the paper passes through here, so a share cannot be rounded one way in
    the abstract and another way in the results section.
    """
    return f"{share * 100:.{places}f}%"


def load_rq_results(results_dir: Path | str = RESULTS) -> dict[str, dict[str, Any]]:
    """Read the five per-RQ result files.

    Args:
        results_dir: Directory holding ``rqN_*.json``.

    Returns:
        Logical RQ name to the parsed result file.

    Raises:
        FileNotFoundError: Naming the experiment script that produces the missing file.
    """
    directory = Path(results_dir)
    out: dict[str, dict[str, Any]] = {}
    for key, stem in RQ_SOURCES.items():
        path = directory / f"{stem}.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"{path} not found; run `python experiments/{stem}.py` first "
                "(or `make experiments`)"
            )
        out[key] = json.loads(path.read_text(encoding="utf-8"))
    return out


def example_pack_summary() -> dict[str, Any]:
    """Return ``AuditPack.summary_json()`` for the shipped synthetic bank portfolio.

    This is the same object ``airm report`` writes beside the pack, so the paper's portfolio
    counts are the counts a reader gets by running the worked example.
    """
    from airm.controls import load_controls
    from airm.inventory import Register
    from airm.materiality import load_rubric
    from airm.monitor import AuditTrail
    from airm.report import AuditPack
    from airm.thirdparty import VendorRegister

    register = Register.load(EXAMPLE / "ai-inventory.yaml")
    vendors = VendorRegister.load(EXAMPLE / "third-party-assessments.yaml")
    trail = AuditTrail(EXAMPLE / "evidence" / "trail.jsonl")

    evidence = {entry.id: trail.evidence_map(entry.id) for entry in register.use_cases}
    institution_evidence: dict[str, str] = {}
    for record in trail.records():
        if record.use_case_id is None:
            for item in record.evidence:
                institution_evidence[item.item] = item.ref

    pack = AuditPack(
        register,
        rubric=load_rubric(None),
        controls=load_controls(None),
        vendors=vendors,
        evidence=evidence,
        institution_evidence=institution_evidence,
    )
    return pack.summary_json()


def verdict_table(rqs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten every pre-registered verdict into one table, tagged with its RQ.

    Refuted hypotheses are kept exactly as recorded. The thresholds were fixed in
    docs/RESEARCH_QUESTIONS.md before the experiments ran, so this table is the honest record of
    what survived and nothing is filtered here.
    """
    return [
        {
            "rq": key,
            "hypothesis": row["hypothesis"],
            "holds": bool(row["holds"]),
            "detail": row["detail"],
        }
        for key, payload in rqs.items()
        for row in payload["verdicts"]
    ]


def figures(rqs: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    """Return each figure with the caption its experiment wrote beside the PNG."""
    out: list[dict[str, str]] = []
    for key, payload in rqs.items():
        for name in payload.get("figures", []):
            caption_path = FIGURES / f"{Path(name).stem}.txt"
            caption = (
                caption_path.read_text(encoding="utf-8").strip() if caption_path.is_file() else ""
            )
            out.append({"rq": key, "file": name, "caption": caption})
    return out


def threats_to_validity(rqs: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Return the per-RQ threats, unedited.

    The paper's Threats to Validity section is assembled from these, so a threat recorded during
    an experiment cannot be quietly dropped when the prose is written.
    """
    return {key: list(payload["threats_to_validity"]) for key, payload in rqs.items()}


def disclosures(rqs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Return the caveats that must appear in the paper verbatim.

    Two are measurement defects found during RQ3 and one is a post-hoc change to the RQ2 autonomy
    ladder. All three were found after pre-registration, so the paper reports them rather than
    presenting the corrected numbers as if they had always been the plan.
    """
    rq3 = rqs["rq3"]
    backend = rq3["backend"]
    return {
        "rq2_post_hoc_ladder_change": rqs["rq2"]["post_hoc_disclosure"],
        "rq3_detector_calibration": rq3["detector_calibration"],
        "rq3_backend": (
            f"{backend['backend']} {backend['model']} at temperature {backend['temperature']}, "
            f"seed {backend['seed']}, num_predict {backend['num_predict']}, "
            f"think={backend['think']}"
        ),
        "rq3_is_mock": bool(rq3["is_mock"]),
        "rq3_joint_criterion": rq3["joint_criterion"]["note"],
        "rq5_estimates": rqs["rq5"]["estimates"]["note"],
        "rq4_mapping_confidence": (
            f"{rqs['rq4']['mapping_confidence'].get('low', 0)} of "
            f"{sum(rqs['rq4']['mapping_confidence'].values())} crosswalk rows are low confidence "
            "and are listed individually in results/rq4_crosswalk.json"
        ),
    }


def _outcome_totals(portfolio: dict[str, Any]) -> dict[str, int]:
    """Sum control outcomes across the portfolio and the institution-level controls."""
    totals: dict[str, int] = {}
    per_use_case = [row["counts"] for row in portfolio["results"].values()]
    for counts in [*per_use_case, portfolio["institution_controls"]["counts"]]:
        for outcome, value in counts.items():
            totals[outcome] = totals.get(outcome, 0) + value
    return totals


def headline_numbers(
    rqs: dict[str, dict[str, Any]], portfolio: dict[str, Any]
) -> dict[str, str | int | float]:
    """Return the flat, print-ready map the paper substitutes from.

    Keys are dotted and stable: ``paper/paper.md.in`` references them by name, and the renderer
    fails loudly on an unknown key, so a renamed key cannot silently leave a gap in the prose.
    """
    rq1, rq2, rq3, rq4, rq5 = (rqs[k] for k in ("rq1", "rq2", "rq3", "rq4", "rq5"))
    paragraphs = rq1["paragraph_totals"]
    controls = rq1["control_totals"]
    sections = rq1["by_section"]
    results3 = rq3["results"]
    best_single = max(rq4["per_framework"].items(), key=lambda kv: kv[1]["full_share"])
    union_intl = rq4["union_international"]
    totals5 = rq5["totals"]
    by_tier = rq5["by_tier"]
    outcomes = _outcome_totals(portfolio)
    verdicts = verdict_table(rqs)

    numbers: dict[str, str | int | float] = {
        # catalogue and library
        "catalogue.paragraphs": portfolio["catalogue"]["paragraphs"],
        "catalogue.expectations": portfolio["catalogue"]["expectations"],
        "catalogue.footnotes": portfolio["catalogue"]["footnotes"],
        "catalogue.normative_footnotes": portfolio["catalogue"]["normative_footnotes"],
        "controls.total": portfolio["controls"]["total"],
        "controls.use_case_scope": portfolio["controls"]["use_case_scope"],
        "controls.institution_scope": portfolio["controls"]["institution_scope"],
        "controls.covered_paragraphs": portfolio["controls"]["covered_paragraphs"],
        "controls.uncovered_expectations": ", ".join(
            f"§{clause}" for clause in portfolio["controls"]["uncovered_expectations"]
        )
        or "none",
        "controls.families": portfolio["controls"]["families"],
        # portfolio
        "portfolio.institution": portfolio["institution"],
        "portfolio.use_cases": portfolio["portfolio"]["use_cases"],
        "portfolio.live": portfolio["portfolio"]["live"],
        "portfolio.agentic": portfolio["portfolio"]["agentic"],
        "portfolio.high_materiality": len(portfolio["portfolio"]["high_materiality"]),
        "portfolio.pass": outcomes.get("pass", 0),
        "portfolio.fail": outcomes.get("fail", 0),
        "portfolio.needs_attestation": outcomes.get("needs_attestation", 0),
        "portfolio.not_applicable": outcomes.get("not_applicable", 0),
        # RQ1
        "rq1.expectations": paragraphs["n"],
        "rq1.auto_count": paragraphs["counts"]["auto"],
        "rq1.semi_count": paragraphs["counts"]["semi"],
        "rq1.doc_count": paragraphs["counts"]["doc"],
        "rq1.auto_share": pct(paragraphs["shares"]["auto"]),
        "rq1.semi_share": pct(paragraphs["shares"]["semi"]),
        "rq1.doc_share": pct(paragraphs["shares"]["doc"]),
        "rq1.controls": controls["n"],
        "rq1.controls_auto": controls["counts"]["auto"],
        "rq1.controls_semi": controls["counts"]["semi"],
        "rq1.controls_doc": controls["counts"]["doc"],
        "rq1.controls_auto_share": pct(controls["shares"]["auto"]),
        "rq1.controls_semi_share": pct(controls["shares"]["semi"]),
        "rq1.controls_doc_share": pct(controls["shares"]["doc"]),
        "rq1.section4_auto_share": pct(sections["4"]["auto"]),
        "rq1.section3_auto_share": pct(sections["3"]["auto"]),
        "rq1.section5_auto_share": pct(sections["5"]["auto"]),
        "rq1.uncovered_expectations": ", ".join(f"§{c}" for c in rq1["uncovered_expectations"])
        or "none",
        # RQ2
        "rq2.ladder_steps": len(rq2["ladder"]),
        "rq2.ladder": " -> ".join(rq2["ladder"]),
        "rq2.subjects": len(rq2["subjects"]),
        "rq2.monotone_count": sum(1 for ok in rq2["monotone"].values() if ok),
        "rq2.kendall_tau": max(rq2["kendall_tau"].values()),
        "rq2.tier_gains": sum(rq2["tier_gain_at_agent_step"].values()),
        "rq2.saturated_count": sum(1 for ok in rq2["tier_saturation"].values() if ok),
        "rq2.agent_step_controls": len(rq2["controls_first_binding_at_autonomous_agent"]),
        "rq2.largest_step": sorted(set(rq2["largest_step"].values()))[0],
        # RQ3
        "rq3.model": rq3["backend"]["model"],
        "rq3.probes": rq3["probe_count"],
        "rq3.patterns": len(rq3["patterns"]),
        "rq3.trials_per_pattern": results3["none"]["trials"],
        "rq3.benign_trials": results3["none"]["over_refusal_trials"],
        "rq3.asr_none": pct(results3["none"]["overall_asr"]),
        "rq3.asr_system_prompt": pct(results3["system_prompt"]["overall_asr"]),
        "rq3.asr_filter": pct(results3["filter"]["overall_asr"]),
        "rq3.asr_llm_judge": pct(results3["llm_judge"]["overall_asr"]),
        "rq3.asr_layered": pct(results3["layered"]["overall_asr"]),
        "rq3.asr_layered_ci": (
            f"[{pct(results3['layered']['ci_lower'])}, {pct(results3['layered']['ci_upper'])}]"
        ),
        "rq3.asr_filter_ci": (
            f"[{pct(results3['filter']['ci_lower'])}, {pct(results3['filter']['ci_upper'])}]"
        ),
        "rq3.over_refusal_none": pct(results3["none"]["over_refusal"]),
        "rq3.over_refusal_system_prompt": pct(results3["system_prompt"]["over_refusal"]),
        "rq3.over_refusal_filter": pct(results3["filter"]["over_refusal"]),
        "rq3.over_refusal_llm_judge": pct(results3["llm_judge"]["over_refusal"]),
        "rq3.over_refusal_layered": pct(results3["layered"]["over_refusal"]),
        "rq3.patterns_meeting_both": len(rq3["joint_criterion"]["patterns_meeting_both"]),
        "rq3.threshold_high": pct(rq3["proposed_thresholds"]["asr_by_tier"]["High"]),
        "rq3.threshold_over_refusal": pct(rq3["proposed_thresholds"]["max_over_refusal"]),
        # RQ4
        "rq4.expectations": rq4["expectations"],
        "rq4.frameworks": len(rq4["per_framework"]),
        "rq4.best_single_framework": best_single[1]["title"],
        "rq4.best_single_framework_share": pct(best_single[1]["full_share"]),
        "rq4.iso_share": pct(rq4["per_framework"]["iso_42001"]["full_share"]),
        "rq4.nist_share": pct(rq4["per_framework"]["nist_ai_rmf"]["full_share"]),
        "rq4.genai_profile_share": pct(rq4["per_framework"]["nist_genai_profile"]["full_share"]),
        "rq4.eu_share": pct(rq4["per_framework"]["eu_ai_act"]["full_share"]),
        "rq4.union_full": union_intl["full"],
        "rq4.union_full_share": pct(union_intl["full_share"]),
        "rq4.union_residue": len(union_intl["residue"]),
        "rq4.union_residue_share": pct(
            len(union_intl["residue"]) / rq4["expectations"] if rq4["expectations"] else 0.0
        ),
        "rq4.residue_all_frameworks": ", ".join(f"§{c}" for c in rq4["residue_all_frameworks"]),
        "rq4.mapping_rows": sum(rq4["mapping_confidence"].values()),
        "rq4.low_confidence_rows": rq4["mapping_confidence"].get("low", 0),
        # RQ5
        "rq5.first_time_hours": totals5["first_time_hours"],
        "rq5.recurring_hours_per_year": totals5["recurring_hours_per_year"],
        "rq5.semi_doc_effort_share": pct(
            totals5["effort_share_by_class"]["semi"] + totals5["effort_share_by_class"]["doc"]
        ),
        "rq5.auto_effort_share": pct(totals5["effort_share_by_class"]["auto"]),
        "rq5.largest_category": max(
            totals5["effort_share_by_category"],
            key=lambda k: totals5["effort_share_by_category"][k],
        ),
        "rq5.largest_category_share": pct(max(totals5["effort_share_by_category"].values())),
        "rq5.gini": totals5["gini_across_use_cases"],
        "rq5.critical_evidence_items": by_tier["Critical"]["mean_evidence_items"],
        "rq5.medium_evidence_items": by_tier["Medium"]["mean_evidence_items"],
        "rq5.critical_hours": by_tier["Critical"]["mean_first_time_hours"],
        "rq5.medium_hours": by_tier["Medium"]["mean_first_time_hours"],
        "rq5.institution_hours": rq5["institution_level"]["first_time_hours"],
        "rq5.low_tier_use_cases": by_tier["Low"]["use_cases"],
        # verdicts
        "verdicts.total": len(verdicts),
        "verdicts.held": sum(1 for row in verdicts if row["holds"]),
        "verdicts.refuted": sum(1 for row in verdicts if not row["holds"]),
    }
    for tier, count in portfolio["portfolio"]["tier_counts"].items():
        numbers[f"portfolio.tier_{tier.lower()}"] = count
    return numbers


def collate(rqs: dict[str, dict[str, Any]], portfolio: dict[str, Any]) -> dict[str, Any]:
    """Merge the per-RQ results and the portfolio summary into one object."""
    verdicts = verdict_table(rqs)
    held = sum(1 for row in verdicts if row["holds"])
    merge_provenance = {
        **provenance(),
        "git_revision": git_revision(),
        "merged_from": {key: payload["provenance"]["generated_at"] for key, payload in rqs.items()},
        "portfolio_generated_by": portfolio["generated_by"],
    }
    return {
        "provenance": merge_provenance,
        "catalogue": portfolio["catalogue"],
        "controls": portfolio["controls"],
        "portfolio": {
            "institution": portfolio["institution"],
            **portfolio["portfolio"],
            "outcomes": _outcome_totals(portfolio),
            "institution_control_failures": portfolio["institution_controls"]["failures"],
        },
        "questions": {key: payload["question"] for key, payload in rqs.items()},
        "methods": {key: payload["method"] for key, payload in rqs.items()},
        "verdicts": verdicts,
        "verdict_counts": {
            "total": len(verdicts),
            "held": held,
            "refuted": len(verdicts) - held,
        },
        "numbers": headline_numbers(rqs, portfolio),
        "figures": figures(rqs),
        "threats_to_validity": threats_to_validity(rqs),
        "disclosures": disclosures(rqs),
        "rq": rqs,
        "disclaimer": portfolio["disclaimer"],
    }


def _without_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the payload without its own provenance block.

    The provenance carries a timestamp, so two merges of identical results differ. Comparing
    without it is how :func:`main` decides whether anything actually changed.
    """
    return {key: value for key, value in payload.items() if key != "provenance"}


def main() -> None:
    """Write results/summary.json from the per-RQ files and the worked example.

    If nothing but the timestamp changed, the committed provenance block is kept, so that
    ``summary.json`` is a stable artefact: CI can fail a build whose generated files are stale
    without failing every build for the date.
    """
    banner("collect: merging per-RQ results into summary.json")
    rqs = load_rq_results()
    portfolio = example_pack_summary()
    summary = collate(rqs, portfolio)
    if SUMMARY.is_file():
        existing = json.loads(SUMMARY.read_text(encoding="utf-8"))
        if _without_provenance(existing) == _without_provenance(summary):
            summary["provenance"] = existing["provenance"]
            print("  no change beyond the timestamp; keeping the committed provenance block")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    counts = summary["verdict_counts"]
    print(f"  merged {len(rqs)} result files and the {portfolio['institution']} portfolio")
    print(f"  {len(summary['numbers'])} headline numbers, {len(summary['figures'])} figures")
    print(f"  verdicts: {counts['held']} held, {counts['refuted']} refuted of {counts['total']}")
    print(f"  result: {SUMMARY}")


if __name__ == "__main__":
    main()
