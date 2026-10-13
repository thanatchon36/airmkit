"""Inventory models: MAS-AIRM 4.5-4.9 and footnote 25."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from airm.inventory import (
    SIGNIFICANT_CHANGE_FIELDS,
    AgentExtension,
    AutonomyLevel,
    Guardrail,
    LifecycleStatus,
    Register,
    ReviewStatus,
    Role,
    ThirdPartyComponent,
    UseCase,
    expected_agent_attributes,
    expected_attributes,
)


class TestEnums:
    def test_lifecycle_live_states(self):
        assert LifecycleStatus.DEPLOYED.is_live
        assert LifecycleStatus.PILOT.is_live
        assert not LifecycleStatus.PROPOSED.is_live
        assert not LifecycleStatus.RETIRED.is_live

    def test_review_independence(self):
        assert ReviewStatus.INDEPENDENT_VALIDATION.is_independent
        assert not ReviewStatus.PEER_REVIEW.is_independent

    def test_autonomy_ordering_and_classification(self):
        ranks = [a.rank for a in AutonomyLevel]
        assert ranks == sorted(ranks) and len(set(ranks)) == len(ranks)
        assert AutonomyLevel.AUTONOMOUS_AGENT.is_agentic
        assert AutonomyLevel.MULTI_AGENT.is_agentic
        assert not AutonomyLevel.AUTONOMOUS_DECISIONING.is_agentic
        assert AutonomyLevel.AUTONOMOUS_DECISIONING.is_autonomous
        assert not AutonomyLevel.HUMAN_OVER_THE_LOOP.is_autonomous


class TestUseCaseValidation:
    def test_agentic_autonomy_requires_agent_extension(self):
        """MAS-AIRM 4.8 fn25 ties agent attributes to agent use cases."""
        with pytest.raises(ValidationError, match="no agent extension"):
            UseCase(id="a", name="A", purpose="p", autonomy=AutonomyLevel.AUTONOMOUS_AGENT)

    def test_agent_extension_requires_agentic_autonomy(self):
        with pytest.raises(ValidationError, match="but autonomy"):
            UseCase(
                id="a",
                name="A",
                purpose="p",
                agent=AgentExtension(agent_identifier="x"),
                autonomy=AutonomyLevel.ASSISTIVE,
            )

    def test_autonomous_decisioning_needs_no_agent_extension(self):
        """A fraud model that blocks without review is autonomous but has no tools."""
        use_case = UseCase(
            id="fraud", name="Fraud", purpose="p", autonomy=AutonomyLevel.AUTONOMOUS_DECISIONING
        )
        assert use_case.agent is None

    def test_unknown_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            UseCase(id="a", name="A", purpose="p", nonexistent_field=1)

    def test_id_must_be_a_slug(self):
        with pytest.raises(ValidationError):
            UseCase(id="Not A Slug", name="A", purpose="p")

    def test_uppercase_id_is_rejected_not_normalised(self):
        """The id is the key other modules and evidence paths use, so it is not rewritten."""
        with pytest.raises(ValidationError):
            UseCase(id="ABC", name="A", purpose="p")

    def test_single_character_id_allowed(self):
        assert UseCase(id="a", name="A", purpose="p").id == "a"


class TestDerivedViews:
    def test_generative_detection_from_model_type(self):
        assert UseCase(id="a", name="A", purpose="p", model_type="llm_rag").is_generative
        assert not UseCase(
            id="b", name="B", purpose="p", model_type="logistic_regression"
        ).is_generative

    def test_generative_detection_from_tags(self):
        assert UseCase(id="a", name="A", purpose="p", tags=["genai"]).is_generative

    def test_agents_are_treated_as_generative(self, agent_use_case):
        assert agent_use_case.is_generative

    def test_catalogue_tags(self, agent_use_case):
        assert set(agent_use_case.catalogue_tags) >= {"agent", "genai", "third-party", "privacy"}

    def test_fairness_relevance_default(self):
        assert UseCase(id="a", name="A", purpose="p", affects_individuals=True).is_fairness_relevant
        assert UseCase(id="b", name="B", purpose="p", tags=["credit"]).is_fairness_relevant
        assert not UseCase(id="c", name="C", purpose="p").is_fairness_relevant

    def test_fairness_relevance_override(self):
        use_case = UseCase(
            id="a", name="A", purpose="p", affects_individuals=True, fairness_relevant=False
        )
        assert not use_case.is_fairness_relevant

    def test_regulated_domain_exposure_requires_external_effect(self):
        """MAS-AIRM 4.12(a): domain adjacency is not consequence."""
        internal = UseCase(
            id="a", name="A", purpose="p", tags=["trading", "internal"], affects_individuals=False
        )
        assert not internal.regulated_domain_exposure
        assert internal.regulated_domain_internal_only

        external = UseCase(id="b", name="B", purpose="p", tags=["credit"], affects_individuals=True)
        assert external.regulated_domain_exposure
        assert not external.regulated_domain_internal_only

        unrelated = UseCase(id="c", name="C", purpose="p", tags=["internal"])
        assert not unrelated.regulated_domain_exposure
        assert not unrelated.regulated_domain_internal_only

    def test_third_party_and_embedded_detection(self):
        use_case = UseCase(
            id="a",
            name="A",
            purpose="p",
            third_party=[ThirdPartyComponent(provider="V", component="c", embedded=True)],
        )
        assert use_case.uses_third_party_ai
        assert use_case.has_embedded_ai

    def test_guardrail_views(self, agent_use_case):
        assert agent_use_case.has_tested_guardrail
        assert agent_use_case.untested_guardrails == ()
        agent_use_case.guardrails = [Guardrail(name="untested", kind="output_filter")]
        assert agent_use_case.untested_guardrails == ("untested",)

    def test_explainability_evidence_detection(self, credit_use_case):
        assert credit_use_case.has_explainability_evidence
        assert not UseCase(
            id="a", name="A", purpose="p", documentation=["readme.md"]
        ).has_explainability_evidence

    def test_role_lookup_is_case_insensitive(self, credit_use_case):
        assert credit_use_case.role_party("OWNER") == "Head of Credit"
        assert credit_use_case.role_party("absent") is None


class TestIndependentValidator:
    def test_validator_distinct_from_development(self, credit_use_case):
        """MAS-AIRM 5.19 and 5.20 fn48: independent of development and deployment."""
        assert credit_use_case.has_independent_validator()

    def test_validator_who_also_developed_is_not_independent(self):
        use_case = UseCase(
            id="a",
            name="A",
            purpose="p",
            roles=[
                Role(role="owner", party="X"),
                Role(role="developer", party="Y"),
                Role(role="validator", party="Y"),
            ],
        )
        assert not use_case.has_independent_validator()

    def test_no_validator_recorded(self):
        assert not UseCase(id="a", name="A", purpose="p").has_independent_validator()


class TestCompleteness:
    def test_minimal_entry_is_incomplete(self, minimal_use_case):
        completeness = minimal_use_case.completeness()
        assert not completeness.is_complete
        assert 0 < completeness.score < 1
        assert "model_type" in completeness.missing

    def test_full_entry_is_complete(self, credit_use_case):
        assert credit_use_case.completeness().is_complete

    def test_agent_attributes_scored_separately(self, agent_use_case):
        completeness = agent_use_case.completeness()
        assert completeness.agent_score == 1.0
        assert completeness.agent_missing == []
        assert "MAS-AIRM §4.8 fn25" in completeness.citations

    def test_missing_agent_attributes_reported(self):
        use_case = UseCase(
            id="a",
            name="A",
            purpose="p",
            autonomy=AutonomyLevel.AUTONOMOUS_AGENT,
            agent=AgentExtension(agent_identifier="x"),
        )
        completeness = use_case.completeness()
        assert set(completeness.agent_missing) == {
            "tools_and_systems_accessible",
            "components",
            "guardrails",
        }

    def test_agent_scoring_can_be_switched_off(self, agent_use_case):
        """docs/INTERPRETATIONS.md I-6 exposes the lenient reading."""
        completeness = agent_use_case.completeness(require_agent_attributes=False)
        assert completeness.agent_score is None

    def test_attribute_names_track_the_catalogue(self):
        assert "risk_materiality_rating" in expected_attributes()
        assert "agent_identifier" in expected_agent_attributes()


class TestRegister:
    def test_duplicate_ids_rejected(self, credit_use_case):
        with pytest.raises(ValidationError, match="duplicate use case id"):
            Register(institution="T", use_cases=[credit_use_case, credit_use_case])

    def test_container_protocol(self, register, credit_use_case):
        assert len(register) == 2
        assert "credit-model" in register
        assert 5 not in register
        assert register.get("credit-model").name == credit_use_case.name
        assert [uc.id for uc in register] == ["credit-model", "kyc-agent"]

    def test_missing_use_case_raises(self, register):
        with pytest.raises(KeyError, match="no such use case"):
            register.get("absent")

    def test_live_and_agentic_views(self, register):
        assert {uc.id for uc in register.live()} == {"credit-model", "kyc-agent"}
        assert {uc.id for uc in register.agentic()} == {"kyc-agent"}

    def test_third_party_providers(self, register):
        assert register.third_party_providers() == {"VendorCo": ["kyc-agent"]}

    def test_missing_control_functions(self, register, credit_use_case):
        """MAS-AIRM 4.3, 4.9 and 4.13 each expect a designated control function."""
        assert register.missing_control_functions() == ()
        bare = Register(institution="T", use_cases=[credit_use_case])
        assert bare.missing_control_functions() == ("identification", "inventory", "materiality")

    def test_completeness_across_register(self, register):
        scores = register.completeness()
        assert set(scores) == {"credit-model", "kyc-agent"}

    def test_roundtrip_yaml(self, register, tmp_path):
        path = register.save(tmp_path / "r.yaml")
        assert Register.load(path) == register

    def test_roundtrip_json(self, register, tmp_path):
        path = register.save(tmp_path / "r.json")
        assert Register.load(path) == register

    def test_load_rejects_non_mapping(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("- just\n- a\n- list\n")
        with pytest.raises(ValueError, match="expected a mapping"):
            Register.load(path)

    def test_from_use_cases(self, credit_use_case):
        assert len(Register.from_use_cases("T", [credit_use_case])) == 1


class TestDiff:
    def test_identical_registers(self, register):
        assert register.diff(register).is_empty

    def test_added_and_removed(self, register, credit_use_case):
        smaller = Register(institution="T", use_cases=[credit_use_case])
        diff = register.diff(smaller)
        assert diff.removed == ["kyc-agent"]
        assert diff.added == []
        assert smaller.diff(register).added == ["kyc-agent"]

    def test_significant_change_detected(self, register):
        """MAS-AIRM 5.25(a): a scope change is significant and needs re-approval."""
        changed = register.model_copy(deep=True)
        changed.get("credit-model").approved_scope = "Expanded to SME lending"
        diff = register.diff(changed)
        assert diff.changed["credit-model"] == ["approved_scope"]
        assert diff.significant["credit-model"] == ["approved_scope"]
        assert "MAS-AIRM §5.25(a)" in diff.citations

    def test_insignificant_change_not_flagged(self, register):
        changed = register.model_copy(deep=True)
        changed.get("credit-model").notes = "a note"
        diff = register.diff(changed)
        assert diff.changed["credit-model"] == ["notes"]
        assert "credit-model" not in diff.significant

    def test_agent_tool_change_is_significant(self, register):
        """Tools granted to an agent are a significant change (INTERPRETATIONS I-10)."""
        changed = register.model_copy(deep=True)
        agent = changed.get("kyc-agent").agent
        assert agent is not None
        agent.approved_tools = [*agent.approved_tools, "wire_transfer"]
        assert "agent" in register.diff(changed).significant["kyc-agent"]

    def test_significant_fields_cover_the_llm_and_agent_surface(self):
        assert {"autonomy", "agent", "guardrails", "third_party"} <= SIGNIFICANT_CHANGE_FIELDS


class TestAgentExtension:
    def test_untested_guardrails(self):
        agent = AgentExtension(
            agent_identifier="a",
            guardrails=[
                Guardrail(name="ok", kind="output_filter", tested=True),
                Guardrail(name="nope", kind="input_filter"),
            ],
        )
        assert agent.untested_guardrails == ("nope",)


def test_example_portfolio_is_valid(example_register):
    """The shipped worked example must stay loadable and internally consistent."""
    assert len(example_register) == 8
    assert example_register.missing_control_functions() == ()
    assert len(example_register.agentic()) == 2
    assert example_register.as_of == dt.date(2026, 10, 13)
