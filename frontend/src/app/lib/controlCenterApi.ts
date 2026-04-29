import type { components } from "../../../../generated/types/api-types";

type ResourceOutBase = components["schemas"]["ResourceOut"];
type ResourceCreateBase = components["schemas"]["ResourceCreate"];
type RunOutBase = components["schemas"]["RunOut"];

export type ResourceRecord = ResourceOutBase & {
  kind: "runtime" | "artifact";
  tags: string[];
};

export type RunRecord = RunOutBase & {
  trigger_source?: string | null;
  execution_backend?: string | null;
  execution_mode?: string | null;
  submitted_config_json?: Record<string, unknown> | null;
  resolved_job_spec_json?: Record<string, unknown> | null;
};

export type ResourceCreatePayload = ResourceCreateBase & {
  kind: "runtime" | "artifact";
  config: Record<string, unknown>;
  tags: string[];
};

export interface RunCreatePayload {
  action: string;
  target_environment: string;
  params: Record<string, unknown>;
  job_config?: {
    intent?: string | null;
    schedule?: string | null;
    tasks?: string[];
    metadata?: Record<string, unknown>;
  };
  mcp_config?: {
    server_names?: string[];
    tool_name?: string | null;
    tool_arguments?: Record<string, unknown>;
    prompt?: string | null;
    connector_selection_prompt?: string | null;
    allow_auto_selection?: boolean;
  };
}

export interface ResourceListResponse {
  items: ResourceRecord[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface RunListResponse {
  items: RunRecord[];
  next_cursor?: string | null;
}

export interface OpenAIChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface OpenAIChatRequest {
  messages: OpenAIChatMessage[];
  goal?: string;
  workflow_state?: Record<string, unknown>;
  fallback_response?: string;
}

export interface OpenAIChatResponse {
  content: string;
  model: string;
  response_id?: string | null;
}

export interface MCPServerSummary {
  name: string;
  display_name?: string | null;
  description?: string | null;
  tags: string[];
  allowed_environments: string[];
  active: boolean;
}

export interface MCPServerListResponse {
  items: MCPServerSummary[];
}

export interface MCPConnectionBundleSummary {
  id: string;
  title: string;
  summary: string;
  primary_server: string;
  server_names: string[];
  companion_servers: string[];
  manual_connection_supported: boolean;
  chat_connection_supported: boolean;
  resource_type: string;
  required_config_fields: string[];
  optional_config_fields: string[];
  recommended_use_cases: string[];
}

export interface MCPConnectionBundleListResponse {
  items: MCPConnectionBundleSummary[];
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";
const AUTH_TOKEN_KEY = "control-center-auth-token";

function getStoredAuthToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}, token?: string | null): Promise<T> {
  const effectiveToken = token ?? getStoredAuthToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(effectiveToken ? { Authorization: `Bearer ${effectiveToken}` } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listResources(token?: string | null) {
  return request<ResourceListResponse>("/resources?page=1&page_size=200", {}, token);
}

export function createResource(payload: ResourceCreatePayload, token?: string | null) {
  return request<ResourceRecord>(
    "/resources",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function listRuns(token?: string | null) {
  return request<RunListResponse>("/runs?limit=200", {}, token);
}

export function createResourceRun(resourceId: string, payload: RunCreatePayload, token?: string | null) {
  return request<RunRecord>(
    `/resources/${resourceId}/runs`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function requestOpenAIChat(payload: OpenAIChatRequest, token?: string | null) {
  return request<OpenAIChatResponse>(
    "/integrations/openai/chat",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function listMcpServers(token?: string | null) {
  return request<MCPServerListResponse>("/integrations/mcp/servers", {}, token);
}

export function listMcpRepoBundles(environment = "dev", token?: string | null) {
  const query = new URLSearchParams({ environment });
  return request<MCPConnectionBundleListResponse>(`/integrations/mcp/repo-bundles?${query.toString()}`, {}, token);
}

export interface RunLogEntry {
  run_id: string;
  timestamp: string;
  level: string;
  message: string;
  metadata: Record<string, unknown>;
}

export interface RunLogsResponse {
  run_id: string;
  status: string;
  logs: RunLogEntry[];
  next_cursor?: string | null;
}

export function getRunLogs(runId: string, token?: string | null) {
  return request<RunLogsResponse>(`/runs/${runId}/logs?limit=500`, {}, token);
}
