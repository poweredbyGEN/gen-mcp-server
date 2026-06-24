"""Entrypoint — dual transport.

  gen-mcp-server                 -> stdio   (default; what the PyPI/npm package ships
                                             and what Claude Code / Cursor / VS Code run)
  gen-mcp-server --http          -> streamable-http on 0.0.0.0:8080/mcp
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
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        # stdio: PAT must be present in env (fail fast, like the TS server).
        if not os.environ.get("GEN_API_KEY"):
            print("GEN_API_KEY environment variable is required", file=sys.stderr)
            sys.exit(1)
        mcp.run()  # stdio default


if __name__ == "__main__":
    main()
