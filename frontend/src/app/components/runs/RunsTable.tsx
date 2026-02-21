import { Run } from "../../pages/Runs";
import {
  MoreVertical,
  Play,
  FileText,
  Eye,
  X,
  Bot,
  Database,
  BarChart3,
  Code,
  FileSpreadsheet,
  Presentation,
  Workflow,
  PackageX,
  User,
  Clock,
  Terminal,
  ArrowUpCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Badge } from "../ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import React from "react";

interface RunsTableProps {
  searchQuery: string;
  statusFilter: string;
  typeFilter: string;
  environmentFilter: string;
  onRunClick: (run: Run) => void;
}

const mockRuns: Run[] = [
  {
    id: "run-a7f3d2",
    resourceName: "customer_churn_predictor",
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
    resourceName: "dbt_daily_model",
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
    resourceName: "revenue_dashboard",
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
    resourceName: "airflow_etl_pipeline",
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
    resourceName: "sales_forecast_query",
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
    resourceName: "inventory_optimizer",
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
    resourceName: "dbt_staging_models",
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
    resourceName: "quarterly_report_deck",
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

function StatusBadge({ status }: { status: Run["status"] }) {
  const variants = {
    running: "bg-red-50 text-[#b8071c] border-red-200",
    succeeded: "bg-green-50 text-green-700 border-green-200",
    failed: "bg-red-50 text-red-700 border-red-200",
    cancelled: "bg-gray-50 text-gray-700 border-gray-200",
  };

  const labels = {
    running: "Running",
    succeeded: "Succeeded",
    failed: "Failed",
    cancelled: "Cancelled",
  };

  return (
    <Badge variant="outline" className={`${variants[status]} border`}>
      {labels[status]}
    </Badge>
  );
}

function TriggerBadge({ trigger, user }: { trigger: Run["triggeredBy"]; user?: string }) {
  const getIcon = () => {
    switch (trigger) {
      case "User":
        return <User className="h-3 w-3" />;
      case "Schedule":
        return <Clock className="h-3 w-3" />;
      case "CLI":
        return <Terminal className="h-3 w-3" />;
      case "Promotion":
        return <ArrowUpCircle className="h-3 w-3" />;
    }
  };

  return (
    <div className="flex items-center gap-1.5 text-sm text-gray-600">
      {getIcon()}
      <span>{trigger}</span>
      {user && <span className="text-gray-400">· {user}</span>}
    </div>
  );
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
          Run a resource to begin tracking execution history.
        </p>
        <button className="mt-6 inline-flex items-center gap-2 rounded-md bg-[#ed0923] px-4 py-2 text-sm font-medium text-white hover:bg-[#b8071c]">
          <Play className="h-4 w-4" />
          Run Resource
        </button>
      </div>
    </div>
  );
}

export function RunsTable({
  searchQuery,
  statusFilter,
  typeFilter,
  environmentFilter,
  onRunClick,
}: RunsTableProps) {
  const [currentPage, setCurrentPage] = React.useState(1);
  const itemsPerPage = 5;

  const filteredRuns = mockRuns.filter((run) => {
    if (
      searchQuery &&
      !run.resourceName.toLowerCase().includes(searchQuery.toLowerCase()) &&
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

  const totalPages = Math.ceil(filteredRuns.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedRuns = filteredRuns.slice(startIndex, endIndex);

  // Reset to page 1 when filters change
  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, typeFilter, environmentFilter]);

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
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-200 hover:bg-transparent">
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Run ID
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Resource Name
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Type
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Environment
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Started At
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Duration
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Status
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Risk Score
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Triggered By
              </TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedRuns.map((run) => (
              <TableRow
                key={run.id}
                className="cursor-pointer border-gray-200 hover:bg-gray-50"
                onClick={() => onRunClick(run)}
              >
                <TableCell className="py-2 font-mono text-sm text-gray-900">
                  {run.id}
                </TableCell>
                <TableCell className="py-2 font-medium text-gray-900">
                  {run.resourceName}
                </TableCell>
                <TableCell className="py-2">
                  <div className="flex items-center gap-2 text-gray-700">
                    {getTypeIcon(run.type)}
                    <span className="text-sm">{run.type}</span>
                  </div>
                </TableCell>
                <TableCell className="py-2 text-gray-600">{run.environment}</TableCell>
                <TableCell className="py-2 text-gray-600">{run.startedAt}</TableCell>
                <TableCell className="py-2 font-mono text-sm text-gray-600">
                  {run.duration}
                </TableCell>
                <TableCell className="py-2">
                  <StatusBadge status={run.status} />
                </TableCell>
                <TableCell className="py-2">
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
                      {run.riskScore}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="py-2">
                  <TriggerBadge trigger={run.triggeredBy} user={run.triggerUser} />
                </TableCell>
                <TableCell className="py-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                      <button className="rounded p-1 hover:bg-gray-100 transition-colors">
                        <MoreVertical className="h-4 w-4 text-gray-500" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem>
                        <FileText className="mr-2 h-4 w-4" />
                        View Logs
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Play className="mr-2 h-4 w-4" />
                        Re-run
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Eye className="mr-2 h-4 w-4" />
                        View Spec
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Eye className="mr-2 h-4 w-4" />
                        View Resource
                      </DropdownMenuItem>
                      {run.status === "running" && (
                        <>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem className="text-red-600 focus:text-red-600">
                            <X className="mr-2 h-4 w-4" />
                            Cancel
                          </DropdownMenuItem>
                        </>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3">
          <div className="text-sm text-gray-600">
            Showing {startIndex + 1} to {Math.min(endIndex, filteredRuns.length)} of{" "}
            {filteredRuns.length} runs
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page)}
                  className={`h-8 w-8 rounded-md text-sm font-medium transition-colors ${
                    currentPage === page
                      ? "bg-[#ed0923] text-white"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  {page}
                </button>
              ))}
            </div>
            <button
              onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}