import { createContext, ReactNode, useContext, useEffect, useMemo, useRef, useState } from "react";

import {
  createResource,
  createResourceRun,
  listResources,
  listRuns,
  type ResourceCreatePayload,
  type ResourceRecord,
  type RunCreatePayload,
  type RunRecord,
} from "../lib/controlCenterApi";

const JOB_RUN_CACHE_KEY = "control-center-job-run-cache";
const AUTH_TOKEN_KEY = "control-center-auth-token";

type ChatJobType = "sql" | "excel" | "powerpoint" | "mcp";

export interface ChatJobDraft {
  name: string;
  jobType: ChatJobType;
  environment: "dev" | "semi-prod" | "prod";
  oneTime: boolean;
  description: string;
  topic?: string;
  query?: string;
  schedule?: string;
  mcpServer?: string;
  mcpPrompt?: string;
  mcpToolName?: string;
  mcpToolArguments?: Record<string, unknown>;
  maxResults?: number;
}

interface LocalCacheShape {
  resources: ResourceRecord[];
  runs: RunRecord[];
}

interface JobRunContextType {
  resources: ResourceRecord[];
  runs: RunRecord[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  launchJobFromChat: (draft: ChatJobDraft) => Promise<{ resource: ResourceRecord; run: RunRecord }>;
}

const JobRunContext = createContext<JobRunContextType | undefined>(undefined);

function getAuthToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_KEY) ?? "u_analyst";
}

function readCache(): LocalCacheShape {
  if (typeof window === "undefined") {
    return { resources: [], runs: [] };
  }

  const raw = window.localStorage.getItem(JOB_RUN_CACHE_KEY);
  if (!raw) {
    return { resources: [], runs: [] };
  }

  try {
    return JSON.parse(raw) as LocalCacheShape;
  } catch {
    return { resources: [], runs: [] };
  }
}

function writeCache(cache: LocalCacheShape) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(JOB_RUN_CACHE_KEY, JSON.stringify(cache));
}

function dedupeById<T extends { id: string }>(items: T[]) {
  const map = new Map<string, T>();
  items.forEach((item) => map.set(item.id, item));
  return Array.from(map.values());
}

function localOnly<T extends { id: string }>(items: T[]) {
  return items.filter((item) => item.id.startsWith("local-"));
}

function toIsoNow() {
  return new Date().toISOString();
}

function normalizeOptionalSchedule(schedule?: string) {
  const trimmed = schedule?.trim();
  if (!trimmed) {
    return null;
  }

  const lowered = trimmed.toLowerCase();
  if (["i don't know", "idk", "not sure", "unknown", "tbd", "n/a", "none", "no schedule"].includes(lowered)) {
    return null;
  }

  return trimmed;
}

function normalizeDraftToResource(draft: ChatJobDraft): ResourceCreatePayload {
  const tags = ["chat-created", draft.oneTime ? "one-time" : "saved-job"];
  const normalizedSchedule = draft.oneTime ? null : normalizeOptionalSchedule(draft.schedule);

  if (draft.jobType === "sql") {
    if (!draft.mcpServer) {
      throw new Error("Choose a database source before launching this SQL job.");
    }
    return {
      name: draft.name,
      kind: "runtime",
      type: "sql",
      connector: draft.mcpServer,
      environment: draft.environment,
      config: {
        connection_id: draft.mcpServer,
        query: draft.query ?? "",
        schedule: normalizedSchedule,
      },
      data_sensitivity: "low",
      tags: [...tags, "sql-mcp"],
    };
  }

  if (draft.jobType === "excel") {
    return {
      name: draft.name,
      kind: "runtime",
      type: "excel",
      connector: draft.mcpServer ?? "filesystem",
      environment: draft.environment,
      config: {
        brief: draft.description,
        connection_id: draft.mcpServer ?? "filesystem",
        schedule: normalizedSchedule,
      },
      data_sensitivity: "low",
      tags,
    };
  }

  if (draft.jobType === "powerpoint") {
    return {
      name: draft.name,
      kind: "runtime",
      type: "powerpoint",
      connector: draft.mcpServer ?? "filesystem",
      environment: draft.environment,
      config: {
        brief: draft.description,
        connection_id: draft.mcpServer ?? "filesystem",
        schedule: normalizedSchedule,
      },
      data_sensitivity: "low",
      tags,
    };
  }

  return {
    name: draft.name,
    kind: "runtime",
    type: draft.mcpServer === "arxiv-research" ? "research" : "mcp",
    connector: draft.mcpServer ?? "fetch",
    environment: draft.environment,
    config:
      draft.mcpServer === "arxiv-research"
        ? {
            topic: draft.topic ?? draft.mcpPrompt ?? draft.description,
            schedule: normalizedSchedule,
            max_results: draft.maxResults ?? 5,
          }
        : {
            prompt: draft.mcpPrompt ?? draft.description,
            description: draft.description,
            schedule: normalizedSchedule,
            max_results: draft.maxResults ?? 5,
          },
    data_sensitivity: "low",
    tags,
  };
}

