"""Shadow-AI discovery: MAS-AIRM 4.2 and 4.4 with footnote 22."""

from __future__ import annotations

import pytest

from airm.scan import (
    DEFAULT_EXCLUDES,
    SIGNALS,
    SignalKind,
    scan_path,
    signal_catalogue,
    to_use_cases,
)


class TestSignals:
    def test_every_signal_has_a_citation(self):
        for signal in SIGNALS:
            assert signal.kind.citation.startswith("MAS-AIRM")

    def test_signal_ids_unique(self):
        ids = [s.id for s in SIGNALS]
        assert len(ids) == len(set(ids))

    def test_patterns_compile(self):
        for signal in SIGNALS:
            assert signal.compiled().pattern

    def test_confidence_values_are_valid(self):
        assert {s.confidence for s in SIGNALS} <= {"low", "medium", "high"}

    def test_agent_kinds_flagged(self):
        assert SignalKind.MCP_CONFIG.suggests_agent
        assert SignalKind.AGENT_FRAMEWORK.suggests_agent
        assert not SignalKind.ML_FRAMEWORK.suggests_agent

    def test_signal_catalogue_is_plain_data(self):
        entries = signal_catalogue()
        assert len(entries) == len(SIGNALS)
        assert all("citation" in e for e in entries)


class TestScanning:
    def test_detects_an_llm_sdk_import(self, tmp_path):
        (tmp_path / "app.py").write_text("import anthropic\n")
        report = scan_path(tmp_path)
        assert report.kinds == {"llm_sdk": 1}
        assert report.findings[0].location == "app.py:1"

    def test_detects_an_mcp_config(self, tmp_path):
        (tmp_path / ".mcp.json").write_text('{"mcpServers": {"x": {}}}\n')
        report = scan_path(tmp_path)
        assert report.has_agent_signals

    def test_detects_a_public_ai_tool_reference(self, tmp_path):
        """MAS-AIRM 4.4 fn22: shadow AI."""
        (tmp_path / "notes.md").write_text("pasted from chatgpt.com\n")
        report = scan_path(tmp_path, min_confidence="low")
        assert report.shadow_ai_findings

    def test_detects_vendor_ai_saas(self, tmp_path):
        """MAS-AIRM 4.2 fn21: embedded AI."""
        (tmp_path / "config.yaml").write_text("service: einstein_gpt\n")
        report = scan_path(tmp_path)
        assert report.embedded_ai_findings

    def test_secrets_are_redacted(self, tmp_path):
        (tmp_path / "app.py").write_text('import openai\nAPI_KEY = "sk-abcdefghijklmnopqrst"\n')
        report = scan_path(tmp_path)
        for finding in report.findings:
            assert "sk-abcdefghijklmnopqrst" not in finding.excerpt

    def test_excluded_directories_are_skipped(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "x.js").write_text("import anthropic\n")
        assert scan_path(tmp_path).findings == []

    def test_custom_excludes(self, tmp_path):
        (tmp_path / "skipme").mkdir()
        (tmp_path / "skipme" / "x.py").write_text("import anthropic\n")
        assert scan_path(tmp_path, excludes={"skipme"}).findings == []
        assert scan_path(tmp_path, excludes=set()).findings

    def test_symlinks_are_not_followed(self, tmp_path):
        """A scanned repository must not redirect the scanner out of its tree."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.py").write_text("import anthropic\n")
        inside = tmp_path / "repo"
        inside.mkdir()
        (inside / "link").symlink_to(outside)
        assert scan_path(inside).findings == []

    def test_unscanned_suffixes_are_skipped(self, tmp_path):
        (tmp_path / "image.png").write_bytes(b"\x89PNG import anthropic")
        report = scan_path(tmp_path)
        assert report.findings == []
        assert report.files_skipped == 1

    def test_min_confidence_filters(self, tmp_path):
        (tmp_path / "notes.md").write_text("see chatgpt.com for details\n")
        assert scan_path(tmp_path, min_confidence="low").findings
        assert scan_path(tmp_path, min_confidence="high").findings == []

    def test_scanning_a_single_file(self, tmp_path):
        path = tmp_path / "app.py"
        path.write_text("import anthropic\n")
        assert scan_path(path).files_scanned == 1

    def test_report_carries_the_caveat(self, tmp_path):
        """A clean scan is not assurance of completeness."""
        report = scan_path(tmp_path)
        assert "not an inventory" in report.caveat
        assert "§4.3" in report.caveat

    def test_summary_lines(self, tmp_path):
        (tmp_path / "app.py").write_text("import anthropic\n")
        lines = scan_path(tmp_path).summary_lines()
        assert any("scanned" in line for line in lines)

    def test_by_directory_grouping(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "a" / "x.py").write_text("import openai\n")
        (tmp_path / "b").mkdir()
        (tmp_path / "b" / "y.py").write_text("import langchain\n")
        assert set(scan_path(tmp_path).by_directory) == {"a", "b"}

    def test_default_excludes_cover_the_usual_suspects(self):
        assert {".git", ".venv", "node_modules", "site-packages"} <= DEFAULT_EXCLUDES


class TestCandidates:
    def test_candidates_are_proposed_not_adopted(self, tmp_path):
        """MAS-AIRM 4.3: the control function is the final arbiter, not a scanner."""
        (tmp_path / "agent.py").write_text("from langgraph.graph import StateGraph\n")
        candidates = to_use_cases(scan_path(tmp_path))
        assert candidates
        candidate = candidates[0]
        assert candidate.lifecycle_status.value == "proposed"
        assert "UNTRIAGED" in candidate.purpose
        assert "final arbiter" in (candidate.notes or "")

    def test_agent_signals_are_called_out(self, tmp_path):
        (tmp_path / "agent.py").write_text("from crewai import Agent\n")
        candidate = to_use_cases(scan_path(tmp_path))[0]
        assert "agent" in candidate.tags
        assert "fn25" in (candidate.notes or "")

    def test_grouping_by_file(self, tmp_path):
        (tmp_path / "a.py").write_text("import openai\n")
        (tmp_path / "b.py").write_text("import anthropic\n")
        assert len(to_use_cases(scan_path(tmp_path), group_by="file")) == 2
        assert len(to_use_cases(scan_path(tmp_path), group_by="directory")) == 1

    def test_candidate_ids_are_valid_slugs(self, tmp_path):
        nested = tmp_path / "Some_Dir" / "Sub"
        nested.mkdir(parents=True)
        (nested / "x.py").write_text("import openai\n")
        for candidate in to_use_cases(scan_path(tmp_path)):
            assert candidate.id == candidate.id.lower()
            assert " " not in candidate.id


def test_scanning_this_repository_finds_its_own_signals():
    """The toolkit's own code trips its own detectors, which is the honest self-test."""
    report = scan_path("src", min_confidence="medium")
    assert report.files_scanned > 5
    assert report.kinds


