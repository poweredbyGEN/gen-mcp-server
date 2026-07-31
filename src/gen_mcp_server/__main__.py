"""Entrypoint — dual transport.

  gen-mcp-server                 -> stdio   (default; what the PyPI/npm package ships
                                             and what Claude Code / Cursor / VS Code run)
  gen-mcp-server --http          -> streamable-http on 0.0.0.0:8080, served at
                                    BOTH `/` (canonical: https://mcp.gen.pro) and
                                    `/mcp` (legacy alias for existing configs)
                                    (hosted mode for Manus / claude.ai connectors /
                                     ChatGPT — fronted by Cloudflare at mcp.gen.pro)

The PAT (per-request `Authorization: Bearer <gen_PAT>` in HTTP mode, or
GEN_API_KEY env in stdio mode) is resolved inside client._resolve_pat() via
fastmcp's get_http_headers(); no middleware needed. HTTP mode is multi-tenant —
each caller acts as their own GEN identity.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import DEPRECATION_NOTICE
from .server import mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="gen-mcp-server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run hosted streamable-http transport instead of stdio.",
    )
    parser.add_argument("--host", default=os.environ.get("GEN_MCP_HOST", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("GEN_MCP_PORT", "8080"))
    )
    args = parser.parse_args()

    if args.http:
        # Hosted mode IS the official surface (mcp.gen.pro) — no deprecation
        # banner here (GEN-4785); only the stdio path below is deprecated.
        import uvicorn

        # Canonical MCP endpoint is the BARE root (`{"url": "https://mcp.gen.pro"}`).
        # `/mcp` (the old FastMCP-default path) stays as an alias so every client
        # configured before the switch keeps working — alias, not redirect, because
        # MCP clients are not guaranteed to re-POST a JSON-RPC body across a 30x.
        app = mcp.http_app(path="/")

        async def dual_path_app(scope, receive, send):  # ASGI wrapper
            if scope["type"] == "http" and scope.get("path") in ("/mcp", "/mcp/"):
                scope = dict(scope)
                scope["path"] = "/"
                scope["raw_path"] = b"/"
            await app(scope, receive, send)

        uvicorn.run(dual_path_app, host=args.host, port=args.port)
    else:
        # Local stdio is the deprecated delivery path (GEN-4785). Plain stderr,
        # not a warnings.warn(), so no warning filter can silence it; stdio MCP
        # clients ignore stderr for protocol purposes, so this is safe to print.
        print(f"DEPRECATED: {DEPRECATION_NOTICE}", file=sys.stderr)
        # stdio: PAT must be present in env (fail fast, like the TS server).
        if not os.environ.get("GEN_API_KEY"):
            print("GEN_API_KEY environment variable is required", file=sys.stderr)
            sys.exit(1)
        mcp.run()  # stdio default


if __name__ == "__main__":
    main()