function normalizeDraftToRun(draft: ChatJobDraft): RunCreatePayload {
  const normalizedSchedule = draft.oneTime ? null : normalizeOptionalSchedule(draft.schedule);
  if (draft.jobType === "sql") {
    if (!draft.mcpServer) {
      throw new Error("Choose a database source before launching this SQL job.");
    }
    return {
      action: "run",
      target_environment: draft.environment,
      params: {
        prompt: draft.query?.trim() ? draft.query : draft.description,
        query: draft.query ?? "",
      },
      job_config: {
        intent: draft.description,
        schedule: normalizedSchedule,
        metadata: {
          created_via: "chatbot",
          one_time: draft.oneTime,
          job_type: "sql",
        },
      },
      mcp_config: {
        server_names: [draft.mcpServer],
        prompt: draft.query?.trim() ? draft.query : draft.description,
        allow_auto_selection: true,
      },
    };
  }

  if (draft.jobType === "mcp") {
    return {
      action: "run",
      target_environment: draft.environment,
      params: {
        prompt: draft.mcpPrompt ?? draft.description,
        ...(draft.mcpServer === "arxiv-research"
          ? {
              topic: draft.topic ?? draft.mcpPrompt ?? draft.description,
            }
          : {}),
        max_results: draft.maxResults ?? 5,
      },
      job_config: {
        intent: draft.description,
        schedule: normalizedSchedule,
        tasks: draft.mcpToolName ? [draft.mcpToolName] : [],
        metadata: {
          created_via: "chatbot",
          one_time: draft.oneTime,
        },
      },
      mcp_config: {
        server_names: draft.mcpServer ? [draft.mcpServer] : [],
        tool_name: draft.mcpToolName ?? null,
        tool_arguments: draft.mcpToolArguments ?? {},
        prompt: draft.mcpPrompt ?? draft.description,
        allow_auto_selection: !draft.mcpToolName,
      },
    };
  }

  return {
    action: "run",
    target_environment: draft.environment,
    params: {
      brief: draft.description,
      prompt: draft.description,
    },
    job_config: {
      intent: draft.description,
      schedule: normalizedSchedule,
      metadata: {
        created_via: "chatbot",
        one_time: draft.oneTime,
        job_type: draft.jobType,
      },
    },
    mcp_config: {
      server_names: draft.mcpServer ? [draft.mcpServer] : [],
      prompt: draft.description,
      allow_auto_selection: true,
    },
  };
}

