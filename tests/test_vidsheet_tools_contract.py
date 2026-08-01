"""Hosted MCP schemas are thin projections of the Rails Vidsheet artifact."""
from __future__ import annotations

import asyncio

import pytest

from gen_mcp_server import server


def test_vidsheet_tool_schemas_use_rails_enums_and_hide_raw_positions():
    tools = {
        tool.name: tool.parameters
        for tool in asyncio.run(server.mcp.list_tools())
    }

    create_column = tools["gen_create_column"]["properties"]
    update_column = tools["gen_update_column"]["properties"]
    create_layer = tools["gen_create_layer"]["properties"]
    update_layer = tools["gen_update_layer"]["properties"]

    assert create_column["type"]["enum"] == list(server.VIDSHEET_COLUMN_TYPES)
    assert update_column["type"]["enum"] == list(server.VIDSHEET_COLUMN_TYPES)
    assert create_layer["type"]["enum"] == list(server.VIDEO_LAYER_TYPES)
    assert update_layer["type"]["enum"] == list(server.VIDEO_LAYER_TYPES)
    for schema in (create_column, update_column, create_layer, update_layer):
        assert "position" not in schema

    assert "column_ids" in tools["gen_reorder_columns"]["properties"]
    assert "layer_ids" in tools["gen_reorder_layers"]["properties"]


def test_named_reorder_derives_positions_before_the_rails_request(monkeypatch):
    calls = []

    async def fake_api_call(method, path, body=None):
        calls.append((method, path, body))
        return {"ok": True}

    monkeypatch.setattr(server, "api_call", fake_api_call)
    asyncio.run(server.gen_reorder_columns("sheet", "agent", ["left", "right"]))
    asyncio.run(server.gen_reorder_layers("sheet", "cell", "agent", ["top", "bottom"]))

    assert calls == [
        (
            "PATCH",
            "/vidsheet/sheet/columns/update_positions",
            {"agent_id": "agent", "id_to_position": {"left": 0, "right": 1}},
        ),
        (
            "PUT",
            "/vidsheet/sheet/cells/cell/layers/update_positions",
            {"agent_id": "agent", "id_to_position": {"top": 0, "bottom": 1}},
        ),
    ]


def test_create_layer_derives_its_required_wire_position(monkeypatch):
    calls = []

    async def fake_api_call(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET":
            return {"video_layers": [{"position": 0}, {"position": 3}]}
        return {"ok": True}

    monkeypatch.setattr(server, "api_call", fake_api_call)
    asyncio.run(server.gen_create_layer("sheet", "cell", "agent", "Caption", "text"))

    assert calls == [
        ("GET", "/vidsheet/sheet/cells/cell?agent_id=agent", None),
        (
            "POST",
            "/vidsheet/sheet/cells/cell/layers",
            {
                "agent_id": "agent",
                "video_layer": {"name": "Caption", "type": "text", "position": 4},
            },
        ),
    ]


def test_reorder_rejects_ambiguous_or_empty_id_lists(monkeypatch):
    async def never_called(*args, **kwargs):
        raise AssertionError("invalid input must not call Rails")

    monkeypatch.setattr(server, "api_call", never_called)
    with pytest.raises(ValueError, match="duplicate"):
        asyncio.run(server.gen_reorder_columns("sheet", "agent", ["one", "one"]))
    with pytest.raises(ValueError, match="complete desired order"):
        asyncio.run(server.gen_reorder_layers("sheet", "cell", "agent", []))
