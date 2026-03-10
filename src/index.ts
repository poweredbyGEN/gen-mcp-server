#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const API_KEY = process.env.GEN_API_KEY;
const BASE_URL = process.env.GEN_API_BASE_URL || "https://api.gen.pro/v1";

if (!API_KEY) {
  console.error("GEN_API_KEY environment variable is required");
  process.exit(1);
}

async function apiCall(method: string, path: string, body?: unknown): Promise<unknown> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    method,
    headers: {
      "X-API-Key": API_KEY!,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${JSON.stringify(data)}`);
  }
  return data;
}

function jsonResult(data: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }],
  };
}

const server = new McpServer({
  name: "autocontentengine",
  version: "0.1.0",
});

// ── Discovery tools ──────────────────────────────────────────────────────────

server.tool(
  "gen_get_me",
  "Get the authenticated user's profile and workspace info",
  {},
  async () => {
    const data = await apiCall("GET", "/me");
    return jsonResult(data);
  }
);

server.tool(
  "gen_list_workspaces",
  "List all workspaces the authenticated user has access to",
  {},
  async () => {
    const data = await apiCall("GET", "/workspaces");
    return jsonResult(data);
  }
);

server.tool(
  "gen_list_agents",
  "List agents, optionally filtered by workspace",
  {
    workspace_id: z.string().optional().describe("Filter agents by workspace ID"),
  },
  async ({ workspace_id }) => {
    const params = workspace_id ? `?workspace_id=${workspace_id}` : "";
    const data = await apiCall("GET", `/agents${params}`);
    return jsonResult(data);
  }
);

// ── Engine tools ─────────────────────────────────────────────────────────────

server.tool(
  "gen_create_engine",
  "Create a new Auto Content Engine for an agent",
  {
    agent_id: z.string().describe("The agent ID to create the engine for"),
    title: z.string().describe("Title for the new engine"),
  },
  async ({ agent_id, title }) => {
    const data = await apiCall("POST", "/autocontentengine", { agent_id, title });
    return jsonResult(data);
  }
);

server.tool(
  "gen_get_engine",
  "Get details of a specific Auto Content Engine",
  {
    agent_id: z.string().describe("The agent ID that owns the engine"),
    engine_id: z.string().describe("The engine ID to retrieve"),
  },
  async ({ agent_id, engine_id }) => {
    const data = await apiCall("GET", `/autocontentengine/${engine_id}?agent_id=${agent_id}`);
    return jsonResult(data);
  }
);

server.tool(
  "gen_clone_engine",
  "Clone an existing engine, optionally to a different agent",
  {
    agent_id: z.string().describe("The agent ID that owns the source engine"),
    engine_id: z.string().describe("The engine ID to clone"),
    target_agent_id: z.string().optional().describe("Target agent ID (defaults to same agent)"),
  },
  async ({ agent_id, engine_id, target_agent_id }) => {
    const body: Record<string, string> = { agent_id };
    if (target_agent_id) body.target_agent_id = target_agent_id;
    const data = await apiCall("POST", `/autocontentengine/${engine_id}/clone`, body);
    return jsonResult(data);
  }
);

// ── Row tools ────────────────────────────────────────────────────────────────

server.tool(
  "gen_list_rows",
  "List all rows in an Auto Content Engine",
  {
    engine_id: z.string().describe("The engine ID"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
  },
  async ({ engine_id, agent_id }) => {
    const data = await apiCall("GET", `/autocontentengine/${engine_id}/rows?agent_id=${agent_id}`);
    return jsonResult(data);
  }
);

server.tool(
  "gen_create_row",
  "Create a new row in an Auto Content Engine",
  {
    engine_id: z.string().describe("The engine ID"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
  },
  async ({ engine_id, agent_id }) => {
    const data = await apiCall("POST", `/autocontentengine/${engine_id}/rows`, { agent_id });
    return jsonResult(data);
  }
);

server.tool(
  "gen_duplicate_row",
  "Duplicate an existing row in an Auto Content Engine",
  {
    engine_id: z.string().describe("The engine ID"),
    row_id: z.string().describe("The row ID to duplicate"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
  },
  async ({ engine_id, row_id, agent_id }) => {
    const data = await apiCall("POST", `/autocontentengine/${engine_id}/rows/${row_id}/duplicate`, { agent_id });
    return jsonResult(data);
  }
);

// ── Cell tools ───────────────────────────────────────────────────────────────

server.tool(
  "gen_get_cell",
  "Get the value and metadata of a specific cell",
  {
    engine_id: z.string().describe("The engine ID"),
    cell_id: z.string().describe("The cell ID to retrieve"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
  },
  async ({ engine_id, cell_id, agent_id }) => {
    const data = await apiCall("GET", `/autocontentengine/${engine_id}/cells/${cell_id}?agent_id=${agent_id}`);
    return jsonResult(data);
  }
);

server.tool(
  "gen_update_cell",
  "Update the value of a specific cell",
  {
    engine_id: z.string().describe("The engine ID"),
    cell_id: z.string().describe("The cell ID to update"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
    value: z.string().describe("The new cell value"),
  },
  async ({ engine_id, cell_id, agent_id, value }) => {
    const data = await apiCall("PATCH", `/autocontentengine/${engine_id}/cells/${cell_id}`, { agent_id, value });
    return jsonResult(data);
  }
);

// ── Generation tools ─────────────────────────────────────────────────────────

server.tool(
  "gen_generate_content",
  "Trigger content generation for a cell (e.g. script, image, video)",
  {
    engine_id: z.string().describe("The engine ID"),
    cell_id: z.string().describe("The cell ID to generate content for"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
    generation_type: z.string().describe("Type of generation (e.g. 'script', 'image', 'video')"),
    data: z.record(z.string(), z.unknown()).optional().describe("Additional generation parameters"),
  },
  async ({ engine_id, cell_id, agent_id, generation_type, data: extraData }) => {
    const body: Record<string, unknown> = { agent_id, generation_type };
    if (extraData) body.data = extraData;
    const result = await apiCall("POST", `/autocontentengine/${engine_id}/cells/${cell_id}/generate`, body);
    return jsonResult(result);
  }
);

server.tool(
  "gen_generate_layer",
  "Trigger generation for a specific layer within a cell",
  {
    engine_id: z.string().describe("The engine ID"),
    cell_id: z.string().describe("The cell ID"),
    layer_id: z.string().describe("The layer ID to generate"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
  },
  async ({ engine_id, cell_id, layer_id, agent_id }) => {
    const data = await apiCall(
      "POST",
      `/autocontentengine/${engine_id}/cells/${cell_id}/layers/${layer_id}/generate`,
      { agent_id }
    );
    return jsonResult(data);
  }
);

server.tool(
  "gen_get_generation",
  "Get the status and result of a generation job",
  {
    generation_id: z.string().describe("The generation ID to check"),
  },
  async ({ generation_id }) => {
    const data = await apiCall("GET", `/generations/${generation_id}`);
    return jsonResult(data);
  }
);

server.tool(
  "gen_stop_generation",
  "Stop a running generation job",
  {
    generation_id: z.string().describe("The generation ID to stop"),
  },
  async ({ generation_id }) => {
    const data = await apiCall("POST", `/generations/${generation_id}/stop`);
    return jsonResult(data);
  }
);

// ── Layer tools ──────────────────────────────────────────────────────────────

server.tool(
  "gen_create_layer",
  "Create a new layer in a cell",
  {
    engine_id: z.string().describe("The engine ID"),
    cell_id: z.string().describe("The cell ID to add the layer to"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
    name: z.string().describe("Name of the layer"),
    type: z.string().describe("Type of the layer"),
    position: z.number().optional().describe("Position of the layer (0-indexed)"),
  },
  async ({ engine_id, cell_id, agent_id, name, type, position }) => {
    const body: Record<string, unknown> = { agent_id, name, type };
    if (position !== undefined) body.position = position;
    const data = await apiCall("POST", `/autocontentengine/${engine_id}/cells/${cell_id}/layers`, body);
    return jsonResult(data);
  }
);

server.tool(
  "gen_delete_layer",
  "Delete a layer from a cell",
  {
    engine_id: z.string().describe("The engine ID"),
    cell_id: z.string().describe("The cell ID"),
    layer_id: z.string().describe("The layer ID to delete"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
  },
  async ({ engine_id, cell_id, layer_id, agent_id }) => {
    const data = await apiCall(
      "DELETE",
      `/autocontentengine/${engine_id}/cells/${cell_id}/layers/${layer_id}?agent_id=${agent_id}`
    );
    return jsonResult(data);
  }
);

// ── Column tools ─────────────────────────────────────────────────────────────

server.tool(
  "gen_list_columns",
  "List all columns in an Auto Content Engine",
  {
    engine_id: z.string().describe("The engine ID"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
  },
  async ({ engine_id, agent_id }) => {
    const data = await apiCall("GET", `/autocontentengine/${engine_id}/columns?agent_id=${agent_id}`);
    return jsonResult(data);
  }
);

server.tool(
  "gen_create_column",
  "Create a new column in an Auto Content Engine",
  {
    engine_id: z.string().describe("The engine ID"),
    agent_id: z.string().describe("The agent ID that owns the engine"),
    title: z.string().describe("Column title"),
    type: z.string().describe("Column type"),
    position: z.number().optional().describe("Column position (0-indexed)"),
  },
  async ({ engine_id, agent_id, title, type, position }) => {
    const body: Record<string, unknown> = { agent_id, title, type };
    if (position !== undefined) body.position = position;
    const data = await apiCall("POST", `/autocontentengine/${engine_id}/columns`, body);
    return jsonResult(data);
  }
);

// ── Start server ─────────────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
