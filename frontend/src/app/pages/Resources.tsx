import { useState } from "react";
import { Plus, Upload, Search, Filter, LayoutGrid, Table as TableIcon } from "lucide-react";
import { Button } from "../components/ui/button";
import { ResourcesTable } from "../components/resources/ResourcesTable";
import { ResourcesCards } from "../components/resources/ResourcesCards";
import { ResourcesSidebar } from "../components/resources/ResourcesSidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import { ChevronDown } from "lucide-react";

export type ViewType = "table" | "card";
export type FilterType = "all" | "my" | "high-risk" | "failed" | "needs-approval" | "recent";

export default function Resources() {
  const [viewType, setViewType] = useState<ViewType>("table");
  const [activeFilter, setActiveFilter] = useState<FilterType>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("All Types");
  const [statusFilter, setStatusFilter] = useState<string>("All Status");
  const [riskFilter, setRiskFilter] = useState<string>("All Risk Levels");

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <ResourcesSidebar
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
      />

      {/* Main Content */}
      <div className="flex-1">
        {/* Page Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Resources</h1>
            <p className="mt-2 text-sm text-gray-600">
              Manage AI agents, data jobs, pipelines, and automation workflows
              in one place.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              className="h-9 gap-2 border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              <Upload className="h-4 w-4" />
              Import from GitHub
            </Button>
          </div>
        </div>

        {/* Filter + Control Bar */}
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            {/* Left: Search and Filters */}
            <div className="flex flex-1 items-center gap-3">
              {/* Search */}
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by name, owner, tag..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-9 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                />
              </div>

              {/* Type Filter */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50"
                  >
                    <Filter className="h-4 w-4" />
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
                  <DropdownMenuItem onClick={() => setTypeFilter("Excel")}>
                    Excel
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setTypeFilter("PowerPoint")}>
                    PowerPoint
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Status Filter */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50"
                  >
                    {statusFilter}
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-40">
                  <DropdownMenuItem onClick={() => setStatusFilter("All Status")}>
                    All Status
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setStatusFilter("Healthy")}>
                    Healthy
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setStatusFilter("Warning")}>
                    Warning
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setStatusFilter("Failed")}>
                    Failed
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>

              {/* Risk Filter */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="outline"
                    className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50"
                  >
                    {riskFilter}
                    <ChevronDown className="h-4 w-4 text-gray-400" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="w-44">
                  <DropdownMenuItem onClick={() => setRiskFilter("All Risk Levels")}>
                    All Risk Levels
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setRiskFilter("Low")}>
                    Low
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setRiskFilter("Medium")}>
                    Medium
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setRiskFilter("High")}>
                    High
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
                onClick={() => setViewType("card")}
                className={`flex h-7 items-center gap-2 rounded px-3 text-sm font-medium transition-colors ${
                  viewType === "card"
                    ? "bg-white text-gray-900 shadow-sm"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <LayoutGrid className="h-4 w-4" />
                Card
              </button>
            </div>
          </div>
        </div>

        {/* Resource Display */}
        {viewType === "table" ? (
          <ResourcesTable
            searchQuery={searchQuery}
            typeFilter={typeFilter}
            statusFilter={statusFilter}
            riskFilter={riskFilter}
            activeFilter={activeFilter}
          />
        ) : (
          <ResourcesCards
            searchQuery={searchQuery}
            typeFilter={typeFilter}
            statusFilter={statusFilter}
            riskFilter={riskFilter}
            activeFilter={activeFilter}
          />
        )}
      </div>
    </div>
  );
}