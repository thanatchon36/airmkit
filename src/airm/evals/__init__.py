"""Adapters mapping existing evaluation-tool output onto MAS-AIRM controls.

Serves MAS-AIRM §5.14 (evaluation measures and thresholds, testing approaches), §5.15 with
footnote 46 (key failure modes of Generative AI and agents, and the effectiveness of associated
guardrails), §5.8 (fairness assessments) and §5.23(a) (monitoring agent reasoning, actions and
tools against approved scope).

**This module is not an evaluation framework and must not become one.** The MISSION is explicit:
build adapters to `inspect-ai`, `promptfoo`, `deepeval`, `ragas` and `garak` rather than a new
harness. The value this toolkit adds is the mapping from a tool's output to a MAS control and an
evidence record, which is exactly what those tools do not do.

The one thing this module does run is :mod:`airm.evals.probes`, a guardrail *probe runner*. It
orchestrates prompts against a local or mocked backend and records outcomes; it implements no
metrics, no scoring models and no attack generation beyond a fixed, published probe list. It
exists because MAS-AIRM §5.15 expects guardrail effectiveness to be measured and no existing tool
reports results in a form a control catalogue can consume.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from airm.catalog import cite, load_catalogue
from airm.inventory import UseCase

__all__ = [
    "EvalResult",
    "FailureMode",
    "MetricResult",
    "ToolScopeAudit",
    "fairness_from_metrics",
    "from_deepeval",
    "from_garak",
    "from_inspect",
    "from_promptfoo",
    "from_ragas",
    "tool_scope_audit",
]


class FailureMode(StrEnum):
    """The Generative AI failure modes MAS-AIRM §5.15 footnote 46 names.

    Footnote 46: "for Generative AI, evaluation and testing should pay greater attention to
    hallucinations, generation of undesirable content such as toxic, harmful or biased content,
    bias, data leakages or disclosures, and vulnerability to adversarial attacks."

    ``TOOL_MISUSE`` is not in footnote 46. It is added for agents, whose risk §1.11 describes as
    autonomously executing "unauthorised or erroneous actions", and is labelled as an addition
    wherever it is reported.
    """

    HALLUCINATION = "hallucination"
    UNDESIRABLE_CONTENT = "undesirable_content"
    BIAS = "bias"
    DATA_LEAKAGE = "data_leakage"
    ADVERSARIAL_VULNERABILITY = "adversarial_vulnerability"
    TOOL_MISUSE = "tool_misuse"

    @property
    def in_footnote_46(self) -> bool:
        """Whether MAS-AIRM §5.15 footnote 46 names this mode."""
        return self is not FailureMode.TOOL_MISUSE

    @property
    def citation(self) -> str:
        """Return the citation for this failure mode."""
        if self.in_footnote_46:
            return cite("5.15", footnote=46)
        return cite("1.11")


def footnote_46_modes() -> tuple[FailureMode, ...]:
    """Return the failure modes footnote 46 names, read from the clause catalogue."""
    named = set(load_catalogue().genai_failure_modes())
    return tuple(m for m in FailureMode if m.value in named)


class _Model(BaseModel):
    """Base model forbidding unknown fields."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class MetricResult(_Model):
    """One measured metric with its threshold and verdict.

    MAS-AIRM §5.14(a) expects "acceptable performance thresholds" that are "clearly defined,
    documented, and mutually agreed upon by business owners, developers and reviewers". MAS sets no
    values (Response to Feedback §10.29), so the threshold must come from the FI; when none is
    supplied the metric is recorded without a verdict rather than silently judged.
    """

    name: str
    value: float
    threshold: float | None = None
    direction: str = Field(
        default="higher_is_better",
        description="'higher_is_better' or 'lower_is_better'; decides how threshold is applied.",
    )
    unit: str | None = None
    n: int | None = Field(default=None, description="Sample size, for interval reporting.")
    failure_mode: FailureMode | None = None
    note: str | None = None

    @property
    def passed(self) -> bool | None:
        """Whether the metric meets its threshold, or None if no threshold was supplied."""
        if self.threshold is None:
            return None
        if self.direction == "lower_is_better":
            return self.value <= self.threshold
        return self.value >= self.threshold

    @property
    def verdict(self) -> str:
        """Return 'pass', 'fail' or 'no_threshold'."""
        passed = self.passed
        if passed is None:
            return "no_threshold"
        return "pass" if passed else "fail"


