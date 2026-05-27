# Watchlists + Recurring Jobs — Public gen-api Exposure

> **Spec status:** approved 2026-05-27. Implements approach A (single coordinated sprint, all surfaces).
> **Jira:** piggybacks on **GEN-3159** (Watchlists, READY FOR QA ON PROD) and **GEN-3357** (Recurring agent jobs, READY FOR QA ON PROD). No new ticket.
> **Related backend PRs already merged:** gen-agentic #269, #271, #272, #273, #274, #279, agent-core watchlist router.

## Goal

Expose every watchlist and recurring-job ("daily task") backend operation that the sim-gen chat regression suites exercise through the public developer surfaces: MCP server, TypeScript SDK, llms.txt + llms-full.txt, OpenAPI spec, and the api-docs Astro site. After exposure, create the SUI workspace crypto watchlist for the CORE Alex Lin agent (TikTok, keywords `crypto, btc, xrp, sui, aptos, solana`).

## Why this is "expose-only"

Both backends are deployed and proven by their regression matrices:

- **Watchlists** — implemented in `agent-core/app/routers/watchlists.py` (494 lines). Tested by `tests/sim/test_watchlist_chat_scenarios.py` (14 scenarios) which the chat agent already passes by calling these endpoints internally. Public base URL: `https://agent-core.gen.pro`. Auth: PAT (`X-API-Key`) or Bearer.
- **Recurring jobs** — implemented in `gen-agentic/src/gen/recurring_jobs_api.py` (344 lines). Tested by `tests/sim/test_daily_tasks_chat_scenarios.py` (11 scenarios). Public base URL: `https://agent.gen.pro`. Auth: same.

The gap is purely the developer surface — no MCP tool, no SDK method, no doc page, no OpenAPI path. This spec closes that gap.

## Architecture — three API bases

The MCP server's `apiCall` / `agentApiCall` duo grows to a trio:

| Function | Default base URL | Env override | Backs |
|---|---|---|---|
| `apiCall` | `https://api.gen.pro/v1` | `GEN_API_BASE_URL` | Rails (engines, rows, cells, layers, generations) |
| `agentApiCall` | `https://agent.gen.pro/v1` | `GEN_AGENT_API_URL` | gen-agentic (chat, content ideas, profile, **recurring jobs**) |
| `agentCoreApiCall` (NEW) | `https://agent-core.gen.pro/v1` | `GEN_AGENT_CORE_API_URL` | agent-core (**watchlists**) |

The TypeScript SDK mirrors the same three-client structure.

## Endpoint inventory

### Watchlists (agent-core, 8 endpoints)

All paths are prefixed with `https://agent-core.gen.pro/v1`.

| Method | Path | Description |
|---|---|---|
| GET | `/agents/{agent_id}/watchlists` | List active watchlists |
| POST | `/agents/{agent_id}/watchlists` | Create watchlist (idempotent on name; merges sources if name exists) |
| GET | `/agents/{agent_id}/watchlists/{watchlist_id}` | Fetch one watchlist with sources |
| PATCH | `/agents/{agent_id}/watchlists/{watchlist_id}` | Update `name`, `intent_active`, `project_id`, `rails_project_error` |
| DELETE | `/agents/{agent_id}/watchlists/{watchlist_id}` | Soft-delete (clears `intent_active`, sets `deleted_at`) |
| POST | `/agents/{agent_id}/watchlists/{watchlist_id}/sources` | Add or restore a source |
| DELETE | `/agents/{agent_id}/watchlists/{watchlist_id}/sources/{source_id}` | Remove source by id |
| DELETE | `/agents/{agent_id}/watchlists/{watchlist_id}/sources?platform=&target_type=&target_value=` | Remove source by key |

**Source shape:** `{platform: string, target_type: "account"|"hashtag"|"keyword", target_value: string, original_display_value?: string}`.

**Watchlist response:** `{id, user_id, agent_id, name, intent_active, project_id?, rails_project_error?, conversation_id?, created_by_run_id?, sources: [...], created_at, updated_at}`.

### Recurring Jobs (gen-agentic, 8 endpoints)

