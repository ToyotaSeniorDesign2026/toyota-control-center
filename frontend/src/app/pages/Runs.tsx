import { useState } from "react";
import { Download, Search, Filter, Table as TableIcon, List, ChevronDown } from "lucide-react";
import { Button } from "../components/ui/button";
import { RunsMetrics } from "../components/runs/RunsMetrics";
import { RunsTable } from "../components/runs/RunsTable";
import { RunsTimeline } from "../components/runs/RunsTimeline";
import { ActiveRuns } from "../components/runs/ActiveRuns";
import { RunDetailDrawer } from "../components/runs/RunDetailDrawer";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";

export type ViewType = "table" | "timeline";

export interface Run {
  id: string;
  jobName: string;
  type: "AI Agent" | "Airflow" | "dbt" | "SQL" | "BI" | "Excel" | "PowerPoint";
  environment: string;
  startedAt: string;
  duration: string;
  status: "running" | "succeeded" | "failed" | "cancelled";
  riskScore: number;
  triggeredBy: "User" | "Schedule" | "CLI" | "Promotion";
  triggerUser?: string;
}

export default function Runs() {
  const [viewType, setViewType] = useState<ViewType>("table");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("All Status");
  const [typeFilter, setTypeFilter] = useState<string>("All Types");
  const [environmentFilter, setEnvironmentFilter] = useState<string>("All Environments");
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [filtersExpanded, setFiltersExpanded] = useState(false);

  return (
    <>
      {/* Page Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Runs</h1>
          <p className="mt-1 text-sm text-gray-600">
            Execution history and real-time visibility into automation activity.
          </p>
        </div>
        <Button
          variant="outline"
          className="h-9 gap-2 border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <Download className="h-4 w-4" />
          Export Run Data
        </Button>
      </div>

      {/* Summary Metrics */}
      <div className="mb-4">
        <RunsMetrics />
      </div>

      {/* Active Runs (if any) */}
      <div className="mb-4">
        <ActiveRuns />
      </div>

      {/* Filter & Search Bar - Collapsible */}
      <div className="mb-4 rounded-lg border border-gray-200 bg-white shadow-sm">
        <button
          onClick={() => setFiltersExpanded(!filtersExpanded)}
          className="w-full flex items-center justify-between px-4 py-2 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-700">Filters</span>
            {(searchQuery || statusFilter !== "All Status" || typeFilter !== "All Types" || environmentFilter !== "All Environments") && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-[#b8071c]">
                Active
              </span>
            )}
          </div>
          <ChevronDown
            className={`h-4 w-4 text-gray-400 transition-transform ${
              filtersExpanded ? "rotate-180" : ""
            }`}
          />
        </button>

        {filtersExpanded && (
          <div className="border-t border-gray-200 p-4">
            <div className="flex items-center justify-between gap-4">
              {/* Left: Search and Filters */}
              <div className="flex flex-1 items-center gap-3">
                {/* Search */}
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search by job name or run ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-9 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>

                {/* Status Filter */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50"
                    >
                      <Filter className="h-4 w-4" />
                      {statusFilter}
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-40">
                    <DropdownMenuItem onClick={() => setStatusFilter("All Status")}>
                      All Status
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setStatusFilter("Running")}>
                      Running
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setStatusFilter("Succeeded")}>
                      Succeeded
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setStatusFilter("Failed")}>
                      Failed
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setStatusFilter("Cancelled")}>
                      Cancelled
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Type Filter */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50"
                    >
                      {typeFilter}
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-48">
                    <DropdownMenuItem onClick={() => setTypeFilter("All Types")}>
                      All Types
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTypeFilter("AI Agent")}>
                      AI Agent
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTypeFilter("Airflow")}>
                      Airflow
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTypeFilter("dbt")}>
                      dbt
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTypeFilter("SQL")}>
                      SQL
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setTypeFilter("BI")}>
                      BI
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                {/* Environment Filter */}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50"
                    >
                      {environmentFilter}
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-48">
                    <DropdownMenuItem onClick={() => setEnvironmentFilter("All Environments")}>
                      All Environments
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setEnvironmentFilter("Dev")}>
                      Dev
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setEnvironmentFilter("Semi-Prod")}>
                      Semi-Prod
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => setEnvironmentFilter("Prod")}>
                      Prod
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* Right: View Toggle */}
              <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 p-1">
                <button
                  onClick={() => setViewType("table")}
                  className={`flex h-7 items-center gap-2 rounded px-3 text-sm font-medium transition-colors ${
                    viewType === "table"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  <TableIcon className="h-4 w-4" />
                  Table
                </button>
                <button
                  onClick={() => setViewType("timeline")}
                  className={`flex h-7 items-center gap-2 rounded px-3 text-sm font-medium transition-colors ${
                    viewType === "timeline"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  <List className="h-4 w-4" />
                  Timeline
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Runs Display */}
      {viewType === "table" ? (
        <RunsTable
          searchQuery={searchQuery}
          statusFilter={statusFilter}
          typeFilter={typeFilter}
          environmentFilter={environmentFilter}
          onRunClick={setSelectedRun}
        />
      ) : (
        <RunsTimeline
          searchQuery={searchQuery}
          statusFilter={statusFilter}
          typeFilter={typeFilter}
          environmentFilter={environmentFilter}
          onRunClick={setSelectedRun}
        />
      )}

      {/* Run Detail Drawer */}
      <RunDetailDrawer
        run={selectedRun}
        open={!!selectedRun}
        onClose={() => setSelectedRun(null)}
      />
    </>
  );
}