class EvalResult(_Model):
    """A normalised evaluation result from any supported tool.

    This is the shape every adapter produces, and the shape :mod:`airm.controls` and
    :mod:`airm.monitor` consume. ``model`` and ``model_digest`` are mandatory-by-convention for
    reproducibility: MAS-AIRM §5.17 as clarified by Response to Feedback §10.44 expects the
    *evaluation and testing process* to be replicable even where outputs are non-deterministic,
    which requires knowing which model version produced them.
    """

    source: str = Field(description="Tool that produced the result, e.g. 'garak', 'inspect-ai'.")
    use_case_id: str
    run_id: str | None = None
    ran_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(tz=dt.UTC))
    model: str | None = Field(default=None, description="Model identifier under test.")
    model_digest: str | None = Field(
        default=None, description="Model digest or quantisation, for reproducibility (§5.17)."
    )
    seed: int | None = None
    temperature: float | None = None
    dataset: str | None = Field(default=None, description="Dataset or probe set used (§5.14(b)).")
    metrics: list[MetricResult] = Field(default_factory=list)
    failure_modes_covered: list[FailureMode] = Field(default_factory=list)
    total: int | None = None
    failures: int | None = None
    clauses: list[str] = Field(default_factory=list)
    raw_ref: str | None = Field(
        default=None, description="Path to the tool's own output, kept as primary evidence."
    )
    notes: list[str] = Field(default_factory=list)

    @property
    def failure_rate(self) -> float | None:
        """Failures over total, or None if the counts were not reported."""
        if self.total in (None, 0) or self.failures is None:
            return None
        assert self.total is not None
        return self.failures / self.total

    @property
    def verdicts(self) -> dict[str, str]:
        """Metric name to verdict."""
        return {m.name: m.verdict for m in self.metrics}

    @property
    def any_failed(self) -> bool:
        """Whether any metric with a threshold failed it (MAS-AIRM §5.14(a))."""
        return any(m.passed is False for m in self.metrics)

    @property
    def thresholds_missing(self) -> tuple[str, ...]:
        """Metrics recorded with no agreed threshold.

        Reported rather than defaulted: §5.14(a) makes the threshold an agreement between business
        owners, developers and reviewers, which a toolkit cannot manufacture.
        """
        return tuple(m.name for m in self.metrics if m.threshold is None)

    def uncovered_failure_modes(self) -> tuple[FailureMode, ...]:
        """Return the footnote 46 failure modes this result does not cover (MAS-AIRM §5.15)."""
        covered = set(self.failure_modes_covered)
        return tuple(m for m in footnote_46_modes() if m not in covered)

    def metric(self, name: str) -> MetricResult:
        """Return one metric by name.

        Raises:
            KeyError: If the result has no such metric.
        """
        for candidate in self.metrics:
            if candidate.name == name:
                return candidate
        raise KeyError(f"no metric named {name!r} in this result")


def _load_json(path: str | Path) -> Any:
    """Read a JSON or JSONL file produced by an eval tool.

    Tool output is untrusted data: it is parsed, never evaluated, and a JSONL file is read line by
    line so that one malformed record does not discard the run.
    """
    target = Path(path)
    text = target.read_text(encoding="utf-8", errors="replace")
    if target.suffix == ".jsonl":
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return records
    return json.loads(text)


