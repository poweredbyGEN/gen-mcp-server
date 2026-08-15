"""GEN API client + per-request PAT auth.

The TS server sent the PAT as `X-API-Key` to three backends:
  - api.gen.pro/v1         (Rails — content engine, agents, orgs, vidsheet, ...)
  - agent.gen.pro/v1       (gen-agentic — chat, ideas, research, conversations)
  - agent-core.gen.pro/v1  (agent-core — watchlists, agent core/profile)
  - python.gen.pro         (social OAuth + schedule — connect/disconnect/post calendar)

We preserve that exactly. The only change for hosted mode is WHERE the PAT
comes from:

  - stdio mode  : env var GEN_API_KEY (single identity, like the TS server)
  - http mode   : per-request `Authorization: Bearer <gen_PAT>` header, so the
                  hosted server is multi-tenant — each caller acts as their own
                  GEN identity. We forward that PAT to the GEN API as X-API-Key.

Resolution order per call: explicit token arg > contextvar (set from the HTTP
request) > GEN_API_KEY env. Never logged.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

BASE_URL = os.environ.get("GEN_API_BASE_URL", "https://api.gen.pro/v1")
AGENT_API_BASE = os.environ.get("GEN_AGENT_API_URL", "https://agent.gen.pro/v1")
AGENT_CORE_API_BASE = os.environ.get(
    "GEN_AGENT_CORE_API_URL", "https://agent-core.gen.pro/v1"
)
INTEGRATION_BASE = os.environ.get("GEN_INTEGRATION_API_URL", "https://python.gen.pro")


class GenApiError(Exception):
    """Raised on a non-2xx GEN API response. Message mirrors the TS server."""


class GenConfirmationRequired(Exception):
    """Rails returned 428 for a destructive Vidsheet operation (GEN-4797).

    Rails gates PAT-authenticated destructive Vidsheet deletes behind a
    two-phase confirm: the first DELETE returns 428 with an authoritative
    ``would_destroy`` preview and a short-lived, single-use ``confirm_token``
    bound to (operation, target-state fingerprint, acting user + agent).

    MCP callers are interactive humans holding a PAT, so they are *in* the
    gated class by design. This exception carries the preview back to the
    caller instead of collapsing it into an opaque ``GenApiError``, so the
    model can show what would be destroyed and re-call with ``confirm_token``.

    We deliberately do NOT auto-confirm: Rails is the authority for target
    drift, expiry and one-shot consumption, and an MCP tool must never
    manufacture a user's approval.
    """

    def __init__(self, would_destroy: Any, confirm_token: str, body: Any) -> None:
        self.would_destroy = would_destroy
        self.confirm_token = confirm_token
        self.body = body
        super().__init__("confirmation_required")


def _pat_from_http_request() -> str | None:
    """In hosted (HTTP) mode, read the caller's PAT from the request headers.

    Accepts `Authorization: Bearer <gen_PAT>` (what Manus / claude.ai connector
    UIs send) or a raw `X-API-Key`. Returns None in stdio mode (no HTTP request),
    where the PAT comes from the GEN_API_KEY env var instead.
    """
    try:
        from fastmcp.server.dependencies import get_http_headers
    except Exception:
        return None
    try:
        # By default fastmcp STRIPS `authorization` (and x-api-key) to avoid
        # leaking creds downstream; we explicitly opt them back in because the
        # caller's PAT IS the credential we forward to the GEN API.
        headers = get_http_headers(include={"authorization", "x-api-key"}) or {}
    except Exception:
        return None
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return headers.get("x-api-key") or headers.get("X-API-Key")


def _resolve_pat() -> str:
    pat = _pat_from_http_request() or os.environ.get("GEN_API_KEY")
    if not pat:
        raise GenApiError(
            "No GEN PAT available: send `Authorization: Bearer <gen_PAT>` "
            "(hosted) or set GEN_API_KEY (stdio)."
        )
    return pat


async def _call(
    base: str,
    method: str,
    path: str,
    body: Any | None = None,
    params: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    pat = _resolve_pat()
    url = f"{base}{path}"
    headers = {
        "X-API-Key": pat,
        "Content-Type": "application/json",
        "X-Client": "gen-mcp-server",
    }
    if extra_headers:
        headers.update(extra_headers)
    async with httpx.AsyncClient(timeout=120.0) as http:
        res = await http.request(
            method,
            url,
            headers=headers,
            params=params,
            content=json.dumps(body) if body is not None else None,
        )
    text = res.text
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        data = {"raw": text}
    if res.status_code == httpx.codes.PRECONDITION_REQUIRED:
        # GEN-4808: Rails' two-phase destructive confirm. Surface the preview
        # + token rather than the generic error, which is unactionable and made
        # every gated MCP delete look like an opaque server failure.
        token = data.get("confirm_token") if isinstance(data, dict) else None
        if isinstance(token, str) and token:
            raise GenConfirmationRequired(
                would_destroy=data.get("would_destroy") if isinstance(data, dict) else None,
                confirm_token=token,
                body=data,
            )
        # A 428 without a usable token is a real error — fail closed.
    if not res.is_success:
        # Same shape as TS: "API error <status>: <json>"
        raise GenApiError(f"API error {res.status_code}: {json.dumps(data)}")
    return data


async def api_call(
    method: str,
    path: str,
    body: Any | None = None,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    """Rails content engine — api.gen.pro/v1."""
    return await _call(BASE_URL, method, path, body, extra_headers=extra_headers)


async def form_call(method: str, path: str, form: dict[str, str]) -> Any:
    """POST/PUT form-urlencoded to the Rails content engine (user_jobs monitoring).

    Mirrors the TS handlers that send Content-Type:
    application/x-www-form-urlencoded instead of JSON.
    """
    pat = _resolve_pat()
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=120.0) as http:
        res = await http.request(
            method,
            url,
            headers={
                "X-API-Key": pat,
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Client": "gen-mcp-server",
            },
            data=form,
        )
    text = res.text
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        data = {"raw": text}
    if not res.is_success:
        raise GenApiError(f"API error {res.status_code}: {json.dumps(data)}")
    return data


async def agent_api_call(method: str, path: str, body: Any | None = None) -> Any:
    """gen-agentic — agent.gen.pro/v1."""
    return await _call(AGENT_API_BASE, method, path, body)


async def agent_core_api_call(method: str, path: str, body: Any | None = None) -> Any:
    """agent-core — agent-core.gen.pro/v1."""
    return await _call(AGENT_CORE_API_BASE, method, path, body)


async def integration_api_call(
    method: str,
    path: str,
    body: Any | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Social publishing integration service — python.gen.pro (schedule, OAuth connect)."""
    return await _call(INTEGRATION_BASE, method, path, body, params=params)


def json_result(data: Any) -> str:
    """FastMCP returns the string as the tool's text content (mirrors jsonResult)."""
    return json.dumps(data, indent=2)


async def gated_delete(path: str, *, confirm_token: str | None = None) -> str:
    """DELETE a destructive Vidsheet resource through Rails' two-phase gate.

    GEN-4808. Without ``confirm_token`` Rails answers 428 with the
    authoritative ``would_destroy`` preview; we return that preview so the
    caller can show the user exactly what would be deleted and then re-call
    the same tool with the returned ``confirm_token``.

    The token is minted and validated by Rails and is single-use, expiring,
    and bound to the target's state fingerprint — so a stale preview fails
    closed rather than deleting something the user never saw.
    """
    try:
        data = await api_call("DELETE", path)
    except GenConfirmationRequired as gate:
        return json_result(
            {
                "status": "confirmation_required",
                "would_destroy": gate.would_destroy,
                "confirm_token": gate.confirm_token,
                "next_step": (
                    "Show the user what would_destroy lists. If they confirm, call this "
                    "same tool again with confirm_token set to the value above. The token "
                    "is single-use and expires; do not reuse or cache it."
                ),
            }
        )
    return json_result(data)
