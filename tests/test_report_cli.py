"""Audit pack generation and the command-line interface."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from airm.catalog import load_catalogue
from airm.cli import app
from airm.controls import load_controls
from airm.inventory import Register
from airm.report import AuditPack, build_pack, clause_index_markdown, to_docx
from airm.thirdparty import VendorRegister
from tests.conftest import EXAMPLE_DIR

runner = CliRunner()


@pytest.fixture(scope="module")
def pack(example_register_module) -> AuditPack:
    return AuditPack(
        example_register_module,
        vendors=VendorRegister.load(EXAMPLE_DIR / "third-party-assessments.yaml"),
    )


@pytest.fixture(scope="module")
def example_register_module() -> Register:
    return Register.load(EXAMPLE_DIR / "ai-inventory.yaml")


class TestClauseIndex:
    def test_every_paragraph_appears(self):
        """The docs-site clause index must be generated, never hand-maintained."""
        text = clause_index_markdown()
        for paragraph in load_catalogue().paragraphs:
            assert f"**§{paragraph.id}**" in text

    def test_normative_footnotes_listed(self):
        text = clause_index_markdown()
        assert "**fn25**" in text
        assert "**fn46**" in text

    def test_uncovered_expectations_are_published(self):
        """The toolkit prefers a traceable catalogue to a complete-looking one."""
        text = clause_index_markdown()
        assert "no implementing control" in text
        assert "**§2.2**" in text

    def test_summaries_are_flagged_as_paraphrase(self):
        assert "authors' paraphrase" in clause_index_markdown()


class TestDocuments:
    def test_every_document_carries_the_disclaimer(self, pack):
        for document in (
            pack.board_summary(),
            pack.inventory_register(),
            pack.materiality_report(),
            pack.applicability_statement(),
            pack.gap_analysis(),
            pack.crosswalk_report(),
        ):
            assert "not affiliated with MAS" in document
            assert "Response to Feedback §7.19" in document

    def test_inventory_register_shows_agent_attributes(self, pack):
        text = pack.inventory_register()
        assert "Agent attributes (§4.8 footnote 25)" in text
        assert "AGT-KYC-001" in text

    def test_inventory_register_shows_control_functions(self, pack):
        assert "Designated control functions" in pack.inventory_register()

    def test_materiality_report_shows_reasons(self, pack):
        """MAS-AIRM 4.13: assessments must be clearly documented."""
        text = pack.materiality_report()
        assert "## Reasons" in text
        assert "MAS-AIRM §4.12(a)" in text
        assert "IMP-DOMAIN-CRITICAL" in text

    def test_applicability_statement_explains_exclusions(self, pack):
        """MAS-AIRM 5.2 expects risks from non-application to be identified."""
        text = pack.applicability_statement()
        assert "n/a" in text
        assert "applies only to" in text

    def test_gap_analysis_splits_by_effective_date(self, pack):
        text = pack.gap_analysis()
        assert "Due 2027-10-07 (Sections 3-4)" in text
        assert "Due 2028-10-07 (Sections 5-6)" in text
        assert "Response to Feedback §13.5" in text

    def test_gap_analysis_prioritises_high_materiality(self, pack):
        assert "Priority: high-materiality lifecycle gaps" in pack.gap_analysis()

    def test_board_summary_separates_fail_from_attestation(self, pack):
        """A semi control that passed is not a missing control."""
        text = pack.board_summary()
        assert "What the toolkit cannot tell you" in text
        assert "Decisions needed" in text

    def test_board_summary_names_the_concentration(self, pack):
        assert "NorthStar AI" in pack.board_summary()

    def test_crosswalk_report_lists_the_residue(self, pack):
        text = pack.crosswalk_report()
        assert "no full mapping in any framework" in text

    def test_vendor_report_surfaces_self_attestation(self, pack):
        text = pack._vendor_report()
        assert "self-attestations" in text
        assert "Concentration (§5.11(c))" in text


class TestSummaryJson:
    def test_shape(self, pack):
        summary = pack.summary_json()
        assert summary["catalogue"]["expectations"] == 51
        assert summary["controls"]["total"] == len(load_controls())
        assert sum(summary["portfolio"]["tier_counts"].values()) == 8
        assert set(summary["results"]) == {uc.id for uc in pack.register.use_cases}
        assert "union" in summary["crosswalk"]

    def test_disclaimer_travels_with_the_numbers(self, pack):
        assert "not affiliated" in pack.summary_json()["disclaimer"]

    def test_json_serialisable(self, pack):
        json.dumps(pack.summary_json())


class TestWrite:
    def test_writes_every_document(self, example_register_module, tmp_path):
        written = build_pack(
            example_register_module,
            tmp_path,
            vendors=VendorRegister.load(EXAMPLE_DIR / "third-party-assessments.yaml"),
        )
        assert "00-board-summary.md" in written
        assert "summary.json" in written
        assert "07-third-party-assessments.md" in written
        for path in written.values():
            assert path.is_file()
            assert path.stat().st_size > 0

    def test_pack_without_vendors_omits_that_document(self, example_register_module, tmp_path):
        written = build_pack(example_register_module, tmp_path)
        assert "07-third-party-assessments.md" not in written

    def test_docx_conversion(self, example_register_module, tmp_path):
        written = build_pack(example_register_module, tmp_path)
        target = to_docx(written["00-board-summary.md"], tmp_path / "out.docx")
        assert target.is_file()
        assert target.stat().st_size > 0


class TestCli:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "airmkit" in result.stdout
        assert "d9a40955" in result.stdout

    def test_init_scaffolds_a_register(self, tmp_path):
        target = tmp_path / "reg.yaml"
        result = runner.invoke(
            app,
            [
                "init",
                "-i",
                "Test Bank",
                "-o",
                str(target),
                "--rubric-out",
                str(tmp_path / "r.yaml"),
            ],
        )
        assert result.exit_code == 0
        register = Register.load(target)
        assert register.institution == "Test Bank"
        assert register.missing_control_functions(), "scaffold must leave gaps visible"

    def test_init_refuses_to_overwrite(self, tmp_path):
        target = tmp_path / "reg.yaml"
        runner.invoke(app, ["init", "-o", str(target)])
        result = runner.invoke(app, ["init", "-o", str(target)])
        assert result.exit_code == 2
        assert runner.invoke(app, ["init", "-o", str(target), "--force"]).exit_code == 0

    def test_missing_register_is_a_usage_error(self, tmp_path):
        result = runner.invoke(app, ["assess", "-r", str(tmp_path / "absent.yaml")])
        assert result.exit_code == 2

    def test_malformed_register_is_a_usage_error(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("institution: 5\nuse_cases: not-a-list\n")
        assert runner.invoke(app, ["assess", "-r", str(bad)]).exit_code == 2

    def test_assess(self):
        result = runner.invoke(
            app, ["assess", "-r", str(EXAMPLE_DIR / "ai-inventory.yaml"), "--explain"]
        )
        assert result.exit_code == 0
        assert "Risk materiality" in result.stdout
        assert "MAS-AIRM §4.12" in result.stdout

    def test_assess_one_use_case(self):
        result = runner.invoke(
            app,
            ["assess", "-r", str(EXAMPLE_DIR / "ai-inventory.yaml"), "-u", "kyc-document-agent"],
        )
        assert result.exit_code == 0

    def test_assess_unknown_use_case(self):
        result = runner.invoke(
            app, ["assess", "-r", str(EXAMPLE_DIR / "ai-inventory.yaml"), "-u", "absent"]
        )
        assert result.exit_code == 2

    def test_assess_writes_ratings(self, tmp_path, example_register_module):
        target = tmp_path / "r.yaml"
        stripped = example_register_module.model_copy(deep=True)
        for use_case in stripped.use_cases:
            use_case.risk_materiality_rating = None
        stripped.save(target)
        result = runner.invoke(app, ["assess", "-r", str(target), "--write"])
        assert result.exit_code == 0
        assert all(uc.risk_materiality_rating for uc in Register.load(target).use_cases)

    def test_check_exits_nonzero_on_failures(self):
        """The command must be usable as a pipeline gate."""
        result = runner.invoke(app, ["check", "-r", str(EXAMPLE_DIR / "ai-inventory.yaml")])
        assert result.exit_code == 1
        assert "FAIL" in result.stdout

    def test_check_institution_only(self):
        result = runner.invoke(
            app, ["check", "-r", str(EXAMPLE_DIR / "ai-inventory.yaml"), "--institution"]
        )
        assert "Institution-level controls" in result.stdout

    def test_check_reads_evidence_from_the_trail(self, tmp_path):
        """Evidence recorded in the trail must reach the control evaluation."""

        def run(with_trail: bool) -> dict:
            target = tmp_path / f"out-{with_trail}.json"
            args = [
                "check",
                "-r",
                str(EXAMPLE_DIR / "ai-inventory.yaml"),
                "-u",
                "credit-decision-model",
                "--json",
                str(target),
            ]
            if with_trail:
                args += ["--trail", str(EXAMPLE_DIR / "evidence" / "trail.jsonl")]
            runner.invoke(app, args)
            return json.loads(target.read_text())["credit-decision-model"]

        without = run(False)
        with_evidence = run(True)
        missing_without = sum(len(r["evidence_missing"]) for r in without["results"])
        missing_with = sum(len(r["evidence_missing"]) for r in with_evidence["results"])
        found_with = sum(len(r["evidence_found"]) for r in with_evidence["results"])
        assert found_with > 0
        assert missing_with < missing_without

    def test_check_json_output(self, tmp_path):
        target = tmp_path / "out.json"
        runner.invoke(
            app,
            ["check", "-r", str(EXAMPLE_DIR / "ai-inventory.yaml"), "--json", str(target)],
        )
        assert json.loads(target.read_text())

    def test_scan(self, tmp_path):
        (tmp_path / "app.py").write_text("import anthropic\n")
        out = tmp_path / "candidates.yaml"
        result = runner.invoke(
            app, ["scan", str(tmp_path), "--out", str(out), "--json", str(tmp_path / "s.json")]
        )
        assert result.exit_code == 0
        assert "not an inventory" in result.stdout
        assert "UNTRIAGED" in Register.load(out).institution

    def test_scan_clean_tree(self, tmp_path):
        result = runner.invoke(app, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "no signals found" in result.stdout

    def test_scan_rejects_bad_confidence(self, tmp_path):
        assert runner.invoke(app, ["scan", str(tmp_path), "--min-confidence", "x"]).exit_code == 2

    def test_report(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "report",
                "-r",
                str(EXAMPLE_DIR / "ai-inventory.yaml"),
                "--vendors",
                str(EXAMPLE_DIR / "third-party-assessments.yaml"),
                "--trail",
                str(EXAMPLE_DIR / "evidence" / "trail.jsonl"),
                "-o",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "00-board-summary.md").is_file()
        assert (tmp_path / "summary.json").is_file()

    def test_gap(self):
        result = runner.invoke(app, ["gap", "-r", str(EXAMPLE_DIR / "ai-inventory.yaml")])
        assert result.exit_code == 0
        assert "Due 2027-10-07" in result.stdout

    def test_crosswalk_summary(self, tmp_path):
        result = runner.invoke(app, ["crosswalk", "--json", str(tmp_path / "c.json")])
        assert result.exit_code == 0
        assert "UNION" in result.stdout
        assert json.loads((tmp_path / "c.json").read_text())["coverage"]

    def test_crosswalk_one_clause(self):
        result = runner.invoke(app, ["crosswalk", "--clause", "5.19"])
        assert result.exit_code == 0
        assert "MAS-AIRM §5.19" in result.stdout

    def test_crosswalk_unknown_clause(self):
        assert runner.invoke(app, ["crosswalk", "--clause", "9.9"]).exit_code == 2

    def test_crosswalk_reverse_lookup(self):
        result = runner.invoke(app, ["crosswalk", "--framework", "iso_42001", "--ref", "A.6.2.4"])
        assert result.exit_code == 0
        assert "maps to" in result.stdout

    def test_crosswalk_reverse_lookup_needs_a_framework(self):
        assert runner.invoke(app, ["crosswalk", "--ref", "A.6.2.4"]).exit_code == 2

    def test_crosswalk_unknown_framework(self):
        result = runner.invoke(app, ["crosswalk", "--framework", "nope", "--ref", "x"])
        assert result.exit_code == 2

    def test_crosswalk_residual_work(self):
        result = runner.invoke(app, ["crosswalk", "--holding", "iso_42001"])
        assert result.exit_code == 0
        assert "Residual work" in result.stdout

    def test_crosswalk_bad_holding(self):
        assert runner.invoke(app, ["crosswalk", "--holding", "nope"]).exit_code == 2

    def test_clauses_table_and_markdown(self, tmp_path):
        assert runner.invoke(app, ["clauses", "--tag", "agent"]).exit_code == 0
        assert runner.invoke(app, ["clauses", "--section", "5", "--expectations"]).exit_code == 0
        target = tmp_path / "index.md"
        runner.invoke(app, ["clauses", "--format", "markdown", "--out", str(target)])
        assert "**§5.19**" in target.read_text()

    def test_evidence_append_and_verify(self, tmp_path):
        trail = tmp_path / "trail.jsonl"
        evidence_file = tmp_path / "report.md"
        evidence_file.write_text("synthetic")
        append = runner.invoke(
            app,
            [
                "evidence",
                "guardrail_test",
                "--summary",
                "probes run",
                "--trail",
                str(trail),
                "--use-case",
                "x",
                "--item",
                f"guardrail_test_report={evidence_file}",
                "--outcome",
                "pass",
            ],
        )
        assert append.exit_code == 0
        assert "sha256:" in append.stdout
        assert (
            runner.invoke(
                app, ["evidence", "review", "-s", "s", "--trail", str(trail), "--verify"]
            ).exit_code
            == 0
        )

    def test_evidence_verify_detects_a_changed_file(self, tmp_path):
        trail = tmp_path / "trail.jsonl"
        evidence_file = tmp_path / "report.md"
        evidence_file.write_text("original")
        runner.invoke(
            app,
            [
                "evidence",
                "review",
                "-s",
                "s",
                "--trail",
                str(trail),
                "--item",
                f"report={evidence_file}",
            ],
        )
        evidence_file.write_text("tampered")
        result = runner.invoke(
            app, ["evidence", "review", "-s", "s", "--trail", str(trail), "--verify"]
        )
        assert result.exit_code == 1

    def test_evidence_verify_detects_a_broken_chain(self, tmp_path):
        trail = tmp_path / "trail.jsonl"
        runner.invoke(app, ["evidence", "review", "-s", "first", "--trail", str(trail)])
        runner.invoke(app, ["evidence", "review", "-s", "second", "--trail", str(trail)])
        lines = trail.read_text().splitlines()
        trail.write_text(lines[0].replace('"first"', '"altered"') + "\n" + lines[1] + "\n")
        result = runner.invoke(
            app, ["evidence", "review", "-s", "s", "--trail", str(trail), "--verify"]
        )
        assert result.exit_code == 1
        assert "chain broken" in result.stderr

    def test_evidence_rejects_unknown_event(self, tmp_path):
        result = runner.invoke(
            app, ["evidence", "nonsense", "-s", "s", "--trail", str(tmp_path / "t.jsonl")]
        )
        assert result.exit_code == 2

    def test_evidence_rejects_bad_severity(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "evidence",
                "review",
                "-s",
                "s",
                "--trail",
                str(tmp_path / "t.jsonl"),
                "--severity",
                "nope",
            ],
        )
        assert result.exit_code == 2

    def test_evidence_rejects_malformed_item(self, tmp_path):
        result = runner.invoke(
            app,
            [
                "evidence",
                "review",
                "-s",
                "s",
                "--trail",
                str(tmp_path / "t.jsonl"),
                "--item",
                "no-equals-sign",
            ],
        )
        assert result.exit_code == 2
