"""Third-party AI assessments: MAS-AIRM 5.10-5.11."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from airm.thirdparty import (
    Assurance,
    Consideration,
    ConsiderationRecord,
    ConsiderationStatus,
    Decision,
    VendorAssessment,
    VendorRegister,
)


def record(consideration, status, finding="f", controls=None):
    return ConsiderationRecord(
        consideration=consideration,
        status=status,
        finding=finding,
        compensating_controls=controls or [],
    )


class TestEnums:
    def test_all_eight_considerations_map_to_5_11_items(self):
        letters = {c.citation for c in Consideration}
        assert len(letters) == 8
        assert "MAS-AIRM §5.11(a)" in letters
        assert "MAS-AIRM §5.11(h)" in letters

    def test_each_consideration_has_a_description(self):
        for consideration in Consideration:
            assert consideration.description

    def test_independence_line_matches_response_9_9(self):
        """Self-attestation is not independent assurance."""
        assert Assurance.CERTIFICATION.is_independent
        assert Assurance.INDEPENDENT_ASSESSMENT.is_independent
        assert not Assurance.SELF_ATTESTATION.is_independent
        assert not Assurance.FI_OWN_TESTING.is_independent
        assert not Assurance.NONE.is_independent

    def test_decision_permits_use(self):
        assert Decision.ONBOARD.permits_use
        assert Decision.LIMIT.permits_use
        assert not Decision.SUSPEND.permits_use
        assert not Decision.REJECT.permits_use

    def test_gap_statuses(self):
        assert ConsiderationStatus.NOT_MET.is_gap
        assert ConsiderationStatus.PARTIALLY_MET.is_gap
        assert not ConsiderationStatus.MET.is_gap
        assert not ConsiderationStatus.NOT_RELEVANT.is_gap


class TestAssessmentValidation:
    def test_outside_appetite_cannot_be_plainly_onboarded(self):
        """MAS-AIRM 5.11 expects limit, suspend or replace instead."""
        with pytest.raises(ValidationError, match="expects the service to be limited"):
            VendorAssessment(
                id="v",
                provider="P",
                component="c",
                residual_within_appetite=False,
                decision=Decision.ONBOARD,
            )

    def test_outside_appetite_with_limit_is_allowed(self):
        assessment = VendorAssessment(
            id="v",
            provider="P",
            component="c",
            residual_within_appetite=False,
            decision=Decision.LIMIT,
        )
        assert assessment.decision is Decision.LIMIT

    def test_duplicate_assessment_ids_rejected(self):
        assessment = VendorAssessment(id="v", provider="P", component="c")
        with pytest.raises(ValidationError, match="duplicate vendor assessment id"):
            VendorRegister(institution="T", assessments=[assessment, assessment])


class TestFindings:
    def test_self_attestation_is_a_finding(self):
        assessment = VendorAssessment(
            id="v", provider="P", component="c", assurance=Assurance.SELF_ATTESTATION
        )
        findings = assessment.findings()
        assert any("self-attestation" in f for f in findings)
        assert assessment.relies_on_self_attestation

    def test_certification_without_a_scope_is_a_finding(self):
        """A certificate of unknown scope is not assurance about the AI risks."""
        assessment = VendorAssessment(
            id="v", provider="P", component="c", assurance=Assurance.CERTIFICATION
        )
        assert any("scope is not recorded" in f for f in assessment.findings())
        assert not assessment.has_independent_assurance

    def test_certification_with_scope_is_independent_assurance(self):
        assessment = VendorAssessment(
            id="v",
            provider="P",
            component="c",
            assurance=Assurance.CERTIFICATION,
            assurance_scope="Covers data governance and model validation.",
        )
        assert assessment.has_independent_assurance

    def test_missing_fi_testing_is_a_finding(self):
        """MAS-AIRM 5.10: test third-party AI in the FI's own use case context."""
        assessment = VendorAssessment(id="v", provider="P", component="c")
        assert any("§5.10" in f for f in assessment.findings())

    def test_unmitigated_gap_is_a_finding(self):
        assessment = VendorAssessment(
            id="v",
            provider="P",
            component="c",
            considerations=[record(Consideration.TRANSPARENCY, ConsiderationStatus.NOT_MET)],
        )
        assert any("no compensating control" in f for f in assessment.findings())
        assert len(assessment.unmitigated_gaps()) == 1

    def test_mitigated_gap_is_not_an_unmitigated_finding(self):
        assessment = VendorAssessment(
            id="v",
            provider="P",
            component="c",
            considerations=[
                record(
                    Consideration.TRANSPARENCY,
                    ConsiderationStatus.PARTIALLY_MET,
                    controls=["additional testing on the FI's own data"],
                )
            ],
        )
        assert assessment.unmitigated_gaps() == ()
        assert len(assessment.gaps()) == 1

    def test_unaddressed_considerations_are_findings(self):
        assessment = VendorAssessment(id="v", provider="P", component="c")
        assert len(assessment.missing_considerations()) == 8
        assert assessment.coverage() == 0.0

    def test_full_coverage(self):
        assessment = VendorAssessment(
            id="v",
            provider="P",
            component="c",
            considerations=[record(c, ConsiderationStatus.MET) for c in Consideration],
        )
        assert assessment.coverage() == 1.0
        assert assessment.missing_considerations() == ()

    def test_embedded_material_provider_without_assurance(self):
        """MAS-AIRM 4.2 fn21."""
        assessment = VendorAssessment(
            id="v",
            provider="P",
            component="ocr",
            embedded=True,
            material_provider=True,
            fi_testing_done=True,
        )
        assert any("fn21" in f for f in assessment.findings())

    def test_overdue_review_is_a_finding(self):
        assessment = VendorAssessment(
            id="v",
            provider="P",
            component="c",
            fi_testing_done=True,
            review_due=dt.date(2020, 1, 1),
        )
        assert assessment.is_overdue()
        assert any("§5.24" in f for f in assessment.findings())

    def test_not_overdue_when_no_due_date(self):
        assert not VendorAssessment(id="v", provider="P", component="c").is_overdue()


