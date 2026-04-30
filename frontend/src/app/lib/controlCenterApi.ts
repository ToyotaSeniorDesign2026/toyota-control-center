import type { components } from "../../../../generated/types/api-types";

type JobOutBase = components["schemas"]["ResourceOut"];
type JobCreateBase = components["schemas"]["ResourceCreate"];
type RunOutBase = components["schemas"]["RunOut"];

export type JobRecord = JobOutBase & {
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

export type JobCreatePayload = JobCreateBase & {
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

export interface JobListResponse {
  items: JobRecord[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface RunListResponse {
  items: RunRecord[];
  next_cursor?: string | null;
}

export interface ConnectorRecord {
  id: string;
  name: string;
  connector_type: string;
  owner_id: string;
  owner_domain: string;
  environment: string;
  status: string;
  config: Record<string, unknown>;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConnectorListResponse {
  items: ConnectorRecord[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface ConnectorCreatePayload {
  name: string;
  connector_type: string;
  environment: string;
  config: Record<string, unknown>;
  is_shared: boolean;
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

export interface UserRecord {
  id: string;
  email: string;
  name?: string;
  domain: string;
  role: string;
  active?: boolean;
  is_active?: boolean;
}

export interface PolicyCheckResult {
  id: string;
  evaluation_id: string;
  check_name: string;
  category: string;
  result: string;
  reason: string;
  severity: string;
  weight: number;
  threshold?: string | null;
  actual_value?: string | null;
}

export interface PolicyEvaluation {
  evaluation_id: string;
  run_id: string;
  policy_version: string;
  overall_status: string;
  risk_score: number;
  risk_level: string;
  requires_approval: boolean;
  evaluated_at: string;
  checks: PolicyCheckResult[];
}

export interface ApprovalRecord {
  id: string;
  run_id: string;
  status: string;
  requested_by: string;
  reviewer_id?: string | null;
  risk_level: string;
  comment?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface AuditEventRecord {
  id: string;
  actor_id?: string | null;
  action: string;
  metadata: Record<string, unknown>;
  created_at: string;
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

  const responseText = await response.text();

  if (!response.ok) {
    let message = responseText;
    if (responseText) {
      try {
        const errorBody = JSON.parse(responseText) as { detail?: unknown; message?: unknown };
        const detail = errorBody.detail ?? errorBody.message;
        if (typeof detail === "string") {
          message = detail;
        } else if (detail) {
          message = JSON.stringify(detail);
        }
      } catch {
        // Keep the raw response text for non-JSON error bodies.
      }
    }
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  if (response.status === 204 || !responseText) {
    return undefined as T;
  }

  return JSON.parse(responseText) as T;
}

export function listJobs(token?: string | null) {
  return request<JobListResponse>("/jobs?page=1&page_size=200", {}, token);
}

export function createJob(payload: JobCreatePayload, token?: string | null) {
  return request<JobRecord>(
    "/jobs",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function deleteJob(jobId: string, token?: string | null) {
  return request<void>(`/jobs/${jobId}`, { method: "DELETE" }, token);
}

export function listRuns(token?: string | null) {
  return request<RunListResponse>("/runs?limit=200", {}, token);
}

export function createJobRun(jobId: string, payload: RunCreatePayload, token?: string | null) {
  return request<RunRecord>(
    `/jobs/${jobId}/runs`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function listConnectors(token?: string | null) {
  return request<ConnectorListResponse>("/connectors?page=1&page_size=200", {}, token);
}

export function createConnector(payload: ConnectorCreatePayload, token?: string | null) {
  return request<ConnectorRecord>(
    "/connectors",
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

export function getCurrentUser(token?: string | null) {
  return request<UserRecord>("/auth/me", {}, token);
}

export function updateCurrentUser(payload: { name?: string; email?: string }, token?: string | null) {
  return request<UserRecord>(
    "/auth/me",
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export function getPolicyChecks(runId: string, token?: string | null) {
  return request<PolicyEvaluation | null>(`/policy/runs/${runId}/checks`, {}, token);
}

export function listApprovals(status?: string, token?: string | null) {
  const query = new URLSearchParams();
  query.set("limit", "200");
  if (status) {
    query.set("status", status);
  }
  return request<ApprovalRecord[]>(`/policy/approvals?${query.toString()}`, {}, token);
}

export function approveApproval(approvalId: string, token?: string | null) {
  return request<ApprovalRecord>(`/policy/approvals/${approvalId}/approve`, { method: "POST" }, token);
}

export function rejectApproval(approvalId: string, comment?: string, token?: string | null) {
  return request<ApprovalRecord>(
    `/policy/approvals/${approvalId}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ comment }),
    },
    token,
  );
}

export function listAuditEvents(limit = 200, token?: string | null) {
  return request<AuditEventRecord[]>(`/audit/events?limit=${limit}`, {}, token);
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

export interface AgentChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AgentChatRequest {
  message: string;
  conversation_history?: AgentChatMessage[];
  model?: string;
}

export interface AgentChatResponse {
  response: string;
}

export function sendAgentMessage(payload: AgentChatRequest, token?: string | null) {
  return request<AgentChatResponse>(
    "/api/chat/agent",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}
