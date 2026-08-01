"""The hosted MCP must consume the same generated wire artifact as ASK."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gen_mcp_server import vidsheet_contract as contract


@pytest.fixture(autouse=True)
def fresh_contract_cache():
    contract._derived.cache_clear()
    yield
    contract._derived.cache_clear()


def test_column_type_enum_is_derived_from_the_vendored_rails_artifact():
    assert contract.enum_values("spreadsheet_column", "type") == (
        "text",
        "image",
        "video",
        "audio",
        "media",
        "stats",
    )


def test_ordering_axis_is_derived_and_not_model_facing():
    assert contract.ordering_axis_fields() == {
        "video_layer": frozenset({"position"}),
        "spreadsheet_column": frozenset({"position"}),
        "spreadsheet_row": frozenset({"position"}),
    }
    with pytest.raises(contract.VidsheetContractError, match="ordering"):
        contract.model_facing_fields("spreadsheet_column", {"title", "position"})


def test_unknown_enum_value_is_rejected_before_the_rails_request():
    with pytest.raises(ValueError, match="spreadsheet_column.type"):
        contract.require_enum_value("spreadsheet_column", "type", "hologram")


def test_missing_or_markerless_artifact_fails_closed(monkeypatch, tmp_path):
    missing = tmp_path / "missing.json"
    monkeypatch.setattr(contract, "ARTIFACT_PATH", missing)
    with pytest.raises(contract.VidsheetContractError, match="missing"):
        contract.ordering_axis_fields()

    markerless = json.loads(
        (Path(__file__).parents[1] / "src/gen_mcp_server/contracts/vidsheet-operations-schema.json").read_text()
    )
    for _entity, _field, schema in contract._request_fields(markerless):
        schema.pop("x-ordering-axis", None)
    path = tmp_path / "markerless.json"
    path.write_text(json.dumps(markerless))
    monkeypatch.setattr(contract, "ARTIFACT_PATH", path)
    contract._derived.cache_clear()
    with pytest.raises(contract.VidsheetContractError, match="ordering-axis"):
        contract.ordering_axis_fields()