All paths are prefixed with `https://agent.gen.pro/v1`.

| Method | Path | Description |
|---|---|---|
| GET | `/agents/{agent_id}/recurring-jobs` | List non-deleted jobs |
| POST | `/agents/{agent_id}/recurring-jobs` | Create a recurring job |
| POST | `/agents/{agent_id}/recurring-jobs/defaults` | Idempotent default content-ideas job seed |
| GET | `/agents/{agent_id}/recurring-jobs/{job_id}` | Fetch one |
| PATCH | `/agents/{agent_id}/recurring-jobs/{job_id}` | Update name/prompt/schedule/delivery/status/next_run_at |
| DELETE | `/agents/{agent_id}/recurring-jobs/{job_id}` | Soft-delete (status → `deleted`) |
| POST | `/agents/{agent_id}/recurring-jobs/{job_id}/pause` | status → `paused` |
| POST | `/agents/{agent_id}/recurring-jobs/{job_id}/resume` | status → `active` |

**Create body:** `{name?: string, job_type: string, prompt: string, schedule: {cadence: "daily"|"weekly"|"hourly", timezone: string, time_of_day?: string}, delivery: {type: "chat_only"|"email"}, next_run_at?: string}`.

**Job response:** `{id, user_id, agent_id, name, job_type, prompt, schedule, delivery, status: "active"|"paused"|"deleted", next_run_at?, last_run_at?, created_at, updated_at}`.

**Built-in `job_type` values seen in code:** `generate_content_ideas` (default).

## MCP tools (17 new)

### Watchlists (9)

| Tool | Verb / path |
|---|---|
| `gen_list_watchlists` | GET agent-core `/agents/{agent_id}/watchlists` |
| `gen_create_watchlist` | POST agent-core `/agents/{agent_id}/watchlists` |
| `gen_get_watchlist` | GET one |
| `gen_update_watchlist` | PATCH (rename / project_id) |
| `gen_pause_watchlist` | PATCH `intent_active: false` |
| `gen_resume_watchlist` | PATCH `intent_active: true` |
| `gen_delete_watchlist` | DELETE |
| `gen_add_watchlist_source` | POST `/sources` |
| `gen_remove_watchlist_source` | DELETE `/sources/{id}` or `?key=` |

### Recurring Jobs (8)

| Tool | Verb / path |
|---|---|
| `gen_list_recurring_jobs` | GET gen-agentic `/agents/{agent_id}/recurring-jobs` |
| `gen_create_recurring_job` | POST |
| `gen_ensure_default_recurring_job` | POST `/defaults` (idempotent seed) |
| `gen_get_recurring_job` | GET one |
| `gen_update_recurring_job` | PATCH |
| `gen_pause_recurring_job` | POST `/pause` |
| `gen_resume_recurring_job` | POST `/resume` |
| `gen_delete_recurring_job` | DELETE |

**Tool description rules** (per gen-api skill):

- First sentence = what it does
- Include WHEN to use it vs. alternatives
- For enums (`target_type`, `cadence`, `delivery.type`, `status`), list valid values inline in the Zod `.describe()` and the tool description
- Group under a new `Step 3 (Monitoring & Automation)` section in `API_REFERENCE` so the AI consumer learns the workflow

## TypeScript SDK (17 new methods)

Names mirror MCP tool names 1:1, dropping the `gen_` prefix and using camelCase. Same parameter shapes. Each surface gets its own client object on the main SDK class, paralleling the three-base architecture.

## llms.txt + llms-full.txt

**llms.txt additions** (workflow-first per gen-api skill):

```markdown
## Watchlists
A Watchlist is a named collection of social-media monitoring targets...
Quick start: POST /v1/agents/{agent_id}/watchlists with name + sources[]...

## Recurring Jobs (Daily Tasks)
Schedule the agent to run a prompt on a recurring cadence...
Quick start: POST /v1/agents/{agent_id}/recurring-jobs/defaults for the default...
```

**llms-full.txt** gets the full schema + every endpoint + all enum values + error codes.

## OpenAPI spec

Add two new tags (`watchlists`, `recurring-jobs`). Add two new server entries (agent-core + reuse existing agent.gen.pro server). All 17 paths with request/response schemas mirroring the Pydantic models.

