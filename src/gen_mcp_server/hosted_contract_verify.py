"""Verify the live hosted Vidsheet tool surface against its packaged contract.

``scripts/deploy_hosted.sh`` runs this from the exact staged/active virtualenv.
That makes a successful deployment mean more than a TCP/initialize response:
the process that clients reach must advertise the Vidsheet tool enums generated
from the Rails wire artifact, and it must not expose editor ordering axes.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from . import server


class HostedContractVerificationError(RuntimeError):
    """The live MCP endpoint does not match the packaged Vidsheet contract."""


def _jsonrpc(url: str, payload: dict[str, Any], session_id: str | None = None) -> tuple[dict[str, Any], str | None]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode()
            new_session = response.headers.get("Mcp-Session-Id")
    except URLError as exc:
        raise HostedContractVerificationError(f"MCP request failed: {exc}") from exc

    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                message = json.loads(line.removeprefix("data: "))
            except json.JSONDecodeError as exc:
                raise HostedContractVerificationError("MCP returned malformed SSE JSON") from exc
            if isinstance(message, dict):
                return message, new_session
    raise HostedContractVerificationError("MCP returned no JSON-RPC message")


def _tools_by_name(response: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tools = response.get("result", {}).get("tools")
    if not isinstance(tools, list):
        raise HostedContractVerificationError("tools/list returned no tools array")
    result: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if isinstance(tool, dict) and isinstance(tool.get("name"), str):
            result[tool["name"]] = tool
    return result


def _properties(tools: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    try:
        properties = tools[name]["inputSchema"]["properties"]
    except (KeyError, TypeError) as exc:
        raise HostedContractVerificationError(f"{name} has no inputSchema.properties") from exc
    if not isinstance(properties, dict):
        raise HostedContractVerificationError(f"{name} inputSchema.properties is not an object")
    return properties


def assert_vidsheet_tool_surface(response: dict[str, Any]) -> None:
    """Assert the public JSON-RPC tool schemas match the packaged Rails projection."""
    tools = _tools_by_name(response)
    expectations = {
        "gen_create_column": (server.VIDSHEET_COLUMN_TYPES, "column_ids"),
        "gen_update_column": (server.VIDSHEET_COLUMN_TYPES, "column_ids"),
        "gen_create_layer": (server.VIDEO_LAYER_TYPES, "layer_ids"),
        "gen_update_layer": (server.VIDEO_LAYER_TYPES, "layer_ids"),
    }
    for name, (expected_enum, _reorder_key) in expectations.items():
        properties = _properties(tools, name)
        actual_enum = properties.get("type", {}).get("enum")
        if actual_enum != list(expected_enum):
            raise HostedContractVerificationError(
                f"{name}.type enum does not match packaged Rails contract: {actual_enum!r}"
            )
        if "position" in properties:
            raise HostedContractVerificationError(f"{name} exposes forbidden raw position")

    for name, expected_key in (
        ("gen_reorder_columns", "column_ids"),
        ("gen_reorder_layers", "layer_ids"),
    ):
        properties = _properties(tools, name)
        if expected_key not in properties:
            raise HostedContractVerificationError(f"{name} is missing {expected_key}")
        if "position" in properties:
            raise HostedContractVerificationError(f"{name} exposes forbidden raw position")


def verify(url: str) -> None:
    initialized, session_id = _jsonrpc(
        url,
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "gen-hosted-contract-verify", "version": "1"},
            },
            "id": 1,
        },
    )
    if "serverInfo" not in initialized.get("result", {}):
        raise HostedContractVerificationError("initialize returned no serverInfo")
    if not session_id:
        raise HostedContractVerificationError("initialize returned no MCP session id")
    listed, _ = _jsonrpc(
        url,
        {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
        session_id,
    )
    assert_vidsheet_tool_surface(listed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="MCP streamable HTTP endpoint")
    args = parser.parse_args()
    try:
        verify(args.url)
    except HostedContractVerificationError as exc:
        print(f"hosted contract verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print("hosted Vidsheet contract: OK")


if __name__ == "__main__":
    main()
