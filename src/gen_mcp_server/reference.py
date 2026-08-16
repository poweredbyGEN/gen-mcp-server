"""GEN MCP API reference — served at gen://api-reference."""

API_REFERENCE = """# GEN MCP — System Prompt & API Reference

## About GEN

GEN is an Autonomous Social Media Agent platform. An *agent* is a brand identity
that detects trends, generates video content (text, images, video, speech,
lipsync, captions), publishes across platforms, and improves automatically.

This MCP server gives you programmatic access to the whole loop. You are
interacting with GEN through MCP tools. This reference teaches you **the
5-step journey** every user takes, and which tools belong to each step.

## Authentication

All calls use a Personal Access Token (PAT) sent as `X-API-Key`.

1. Log in at https://gen.pro
2. Pick an agent
3. Go to the **API** page in the sidebar
4. Click **Create API Key**
5. Copy the token (shown once) → set as `GEN_API_KEY`

Manage PATs programmatically with `gen_list_api_keys`,
`gen_create_api_key`, `gen_revoke_api_key`.

## Mental Model

Think of GEN as a hierarchy:

1. **Workspace (Organization)** — a company or brand container. Holds billing,
   team members, and credits.
2. **Agent** — a brand identity inside a workspace. Has a name, personality,
   voice, inspiration sources, and its own social accounts. **Every content
   operation is scoped to an agent via `agent_id`.**
3. **Vidsheet (Auto Content Engine)** — a spreadsheet-like production pipeline
   attached to an agent. Each column is a content type, each row is one piece
   of content, each cell holds generated or user-supplied media.
4. **Creation Cards** — the generation recipes inside cells. A creation card
   says "generate a video from this text with this model at this aspect ratio".

Within a vidsheet:
- **Columns** define content types (text script, hero image, video clip, VO, etc.)
- **Rows** represent one piece of content across all columns
- **Cells** are the intersection of a row and column — where content lives
- **Layers** are composition elements within a video cell (overlays, tracks, clips)
- **Generations** are async AI jobs that produce content in a cell or layer

─────────────────────────────────────────────────────────────────────────────

# The 5-Step Journey

Every user of GEN — human or AI — follows the same 5-step arc. This server's
157 tools are organized around it. **Always know which step you're in.**

```
  Step 1           Step 2            Step 3             Step 4            Step 5
  ──────           ──────            ──────             ──────            ──────
  Set Up    →    Generate    →     Idea to      →     Edit &     →     Export &
  Agent          Ideas             Vidsheet           Generate          Publish
```

─────────────────────────────────────────────────────────────────────────────

## Step 1 — Set Up Your Agent

**What this step does.** Before content can be made, the agent needs identity.
You create a workspace (organization), create an agent inside it, teach it who
it is (overview, personality, inspiration sources, look, voice), and attach the
API keys (PAT + voice provider) it needs to generate content.

Think of this as onboarding. Do it once per agent. Do it well — the downstream
ideas and videos are only as good as the identity and voice set here.

**Top tools for this step:**

| Tool | When to use |
|---|---|
| `gen_get_me` | Start here. Verify your PAT works and see which workspaces you belong to. |
| `gen_list_organizations` | List workspaces. Each agent lives inside one. |
| `gen_create_organization` | New workspace. Needed only if the user doesn't already have one. |
| `gen_list_agents` | List agents in a workspace. Use the returned `agent_id` for everything else. |
| `gen_create_agent` | New agent inside a workspace. Pass `organization_id`. |
| `gen_get_agent_core` | **STAR tool for reads.** Returns identity + overview + personality + inspiration + voice + look + accounts in one call. Always read before updating. |
| `gen_update_agent_core` | **STAR tool for writes.** Set identity/overview/personality/voice in one call. Merge semantics for identity and overview; replace semantics for personality, inspiration, voice, accounts. |
| `gen_list_agent_voices` | Browse available voices (public + user_designed + user_trained + user_elevenlabs). Pick one, then bind it via `gen_update_agent_core` voice section. |
| `gen_connect_agent_elevenlabs` | Attach the user's ElevenLabs key so custom voices appear in the voice library. |
| `gen_create_api_key` | Issue a PAT the agent or its downstream tools can use. Returned plain text ONCE. |

**Voice design flow** (only if the user wants to design a new voice here
rather than using the web UI):
`gen_generate_voice_script` → `gen_generate_voice_description` →
`gen_generate_voice_samples` → `gen_design_voice`.
For cloning from a sample clip, use `gen_clone_voice` (synchronous). To
audition any voice, `gen_preview_voice` + `gen_get_voice_preview_status`.

**Example — from zero to a ready agent:**

```bash
# 1. Verify auth and pick a workspace
curl https://api.gen.pro/v1/me \\
  -H "X-API-Key: $GEN_API_KEY"

# 2. Create an agent in that workspace
curl -X POST https://api.gen.pro/v1/agents \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{"organization_id":"<workspace_id>","agent":{"name":"Santiago"}}'
# → returns {"id":"<agent_id>", ...}

# 3. Fill in identity + overview + personality in one call
curl -X PATCH https://api.gen.pro/v1/agents/<agent_id>/core \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{
    "identity": {"name": "Santiago", "profile_photo_url": "https://..."},
    "overview": {
      "brand_name": "Santiago Fitness",
      "description": "Home workouts for busy parents",
      "identity_type": "character",
      "goal": "growth",
      "keywords": ["home workouts","busy parents","no equipment"],
      "target_platforms": ["tiktok","instagram"],
      "shortform": true
    },
    "personality": "Warm, disciplined, early-morning energy. Never preachy.",
    "inspiration": [
      {"url": "https://tiktok.com/@some_creator", "platform": "tiktok"}
    ]
  }'
```

→ Continue to Step 2 with the `agent_id` in hand.

─────────────────────────────────────────────────────────────────────────────

## Step 2 — Generate Content Ideas

**What this step does.** The agent has an identity. Now you ask it for ideas.
Ideas aren't just titles — each one is a full video concept grounded in real
trend data from social platforms and research sources, with a hook, full script,
estimated duration, video type, pre-selected assets, and a timeline manifest.
You can refine iteratively in conversation, set persistent preferences, and
optionally trigger content monitoring jobs that keep scraping trending posts in
the background.

This step is powered by the **agent.gen.pro** service (separate from the main
content API). Tools that hit it live under "Agent Ideas" below.

**Top tools for this step:**

| Tool | When to use |
|---|---|
| `gen_generate_content_ideas` | **Starting point.** Generates N video ideas for an agent. Returns a `run_id` — poll with `gen_get_run_status`. |
| `gen_get_run_status` | Poll every 5s until `completed`. Ideas arrive in the messages array. |
| `gen_list_content_ideas` | List all ideas for the agent (across runs). Filter by status. |
| `gen_refine_content_ideas` | Feedback on existing ideas — "redo idea 2 as a montage". Requires the `conversation_id` from the original run. |
| `gen_set_content_preference` | Persistent rules that apply to EVERY future generation ("always use statement hooks", "never mention competitors"). Different from per-batch `requirements`. |
| `gen_decide_agent_run` | Approve or reject a pending action gate on a run. |
| `gen_update_idea_status` | Promote an idea: generated → approve_to_create → ready_for_review → approved_to_post → posted. |
| `gen_run_research` | Standalone research on any topic. Use for trend hunts before generating ideas. |
| `gen_create_song_mix` | Combine multiple songs into one continuous DJ-style audio mix. Returns a generation_id to poll with gen_get_generation. |
| `gen_create_monitoring_job` | Schedule ongoing scrapes of a hashtag/creator/keyword — the data feeds back into future idea generation. |
| `gen_list_conversations` / `gen_get_conversation` | Review chat history before refining. |

**Three layers of control**

- **Per-batch requirements** — one-time constraints passed to
  `gen_generate_content_ideas` (`requirements: ["under 12 seconds"]`).
- **Long-term preferences** — persistent rules via
  `gen_set_content_preference`. Apply to ALL future runs.
- **Feedback/refinement** — iterate on specific ideas in the same conversation
  via `gen_refine_content_ideas`.

**Video types** (pass as `video_type` filter):
`talking_avatar`, `green_screen`, `montage`, `text_driven`, `pov_object`,
`voiceover`, `split_screen`, `skit`.

**Each idea returns:** `title`, `hook`, `full_script`, `video_type`,
`estimated_duration`, `selected_assets[]` (pre-picked images/videos/audio with
`clip_range` and recommended `usage`), `project_manifest` (timeline_layers),
`inspiration_sources[]`, `rationale`.

**Example — generate 5 ideas and poll to completion:**

```bash
# 1. Kick off a run
curl -X POST https://agent.gen.pro/v1/agent/run \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{"agent_id":"<agent_id>","message":"generate 5 montage ideas focused on before/after"}'
# → {"run_id":"<run_id>", "conversation_id":"<conv_id>"}

# 2. Poll
curl "https://agent.gen.pro/v1/agent/runs/<run_id>" \\
  -H "X-API-Key: $GEN_API_KEY"
# → {"status":"completed", "messages":[{"ideas":[...]}]}

# 3. Approve the best one
curl -X PUT "https://agent.gen.pro/v1/agent/ideas/<idea_id>/status/approve_to_create" \\
  -H "X-API-Key: $GEN_API_KEY"
```

→ Continue to Step 3 carrying the approved `idea_id`.

─────────────────────────────────────────────────────────────────────────────

## Step 3 — Convert Idea to Vidsheet

**What this step does.** An approved idea is still abstract — it has a script
and an asset list but nothing to edit or render yet. This step materializes the
idea into a **vidsheet** (Auto Content Engine): a spreadsheet-like pipeline
pre-populated with the right columns (text, image, video, audio, final_video,
stats) and rows.

Two paths:
- **Template path** (fastest): clone a pre-configured template into the agent.
  Templates come with columns and example rows wired up for common formats
  like "Talking Avatar", "Montage", "Split Screen". Use this 80% of the time.
  After cloning, PATCH cells to inject the idea's script, hook, and variables.
- **From-scratch path**: create an empty engine and build columns manually.
  Only reach for this if no template fits.

**Top tools for this step:**

| Tool | When to use |
|---|---|
| `gen_list_templates` | Browse pre-built vidsheet templates. Check here FIRST. |
| `gen_get_template` | Inspect a template's columns and structure before cloning. |
| `gen_clone_template` | Clone a template into the agent. Returns a ready-to-edit vidsheet. The **fastest** path to production. |
| `gen_create_engine` | Create an empty engine. Use only if no template fits. |
| `gen_get_engine` | Fetch an engine with all columns, rows, cells in one call — do this before editing. |
| `gen_clone_engine` | Duplicate an existing engine (same agent or cross-agent). |

**Example — template clone path:**

```bash
curl https://api.gen.pro/v1/templates/projects \\
  -H "X-API-Key: $GEN_API_KEY"
# → pick a slug like "tiktok-montage-v2"

curl -X POST https://api.gen.pro/v1/templates/spreadsheets/tiktok-montage-v2/clone \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{"agent_id":"<agent_id>"}'
# → {"engine_id":"<engine_id>", ...}
```

→ Continue to Step 4 with `engine_id` + `agent_id`.

─────────────────────────────────────────────────────────────────────────────

## Step 4 — Edit & Generate

**What this step does.** The vidsheet exists, rows exist, columns exist. Now
you fill the ingredient cells (scripts, prompts, reference images) and trigger
AI generations to produce text, images, video clips, speech, lipsync, and
captions. You can stack **layers** inside a video cell to compose overlays,
tracks, and clips. Every generation returns a `generation_id` you poll until
`completed`.

**Top tools for this step:**

| Tool | When to use |
|---|---|
| `gen_get_engine` | Read the full engine (columns, rows, cells) before editing. |
| `gen_list_rows_delta` | Poll only the rows that CHANGED since a cursor while watching a busy sheet; `row_ids` + `cursor` drive deletion reconciliation. |
| `gen_update_cell` | Set a cell value directly (text, prompt, etc.). |
| `gen_generate_content` | **Workhorse.** Trigger AI generation for a cell. Returns `generation_id`. |
| `gen_generate_layer` | Trigger AI generation for a specific layer within a video cell. |
| `gen_get_generation` | Poll generation status every 5s until `completed`. |
| `gen_list_cell_jobs` | Fetch one cell's (or one video layer's) generation/job history without pulling the whole row. |
| `gen_stop_generation` | Stop a running generation (refunds credits). |
| `gen_continue_generation` | Resume a stopped generation (re-charges credits). |
| `gen_create_layer` / `gen_update_layer` | Compose video layers inside a cell. |
| `gen_create_row` / `gen_duplicate_row` | Add or duplicate rows for batch production. Pass `idempotency_key` so a retried call replays the original result instead of creating a duplicate. |
| `gen_import_asset_from_url` | Import a YouTube/TikTok/Instagram/direct URL as an asset. |
| `gen_create_direct_upload` | Get a pre-signed URL for large file uploads (>50 MB). |
| `gen_transcribe` | Standalone audio/video → text transcript with timestamps. Exactly one of `audio_url`/`video_url`/`content_resource_id`. Billed by duration. |
| `gen_estimate_job` | Check the credit cost BEFORE triggering a paid generation. |

**Generation types and models:**

```
TEXT:              generation_type="text",
                   data={model: "gemini_2_5_pro"|"gpt_4o"|"claude_sonnet_4"|..., prompt: "..."}

IMAGE:             generation_type="image_from_text",
                   data={prompt: "...", model: "nano-banana-pro"|"midjourney"|"grok",
                         aspect_ratio: "1:1"|"9:16"|"16:9"}

VIDEO (text):      generation_type="video_from_text",
                   data={prompt: "...", model: "veo_3"|"veo_3_1"|"seedance-2.0"|
                         "kling_2_1"|"kling_2_6"|"sora_2"|"grok",
                         aspect_ratio: "9:16"|"16:9"|"1:1", duration: 5, resolution: "1080p"}

VIDEO (image):     generation_type="video_from_image",
                   data={prompt: "...", model: "kling_2_1"|"kling_2_6"|"veo_3"|"veo_3_1"|
                         "seedance-2.0"|"sora_2"|"grok",
                         image_resource_id: 123, aspect_ratio: "9:16"}

VIDEO (clips):     generation_type="video_from_ingredients",
                   data={prompt: "...", model: "pika"|"kling_1_6"|"grok",
                         asset_resource_ids: [123, 456]}

SPEECH:            generation_type="speech_from_text",
                   data={script: "...", voice_method: "my_voices"|"design_voice"|"clone_voice",
                         voice_id: "...", voice_model_provider?: "supertonic_3"|"qwen3_voice_design"}

LIPSYNC:           generation_type="lipsync",
                   data={model: "sync_so"|"gen", video_resource_id: 123, audio_resource_id: 456}

CAPTIONS:          generation_type="captions",
                   data={model: "gemini", source_resource_id: 123}
```

Credits are pre-charged before generation and refunded automatically on failure
or stop. Always call `gen_estimate_job` before an expensive generation.
Call `gen_get_credit_balance` if you're unsure whether funds are sufficient.

**3-call pattern for any cell:**

```bash
# 1. Set the prompt in the ingredient cell
curl -X PATCH "https://api.gen.pro/v1/vidsheet/$ENGINE_ID/cells/$CELL_ID?agent_id=$AGENT_ID" \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{"spreadsheet_cell": {"value": "San Antonio taco truck at golden hour"}}'

# 2. Trigger generation
curl -X POST "https://api.gen.pro/v1/vidsheet/$ENGINE_ID/cells/$VIDEO_CELL_ID/generate?agent_id=$AGENT_ID" \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{"generation_type": "video_from_text", "data": {"model": "veo_3", "aspect_ratio": "9:16", "duration": 8}}'
# → {"generation_id": 789, "status": "pending"}

# 3. Poll until done
curl "https://api.gen.pro/v1/generations/789" -H "X-API-Key: $GEN_API_KEY"
# status: pending → processing → completed | failed | stopped
# on completed: result (text) or output_resources (media URLs)
```

→ Repeat for each column (script → image → voiceover → video). Then go to Step 5.

─────────────────────────────────────────────────────────────────────────────

## Step 5 — Export & Publish

**What this step does.** Composite all layers on the final_video cell into one
MP4 (render), then publish to social platforms: TikTok, Instagram, Facebook,
YouTube, and X. You can post immediately or schedule for a specific time.

**Top tools for this step:**

| Tool | When to use |
|---|---|
| `gen_render_video` | Composite all layers into the final MP4. Returns `generation_id` to poll. |
| `gen_get_generation` | Poll render status until `completed`; `output_resources[0].url` is the CDN URL. |
| `gen_get_social_connect_url` | Get an OAuth URL for the user to connect a social account in their browser. |
| `gen_list_connected_socials` | Check which platforms are connected before scheduling. |
| `gen_schedule_post` | Post immediately or schedule for a specific time. |
| `gen_list_scheduled_posts` | View the content calendar. |
| `gen_get_post_status` | Poll post status — `accepted` → `publishing` → `published` or `failed`. |
| `gen_create_recurring_job` | Set up an automated daily/weekly content job. |
| `gen_preview_recurring_job_prompt` | Parse a recurring-job prompt into the row strategy/actions it implies — WITHOUT saving (free, read-only). Check before saving, or diff against existing actions. |
| `gen_draft_test_recurring_job` | Test an UNSAVED recurring job once before committing to save it (configure → Test → Save). Paid-media gated. |

**Render the final video:**

```bash
curl -X POST "https://api.gen.pro/v1/vidsheet/$ENGINE_ID/cells/$FINAL_VIDEO_CELL_ID/render?agent_id=$AGENT_ID" \\
  -H "X-API-Key: $GEN_API_KEY"
# → {"generation_id": 56789, "status": "pending"}

# Poll:
curl "https://api.gen.pro/v1/generations/56789" -H "X-API-Key: $GEN_API_KEY"
# on completed: output_resources[0].url = public CDN URL
```

**Connect a social account** (user opens URL in their browser):

```bash
curl -X POST "https://python.gen.pro/platform/get_authorization_url?platform=tiktok" \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{"agent_id": "<agent_id>"}'
# → {"url": "https://..."} — give this URL to the user to open in their browser
```

**Post immediately:**

```bash
curl -X POST "https://python.gen.pro/schedule/with-post" \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{
    "agent_id": "<agent_id>",
    "platform": ["tiktok"],
    "media_url": "https://cdn.gen.pro/outputs/render_xyz.mp4",
    "description": "The $2 taco at 2am #streetfood #tacotok",
    "media_type": "VIDEO",
    "schedule_type": "now"
  }'
```

**Schedule for later:**

```bash
curl -X POST "https://python.gen.pro/schedule/with-post" \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{
    "agent_id": "<agent_id>",
    "platform": ["instagram"],
    "media_url": "https://cdn.gen.pro/outputs/render_xyz.mp4",
    "description": "Morning routine #wellness",
    "schedule_type": "specific_time",
    "scheduled_time": "2026-08-05T09:00:00Z"
  }'
```

**Automate with recurring jobs:**

```bash
curl -X POST "https://agent.gen.pro/v1/agents/<agent_id>/recurring_jobs" \\
  -H "X-API-Key: $GEN_API_KEY" -H "Content-Type: application/json" \\
  -d '{
    "job_type": "generate_content_ideas",
    "schedule": {"cadence": "daily", "time_of_day": "09:00", "timezone": "America/Chicago"},
    "delivery": {"type": "chat_only"}
  }'
```

─────────────────────────────────────────────────────────────────────────────

## Credits & Errors

Credits are consumed by every paid operation (generations, research, rendering).
The server flags `insufficient_credits: true` when a call fails due to low
balance. Use `gen_get_credit_balance` to check and `gen_buy_credits` to add
more (confirmation-gated). Use `gen_estimate_job` before expensive generations.
`gen_list_subscriptions` shows the user's active plans across their workspaces
(ACTIVE first).

Standard error shape:
```json
{"error": "Human-readable message", "error_code": "machine_readable_code"}
```

Common codes: `insufficient_credits` · `not_found` · `unauthorized` ·
`unprocessable_entity` · `rate_limit_exceeded`
"""
