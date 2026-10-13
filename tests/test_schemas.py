"""Tests for the JSON Schema exports.

The schemas are the part of this project someone can adopt without adopting the library, so they
are tested for three things: that they are valid JSON Schema, that they actually validate the
shipped worked example, and that the committed files in ``schemas/`` match the models.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from airm.schemas import EXPORTS, export, schema_for

REPO = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO / "schemas"
EXAMPLE = REPO / "examples" / "synthetic_bank"


def test_exports_cover_the_formats_mission_names() -> None:
    for stem in (
        "ai-inventory-register",
        "ai-use-case",
        "agent-extension",
        "materiality-rubric",
        "control-catalogue",
        "audit-trail-record",
        "vendor-register",
        "crosswalk",
    ):
        assert stem in EXPORTS, stem


@pytest.mark.parametrize("stem", sorted(EXPORTS))
def test_each_schema_is_valid_json_schema(stem: str) -> None:
    schema = schema_for(stem)
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["$id"].endswith(f"{stem}.schema.json")
    assert schema["x-mas-airm-clauses"]
    assert "Monetary Authority of Singapore" in schema["x-disclaimer"]


def test_schema_for_rejects_an_unknown_stem() -> None:
    with pytest.raises(KeyError, match="unknown schema"):
        schema_for("not-a-format")


def test_register_schema_validates_the_worked_example() -> None:
    register = yaml.safe_load((EXAMPLE / "ai-inventory.yaml").read_text(encoding="utf-8"))
    jsonschema.validate(register, schema_for("ai-inventory-register"))


def test_vendor_schema_validates_the_worked_example() -> None:
    vendors = yaml.safe_load((EXAMPLE / "third-party-assessments.yaml").read_text(encoding="utf-8"))
    jsonschema.validate(vendors, schema_for("vendor-register"))


def test_trail_schema_validates_every_committed_record() -> None:
    schema = schema_for("audit-trail-record")
    lines = (EXAMPLE / "evidence" / "trail.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines
    for line in lines:
        jsonschema.validate(json.loads(line), schema)


def test_register_schema_rejects_a_use_case_without_a_purpose() -> None:
    bad = {"institution": "Test", "use_cases": [{"id": "x", "name": "X"}]}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema_for("ai-inventory-register"))


def test_export_writes_every_schema_and_an_index(tmp_path: Path) -> None:
    written = export(tmp_path)
    assert len(written) == len(EXPORTS) + 1
    index = (tmp_path / "README.md").read_text(encoding="utf-8")
    for stem in EXPORTS:
        assert (tmp_path / f"{stem}.schema.json").is_file()
        assert f"{stem}.schema.json" in index


def test_committed_schemas_match_the_models(tmp_path: Path) -> None:
    """`schemas/` is generated; a stale file would advertise a format the library rejects."""
    export(tmp_path)
    for path in sorted(tmp_path.glob("*.json")):
        committed = SCHEMA_DIR / path.name
        assert committed.is_file(), f"{path.name} is missing; run `airm schemas`"
        assert json.loads(committed.read_text(encoding="utf-8")) == json.loads(
            path.read_text(encoding="utf-8")
        ), f"{path.name} is stale; run `airm schemas`"
    assert (SCHEMA_DIR / "README.md").read_text(encoding="utf-8") == (
        tmp_path / "README.md"
    ).read_text(encoding="utf-8")


def test_no_stray_files_in_the_schema_directory() -> None:
    expected = {f"{stem}.schema.json" for stem in EXPORTS} | {"README.md"}
    assert {path.name for path in SCHEMA_DIR.iterdir()} == expected
