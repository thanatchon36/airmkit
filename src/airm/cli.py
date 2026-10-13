"""Command-line interface for airmkit.

Commands: ``init``, ``scan``, ``assess``, ``check``, ``evidence``, ``report``, ``gap``,
``crosswalk``, ``clauses`` and ``schemas``.

Serves the MAS-AIRM expectations by giving each of them a command a model-risk engineer can run in
CI. Every command prints the paragraph behind what it says, because a tool that asserts a
compliance position without a citation is worse than no tool.

Exit codes are meaningful so the commands can gate a pipeline:

* ``0`` nothing adverse found;
* ``1`` at least one automated control check failed (MAS-AIRM §5.2 proportionate controls not met);
* ``2`` a usage or input error.

``needs_attestation`` does not fail the build: by construction it is a question for a person, and
a pipeline that failed on it would teach people to suppress it.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from airm import DISCLAIMER, __version__
from airm.catalog import load_catalogue
from airm.controls import (
    Automatability,
    Outcome,
    Scope,
    check_institution,
    check_register,
    check_use_case,
    load_controls,
)
from airm.crosswalk import Coverage, Framework, coverage_summary, load_crosswalk, residual_work
from airm.inventory import (
    AutonomyLevel,
    Dependency,
    Guardrail,
    LifecycleStatus,
    Register,
    ReviewStatus,
    Role,
    ThirdPartyComponent,
    UseCase,
)
from airm.materiality import Dimension, Tier, assess_register, load_rubric
from airm.monitor import AuditTrail, EventType, Severity, new_evidence
from airm.report import AuditPack, clause_index_markdown
from airm.scan import scan_path, to_use_cases

app = typer.Typer(
    name="airm",
    help=(
        "Operationalise the MAS Guidelines on AI Risk Management (7 October 2026) for LLM and "
        "agentic AI systems. Independent project, not affiliated with MAS; not legal or "
        "regulatory advice."
    ),
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err = Console(stderr=True)

_DEFAULT_REGISTER = "ai-inventory.yaml"
_EXIT_FAIL = 1
_EXIT_USAGE = 2

_TIER_STYLE = {
    Tier.LOW: "green",
    Tier.MEDIUM: "yellow",
    Tier.HIGH: "dark_orange",
    Tier.CRITICAL: "red",
}
_OUTCOME_STYLE = {
    Outcome.PASS: "green",
    Outcome.FAIL: "red",
    Outcome.NEEDS_ATTESTATION: "yellow",
    Outcome.NOT_APPLICABLE: "dim",
}
_OUTCOME_LABEL = {
    Outcome.PASS: "PASS",
    Outcome.FAIL: "FAIL",
    Outcome.NEEDS_ATTESTATION: "ATTEST",
    Outcome.NOT_APPLICABLE: "n/a",
}


def _load_register(path: Path) -> Register:
    """Load a register, exiting with a usage error if it cannot be read."""
    if not path.is_file():
        err.print(f"[red]register not found:[/red] {path}")
        err.print("Run [bold]airm init[/bold] to scaffold one.")
        raise typer.Exit(_EXIT_USAGE)
    try:
        return Register.load(path)
    except Exception as exc:
        err.print(f"[red]could not load {path}:[/red] {exc}")
        raise typer.Exit(_EXIT_USAGE) from exc


def _footer() -> None:
    """Print the standing disclaimer, dimmed, after every substantive command."""
    console.print(f"\n[dim]{DISCLAIMER}[/dim]")


@app.callback()
def main() -> None:
    """Toolkit for the MAS Guidelines on Artificial Intelligence Risk Management."""


@app.command()
def version() -> None:
    """Print the airmkit version and the Guidelines edition it indexes."""
    catalogue = load_catalogue()
    console.print(f"airmkit {__version__}")
    console.print(
        f"indexes {catalogue.meta['title']}, issued {catalogue.meta['issued']} "
        f"({len(catalogue)} paragraphs, {len(catalogue.footnotes)} footnotes)"
    )
    console.print(f"source sha256: {catalogue.meta['source_sha256']}")


@app.command()
def init(
    institution: Annotated[
        str, typer.Option("--institution", "-i", help="Institution name.")
    ] = "Example Financial Institution",
    out: Annotated[Path, typer.Option("--out", "-o", help="Register path to write.")] = Path(
        _DEFAULT_REGISTER
    ),
    rubric_out: Annotated[
        Path | None,
        typer.Option("--rubric-out", help="Also write an editable copy of the default rubric."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing register.")] = False,
) -> None:
    """Scaffold an AI inventory register and optionally a copy of the rubric.

    Serves MAS-AIRM §4.5-§4.6 (establish an inventory) and §4.3, §4.9, §4.13 (designate control
    functions). The scaffold deliberately leaves the control functions blank so that the first
    ``airm check`` reports them as gaps rather than inventing an owner.
    """
    if out.exists() and not force:
        err.print(f"[red]{out} already exists.[/red] Pass --force to overwrite.")
        raise typer.Exit(_EXIT_USAGE)

    example = UseCase(
        id="example-policy-assistant",
        name="Internal policy assistant",
        purpose="Answer staff questions about internal policies from an approved document set.",
        business_function="Operations",
        approved_scope="Internal staff use in Singapore only; not for customer-facing responses.",
        jurisdictions=["SG"],
        model_type="llm_rag",
        data_used=["internal_policy_documents"],
        data_classification="internal",
        dependencies=[Dependency(kind="dataset", name="policy_corpus", identifier="DATA-0001")],
        lifecycle_status=LifecycleStatus.PROPOSED,
        review_status=ReviewStatus.NOT_REVIEWED,
        roles=[
            Role(role="owner", party="TODO", function="Operations"),
            Role(role="developer", party="TODO", function="Data Science"),
            Role(role="validator", party="TODO", function="Model Risk"),
            Role(role="monitor", party="TODO", function="Operations"),
        ],
        documentation=["docs/model-card-policy-assistant.md"],
        third_party=[
            ThirdPartyComponent(
                provider="TODO",
                component="TODO",
                embedded=False,
                material_provider=False,
                independent_assessment=False,
                change_notification=False,
            )
        ],
        guardrails=[
            Guardrail(
                name="scope filter",
                kind="output_filter",
                description="Refuses questions outside the approved document set.",
                tested=False,
            )
        ],
        autonomy=AutonomyLevel.ASSISTIVE,
        human_oversight="Staff review answers before relying on them.",
        affects_individuals=False,
        tags=["internal", "genai"],
    )
    register = Register(
        institution=institution,
        as_of=dt.date.today(),
        linked_registers={},
        control_functions={"identification": "", "inventory": "", "materiality": ""},
        use_cases=[example],
        notes=(
            "Scaffold. Replace the example use case and fill the designated control functions "
            "(MAS-AIRM §4.3, §4.9, §4.13) and register linkages (§4.6 fn23)."
        ),
    )
    register.save(out)
    console.print(f"[green]wrote[/green] {out} with 1 example use case")
    if rubric_out is not None:
        load_rubric().save(rubric_out)
        console.print(f"[green]wrote[/green] {rubric_out} (editable copy of the default rubric)")
    console.print(
        "\nNext: [bold]airm scan .[/bold] to find AI already in your code, then "
        "[bold]airm assess[/bold] and [bold]airm check[/bold]."
    )
    _footer()


@app.command()
def scan(
    path: Annotated[Path, typer.Argument(help="Directory or file to scan.")] = Path(),
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Write candidate inventory entries here.")
    ] = None,
    json_out: Annotated[
        Path | None, typer.Option("--json", help="Write the raw scan report as JSON.")
    ] = None,
    min_confidence: Annotated[
        str, typer.Option("--min-confidence", help="low, medium or high.")
    ] = "medium",
    group_by: Annotated[
        str, typer.Option("--group-by", help="'directory' or 'file' for candidate grouping.")
    ] = "directory",
    show: Annotated[int, typer.Option("--show", help="How many findings to print.")] = 20,
) -> None:
    """Find signals of AI use in code and configuration (shadow-AI discovery).

    Serves MAS-AIRM §4.2 and §4.4 with footnote 22. Output is a list of candidates for human
    triage, never an inventory: §4.3 makes the designated control function the final arbiter of
    whether a given use constitutes AI use. Scanned files are treated as untrusted data and are
    never imported or executed; matched lines are secret-redacted before being recorded.
    """
    if min_confidence not in {"low", "medium", "high"}:
        err.print("[red]--min-confidence must be low, medium or high[/red]")
        raise typer.Exit(_EXIT_USAGE)
    report = scan_path(path, min_confidence=min_confidence)

    console.print(
        f"scanned [bold]{report.files_scanned}[/bold] file(s), skipped {report.files_skipped}"
    )
    if not report.findings:
        console.print("[green]no signals found[/green]")
        console.print(f"[dim]{report.caveat}[/dim]")
        return

    table = Table(title=f"{len(report.findings)} signal(s)", show_lines=False)
    table.add_column("Kind")
    table.add_column("Signal")
    table.add_column("Location")
    table.add_column("Clause")
    for finding in report.findings[:show]:
        table.add_row(finding.kind.value, finding.label, finding.location, finding.citation)
    console.print(table)
    if len(report.findings) > show:
        console.print(f"[dim]... and {len(report.findings) - show} more[/dim]")

    summary = Table(title="By kind")
    summary.add_column("Kind")
    summary.add_column("Count", justify="right")
    for kind, count in report.kinds.items():
        summary.add_row(kind, str(count))
    console.print(summary)

    if report.shadow_ai_findings:
        console.print(
            f"\n[yellow]{len(report.shadow_ai_findings)} reference(s) to public AI tools[/yellow] "
            f"— MAS-AIRM §4.4 fn22 expects risks from unidentified AI use to be mitigated."
        )
    if report.embedded_ai_findings:
        console.print(
            f"[yellow]{len(report.embedded_ai_findings)} vendor AI service reference(s)[/yellow] "
            f"— MAS-AIRM §4.2 fn21 covers AI embedded in third-party services."
        )
    if report.has_agent_signals:
        console.print(
            "[yellow]agent signals present[/yellow] — MAS-AIRM §4.8 fn25 expects agent "
            "identifiers, accessible tools and systems, components and guardrails in the inventory."
        )

    if out is not None:
        candidates = to_use_cases(report, group_by=group_by)
        Register(
            institution="UNTRIAGED SCAN CANDIDATES",
            notes=report.caveat,
            use_cases=candidates,
        ).save(out)
        console.print(f"\n[green]wrote[/green] {out} with {len(candidates)} candidate entr(ies)")
    if json_out is not None:
        json_out.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        console.print(f"[green]wrote[/green] {json_out}")

    console.print(f"\n[dim]{report.caveat}[/dim]")


@app.command()
def assess(
    register: Annotated[Path, typer.Option("--register", "-r", help="Register path.")] = Path(
        _DEFAULT_REGISTER
    ),
    rubric: Annotated[
        Path | None, typer.Option("--rubric", help="Rubric YAML; the packaged default if omitted.")
    ] = None,
    use_case: Annotated[
        str | None, typer.Option("--use-case", "-u", help="Assess one use case only.")
    ] = None,
    explain: Annotated[
        bool, typer.Option("--explain", help="Print the reasons behind every score.")
    ] = False,
    write: Annotated[
        bool,
        typer.Option("--write", help="Write the ratings back into the register (MAS-AIRM §4.7)."),
    ] = False,
    json_out: Annotated[
        Path | None, typer.Option("--json", help="Write assessments as JSON.")
    ] = None,
) -> None:
    """Score risk materiality on Impact, Complexity and Reliance.

    Serves MAS-AIRM §4.10-§4.13. Deterministic, so a rating can be reproduced by a reviewer. The
    rubric's levels, their combination and the tier names are this toolkit's proposal: MAS
    declines to prescribe a formula or a universal threshold for high risk materiality (Response
    to Feedback §7.19).
    """
    reg = _load_register(register)
    active_rubric = load_rubric(rubric)
    portfolio = assess_register(reg, active_rubric)
    targets = [use_case] if use_case else [uc.id for uc in reg.use_cases]
    if use_case and use_case not in reg:
        err.print(f"[red]no such use case in register:[/red] {use_case}")
        raise typer.Exit(_EXIT_USAGE)

    table = Table(
        title=f"Risk materiality — rubric {active_rubric.id} ({active_rubric.combination})"
    )
    table.add_column("Use case")
    for dimension in Dimension:
        table.add_column(dimension.value.title())
    table.add_column("Inherent")
    table.add_column("Residual")
    for use_case_id in targets:
        assessment = portfolio.assessments[use_case_id]
        row = [use_case_id]
        row.extend(assessment.dimensions[d].level.value for d in Dimension)
        row.append(f"[{_TIER_STYLE[assessment.inherent_tier]}]{assessment.inherent_tier.value}[/]")
        row.append(f"[{_TIER_STYLE[assessment.residual_tier]}]{assessment.residual_tier.value}[/]")
        table.add_row(*row)
    console.print(table)
    console.print(
        "[dim]Dimensions: MAS-AIRM §4.12(a) Impact, (b) Complexity, (c) Reliance. Tiering is this "
        "toolkit's proposal, not a MAS requirement (Response to Feedback §7.19).[/dim]"
    )

    if explain:
        for use_case_id in targets:
            assessment = portfolio.assessments[use_case_id]
            console.print(f"\n[bold]{use_case_id}[/bold]")
            for dimension in Dimension:
                score = assessment.dimensions[dimension]
                console.print(
                    f"  [bold]{dimension.value}[/bold] = {score.level.value}  "
                    f"[dim]{score.citation}[/dim]"
                )
                for reason in score.reasons:
                    console.print(f"    - {reason}")
            for note in assessment.mitigation_notes:
                console.print(f"  [dim]{note}[/dim]")

    high = portfolio.high_materiality_ids
    if high:
        console.print(
            f"\n[dark_orange]{len(high)} use case(s) at high risk materiality[/dark_orange]: "
            f"{', '.join(high)}"
        )
        console.print(
            "[dim]These attract §5.3 contingency plans, §5.19 formal independent validation, "
            "§5.23(b) kill switches and §5.24 independent re-validation. Triggers key on "
            "inherent materiality (Response to Feedback §7.21).[/dim]"
        )

    if write:
        for use_case_id, assessment in portfolio.assessments.items():
            reg.get(use_case_id).risk_materiality_rating = assessment.inherent_tier.value
        reg.save(register)
        console.print(f"\n[green]wrote ratings into[/green] {register} (MAS-AIRM §4.7)")
    if json_out is not None:
        json_out.write_text(portfolio.model_dump_json(indent=2) + "\n", encoding="utf-8")
        console.print(f"[green]wrote[/green] {json_out}")
    _footer()


@app.command()
def check(
    register: Annotated[Path, typer.Option("--register", "-r", help="Register path.")] = Path(
        _DEFAULT_REGISTER
    ),
    use_case: Annotated[
        str | None, typer.Option("--use-case", "-u", help="Check one use case only.")
    ] = None,
    rubric: Annotated[Path | None, typer.Option("--rubric", help="Rubric YAML.")] = None,
    controls: Annotated[
        Path | None, typer.Option("--controls", help="Control catalogue YAML.")
    ] = None,
    trail: Annotated[
        Path | None,
        typer.Option(
            "--trail", help="Audit trail JSONL to read evidence from (MAS-AIRM §5.23(d))."
        ),
    ] = None,
    institution: Annotated[
        bool, typer.Option("--institution", help="Check the institution-level controls only.")
    ] = False,
    show_all: Annotated[
        bool, typer.Option("--all", help="Include not-applicable controls and their reasons.")
    ] = False,
    json_out: Annotated[Path | None, typer.Option("--json", help="Write results as JSON.")] = None,
) -> None:
    """Evaluate a use case or register against the applicable controls.

    Serves MAS-AIRM §5.2 (proportionate application of relevant controls) and §5.18-§5.21 (the
    pass / fail / needs-attestation statement a reviewer works from).

    Exits 1 if any automated check failed. ``needs_attestation`` does not fail the build: it is a
    question for a person by construction.
    """
    reg = _load_register(register)
    catalogue = load_controls(controls)
    active_rubric = load_rubric(rubric)
    evidence: dict[str, dict[str, str]] = {}
    institution_evidence: dict[str, str] = {}
    if trail is not None and trail.is_file():
        audit = AuditTrail(trail)
        for entry in reg.use_cases:
            evidence[entry.id] = audit.evidence_map(entry.id)
        for record in audit.records():
            if record.use_case_id is None:
                for item in record.evidence:
                    institution_evidence[item.item] = item.ref

    failures = 0

    if institution or use_case is None:
        report = check_institution(reg, catalogue=catalogue, evidence=institution_evidence)
        table = Table(title=f"Institution-level controls — {reg.institution}")
        table.add_column("Outcome")
        table.add_column("Control")
        table.add_column("Clauses")
        table.add_column("Class")
        table.add_column("Finding")
        for result in report.results:
            if result.outcome is Outcome.NOT_APPLICABLE and not show_all:
                continue
            table.add_row(
                f"[{_OUTCOME_STYLE[result.outcome]}]{_OUTCOME_LABEL[result.outcome]}[/]",
                result.control_id,
                ", ".join(result.clauses),
                result.automatability.value,
                result.reason,
            )
        console.print(table)
        failures += len(report.failures)

    if not institution:
        targets = [use_case] if use_case else [uc.id for uc in reg.use_cases]
        if use_case and use_case not in reg:
            err.print(f"[red]no such use case in register:[/red] {use_case}")
            raise typer.Exit(_EXIT_USAGE)
        reports = {}
        for use_case_id in targets:
            entry = reg.get(use_case_id)
            assessment = active_rubric.assess(entry)
            report_uc = check_use_case(
                entry,
                assessment=assessment,
                catalogue=catalogue,
                evidence=evidence.get(use_case_id, {}),
            )
            reports[use_case_id] = report_uc
            failures += len(report_uc.failures)

            table = Table(
                title=(
                    f"{use_case_id} — inherent {report_uc.inherent_tier.value}, "
                    f"residual {report_uc.residual_tier.value}"
                )
            )
            table.add_column("Outcome")
            table.add_column("Control")
            table.add_column("Clauses")
            table.add_column("Class")
            table.add_column("Finding")
            table.add_column("Due")
            for result in report_uc.results:
                if result.outcome is Outcome.NOT_APPLICABLE and not show_all:
                    continue
                table.add_row(
                    f"[{_OUTCOME_STYLE[result.outcome]}]{_OUTCOME_LABEL[result.outcome]}[/]",
                    result.control_id,
                    ", ".join(result.clauses),
                    result.automatability.value,
                    result.reason,
                    result.effective_by.isoformat() if result.effective_by else "—",
                )
            console.print(table)
            counts = report_uc.counts
            console.print(
                f"[green]{counts['pass']} pass[/green] · [red]{counts['fail']} fail[/red] · "
                f"[yellow]{counts['needs_attestation']} attest[/yellow] · "
                f"[dim]{counts['not_applicable']} n/a[/dim]\n"
            )
        if json_out is not None:
            json_out.write_text(
                json.dumps(
                    {k: json.loads(v.model_dump_json()) for k, v in reports.items()}, indent=2
                )
                + "\n",
                encoding="utf-8",
            )
            console.print(f"[green]wrote[/green] {json_out}")

    console.print(
        "[dim]ATTEST means the artefact's existence is checkable but its adequacy is a human "
        "judgement, or the control is purely documentary. It does not fail the build.[/dim]"
    )
    _footer()
    if failures:
        raise typer.Exit(_EXIT_FAIL)


@app.command()
def evidence(
    event: Annotated[
        str,
        typer.Argument(help=f"Event type: {', '.join(e.value for e in EventType)}."),
    ],
    summary: Annotated[str, typer.Option("--summary", "-s", help="One-line summary.")],
    trail: Annotated[Path, typer.Option("--trail", "-t", help="Audit trail JSONL.")] = Path(
        "evidence/trail.jsonl"
    ),
    use_case: Annotated[
        str | None,
        typer.Option("--use-case", "-u", help="Use case id; omit for institution-level."),
    ] = None,
    actor: Annotated[str, typer.Option("--actor", "-a", help="Who is recording this.")] = "cli",
    item: Annotated[
        list[str] | None,
        typer.Option("--item", help="Evidence as name=path; repeatable. Files are hashed."),
    ] = None,
    outcome: Annotated[str | None, typer.Option("--outcome", help="pass, fail, etc.")] = None,
    severity: Annotated[
        str, typer.Option("--severity", help="info, warning, breach, critical.")
    ] = "info",
    verify: Annotated[
        bool, typer.Option("--verify", help="Verify the chain and evidence digests, then exit.")
    ] = False,
) -> None:
    """Append a record to the hash-chained audit trail, or verify it.

    Serves MAS-AIRM §5.23(d) (clear records of activities, results, issues and remediation, with
    access controlled and logged) and §5.17 (documentation enabling auditability). Records are
    append-only and chained, so an alteration is detectable.
    """
    audit = AuditTrail(trail)
    if verify:
        try:
            audit.verify()
        except Exception as exc:
            err.print(f"[red]chain broken:[/red] {exc}")
            raise typer.Exit(_EXIT_FAIL) from exc
        console.print(f"[green]chain intact[/green]: {len(audit)} record(s) in {trail}")
        digests = audit.verify_evidence()
        changed = [ref for ref, ok in digests.items() if ok is False]
        unchecked = [ref for ref, ok in digests.items() if ok is None]
        if changed:
            err.print(f"[red]{len(changed)} evidence file(s) changed since attestation:[/red]")
            for ref in changed:
                err.print(f"  {ref}")
            raise typer.Exit(_EXIT_FAIL)
        console.print(
            f"[green]{len(digests) - len(unchecked)} evidence digest(s) verified[/green]"
            + (f", {len(unchecked)} not checkable" if unchecked else "")
        )
        return

    try:
        event_type = EventType(event)
    except ValueError as exc:
        err.print(f"[red]unknown event type:[/red] {event}")
        err.print(f"expected one of: {', '.join(e.value for e in EventType)}")
        raise typer.Exit(_EXIT_USAGE) from exc
    try:
        severity_value = Severity(severity)
    except ValueError as exc:
        err.print(f"[red]unknown severity:[/red] {severity}")
        raise typer.Exit(_EXIT_USAGE) from exc

    items = []
    for spec in item or []:
        if "=" not in spec:
            err.print(f"[red]--item expects name=path, got:[/red] {spec}")
            raise typer.Exit(_EXIT_USAGE)
        name, ref = spec.split("=", 1)
        items.append(new_evidence(name.strip(), ref.strip()))

    record = audit.append(
        event_type,
        actor=actor,
        summary=summary,
        use_case_id=use_case,
        severity=severity_value,
        outcome=outcome,
        evidence=items,
    )
    console.print(f"[green]appended[/green] record {record.seq} ({record.event.value}) to {trail}")
    console.print(f"  clauses: {', '.join(record.clauses)}")
    console.print(f"  hash: {record.record_hash[:16]}…")
    for entry in record.evidence:
        digest = f" sha256:{entry.digest[:12]}…" if entry.digest else " (not hashed)"
        console.print(f"  evidence: {entry.item} -> {entry.ref}{digest}")


@app.command()
def report(
    register: Annotated[Path, typer.Option("--register", "-r", help="Register path.")] = Path(
        _DEFAULT_REGISTER
    ),
    out: Annotated[Path, typer.Option("--out", "-o", help="Output directory.")] = Path(
        "audit-pack"
    ),
    rubric: Annotated[Path | None, typer.Option("--rubric", help="Rubric YAML.")] = None,
    controls: Annotated[
        Path | None, typer.Option("--controls", help="Control catalogue YAML.")
    ] = None,
    vendors: Annotated[
        Path | None, typer.Option("--vendors", help="Third-party AI assessment register YAML.")
    ] = None,
    trail: Annotated[Path | None, typer.Option("--trail", help="Audit trail for evidence.")] = None,
    docx: Annotated[bool, typer.Option("--docx", help="Also write DOCX versions.")] = False,
) -> None:
    """Generate the audit-ready pack.

    Writes the AI inventory register (MAS-AIRM §4.5-§4.9), the risk materiality report
    (§4.10-§4.13), the control applicability statement (§5.2), the gap analysis by effective date
    (§1.8), the crosswalk coverage report, the clause index, and a board one-pager (§3.4, §3.5(f)).
    """
    reg = _load_register(register)
    vendor_register = None
    if vendors is not None:
        from airm.thirdparty import VendorRegister

        vendor_register = VendorRegister.load(vendors)

    evidence_map: dict[str, dict[str, str]] = {}
    institution_evidence: dict[str, str] = {}
    if trail is not None and trail.is_file():
        audit = AuditTrail(trail)
        for entry in reg.use_cases:
            evidence_map[entry.id] = audit.evidence_map(entry.id)
        for record in audit.records():
            if record.use_case_id is None:
                for item in record.evidence:
                    institution_evidence[item.item] = item.ref

    pack = AuditPack(
        reg,
        rubric=load_rubric(rubric),
        controls=load_controls(controls),
        vendors=vendor_register,
        evidence=evidence_map,
        institution_evidence=institution_evidence,
    )
    written = pack.write(out)
    for path in written.values():
        console.print(f"[green]wrote[/green] {path}")

    if docx:
        from airm.report import to_docx

        for path in written.values():
            if path.suffix == ".md":
                target = to_docx(path, path.with_suffix(".docx"))
                console.print(f"[green]wrote[/green] {target}")

    console.print(
        f"\n{len(written)} document(s) in {out}. Start with [bold]{out}/00-board-summary.md[/bold]."
    )
    _footer()


@app.command()
def gap(
    register: Annotated[Path, typer.Option("--register", "-r", help="Register path.")] = Path(
        _DEFAULT_REGISTER
    ),
    by_date: Annotated[
        bool, typer.Option("--by-date", help="Group by the effective date of the clause.")
    ] = True,
    rubric: Annotated[Path | None, typer.Option("--rubric", help="Rubric YAML.")] = None,
) -> None:
    """Show open items grouped by when the underlying clause takes effect.

    Serves MAS-AIRM §1.8: Sections 3-4 from 7 October 2027, Sections 5-6 by 7 October 2028.
    Response to Feedback §13.5 asks that lifecycle controls for high risk use cases be applied as
    soon as possible rather than at the end of the transition, so those are listed separately.
    """
    reg = _load_register(register)
    active_rubric = load_rubric(rubric)
    catalogue = load_controls()
    portfolio = assess_register(reg, active_rubric)
    reports = check_register(reg, catalogue=catalogue)
    institution = check_institution(reg, catalogue=catalogue)

    buckets: dict[str, list[tuple[str, str, str]]] = {}
    for result in institution.results:
        if result.is_adverse and result.effective_by:
            buckets.setdefault(result.effective_by.isoformat(), []).append(
                ("(institution)", result.control_id, result.reason)
            )
    for use_case_id, report_uc in reports.items():
        for result in report_uc.results:
            if result.is_adverse and result.effective_by:
                buckets.setdefault(result.effective_by.isoformat(), []).append(
                    (use_case_id, result.control_id, result.reason)
                )

    if not by_date:
        buckets = {"all": [row for rows in buckets.values() for row in rows]}

    for due in sorted(buckets):
        rows = buckets[due]
        section = "Sections 3-4" if due == "2027-10-07" else "Sections 5-6"
        table = Table(title=f"Due {due} ({section}) — {len(rows)} open item(s)")
        table.add_column("Use case")
        table.add_column("Control")
        table.add_column("Finding")
        for use_case_id, control_id, reason in sorted(rows):
            table.add_row(use_case_id, control_id, reason)
        console.print(table)

    high = portfolio.high_materiality_ids
    if high:
        console.print(
            f"\n[dark_orange]Priority[/dark_orange]: {len(high)} high-materiality use case(s) "
            f"({', '.join(high)}). Response to Feedback §13.5 asks that their lifecycle controls "
            f"not wait for 7 October 2028."
        )
    if not any(buckets.values()):
        console.print("[green]no open items[/green]")
    _footer()


@app.command()
def crosswalk(
    framework: Annotated[
        str | None,
        typer.Option("--framework", "-f", help=f"One of: {', '.join(f.value for f in Framework)}."),
    ] = None,
    clause: Annotated[
        str | None, typer.Option("--clause", "-c", help="A MAS-AIRM paragraph, e.g. 5.19.")
    ] = None,
    ref: Annotated[
        str | None,
        typer.Option("--ref", help="Reverse lookup: a provision of the other framework."),
    ] = None,
    holding: Annotated[
        list[str] | None,
        typer.Option("--holding", help="Frameworks already met; prints the residual work."),
    ] = None,
    json_out: Annotated[Path | None, typer.Option("--json", help="Write as JSON.")] = None,
) -> None:
    """Query the crosswalk to ISO/IEC 42001, NIST AI RMF, the EU AI Act, FEAT and the Info Paper.

    Mapping is interpretive and asymmetric: ISO 42001 is a management-system standard, the EU AI
    Act is product law, and the NIST AI RMF is voluntary guidance, so a paragraph can be covered
    in substance and uncovered in legal effect. Every row carries a justification and a confidence
    so it can be argued with individually.
    """
    cw = load_crosswalk()
    catalogue = load_catalogue()

    if clause:
        if clause not in catalogue:
            err.print(f"[red]unknown MAS-AIRM paragraph:[/red] {clause}")
            raise typer.Exit(_EXIT_USAGE)
        paragraph = catalogue.paragraph(clause)
        console.print(f"[bold]MAS-AIRM §{clause}[/bold] — {paragraph.heading}")
        console.print(f"{paragraph.summary}\n")
        table = Table(title=f"Coverage of §{clause}")
        table.add_column("Framework")
        table.add_column("Coverage")
        table.add_column("References")
        table.add_column("Confidence")
        for row in cw.for_clause(clause):
            style = {"full": "green", "partial": "yellow", "none": "red"}[row.coverage.value]
            table.add_row(
                row.framework.value,
                f"[{style}]{row.coverage.value}[/]",
                ", ".join(row.refs) or "—",
                row.confidence,
            )
        console.print(table)
        for row in cw.for_clause(clause):
            console.print(f"\n[bold]{row.framework.value}[/bold]: {row.justification}")
            if row.gap:
                console.print(f"  [yellow]gap:[/yellow] {row.gap}")
        return

    if ref:
        if not framework:
            err.print("[red]--ref needs --framework[/red]")
            raise typer.Exit(_EXIT_USAGE)
        try:
            target = Framework(framework)
        except ValueError as exc:
            err.print(f"[red]unknown framework:[/red] {framework}")
            raise typer.Exit(_EXIT_USAGE) from exc
        rows = cw.for_ref(target, ref)
        table = Table(title=f"{target.value} {ref} maps to")
        table.add_column("MAS-AIRM")
        table.add_column("Coverage")
        table.add_column("Heading")
        for row in rows:
            table.add_row(
                f"§{row.clause}", row.coverage.value, catalogue.paragraph(row.clause).heading
            )
        console.print(table)
        if not rows:
            console.print("[dim]no mapping found for that reference[/dim]")
        return

    if holding:
        try:
            held = [Framework(f) for f in holding]
        except ValueError as exc:
            err.print(f"[red]unknown framework in --holding:[/red] {exc}")
            raise typer.Exit(_EXIT_USAGE) from exc
        work = residual_work(held)
        console.print(
            f"[bold]Residual work[/bold] for an institution already meeting "
            f"{', '.join(f.value for f in held)}\n"
        )
        for label, clauses, style in (
            ("No coverage", work["uncovered"], "red"),
            ("Partial coverage, delta remains", work["partial"], "yellow"),
        ):
            table = Table(title=f"{label} ({len(clauses)})")
            table.add_column("Clause")
            table.add_column("Heading")
            table.add_column("Expectation")
            for clause_id in clauses:
                paragraph = catalogue.paragraph(clause_id)
                table.add_row(f"[{style}]§{clause_id}[/]", paragraph.heading, paragraph.summary)
            console.print(table)
        return

    summary = coverage_summary(cw)
    table = Table(title=f"Coverage of {len(catalogue.expectations())} MAS-AIRM expectations")
    table.add_column("Framework")
    table.add_column("Full", justify="right")
    table.add_column("Partial", justify="right")
    table.add_column("None", justify="right")
    for name, counts in summary.items():
        label = "UNION" if name == "union" else name
        table.add_row(
            label,
            str(counts[Coverage.FULL.value]),
            str(counts[Coverage.PARTIAL.value]),
            str(counts[Coverage.NONE.value]),
        )
    console.print(table)
    residue = cw.uncovered()
    console.print(
        f"\n[yellow]{len(residue)} expectation(s) have no full mapping in any framework[/yellow]: "
        f"{', '.join('§' + c for c in residue)}"
    )
    if json_out is not None:
        json_out.write_text(
            json.dumps({"coverage": summary, "residue": list(residue)}, indent=2) + "\n",
            encoding="utf-8",
        )
        console.print(f"[green]wrote[/green] {json_out}")
    _footer()


@app.command()
def clauses(
    section: Annotated[
        str | None, typer.Option("--section", "-s", help="One section, e.g. 5.")
    ] = None,
    tag: Annotated[
        str | None, typer.Option("--tag", "-t", help="Filter by tag, e.g. agent or genai.")
    ] = None,
    expectations_only: Annotated[
        bool, typer.Option("--expectations", help="Only paragraphs stating an expectation.")
    ] = False,
    fmt: Annotated[str, typer.Option("--format", help="'table' or 'markdown'.")] = "table",
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Write markdown here.")] = None,
) -> None:
    """Print the clause index: every paragraph and what implements it.

    Generated from the clause catalogue and the control catalogue, never hand-maintained, so the
    index cannot drift from either.
    """
    catalogue = load_catalogue()
    controls = load_controls()

    if fmt == "markdown":
        text = clause_index_markdown(controls=controls, catalogue=catalogue)
        if out is not None:
            out.write_text(text, encoding="utf-8")
            console.print(f"[green]wrote[/green] {out}")
        else:
            console.print(text)
        return

    paragraphs = catalogue.paragraphs
    if section:
        paragraphs = catalogue.by_section(section)
    if tag:
        paragraphs = tuple(p for p in paragraphs if p.has_tag(tag))
    if expectations_only:
        paragraphs = tuple(p for p in paragraphs if p.is_expectation)

    table = Table(title=f"MAS-AIRM clause index ({len(paragraphs)} paragraph(s))")
    table.add_column("Clause")
    table.add_column("Kind")
    table.add_column("Due")
    table.add_column("Summary")
    table.add_column("Controls")
    for paragraph in paragraphs:
        implementing = controls.by_clause(paragraph.id)
        table.add_row(
            f"§{paragraph.id}",
            paragraph.kind,
            paragraph.effective.isoformat(),
            paragraph.summary,
            str(len(implementing)) if implementing else "[red]0[/red]",
        )
    console.print(table)

    counts = controls.automatability_counts()
    console.print(
        f"\n[dim]Controls by automatability: {counts[Automatability.AUTO.value]} auto, "
        f"{counts[Automatability.SEMI.value]} semi, {counts[Automatability.DOC.value]} doc. "
        f"{sum(1 for c in controls.controls if c.scope is Scope.INSTITUTION)} of "
        f"{len(controls)} are institution-level.[/dim]"
    )


@app.command()
def schemas(
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Directory to write the JSON Schemas to.")
    ] = Path("schemas"),
) -> None:
    """Export a JSON Schema for every format the toolkit reads or writes.

    Lets a GRC platform, a spreadsheet or a service in another language validate an AI inventory
    register (MAS-AIRM §4.5-§4.9), a materiality assessment (§4.10-§4.13), a vendor assessment
    (§5.10-§5.11) or an evidence record (§5.23(d)) against the same schema this library enforces,
    without installing Python.
    """
    from airm.schemas import export

    written = export(out)
    for stem, path in written.items():
        console.print(f"[green]wrote[/green] {path} [dim]({stem})[/dim]")
    console.print(f"\n{len(written)} file(s) in {out}.")
    _footer()


if __name__ == "__main__":  # pragma: no cover
    app()
