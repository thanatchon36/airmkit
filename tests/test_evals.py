"""Eval adapters, fairness, tool-scope audit and the guardrail probe suite."""

from __future__ import annotations

import json

import pytest

from airm.evals import (
    EvalResult,
    FailureMode,
    MetricResult,
    fairness_from_metrics,
    footnote_46_modes,
    from_deepeval,
    from_garak,
    from_inspect,
    from_promptfoo,
    from_ragas,
    tool_scope_audit,
)
from airm.evals.probes import (
    MAX_OVER_REFUSAL,
    SYNTH_PII,
    TIER_ASR_THRESHOLDS,
    GuardrailPattern,
    MockBackend,
    ProbeFamily,
    default_probes,
    run_suite,
    wilson_interval,
)
from airm.inventory import AgentExtension, AutonomyLevel, UseCase
from airm.materiality import Tier


class TestFailureModes:
    def test_footnote_46_modes_match_the_catalogue(self):
        modes = footnote_46_modes()
        assert set(modes) == {
            FailureMode.HALLUCINATION,
            FailureMode.UNDESIRABLE_CONTENT,
            FailureMode.BIAS,
            FailureMode.DATA_LEAKAGE,
            FailureMode.ADVERSARIAL_VULNERABILITY,
        }

    def test_tool_misuse_is_flagged_as_an_addition(self):
        """MAS-AIRM 5.15 fn46 does not name tool misuse; 1.11 is its basis."""
        assert not FailureMode.TOOL_MISUSE.in_footnote_46
        assert FailureMode.TOOL_MISUSE.citation == "MAS-AIRM §1.11"
        assert FailureMode.HALLUCINATION.citation == "MAS-AIRM §5.15 fn46"


class TestMetricResult:
    def test_higher_is_better(self):
        assert MetricResult(name="m", value=0.9, threshold=0.8).passed is True
        assert MetricResult(name="m", value=0.7, threshold=0.8).passed is False

    def test_lower_is_better(self):
        metric = MetricResult(name="asr", value=0.03, threshold=0.05, direction="lower_is_better")
        assert metric.passed is True
        assert metric.verdict == "pass"

    def test_no_threshold_means_no_verdict(self):
        """MAS-AIRM 5.14(a) makes the threshold an agreement; the toolkit cannot invent one."""
        metric = MetricResult(name="m", value=0.9)
        assert metric.passed is None
        assert metric.verdict == "no_threshold"


class TestEvalResult:
    def test_failure_rate_and_verdicts(self):
        result = EvalResult(
            source="t",
            use_case_id="x",
            total=100,
            failures=7,
            metrics=[MetricResult(name="m", value=0.9, threshold=0.95)],
        )
        assert result.failure_rate == 0.07
        assert result.any_failed
        assert result.verdicts == {"m": "fail"}

    def test_missing_counts_give_no_rate(self):
        assert EvalResult(source="t", use_case_id="x").failure_rate is None

    def test_thresholds_missing_is_reported(self):
        result = EvalResult(
            source="t", use_case_id="x", metrics=[MetricResult(name="m", value=1.0)]
        )
        assert result.thresholds_missing == ("m",)

    def test_uncovered_failure_modes(self):
        result = EvalResult(
            source="t", use_case_id="x", failure_modes_covered=[FailureMode.HALLUCINATION]
        )
        assert FailureMode.BIAS in result.uncovered_failure_modes()
        assert FailureMode.HALLUCINATION not in result.uncovered_failure_modes()

    def test_metric_lookup(self):
        result = EvalResult(
            source="t", use_case_id="x", metrics=[MetricResult(name="m", value=1.0)]
        )
        assert result.metric("m").value == 1.0
        with pytest.raises(KeyError, match="no metric named"):
            result.metric("absent")