def _promptfoo_provider(results: Mapping[str, Any]) -> str | None:
    """Extract the provider label from a promptfoo results table, if present."""
    table = results.get("table")
    if not isinstance(table, dict):
        return None
    prompts = (table.get("head", {}) or {}).get("prompts") or []
    if prompts and isinstance(prompts[0], dict):
        provider = prompts[0].get("provider")
        return str(provider) if provider else None
    return None


def _thresholds(spec: Mapping[str, float] | None, name: str) -> float | None:
    """Look up a threshold for a metric, returning None when the FI supplied none."""
    return None if spec is None else spec.get(name)


# --------------------------------------------------------------------------- adapters


def from_inspect(
    path: str | Path,
    *,
    use_case_id: str,
    thresholds: Mapping[str, float] | None = None,
) -> EvalResult:
    """Adapt an ``inspect-ai`` JSON eval log.

    Serves MAS-AIRM §5.14. Reads the exported JSON log format (``inspect view``/``--log-format
    json``): ``eval`` metadata plus ``results.scores[].metrics``.

    Args:
        path: Path to the exported JSON log.
        use_case_id: Use case the evaluation belongs to.
        thresholds: Metric name to agreed threshold (MAS-AIRM §5.14(a)).

    Returns:
        A normalised :class:`EvalResult`.
    """
    data = _load_json(path)
    header = data.get("eval", {}) if isinstance(data, dict) else {}
    results = data.get("results", {}) if isinstance(data, dict) else {}
    model_args = header.get("model_args", {}) or {}
    generate = (header.get("config", {}) or {}).get("generate_config", {}) or {}

    metrics: list[MetricResult] = []
    for score in results.get("scores", []) or []:
        scorer = score.get("name") or score.get("scorer") or "score"
        for metric_name, metric in (score.get("metrics", {}) or {}).items():
            value = metric.get("value") if isinstance(metric, dict) else metric
            if not isinstance(value, (int, float)):
                continue
            full = f"{scorer}.{metric_name}"
            metrics.append(
                MetricResult(
                    name=full,
                    value=float(value),
                    threshold=_thresholds(thresholds, full) or _thresholds(thresholds, metric_name),
                    direction="higher_is_better",
                    n=results.get("completed_samples") or results.get("total_samples"),
                )
            )
    return EvalResult(
        source="inspect-ai",
        use_case_id=use_case_id,
        run_id=header.get("run_id") or header.get("eval_id"),
        model=header.get("model"),
        model_digest=model_args.get("model_digest") or model_args.get("revision"),
        seed=generate.get("seed"),
        temperature=generate.get("temperature"),
        dataset=(header.get("dataset", {}) or {}).get("name") or header.get("task"),
        metrics=metrics,
        total=results.get("total_samples"),
        failures=results.get("errors") if isinstance(results.get("errors"), int) else None,
        clauses=[cite("5.14"), cite("5.14", item="a")],
        raw_ref=str(path),
    )


def from_promptfoo(
    path: str | Path,
    *,
    use_case_id: str,
    thresholds: Mapping[str, float] | None = None,
) -> EvalResult:
    """Adapt a ``promptfoo eval --output results.json`` file.

    Serves MAS-AIRM §5.14(b) (testing approaches) and §5.15 where red-team probes are used.
    Reads ``results.stats`` for pass/fail counts and the per-assertion names for coverage.
    """
    data = _load_json(path)
    results = data.get("results", data) if isinstance(data, dict) else {}
    stats = results.get("stats", {}) or {}
    successes = int(stats.get("successes", 0) or 0)
    failures = int(stats.get("failures", 0) or 0)
    total = successes + failures

    assertion_names: set[str] = set()
    modes: set[FailureMode] = set()
    for row in results.get("results", []) or []:
        for component in (row.get("gradingResult", {}) or {}).get("componentResults", []) or []:
            assertion = (component.get("assertion", {}) or {}).get("type")
            if assertion:
                assertion_names.add(str(assertion))
        for key in ("pluginId", "plugin", "harmCategory"):
            value = (row.get("metadata", {}) or {}).get(key)
            if value:
                mode = _map_probe_to_mode(str(value))
                if mode:
                    modes.add(mode)

    metrics = [
        MetricResult(
            name="pass_rate",
            value=(successes / total) if total else 0.0,
            threshold=_thresholds(thresholds, "pass_rate"),
            direction="higher_is_better",
            n=total or None,
        )
    ]
    if total:
        metrics.append(
            MetricResult(
                name="attack_success_rate",
                value=failures / total,
                threshold=_thresholds(thresholds, "attack_success_rate"),
                direction="lower_is_better",
                n=total,
                failure_mode=FailureMode.ADVERSARIAL_VULNERABILITY,
            )
        )
    return EvalResult(
        source="promptfoo",
        use_case_id=use_case_id,
        model=_promptfoo_provider(results),
        dataset=", ".join(sorted(assertion_names)) or None,
        metrics=metrics,
        failure_modes_covered=sorted(modes, key=lambda m: m.value),
        total=total or None,
        failures=failures or None,
        clauses=[cite("5.14", item="b"), cite("5.15")],
        raw_ref=str(path),
    )


