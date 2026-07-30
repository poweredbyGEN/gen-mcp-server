# GEN MCP Server

> ## ⚠️ The downloadable package is deprecated — use `https://mcp.gen.pro`
>
> **This is the FINAL PyPI release of `gen-mcp-server`.** GEN no longer ships a
> downloadable MCP: the official GEN MCP is the **hosted server** at
> `https://mcp.gen.pro`. No further versions will be published to PyPI.
>
> The package still works so existing integrations have a migration window, but
> it will not receive new tools, fixes, or API updates — the hosted server is
> already ahead of it and is the only surface kept in sync with the GEN API.
> Installing it emits a `DeprecationWarning`; the stdio CLI prints a notice to
> stderr on start.

## Use the official hosted MCP (all clients)

No install. Point your MCP client at the hosted endpoint and authenticate with
your GEN Personal Access Token (from https://gen.pro — log in, pick an agent,
open the **API** page in the sidebar, click **Create API Key**):

```json
{
  "name": "gen",
  "url": "https://mcp.gen.pro",
  "headers": { "Authorization": "Bearer gen_pat_…" }
}
```

(Existing configs using `https://mcp.gen.pro/mcp` keep working.)

**Claude Code:**

```bash
claude mcp add --transport http gen https://mcp.gen.pro \
  --header "Authorization: Bearer gen_pat_…"
```

**Manus:** Settings → Integrations → Custom MCP Servers → Add Server
- **Server URL:** `https://mcp.gen.pro`
- **Authentication:** Bearer token → your `gen_…` PAT

**claude.ai connectors / ChatGPT:** add a custom MCP connector with the same
URL + bearer token.

The hosted server is multi-tenant — each caller acts as their own GEN identity;
your PAT scopes everything you can see and do.

## What it is

MCP (Model Context Protocol) server for the GEN platform — lets Claude and any
MCP-compatible AI drive the GEN Auto Content Engine + Agent Core: the full
5-step journey from onboarding an agent to publishing a video.

```
Step 1           Step 2            Step 3              Step 4             Step 5
──────           ──────            ──────              ──────             ──────
Set Up    →    Generate    →     Idea to      →     Edit &      →     Export &
Agent          Ideas             Vidsheet            Generate           Publish
```

Read the `gen://api-reference` MCP resource for the full teaching document, and
[api.gen.pro](https://api.gen.pro) for the API reference. Tool descriptions
start with the step name (e.g. "Step 4 (Edit & Generate): …") so AI tooling can
route quickly.

## Legacy local install (deprecated — migrate to the hosted URL above)

The stdio mode still functions for the migration window:

```bash
uvx gen-mcp-server           # or: pip install gen-mcp-server && gen-mcp-server
export GEN_API_KEY=your-api-key
```

It prints a deprecation notice to stderr on start. Do not build new
integrations on it; use `https://mcp.gen.pro`.

Optional base-URL overrides (legacy stdio only):

```bash
export GEN_API_BASE_URL=https://api.gen.pro/v1
export GEN_AGENT_API_URL=https://agent.gen.pro/v1
export GEN_AGENT_CORE_API_URL=https://agent-core.gen.pro/v1
```

## Development (this repo stays alive — it IS the hosted server)

This repository remains the source of the hosted `mcp.gen.pro` deployment; only
the PyPI distribution is retired.

```bash
git clone https://github.com/poweredbyGEN/gen-mcp-server.git
cd gen-mcp-server
uv venv && . .venv/bin/activate
uv pip install -e .
GEN_MCP_PORT=8080 gen-mcp-server --http   # hosted streamable-http mode, serves `/` and `/mcp`
```

## See also

- **API Docs:** [api.gen.pro](https://api.gen.pro) — full API reference and guides
- **TypeScript SDK:** [github.com/poweredbyGEN/gen-typescript-sdk](https://github.com/poweredbyGEN/gen-typescript-sdk)

## Changelog

### 1.0.0 — FINAL PyPI RELEASE (deprecation pointer)
- The downloadable package is deprecated; the official GEN MCP is the hosted
  server at `https://mcp.gen.pro` (GEN-4785)
- `DeprecationWarning` on import when installed from PyPI; stderr notice on
  stdio CLI start. Hosted (`--http`) mode is unaffected
- Includes everything on main at cut time, including the Python/FastMCP rewrite
  (GEN-3788) and the 2026-07-30 tool additions (billing, social, schedule,
  assets, generation, compose — 31 tools) never previously published

### 0.5.0
- Restructured all 81 tools around the 5-step user journey (GEN-2879)
- Rewrote the embedded `gen://api-reference` resource as a step-by-step teaching document with chained curl examples
- Tool descriptions now start with the phase (e.g. "Step 1 (Agent Setup): …") so AI tooling can route quickly

### 0.4.x
- Added Agent Core flat endpoints (GEN-2755)
- Stripped vendor branding from tool descriptions
- Added `gen_run_research`, expanded API_REFERENCE with agentic chat docs
- Content monitoring + publishing tools

## License

MIT
