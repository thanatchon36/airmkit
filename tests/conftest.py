"""Shared fixtures. All data here is synthetic and fictional."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from airm.inventory import (
    AgentExtension,
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

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "synthetic_bank"


@pytest.fixture
def minimal_use_case() -> UseCase:
    """The least an inventory entry can be: id, name and purpose."""
    return UseCase(id="minimal", name="Minimal", purpose="Do one thing.")


@pytest.fixture
def credit_use_case() -> UseCase:
    """A fully populated, validated, human-in-the-loop credit model."""
    return UseCase(
        id="credit-model",
        name="Credit model",
        purpose="Score retail loan applications.",
        approved_scope="SG retail unsecured only",
        jurisdictions=["SG"],
        model_type="gradient_boosting",
        data_used=["bureau_synth"],
        data_classification="confidential",
        processes_personal_data=True,
        dependencies=[Dependency(kind="dataset", name="bureau", identifier="DATA-1")],
        lifecycle_status=LifecycleStatus.DEPLOYED,
        risk_materiality_rating="Critical",
        review_status=ReviewStatus.INDEPENDENT_VALIDATION,
        roles=[
            Role(role="owner", party="Head of Credit", function="Credit Risk"),
            Role(role="developer", party="Modelling", function="Data Science"),
            Role(role="validator", party="Validation unit", function="Model Risk"),
            Role(role="monitor", party="Portfolio Monitoring", function="Credit Risk"),
        ],
        documentation=["docs/model-card.md", "docs/explainability-analysis.md"],
        guardrails=[
            Guardrail(
                name="override band", kind="human_checkpoint", tested=True, evidence_ref="EV-1"
            )
        ],
        autonomy=AutonomyLevel.HUMAN_IN_THE_LOOP,
        human_oversight="Underwriter reviews referred applications.",
        affects_individuals=True,
        contingency_plan="Fall back to the prior scorecard.",
        kill_switch=True,
        tags=["credit"],
        last_reviewed=dt.date(2026, 9, 30),
    )


@pytest.fixture
def agent_use_case() -> UseCase:
    """An agentic use case carrying the MAS-AIRM 4.8 fn25 attributes."""
    return UseCase(
        id="kyc-agent",
        name="KYC agent",
        purpose="Process onboarding documents.",
        approved_scope="SG corporate onboarding",
        model_type="llm_agent",
        data_used=["onboarding_docs_synth"],
        data_classification="confidential",
        processes_personal_data=True,
        lifecycle_status=LifecycleStatus.PILOT,
        risk_materiality_rating="Critical",
        review_status=ReviewStatus.IN_REVIEW,
        roles=[
            Role(role="owner", party="Head of Onboarding"),
            Role(role="developer", party="Agent Platform"),
            Role(role="monitor", party="Onboarding QA"),
        ],
        documentation=["docs/agent-design.md"],
        third_party=[
            ThirdPartyComponent(
                provider="VendorCo",
                component="hosted-llm",
                material_provider=True,
                independent_assessment=True,
                change_notification=True,
            )
        ],
        agent=AgentExtension(
            agent_identifier="AGT-1",
            approved_tools=["ocr", "registry_lookup"],
            systems_accessible=["case_management"],
            permissions=["read:docs", "write:note"],
            components=["planner", "extractor"],
            guardrails=[
                Guardrail(
                    name="tool allowlist",
                    kind="tool_allowlist",
                    tested=True,
                    evidence_ref="EV-2",
                )
            ],
            human_checkpoints=["before case note"],
            max_steps=25,
            can_initiate_external_actions=True,
            trace_logging=True,
        ),
        autonomy=AutonomyLevel.AUTONOMOUS_AGENT,
        human_oversight="Analyst reviews every file.",
        affects_individuals=True,
        contingency_plan="Suspend and revert to manual review.",
        kill_switch=True,
        tags=["agent", "onboarding"],
    )


@pytest.fixture
def register(credit_use_case: UseCase, agent_use_case: UseCase) -> Register:
    """A two-entry register with control functions and linkages declared."""
    return Register(
        institution="Test Bank (fictional)",
        as_of=dt.date(2026, 10, 13),
        linked_registers={"third_party_register": "VEND-id"},
        control_functions={
            "identification": "Model Risk",
            "inventory": "Model Risk",
            "materiality": "Model Risk",
        },
        use_cases=[credit_use_case, agent_use_case],
    )


@pytest.fixture(scope="session")
def example_register() -> Register:
    """The shipped synthetic bank portfolio, so the worked example is covered by tests."""
    return Register.load(EXAMPLE_DIR / "ai-inventory.yaml")
