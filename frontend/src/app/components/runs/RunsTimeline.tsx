import { Run } from "../../pages/Runs";
import {
  Bot,
  Database,
  BarChart3,
  Code,
  FileSpreadsheet,
  Presentation,
  Workflow,
  CheckCircle2,
  XCircle,
  Circle,
  Loader2,
  PackageX,
  Play,
} from "lucide-react";

interface RunsTimelineProps {
  searchQuery: string;
  statusFilter: string;
  typeFilter: string;
  environmentFilter: string;
  onRunClick: (run: Run) => void;
}

const mockRuns: Run[] = [
  {
    id: "run-a7f3d2",
    jobName: "customer_churn_predictor",
    type: "AI Agent",
    environment: "Prod",
    startedAt: "2 min ago",
    duration: "3m 24s",
    status: "succeeded",
    riskScore: 12,
    triggeredBy: "Schedule",
  },
  {
    id: "run-9c2e1d",
    jobName: "dbt_daily_model",
    type: "dbt",
    environment: "Semi-Prod",
    startedAt: "5 min ago",
    duration: "Running...",
    status: "running",
    riskScore: 45,
    triggeredBy: "User",
    triggerUser: "Mike Johnson",
  },
  {
    id: "run-4b8f3a",
    jobName: "revenue_dashboard",
    type: "BI",
    environment: "Prod",
    startedAt: "15 min ago",
    duration: "1m 08s",
    status: "succeeded",
    riskScore: 8,
    triggeredBy: "Schedule",
  },
  {
    id: "run-7e3b9f",
    jobName: "airflow_etl_pipeline",
    type: "Airflow",
    environment: "Prod",
    startedAt: "28 min ago",
    duration: "12m 45s",
    status: "failed",
    riskScore: 78,
    triggeredBy: "CLI",
    triggerUser: "David Park",
  },
  {
    id: "run-2d5c8a",
    jobName: "sales_forecast_query",
    type: "SQL",
    environment: "Prod",
    startedAt: "1 hour ago",
    duration: "0m 42s",
    status: "succeeded",
    riskScore: 18,
    triggeredBy: "Schedule",
  },
  {
    id: "run-6f1e4b",
    jobName: "inventory_optimizer",
    type: "AI Agent",
    environment: "Dev",
    startedAt: "2 hours ago",
    duration: "Cancelled",
    status: "cancelled",
    riskScore: 52,
    triggeredBy: "User",
    triggerUser: "Sarah Chen",
  },
  {
    id: "run-8a3c7d",
    jobName: "dbt_staging_models",
    type: "dbt",
    environment: "Dev",
    startedAt: "3 hours ago",
    duration: "8m 15s",
    status: "succeeded",
    riskScore: 10,
    triggeredBy: "Promotion",
  },
  {
    id: "run-5b9d2e",
    jobName: "quarterly_report_deck",
    type: "PowerPoint",
    environment: "Prod",
    startedAt: "5 hours ago",
    duration: "2m 30s",
    status: "succeeded",
    riskScore: 5,
    triggeredBy: "User",
    triggerUser: "Emily Davis",
  },
];

function getTypeIcon(type: Run["type"]) {
  switch (type) {
    case "AI Agent":
      return <Bot className="h-4 w-4" />;
    case "Airflow":
      return <Workflow className="h-4 w-4" />;
    case "dbt":
      return <Database className="h-4 w-4" />;
    case "SQL":
      return <Code className="h-4 w-4" />;
    case "BI":
      return <BarChart3 className="h-4 w-4" />;
    case "Excel":
      return <FileSpreadsheet className="h-4 w-4" />;
    case "PowerPoint":
      return <Presentation className="h-4 w-4" />;
  }
}

function getStatusIcon(status: Run["status"]) {
  switch (status) {
    case "running":
      return <Loader2 className="h-5 w-5 animate-spin text-blue-600" />;
    case "succeeded":
      return <CheckCircle2 className="h-5 w-5 text-green-600" />;
    case "failed":
      return <XCircle className="h-5 w-5 text-red-600" />;
    case "cancelled":
      return <Circle className="h-5 w-5 text-gray-400" />;
  }
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="flex flex-col items-center justify-center py-16">
        <div className="rounded-full bg-gray-100 p-4">
          <PackageX className="h-12 w-12 text-gray-400" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-gray-900">
          No runs yet.
        </h3>
        <p className="mt-2 text-sm text-gray-600">
          Run a job to begin tracking execution history.
        </p>
        <button className="mt-6 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Play className="h-4 w-4" />
          Run Job
        </button>
      </div>
    </div>
  );
}

export function RunsTimeline({
  searchQuery,
  statusFilter,
  typeFilter,
  environmentFilter,
  onRunClick,
}: RunsTimelineProps) {
  const filteredRuns = mockRuns.filter((run) => {
    if (
      searchQuery &&
      !run.jobName.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !run.id.toLowerCase().includes(searchQuery.toLowerCase())
    ) {
      return false;
    }

    if (statusFilter !== "All Status" && run.status !== statusFilter.toLowerCase()) {
      return false;
    }

    if (typeFilter !== "All Types" && run.type !== typeFilter) {
      return false;
    }

    if (environmentFilter !== "All Environments" && run.environment !== environmentFilter) {
      return false;
    }

    return true;
  });

  if (filteredRuns.length === 0 && searchQuery === "") {
    return <EmptyState />;
  }

  if (filteredRuns.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-12 text-center shadow-sm">
        <p className="text-gray-600">No runs match your filters.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <div className="relative space-y-6">
        {/* Vertical line */}
        <div className="absolute left-6 top-0 bottom-0 w-px bg-gray-200" />

        {filteredRuns.map((run, index) => (
          <div
            key={run.id}
            className="relative flex gap-6 cursor-pointer group"
            onClick={() => onRunClick(run)}
          >
            {/* Timestamp */}
            <div className="w-24 shrink-0 pt-1 text-right">
              <p className="text-sm font-medium text-gray-900">{run.startedAt}</p>
            </div>

            {/* Status Icon */}
            <div className="relative z-10 flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white border-2 border-gray-200 group-hover:border-blue-300 transition-colors">
              {getStatusIcon(run.status)}
            </div>

            {/* Content */}
            <div className="flex-1 pb-6">
              <div className="rounded-lg border border-gray-200 bg-white p-4 group-hover:border-gray-300 group-hover:shadow-md transition-all">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h4 className="font-semibold text-gray-900">
                        {run.jobName}
                      </h4>
                      <div className="flex items-center gap-1.5 text-gray-600">
                        {getTypeIcon(run.type)}
                        <span className="text-sm">{run.type}</span>
                      </div>
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                        {run.environment}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center gap-4 text-sm text-gray-600">
                      <span className="font-mono text-xs">{run.id}</span>
                      <span>•</span>
                      <span className="font-mono">{run.duration}</span>
                      <span>•</span>
                      <span>{run.triggeredBy}</span>
                      {run.triggerUser && (
                        <>
                          <span>by</span>
                          <span className="font-medium">{run.triggerUser}</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Risk Score */}
                  <div className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 rounded-full ${
                        run.riskScore < 30
                          ? "bg-green-500"
                          : run.riskScore < 60
                          ? "bg-yellow-500"
                          : "bg-red-500"
                      }`}
                    />
                    <span className="text-sm font-medium text-gray-700">
                      Risk: {run.riskScore}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
