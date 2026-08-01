"""Unit tests for the deploy-time public MCP schema verifier."""
from __future__ import annotations

from copy import deepcopy

import pytest

from gen_mcp_server import server
from gen_mcp_server.hosted_contract_verify import (
    HostedContractVerificationError,
    assert_vidsheet_tool_surface,
    verify,
)


def _tool(name: str, properties: dict):
    return {"name": name, "inputSchema": {"properties": properties}}


@pytest.fixture
def live_tools_response():
    return {
        "result": {
            "tools": [
                _tool("gen_create_column", {"type": {"enum": list(server.VIDSHEET_COLUMN_TYPES)}}),
                _tool("gen_update_column", {"type": {"enum": list(server.VIDSHEET_COLUMN_TYPES)}}),
                _tool("gen_create_layer", {"type": {"enum": list(server.VIDEO_LAYER_TYPES)}}),
                _tool("gen_update_layer", {"type": {"enum": list(server.VIDEO_LAYER_TYPES)}}),
                _tool("gen_reorder_columns", {"column_ids": {"type": "array"}}),
                _tool("gen_reorder_layers", {"layer_ids": {"type": "array"}}),
            ]
        }
    }


def test_accepts_live_projection_of_packaged_rails_contract(live_tools_response):
    assert_vidsheet_tool_surface(live_tools_response)


def test_rejects_stale_or_hand_maintained_enum(live_tools_response):
    response = deepcopy(live_tools_response)
    response["result"]["tools"][0]["inputSchema"]["properties"]["type"]["enum"] = ["wrong"]
    with pytest.raises(HostedContractVerificationError, match="does not match"):
        assert_vidsheet_tool_surface(response)


def test_rejects_position_reintroduced_to_public_tool(live_tools_response):
    response = deepcopy(live_tools_response)
    response["result"]["tools"][2]["inputSchema"]["properties"]["position"] = {"type": "integer"}
    with pytest.raises(HostedContractVerificationError, match="forbidden raw position"):
        assert_vidsheet_tool_surface(response)


def test_verify_requires_a_session_bound_public_tools_list(monkeypatch, live_tools_response):
    calls = []

    def fake_jsonrpc(url, payload, session_id=None):
        calls.append((url, payload["method"], session_id))
        if payload["method"] == "initialize":
            return {"result": {"serverInfo": {"name": "gen"}}}, "session-123"
        return live_tools_response, None

    monkeypatch.setattr("gen_mcp_server.hosted_contract_verify._jsonrpc", fake_jsonrpc)

    verify("http://127.0.0.1:8090/mcp")

    assert calls == [
        ("http://127.0.0.1:8090/mcp", "initialize", None),
        ("http://127.0.0.1:8090/mcp", "tools/list", "session-123"),
    ]
