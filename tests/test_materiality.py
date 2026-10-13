"""Risk materiality rubric: MAS-AIRM 4.10-4.13."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from airm.inventory import AgentExtension, AutonomyLevel, Register, ReviewStatus, UseCase
from airm.materiality import (
    Dimension,
    Level,
    Rubric,
    Tier,
    assess,
    assess_register,
    load_rubric,
)


class TestLevelsAndTiers:
    def test_level_rank_roundtrip(self):
        for level in Level:
            assert Level.from_rank(level.rank) is level

    def test_level_rank_is_clamped(self):
        assert Level.from_rank(-5) is Level.LOW
        assert Level.from_rank(99) is Level.CRITICAL

    def test_tier_rank_roundtrip(self):
        for tier in Tier:
            assert Tier.from_rank(tier.rank) is tier

    def test_high_materiality_definition(self):
        """MAS-AIRM Section 5 clauses that bind at 'high risk materiality'."""
        assert Tier.HIGH.is_high_materiality
        assert Tier.CRITICAL.is_high_materiality
        assert not Tier.MEDIUM.is_high_materiality
        assert not Tier.LOW.is_high_materiality

    def test_dimension_citations_point_at_4_12(self):
        assert Dimension.IMPACT.citation == "MAS-AIRM §4.12(a)"
        assert Dimension.COMPLEXITY.citation == "MAS-AIRM §4.12(b)"
        assert Dimension.RELIANCE.citation == "MAS-AIRM §4.12(c)"


class TestRubricValidation:
    def test_unknown_combination_rejected(self):
        with pytest.raises(ValidationError, match="unknown combination method"):
            Rubric(combination="magic")

    def test_unknown_residual_floor_rejected(self):
        with pytest.raises(ValidationError, match="unknown residual_floor"):
            Rubric(residual_floor="unlimited")

    def test_signal_without_comparison_raises(self):
        rubric = Rubric(
            signals={Dimension.IMPACT: [{"id": "BAD", "field": "purpose", "level": "high"}]}
        )
        with pytest.raises(ValueError, match="has no comparison clause"):
            rubric.score_dimension(UseCase(id="a", name="A", purpose="p"), Dimension.IMPACT)


class TestDefaultRubric:
    def test_packaged_rubric_loads(self):
        rubric = load_rubric()
        assert rubric.id == "default-v1"
        assert rubric.combination == "max_with_impact_gate"
        assert set(rubric.signals) == set(Dimension)

    def test_every_signal_cites_its_paragraph(self):
        """MISSION: rubric defaults must cite the paragraphs they derive from."""
        rubric = load_rubric()
        for signals in rubric.signals.values():
            for signal in signals:
                assert signal.get("derives_from"), signal["id"]
                assert "MAS-AIRM" in signal["derives_from"], signal["id"]
        for credit in rubric.residual_credits:
            assert "MAS-AIRM" in credit.get("derives_from", ""), credit["id"]

    def test_signal_ids_unique(self):
        rubric = load_rubric()
        ids = [s["id"] for signals in rubric.signals.values() for s in signals]
        ids += [c["id"] for c in rubric.residual_credits]
        assert len(ids) == len(set(ids))

    def test_rubric_roundtrip(self, tmp_path):
        rubric = load_rubric()
        assert Rubric.load(rubric.save(tmp_path / "r.yaml")) == rubric

    def test_load_rejects_non_mapping(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("- a\n")
        with pytest.raises(ValueError, match="mapping at the top level"):
            Rubric.load(path)


class TestScoring:
    def test_scores_carry_reasons(self, credit_use_case):
        """MAS-AIRM 4.13 expects assessments to be clearly documented."""
        assessment = assess(credit_use_case)
        for score in assessment.dimensions.values():
            assert score.reasons
            assert "MAS-AIRM §4.12" in score.citation
        assert assessment.explain()

    def test_credit_model_is_critical_impact(self, credit_use_case):
        assessment = assess(credit_use_case)
        assert assessment.level(Dimension.IMPACT) is Level.CRITICAL
        assert assessment.inherent_tier is Tier.CRITICAL
        assert assessment.is_high_materiality

    def test_agent_raises_complexity_and_reliance(self, agent_use_case):
        assessment = assess(agent_use_case)
        assert assessment.level(Dimension.COMPLEXITY) is Level.CRITICAL
        assert assessment.level(Dimension.RELIANCE) is Level.CRITICAL

    def test_internal_assistive_use_is_lower(self):
        use_case = UseCase(
            id="copilot",
            name="Copilot",
            purpose="Draft internal emails.",
            tags=["internal", "assistive", "productivity"],
            autonomy=AutonomyLevel.ASSISTIVE,
            human_oversight="User reviews the draft.",
            contingency_plan="Write it by hand.",
        )
        assert assess(use_case).level(Dimension.IMPACT) is Level.LOW

    def test_deterministic(self, credit_use_case):
        """MAS-AIRM 5.17: a reviewer must be able to reproduce the rating."""
        first = assess(credit_use_case)
        second = assess(credit_use_case)
        assert first.inherent_tier == second.inherent_tier
        assert first.dimensions == second.dimensions

    def test_assessment_carries_the_disclaimer(self, credit_use_case):
        assert "Response to Feedback §7.19" in assess(credit_use_case).disclaimer

    def test_no_signal_fires_defaults_to_low(self, minimal_use_case):
        score = load_rubric().score_dimension(minimal_use_case, Dimension.IMPACT)
        assert score.level is Level.LOW
        assert "no signal fired" in score.reasons[0]


class TestCombination:
    LEVELS = {
        Dimension.IMPACT: Level.LOW,
        Dimension.COMPLEXITY: Level.CRITICAL,
        Dimension.RELIANCE: Level.CRITICAL,
    }

    def test_impact_gate_caps_secondary_dimensions(self):
        """Response to Feedback 7.9: Complexity is not standalone."""
        tier, how = Rubric(combination="max_with_impact_gate", gate_headroom=1).combine(self.LEVELS)
        assert tier is Tier.MEDIUM
        assert "capped at impact+1" in how

    def test_plain_max_ignores_impact(self):
        tier, _ = Rubric(combination="max").combine(self.LEVELS)
        assert tier is Tier.CRITICAL

    def test_impact_primary_raises_one_level_on_critical_secondary(self):
        tier, _ = Rubric(combination="impact_primary").combine(self.LEVELS)
        assert tier is Tier.MEDIUM

    def test_weighted_method(self):
        tier, how = Rubric(combination="weighted").combine(self.LEVELS)
        assert tier in set(Tier)
        assert "weighted mean" in how

    def test_gate_headroom_zero_pins_to_impact(self):
        tier, _ = Rubric(combination="max_with_impact_gate", gate_headroom=0).combine(self.LEVELS)
        assert tier is Tier.LOW

    def test_generative_use_cases_cannot_be_low(self):
        """A reported finding: GenAI sets Complexity High, and the gate allows Impact+1."""
        use_case = UseCase(
            id="genai-internal",
            name="Internal GenAI",
            purpose="Summarise internal notes.",
            model_type="llm",
            tags=["internal", "assistive"],
            autonomy=AutonomyLevel.ASSISTIVE,
            human_oversight="User reviews.",
            contingency_plan="Do it manually.",
        )
        assessment = assess(use_case)
        assert assessment.level(Dimension.IMPACT) is Level.LOW
        assert assessment.level(Dimension.COMPLEXITY) is Level.HIGH
        assert assessment.inherent_tier is Tier.MEDIUM


class TestResidual:
    def test_controls_reduce_the_tier_by_one_level(self, agent_use_case):
        assessment = assess(agent_use_case)
        assert assessment.inherent_tier is Tier.CRITICAL
        assert assessment.residual_tier is Tier.HIGH

    def test_residual_floor_none_blocks_reduction(self, agent_use_case):
        rubric = load_rubric()
        rubric.residual_floor = "none"
        assessment = rubric.assess(agent_use_case)
        assert assessment.residual_tier == assessment.inherent_tier

    def test_two_level_floor_allows_more_credit(self, agent_use_case):
        rubric = load_rubric()
        rubric.residual_floor = "two_levels"
        assessment = rubric.assess(agent_use_case)
        assert assessment.residual_tier.rank <= Tier.HIGH.rank - 1

    def test_no_credits_leaves_the_tier_unchanged(self):
        use_case = UseCase(
            id="bare", name="Bare", purpose="p", tags=["credit"], affects_individuals=True
        )
        assessment = assess(use_case)
        assert assessment.residual_tier == assessment.inherent_tier
        assert any("no mitigating control credits" in n for n in assessment.mitigation_notes)

    def test_high_materiality_keys_on_inherent(self):
        """Response to Feedback 7.21: high-materiality triggers use inherent materiality."""
        use_case = UseCase(
            id="x",
            name="X",
            purpose="p",
            tags=["credit"],
            affects_individuals=True,
            review_status=ReviewStatus.INDEPENDENT_VALIDATION,
            kill_switch=True,
            contingency_plan="manual",
        )
        assessment = assess(use_case)
        assert assessment.inherent_tier is Tier.CRITICAL
        assert assessment.residual_tier is Tier.HIGH
        assert assessment.is_high_materiality


class TestPortfolio:
    def test_assess_register_covers_every_use_case(self, register):
        portfolio = assess_register(register)
        assert set(portfolio.assessments) == {uc.id for uc in register.use_cases}

    def test_tier_counts_sum_to_the_portfolio(self, example_register):
        portfolio = assess_register(example_register)
        assert sum(portfolio.tier_counts.values()) == len(example_register)

    def test_high_materiality_ids_sorted(self, example_register):
        ids = assess_register(example_register).high_materiality_ids
        assert list(ids) == sorted(ids)

    def test_provider_concentration(self, example_register):
        """MAS-AIRM 3.4 fn18: material use cases dependent on a single provider."""
        portfolio = assess_register(example_register)
        concentration = portfolio.provider_concentration(example_register)
        assert concentration
        assert max(concentration.values()) >= 2

    def test_example_portfolio_spans_tiers(self, example_register):
        """MISSION: the portfolio must span the materiality range."""
        counts = assess_register(example_register).tier_counts
        assert counts["Critical"] >= 1
        assert counts["High"] >= 1
        assert counts["Medium"] >= 1


class TestSignalComparisons:
    """Each comparison form the rubric DSL supports."""

    @pytest.mark.parametrize(
        ("signal", "expected"),
        [
            ({"field": "model_type", "equals": "llm_rag"}, True),
            ({"field": "model_type", "equals": "other"}, False),
            ({"field": "model_type", "in": ["llm_rag", "x"]}, True),
            ({"field": "model_type", "not_in": ["x"]}, True),
            ({"field": "affects_individuals", "is_true": True}, True),
            ({"field": "affects_individuals", "is_false": True}, False),
            ({"field": "tags", "contains_any": ["credit"]}, True),
            ({"field": "tags", "contains_any": ["none"]}, False),
            ({"field": "data_used", "nonempty": True}, True),
            ({"field": "contingency_plan", "empty": True}, True),
            ({"field": "autonomy", "autonomy_at_least": "assistive"}, True),
            ({"field": "autonomy", "autonomy_at_least": "multi_agent"}, False),
            ({"field": "agent.max_steps", "gte": 1}, False),
        ],
    )
    def test_comparison(self, signal, expected):
        use_case = UseCase(
            id="t",
            name="T",
            purpose="p",
            model_type="llm_rag",
            data_used=["d"],
            tags=["credit"],
            affects_individuals=True,
            autonomy=AutonomyLevel.ASSISTIVE,
        )
        rubric = Rubric(signals={Dimension.IMPACT: [{"id": "T", "level": "high", **signal}]})
        score = rubric.score_dimension(use_case, Dimension.IMPACT)
        assert (score.level is Level.HIGH) is expected

    def test_dotted_field_on_agent(self, agent_use_case):
        rubric = Rubric(
            signals={
                Dimension.IMPACT: [
                    {
                        "id": "T",
                        "field": "agent.can_initiate_external_actions",
                        "is_true": True,
                        "level": "critical",
                    }
                ]
            }
        )
        score = rubric.score_dimension(agent_use_case, Dimension.IMPACT)
        assert score.level is Level.CRITICAL
