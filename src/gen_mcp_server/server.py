"""GEN MCP tools — Python/FastMCP port of the TS server (origin/main @ 6d91d46).
Behavior-parity target: @poweredbygen/gen-mcp-server. Mechanical handlers are
codegen (reproducible by the daily sync); complex tools are hand-ported below.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastmcp import FastMCP
from pydantic import Field

from .client import api_call, agent_api_call, agent_core_api_call, form_call, integration_api_call, json_result
from .generation_types import resolve_generation_type
from .reference import API_REFERENCE
from .vidsheet_contract import enum_values, model_facing_fields, require_enum_value

# These MCP JSON-schema enums are derived at import time from the vendored
# Rails artifact.  Do not replace them with a hand-maintained Literal list.
VIDSHEET_COLUMN_TYPES = enum_values("spreadsheet_column", "type")
VIDEO_LAYER_TYPES = enum_values("video_layer", "type")
VidsheetColumnType = Annotated[
    str,
    Field(
        description="Column type accepted by Rails",
        json_schema_extra={"enum": list(VIDSHEET_COLUMN_TYPES)},
    ),
]
OptionalVidsheetColumnType = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Column type accepted by Rails",
        json_schema_extra={"enum": list(VIDSHEET_COLUMN_TYPES)},
    ),
]
VideoLayerType = Annotated[
    str,
    Field(
        description="Persisted video-layer type accepted by Rails",
        json_schema_extra={"enum": list(VIDEO_LAYER_TYPES)},
    ),
]
OptionalVideoLayerType = Annotated[
    Optional[str],
    Field(
        default=None,
        description="Persisted video-layer type accepted by Rails",
        json_schema_extra={"enum": list(VIDEO_LAYER_TYPES)},
    ),
]

# Assert the tool signatures below remain model-facing.  Rails' wire contract
# has ``position`` for editor persistence, but models must use named reorder
# operations with ID lists; this server derives the integer positions itself.
model_facing_fields("spreadsheet_column", {"title", "type"})
model_facing_fields("video_layer", {"name", "type", "additional_attributes"})

mcp = FastMCP(name="gen", version="1.0.0")


@mcp.resource("gen://api-reference", mime_type="text/markdown")
def api_reference() -> str:
    """GEN MCP system prompt + API reference. Read this first."""
    return API_REFERENCE


@mcp.tool(name="gen_get_me", description="Step 1 (Agent Setup): Get the authenticated user's profile and workspace memberships. Always call first to verify your PAT and discover which workspaces you have access to.")
async def gen_get_me() -> str:
    data = await api_call("GET", "/me")
    return json_result(data)

@mcp.tool(name="gen_list_workspaces", description="Step 1 (Agent Setup): List all workspaces the authenticated user has access to. A workspace is the billing container; every agent lives inside one.")
async def gen_list_workspaces() -> str:
    data = await api_call("GET", "/workspaces")
    return json_result(data)

@mcp.tool(name="gen_list_agents", description="Step 1 (Agent Setup): List agents, optionally filtered by workspace. Use the returned agent_id for ALL downstream content operations (ideas, vidsheets, generations).")
async def gen_list_agents(
    workspace_id: Annotated[Optional[str], Field(default=None, description="Filter agents by workspace ID")] = None,
) -> str:
    path = "/agents"
    if workspace_id is not None:
        path += f"?workspace_id={workspace_id}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_list_organizations", description="Step 1 (Agent Setup): List all organizations/workspaces the authenticated user is a member of, including credits, role, and plan.")
async def gen_list_organizations() -> str:
    data = await api_call("GET", "/organizations")
    return json_result(data)

@mcp.tool(name="gen_create_organization", description="Step 1 (Agent Setup): Create a new organization/workspace. You become owner automatically. Only needed if the user doesn't already have a workspace.")
async def gen_create_organization(
    name: Annotated[str, Field(description="Display name for the organization")],
) -> str:
    data = await api_call("POST", "/organizations", {"organization": {"name": name}})
    return json_result(data)

@mcp.tool(name="gen_get_organization", description="Step 1 (Agent Setup): Get details of a specific organization by ID.")
async def gen_get_organization(
    organization_id: Annotated[str, Field(description="The organization ID")],
) -> str:
    data = await api_call("GET", f"/organizations/{organization_id}")
    return json_result(data)

@mcp.tool(name="gen_update_organization", description="Step 1 (Agent Setup): Update an organization's name (requires owner or manager role).")
async def gen_update_organization(
    organization_id: Annotated[str, Field(description="The organization ID to update")],
    name: Annotated[str, Field(description="New display name for the organization")],
) -> str:
    data = await api_call("PATCH", f"/organizations/{organization_id}", {"organization": {"name": name}})
    return json_result(data)

@mcp.tool(name="gen_delete_organization", description="Step 1 (Agent Setup): Permanently delete an organization and all associated data (requires owner role, irreversible).")
async def gen_delete_organization(
    organization_id: Annotated[str, Field(description="The organization ID to delete")],
) -> str:
    data = await api_call("DELETE", f"/organizations/{organization_id}")
    return json_result(data)

@mcp.tool(name="gen_create_agent", description="Step 1 (Agent Setup): Create a new agent inside a workspace. After creation, use gen_update_agent_core to fill in identity, overview, personality, voice, and inspiration sources.")
async def gen_create_agent(
    name: Annotated[str, Field(description="Agent name (must be unique within the workspace)")],
    description: Annotated[Optional[str], Field(default=None, description="Short description of the agent's purpose")] = None,
    time_zone: Annotated[Optional[str], Field(default=None, description="IANA time zone identifier (e.g. America/New_York)")] = None,
    organization_id: Annotated[Optional[str], Field(default=None, description="Workspace ID to create the agent in")] = None,
    eleven_lab_api_key: Annotated[Optional[str], Field(default=None, description="ElevenLabs API key for voice synthesis")] = None,
    hume_ai_api_key: Annotated[Optional[str], Field(default=None, description="Hume AI API key for emotional voice")] = None,
) -> str:
    agent_attrs: dict = {"name": name}
    if description is not None:
        agent_attrs["description"] = description
    if time_zone is not None:
        agent_attrs["time_zone"] = time_zone
    if eleven_lab_api_key is not None:
        agent_attrs["eleven_lab_api_key"] = eleven_lab_api_key
    if hume_ai_api_key is not None:
        agent_attrs["hume_ai_api_key"] = hume_ai_api_key
    body: dict = {"agent": agent_attrs}
    if organization_id is not None:
        body["organization_id"] = organization_id
    data = await api_call("POST", "/agents", body)
    return json_result(data)

@mcp.tool(name="gen_get_agent", description="Step 1 (Agent Setup): Get full details of a specific agent by ID. For reading full setup state (identity + overview + personality + voice + inspiration + accounts), prefer gen_get_agent_core.")
async def gen_get_agent(
    agent_id: Annotated[str, Field(description="The agent ID")],
    with_organization_uuid: Annotated[Optional[str], Field(default=None, description="If 'true', includes the workspace UUID in the response")] = None,
) -> str:
    path = f"/agents/{agent_id}"
    if with_organization_uuid is not None:
        path += f"?with_organization_uuid={with_organization_uuid}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_update_agent", description="Step 1 (Agent Setup): Update an existing agent's name, description, time zone, or voice keys. For richer setup updates (personality, inspiration, accounts, voice binding), use gen_update_agent_core.")
async def gen_update_agent(
    agent_id: Annotated[str, Field(description="The agent ID to update")],
    name: Annotated[Optional[str], Field(default=None, description="Updated agent name")] = None,
    description: Annotated[Optional[str], Field(default=None, description="Updated description")] = None,
    time_zone: Annotated[Optional[str], Field(default=None, description="IANA time zone identifier")] = None,
    eleven_lab_api_key: Annotated[Optional[str], Field(default=None, description="ElevenLabs API key")] = None,
    hume_ai_api_key: Annotated[Optional[str], Field(default=None, description="Hume AI API key")] = None,
) -> str:
    agent_attrs: dict = {}
    if name is not None:
        agent_attrs["name"] = name
    if description is not None:
        agent_attrs["description"] = description
    if time_zone is not None:
        agent_attrs["time_zone"] = time_zone
    if eleven_lab_api_key is not None:
        agent_attrs["eleven_lab_api_key"] = eleven_lab_api_key
    if hume_ai_api_key is not None:
        agent_attrs["hume_ai_api_key"] = hume_ai_api_key
    data = await api_call("PATCH", f"/agents/{agent_id}", {"agent": agent_attrs})
    return json_result(data)

@mcp.tool(name="gen_delete_agent", description="Step 1 (Agent Setup): Soft-delete an agent (requires owner/manager role or being the creator).")
async def gen_delete_agent(
    agent_id: Annotated[str, Field(description="The agent ID to delete")],
) -> str:
    data = await api_call("DELETE", f"/agents/{agent_id}")
    return json_result(data)

@mcp.tool(name="gen_list_agent_avatars", description="Step 1 (Agent Setup): List avatar images for an agent, with the primary avatar first.")
async def gen_list_agent_avatars(
    agent_id: Annotated[str, Field(description="The agent ID")],
    cursor: Annotated[Optional[str], Field(default=None, description="Return avatars with ID greater than this value (for pagination)")] = None,
) -> str:
    path = f"/agents/{agent_id}/avatars"
    if cursor is not None:
        path += f"?cursor={cursor}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_create_agent_avatar", description="Step 1 (Agent Setup): Create an avatar for an agent using a DeGod avatar ID (for file uploads, use the API directly via direct_upload + a PATCH to the agent).")
async def gen_create_agent_avatar(
    agent_id: Annotated[str, Field(description="The agent ID")],
    degod_avatar_id: Annotated[Optional[str], Field(default=None, description="DeGod avatar ID to use")] = None,
) -> str:
    body = {"agent_avatars_attributes": [{"degod_avatar_id": degod_avatar_id} if degod_avatar_id else {}]}
    data = await api_call("POST", f"/agents/{agent_id}/avatars", body)
    return json_result(data)

@mcp.tool(name="gen_delete_agent_avatar", description="Step 1 (Agent Setup): Delete one or more avatars from an agent (separate multiple IDs with underscores).")
async def gen_delete_agent_avatar(
    agent_id: Annotated[str, Field(description="The agent ID")],
    avatar_id: Annotated[str, Field(description="The avatar ID to delete (use underscores for multiple, e.g. '7_8_9')")],
) -> str:
    data = await api_call("DELETE", f"/agents/{agent_id}/avatars/{avatar_id}")
    return json_result(data)

@mcp.tool(name="gen_add_agent_look", description="Step 1 (Agent Setup): Attach an uploaded image as an additional look (non-primary) on the agent. Use after gen_create_direct_upload + PUT-ing the file bytes to the returned upload URL: pass the direct-upload response's signed_id here. Existing primary avatar is preserved. Use gen_set_agent_primary_photo when the image should become the primary photo.")
async def gen_add_agent_look(
    agent_id: Annotated[str, Field(description="The agent ID")],
    signed_id: Annotated[str, Field(description="The signed_id returned from gen_create_direct_upload after uploading the image")],
) -> str:
    data = await api_call("POST", f"/agents/{agent_id}/avatars", {"agent_avatars_attributes": [{"file": signed_id}]})
    return json_result(data)

@mcp.tool(name="gen_set_agent_primary_photo", description="Step 1 (Agent Setup): Attach an uploaded image and set it as the agent's PRIMARY photo (replacing any existing primary). Use after gen_create_direct_upload + PUT-ing the file bytes to the returned upload URL: pass the direct-upload response's signed_id here. The agent's primary_avatar_url updates immediately. To add as a non-primary look instead, use gen_add_agent_look.")
async def gen_set_agent_primary_photo(
    agent_id: Annotated[str, Field(description="The agent ID")],
    signed_id: Annotated[str, Field(description="The signed_id returned from gen_create_direct_upload after uploading the image")],
) -> str:
    data = await api_call("PATCH", f"/agents/{agent_id}", {"agent": {"agent_avatars_attributes": [{"file": signed_id, "is_primary": True}]}})
    return json_result(data)

@mcp.tool(name="gen_get_agent_core", description="Step 1 (Agent Setup): STAR READ TOOL. Returns all agent setup sections in one call: identity (name + profile photo), overview (brand name, description, identity type, goal, keywords, target platforms), personality, inspiration sources, voice, look (description + reference images), and accounts (the agent's own socials). Always call before gen_update_agent_core.")
async def gen_get_agent_core(
    agent_id: Annotated[str, Field(description="The agent ID")],
) -> str:
    data = await api_call("GET", f"/agents/{agent_id}/core")
    return json_result(data)

@mcp.tool(name="gen_update_agent_core", description="Step 1 (Agent Setup): STAR WRITE TOOL. Update any combination of agent setup sections in one call: identity, overview, personality, inspiration, voice, look, accounts. Merge semantics for identity + overview + look.description; replace semantics for personality + inspiration + voice + accounts. Returns 200 on full success or 207 with per-section results on partial failure. This is the only supported path for agent setup writes.")
async def gen_update_agent_core(
    agent_id: Annotated[str, Field(description="The agent ID")],
    identity: Annotated[Optional[dict], Field(default=None, description="Identity merge-patch")] = None,
    overview: Annotated[Optional[dict], Field(default=None, description="Overview merge-patch, e.g. {'goal': 'growth'} | {'brand_name': '...', 'identity_type': 'personal'}")] = None,
    personality: Annotated[Optional[str], Field(default=None, description="Full personality / backstory text — replaces existing")] = None,
    inspiration: Annotated[Optional[list], Field(default=None, description="Inspiration source URLs — replaces full list")] = None,
    look: Annotated[Optional[dict], Field(default=None, description="Look description merge-patch (reference_images managed via item-level tools)")] = None,
    voice: Annotated[Optional[dict], Field(default=None, description="Voice reference — replaces default")] = None,
    accounts: Annotated[Optional[list], Field(default=None, description="Agent's own socials — replaces full list")] = None,
) -> str:
    patch = {
        "identity": identity, "overview": overview, "personality": personality,
        "inspiration": inspiration, "look": look, "voice": voice, "accounts": accounts,
    }
    body = {k: v for k, v in patch.items() if v is not None}
    data = await api_call("PATCH", f"/agents/{agent_id}/core", body)
    return json_result(data)

@mcp.tool(name="gen_add_agent_account", description="Step 1 (Agent Setup): Add one social account to the agent (the agent's OWN account, not an inspiration source). Detects platform from URL if not provided.")
async def gen_add_agent_account(
    agent_id: Annotated[str, Field(description="The agent ID")],
    url: Annotated[str, Field(description="Full social URL")],
    platform: Annotated[Optional[str], Field(default=None, description="Override platform detection (e.g. 'tiktok', 'instagram')")] = None,
    display_name: Annotated[Optional[str], Field(default=None, description="")] = None,
) -> str:
    body = {"url": url}
    if platform is not None:
        body["platform"] = platform
    if display_name is not None:
        body["display_name"] = display_name
    data = await api_call("POST", f"/agents/{agent_id}/core/accounts", body)
    return json_result(data)

@mcp.tool(name="gen_add_agent_inspiration", description="Step 1 (Agent Setup): Add one inspiration source URL to the agent. These are creators/accounts the agent draws style from — NOT the agent's own socials.")
async def gen_add_agent_inspiration(
    agent_id: Annotated[str, Field(description="The agent ID")],
    url: Annotated[str, Field(description="Full URL of the inspiration source")],
    platform: Annotated[Optional[str], Field(default=None, description="e.g. 'tiktok', 'instagram', 'youtube'")] = None,
) -> str:
    body = {"url": url}
    if platform is not None:
        body["platform"] = platform
    data = await api_call("POST", f"/agents/{agent_id}/core/inspiration", body)
    return json_result(data)

@mcp.tool(name="gen_get_agent_profile", description="Step 1 (Agent Setup): Get the agent profile from the agentic service (alternate to gen_get_agent_core). Returns grouped sections: identity (name, avatar, persona), voice (API keys, default voice), and brand (keywords, platforms, linked accounts, content_idea_preferences). Useful when agent.gen.pro is the canonical source (content idea preferences live here).")
async def gen_get_agent_profile(
    agent_id: Annotated[str, Field(description="The agent ID")],
) -> str:
    data = await agent_api_call("GET", f"/agent/profile?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_create_agent_profile", description="Step 1 (Agent Setup): Initialize an agent's profile on the agentic service. Send any combination of identity, voice, and brand sections. Identity: name, description, persona. Voice: API keys and default_voice. Brand: brand_name, description, goal, keywords, target_platforms, shortform, longform, linked_accounts, content_idea_preferences.")
async def gen_create_agent_profile(
    agent_id: Annotated[str, Field(description="The agent ID")],
    identity: Annotated[Optional[dict], Field(default=None, description="Identity: name, description, persona")] = None,
    voice: Annotated[Optional[dict], Field(default=None, description="Voice: API keys and default voice config")] = None,
    brand: Annotated[Optional[dict], Field(default=None, description="Brand section: brand_name, description, goal, keywords, target_platforms, content_idea_preferences")] = None,
) -> str:
    body = {}
    if identity is not None:
        body["identity"] = identity
    if voice is not None:
        body["voice"] = voice
    if brand is not None:
        body["brand"] = brand
    data = await agent_api_call("POST", f"/agent/profile?agent_id={agent_id}", body)
    return json_result(data)

@mcp.tool(name="gen_update_agent_profile", description="Step 1 (Agent Setup): Update an existing agent profile on the agentic service. Only send the sections and fields you want to change. Array fields (keywords, platforms, linked_accounts) are replaced entirely, not appended.")
async def gen_update_agent_profile(
    agent_id: Annotated[str, Field(description="The agent ID")],
    identity: Annotated[Optional[dict], Field(default=None, description="")] = None,
    voice: Annotated[Optional[dict], Field(default=None, description="")] = None,
    brand: Annotated[Optional[dict], Field(default=None, description="Brand section: brand_name, description, goal, keywords, target_platforms, content_idea_preferences")] = None,
) -> str:
    body = {}
    if identity is not None:
        body["identity"] = identity
    if voice is not None:
        body["voice"] = voice
    if brand is not None:
        body["brand"] = brand
    data = await agent_api_call("PUT", f"/agent/profile?agent_id={agent_id}", body)
    return json_result(data)

@mcp.tool(name="gen_reset_agent_profile", description="Step 1 (Agent Setup): Reset the agent's brand configuration on the agentic service. Clears brand name, keywords, platforms, linked accounts, and content preferences. Does NOT delete the agent or voice settings.")
async def gen_reset_agent_profile(
    agent_id: Annotated[str, Field(description="The agent ID")],
) -> str:
    data = await agent_api_call("DELETE", f"/agent/profile?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_connect_agent_elevenlabs", description="Step 1 (Agent Setup): Connect the user's ElevenLabs API key to the agent. Validates the key before saving. Once connected, gen_list_agent_voices includes the user's ElevenLabs voices as source=user_elevenlabs.")
async def gen_connect_agent_elevenlabs(
    agent_id: Annotated[str, Field(description="The agent ID")],
    api_key: Annotated[str, Field(description="The user's ElevenLabs API key")],
) -> str:
    data = await api_call("POST", f"/agents/{agent_id}/voice/integrations/elevenlabs", {"api_key": api_key})
    return json_result(data)

@mcp.tool(name="gen_list_agent_voices", description="Step 1 (Agent Setup): List available voices for the agent. Sources: public (shared catalog), user_designed (via prompt flow), user_trained (from audio clone), user_elevenlabs (from connected key). Filter with `source` to narrow. Pick a voice and bind it via gen_update_agent_core voice section.")
async def gen_list_agent_voices(
    agent_id: Annotated[str, Field(description="The agent ID")],
    source: Annotated[Optional[str], Field(default=None, description="Filter by source")] = None,
) -> str:
    path = f"/agents/{agent_id}/voice/library"
    if source is not None:
        path += f"?source={source}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_generate_voice_script", description="Step 1 (Agent Setup) — Voice design 1/4: generate a read-aloud script (the text the candidate voice will speak in step 3). Only needed when designing a new voice programmatically; most users do this in the web UI.")
async def gen_generate_voice_script(
    agent_id: Annotated[str, Field(description="The agent ID")],
    language: Annotated[Optional[str], Field(default=None, description="Target language (e.g. 'en', 'es')")] = None,
) -> str:
    body = {}
    if language is not None:
        body["language"] = language
    data = await api_call("POST", f"/agents/{agent_id}/voice/design/generate-script", body)
    return json_result(data)

@mcp.tool(name="gen_generate_voice_description", description="Step 1 (Agent Setup) — Voice design 2/4: generate style descriptors (tone, pace, energy). Requires gender.")
async def gen_generate_voice_description(
    agent_id: Annotated[str, Field(description="The agent ID")],
    gender: Annotated[str, Field(description="REQUIRED — e.g. 'male', 'female', 'non-binary'")],
    voice_description: Annotated[Optional[str], Field(default=None, description="Optional user hint like 'warm and confident'")] = None,
    language: Annotated[Optional[str], Field(default=None, description="")] = None,
    script: Annotated[Optional[str], Field(default=None, description="The script from step 1 (helps tune the description)")] = None,
) -> str:
    raw = {"gender": gender, "voice_description": voice_description, "language": language, "script": script}
    clean = {k: v for k, v in raw.items() if v is not None}
    data = await api_call("POST", f"/agents/{agent_id}/voice/design/generate-description", clean)
    return json_result(data)

@mcp.tool(name="gen_generate_voice_samples", description="Step 1 (Agent Setup) — Voice design 3/4: generate 3 candidate audio samples. Returns `{samples: [{generation_id, audio}, ...]}` — pick one and pass its `generation_id` to gen_design_voice to finalize.")
async def gen_generate_voice_samples(
    agent_id: Annotated[str, Field(description="The agent ID")],
    text: Annotated[str, Field(description="REQUIRED — the script to speak (from step 1)")],
    description: Annotated[Optional[str], Field(default=None, description="Style descriptor from step 2")] = None,
) -> str:
    body = {"text": text}
    if description is not None:
        body["description"] = description
    data = await api_call("POST", f"/agents/{agent_id}/voice/design/generate-samples", body)
    return json_result(data)

@mcp.tool(name="gen_design_voice", description="Step 1 (Agent Setup) — Voice design 4/4: finalize a designed voice by picking one of the candidates from step 3. Persists the new voice; shows up in gen_list_agent_voices under source=user_designed.")
async def gen_design_voice(
    agent_id: Annotated[str, Field(description="The agent ID")],
    generation_id: Annotated[str, Field(description="REQUIRED — opaque token from gen_generate_voice_samples")],
    name: Annotated[str, Field(description="REQUIRED — display name for the new voice")],
    gender: Annotated[Optional[str], Field(default=None, description="")] = None,
    language: Annotated[Optional[str], Field(default=None, description="")] = None,
    description: Annotated[Optional[str], Field(default=None, description="")] = None,
) -> str:
    raw = {"generation_id": generation_id, "name": name, "gender": gender, "language": language, "description": description}
    clean = {k: v for k, v in raw.items() if v is not None}
    data = await api_call("POST", f"/agents/{agent_id}/voice/design", clean)
    return json_result(data)

@mcp.tool(name="gen_clone_voice", description="Step 1 (Agent Setup): Clone a voice from an existing audio sample. Pass EITHER audio_url (preferred; server downloads it) OR audio_base64 (inline bytes for small clips). Synchronous — returns the created voice immediately. Shows up under source=user_trained.")
async def gen_clone_voice(
    agent_id: Annotated[str, Field(description="The agent ID")],
    name: Annotated[str, Field(description="REQUIRED — display name for the cloned voice")],
    audio_url: Annotated[Optional[str], Field(default=None, description="URL to an audio sample (mp3/wav). PREFERRED.")] = None,
    audio_base64: Annotated[Optional[str], Field(default=None, description="Base64-encoded audio bytes. Only for small clips.")] = None,
    gender: Annotated[Optional[str], Field(default=None, description="")] = None,
    language: Annotated[Optional[str], Field(default=None, description="")] = None,
    description: Annotated[Optional[str], Field(default=None, description="")] = None,
) -> str:
    raw = {"name": name, "audio_url": audio_url, "audio_base64": audio_base64, "gender": gender, "language": language, "description": description}
    clean = {k: v for k, v in raw.items() if v is not None}
    data = await api_call("POST", f"/agents/{agent_id}/voice/clone", clean)
    return json_result(data)

@mcp.tool(name="gen_preview_voice", description="Step 1 (Agent Setup): Generate a TTS preview of a voice saying a given text. Use to audition a voice before binding it via gen_update_agent_core. Returns a user_job_id — poll with gen_get_voice_preview_status.")
async def gen_preview_voice(
    agent_id: Annotated[str, Field(description="The agent ID")],
    voice_id: Annotated[str, Field(description="The voice ID to preview")],
    text: Annotated[str, Field(description="The text to speak (keep under 500 chars for fast preview)")],
) -> str:
    data = await api_call("POST", f"/agents/{agent_id}/voice/{voice_id}/preview", {"text": text})
    return json_result(data)

@mcp.tool(name="gen_get_voice_preview_status", description="Step 1 (Agent Setup): Poll the status of a TTS preview job from gen_preview_voice. Returns the full user_job — check `.status` (pending/processing/completed/failed) and read the audio from `.output_resources` when completed.")
async def gen_get_voice_preview_status(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The user_job_id returned by gen_preview_voice")],
) -> str:
    data = await api_call("GET", f"/agents/{agent_id}/voice/preview/{job_id}")
    return json_result(data)

@mcp.tool(name="gen_delete_voice", description="Step 1 (Agent Setup): Delete a user-owned voice (designed or trained). Returns 404 if the voice doesn't belong to the agent.")
async def gen_delete_voice(
    agent_id: Annotated[str, Field(description="The agent ID")],
    voice_id: Annotated[str, Field(description="The voice ID to delete")],
) -> str:
    data = await api_call("DELETE", f"/agents/{agent_id}/voice/{voice_id}")
    return json_result(data)

@mcp.tool(name="gen_list_api_keys", description="Step 1 (Agent Setup): List all Personal Access Tokens (API keys) for the authenticated user.")
async def gen_list_api_keys() -> str:
    data = await api_call("GET", "/persisted_tokens")
    return json_result(data)

@mcp.tool(name="gen_create_api_key", description="Step 1 (Agent Setup): Create a new Personal Access Token. The plain-text token is returned ONCE — store it securely.")
async def gen_create_api_key(
    name: Annotated[Optional[str], Field(default=None, description="Descriptive name for the API key")] = None,
    expires_in: Annotated[Optional[float], Field(default=None, description="Seconds until the key expires. Omit for a non-expiring key.")] = None,
) -> str:
    body = {}
    if name is not None:
        body["name"] = name
    if expires_in is not None:
        body["expires_in"] = expires_in
    data = await api_call("POST", "/persisted_tokens", body)
    return json_result(data)

@mcp.tool(name="gen_update_api_key", description="Step 1 (Agent Setup): Rename an existing Personal Access Token. Only the display name can be changed; the token value is immutable.")
async def gen_update_api_key(
    token_id: Annotated[str, Field(description="The token ID to rename")],
    name: Annotated[str, Field(description="New display name for the API key")],
) -> str:
    data = await api_call("PATCH", f"/persisted_tokens/{token_id}", {"persisted_token": {"name": name}})
    return json_result(data)

@mcp.tool(name="gen_revoke_api_key", description="Step 1 (Agent Setup): Revoke (delete) a single Personal Access Token. Use gen_revoke_all_api_keys to revoke every key at once.")
async def gen_revoke_api_key(
    token_id: Annotated[str, Field(description="The token ID to revoke")],
) -> str:
    data = await api_call("DELETE", f"/persisted_tokens/{token_id}/revoke")
    return json_result(data)

@mcp.tool(name="gen_revoke_all_api_keys", description="Step 1 (Agent Setup): Revoke ALL of the user's Personal Access Tokens at once. Irreversible — every existing key stops working immediately. Use gen_revoke_api_key to revoke just one.")
async def gen_revoke_all_api_keys() -> str:
    data = await api_call("DELETE", "/persisted_tokens/revoke_all")
    return json_result(data)

@mcp.tool(name="gen_generate_content_ideas", description="Step 2 (Content Ideas): STARTING POINT. Generates data-driven video content ideas for an agent, analyzing trending videos with engagement-weighted hooks and transcripts. Returns a run_id — poll with gen_get_run_status until completed. Each idea has title, hook, full_script, video_type, estimated_duration, selected_assets[], project_manifest, inspiration_sources, rationale.")
async def gen_generate_content_ideas(
    agent_id: Annotated[str, Field(description="The agent ID to generate ideas for")],
    message: Annotated[Optional[str], Field(default=None, description="Natural language request, e.g. 'generate 10 montage ideas focused on before/after transformations'")] = None,
    num_ideas: Annotated[Optional[float], Field(default=None, description="Number of ideas (1-50, default 5)")] = None,
    requirements: Annotated[Optional[list], Field(default=None, description="Per-batch constraints: ['focus on before/after', 'under 12 seconds']")] = None,
    video_type: Annotated[Optional[str], Field(default=None, description="Filter: talking_avatar | green_screen | montage | text_driven | pov_object | voiceover | split_screen | skit")] = None,
    conversation_id: Annotated[Optional[str], Field(default=None, description="Continue existing conversation to refine ideas")] = None,
) -> str:
    body: dict = {"agent_id": agent_id}
    if message is not None:
        body["message"] = message
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    data = await agent_api_call("POST", "/agent/run", body)
    return json_result(data)

@mcp.tool(name="gen_refine_content_ideas", description="Step 2 (Content Ideas): Give feedback on previously generated content ideas to get revised versions. Must pass the conversation_id from the original generation.")
async def gen_refine_content_ideas(
    agent_id: Annotated[str, Field(description="The agent ID")],
    conversation_id: Annotated[str, Field(description="The conversation_id from the original generation")],
    feedback: Annotated[str, Field(description="Feedback, e.g. 'make idea 1 hook shorter' or 'redo ideas 2 and 4 as montage'")],
) -> str:
    data = await agent_api_call("POST", "/agent/run", {"message": feedback, "agent_id": agent_id, "conversation_id": conversation_id})
    return json_result(data)

@mcp.tool(name="gen_set_content_preference", description="Step 2 (Content Ideas): Set a persistent content generation rule for an agent. Applies to ALL future generations. Different from per-batch requirements which only apply once. Examples: 'always use statement hooks', 'target women 25-34', 'never mention competitors'.")
async def gen_set_content_preference(
    agent_id: Annotated[str, Field(description="The agent ID")],
    preference: Annotated[str, Field(description="Rule to save, e.g. 'always use statement hooks' or 'target women 25-34'")],
    conversation_id: Annotated[Optional[str], Field(default=None, description="Optional conversation context")] = None,
) -> str:
    body = {
        "message": f"Remember this content preference for all future ideas: {preference}",
        "agent_id": agent_id,
    }
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    data = await agent_api_call("POST", "/agent/run", body)
    return json_result(data)

@mcp.tool(name="gen_get_run_status", description="Step 2 (Content Ideas): Poll the status of an agent run. Returns 'running', 'completed', 'failed', or 'awaiting_approval'. When completed, messages array has the result. Poll every 5 seconds.")
async def gen_get_run_status(
    run_id: Annotated[str, Field(description="The run_id from gen_generate_content_ideas or gen_refine_content_ideas")],
) -> str:
    data = await agent_api_call("GET", f"/agent/runs/{run_id}")
    return json_result(data)

@mcp.tool(name="gen_decide_agent_run", description="Step 2 (Content Ideas): Approve or reject a pending agent action gate. Use when gen_get_run_status returns awaiting_approval. Pass approved=true to continue the run, approved=false to reject and fail it.")
async def gen_decide_agent_run(
    run_id: Annotated[str, Field(description="The run ID awaiting approval")],
    approved: Annotated[bool, Field(description="true to approve and continue; false to reject the pending action")],
) -> str:
    data = await agent_api_call("POST", f"/agent/runs/{run_id}/approve", {"approved": approved})
    return json_result(data)

@mcp.tool(name="gen_list_content_ideas", description="Step 2 (Content Ideas): List all generated content ideas for an agent. Filter by status: generated, approve_to_create, ready_for_review, change_idea, change_video, rejected, approved_to_post, posted.")
async def gen_list_content_ideas(
    agent_id: Annotated[str, Field(description="The agent ID")],
    status: Annotated[Optional[str], Field(default=None, description="Filter by status")] = None,
) -> str:
    path = f"/agent/ideas?agent_id={agent_id}"
    if status is not None:
        path += f"&status={status}"
    data = await agent_api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_update_idea_status", description="Step 2 (Content Ideas): Update the status of a content idea. Flow: generated → approve_to_create → ready_for_review → approved_to_post → posted. Edit/rejection statuses: change_idea, change_video, rejected. approved_to_post ideas are candidates to clone into a vidsheet in Step 3.")
async def gen_update_idea_status(
    idea_id: Annotated[str, Field(description="The idea ID")],
    status: Annotated[str, Field(description="New status value")],
) -> str:
    data = await agent_api_call("PUT", f"/agent/ideas/{idea_id}/status/{status}")
    return json_result(data)

@mcp.tool(name="gen_create_song_mix", description="Public API (agent.gen.pro): Create a DJ-style song-mix job that combines multiple songs/tracks into one long audio output. Use for 'mix these 5 songs', 'combine these tracks into one long song', or 'create 5 songs and combine them'. Returns status=pending_engine until the Mixxx-compatible renderer worker is installed, or pending_song_generation when songs must be generated first.")
async def gen_create_song_mix(
    tracks: Annotated[Optional[list], Field(default=None, description="List of track objects to mix, e.g. [{'song_generation_id': '...'}, ...]. Omit to auto-generate songs.")] = None,
    prompt: Annotated[Optional[str], Field(default=None, description="Custom DJ mix prompt. Omit to use the default optimal-order BPM/key/mood prompt.")] = None,
    transition_style: Annotated[Optional[str], Field(default=None, description="Transition style, e.g. professional, smooth, high-energy.")] = None,
    output_format: Annotated[Optional[str], Field(default=None, description="Final audio format. Defaults to mp3.")] = None,
    auto_order: Annotated[Optional[bool], Field(default=None, description="Whether GEN should choose optimal order by BPM/key/mood. Defaults true.")] = None,
    desired_duration_seconds: Annotated[Optional[float], Field(default=None, description="Desired final mix duration in seconds.")] = None,
    generate_missing_count: Annotated[Optional[float], Field(default=None, description="Number of songs to create before mixing, e.g. 5 for 'create 5 songs and combine them'.")] = None,
) -> str:
    body = {}
    if tracks is not None:
        body["tracks"] = tracks
    if prompt is not None:
        body["prompt"] = prompt
    if transition_style is not None:
        body["transition_style"] = transition_style
    if output_format is not None:
        body["output_format"] = output_format
    if auto_order is not None:
        body["auto_order"] = auto_order
    body["desired_duration_seconds"] = desired_duration_seconds
    if generate_missing_count is not None:
        body["generate_missing_count"] = generate_missing_count
    data = await agent_api_call("POST", "/audio/mixes", body)
    return json_result(data)

@mcp.tool(name="gen_expand_idea", description="Step 2 (Content Ideas): Expand a single content idea into a full project_manifest (the structured layer/scene plan a vidsheet is built from). Use this before cloning an idea into a vidsheet in Step 3 when the idea was generated without a manifest. Idempotent — returns the cached manifest if the idea is already expanded. Note the path has no /agent/ segment.")
async def gen_expand_idea(
    idea_id: Annotated[str, Field(description="The idea ID to expand")],
) -> str:
    data = await agent_api_call("POST", f"/ideas/{idea_id}/expand")
    return json_result(data)

@mcp.tool(name="gen_list_conversations", description="Step 2 (Content Ideas): List agent chat conversations with titles and metadata.")
async def gen_list_conversations(
    agent_id: Annotated[Optional[str], Field(default=None, description="Filter by agent ID")] = None,
) -> str:
    path = "/agent/conversations"
    if agent_id is not None:
        path += f"?agent_id={agent_id}"
    data = await agent_api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_get_conversation", description="Step 2 (Content Ideas): Get a conversation with all messages. Use to review chat history and previously generated ideas before refining.")
async def gen_get_conversation(
    conversation_id: Annotated[str, Field(description="The conversation ID")],
) -> str:
    data = await agent_api_call("GET", f"/agent/conversations/{conversation_id}")
    return json_result(data)

@mcp.tool(name="gen_get_session_preferences", description="Step 2 (Content Ideas): Read the per-conversation session preferences (temporary creative rules scoped to this one conversation, distinct from the agent's long-term preferences). Returns null if none are set.")
async def gen_get_session_preferences(
    conversation_id: Annotated[str, Field(description="The conversation ID")],
) -> str:
    data = await agent_api_call("GET", f"/agent/conversations/{conversation_id}/session-preferences")
    return json_result(data)

@mcp.tool(name="gen_update_session_preferences", description="Step 2 (Content Ideas): Set the per-conversation session preferences (creative rules applied only within this conversation; they do not change the agent's saved long-term preferences). Replaces the existing value.")
async def gen_update_session_preferences(
    conversation_id: Annotated[str, Field(description="The conversation ID")],
    preferences: Annotated[str, Field(description="The session preferences text to apply to this conversation")],
) -> str:
    data = await agent_api_call("PATCH", f"/agent/conversations/{conversation_id}/session-preferences", {"preferences": preferences})
    return json_result(data)

@mcp.tool(name="gen_run_research", description="Step 2 (Content Ideas): Research a topic across 10+ platforms (Reddit, X, YouTube, TikTok, Instagram, HN, Perplexity, Gemini). Returns structured findings with source counts, citations, and AI synthesis. Use for trend analysis, competitive research, or grounding content ideas in real data.")
async def gen_run_research(
    topic: Annotated[str, Field(description="Research topic (e.g. 'tariffs on beauty imports 2026', 'skincare routine trends')")],
    agent_id: Annotated[str, Field(description="The agent ID")],
    depth: Annotated[Optional[str], Field(default=None, description="Research depth — quick (~30s), default (~2min), deep (~5min)")] = None,
) -> str:
    body = {"topic": topic, "agent_id": agent_id}
    if depth is not None:
        body["depth"] = depth
    data = await agent_api_call("POST", "/research", body)
    return json_result(data)

@mcp.tool(name="gen_create_monitoring_job", description="Step 2 (Content Ideas): Start monitoring or scraping social media content to feed future idea generation. Supports 3 platforms: tiktok, instagram, youtube. Search types: username (@creator), hashtag (#topic), keyword (plain text). Not all platform/type combos are valid — TikTok and YouTube support all three; Instagram supports username+hashtag only. Set monitoring=true for ongoing scheduled scraping, false for one-time (default). Scraped data is queried through the agent chat, not returned directly. This is a paid operation.")
async def gen_create_monitoring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    platform: Annotated[str, Field(description="Target platform")],
    search_type: Annotated[str, Field(description="Search type — must be supported by the chosen platform")],
    value: Annotated[str, Field(description="Search value: @username, #hashtag, or keyword text")],
    days: Annotated[Optional[float], Field(default=None, description="Filter to content from last N days: 0 (no filter), 1, 7, 30, 90, or 180")] = None,
    country: Annotated[Optional[str], Field(default=None, description="Two-letter country code (e.g. us, gb) to filter by region")] = None,
    max_results: Annotated[Optional[float], Field(default=None, description="Max results per scrape (1-50)")] = None,
    monitoring: Annotated[Optional[bool], Field(default=None, description="true for ongoing monitoring, false for one-time scrape (default)")] = None,
    comment_monitoring: Annotated[Optional[bool], Field(default=None, description="true to also scrape comments (adds per-comment cost)")] = None,
) -> str:
    import json as _json
    job_data: dict = {"platform": platform, "type": search_type, "value": value}
    if days is not None:
        job_data["days"] = days
    if country is not None:
        job_data["country"] = country
    if max_results is not None:
        job_data["max_results"] = max_results
    if monitoring is not None:
        job_data["monitoring"] = monitoring
    if comment_monitoring is not None:
        job_data["comment_monitoring"] = comment_monitoring
    form = {
        "agent_id": agent_id,
        "user_job[user_job_type]": "train_social",
        "user_job[data]": _json.dumps(job_data),
    }
    data = await form_call("POST", f"/user_jobs?agent_id={agent_id}", form)
    return json_result(data)

@mcp.tool(name="gen_update_monitoring_job", description="Step 2 (Content Ideas): Update an existing content monitoring job. Only jobs with pending or processing status can be updated.")
async def gen_update_monitoring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The monitoring job ID to update")],
    platform: Annotated[str, Field(description="Target platform")],
    search_type: Annotated[str, Field(description="Search type")],
    value: Annotated[str, Field(description="Search value: @username, #hashtag, or keyword text")],
    days: Annotated[Optional[float], Field(default=None, description="Filter to content from last N days")] = None,
    country: Annotated[Optional[str], Field(default=None, description="Two-letter country code")] = None,
    max_results: Annotated[Optional[float], Field(default=None, description="Max results per scrape (1-50)")] = None,
    monitoring: Annotated[Optional[bool], Field(default=None, description="true for ongoing, false for one-time")] = None,
    comment_monitoring: Annotated[Optional[bool], Field(default=None, description="true to also scrape comments")] = None,
) -> str:
    form: dict = {
        "agent_id": agent_id,
        "platform": platform,
        "type": search_type,
        "value": value,
    }
    if days is not None:
        form["days"] = str(days)
    if country is not None:
        form["country"] = country
    if max_results is not None:
        form["max_results"] = str(max_results)
    if monitoring is not None:
        form["monitoring"] = str(monitoring).lower()
    if comment_monitoring is not None:
        form["comment_monitoring"] = str(comment_monitoring).lower()
    data = await form_call("PUT", f"/user_jobs/{job_id}?agent_id={agent_id}", form)
    return json_result(data)

@mcp.tool(name="gen_list_templates", description="Step 3 (Idea to Vidsheet): List available vidsheet templates. Templates are pre-configured engines — cloning one is the fastest way to start. ALWAYS check templates before creating an engine from scratch.")
async def gen_list_templates(
    page: Annotated[Optional[str], Field(default=None, description="Page number (default 1, 20 per page)")] = None,
) -> str:
    path = "/templates/projects"
    if page is not None:
        path += f"?page={page}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_get_template", description="Step 3 (Idea to Vidsheet): Get details of a specific template by slug, UUID, or ID. Inspect columns and structure before cloning.")
async def gen_get_template(
    slug: Annotated[str, Field(description="Template slug, UUID, or numeric ID")],
) -> str:
    data = await api_call("GET", f"/templates/projects/{slug}")
    return json_result(data)

@mcp.tool(name="gen_clone_template", description="Step 3 (Idea to Vidsheet): Clone a template into an agent's workspace. FASTEST path to a production-ready vidsheet with pre-configured columns. Returns the new engine with its engine_id.")
async def gen_clone_template(
    slug: Annotated[str, Field(description="Template slug to clone")],
    agent_id: Annotated[str, Field(description="Agent ID to clone the template into")],
) -> str:
    data = await api_call("POST", f"/templates/spreadsheets/{slug}/clone", {"agent_id": agent_id})
    return json_result(data)

@mcp.tool(name="gen_create_engine", description="Step 3 (Idea to Vidsheet): Create a new empty Auto Content Engine (vidsheet) for an agent. Prefer gen_clone_template (fastest) unless neither fits — templates come pre-configured with the right columns for common workflows. After cloning, PATCH cells to inject the idea's fields.")
async def gen_create_engine(
    agent_id: Annotated[str, Field(description="The agent ID to create the engine for")],
    title: Annotated[str, Field(description="Title for the new engine")],
) -> str:
    data = await api_call("POST", "/vidsheet", {"agent_id": agent_id, "title": title})
    return json_result(data)

@mcp.tool(name="gen_get_engine", description="Step 3 (Idea to Vidsheet): Get full details of a vidsheet — returns all columns, rows, and cells in one call. Cheap and fast. Use liberally at the start of Step 4.")
async def gen_get_engine(
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    engine_id: Annotated[str, Field(description="The engine ID to retrieve")],
) -> str:
    data = await api_call("GET", f"/vidsheet/{engine_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_clone_engine", description="Step 3 (Idea to Vidsheet): Clone an existing engine, optionally to a different agent. Useful for duplicating proven pipelines across brands.")
async def gen_clone_engine(
    agent_id: Annotated[str, Field(description="The agent ID that owns the source engine")],
    engine_id: Annotated[str, Field(description="The engine ID to clone")],
    target_agent_id: Annotated[Optional[str], Field(default=None, description="Target agent ID (defaults to same agent)")] = None,
) -> str:
    body = {"agent_id": agent_id}
    if target_agent_id is not None:
        body["target_agent_id"] = target_agent_id
    data = await api_call("POST", f"/vidsheet/{engine_id}/clone", body)
    return json_result(data)

@mcp.tool(name="gen_list_columns", description="Step 4 (Edit & Generate): List all columns in a vidsheet, including role (ingredient/video/final_video/stats) and type.")
async def gen_list_columns(
    engine_id: Annotated[str, Field(description="The engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("GET", f"/vidsheet/{engine_id}/columns?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_create_column", description="Step 4 (Edit & Generate): Create a new ingredient column in a vidsheet. The column type enum is derived from the Rails Vidsheet schema. To place it, create it first then use gen_reorder_columns; models never set raw editor positions.")
async def gen_create_column(
    engine_id: Annotated[str, Field(description="The engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    title: Annotated[str, Field(description="Column title")],
    type: VidsheetColumnType,
) -> str:
    require_enum_value("spreadsheet_column", "type", type)
    body = {"agent_id": agent_id, "title": title, "type": type}
    data = await api_call("POST", f"/vidsheet/{engine_id}/columns", body)
    return json_result(data)

@mcp.tool(name="gen_update_column", description="Step 4 (Edit & Generate): Update a column's title or type. Use gen_reorder_columns to change its order; raw editor positions are intentionally not model-facing.")
async def gen_update_column(
    engine_id: Annotated[str, Field(description="The engine ID")],
    column_id: Annotated[str, Field(description="The column ID to update")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    title: Annotated[Optional[str], Field(default=None, description="New column title")] = None,
    type: OptionalVidsheetColumnType = None,
) -> str:
    col: dict = {}
    if title is not None:
        col["title"] = title
    if type is not None:
        require_enum_value("spreadsheet_column", "type", type)
        col["type"] = type
    body = {"agent_id": agent_id, "spreadsheet_column": col}
    data = await api_call("PATCH", f"/vidsheet/{engine_id}/columns/{column_id}", body)
    return json_result(data)


def _id_to_position(ordered_ids: list[str], *, entity: str) -> dict[str, int]:
    if not ordered_ids:
        raise ValueError(f"{entity}_ids must contain the complete desired order")
    if any(not item.strip() for item in ordered_ids):
        raise ValueError(f"{entity}_ids cannot contain blank IDs")
    if len(set(ordered_ids)) != len(ordered_ids):
        raise ValueError(f"{entity}_ids cannot contain duplicate IDs")
    return {item: position for position, item in enumerate(ordered_ids)}


async def _next_layer_position(engine_id: str, cell_id: str, agent_id: str) -> int:
    """Derive Rails' required wire position; models never choose it.

    The wire schema correctly marks ``video_layer.position`` as required.  A
    model-facing create tool owns the higher-level operation "append a layer",
    so it reads the live cell and turns that into the next editor-track index.
    """
    cell = await api_call(
        "GET", f"/vidsheet/{engine_id}/cells/{cell_id}?agent_id={agent_id}"
    )
    positions = [
        layer.get("position")
        for layer in (cell.get("video_layers") or [])
        if isinstance(layer, dict) and isinstance(layer.get("position"), (int, float))
    ]
    return int(max(positions, default=-1)) + 1


@mcp.tool(name="gen_reorder_columns", description="Step 4 (Edit & Generate): Set the complete left-to-right order of every column in a Vidsheet. Pass every column ID exactly once, including system columns. This is the model-facing replacement for Rails' raw position field.")
async def gen_reorder_columns(
    engine_id: Annotated[str, Field(description="The Vidsheet ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the Vidsheet")],
    column_ids: Annotated[list[str], Field(description="Every column ID once, in desired left-to-right order")],
) -> str:
    data = await api_call(
        "PATCH",
        f"/vidsheet/{engine_id}/columns/update_positions",
        {"agent_id": agent_id, "id_to_position": _id_to_position(column_ids, entity="column")},
    )
    return json_result(data)

@mcp.tool(name="gen_delete_column", description="Step 4 (Edit & Generate): Delete a column from a vidsheet. Only ingredient-role columns can be deleted.")
async def gen_delete_column(
    engine_id: Annotated[str, Field(description="The engine ID")],
    column_id: Annotated[str, Field(description="The column ID to delete")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("DELETE", f"/vidsheet/{engine_id}/columns/{column_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_list_rows", description="Step 4 (Edit & Generate): List all rows in a vidsheet. A row is one piece of content; cells across its columns are its ingredients and generated outputs.")
async def gen_list_rows(
    engine_id: Annotated[str, Field(description="The engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("GET", f"/vidsheet/{engine_id}/rows?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_create_row", description="Step 4 (Edit & Generate): Create a new row in a vidsheet. Each row is one piece of content.")
async def gen_create_row(
    engine_id: Annotated[str, Field(description="The engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("POST", f"/vidsheet/{engine_id}/rows", {"agent_id": agent_id})
    return json_result(data)

@mcp.tool(name="gen_duplicate_row", description="Step 4 (Edit & Generate): Duplicate an existing row, including its ingredient cell values. Useful for batch-generating variants from a known-good row.")
async def gen_duplicate_row(
    engine_id: Annotated[str, Field(description="The engine ID")],
    row_id: Annotated[str, Field(description="The row ID to duplicate")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("POST", f"/vidsheet/{engine_id}/rows/{row_id}/duplicate", {"agent_id": agent_id})
    return json_result(data)

@mcp.tool(name="gen_get_cell", description="Step 4 (Edit & Generate): Get the value and metadata of a specific cell, including any layers, generations, and attached content resources.")
async def gen_get_cell(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID to retrieve")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("GET", f"/vidsheet/{engine_id}/cells/{cell_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_update_cell", description="Step 4 (Edit & Generate): Update the value of a specific cell. Use on ingredient cells to set scripts, prompts, or reference values before triggering generation.")
async def gen_update_cell(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID to update")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    value: Annotated[str, Field(description="The new cell value")],
) -> str:
    data = await api_call("PATCH", f"/vidsheet/{engine_id}/cells/{cell_id}", {"agent_id": agent_id, "spreadsheet_cell": {"value": value}})
    return json_result(data)

@mcp.tool(name="gen_create_layer", description="Step 4 (Edit & Generate): Create a new layer inside a video cell. Layer type is derived from the Rails Vidsheet schema. Use gen_reorder_layers for editor-track order, never a raw position.")
async def gen_create_layer(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID to add the layer to")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    name: Annotated[str, Field(description="Name of the layer")],
    type: VideoLayerType,
) -> str:
    require_enum_value("video_layer", "type", type)
    # ``position`` is required on the Rails wire but banned from the MCP
    # schema. Derive append order from the current editor state.
    layer: dict = {
        "name": name,
        "type": type,
        "position": await _next_layer_position(engine_id, cell_id, agent_id),
    }
    data = await api_call("POST", f"/vidsheet/{engine_id}/cells/{cell_id}/layers", {"agent_id": agent_id, "video_layer": layer})
    return json_result(data)

@mcp.tool(name="gen_get_layer", description="Step 4 (Edit & Generate): Get details of a specific layer in a cell, including its type, position, additional_attributes, and generation history.")
async def gen_get_layer(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID")],
    layer_id: Annotated[str, Field(description="The layer ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("GET", f"/vidsheet/{engine_id}/cells/{cell_id}/layers/{layer_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_update_layer", description="Step 4 (Edit & Generate): Update a layer's name, type, or additional attributes. Use gen_reorder_layers for editor-track order, never a raw position.")
async def gen_update_layer(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID")],
    layer_id: Annotated[str, Field(description="The layer ID to update")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    name: Annotated[Optional[str], Field(default=None, description="New layer name")] = None,
    type: OptionalVideoLayerType = None,
    additional_attributes: Annotated[Optional[dict], Field(default=None, description="Additional attributes to set")] = None,
) -> str:
    layer_patch: dict = {}
    if name is not None:
        layer_patch["name"] = name
    if type is not None:
        require_enum_value("video_layer", "type", type)
        layer_patch["type"] = type
    if additional_attributes is not None:
        layer_patch["additional_attributes"] = additional_attributes
    body = {"agent_id": agent_id, "video_layer": layer_patch}
    data = await api_call("PATCH", f"/vidsheet/{engine_id}/cells/{cell_id}/layers/{layer_id}", body)
    return json_result(data)


@mcp.tool(name="gen_reorder_layers", description="Step 4 (Edit & Generate): Set the complete editor-track order of every layer in one Vidsheet cell. Pass every layer ID exactly once, from top to bottom. This is the model-facing replacement for Rails' raw position field.")
async def gen_reorder_layers(
    engine_id: Annotated[str, Field(description="The Vidsheet ID")],
    cell_id: Annotated[str, Field(description="The video cell ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the Vidsheet")],
    layer_ids: Annotated[list[str], Field(description="Every layer ID once, in desired top-to-bottom editor order")],
) -> str:
    data = await api_call(
        "PUT",
        f"/vidsheet/{engine_id}/cells/{cell_id}/layers/update_positions",
        {"agent_id": agent_id, "id_to_position": _id_to_position(layer_ids, entity="layer")},
    )
    return json_result(data)

@mcp.tool(name="gen_delete_layer", description="Step 4 (Edit & Generate): Delete a layer from a cell.")
async def gen_delete_layer(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID")],
    layer_id: Annotated[str, Field(description="The layer ID to delete")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("DELETE", f"/vidsheet/{engine_id}/cells/{cell_id}/layers/{layer_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_list_variables", description="Step 4 (Edit & Generate): Get global variables for a vidsheet. Variables are key-value pairs used for template substitution in prompts and content (e.g. {{brand_name}}).")
async def gen_list_variables(
    engine_id: Annotated[str, Field(description="The engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("GET", f"/vidsheet/{engine_id}/global_variables?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_list_content_resources", description="Step 4 (Edit & Generate): List content resources (files) belonging to an agent, with optional filters. Content resources are the media files (images, videos, audio) referenced by generations like video_from_image or lipsync.")
async def gen_list_content_resources(
    agent_id: Annotated[str, Field(description="The agent whose resources to list")],
    type: Annotated[Optional[str], Field(default=None, description="Filter by file type: image, video, audio, zip, or safe_tensors")] = None,
    project_id: Annotated[Optional[str], Field(default=None, description="Filter to resources attached to a specific project")] = None,
    page: Annotated[Optional[str], Field(default=None, description="Page number for pagination (default 0, 20 items per page)")] = None,
) -> str:
    path = f"/content_resources?agent_id={agent_id}"
    if type is not None:
        path += f"&type={type}"
    if project_id is not None:
        path += f"&project_id={project_id}"
    if page is not None:
        path += f"&page={page}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_create_content_resource", description="Step 4 (Edit & Generate): Create a content resource from a signed_id. Use gen_create_direct_upload first to upload the file, then pass the signed_id here.")
async def gen_create_content_resource(
    agent_id: Annotated[str, Field(description="The agent to create the resource under")],
    signed_id: Annotated[str, Field(description="The signed_id returned from gen_create_direct_upload")],
    asset_folder_id: Annotated[Optional[str], Field(default=None, description="Place the resource inside this asset folder")] = None,
) -> str:
    body: dict = {"content_resource": {"file": signed_id}}
    if asset_folder_id:
        body["asset_folder"] = {"id": asset_folder_id}
    data = await api_call("POST", f"/content_resources?agent_id={agent_id}", body)
    return json_result(data)

@mcp.tool(name="gen_get_content_resource", description="Step 4 (Edit & Generate): Get full details of a content resource, including its public URL and generator info if AI-generated.")
async def gen_get_content_resource(
    agent_id: Annotated[str, Field(description="The agent that owns the resource")],
    resource_id: Annotated[str, Field(description="The content resource ID")],
) -> str:
    data = await api_call("GET", f"/content_resources/{resource_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_update_content_resource", description="Step 4 (Edit & Generate): Rename a content resource file.")
async def gen_update_content_resource(
    agent_id: Annotated[str, Field(description="The agent that owns the resource")],
    resource_id: Annotated[str, Field(description="The content resource ID")],
    filename: Annotated[str, Field(description="The new filename for the resource")],
) -> str:
    data = await api_call("PATCH", f"/content_resources/{resource_id}?agent_id={agent_id}", {"content_resource": {"filename": filename}})
    return json_result(data)

@mcp.tool(name="gen_delete_content_resource", description="Step 4 (Edit & Generate): Permanently delete a content resource and its associated file.")
async def gen_delete_content_resource(
    agent_id: Annotated[str, Field(description="The agent that owns the resource")],
    resource_id: Annotated[str, Field(description="The content resource ID to delete")],
) -> str:
    data = await api_call("DELETE", f"/content_resources/{resource_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_list_asset_libraries", description="Step 4 (Edit & Generate): List the agent's asset library (files and folders) with filtering and search.")
async def gen_list_asset_libraries(
    agent_id: Annotated[str, Field(description="The agent whose asset library to list")],
    folder_id: Annotated[Optional[str], Field(default=None, description="Show contents of a specific folder (omit for root-level)")] = None,
    asset_type: Annotated[Optional[str], Field(default=None, description="Comma-separated filter: image, video, audio, folder")] = None,
    search: Annotated[Optional[str], Field(default=None, description="Search assets by name")] = None,
    order: Annotated[Optional[str], Field(default=None, description="Sort order: 'recent' for newest first")] = None,
    page: Annotated[Optional[str], Field(default=None, description="Page number (default 1)")] = None,
    page_size: Annotated[Optional[str], Field(default=None, description="Items per page (default 20)")] = None,
) -> str:
    path = f"/asset_libraries?agent_id={agent_id}"
    if folder_id is not None:
        path += f"&folder_id={folder_id}"
    if asset_type is not None:
        path += f"&asset_type={asset_type}"
    if search is not None:
        path += f"&search={search}"
    if order is not None:
        path += f"&order={order}"
    if page is not None:
        path += f"&page={page}"
    if page_size is not None:
        path += f"&page_size={page_size}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_create_direct_upload", description="Step 4 (Edit & Generate): Get a pre-signed S3 URL for direct file upload. Two-step: (1) call this, (2) PUT the file to the returned URL, (3) pass the returned signed_id to gen_create_content_resource.")
async def gen_create_direct_upload(
    filename: Annotated[str, Field(description="Original filename including extension")],
    byte_size: Annotated[float, Field(description="File size in bytes (max 1 GB)")],
    checksum: Annotated[str, Field(description="Base64-encoded MD5 checksum of the file")],
    content_type: Annotated[str, Field(description="MIME type (e.g. image/png, video/mp4)")],
) -> str:
    data = await api_call("POST", "/direct_upload", {"blob": {"filename": filename, "byte_size": byte_size, "checksum": checksum, "content_type": content_type}})
    return json_result(data)

@mcp.tool(name="gen_generate_content", description="Step 4 (Edit & Generate): THE WORKHORSE. Trigger AI content generation for a cell. Returns a generation_id — poll with gen_get_generation until status is \"completed\".  Canonical generation types (legacy names also accepted): - TEXT: generation_type=\"text\", data={model:\"gemini_2_0_flash\"|\"gpt_4o\"|..., prompt:\"...\"} - IMAGE: generation_type=\"image_from_text\", data={prompt:\"...\", model:\"gemini_image\"|\"gemini_pro_image\"|\"midjourney\"|\"grok\", aspect_ratio:\"1:1\"|\"9:16\"|\"16:9\"} - VIDEO (text): generation_type=\"video_from_text\", data={prompt:\"...\", model:\"veo_3\"|\"veo_3_1\"|\"sora_2\"|\"kling_1_6\"|\"kling_2_1\"|\"kling_2_6\"|\"seedance_pro\"|\"seedance-2.0\"|\"grok\"|..., duration:5|10} - VIDEO (image): generation_type=\"video_from_image\", data={prompt:\"...\", model:\"kling_2_1\"|\"kling_2_6\"|\"veo_3\"|\"veo_3_1\"|\"seedance-2.0\"|\"grok\"|..., image_resource_id:123} - VIDEO (ingredients): generation_type=\"video_from_ingredients\", data={prompt:\"...\", model:\"pika\"|\"kling_1_6\"|\"grok\"|..., asset_resource_ids:[...]} - SPEECH: generation_type=\"speech_from_text\", data={voice_id:\"...\", script:\"...\", voice_method:\"my_voices\"|\"design_voice\"|\"clone_voice\", voice_model_provider?:\"supertonic_3\"|\"qwen3_voice_design\"} - LIPSYNC: generation_type=\"lipsync\", data={model:\"sync_so\"|\"gen\", video_resource_id:123, audio_resource_id:456} - CAPTIONS: generation_type=\"captions\", data={model:\"gemini\", source_resource_id:123} - MEDIA: generation_type=\"media\", data={content_resource_id:123}  Credits are pre-charged and refunded on failure/stop.")
async def gen_generate_content(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID to generate content for")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    generation_type: Annotated[str, Field(description="text | image_from_text | video_from_text | video_from_image | video_from_ingredients | speech_from_text | lipsync | captions | media")],
    data: Annotated[Optional[dict], Field(default=None, description="Generation-specific parameters (prompt, model, aspect_ratio, duration, voice_id, etc.)")] = None,
) -> str:
    rails_type = resolve_generation_type(generation_type, data if isinstance(data, dict) else None)
    body: dict = {"agent_id": agent_id, "generation_type": rails_type}
    if data:
        body["data"] = data
    result = await api_call("POST", f"/vidsheet/{engine_id}/cells/{cell_id}/generate", body)
    return json_result(result)

@mcp.tool(name="gen_generate_layer", description="Step 4 (Edit & Generate): Trigger generation for a specific layer within a cell. Use when the layer's generation type and data are already configured on the layer.")
async def gen_generate_layer(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID")],
    layer_id: Annotated[str, Field(description="The layer ID to generate")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("POST", f"/vidsheet/{engine_id}/cells/{cell_id}/layers/{layer_id}/generate", {"agent_id": agent_id})
    return json_result(data)

@mcp.tool(name="gen_get_generation", description="Step 4 (Edit & Generate): Poll a generation job's status. Flow: pending → processing → completed | failed | stopped. On completion: text in `result`, media URLs in `output_resources`. Poll every 5–10s for video, every 2–5s for text/image.")
async def gen_get_generation(
    generation_id: Annotated[str, Field(description="The generation ID to check")],
) -> str:
    data = await api_call("GET", f"/generations/{generation_id}")
    return json_result(data)

@mcp.tool(name="gen_stop_generation", description="Step 4 (Edit & Generate): Stop a running generation job. Credits are refunded.")
async def gen_stop_generation(
    generation_id: Annotated[str, Field(description="The generation ID to stop")],
) -> str:
    data = await api_call("POST", f"/generations/{generation_id}/stop")
    return json_result(data)

@mcp.tool(name="gen_continue_generation", description="Step 4 (Edit & Generate): Continue a previously stopped generation. Credits are re-charged.")
async def gen_continue_generation(
    generation_id: Annotated[str, Field(description="The generation ID to continue")],
) -> str:
    data = await api_call("POST", f"/generations/{generation_id}/continue")
    return json_result(data)

@mcp.tool(name="gen_render_video", description="Step 5 (Export & Publish): Render the final composed video for a cell in a final_video column. Combines all layers (video, audio, text overlays, captions) into one deliverable. Returns a generation_id — poll with gen_get_generation; the final MP4 URL arrives in output_resources when status is completed.")
async def gen_render_video(
    engine_id: Annotated[str, Field(description="The engine ID")],
    cell_id: Annotated[str, Field(description="The cell ID (must be a final_video column cell)")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("POST", f"/vidsheet/{engine_id}/cells/{cell_id}/render", {"agent_id": agent_id})
    return json_result(data)

@mcp.tool(name="gen_publish_content", description="Step 5 (Export & Publish): Publish or schedule content to a social media platform. Currently supports TikTok. The agent must have a connected TikTok social account. For immediate posting use schedule_type='now'. For scheduled posting use schedule_type='scheduled' with a future scheduled_time. This is a paid operation.")
async def gen_publish_content(
    agent_id: Annotated[str, Field(description="The agent ID")],
    platform: Annotated[str, Field(description="Target platform (currently only tiktok)")],
    media_url: Annotated[str, Field(description="Public URL to the media file (must be accessible at post time)")],
    description: Annotated[str, Field(description="Post caption/description. Max ~2200 chars for TikTok. Include hashtags inline.")],
    schedule_type: Annotated[str, Field(description="'now' for immediate posting, 'scheduled' for future posting")],
    title: Annotated[Optional[str], Field(default=None, description="Post title")] = None,
    media_type: Annotated[Optional[str], Field(default=None, description="Media type (default VIDEO)")] = None,
    scheduled_time: Annotated[Optional[str], Field(default=None, description="ISO 8601 UTC datetime. Required when schedule_type is 'scheduled'.")] = None,
    thumbnail_url: Annotated[Optional[str], Field(default=None, description="Custom thumbnail URL")] = None,
    timezone_offset: Annotated[Optional[float], Field(default=None, description="Timezone offset in minutes from UTC (default 0)")] = None,
) -> str:
    import json as _json
    publish_data: dict = {
        "platform": platform,
        "media_url": media_url,
        "description": description,
        "schedule_type": schedule_type,
    }
    if title:
        publish_data["title"] = title
    if media_type:
        publish_data["media_type"] = media_type
    if scheduled_time:
        publish_data["scheduled_time"] = scheduled_time
    if thumbnail_url:
        publish_data["thumbnail_url"] = thumbnail_url
    if timezone_offset is not None:
        publish_data["timezone_offset"] = timezone_offset
    body = {"user_job_type": "publish_content", "data": _json.dumps(publish_data)}
    data = await api_call("POST", f"/user_jobs?agent_id={agent_id}", body)
    return json_result(data)

@mcp.tool(name="gen_list_watchlists", description="Step 3 (Monitoring): List all active watchlists for an agent. Each watchlist contains a name and a list of sources (account/hashtag/keyword) being monitored across platforms. Returns soft-deleted watchlists filtered out.")
async def gen_list_watchlists(
    agent_id: Annotated[str, Field(description="The agent ID that owns the watchlists")],
) -> str:
    data = await agent_core_api_call("GET", f"/agents/{agent_id}/watchlists")
    return json_result(data)

@mcp.tool(name="gen_create_watchlist", description="Step 3 (Monitoring): Create a new watchlist for an agent, optionally with initial sources. Idempotent on watchlist name (case-insensitive): if a watchlist with the same name already exists, the provided sources are merged into it instead of creating a duplicate. Each source is (platform, target_type ∈ account|hashtag|keyword, target_value). Returns the full watchlist including all active sources.")
async def gen_create_watchlist(
    agent_id: Annotated[str, Field(description="The agent ID")],
    name: Annotated[str, Field(description="Watchlist display name (1-200 chars). Idempotent: same name reuses the existing watchlist.")],
    sources: Annotated[Optional[dict], Field(default=None, description="Platform — e.g. tiktok, instagram, youtube")] = None,
    project_id: Annotated[Optional[float], Field(default=None, description="Optional Rails project id to link this watchlist to a project shell")] = None,
    conversation_id: Annotated[Optional[str], Field(default=None, description="Optional chat conversation that triggered creation (for attribution)")] = None,
    created_by_run_id: Annotated[Optional[str], Field(default=None, description="Optional agent_run id that triggered creation (for attribution)")] = None,
) -> str:
    body = {"name": name}
    if sources is not None:
        body["sources"] = sources
    if project_id is not None:
        body["project_id"] = project_id
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    if created_by_run_id is not None:
        body["created_by_run_id"] = created_by_run_id
    data = await agent_core_api_call("POST", f"/agents/{agent_id}/watchlists", body)
    return json_result(data)

@mcp.tool(name="gen_get_watchlist", description="Step 3 (Monitoring): Fetch a single watchlist by id, including its full active sources list. Returns 404 if the watchlist is soft-deleted.")
async def gen_get_watchlist(
    agent_id: Annotated[str, Field(description="The agent ID")],
    watchlist_id: Annotated[str, Field(description="The watchlist id (UUID)")],
) -> str:
    data = await agent_core_api_call("GET", f"/agents/{agent_id}/watchlists/{watchlist_id}")
    return json_result(data)

@mcp.tool(name="gen_update_watchlist", description="Step 3 (Monitoring): Update a watchlist's mutable fields (name, project_id, rails_project_error). Use gen_pause_watchlist or gen_resume_watchlist for status changes; use gen_delete_watchlist to remove. Only the fields you pass are updated.")
async def gen_update_watchlist(
    agent_id: Annotated[str, Field(description="The agent ID")],
    watchlist_id: Annotated[str, Field(description="The watchlist id")],
    name: Annotated[Optional[str], Field(default=None, description="New display name")] = None,
    project_id: Annotated[Optional[float], Field(default=None, description="New Rails project id to link")] = None,
    rails_project_error: Annotated[Optional[str], Field(default=None, description="Last Rails project sync error, if any")] = None,
) -> str:
    body = {}
    if name is not None:
        body["name"] = name
    if project_id is not None:
        body["project_id"] = project_id
    if rails_project_error is not None:
        body["rails_project_error"] = rails_project_error
    data = await agent_core_api_call("PATCH", f"/agents/{agent_id}/watchlists/{watchlist_id}", body)
    return json_result(data)

@mcp.tool(name="gen_pause_watchlist", description="Step 3 (Monitoring): Pause a watchlist without deleting it. Sets intent_active=false so the scheduler stops queueing scrapes, but the watchlist + its sources are preserved. Use gen_resume_watchlist to re-enable. Use gen_delete_watchlist to permanently remove.")
async def gen_pause_watchlist(
    agent_id: Annotated[str, Field(description="The agent ID")],
    watchlist_id: Annotated[str, Field(description="The watchlist id")],
) -> str:
    data = await agent_core_api_call("PATCH", f"/agents/{agent_id}/watchlists/{watchlist_id}", {"intent_active": False})
    return json_result(data)

@mcp.tool(name="gen_resume_watchlist", description="Step 3 (Monitoring): Resume a paused watchlist. Sets intent_active=true so the scheduler resumes queueing scrapes for the watchlist's sources.")
async def gen_resume_watchlist(
    agent_id: Annotated[str, Field(description="The agent ID")],
    watchlist_id: Annotated[str, Field(description="The watchlist id")],
) -> str:
    data = await agent_core_api_call("PATCH", f"/agents/{agent_id}/watchlists/{watchlist_id}", {"intent_active": True})
    return json_result(data)

@mcp.tool(name="gen_delete_watchlist", description="Step 3 (Monitoring): Soft-delete a watchlist. Marks the watchlist and all its sources as inactive and deleted. The data is retained but no longer returned by gen_list_watchlists or gen_get_watchlist. Use gen_pause_watchlist if you only want to temporarily stop monitoring.")
async def gen_delete_watchlist(
    agent_id: Annotated[str, Field(description="The agent ID")],
    watchlist_id: Annotated[str, Field(description="The watchlist id")],
) -> str:
    data = await agent_core_api_call("DELETE", f"/agents/{agent_id}/watchlists/{watchlist_id}")
    return json_result(data)

@mcp.tool(name="gen_add_watchlist_source", description="Step 3 (Monitoring): Add a monitoring source to an existing watchlist, or restore one that was previously removed. Idempotent on (platform, target_type, target_value) — adding the same source twice returns the existing row. target_type must be one of: account (a username/handle), hashtag (a tag name), or keyword (free text search).")
async def gen_add_watchlist_source(
    agent_id: Annotated[str, Field(description="The agent ID")],
    watchlist_id: Annotated[str, Field(description="The watchlist id")],
    platform: Annotated[str, Field(description="Platform — e.g. tiktok, instagram, youtube")],
    target_type: Annotated[str, Field(description="Source kind: account=@handle, hashtag=tag (no #), keyword=free text")],
    target_value: Annotated[str, Field(description="@handle, hashtag name, or keyword text")],
    original_display_value: Annotated[Optional[str], Field(default=None, description="Optional original form (e.g. '#glassskin')")] = None,
) -> str:
    body = {"platform": platform, "target_type": target_type, "target_value": target_value}
    body["original_display_value"] = original_display_value
    data = await agent_core_api_call("POST", f"/agents/{agent_id}/watchlists/{watchlist_id}/sources", body)
    return json_result(data)

@mcp.tool(name="gen_remove_watchlist_source", description="Step 3 (Monitoring): Remove a single source from a watchlist. Pass EITHER source_id (preferred when known) OR all three of platform/target_type/target_value to remove by key. Soft-delete: the source row is marked inactive but retained.")
async def gen_remove_watchlist_source(
    agent_id: Annotated[str, Field(description="The agent ID")],
    watchlist_id: Annotated[str, Field(description="The watchlist id")],
    source_id: Annotated[Optional[str], Field(default=None, description="The source id (preferred). If omitted, all three of platform/target_type/target_value are required.")] = None,
    platform: Annotated[Optional[str], Field(default=None, description="Platform (only needed when source_id is omitted)")] = None,
    target_type: Annotated[Optional[str], Field(default=None, description="Source kind (only needed when source_id is omitted)")] = None,
    target_value: Annotated[Optional[str], Field(default=None, description="Source value (only needed when source_id is omitted)")] = None,
) -> str:
    if source_id:
        data = await agent_core_api_call(
            "DELETE", f"/agents/{agent_id}/watchlists/{watchlist_id}/sources/{source_id}"
        )
        return json_result(data)
    if not platform or not target_type or not target_value:
        raise ValueError(
            "gen_remove_watchlist_source requires either source_id, or all three of "
            "platform/target_type/target_value"
        )
    from urllib.parse import urlencode
    query = urlencode({"platform": platform, "target_type": target_type, "target_value": target_value})
    data = await agent_core_api_call(
        "DELETE", f"/agents/{agent_id}/watchlists/{watchlist_id}/sources?{query}"
    )
    return json_result(data)

@mcp.tool(name="gen_query_watchlist", description="Step 3 (Monitoring): Ask a question about a watchlist with typed filters (timeframe, count, sort, min engagement rate). Wraps the agent chat path that fans out one DW call per watchlist target with byte-identical filters. Use this for programmatic 'top N from @list:foo by engagement rate in the last 90 days' style asks instead of building a natural-language prompt yourself. Returns a run_id you poll with gen_get_run_status; the final answer contains a video grid plus a natural-language summary.")
async def gen_query_watchlist(
    agent_id: Annotated[str, Field(description="The agent ID")],
    watchlist_id: Annotated[str, Field(description="The watchlist id to query")],
    question: Annotated[str, Field(description="What to ask about the watchlist — e.g. 'top hooks', 'top videos', 'what are people saying', 'trending music'. Drives the analysis kind (top_hooks / trend_videos / comment_themes / top_sounds / top_creators / engagement_summary).")],
    days: Annotated[Optional[float], Field(default=None, description="Time window in days (1-365). When omitted, the chat layer's default policy applies.")] = None,
    limit: Annotated[Optional[float], Field(default=None, description="How many results to return (1-1000). When omitted, defaults to 100.")] = None,
    sort_by: Annotated[Optional[str], Field(default=None, description="Sort key. Without it, the backend default ranking applies.")] = None,
    min_engagement_rate: Annotated[Optional[float], Field(default=None, description="Minimum engagement rate as a 0.0-1.0 fraction (0.05 == 5%).")] = None,
    return_all: Annotated[Optional[bool], Field(default=None, description="Walk every matching row up to the DW hard cap (1000). Pairs with async pagination downstream. Defaults to false.")] = None,
) -> str:
    parts: list[str] = []
    if limit is not None:
        parts.append(f"top {limit}")
    parts.append(question)
    parts.append(f"from @list:{watchlist_id}")
    if sort_by is not None:
        sort_label = {
            "engagement_rate": "engagement rate",
            "watch_count": "views",
            "like_count": "likes",
            "comment_count": "comments",
            "share_count": "shares",
            "save_count": "saves",
            "posted_at": "newest",
            "trending_score": "trending",
        }
        parts.append(f"by {sort_label[sort_by]}")
    if days is not None:
        parts.append(f"in the last {days} days")
    if min_engagement_rate is not None:
        parts.append(f"with engagement rate above {min_engagement_rate * 100:.1f}%")
    if return_all:
        parts.append("all results")
    message = " ".join(parts)
    data = await agent_api_call("POST", "/agent/run", {"message": message, "agent_id": agent_id})
    return json_result(data)

@mcp.tool(name="gen_list_proof_of_genesis_backups", description="Step 4 (Assets): List Proof of Genesis / Backup to Blockchain rows for an agent. Use this to show which assets have been backed up to Walrus, including monthly expires_at and renewal_due_at fields. Removed rows are hidden by default; include_removed=true returns audit history.")
async def gen_list_proof_of_genesis_backups(
    agent_id: Annotated[str, Field(description="The agent ID that owns the backups")],
    include_removed: Annotated[Optional[bool], Field(default=None, description="Include rows removed from the default assets-page view. Defaults to false.")] = None,
) -> str:
    path = f"/agents/{agent_id}/proof-of-genesis/backups"
    if include_removed:
        path += "?include_removed=true"
    data = await agent_core_api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_create_proof_of_genesis_backup", description="Step 4 (Assets): Manually back up a GEN image or video asset to Walrus for the monthly Proof of Genesis storage period, or record an automatic asset event. Automatic backup defaults to downloaded/published assets when enabled. Public assets may be uploaded raw. Private assets must be encrypted before upload because Walrus blobs are public by default. Charges operation backup_to_blockchain with GB-month units after successful upload/readback verification.")
async def gen_create_proof_of_genesis_backup(
    agent_id: Annotated[str, Field(description="The agent ID that owns the asset")],
    asset_url: Annotated[str, Field(description="GEN asset URL to back up. Use assets.gen.pro URLs when available.")],
    asset_type: Annotated[Optional[str], Field(default=None, description="Asset type: video or image.")] = None,
    visibility: Annotated[Optional[str], Field(default=None, description="Asset visibility. Private assets must send encrypted=true and encryption_scheme; raw private requests are rejected before billing or Walrus work.")] = None,
    encrypted: Annotated[Optional[bool], Field(default=None, description="Whether the bytes at asset_url are already encrypted before Walrus upload. Required for private backups.")] = None,
    encryption_scheme: Annotated[Optional[str], Field(default=None, description="Encryption scheme for private backups, e.g. seal/v1.")] = None,
    encryption_key_id: Annotated[Optional[str], Field(default=None, description="Optional key policy/version identifier for private proof metadata.")] = None,
    owner_sui_address: Annotated[Optional[str], Field(default=None, description="Optional customer Sui wallet address that should own the Walrus object. Omit for server-triggered auto-backup when Agent Core resolves the user's Dynamic Sui wallet.")] = None,
    source_event: Annotated[Optional[str], Field(default=None, description="Why this backup is being created.")] = None,
    content_type: Annotated[Optional[str], Field(default=None, description="MIME type if known, e.g. video/mp4 or image/png.")] = None,
    idempotency_key: Annotated[Optional[str], Field(default=None, description="Stable retry key, e.g. content-resource id plus version, to avoid duplicate upload/billing.")] = None,
    metadata: Annotated[Optional[dict], Field(default=None, description="Caller metadata such as content_resource_id, vidsheet_id, row_id, project_id, or publish id.")] = None,
) -> str:
    body = {"asset_url": asset_url, "asset_type": asset_type, "visibility": visibility, "encrypted": encrypted, "source_event": source_event}
    if encryption_scheme is not None:
        body["encryption_scheme"] = encryption_scheme
    if encryption_key_id is not None:
        body["encryption_key_id"] = encryption_key_id
    if owner_sui_address is not None:
        body["owner_sui_address"] = owner_sui_address
    if content_type is not None:
        body["content_type"] = content_type
    if idempotency_key is not None:
        body["idempotency_key"] = idempotency_key
    if metadata is not None:
        body["metadata"] = metadata
    data = await agent_core_api_call("POST", f"/agents/{agent_id}/proof-of-genesis/backups", body)
    return json_result(data)

@mcp.tool(name="gen_remove_proof_of_genesis_backup", description="Step 4 (Assets): Remove a Proof of Genesis row from the default asset view. This soft-removes the GEN proof record (sets removed_at); it does not guarantee deletion from Walrus or Sui.")
async def gen_remove_proof_of_genesis_backup(
    agent_id: Annotated[str, Field(description="The agent ID that owns the backup")],
    backup_id: Annotated[float, Field(description="The Proof of Genesis backup id")],
) -> str:
    data = await agent_core_api_call("DELETE", f"/agents/{agent_id}/proof-of-genesis/backups/{backup_id}")
    return json_result(data)

@mcp.tool(name="gen_list_recurring_jobs", description="Step 3 (Monitoring): List all non-deleted recurring jobs ('daily tasks') for an agent. Returns active, paused, and inactive jobs sorted newest first. Use gen_pause_recurring_job or gen_delete_recurring_job to change state.")
async def gen_list_recurring_jobs(
    agent_id: Annotated[str, Field(description="The agent ID that owns the recurring jobs")],
) -> str:
    data = await agent_api_call("GET", f"/agents/{agent_id}/recurring-jobs")
    return json_result(data)

@mcp.tool(name="gen_create_recurring_job", description="Step 3 (Monitoring): Create a recurring agent job ('daily task'). job_type=generate_content_ideas is the most common default. schedule.cadence ∈ {daily, weekly}; pass timezone (e.g. 'UTC' or 'America/Los_Angeles') and time_of_day ('HH:MM' 24h) for predictable firing. For weekly cadence, days_of_week (0=Mon … 6=Sun) is REQUIRED; for daily it must be omitted. delivery.type ∈ {chat_only, email}; when type=email, the email address is REQUIRED. Each scheduled run is credit-gated: the job remains configured if credits run out and resumes when they return.")
async def gen_create_recurring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_type: Annotated[str, Field(description="Job type. Default content-ideas pipeline: 'generate_content_ideas'.")],
    prompt: Annotated[str, Field(description="Natural-language prompt the agent runs each cycle (e.g. 'Generate 5 TikTok content ideas for my skincare brand')")],
    name: Annotated[Optional[str], Field(default=None, description="Display name. Defaults to the first 80 chars of prompt if omitted.")] = None,
    schedule: Annotated[Optional[dict], Field(default=None, description="Schedule config, e.g. {'cadence': 'daily', 'time_of_day': '09:00', 'timezone': 'UTC'} or {'cadence': 'weekly', 'days_of_week': [0,2,4], 'time_of_day': '09:00', 'timezone': 'UTC'}")] = None,
    delivery: Annotated[Optional[dict], Field(default=None, description="Delivery config, e.g. {'type': 'chat_only'} or {'type': 'email', 'email': 'user@example.com'}")] = None,
    next_run_at: Annotated[Optional[str], Field(default=None, description="ISO-8601 timestamp to schedule the first run (defaults to the next slot from cadence)")] = None,
) -> str:
    body: dict = {"job_type": job_type, "prompt": prompt}
    if schedule is not None:
        body["schedule"] = schedule
    if delivery is not None:
        body["delivery"] = delivery
    if name is not None:
        body["name"] = name
    if next_run_at is not None:
        body["next_run_at"] = next_run_at
    data = await agent_api_call("POST", f"/agents/{agent_id}/recurring-jobs", body)
    return json_result(data)

@mcp.tool(name="gen_ensure_default_recurring_job", description="Step 3 (Monitoring): Idempotently ensure the agent has the default daily content-ideas recurring job. If one already exists for this agent, returns it without changes; otherwise creates it with the standard prompt ('Generate content ideas'), daily cadence at 09:00 UTC, and chat_only delivery. The response 'created' field indicates whether a new job was created (true) or an existing one was returned (false).")
async def gen_ensure_default_recurring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
) -> str:
    data = await agent_api_call("POST", f"/agents/{agent_id}/recurring-jobs/defaults")
    return json_result(data)

@mcp.tool(name="gen_get_recurring_job", description="Step 3 (Monitoring): Fetch a single recurring job by id. Returns 404 if the job is deleted.")
async def gen_get_recurring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The recurring job id")],
) -> str:
    data = await agent_api_call("GET", f"/agents/{agent_id}/recurring-jobs/{job_id}")
    return json_result(data)

@mcp.tool(name="gen_update_recurring_job", description="Step 3 (Monitoring): Update a recurring job's mutable fields. Use gen_pause_recurring_job / gen_resume_recurring_job for status transitions instead of patching status directly. Only fields you pass are updated; pass schedule or delivery as full objects (they replace the existing value).")
async def gen_update_recurring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The recurring job id")],
    name: Annotated[Optional[str], Field(default=None, description="New display name")] = None,
    prompt: Annotated[Optional[str], Field(default=None, description="New prompt the agent will run each cycle")] = None,
    schedule: Annotated[Optional[dict], Field(default=None, description="Schedule config (full replacement): e.g. {'cadence': 'weekly', 'days_of_week': [0,2,4], 'time_of_day': '09:00', 'timezone': 'UTC'}")] = None,
    delivery: Annotated[Optional[dict], Field(default=None, description="Delivery config (full replacement): e.g. {'type': 'email', 'email': 'user@example.com'} or {'type': 'chat_only'}")] = None,
    next_run_at: Annotated[Optional[str], Field(default=None, description="ISO-8601 timestamp to override the next run time")] = None,
) -> str:
    body = {}
    if name is not None:
        body["name"] = name
    if prompt is not None:
        body["prompt"] = prompt
    if schedule is not None:
        body["schedule"] = schedule
    if delivery is not None:
        body["delivery"] = delivery
    if next_run_at is not None:
        body["next_run_at"] = next_run_at
    data = await agent_api_call("PATCH", f"/agents/{agent_id}/recurring-jobs/{job_id}", body)
    return json_result(data)

@mcp.tool(name="gen_pause_recurring_job", description="Step 3 (Monitoring): Pause a recurring job. status → 'paused'. The scheduler stops queueing new runs until gen_resume_recurring_job is called. Does NOT delete the job or its history.")
async def gen_pause_recurring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The recurring job id")],
) -> str:
    data = await agent_api_call("POST", f"/agents/{agent_id}/recurring-jobs/{job_id}/pause")
    return json_result(data)

@mcp.tool(name="gen_resume_recurring_job", description="Step 3 (Monitoring): Resume a paused recurring job. status → 'active'. The scheduler resumes queueing runs at the configured cadence.")
async def gen_resume_recurring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The recurring job id")],
) -> str:
    data = await agent_api_call("POST", f"/agents/{agent_id}/recurring-jobs/{job_id}/resume")
    return json_result(data)

@mcp.tool(name="gen_delete_recurring_job", description="Step 3 (Monitoring): Soft-delete a recurring job. status → 'deleted'. The job stops running and no longer appears in gen_list_recurring_jobs. Use gen_pause_recurring_job if you only want to temporarily stop runs. Returns 204 No Content on success.")
async def gen_delete_recurring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The recurring job id")],
) -> str:
    data = await agent_api_call("DELETE", f"/agents/{agent_id}/recurring-jobs/{job_id}")
    return json_result(data)

@mcp.tool(name="gen_run_recurring_job_now", description="Step 3 (Monitoring): Trigger a recurring job to run immediately without waiting for its next scheduled time. Fires the same execution path as the scheduled run — useful for testing a new job before its first scheduled firing. Returns 202 Accepted with a run_id you can poll via gen_get_run_status.")
async def gen_run_recurring_job_now(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The recurring job id")],
) -> str:
    data = await agent_api_call("POST", f"/agents/{agent_id}/recurring-jobs/{job_id}/test-run")
    return json_result(data)

@mcp.tool(name="gen_duplicate_recurring_job", description="Step 3 (Monitoring): Copy a recurring job to a different vidsheet. The copy inherits the source's prompt (rewritten to the new sheet), schedule, delivery settings, and actions. Returns 409 if the destination sheet already has an automation. Use when you want to run the same workflow on a different sheet without rebuilding it from scratch.")
async def gen_duplicate_recurring_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    job_id: Annotated[str, Field(description="The recurring job ID to duplicate")],
    vidsheet_url: Annotated[str, Field(description="URL of the destination vidsheet to copy the job to")],
    name: Annotated[Optional[str], Field(default=None, description="Name for the copy (defaults to '<source name> (copy)')")] = None,
    activate: Annotated[Optional[bool], Field(default=None, description="Whether the copy starts active (default true)")] = None,
) -> str:
    body: dict = {"vidsheet_url": vidsheet_url}
    if name is not None:
        body["name"] = name
    if activate is not None:
        body["activate"] = activate
    data = await agent_api_call("POST", f"/agents/{agent_id}/recurring-jobs/{job_id}/duplicate", body)
    return json_result(data)

# ─── Billing ──────────────────────────────────────────────────────────────────

@mcp.tool(name="gen_get_credit_balance", description="Step 5 (Export & Publish): Get the agent's available credit balance. Check this before paid operations (generate, render, publish) to confirm the workspace has usable credits.")
async def gen_get_credit_balance(
    agent_id: Annotated[str, Field(description="The agent ID")],
) -> str:
    data = await api_call("GET", f"/credit_balance?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_get_credit_usage", description="Step 5 (Export & Publish): List credit transactions and usage history for an agent. Useful for answering 'how many credits did I spend on video this week?' Read-only.")
async def gen_get_credit_usage(
    agent_id: Annotated[str, Field(description="The agent ID")],
    page: Annotated[Optional[int], Field(default=None, description="Page number (default 1)")] = None,
) -> str:
    path = f"/credit_transactions?agent_id={agent_id}"
    if page is not None:
        path += f"&page={page}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_list_credit_plans", description="Step 5 (Export & Publish): List available credit and subscription plans. Use before gen_buy_credits to show the user their options.")
async def gen_list_credit_plans(
    cycle: Annotated[Optional[str], Field(default=None, description="Billing cycle: 'monthly' (default) or 'annual'")] = None,
) -> str:
    path = "/credit_plans"
    if cycle is not None:
        path += f"?cycle={cycle}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_buy_credits", description="Step 5 (Export & Publish): Start a credit purchase (Stripe checkout) — returns a payment link the user opens to pay. ALWAYS confirm the plan and price with the user BEFORE calling; this initiates a real money charge. Use when the user is out of credits and wants to buy more.")
async def gen_buy_credits(
    organization_id: Annotated[str, Field(description="The organization/workspace ID to fund")],
    credit_plan_id: Annotated[str, Field(description="The credit plan ID from gen_list_credit_plans")],
    success_url: Annotated[Optional[str], Field(default=None, description="Redirect URL after successful payment (default: gen.pro/api-keys)")] = None,
    cancel_url: Annotated[Optional[str], Field(default=None, description="Redirect URL on cancel (default: gen.pro/home)")] = None,
) -> str:
    body = {
        "credit_plan_id": credit_plan_id,
        "organization_id": organization_id,
        "success_url": success_url or "https://gen.pro/api-keys",
        "cancel_url": cancel_url or "https://gen.pro/home",
    }
    data = await api_call("POST", "/payment", body)
    return json_result(data)

@mcp.tool(name="gen_upgrade_workspace", description="Step 5 (Export & Publish): Upgrade a workspace to a higher subscription tier — returns a Stripe checkout link. CONFIRM with the user BEFORE calling; this changes their billing plan.")
async def gen_upgrade_workspace(
    organization_id: Annotated[str, Field(description="The organization/workspace ID to upgrade")],
    credit_plan_id: Annotated[str, Field(description="The target plan ID from gen_list_credit_plans")],
    return_url: Annotated[str, Field(description="URL to redirect to after the checkout completes")],
) -> str:
    body = {
        "creditPlanId": credit_plan_id,
        "organizationId": organization_id,
        "returnUrl": return_url,
    }
    data = await api_call("POST", "/subscription_upgrade", body)
    return json_result(data)

# ─── Social Connect ────────────────────────────────────────────────────────────

_SOCIAL_PLATFORMS = ("tiktok", "instagram", "facebook", "youtube", "x")

@mcp.tool(name="gen_list_connected_socials", description="Step 5 (Export & Publish): List which social accounts (tiktok/instagram/facebook/youtube/x) the agent has connected for publishing. Call this before scheduling or publishing a post, or to check if a platform still needs to be connected.")
async def gen_list_connected_socials(
    agent_id: Annotated[str, Field(description="The agent ID")],
) -> str:
    data = await integration_api_call("POST", "/platform/get_oauth_account", {"agent_id": agent_id})
    return json_result(data)

@mcp.tool(name="gen_get_social_connect_url", description="Step 5 (Export & Publish): Get an OAuth URL the user opens in a browser to connect a social account for publishing. platform: youtube | tiktok | instagram | facebook | x. The MCP never handles credentials — give the user the returned URL; they approve it in their browser and GEN saves the connection automatically. Confirm afterward with gen_list_connected_socials.")
async def gen_get_social_connect_url(
    agent_id: Annotated[str, Field(description="The agent ID")],
    platform: Annotated[str, Field(description="Platform to connect: tiktok | instagram | facebook | youtube | x")] = "youtube",
) -> str:
    if platform not in _SOCIAL_PLATFORMS:
        return json_result({"ok": False, "error": f"Unsupported platform '{platform}'. Use one of: {', '.join(_SOCIAL_PLATFORMS)}.", "error_code": "unsupported_platform"})
    data = await integration_api_call("POST", "/platform/get_authorization_url", {"agent_id": agent_id}, params={"platform": platform})
    return json_result(data)

@mcp.tool(name="gen_disconnect_social", description="Step 5 (Export & Publish): Disconnect a connected social account from the agent. platform: tiktok | instagram | facebook | youtube | x.")
async def gen_disconnect_social(
    agent_id: Annotated[str, Field(description="The agent ID")],
    platform: Annotated[str, Field(description="Platform to disconnect: tiktok | instagram | facebook | youtube | x")],
) -> str:
    if platform not in _SOCIAL_PLATFORMS:
        return json_result({"ok": False, "error": f"Unsupported platform '{platform}'. Use one of: {', '.join(_SOCIAL_PLATFORMS)}.", "error_code": "unsupported_platform"})
    data = await integration_api_call("PUT", f"/platform/disconnect/{platform}", {"agent_id": agent_id})
    return json_result(data)

# ─── Scheduled Posts ───────────────────────────────────────────────────────────

@mcp.tool(name="gen_list_scheduled_posts", description="Step 5 (Export & Publish): List scheduled posts (the content calendar). Returns an empty list when the agent has no calendar yet. Optional date range filter.")
async def gen_list_scheduled_posts(
    agent_id: Annotated[str, Field(description="The agent ID")],
    start_date: Annotated[Optional[str], Field(default=None, description="Start date filter (ISO 8601)")] = None,
    end_date: Annotated[Optional[str], Field(default=None, description="End date filter (ISO 8601)")] = None,
) -> str:
    params: dict = {"agent_id": agent_id}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    try:
        data = await integration_api_call("GET", "/schedule/posts", params=params)
    except Exception as exc:
        msg = str(exc)
        if "404" in msg:
            return json_result({"scheduled_posts": []})
        raise
    return json_result(data)

@mcp.tool(name="gen_schedule_post", description="Step 5 (Export & Publish): Schedule or immediately post content to a social platform. platform: tiktok | instagram | facebook | youtube | x. schedule_type: 'now' for immediate, 'specific_time' with scheduled_time (ISO 8601) for a calendar slot. Pass media_url for a single video, media_urls for images (X supports up to 4). For text-only posts (X only), omit media. timezone_offset is local UTC offset in hours (e.g. -7 for LA daylight time).")
async def gen_schedule_post(
    agent_id: Annotated[str, Field(description="The agent ID")],
    platform: Annotated[str, Field(description="Target platform: tiktok | instagram | facebook | youtube | x")],
    description: Annotated[Optional[str], Field(default=None, description="Post caption/description with hashtags inline")] = None,
    media_url: Annotated[Optional[str], Field(default=None, description="Public URL to a single video file")] = None,
    media_urls: Annotated[Optional[list], Field(default=None, description="List of image URLs (X supports up to 4)")] = None,
    schedule_type: Annotated[Optional[str], Field(default=None, description="'now' for immediate posting, 'specific_time' for scheduled")] = None,
    scheduled_time: Annotated[Optional[str], Field(default=None, description="ISO 8601 UTC datetime. Required when schedule_type is 'specific_time'.")] = None,
    title: Annotated[Optional[str], Field(default=None, description="Post title (YouTube requires this)")] = None,
    media_type: Annotated[Optional[str], Field(default=None, description="VIDEO (default) | IMAGE | TWEET_VIDEO")] = None,
    thumbnail_url: Annotated[Optional[str], Field(default=None, description="Custom thumbnail URL")] = None,
    thread: Annotated[Optional[list], Field(default=None, description="X only — ordered tweet segments for a thread")] = None,
    reply_to_tweet_id: Annotated[Optional[str], Field(default=None, description="X only — post as a reply to this tweet ID")] = None,
    timezone_offset: Annotated[Optional[float], Field(default=None, description="Local UTC offset in hours (e.g. -7 for LA daylight)")] = None,
) -> str:
    import json as _json
    body: dict = {
        "agent_id": agent_id,
        "platform": [platform],
        "schedule_type": schedule_type or "now",
        "media_type": media_type or "VIDEO",
    }
    for k, v in {
        "description": description, "media_url": media_url, "media_urls": media_urls,
        "scheduled_time": scheduled_time, "title": title, "thumbnail_url": thumbnail_url,
        "thread": thread, "reply_to_tweet_id": reply_to_tweet_id,
    }.items():
        if v is not None:
            body[k] = v
    headers = None
    if timezone_offset is not None:
        headers = {"X-Timezone-Offset": str(timezone_offset)}
    data = await integration_api_call("POST", "/schedule/with-post", body)
    return json_result(data)

@mcp.tool(name="gen_get_post_status", description="Step 5 (Export & Publish): Check whether a post actually went live. Returns PLATFORM-CONFIRMED publish status — not just 'queued'. Use to answer 'did my post publish?' and 'why did it fail?'. Status flow: accepted → publishing → published | failed. Each platform entry includes platform_post_id, post_url (when published), and error (when failed).")
async def gen_get_post_status(
    post_id: Annotated[str, Field(description="The post ID from gen_schedule_post")],
) -> str:
    data = await integration_api_call("GET", f"/schedule/post/{post_id}")
    return json_result(data)

@mcp.tool(name="gen_update_scheduled_post", description="Step 5 (Export & Publish): Update a scheduled post's time, description, media, etc. Only works before the post goes out — published posts cannot be edited.")
async def gen_update_scheduled_post(
    post_id: Annotated[str, Field(description="The post ID to update")],
    fields: Annotated[dict, Field(description="Fields to update (sparse — only send what changes)")],
) -> str:
    data = await integration_api_call("PATCH", f"/schedule/post/{post_id}", fields)
    return json_result(data)

@mcp.tool(name="gen_delete_scheduled_post", description="Step 5 (Export & Publish): Delete a scheduled post from the content calendar.")
async def gen_delete_scheduled_post(
    post_id: Annotated[str, Field(description="The post ID to delete")],
) -> str:
    data = await integration_api_call("DELETE", f"/schedule/post/{post_id}")
    return json_result(data)

# ─── Direct Generation (user_jobs convenience wrappers) ────────────────────────

_IMAGE_VERSIONS = ["nano-banana", "nano-banana-pro", "nano-banana-2"]
_VIDEO_MODELS = [
    "seedance-1.0-lite", "seedance-1.0-pro", "seedance-1.5-pro", "seedance-2.0",
    "veo_3", "veo_3_1", "kling_2_1", "kling_2_6", "sora_2", "pika", "grok",
]
_SONG_MODELS = ["suno-v5-beta", "suno-v4.5plus-beta"]

@mcp.tool(name="gen_create_image", description="Step 4 (Edit & Generate): Generate an image from a text prompt. version selects the image model: 'nano-banana-pro' (highest quality, default), 'nano-banana' (fast), 'nano-banana-2' (balanced). aspect_ratio: 1:1 | 9:16 | 16:9. Pass reference_images (public URLs) for image-to-image identity-preserving generation (same face/product in a new scene). Paid — returns a generation_id to poll with gen_get_generation.")
async def gen_create_image(
    agent_id: Annotated[str, Field(description="The agent ID")],
    prompt: Annotated[str, Field(description="Image generation prompt")],
    version: Annotated[Optional[str], Field(default=None, description="Image model: nano-banana-pro (default) | nano-banana | nano-banana-2")] = None,
    aspect_ratio: Annotated[Optional[str], Field(default=None, description="Aspect ratio: 9:16 (default) | 1:1 | 16:9")] = None,
    number_of_images: Annotated[Optional[int], Field(default=None, description="Number of images to generate (default 1)")] = None,
    reference_images: Annotated[Optional[list], Field(default=None, description="List of public image URLs for image-to-image reference (up to 10)")] = None,
    content_resource_ids: Annotated[Optional[list], Field(default=None, description="GEN content resource IDs to use as reference images (preferred over reference_images)")] = None,
) -> str:
    import json as _json
    v = version if version in _IMAGE_VERSIONS else "nano-banana-pro"
    data_body: dict = {
        "model": "gemini", "version": v,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio or "9:16",
        "number_of_images": number_of_images or 1,
    }
    if content_resource_ids:
        data_body["content_resource_ids"] = content_resource_ids[:10]
    elif reference_images:
        data_body["images"] = [{"value": url} for url in reference_images[:10]]
    body = {"agent_id": agent_id, "user_job_type": "gemini_image_generation", "data": _json.dumps(data_body)}
    result = await api_call("POST", "/user_jobs", body)
    return json_result(result)

@mcp.tool(name="gen_create_look", description="Step 1 (Agent Setup): Generate one image of the agent's CHARACTER — a 'look'. Use when the user says 'generate a look for me', 'show my character at the beach', etc. Pass reference_images (public photo URLs of the character) to preserve their face/identity. Paid — returns a generation_id to poll with gen_get_generation.")
async def gen_create_look(
    agent_id: Annotated[str, Field(description="The agent ID")],
    instructions: Annotated[Optional[str], Field(default=None, description="Extra styling/scene direction (outfit, setting, mood)")] = None,
    reference_images: Annotated[Optional[list], Field(default=None, description="Public photo URLs of the character for identity preservation")] = None,
    version: Annotated[Optional[str], Field(default=None, description="Image model: nano-banana-pro (default) | nano-banana | nano-banana-2")] = None,
    aspect_ratio: Annotated[Optional[str], Field(default=None, description="Aspect ratio: 9:16 (default) | 1:1 | 16:9")] = None,
) -> str:
    import json as _json
    v = version if version in _IMAGE_VERSIONS else "nano-banana-pro"
    has_refs = bool(reference_images)
    parts: list = []
    if has_refs:
        parts.append("Generate a high-quality, photorealistic image of the SAME person shown in the attached reference photos. Preserve their face, hair, skin tone, and identity exactly.")
    else:
        parts.append("Generate a high-quality, photorealistic image of a person.")
    if instructions and instructions.strip():
        parts.append(instructions.strip())
    else:
        parts.append("Choose a tasteful, on-brand setting, outfit, and lighting for them.")
    data_body: dict = {
        "model": "gemini", "version": v,
        "prompt": " ".join(parts),
        "aspect_ratio": aspect_ratio or "9:16",
        "number_of_images": 1,
    }
    if has_refs:
        data_body["images"] = [{"value": url} for url in reference_images[:10]]
    body = {"agent_id": agent_id, "user_job_type": "gemini_image_generation", "data": _json.dumps(data_body)}
    result = await api_call("POST", "/user_jobs", body)
    return json_result(result)

@mcp.tool(name="gen_create_video", description="Step 4 (Edit & Generate): Generate one raw video clip from a text prompt. model: seedance-2.0 (default) | seedance-1.0-lite/1.0-pro/1.5-pro | veo_3 | veo_3_1 | kling_2_1 | kling_2_6 | sora_2 | pika | grok. resolution: 1080p (default) | 720p. Seedance 2.0 supports duration 4-15s. Paid — returns a generation_id to poll with gen_get_generation. For a complete multi-scene video from a brief, use gen_chat instead.")
async def gen_create_video(
    agent_id: Annotated[str, Field(description="The agent ID")],
    prompt: Annotated[str, Field(description="Video generation prompt")],
    model: Annotated[Optional[str], Field(default=None, description="Video model (default: seedance-2.0)")] = None,
    aspect_ratio: Annotated[Optional[str], Field(default=None, description="Aspect ratio: 16:9 (default) | 9:16 | 1:1")] = None,
    resolution: Annotated[Optional[str], Field(default=None, description="Resolution: 1080p (default) | 720p")] = None,
    duration: Annotated[Optional[int], Field(default=None, description="Duration in seconds (default 5; seedance-2.0 supports 4-15)")] = None,
    native_audio: Annotated[Optional[bool], Field(default=None, description="Request model-native audio where supported (default false)")] = None,
) -> str:
    import json as _json
    m = model if model in _VIDEO_MODELS else "seedance-2.0"
    if m == "seedance-2.0":
        job_type = "seedance_2_0_video_generation"
    elif m == "grok":
        job_type = "grok_video_generation"
    else:
        job_type = "seedance_video_generation"
    data_body: dict = {
        "model": m,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio or "16:9",
        "resolution": resolution or "1080p",
        "duration": duration or 5,
        "native_audio": native_audio or False,
    }
    body = {"agent_id": agent_id, "user_job_type": job_type, "data": _json.dumps(data_body)}
    result = await api_call("POST", "/user_jobs", body)
    return json_result(result)

@mcp.tool(name="gen_create_song", description="Step 4 (Edit & Generate): Generate one original song/music track. model: suno-v5-beta (default, best quality) | suno-v4.5plus-beta (supports up to 8 min). duration: seconds (default 60, max 480). Pass style for genre/mood, title for a named track, negative_tags for styles to avoid, vocal_gender ('m'/'f'), instrumental=true for no vocals. For audio-to-audio conditioning, pass source_audio_resource_id (preferred) or source_audio_url plus audio_weight (0.0-1.0). Paid — returns a generation_id to poll with gen_get_generation.")
async def gen_create_song(
    agent_id: Annotated[str, Field(description="The agent ID")],
    prompt: Annotated[str, Field(description="Song description / lyrics prompt")],
    model: Annotated[Optional[str], Field(default=None, description="Song model: suno-v5-beta (default) | suno-v4.5plus-beta")] = None,
    duration: Annotated[Optional[int], Field(default=None, description="Duration in seconds (default 60, max 480)")] = None,
    style: Annotated[Optional[str], Field(default=None, description="Musical style/genre/mood (max 1000 chars)")] = None,
    title: Annotated[Optional[str], Field(default=None, description="Song title (max 80 chars)")] = None,
    negative_tags: Annotated[Optional[str], Field(default=None, description="Styles/instruments to avoid (max 500 chars)")] = None,
    vocal_gender: Annotated[Optional[str], Field(default=None, description="'m' or 'f' to bias vocal gender")] = None,
    instrumental: Annotated[Optional[bool], Field(default=None, description="True to generate without vocals")] = None,
    source_audio_resource_id: Annotated[Optional[int], Field(default=None, description="GEN content resource ID for audio-to-audio conditioning")] = None,
    source_audio_url: Annotated[Optional[str], Field(default=None, description="Direct HTTPS audio URL for audio-to-audio conditioning")] = None,
    audio_weight: Annotated[Optional[float], Field(default=None, description="Audio conditioning fidelity 0.0-1.0")] = None,
) -> str:
    import json as _json
    m = model if model in _SONG_MODELS else "suno-v5-beta"
    d = max(1, min(480, duration or 60))
    data_body: dict = {"prompt": prompt, "model": m, "duration": d, "instrumental": instrumental or False}
    for k, v in {"style": style, "title": title, "negative_tags": negative_tags, "vocal_gender": vocal_gender}.items():
        if v is not None:
            data_body[k] = v
    if source_audio_resource_id is not None:
        data_body["source_audio_resource_id"] = int(source_audio_resource_id)
    elif source_audio_url:
        data_body["reference_audio"] = {"value": source_audio_url, "media_type": "audio"}
    if audio_weight is not None:
        data_body["audio_weight"] = float(audio_weight)
    body = {"agent_id": agent_id, "user_job_type": "song_generation", "data": _json.dumps(data_body)}
    result = await api_call("POST", "/user_jobs", body)
    return json_result(result)

@mcp.tool(name="gen_estimate_job", description="Step 4 (Edit & Generate): Estimate the credit cost of one or more generation jobs BEFORE running them. Free to call. Pair with gen_get_credit_balance to check affordability before a paid run.")
async def gen_estimate_job(
    agent_id: Annotated[str, Field(description="The agent ID")],
    jobs: Annotated[list, Field(description="List of job specs to estimate (same shape as user_jobs create body data)")],
) -> str:
    data = await api_call("POST", "/user_jobs/estimate", {"agent_id": agent_id, "user_jobs": jobs})
    return json_result(data)

# ─── Assets ────────────────────────────────────────────────────────────────────

@mcp.tool(name="gen_list_assets", description="Step 4 (Edit & Generate): List the agent's content resources / asset library (images, video, audio). Optional type filter. Use to find existing assets before uploading duplicates.")
async def gen_list_assets(
    agent_id: Annotated[str, Field(description="The agent ID")],
    type: Annotated[Optional[str], Field(default=None, description="Filter by file type: image | video | audio")] = None,
    page: Annotated[Optional[int], Field(default=None, description="Page number (default 1)")] = None,
) -> str:
    path = f"/content_resources?agent_id={agent_id}"
    if type is not None:
        path += f"&type={type}"
    if page is not None:
        path += f"&page={page}"
    data = await api_call("GET", path)
    return json_result(data)

@mcp.tool(name="gen_get_asset", description="Step 4 (Edit & Generate): Get a single content resource including its downloadable CDN URL.")
async def gen_get_asset(
    agent_id: Annotated[str, Field(description="The agent ID")],
    resource_id: Annotated[str, Field(description="The content resource ID")],
) -> str:
    data = await api_call("GET", f"/content_resources/{resource_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_delete_asset", description="Step 4 (Edit & Generate): Delete a content resource from the agent's asset library.")
async def gen_delete_asset(
    agent_id: Annotated[str, Field(description="The agent ID")],
    resource_id: Annotated[str, Field(description="The content resource ID to delete")],
) -> str:
    data = await api_call("DELETE", f"/content_resources/{resource_id}?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_complete_asset_upload", description="Step 4 (Edit & Generate): Attach an already-uploaded blob to the agent's durable asset library. Use after gen_create_direct_upload has returned a signed_id and you have PUT the file bytes to the upload URL. Returns the content_resource id and permanent CDN URL.")
async def gen_complete_asset_upload(
    agent_id: Annotated[str, Field(description="The agent ID")],
    signed_id: Annotated[str, Field(description="The signed_id returned from gen_create_direct_upload")],
    folder_id: Annotated[Optional[str], Field(default=None, description="Place the asset inside this folder")] = None,
) -> str:
    body: dict = {"content_resource": {"file": signed_id}}
    if folder_id is not None:
        body["asset_folder"] = {"id": folder_id}
    data = await api_call("POST", f"/content_resources?agent_id={agent_id}", body)
    return json_result(data)

@mcp.tool(name="gen_import_asset_from_url", description="Step 4 (Edit & Generate): Import media from a public URL (YouTube/TikTok/Instagram/direct file URL) into the agent's asset library. No length limit — useful for long B-roll. Returns a job; poll the import status.")
async def gen_import_asset_from_url(
    agent_id: Annotated[str, Field(description="The agent ID")],
    url: Annotated[str, Field(description="Public URL to import (YouTube, TikTok, Instagram, or direct file)")],
    folder_id: Annotated[Optional[str], Field(default=None, description="Place the imported asset inside this folder")] = None,
) -> str:
    body: dict = {"agent_id": agent_id, "url": url}
    if folder_id is not None:
        body["folder_id"] = folder_id
    data = await api_call("POST", "/content_resources/from_url", body)
    return json_result(data)

# ─── Voice (additional tools) ─────────────────────────────────────────────────

@mcp.tool(name="gen_list_my_voices", description="Step 1 (Agent Setup): List the agent's own custom/created voices (user_voice_resources). These are voices the user has designed, trained, or cloned — not the shared public catalog.")
async def gen_list_my_voices(
    agent_id: Annotated[str, Field(description="The agent ID")],
) -> str:
    data = await api_call("GET", f"/user_voice_resources?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_get_voice_sample_status", description="Step 1 (Agent Setup) — Voice design: Poll a voice-design sample job started by gen_generate_voice_samples. Returns status pending | completed | failed. When completed includes the base64 audio and speaker_embedding_url to pass into gen_design_voice.")
async def gen_get_voice_sample_status(
    agent_id: Annotated[str, Field(description="The agent ID")],
    generation_id: Annotated[str, Field(description="The generation ID from gen_generate_voice_samples")],
) -> str:
    data = await api_call("GET", f"/hume_ai_sample/status?agent_id={agent_id}&generation_id={generation_id}")
    return json_result(data)

# ─── Variables (CRUD on vidsheet global_variables) ─────────────────────────────

@mcp.tool(name="gen_create_variable", description="Step 4 (Edit & Generate): Create a global variable (name + value) on a vidsheet. Variables are used for template substitution in prompts and content (e.g. {{brand_name}}).")
async def gen_create_variable(
    engine_id: Annotated[str, Field(description="The vidsheet/engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    name: Annotated[str, Field(description="Variable name (used as {{name}} in templates)")],
    value: Annotated[str, Field(description="Variable value")],
) -> str:
    data = await api_call("POST", f"/vidsheet/{engine_id}/global_variables?agent_id={agent_id}", {"name": name, "value": value})
    return json_result(data)

@mcp.tool(name="gen_update_variable", description="Step 4 (Edit & Generate): Update a global variable's name and/or value on a vidsheet. Sparse — only send what you want to change.")
async def gen_update_variable(
    engine_id: Annotated[str, Field(description="The vidsheet/engine ID")],
    variable_id: Annotated[str, Field(description="The variable ID to update")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    name: Annotated[Optional[str], Field(default=None, description="New variable name")] = None,
    value: Annotated[Optional[str], Field(default=None, description="New variable value")] = None,
) -> str:
    body: dict = {}
    if name is not None:
        body["name"] = name
    if value is not None:
        body["value"] = value
    data = await api_call("PATCH", f"/vidsheet/{engine_id}/global_variables/{variable_id}?agent_id={agent_id}", body)
    return json_result(data)

@mcp.tool(name="gen_delete_variable", description="Step 4 (Edit & Generate): Delete a global variable from a vidsheet.")
async def gen_delete_variable(
    engine_id: Annotated[str, Field(description="The vidsheet/engine ID")],
    variable_id: Annotated[str, Field(description="The variable ID to delete")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("DELETE", f"/vidsheet/{engine_id}/global_variables/{variable_id}?agent_id={agent_id}")
    return json_result(data)

# ─── Vidsheet undo / redo (change-set history) ───────────────────────────────
# Backs the undo/redo surface: every grouped write to a vidsheet is
# recorded as a change set you can walk back (or forward again). Use the `last`
# tool to find the next thing you'd take back, then `undo`/`redo` it. Pass an
# explicit change_set_id to undo/redo a specific change set instead of the most
# recent one. Conflicts return 409 — refresh the engine and retry.

@mcp.tool(name="gen_list_operations", description="Step 4 (Edit & Generate): List recent undoable change sets for a vidsheet (the undo/redo history). Returns {change_sets:[...]} newest-first. Set include_undone=true to also list already-undone change sets. Use gen_get_last_operation to find just the next thing you'd undo, then gen_undo_operation / gen_redo_operation.")
async def gen_list_operations(
    engine_id: Annotated[str, Field(description="The vidsheet/engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    limit: Annotated[Optional[float], Field(default=None, description="Max change sets to return (1-100, default 20).")] = None,
    include_undone: Annotated[Optional[bool], Field(default=None, description="Include already-undone change sets (default false).")] = None,
) -> str:
    import urllib.parse as _up
    q = {"agent_id": agent_id}
    if limit is not None:
        q["limit"] = str(int(limit))
    if include_undone is not None:
        q["include_undone"] = "true" if include_undone else "false"
    qs = _up.urlencode(q)
    data = await api_call("GET", f"/vidsheet/{engine_id}/operations?{qs}")
    return json_result(data)

@mcp.tool(name="gen_get_last_operation", description="Step 4 (Edit & Generate): Get the single next-to-undo change set for a vidsheet (what the undo button would take back). Returns {change_set: ... | null}. Cheaper than gen_list_operations when you only need the top of the undo stack.")
async def gen_get_last_operation(
    engine_id: Annotated[str, Field(description="The vidsheet/engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
) -> str:
    data = await api_call("GET", f"/vidsheet/{engine_id}/operations/last?agent_id={agent_id}")
    return json_result(data)

@mcp.tool(name="gen_undo_operation", description="Step 4 (Edit & Generate): Undo the most recent undoable change set on a vidsheet (or a specific one by change_set_id). Returns {change_set_id, undone:[...], next_undoable}. Use after gen_get_last_operation. Returns nothing_to_undo (422) when the stack is empty; 409 undo_conflict means the engine changed under you — refresh (gen_get_engine) and retry.")
async def gen_undo_operation(
    engine_id: Annotated[str, Field(description="The vidsheet/engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    change_set_id: Annotated[Optional[str], Field(default=None, description="Undo this specific change set instead of the most recent undoable one.")] = None,
) -> str:
    body = {}
    if change_set_id is not None:
        body["change_set_id"] = change_set_id
    data = await api_call("POST", f"/vidsheet/{engine_id}/operations/undo?agent_id={agent_id}", body or None)
    return json_result(data)

@mcp.tool(name="gen_redo_operation", description="Step 4 (Edit & Generate): Redo the most recently undone change set on a vidsheet (or a specific one by change_set_id). Returns {change_set_id, redone:[...], next_undoable}. Use to re-apply something just undone with gen_undo_operation. Returns nothing_to_redo (422) when there is nothing to redo; 409 redo_conflict — refresh (gen_get_engine) and retry.")
async def gen_redo_operation(
    engine_id: Annotated[str, Field(description="The vidsheet/engine ID")],
    agent_id: Annotated[str, Field(description="The agent ID that owns the engine")],
    change_set_id: Annotated[Optional[str], Field(default=None, description="Redo this specific change set instead of the most recently undone one.")] = None,
) -> str:
    body = {}
    if change_set_id is not None:
        body["change_set_id"] = change_set_id
    data = await api_call("POST", f"/vidsheet/{engine_id}/operations/redo?agent_id={agent_id}", body or None)
    return json_result(data)

# ─── Compose / Natural-language delegation ────────────────────────────────────

@mcp.tool(name="gen_ask", description="Step 2 (Content Ideas): Ask GEN a question about real social media data and get an answer grounded in the GEN data warehouse. Use for any question about a video link, account, hashtag, trend, sound, hook, comment, or creator — across TikTok, Instagram, YouTube, and more. Examples: 'What is this TikTok about? https://tiktok.com/@x/video/123', 'Top creators in #skincare last 30 days', 'Best time to post for fitness content'. Paste social/video links directly in the question. Polls /agent/run to completion by default.")
async def gen_ask(
    agent_id: Annotated[str, Field(description="The agent ID")],
    question: Annotated[str, Field(description="The question to ask (paste video/social links inline)")],
    conversation_id: Annotated[Optional[str], Field(default=None, description="Continue an existing conversation (from a prior run)")] = None,
    wait: Annotated[Optional[bool], Field(default=None, description="Poll to completion (default true). Set false to return the run_id immediately.")] = None,
    attachments: Annotated[Optional[list], Field(default=None, description="File attachments (list of {signed_id, filename, content_type, url})")] = None,
) -> str:
    import asyncio as _asyncio
    body: dict = {
        "message": question,
        "agent_id": agent_id,
        "auto_confirm": True,
        "metadata": {"source": "mcp", "tool": "gen_ask"},
    }
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    if attachments is not None:
        body["attachments"] = attachments
    started = await agent_api_call("POST", "/agent/run", body)
    should_wait = wait if wait is not None else True
    run_id = started.get("run_id") if isinstance(started, dict) else None
    if not should_wait or not run_id:
        return json_result(started)
    for _ in range(120):
        await _asyncio.sleep(2)
        status = await agent_api_call("GET", f"/agent/runs/{run_id}")
        state = status.get("status") if isinstance(status, dict) else None
        if state in ("completed", "failed", "stopped", "awaiting_approval"):
            return json_result(status)
    return json_result({"ok": True, "run_id": run_id, "status": "running", "note": "still running; poll gen_get_run_status"})

@mcp.tool(name="gen_chat", description="Step 2 (Content Ideas): Send an open-ended natural-language BUILD goal to the GEN composer. Use for multi-step goals like 'Create a 5-scene video about Roman history and schedule it' or 'Duplicate this row and make it punchier'. The composer plans and executes across the GEN platform. For questions about data/videos/creators, use gen_ask instead. For exact single operations, use the specific gen_* tool.")
async def gen_chat(
    agent_id: Annotated[str, Field(description="The agent ID")],
    message: Annotated[str, Field(description="The build goal or instruction for the GEN composer")],
    conversation_id: Annotated[Optional[str], Field(default=None, description="Continue an existing conversation (from a prior run)")] = None,
    wait: Annotated[Optional[bool], Field(default=None, description="Poll to completion (default true). Set false to return run_id immediately.")] = None,
    attachments: Annotated[Optional[list], Field(default=None, description="File attachments (list of {signed_id, filename, content_type, url})")] = None,
) -> str:
    import asyncio as _asyncio
    body: dict = {
        "message": message,
        "agent_id": agent_id,
        "auto_confirm": True,
        "metadata": {"source": "mcp", "tool": "gen_chat"},
    }
    if conversation_id is not None:
        body["conversation_id"] = conversation_id
    if attachments is not None:
        body["attachments"] = attachments
    started = await agent_api_call("POST", "/agent/run", body)
    should_wait = wait if wait is not None else True
    run_id = started.get("run_id") if isinstance(started, dict) else None
    if not should_wait or not run_id:
        return json_result(started)
    for _ in range(120):
        await _asyncio.sleep(2)
        status = await agent_api_call("GET", f"/agent/runs/{run_id}")
        state = status.get("status") if isinstance(status, dict) else None
        if state in ("completed", "failed", "stopped", "awaiting_approval"):
            return json_result(status)
    return json_result({"ok": True, "run_id": run_id, "status": "running", "note": "still running; poll gen_get_run_status"})