class TestSecretRedaction:
    """Findings are recorded in reports and often committed, so a matched line must not carry a
    credential out of the file it was found in."""

    @pytest.mark.parametrize(
        "line",
        [
            "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123",
            "GOOGLE_KEY=AIzaSyA1234567890abcdefghijklmnopqrst",
            "SLACK=xoxb-1234567890-abcdefghij",
            "token: ghp_abcdefghijklmnopqrstuvwxyz0123",
            "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
            "HF_TOKEN=hf_abcdefghijklmnopqrstuvwx",
            'auth = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbU"',
            "-----BEGIN RSA PRIVATE KEY-----",
            'password = "hunter2hunter2hunter2"',
        ],
    )
    def test_credentials_are_redacted(self, line):
        from airm.scan import _redact

        redacted = _redact(line)
        assert "[REDACTED]" in redacted
        for secret in (
            "sk-abcdef",
            "AIzaSyA1",
            "xoxb-1234",
            "ghp_abcdef",
            "AKIAIOSFODNN7EXAMPLE",
            "hf_abcdef",
            "dBjftJeZ",
            "PRIVATE KEY",
            "hunter2",
        ):
            assert secret not in redacted

    def test_ordinary_code_is_left_alone(self):
        from airm.scan import _redact

        assert _redact('  model = "claude-opus-5"  ') == 'model = "claude-opus-5"'

    def test_redacted_line_is_truncated(self):
        from airm.scan import MAX_LINE_CHARS, _redact

        assert len(_redact("import anthropic  # " + "x" * 2000)) == MAX_LINE_CHARS