class TestAdapters:
    def test_inspect_log(self, tmp_path):
        path = tmp_path / "log.json"
        path.write_text(
            json.dumps(
                {
                    "eval": {
                        "run_id": "r1",
                        "model": "ollama/qwen3.5:0.8b",
                        "task": "faithfulness",
                        "model_args": {"revision": "abc123"},
                        "config": {"generate_config": {"seed": 7, "temperature": 0.0}},
                    },
                    "results": {
                        "total_samples": 50,
                        "completed_samples": 50,
                        "scores": [{"name": "accuracy", "metrics": {"mean": {"value": 0.82}}}],
                    },
                }
            )
        )
        result = from_inspect(path, use_case_id="x", thresholds={"accuracy.mean": 0.8})
        assert result.source == "inspect-ai"
        assert result.model == "ollama/qwen3.5:0.8b"
        assert result.model_digest == "abc123"
        assert result.seed == 7
        assert result.metric("accuracy.mean").verdict == "pass"

    def test_promptfoo_output(self, tmp_path):
        path = tmp_path / "pf.json"
        path.write_text(
            json.dumps(
                {
                    "results": {
                        "stats": {"successes": 18, "failures": 2},
                        "results": [
                            {
                                "metadata": {"pluginId": "prompt-injection"},
                                "gradingResult": {
                                    "componentResults": [{"assertion": {"type": "llm-rubric"}}]
                                },
                            }
                        ],
                    }
                }
            )
        )
        result = from_promptfoo(path, use_case_id="x", thresholds={"attack_success_rate": 0.05})
        assert result.metric("pass_rate").value == pytest.approx(0.9)
        assert result.metric("attack_success_rate").verdict == "fail"
        assert FailureMode.ADVERSARIAL_VULNERABILITY in result.failure_modes_covered

    def test_garak_jsonl(self, tmp_path):
        path = tmp_path / "garak.jsonl"
        path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {"entry_type": "start_run setup", "plugins.model_name": "qwen3.5:0.8b"}
                    ),
                    json.dumps(
                        {
                            "entry_type": "eval",
                            "probe": "promptinject.HijackHateHumans",
                            "passed": 18,
                            "total": 20,
                        }
                    ),
                    json.dumps(
                        {
                            "entry_type": "eval",
                            "probe": "leakreplay.LiteratureCloze",
                            "passed": 15,
                            "total": 20,
                        }
                    ),
                    "not json at all",
                ]
            )
            + "\n"
        )
        result = from_garak(path, use_case_id="x", thresholds={"attack_success_rate": 0.05})
        assert result.model == "qwen3.5:0.8b"
        assert result.failure_rate == pytest.approx(0.175)
        assert FailureMode.DATA_LEAKAGE in result.failure_modes_covered
        assert FailureMode.ADVERSARIAL_VULNERABILITY in result.failure_modes_covered
        assert result.metric("asr.leakreplay.LiteratureCloze").value == pytest.approx(0.25)

    def test_garak_unknown_probe_is_not_forced_into_a_category(self, tmp_path):
        """Overstating coverage of footnote 46 would be worse than admitting a gap."""
        path = tmp_path / "g.jsonl"
        path.write_text(
            json.dumps(
                {"entry_type": "eval", "probe": "somethingnovel.Probe", "passed": 10, "total": 10}
            )
            + "\n"
        )
        result = from_garak(path, use_case_id="x")
        assert result.failure_modes_covered == []

    def test_ragas_scores(self):
        result = from_ragas(
            {"faithfulness": 0.93, "answer_relevancy": 0.88},
            use_case_id="x",
            thresholds={"faithfulness": 0.9},
            n=120,
            model="qwen3.5:0.8b",
        )
        assert result.metric("faithfulness").verdict == "pass"
        assert FailureMode.HALLUCINATION in result.failure_modes_covered

    def test_ragas_rejects_unknown_metric_only_in_fairness(self):
        result = from_ragas({"context_recall": 0.8}, use_case_id="x")
        assert result.failure_modes_covered == []

    def test_deepeval_results(self):
        result = from_deepeval(
            [
                {"name": "HallucinationMetric", "score": 0.08, "threshold": 0.1, "success": True},
                {"name": "ToxicityMetric", "score": 0.3, "threshold": 0.1, "success": False},
                {"name": "unparseable"},
            ],
            use_case_id="x",
        )
        assert result.total == 2
        assert result.failures == 1
        assert result.metric("ToxicityMetric").direction == "lower_is_better"
        assert FailureMode.UNDESIRABLE_CONTENT in result.failure_modes_covered