## Docs site (api-docs)

- `src/content/docs/reference/watchlists.mdx` — overview, all 8 endpoints, curl + TS examples per endpoint
- `src/content/docs/reference/recurring-jobs.mdx` — overview, all 8 endpoints, curl + TS examples
- `src/content/docs/guides/monitoring-quickstart.mdx` — "create a watchlist to track competitors / keywords; pause vs. delete; query results via chat"
- Update `astro.config.mjs` sidebar

## Public Surface Security pass (per gen-api skill)

- ✅ Only base URLs `https://agent.gen.pro/v1` and `https://agent-core.gen.pro/v1` appear in public surfaces
- ❌ Never reference staging hosts, EC2 IPs, port numbers, internal DB tables (`watchlists`, `watch_sources`, `recurring_agent_jobs`), Celery, systemd unit names
- ❌ Never reference `GEN-3159` / `GEN-3357` in public docs
- ✅ "How to get an API key" link on every new reference page

## Credit billing

Per gen-api skill: all reads + CRUD writes are **free** for both resources. The compute-billed operations are downstream — DW scraping for watchlist sources, `generate_content_ideas` runs for recurring jobs — and those are already billed via existing `pricing_configs` rows (GEN-2772 mechanism). No new `pricing_configs` row, no Rails PR.

## Repos + PR list

| # | Repo | Branch | Scope |
|---|---|---|---|
| 1 | `gen-mcp-server` | `feat/GEN-3159-GEN-3357-watchlists-recurring-jobs-mcp` | 17 tools + `agentCoreApiCall` client + API_REFERENCE updates + bump version + publish |
| 2 | `autocontentengine-typescript-sdk` | `feat/GEN-3159-GEN-3357-watchlists-recurring-jobs-sdk` | 17 methods + three-client structure + types + bump + publish via PR |
| 3 | `api-docs` | `feat/GEN-3159-GEN-3357-watchlists-recurring-jobs-docs` | openapi.yaml + 2 reference .mdx + 1 guide .mdx + sidebar |
| 4 | `gen-backend-v2` / `agent-core` / `gen-agentic` | — | **No changes.** Backends already deployed. |

## Verification

1. MCP server: `npx @poweredbygen/autocontentengine-mcp-server@latest` resolves new version. Each new tool can be called against staging PAT and returns a 2xx.
2. SDK: `npm install @poweredbygen/autocontentengine-typescript-sdk@latest` resolves new version. Type-check passes; smoke calls return 2xx.
3. Docs: `https://api.gen.pro/reference/watchlists` and `/reference/recurring-jobs` render with examples; `https://api.gen.pro/llms.txt` includes new sections; `https://api.gen.pro/openapi.yaml` includes new paths.
4. **SUI crypto watchlist creation** using the new MCP tool against CORE Alex Lin (agent in SUI org 210, phone_id `567759745159530059`), TikTok platform, keywords `crypto, btc, xrp, sui, aptos, solana`. Verify all 6 sources active in the response; verify the chat agent's `list my watchlists` returns the new entry.

## Risks

1. **agent-core public reachability** — confirmed live at `https://agent-core.gen.pro` (Route53 → ALB → EC2:8800, *.gen.pro wildcard cert). Dual-auth supports PAT. No infra gap.
2. **CORS** for browser SDK callers — agent-core's CORS allows `localhost:5173`, `gen.pro`, `app.gen.pro`, `staging.gen.pro`. Server-side SDK use is unaffected. Flag in SDK README.
3. **MCP publishes to GitHub Packages** (not npmjs). `.npmrc` already in repo. No new infra.
4. **SDK repo branch protection** — must use PR flow to bump, then publish from main per gen-api skill.

## Out of scope

- Changing the watchlist or recurring-job storage schema
- Changing chat behavior (chat already works; this is API-side exposure only)
- Adding watchlist analysis ("top hooks from @watchlist:slug") to the API — that's a chat-orchestrated query; the API exposes CRUD only
- Adding new `job_type` values to recurring jobs — that's a separate backend change covered by GEN-2772 flow