export function JobRunProvider({ children }: { children: ReactNode }) {
  const initialCache = useMemo(() => readCache(), []);
  const [resources, setResources] = useState<ResourceRecord[]>(initialCache.resources);
  const [runs, setRuns] = useState<RunRecord[]>(initialCache.runs);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activePollRef = useRef<number | null>(null);

  const syncFromApi = async () => {
    const token = getAuthToken();
    const [resourcesResponse, runsResponse] = await Promise.all([listResources(token), listRuns(token)]);
    const nextResources = dedupeById([...localOnly(resources), ...resourcesResponse.items]);
    const nextRuns = dedupeById([...localOnly(runs), ...runsResponse.items]).sort((a, b) =>
      b.updated_at.localeCompare(a.updated_at),
    );

    setResources(nextResources);
    setRuns(nextRuns);
    writeCache({ resources: nextResources, runs: nextRuns });
  };

  const refresh = async () => {
    setLoading(true);
    try {
      await syncFromApi();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh jobs and runs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    writeCache({ resources, runs });
  }, [resources, runs]);

  useEffect(() => {
    const hasActiveRuns = runs.some((run) => ["queued", "executing", "running"].includes(run.status));
    if (!hasActiveRuns) {
      if (activePollRef.current) {
        window.clearInterval(activePollRef.current);
        activePollRef.current = null;
      }
      return;
    }

    if (activePollRef.current) {
      return;
    }

    activePollRef.current = window.setInterval(() => {
      void syncFromApi().catch(() => undefined);
    }, 8000);

    return () => {
      if (activePollRef.current) {
        window.clearInterval(activePollRef.current);
        activePollRef.current = null;
      }
    };
  }, [runs, resources]);

  const launchJobFromChat = async (draft: ChatJobDraft) => {
    const token = getAuthToken();
    const resourcePayload = normalizeDraftToResource(draft);
    const runPayload = normalizeDraftToRun(draft);

    const optimisticResource: ResourceRecord = {
      id: `local-resource-${Date.now()}`,
      name: draft.name,
      kind: "runtime",
      type: resourcePayload.type,
      connector: resourcePayload.connector,
      owner_id: "current-user",
      owner_domain: "collections",
      environment: draft.environment,
      status: "active",
      data_sensitivity: "low",
      config: resourcePayload.config,
      tags: resourcePayload.tags,
      created_at: toIsoNow(),
      updated_at: toIsoNow(),
      last_run_at: null,
      last_run_status: null,
    };

    setResources((current) => dedupeById([optimisticResource, ...current]));

    try {
      const resource = await createResource(resourcePayload, token);
      const run = await createResourceRun(resource.id, runPayload, token);

      setResources((current) =>
        dedupeById([
          {
            ...resource,
            last_run_at: run.updated_at,
            last_run_status: run.status,
          },
          ...current.filter((item) => item.id !== optimisticResource.id),
        ]),
      );
      setRuns((current) => dedupeById([run, ...current]).sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
      setError(null);

      return { resource, run };
    } catch (err) {
      const failedRun: RunRecord = {
        id: `local-run-${Date.now()}`,
        resource_id: optimisticResource.id,
        requested_by: "current-user",
        domain: "collections",
        action: "run",
        target_environment: draft.environment,
        status: "failed",
        risk_level: "unknown",
        risk_score: 0,
        requires_approval: false,
        error: err instanceof Error ? err.message : "Unable to start run.",
        trigger_source: "ui",
        execution_backend: "mcp",
        execution_mode: draft.jobType === "mcp" && draft.mcpToolName ? "direct_tool" : "agent",
        submitted_config_json: {
          draft,
        },
        resolved_job_spec_json: null,
        created_at: toIsoNow(),
        updated_at: toIsoNow(),
      };

      setRuns((current) => dedupeById([failedRun, ...current]));
      setError(failedRun.error ?? "Unable to start run.");
      throw err;
    }
  };

  return (
    <JobRunContext.Provider
      value={{
        resources,
        runs,
        loading,
        error,
        refresh,
        launchJobFromChat,
      }}
    >
      {children}
    </JobRunContext.Provider>
  );
}

export function useJobRuns() {
  const context = useContext(JobRunContext);
  if (!context) {
    throw new Error("useJobRuns must be used within a JobRunProvider");
  }
  return context;
}