class TestFairness:
    def test_disparity_ratio(self):
        """MAS-AIRM 5.8 with Response 10.21: the FI names the metric and the threshold."""
        result = fairness_from_metrics(
            {"a": {"approval_rate": 0.62}, "b": {"approval_rate": 0.47}},
            use_case_id="credit",
            metric="approval_rate",
            max_disparity=0.8,
            protected_attribute="age_band",
        )
        metric = result.metric("disparity_ratio.age_band.approval_rate")
        assert metric.value == pytest.approx(0.7581, abs=1e-3)
        assert metric.verdict == "fail"
        assert "MAS-AIRM §5.8 fn36" in result.notes[0]

    def test_no_threshold_records_without_judging(self):
        result = fairness_from_metrics(
            {"a": {"r": 0.5}, "b": {"r": 0.5}},
            use_case_id="x",
            metric="r",
            protected_attribute="g",
        )
        assert result.metric("disparity_ratio.g.r").verdict == "no_threshold"

    def test_missing_metric_raises(self):
        with pytest.raises(ValueError, match="no group carries the metric"):
            fairness_from_metrics(
                {"a": {"other": 1.0}}, use_case_id="x", metric="r", protected_attribute="g"
            )

    def test_per_group_values_are_recorded(self):
        result = fairness_from_metrics(
            {"a": {"r": 0.6}, "b": {"r": 0.5}},
            use_case_id="x",
            metric="r",
            protected_attribute="g",
        )
        assert result.metric("r.a").value == 0.6
        assert result.metric("r.b").value == 0.5


class TestToolScopeAudit:
    def test_unapproved_tool_detected(self, agent_use_case):
        """MAS-AIRM 5.23(a) with 4.8 fn25: observed tools against approved scope."""
        audit = tool_scope_audit(agent_use_case, ["ocr", "wire_transfer"], calls=40)
        assert audit.unapproved == ["wire_transfer"]
        assert not audit.within_scope
        assert "outside its approved scope" in audit.finding

    def test_within_scope_and_least_privilege_hint(self, agent_use_case):
        audit = tool_scope_audit(agent_use_case, ["ocr"], calls=10)
        assert audit.within_scope
        assert audit.unused == ["registry_lookup"]
        assert "least privilege" in audit.finding

    def test_exact_scope_match(self, agent_use_case):
        audit = tool_scope_audit(agent_use_case, ["ocr", "registry_lookup"], calls=5)
        assert audit.within_scope
        assert audit.unused == []
        assert "within approved scope" in audit.finding

    def test_non_agent_use_case_raises(self, credit_use_case):
        with pytest.raises(ValueError, match="no agent extension"):
            tool_scope_audit(credit_use_case, ["x"])

    def test_duplicate_observations_collapse(self, agent_use_case):
        audit = tool_scope_audit(agent_use_case, ["ocr", "ocr", "ocr"], calls=3)
        assert audit.observed == ["ocr"]
        assert audit.calls == 3


class TestWilson:
    def test_zero_successes_upper_bound(self):
        lower, upper = wilson_interval(0, 20)
        assert lower == 0.0
        assert upper == pytest.approx(0.161, abs=1e-3)

    def test_interval_contains_the_estimate(self):
        lower, upper = wilson_interval(5, 20)
        assert lower < 0.25 < upper

    def test_bounds_are_clamped(self):
        lower, upper = wilson_interval(20, 20)
        assert lower == pytest.approx(0.839, abs=1e-3)
        assert upper == pytest.approx(1.0)
        assert 0.0 <= lower <= upper <= 1.0

    def test_zero_trials_is_uninformative(self):
        assert wilson_interval(0, 0) == (0.0, 1.0)