class TestRegister:
    @pytest.fixture
    def vendor_register(self) -> VendorRegister:
        return VendorRegister(
            institution="T",
            assessments=[
                VendorAssessment(
                    id="a",
                    provider="BigVendor",
                    component="llm",
                    use_case_ids=["x", "y", "z"],
                    assurance=Assurance.CERTIFICATION,
                    assurance_scope="scope",
                    fi_testing_done=True,
                ),
                VendorAssessment(
                    id="b",
                    provider="SmallVendor",
                    component="ocr",
                    use_case_ids=["x"],
                    assurance=Assurance.SELF_ATTESTATION,
                    review_due=dt.date(2020, 1, 1),
                ),
            ],
        )

    def test_lookup(self, vendor_register):
        assert len(vendor_register) == 2
        assert vendor_register.get("a").provider == "BigVendor"
        with pytest.raises(KeyError, match="no such vendor assessment"):
            vendor_register.get("absent")

    def test_for_use_case(self, vendor_register):
        assert {a.id for a in vendor_register.for_use_case("x")} == {"a", "b"}
        assert {a.id for a in vendor_register.for_use_case("y")} == {"a"}

    def test_concentration_sorted_by_exposure(self, vendor_register):
        """MAS-AIRM 5.11(c)."""
        concentration = vendor_register.concentration()
        assert list(concentration) == ["BigVendor", "SmallVendor"]
        assert concentration["BigVendor"] == 3

    def test_self_attested_only(self, vendor_register):
        assert [a.id for a in vendor_register.self_attested_only()] == ["b"]

    def test_overdue(self, vendor_register):
        assert [a.id for a in vendor_register.overdue()] == ["b"]

    def test_all_findings(self, vendor_register):
        """Both assessments have findings here; the self-attested one has strictly more."""
        findings = vendor_register.all_findings()
        assert set(findings) == {"a", "b"}
        assert len(findings["b"]) > len(findings["a"])
        assert any("self-attestation" in f for f in findings["b"])
        assert not any("self-attestation" in f for f in findings["a"])

    def test_roundtrip(self, vendor_register, tmp_path):
        path = vendor_register.save(tmp_path / "v.yaml")
        assert VendorRegister.load(path) == vendor_register

    def test_load_rejects_non_mapping(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("- a\n")
        with pytest.raises(ValueError, match="expected a mapping"):
            VendorRegister.load(path)


def test_example_vendor_register_is_consistent():
    """The worked example includes a vendor whose residual risk is outside appetite."""
    from tests.conftest import EXAMPLE_DIR

    register = VendorRegister.load(EXAMPLE_DIR / "third-party-assessments.yaml")
    assert len(register) == 3
    limited = [a for a in register.assessments if a.decision is Decision.LIMIT]
    assert len(limited) == 1
    assert limited[0].residual_within_appetite is False
    assert register.self_attested_only()
