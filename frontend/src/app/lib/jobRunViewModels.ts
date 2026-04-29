import type { ResourceRecord, RunRecord } from "./controlCenterApi";

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

function mapType(resource: ResourceRecord): UserJobViewModel["type"] {
  if (resource.type === "sql") return "SQL Query";
  if (resource.type === "excel") return "Excel Report";
  if (resource.type === "powerpoint") return "PowerPoint Deck";
  if (resource.type === "mcp" || resource.type === "research") return "MCP Job";
  if (resource.connector === "internal") return "API Connection";
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

export function buildUserJobs(resources: ResourceRecord[], runs: RunRecord[]): UserJobViewModel[] {
  return resources
    .map((resource) => {
      const latestRun = runs
        .filter((run) => run.resource_id === resource.id)
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];

      const detailParts = [resource.config?.description, resource.config?.brief]
        .filter(Boolean)
        .map((value) => String(value));
      if (resource.type === "sql" && resource.config?.query) {
        detailParts.push("Runs a configured SQL query.");
      }
      if ((resource.type === "mcp" || resource.type === "research") && resource.connector) {
        detailParts.push(`Uses MCP server ${resource.connector}.`);
      }

      return {
        id: resource.id,
        name: resource.name,
        type: mapType(resource),
        status: mapStatus(latestRun?.status ?? resource.last_run_status),
        createdAt: resource.created_at,
        environment: resource.environment,
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
            status: resource.connector ? "passed" : "warning",
            message: resource.connector
              ? `Running through MCP server ${resource.connector}.`
              : "This job is missing an MCP server association.",
          },
        ],
      } satisfies UserJobViewModel;
    })
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function buildRunningJobs(resources: ResourceRecord[], runs: RunRecord[]) {
  const activeStatuses = new Set(["queued", "executing", "running"]);
  const activeRuns = runs.filter((run) => activeStatuses.has(run.status.toLowerCase()));

  return activeRuns
    .map((run) => {
      const resource = resources.find((item) => item.id === run.resource_id);
      return {
        id: run.id,
        name: resource?.name ?? run.resource_id,
        type: resource ? mapType(resource) : "AI Agent",
        status: "running" as const,
        createdAt: run.created_at,
        environment: run.target_environment,
        description:
          resource?.config?.description?.toString() ??
          resource?.config?.brief?.toString() ??
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
