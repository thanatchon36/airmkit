"""Control catalogue and checks: MAS-AIRM Section 5 plus the Section 4 process controls."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from airm.catalog import load_catalogue
from airm.controls import (
    Automatability,
    Control,
    ControlCatalogue,
    Outcome,
    Scope,
    available_checks,
    check_institution,
    check_register,
    check_use_case,
    evidence_items,
    filter_by_use_case,
    load_controls,
)
from airm.inventory import (
    AgentExtension,
    AutonomyLevel,
    Guardrail,
    LifecycleStatus,
    Register,
    ReviewStatus,
    Role,
    ThirdPartyComponent,
    UseCase,
)
from airm.materiality import Tier, assess


class TestCatalogueIntegrity:
    def test_every_control_cites_a_real_paragraph(self):
        """MISSION: traceability over coverage. A control with no clause is a bug."""
        catalogue = load_controls()
        clause_index = load_catalogue()
        for control in catalogue.controls:
            assert control.clauses
            for clause in control.clauses:
                assert ".".join(clause.split(".")[:2]) in clause_index

    def test_control_ids_unique(self):
        ids = [c.id for c in load_controls().controls]
        assert len(ids) == len(set(ids))

    def test_auto_controls_have_a_check(self):
        for control in load_controls().controls:
            if control.automatability is Automatability.AUTO:
                assert control.check is not None, control.id

    def test_every_control_explains_its_automatability(self):
        """The RQ1 classification table must be arguable row by row."""
        for control in load_controls().controls:
            assert control.automatability_rationale.strip(), control.id

    def test_duplicate_control_id_rejected(self):
        control = load_controls().controls[0]
        with pytest.raises(ValidationError, match="duplicate control id"):
            ControlCatalogue(controls=[control, control])

    def test_unknown_clause_rejected(self):
        with pytest.raises(ValidationError, match="unknown paragraph"):
            ControlCatalogue(
                controls=[
                    Control(
                        id="X",
                        title="X",
                        family="f",
                        clauses=["9.9"],
                        intent="i",
                        automatability=Automatability.DOC,
                    )
                ]
            )

    def test_unknown_check_rejected(self):
        with pytest.raises(ValidationError, match="unknown check"):
            Control(
                id="X",
                title="X",
                family="f",
                clauses=["5.1"],
                intent="i",
                check="nope",
                automatability=Automatability.SEMI,
            )

    def test_auto_without_check_rejected(self):
        with pytest.raises(ValidationError, match="requires a check function"):
            Control(
                id="X",
                title="X",
                family="f",
                clauses=["5.1"],
                intent="i",
                automatability=Automatability.AUTO,
            )

    def test_only_paragraph_2_2_is_uncovered(self):
        """2.2 is the roll-up clause saying Sections 3-6 apply; the catalogue satisfies it."""
        assert load_controls().uncovered_expectations() == ("2.2",)

    def test_clause_lookup(self):
        catalogue = load_controls()
        assert catalogue.by_clause("5.15")
        assert any(c.id == "AIRM-5.15-GUARDRAIL-EFFECTIVENESS" for c in catalogue.by_clause("5.15"))

    def test_citations_are_formatted(self):
        control = load_controls().get("AIRM-4.8-FN25-AGENT-ATTRIBUTES")
        assert "MAS-AIRM §4.8 fn25" in control.citations

    def test_item_clause_formatting(self):
        control = load_controls().get("AIRM-5.23-AGENT-TRACE-MONITORING")
        assert "MAS-AIRM §5.23(a)" in control.citations

    def test_effective_dates_from_the_clause(self):
        assert load_controls().get("AIRM-4.7-INVENTORY-ATTRIBUTES").effective_by().year == 2027
        assert load_controls().get("AIRM-5.15-GUARDRAIL-EFFECTIVENESS").effective_by().year == 2028

    def test_families_and_counts(self):
        catalogue = load_controls()
        assert len(catalogue) == len(catalogue.controls)
        assert len(catalogue.families()) > 10
        counts = catalogue.automatability_counts()
        assert sum(counts.values()) == len(catalogue)

    def test_missing_control_raises(self):
        with pytest.raises(KeyError, match="no such control"):
            load_controls().get("NOPE")

    def test_evidence_items_listed(self):
        items = evidence_items()
        assert "guardrail_test_report" in items
        assert "independent_validation_report" in items

    def test_available_checks_registered(self):
        assert "guardrail_effectiveness" in available_checks()
        assert "agent_tool_scope" in available_checks()


class TestApplicability:
    def test_high_materiality_only_controls_excluded_at_low_tier(self, minimal_use_case):
        """MAS-AIRM 5.3 and 5.19 bind only at high risk materiality."""
        report = check_use_case(minimal_use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.19-INDEPENDENT-VALIDATION"
        )
        assert result.outcome is Outcome.NOT_APPLICABLE
        assert "high risk materiality" in result.reason

    def test_high_materiality_controls_apply_at_critical(self, credit_use_case):
        report = check_use_case(credit_use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.19-INDEPENDENT-VALIDATION"
        )
        assert result.outcome is not Outcome.NOT_APPLICABLE

    def test_tag_gated_controls(self, credit_use_case):
        """A gradient boosting model is not GenAI, so the guardrail control does not apply."""
        report = check_use_case(credit_use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.15-GUARDRAIL-EFFECTIVENESS"
        )
        assert result.outcome is Outcome.NOT_APPLICABLE
        assert "tagged" in result.reason

    def test_third_party_controls_need_a_component(self, credit_use_case):
        report = check_use_case(credit_use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.11-THIRD-PARTY-TRANSPARENCY"
        )
        assert result.outcome is Outcome.NOT_APPLICABLE

    def test_live_only_controls(self):
        proposed = UseCase(id="p", name="P", purpose="p", lifecycle_status=LifecycleStatus.PROPOSED)
        report = check_use_case(proposed)
        result = next(r for r in report.results if r.control_id == "AIRM-5.23-MONITORING-MEASURES")
        assert result.outcome is Outcome.NOT_APPLICABLE
        assert "piloted or deployed" in result.reason

    def test_fairness_gated_controls(self):
        """docs/INTERPRETATIONS.md I-7: fairness relevance is explicit, with a reason given."""
        use_case = UseCase(
            id="internal",
            name="I",
            purpose="p",
            fairness_relevant=False,
            lifecycle_status=LifecycleStatus.DEPLOYED,
        )
        report = check_use_case(use_case)
        result = next(r for r in report.results if r.control_id == "AIRM-5.8-FAIRNESS-ASSESSMENT")
        assert result.outcome is Outcome.NOT_APPLICABLE
        assert "not relevant" in result.reason

    def test_filter_by_use_case(self, credit_use_case):
        applicable = filter_by_use_case(credit_use_case)
        assert applicable
        assert all(c.scope is Scope.USE_CASE for c in applicable)

    def test_institution_controls_excluded_from_use_case_checks(self, credit_use_case):
        report = check_use_case(credit_use_case)
        ids = {r.control_id for r in report.results}
        assert "AIRM-2.5-BASIC-POLICIES" not in ids


class TestChecks:
    def test_guardrail_effectiveness_requires_a_test(self):
        """MAS-AIRM 5.15: guardrails must be tested, not merely present."""
        untested = UseCase(
            id="chat",
            name="Chat",
            purpose="p",
            model_type="llm",
            tags=["genai"],
            lifecycle_status=LifecycleStatus.DEPLOYED,
            guardrails=[Guardrail(name="filter", kind="output_filter", tested=False)],
        )
        report = check_use_case(untested)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.15-GUARDRAIL-EFFECTIVENESS"
        )
        assert result.outcome is Outcome.FAIL
        assert "no recorded effectiveness test" in result.reason

    def test_guardrail_marked_tested_needs_an_evidence_pointer(self):
        use_case = UseCase(
            id="chat",
            name="Chat",
            purpose="p",
            model_type="llm",
            tags=["genai"],
            lifecycle_status=LifecycleStatus.DEPLOYED,
            guardrails=[Guardrail(name="filter", kind="output_filter", tested=True)],
        )
        report = check_use_case(use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.15-GUARDRAIL-EFFECTIVENESS"
        )
        assert result.outcome is Outcome.FAIL
        assert "no evidence pointer" in result.reason

    def test_no_guardrails_at_all_fails(self):
        use_case = UseCase(
            id="chat",
            name="Chat",
            purpose="p",
            model_type="llm",
            tags=["genai"],
            lifecycle_status=LifecycleStatus.DEPLOYED,
        )
        report = check_use_case(use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.15-GUARDRAIL-EFFECTIVENESS"
        )
        assert result.outcome is Outcome.FAIL
        assert "no guardrails recorded" in result.reason

    def test_guardrail_check_passes_when_tested_with_evidence(self, agent_use_case):
        report = check_use_case(agent_use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.15-GUARDRAIL-EFFECTIVENESS"
        )
        assert result.outcome is Outcome.PASS

    def test_agent_attributes_check(self, agent_use_case):
        report = check_use_case(agent_use_case)
        result = next(r for r in report.results if r.control_id == "AIRM-4.8-FN25-AGENT-ATTRIBUTES")
        assert result.outcome is Outcome.PASS

    def test_agent_tool_scope_requires_permissions_for_external_actions(self):
        use_case = UseCase(
            id="a",
            name="A",
            purpose="p",
            autonomy=AutonomyLevel.AUTONOMOUS_AGENT,
            lifecycle_status=LifecycleStatus.DEPLOYED,
            agent=AgentExtension(
                agent_identifier="x",
                approved_tools=["t"],
                components=["c"],
                guardrails=[
                    Guardrail(name="g", kind="tool_allowlist", tested=True, evidence_ref="E")
                ],
                can_initiate_external_actions=True,
                permissions=[],
            ),
        )
        report = check_use_case(use_case)
        result = next(r for r in report.results if r.control_id == "AIRM-5.16-AGENT-PERMISSIONS")
        assert result.outcome is Outcome.FAIL
        assert "no permissions are recorded" in result.reason

    def test_independent_validation_requires_an_independent_party(self):
        """MAS-AIRM 5.19 with 5.20 fn48."""
        use_case = UseCase(
            id="x",
            name="X",
            purpose="p",
            tags=["credit"],
            affects_individuals=True,
            review_status=ReviewStatus.INDEPENDENT_VALIDATION,
            roles=[
                Role(role="owner", party="A"),
                Role(role="developer", party="B"),
                Role(role="validator", party="B"),
            ],
        )
        report = check_use_case(use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.19-INDEPENDENT-VALIDATION"
        )
        assert result.outcome is Outcome.FAIL
        assert "independent of the owner" in result.reason

    def test_third_party_self_attestation_fails(self):
        """Response to Feedback 9.9 rejects vendor self-attestation."""
        use_case = UseCase(
            id="v",
            name="V",
            purpose="p",
            third_party=[
                ThirdPartyComponent(provider="V", component="c", independent_assessment=False)
            ],
        )
        report = check_use_case(use_case)
        result = next(
            r for r in report.results if r.control_id == "AIRM-5.11-THIRD-PARTY-TRANSPARENCY"
        )
        assert result.outcome is Outcome.FAIL
        assert "self-attestations" in result.reason

    def test_materiality_rating_mismatch_detected(self, credit_use_case):
        credit_use_case.risk_materiality_rating = "Low"
        report = check_use_case(credit_use_case)
        result = next(r for r in report.results if r.control_id == "AIRM-4.11-MATERIALITY-ASSESSED")
        assert result.outcome is Outcome.FAIL
        assert "does not match" in result.reason

    def test_risk_appetite_cannot_be_inferred(self, credit_use_case):
        """MAS-AIRM 4.11: the toolkit must not invent an appetite statement."""
        report = check_use_case(credit_use_case)
        result = next(r for r in report.results if r.control_id == "AIRM-4.11-RISK-APPETITE")
        assert result.outcome is Outcome.FAIL
        assert "cannot infer" in result.reason

    def test_risk_appetite_confirmed_passes(self, credit_use_case):
        assessment = assess(credit_use_case)
        assessment.within_risk_appetite = True
        report = check_use_case(credit_use_case, assessment=assessment)
        result = next(r for r in report.results if r.control_id == "AIRM-4.11-RISK-APPETITE")
        assert result.outcome is Outcome.NEEDS_ATTESTATION

    def test_pilot_needs_a_scope_limiting_guardrail(self):
        """MAS-AIRM 5.2 fn28: partial deployments need time and user limits."""
        pilot = UseCase(
            id="p",
            name="P",
            purpose="p",
            lifecycle_status=LifecycleStatus.PILOT,
            guardrails=[Guardrail(name="x", kind="output_filter", tested=True, evidence_ref="E")],
        )
        report = check_use_case(pilot)
        result = next(r for r in report.results if r.control_id == "AIRM-5.2-FN28-PILOT-GUARDRAILS")
        assert result.outcome is Outcome.FAIL

    def test_retirement_control_only_applies_to_retired(self, credit_use_case):
        report = check_use_case(credit_use_case)
        result = next(r for r in report.results if r.control_id == "AIRM-5.26-RETIREMENT")
        assert result.outcome is Outcome.NOT_APPLICABLE

    def test_retired_without_a_record_fails(self):
        retired = UseCase(id="r", name="R", purpose="p", lifecycle_status=LifecycleStatus.RETIRED)
        report = check_use_case(retired)
        result = next(r for r in report.results if r.control_id == "AIRM-5.26-RETIREMENT")
        assert result.outcome is Outcome.FAIL

    def test_dynamic_updates_need_monitoring(self):
        use_case = UseCase(
            id="d",
            name="D",
            purpose="p",
            auto_updates=True,
            lifecycle_status=LifecycleStatus.DEPLOYED,
        )
        report = check_use_case(use_case)
        result = next(r for r in report.results if r.control_id == "AIRM-5.25-DYNAMIC-UPDATES")
        assert result.outcome is Outcome.FAIL

    def test_embedded_ai_from_material_provider_needs_assurance(self):
        """MAS-AIRM 4.2 fn21."""
        use_case = UseCase(
            id="e",
            name="E",
            purpose="p",
            third_party=[
                ThirdPartyComponent(
                    provider="V",
                    component="ocr",
                    embedded=True,
                    material_provider=True,
                    independent_assessment=False,
                )
            ],
        )
        report = check_use_case(use_case)
        result = next(r for r in report.results if r.control_id == "AIRM-4.2-FN21-EMBEDDED-AI")
        assert result.outcome is Outcome.FAIL


class TestSemiAndDoc:
    def test_semi_controls_never_report_pass(self, credit_use_case):
        """A machine can see the artefact exists; adequacy is a human judgement."""
        report = check_use_case(credit_use_case)
        for result in report.results:
            if result.automatability is Automatability.SEMI:
                assert result.outcome is not Outcome.PASS

    def test_doc_controls_report_attestation_when_applicable(self, credit_use_case):
        report = check_use_case(credit_use_case)
        for result in report.results:
            if (
                result.automatability is Automatability.DOC
                and result.outcome is not Outcome.NOT_APPLICABLE
            ):
                assert result.outcome is Outcome.NEEDS_ATTESTATION

    def test_evidence_changes_the_reason_not_the_outcome(self, credit_use_case):
        control = load_controls().get("AIRM-5.4-DATA-GOVERNANCE")
        assessment = assess(credit_use_case)
        without = control.evaluate(credit_use_case, assessment, {})
        with_evidence = control.evaluate(
            credit_use_case, assessment, dict.fromkeys(control.evidence, "path")
        )
        assert without.outcome is with_evidence.outcome is Outcome.NEEDS_ATTESTATION
        assert "not supplied" in without.reason
        assert "evidence supplied" in with_evidence.reason
        assert with_evidence.evidence_missing == []


class TestReports:
    def test_counts_sum_to_the_catalogue(self, credit_use_case):
        report = check_use_case(credit_use_case)
        use_case_controls = sum(1 for c in load_controls().controls if c.scope is Scope.USE_CASE)
        assert sum(report.counts.values()) == use_case_controls

    def test_applicable_excludes_not_applicable(self, credit_use_case):
        report = check_use_case(credit_use_case)
        assert all(r.outcome is not Outcome.NOT_APPLICABLE for r in report.applicable)

    def test_grouping_by_effective_date(self, agent_use_case):
        groups = check_use_case(agent_use_case).by_effective_date()
        assert set(groups) <= {"2027-10-07", "2028-10-07"}
        assert groups

    def test_check_register_covers_every_use_case(self, register):
        reports = check_register(register)
        assert set(reports) == {uc.id for uc in register.use_cases}

    def test_tier_recorded_in_the_report(self, credit_use_case):
        report = check_use_case(credit_use_case)
        assert report.inherent_tier is Tier.CRITICAL


class TestInstitutionControls:
    def test_missing_control_function_fails(self, credit_use_case):
        bare = Register(institution="T", use_cases=[credit_use_case])
        report = check_institution(bare)
        result = next(r for r in report.results if r.control_id == "AIRM-4.1-FRAMEWORK-PROCESSES")
        assert result.outcome is Outcome.FAIL
        assert "identification" in result.reason

    def test_designated_control_functions_pass(self, register):
        report = check_institution(register)
        result = next(r for r in report.results if r.control_id == "AIRM-4.1-FRAMEWORK-PROCESSES")
        assert result.outcome is Outcome.PASS

    def test_register_linkages(self, register, credit_use_case):
        report = check_institution(register)
        result = next(
            r for r in report.results if r.control_id == "AIRM-4.6-FN23-LINKAGES-DECLARED"
        )
        assert result.outcome is Outcome.PASS

        bare = Register(institution="T", use_cases=[credit_use_case])
        result = next(
            r
            for r in check_institution(bare).results
            if r.control_id == "AIRM-4.6-FN23-LINKAGES-DECLARED"
        )
        assert result.outcome is Outcome.FAIL

    def test_only_institution_scope_controls_evaluated(self, register):
        report = check_institution(register)
        institution_ids = {c.id for c in load_controls().controls if c.scope is Scope.INSTITUTION}
        assert {r.control_id for r in report.results} == institution_ids

    def test_counts_and_failures(self, register):
        report = check_institution(register)
        assert sum(report.counts.values()) == len(report.results)
        assert all(r.outcome is Outcome.FAIL for r in report.failures)


def test_example_portfolio_produces_a_realistic_mix(example_register):
    """The worked example must show pass, fail and attestation, not a wall of one outcome."""
    reports = check_register(example_register)
    totals = {o.value: 0 for o in Outcome}
    for report in reports.values():
        for key, value in report.counts.items():
            totals[key] += value
    assert totals["pass"] > 0
    assert totals["fail"] > 0
    assert totals["needs_attestation"] > 0
    assert totals["not_applicable"] > 0
