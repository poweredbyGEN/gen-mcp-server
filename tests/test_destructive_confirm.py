"""GEN-4808: MCP delete tools must satisfy Rails' two-phase destructive gate.

Rails (GEN-4797) gates PAT-authenticated destructive Vidsheet deletes: the
first DELETE returns 428 with an authoritative ``would_destroy`` preview and a
single-use ``confirm_token``. mcp.gen.pro sends the caller's PAT, so it is in
the gated class by design — but before this fix no delete tool accepted a
token and ``client._call`` collapsed the 428 into an opaque ``GenApiError``.
Every MCP column/layer/variable delete against a populated target therefore
failed in production (fail-closed: nothing was destroyed, but nothing worked).

These tests fail on a tree without the fix:
- no GenConfirmationRequired / gated_delete export
- the 428 body is swallowed, so would_destroy + confirm_token never reach the caller
- the delete tools expose no confirm_token parameter
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from gen_mcp_server import client as client_mod
from gen_mcp_server.client import (
    GenApiError,
    GenConfirmationRequired,
    gated_delete,
)

PREVIEW = {
    "would_destroy": {"video_layers": [{"id": 42, "name": "Old Logo"}]},
    "confirm_token": "tok_abc123",
}


def _stub_call(monkeypatch, *, status: int, body: dict) -> list[str]:
    """Replace api_call with one that mimics client._call's status handling."""
    seen: list[str] = []

    async def fake_api_call(method: str, path: str, body_arg=None):
        seen.append(path)
        if status == httpx.codes.PRECONDITION_REQUIRED:
            token = body.get("confirm_token")
            if isinstance(token, str) and token:
                raise GenConfirmationRequired(
                    would_destroy=body.get("would_destroy"),
                    confirm_token=token,
                    body=body,
                )
            raise GenApiError(f"API error {status}: {json.dumps(body)}")
        return body

    monkeypatch.setattr(client_mod, "api_call", fake_api_call)
    return seen


def test_gated_delete_surfaces_preview_instead_of_opaque_error(monkeypatch):
    """A 428 must return the preview + token, not raise GenApiError."""
    _stub_call(monkeypatch, status=httpx.codes.PRECONDITION_REQUIRED, body=PREVIEW)

    result = json.loads(asyncio.run(gated_delete("/vidsheet/1/columns/2?agent_id=a")))

    assert result["status"] == "confirmation_required"
    assert result["confirm_token"] == "tok_abc123"
    assert result["would_destroy"] == PREVIEW["would_destroy"]
    # The model must be told what to do next, or it will retry blindly.
    assert "confirm_token" in result["next_step"]


def test_gated_delete_passes_through_a_successful_delete(monkeypatch):
    """With a valid token Rails 2xxes; the tool returns the real body."""
    _stub_call(monkeypatch, status=200, body={"deleted": True})

    result = json.loads(
        asyncio.run(gated_delete("/vidsheet/1/columns/2?agent_id=a&confirm_token=tok_abc123"))
    )

    assert result == {"deleted": True}


def test_428_without_a_token_fails_closed(monkeypatch):
    """A malformed preview must NOT be treated as approval."""
    _stub_call(
        monkeypatch,
        status=httpx.codes.PRECONDITION_REQUIRED,
        body={"would_destroy": {"video_layers": []}},  # no confirm_token
    )

    with pytest.raises(GenApiError):
        asyncio.run(gated_delete("/vidsheet/1/columns/2?agent_id=a"))


def test_delete_tools_accept_confirm_token():
    """All three gated delete tools must expose the token parameter."""
    import gen_mcp_server.server as server

    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    for name in ("gen_delete_column", "gen_delete_layer", "gen_delete_variable"):
        assert name in tools, f"{name} missing from the tool registry"
        params = (getattr(tools[name], "parameters", None) or {}).get("properties", {})
        assert "confirm_token" in params, f"{name} cannot satisfy the Rails 428 gate"
