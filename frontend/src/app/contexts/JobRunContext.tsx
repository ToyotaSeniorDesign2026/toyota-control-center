import { createContext, ReactNode, useContext, useEffect, useMemo, useRef, useState } from "react";

import {
  createJob,
  createJobRun,
  listJobs,
  listRuns,
  type JobCreatePayload,
  type JobRecord,
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
  jobs: JobRecord[];
  runs: RunRecord[];
}

interface JobRunContextType {
  jobs: JobRecord[];
  runs: RunRecord[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  launchJobFromChat: (draft: ChatJobDraft) => Promise<{ job: JobRecord; run: RunRecord }>;
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
    return { jobs: [], runs: [] };
  }

  const raw = window.localStorage.getItem(JOB_RUN_CACHE_KEY);
  if (!raw) {
    return { jobs: [], runs: [] };
  }

  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    // Handle migration from old cache shape that used "resources" key
    const jobs = (parsed.jobs ?? parsed.resources ?? []) as JobRecord[];
    const runs = (parsed.runs ?? []) as RunRecord[];
    return { jobs, runs };
  } catch {
    return { jobs: [], runs: [] };
  }
}

function writeCache(cache: LocalCacheShape) {
  if (typeof window === "undefined") {
    return;
  }
  const persistedCache: LocalCacheShape = {
    jobs: cache.jobs.filter((job) => !job.id.startsWith("local-")),
    runs: cache.runs.filter((run) => !run.id.startsWith("local-")),
  };
  window.localStorage.setItem(JOB_RUN_CACHE_KEY, JSON.stringify(persistedCache));
}

function dedupeById<T extends { id: string }>(items: T[]) {
  const map = new Map<string, T>();
  items.forEach((item) => map.set(item.id, item));
  return Array.from(map.values());
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

function normalizeDraftToJob(draft: ChatJobDraft): JobCreatePayload {
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
  const [jobs, setJobs] = useState<JobRecord[]>(initialCache.jobs);
  const [runs, setRuns] = useState<RunRecord[]>(initialCache.runs);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activePollRef = useRef<number | null>(null);

  const syncFromApi = async () => {
    const token = getAuthToken();
    const [jobsResponse, runsResponse] = await Promise.all([listJobs(token), listRuns(token)]);
    const nextJobs = dedupeById(jobsResponse.items);
    const nextRuns = dedupeById(runsResponse.items).sort((a, b) => b.updated_at.localeCompare(a.updated_at));

    setJobs(nextJobs);
    setRuns(nextRuns);
    writeCache({ jobs: nextJobs, runs: nextRuns });
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
    writeCache({ jobs, runs });
  }, [jobs, runs]);

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
  }, [runs, jobs]);

  const launchJobFromChat = async (draft: ChatJobDraft) => {
    const token = getAuthToken();
    const jobPayload = normalizeDraftToJob(draft);
    const runPayload = normalizeDraftToRun(draft);

    const optimisticJob: JobRecord = {
      id: `local-job-${Date.now()}`,
      name: draft.name,
      kind: "runtime",
      type: jobPayload.type,
      connector: jobPayload.connector,
      owner_id: "current-user",
      owner_domain: "collections",
      environment: draft.environment,
      status: "active",
      data_sensitivity: "low",
      config: jobPayload.config,
      tags: jobPayload.tags,
      created_at: toIsoNow(),
      updated_at: toIsoNow(),
      last_run_at: null,
      last_run_status: null,
    };

    setJobs((current) => dedupeById([optimisticJob, ...current]));

    try {
      const job = await createJob(jobPayload, token);
      const run = await createJobRun(job.id, runPayload, token);

      setJobs((current) =>
        dedupeById([
          {
            ...job,
            last_run_at: run.updated_at,
            last_run_status: run.status,
          },
          ...current.filter((item) => item.id !== optimisticJob.id),
        ]),
      );
      setRuns((current) => dedupeById([run, ...current]).sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
      setError(null);

      return { job, run };
    } catch (err) {
      const failedRun: RunRecord = {
        id: `local-run-${Date.now()}`,
        job_id: optimisticJob.id,
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
        jobs,
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