def from_garak(
    path: str | Path,
    *,
    use_case_id: str,
    thresholds: Mapping[str, float] | None = None,
) -> EvalResult:
    """Adapt a ``garak`` report JSONL file.

    Serves MAS-AIRM §5.15 with footnote 46 and §5.22(b) (adversarial testing). garak writes one
    JSON object per line; ``entry_type: "eval"`` records carry probe, detector, passed and total.
    """
    records = _load_json(path)
    if isinstance(records, dict):
        records = [records]

    model = None
    per_probe: dict[str, tuple[int, int]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("entry_type") == "start_run setup":
            model = record.get("plugins.model_name") or record.get("model_name")
        if record.get("entry_type") == "eval":
            probe = str(record.get("probe", "unknown"))
            passed = int(record.get("passed", 0) or 0)
            total = int(record.get("total", 0) or 0)
            previous = per_probe.get(probe, (0, 0))
            per_probe[probe] = (previous[0] + passed, previous[1] + total)

    metrics: list[MetricResult] = []
    modes: set[FailureMode] = set()
    total_all = 0
    failed_all = 0
    for probe, (passed, total) in sorted(per_probe.items()):
        if not total:
            continue
        failed = total - passed
        total_all += total
        failed_all += failed
        mode = _map_probe_to_mode(probe)
        if mode:
            modes.add(mode)
        metrics.append(
            MetricResult(
                name=f"asr.{probe}",
                value=failed / total,
                threshold=_thresholds(thresholds, f"asr.{probe}")
                or _thresholds(thresholds, "attack_success_rate"),
                direction="lower_is_better",
                n=total,
                failure_mode=mode,
            )
        )
    if total_all:
        metrics.insert(
            0,
            MetricResult(
                name="attack_success_rate",
                value=failed_all / total_all,
                threshold=_thresholds(thresholds, "attack_success_rate"),
                direction="lower_is_better",
                n=total_all,
                failure_mode=FailureMode.ADVERSARIAL_VULNERABILITY,
            ),
        )
    return EvalResult(
        source="garak",
        use_case_id=use_case_id,
        model=model,
        dataset=", ".join(sorted(per_probe)) or None,
        metrics=metrics,
        failure_modes_covered=sorted(modes, key=lambda m: m.value),
        total=total_all or None,
        failures=failed_all or None,
        clauses=[cite("5.15", footnote=46), cite("5.22", item="b")],
        raw_ref=str(path),
    )


def from_ragas(
    scores: Mapping[str, float],
    *,
    use_case_id: str,
    thresholds: Mapping[str, float] | None = None,
    n: int | None = None,
    model: str | None = None,
    raw_ref: str | None = None,
) -> EvalResult:
    """Adapt ``ragas`` scores for a retrieval-augmented use case.

    Serves MAS-AIRM §5.15 footnote 46, specifically the hallucination limb: ragas ``faithfulness``
    measures whether the answer is grounded in the retrieved context.

    Args:
        scores: Metric name to value, as ``ragas.evaluate(...).to_pandas().mean()`` gives.
        use_case_id: Use case the evaluation belongs to.
        thresholds: Agreed thresholds (MAS-AIRM §5.14(a)).
        n: Number of samples.
        model: Model under test.
        raw_ref: Path to the ragas output kept as primary evidence.

    Returns:
        A normalised :class:`EvalResult`.
    """
    mapping = {
        "faithfulness": FailureMode.HALLUCINATION,
        "answer_correctness": FailureMode.HALLUCINATION,
        "factual_correctness": FailureMode.HALLUCINATION,
        "answer_relevancy": None,
        "context_precision": None,
        "context_recall": None,
    }
    metrics = [
        MetricResult(
            name=name,
            value=float(value),
            threshold=_thresholds(thresholds, name),
            direction="higher_is_better",
            n=n,
            failure_mode=mapping.get(name),
        )
        for name, value in sorted(scores.items())
    ]
    modes = sorted(
        {m for name in scores if (m := mapping.get(name)) is not None}, key=lambda m: m.value
    )
    return EvalResult(
        source="ragas",
        use_case_id=use_case_id,
        model=model,
        metrics=metrics,
        failure_modes_covered=modes,
        total=n,
        clauses=[cite("5.14", item="a"), cite("5.15", footnote=46)],
        raw_ref=raw_ref,
    )


def from_deepeval(
    results: Iterable[Mapping[str, Any]],
    *,
    use_case_id: str,
    thresholds: Mapping[str, float] | None = None,
    model: str | None = None,
    raw_ref: str | None = None,
) -> EvalResult:
    """Adapt ``deepeval`` test results.

    Serves MAS-AIRM §5.14 and §5.15 footnote 46. Accepts an iterable of mappings with ``name``,
    ``score``, ``threshold`` and ``success``, which is the shape deepeval's metric results expose.
    """
    mapping = {
        "hallucination": FailureMode.HALLUCINATION,
        "faithfulness": FailureMode.HALLUCINATION,
        "toxicity": FailureMode.UNDESIRABLE_CONTENT,
        "bias": FailureMode.BIAS,
        "pii": FailureMode.DATA_LEAKAGE,
        "prompt_injection": FailureMode.ADVERSARIAL_VULNERABILITY,
        "jailbreak": FailureMode.ADVERSARIAL_VULNERABILITY,
    }
    metrics: list[MetricResult] = []
    modes: set[FailureMode] = set()
    failures = 0
    total = 0
    for row in results:
        name = str(row.get("name") or row.get("metric") or "metric")
        score = row.get("score")
        if not isinstance(score, (int, float)):
            continue
        total += 1
        mode = next((v for k, v in mapping.items() if k in name.lower()), None)
        if mode:
            modes.add(mode)
        lower_is_better = any(
            k in name.lower() for k in ("hallucination", "toxicity", "bias", "injection")
        )
        threshold = row.get("threshold")
        metrics.append(
            MetricResult(
                name=name,
                value=float(score),
                threshold=float(threshold)
                if isinstance(threshold, (int, float))
                else _thresholds(thresholds, name),
                direction="lower_is_better" if lower_is_better else "higher_is_better",
                failure_mode=mode,
            )
        )
        if row.get("success") is False:
            failures += 1
    return EvalResult(
        source="deepeval",
        use_case_id=use_case_id,
        model=model,
        metrics=metrics,
        failure_modes_covered=sorted(modes, key=lambda m: m.value),
        total=total or None,
        failures=failures or None,
        clauses=[cite("5.14"), cite("5.15", footnote=46)],
        raw_ref=raw_ref,
    )


def fairness_from_metrics(
    group_metrics: Mapping[str, Mapping[str, float]],
    *,
    use_case_id: str,
    metric: str,
    max_disparity: float | None = None,
    protected_attribute: str,
    raw_ref: str | None = None,
) -> EvalResult:
    """Build a fairness result from per-group metric values.

    Serves MAS-AIRM §5.8: "assessing whether the use of AI leads to systematic disadvantages for
    specific groups using appropriate fairness metrics, and documenting the results". Response to
    Feedback §10.21 is explicit that "there is no single universally applicable metric or approach
    for measuring fairness", so this function does not choose a metric: the caller names it and
    supplies the disparity threshold from the FI's own fairness methodology.

    The reported statistic is the max-min ratio across groups, the shape both the Veritas
    fairness methodology and the common disparate-impact test use.

    Args:
        group_metrics: Group name to a mapping of metric name to value.
        use_case_id: Use case the assessment belongs to.
        metric: Which metric in ``group_metrics`` to compare across groups.
        max_disparity: Maximum acceptable ratio of the worst group to the best, per the FI's
            fairness methodology. None records the measurement without a verdict.
        protected_attribute: The attribute the groups partition (MAS-AIRM §5.8, fn36).
        raw_ref: Path to the underlying fairness analysis.

    Returns:
        An :class:`EvalResult` whose metrics carry the per-group values and the disparity ratio.
    """
    values = {
        group: float(metrics[metric])
        for group, metrics in group_metrics.items()
        if metric in metrics
    }
    if not values:
        raise ValueError(f"no group carries the metric {metric!r}")
    best = max(values.values())
    worst = min(values.values())
    ratio = (worst / best) if best else 0.0

    metrics_out = [
        MetricResult(
            name=f"disparity_ratio.{protected_attribute}.{metric}",
            value=round(ratio, 4),
            threshold=max_disparity,
            direction="higher_is_better",
            failure_mode=FailureMode.BIAS,
            note=(
                "min/max of the metric across groups; the FI's fairness methodology supplies the "
                "threshold, since MAS prescribes no metric (Response to Feedback §10.21)"
            ),
        )
    ]
    metrics_out.extend(
        MetricResult(
            name=f"{metric}.{group}",
            value=value,
            direction="higher_is_better",
            failure_mode=FailureMode.BIAS,
        )
        for group, value in sorted(values.items())
    )
    return EvalResult(
        source="fairness",
        use_case_id=use_case_id,
        dataset=f"groups: {', '.join(sorted(values))}",
        metrics=metrics_out,
        failure_modes_covered=[FailureMode.BIAS],
        clauses=[cite("5.8"), cite("5.8", footnote=36), cite("5.7")],
        raw_ref=raw_ref,
        notes=[
            f"protected attribute: {protected_attribute}; "
            f"{cite('5.8', footnote=36)} also requires proxies and highly correlated attributes "
            f"to be considered"
        ],
    )


class ToolScopeAudit(_Model):
    """Comparison of an agent's observed tool use against its approved scope.

    Serves MAS-AIRM §4.8 footnote 25 (the tools and systems the agent can access are inventory
    attributes), §5.23(a) (monitor "actions taken, tools used") and §5.16(b) (least privilege).
    This is the check that makes "monitoring of scope adherence" (§4.7) real for agents: the
    inventory declares the approved tools, the trace shows the used tools, and the difference is
    the finding.
    """

    use_case_id: str
    agent_identifier: str | None = None
    approved: list[str] = Field(default_factory=list)
    observed: list[str] = Field(default_factory=list)
    unapproved: list[str] = Field(default_factory=list)
    unused: list[str] = Field(default_factory=list)
    calls: int = 0
    clauses: list[str] = Field(
        default_factory=lambda: [
            cite("4.8", footnote=25),
            cite("5.23", item="a"),
            cite("5.16", item="b"),
        ]
    )

    @property
    def within_scope(self) -> bool:
        """Whether every observed tool was approved."""
        return not self.unapproved

    @property
    def finding(self) -> str:
        """Return the finding a reviewer should see."""
        if self.unapproved:
            return (
                f"agent used {len(self.unapproved)} tool(s) outside its approved scope: "
                f"{', '.join(self.unapproved)} ({cite('5.23', item='a')})"
            )
        if self.unused:
            return (
                f"all {self.calls} call(s) within approved scope; "
                f"{len(self.unused)} approved tool(s) never used, so least privilege could be "
                f"tightened ({cite('5.16', item='b')}): {', '.join(self.unused)}"
            )
        return f"all {self.calls} call(s) within approved scope"


def tool_scope_audit(
    use_case: UseCase,
    observed_tools: Iterable[str],
    *,
    calls: int | None = None,
) -> ToolScopeAudit:
    """Audit an agent's observed tool use against the approved scope in its inventory entry.

    Serves MAS-AIRM §5.23(a) with §4.8 footnote 25.

    Args:
        use_case: The inventory entry, which must carry an agent extension.
        observed_tools: Tool names seen in a trace. Treated as untrusted data: names are compared
            as strings and never resolved or invoked.
        calls: Total number of tool calls observed, if known.

    Returns:
        A :class:`ToolScopeAudit`.

    Raises:
        ValueError: If the use case has no agent extension to audit against.

    Examples:
        >>> from airm.inventory import AgentExtension, AutonomyLevel, UseCase
        >>> uc = UseCase(id="a", name="A", purpose="p", autonomy=AutonomyLevel.AUTONOMOUS_AGENT,
        ...              agent=AgentExtension(agent_identifier="ag-1", approved_tools=["search"]))
        >>> tool_scope_audit(uc, ["search", "wire_transfer"]).unapproved
        ['wire_transfer']
    """
    if use_case.agent is None:
        raise ValueError(
            f"use case {use_case.id!r} has no agent extension; nothing to audit against "
            f"({cite('4.8', footnote=25)})"
        )
    observed = sorted({str(t) for t in observed_tools})
    approved = sorted({str(t) for t in use_case.agent.approved_tools})
    return ToolScopeAudit(
        use_case_id=use_case.id,
        agent_identifier=use_case.agent.agent_identifier,
        approved=approved,
        observed=observed,
        unapproved=sorted(set(observed) - set(approved)),
        unused=sorted(set(approved) - set(observed)),
        calls=calls if calls is not None else len(observed),
    )


def _map_probe_to_mode(probe: str) -> FailureMode | None:
    """Map a probe or plugin name from an eval tool to a MAS-AIRM footnote 46 failure mode.

    The mapping is deliberately conservative: an unrecognised probe returns None rather than being
    forced into a category, so that :meth:`EvalResult.uncovered_failure_modes` does not overstate
    coverage of footnote 46.
    """
    name = probe.lower()
    table: tuple[tuple[tuple[str, ...], FailureMode], ...] = (
        (
            ("hallucin", "misleading", "snowball", "package", "factual", "groundedness"),
            FailureMode.HALLUCINATION,
        ),
        (
            (
                "toxic",
                "harmful",
                "realtoxicity",
                "profanity",
                "slur",
                "harassment",
                "violence",
                "self-harm",
                "unsafe",
            ),
            FailureMode.UNDESIRABLE_CONTENT,
        ),
        (("bias", "stereotyp", "discrimin", "winobias", "fairness"), FailureMode.BIAS),
        (
            ("leak", "pii", "privacy", "disclos", "extract", "memoriz", "replay", "secret"),
            FailureMode.DATA_LEAKAGE,
        ),
        (
            (
                "inject",
                "jailbreak",
                "dan",
                "promptinject",
                "encoding",
                "suffix",
                "gcg",
                "glitch",
                "adversar",
                "manipul",
                "evasion",
                "poison",
                "escape",
                "ascii",
            ),
            FailureMode.ADVERSARIAL_VULNERABILITY,
        ),
        (
            ("tool", "excessive-agency", "agency", "rbac", "ssrf", "shell", "sql-injection"),
            FailureMode.TOOL_MISUSE,
        ),
    )
    for needles, mode in table:
        if any(needle in name for needle in needles):
            return mode
    return None