class TestProbes:
    def test_probe_set_shape(self):
        probes = default_probes()
        assert len(probes) == 20
        families = {p.family for p in probes}
        assert families == set(ProbeFamily)
        for family in ProbeFamily:
            assert sum(1 for p in probes if p.family is family) == 4

    def test_every_probe_cites_its_technique(self):
        for probe in default_probes():
            assert probe.technique
            assert probe.reference

    def test_benign_controls_measure_over_refusal(self):
        """A guardrail that refuses everything is not an effective guardrail."""
        controls = [p for p in default_probes() if p.family.is_control]
        assert len(controls) == 4
        assert all(p.family.failure_mode is None for p in controls)

    def test_pii_probes_use_a_synthetic_identifier(self):
        """MISSION: no real institution data anywhere."""
        assert SYNTH_PII.startswith("SYNTH-PII-")
        pii = [p for p in default_probes() if p.family is ProbeFamily.PII_LEAKAGE]
        assert all(SYNTH_PII in (p.context or "") for p in pii)

    def test_detection_is_deterministic(self):
        probe = next(p for p in default_probes() if p.id == "II-01")
        assert probe.detect("INJECTED")
        assert not probe.detect("Here is a summary of the complaint.")


class TestSuite:
    def test_suite_runs_offline_by_default(self):
        result = run_suite()
        assert result.backend["backend"] == "mock"
        assert "not measurements" in result.backend["warning"]
        assert len(result.runs) == len(GuardrailPattern)

    def test_guardrails_reduce_attack_success(self):
        result = run_suite()
        unguarded = result.run(GuardrailPattern.NONE).asr()[0]
        layered = result.run(GuardrailPattern.LAYERED).asr()[0]
        assert layered <= unguarded

    def test_asr_table_shape(self):
        table = run_suite().asr_table()
        assert set(table) == {p.value for p in GuardrailPattern}
        for row in table.values():
            assert "overall" in row
            assert "over_refusal" in row

    def test_small_samples_cannot_claim_a_strict_tier(self):
        """The Wilson upper bound stops 0/16 from certifying a 1% threshold."""
        result = run_suite()
        run = result.run(GuardrailPattern.LAYERED)
        assert run.asr()[0] == 0.0
        assert not run.meets_tier(Tier.CRITICAL)

    def test_tier_thresholds_are_ordered(self):
        thresholds = [TIER_ASR_THRESHOLDS[t] for t in Tier]
        assert thresholds == sorted(thresholds, reverse=True)
        assert 0 < MAX_OVER_REFUSAL < 1

    def test_eval_result_conversion_labels_the_threshold_as_a_proposal(self):
        result = run_suite()
        eval_result = result.to_eval_result("x", GuardrailPattern.FILTER)
        assert eval_result.source == "airm-probes/filter"
        assert "not a MAS value" in eval_result.metric("attack_success_rate").note
        assert "authors' proposal" in eval_result.notes[0]

    def test_unknown_pattern_raises(self):
        result = run_suite(patterns=[GuardrailPattern.NONE])
        with pytest.raises(KeyError, match="was not run"):
            result.run(GuardrailPattern.LAYERED)

    def test_progress_callback_is_called(self):
        seen: list[str] = []
        run_suite(
            probes=default_probes()[:2],
            patterns=[GuardrailPattern.NONE],
            on_probe=lambda probe, pattern: seen.append(probe.id),
        )
        assert seen == ["DJ-01", "DJ-02"]

    def test_mock_backend_respects_the_system_prompt(self):
        backend = MockBackend(complies_with={"DJ-01"}, respects_system=True)
        result = run_suite(
            backend=backend,
            probes=[p for p in default_probes() if p.id == "DJ-01"],
            patterns=[GuardrailPattern.NONE, GuardrailPattern.SYSTEM_PROMPT],
        )
        assert result.run(GuardrailPattern.NONE).asr()[0] == 1.0
        assert result.run(GuardrailPattern.SYSTEM_PROMPT).asr()[0] == 0.0

    def test_input_filter_blocks_before_the_model_is_called(self):
        result = run_suite(
            probes=[p for p in default_probes() if p.id == "II-01"],
            patterns=[GuardrailPattern.FILTER],
        )
        outcome = result.run(GuardrailPattern.FILTER).outcomes[0]
        assert outcome.blocked_by in ("input_filter", "output_filter")
        assert not outcome.succeeded

    def test_pattern_descriptions_exist(self):
        for pattern in GuardrailPattern:
            assert pattern.description
