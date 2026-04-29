import type { JobRecord, RunRecord } from "./controlCenterApi";

export interface UserJobViewModel {
  id: string;
  name: string;
  type: "AI Agent" | "SQL Query" | "dbt Model" | "API Connection" | "Excel Report" | "PowerPoint Deck" | "MCP Job";
  status: "pending" | "approved" | "running" | "completed" | "failed";
  createdAt: string;
  environment?: string;
  description?: string;
  logs?: Array<{ timestamp: string; message: string; level: "info" | "warning" | "error" }>;
  policyChecks?: Array<{ name: string; status: "passed" | "failed" | "warning"; message: string }>;
}

function mapType(job: JobRecord): UserJobViewModel["type"] {
  if (job.type === "sql") return "SQL Query";
  if (job.type === "excel") return "Excel Report";
  if (job.type === "powerpoint") return "PowerPoint Deck";
  if (job.type === "mcp" || job.type === "research") return "MCP Job";
  if (job.connector === "internal") return "API Connection";
  return "AI Agent";
}

function mapStatus(status: string | null | undefined): UserJobViewModel["status"] {
  switch ((status ?? "").toLowerCase()) {
    case "queued":
    case "executing":
      return "pending";
    case "running":
      return "running";
    case "succeeded":
    case "deployed":
      return "completed";
    case "failed":
    case "stopped":
      return "failed";
    default:
      return "approved";
  }
}

export function buildUserJobs(jobs: JobRecord[], runs: RunRecord[]): UserJobViewModel[] {
  return jobs
    .map((job) => {
      const latestRun = runs
        .filter((run) => run.job_id === job.id)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];

      const detailParts = [job.config?.description, job.config?.brief]
        .filter(Boolean)
        .map((value) => String(value));
      if (job.type === "sql" && job.config?.query) {
        detailParts.push("Runs a configured SQL query.");
      }
      if ((job.type === "mcp" || job.type === "research") && job.connector) {
        detailParts.push(`Uses MCP server ${job.connector}.`);
      }

      return {
        id: job.id,
        name: job.name,
        type: mapType(job),
        status: mapStatus(latestRun?.status ?? job.last_run_status),
        createdAt: job.created_at,
        environment: job.environment,
        description: detailParts.join(" "),
        logs: latestRun
          ? [
              {
                timestamp: latestRun.updated_at,
                message: latestRun.error ?? `Latest run status: ${latestRun.status}`,
                level: latestRun.error ? "error" : "info",
              },
            ]
          : [],
        policyChecks: [
          {
            name: "MCP Association",
            status: job.connector ? "passed" : "warning",
            message: job.connector
              ? `Running through MCP server ${job.connector}.`
              : "This job is missing an MCP server association.",
          },
        ],
      } satisfies UserJobViewModel;
    })
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function buildRunningJobs(jobs: JobRecord[], runs: RunRecord[]) {
  const activeStatuses = new Set(["queued", "executing", "running"]);
  const activeRuns = runs.filter((run) => activeStatuses.has(run.status.toLowerCase()));

  return activeRuns
    .map((run) => {
      const job = jobs.find((item) => item.id === run.job_id);
      return {
        id: run.id,
        name: job?.name ?? run.job_id,
        type: job ? mapType(job) : "AI Agent",
        status: "running" as const,
        createdAt: run.created_at,
        environment: run.target_environment,
        description:
          job?.config?.description?.toString() ??
          job?.config?.brief?.toString() ??
          `Active run ${run.id}`,
        logs: [
          {
            timestamp: run.updated_at,
            message: `Run is currently ${run.status}.`,
            level: "info" as const,
          },
        ],
      };
    })
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}
