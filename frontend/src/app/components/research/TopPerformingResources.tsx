import { ArrowDown, ArrowUp, ArrowUpDown, Search, ChevronLeft, ChevronRight } from "lucide-react";
import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";

interface Job {
  id: string;
  name: string;
  type: string;
  totalRuns: number;
  successRate: number;
  avgDuration: string;
  riskTrend: "up" | "down" | "stable";
}

const mockJobs: Job[] = [
  {
    id: "1",
    name: "customer_churn_predictor",
    type: "AI Agent",
    totalRuns: 2847,
    successRate: 98.5,
    avgDuration: "2.3 min",
    riskTrend: "down",
  },
  {
    id: "2",
    name: "revenue_dashboard",
    type: "BI",
    totalRuns: 2456,
    successRate: 99.2,
    avgDuration: "1.1 min",
    riskTrend: "stable",
  },
  {
    id: "3",
    name: "airflow_etl_pipeline",
    type: "Airflow",
    totalRuns: 1998,
    successRate: 96.8,
    avgDuration: "8.5 min",
    riskTrend: "down",
  },
  {
    id: "4",
    name: "customer_summary_agent",
    type: "AI Agent",
    totalRuns: 1847,
    successRate: 97.4,
    avgDuration: "3.2 min",
    riskTrend: "stable",
  },
  {
    id: "5",
    name: "sales_forecast_query",
    type: "SQL",
    totalRuns: 1756,
    successRate: 99.8,
    avgDuration: "0.8 min",
    riskTrend: "down",
  },
  {
    id: "6",
    name: "dbt_daily_model",
    type: "dbt",
    totalRuns: 1654,
    successRate: 94.2,
    avgDuration: "12.4 min",
    riskTrend: "up",
  },
  {
    id: "7",
    name: "inventory_optimizer",
    type: "AI Agent",
    totalRuns: 1432,
    successRate: 96.1,
    avgDuration: "4.7 min",
    riskTrend: "stable",
  },
  {
    id: "8",
    name: "marketing_attribution",
    type: "SQL",
    totalRuns: 1289,
    successRate: 98.9,
    avgDuration: "1.5 min",
    riskTrend: "down",
  },
];

function RiskTrendIndicator({ trend }: { trend: Job["riskTrend"] }) {
  if (trend === "down") {
    return (
      <div className="flex items-center gap-1 text-green-600">
        <ArrowDown className="h-4 w-4" />
        <span className="text-sm">Improving</span>
      </div>
    );
  }
  if (trend === "up") {
    return (
      <div className="flex items-center gap-1 text-red-600">
        <ArrowUp className="h-4 w-4" />
        <span className="text-sm">Increasing</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1 text-gray-500">
      <ArrowUpDown className="h-4 w-4" />
      <span className="text-sm">Stable</span>
    </div>
  );
}

export function TopPerformingJobs() {
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const filteredJobs = mockJobs.filter((job) =>
    job.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const totalPages = Math.ceil(filteredJobs.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedJobs = filteredJobs.slice(startIndex, endIndex);

  // Reset to page 1 when search changes
  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
        <h2 className="text-lg font-semibold text-gray-900">
          Top Performing Jobs
        </h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search jobs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-64 rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-200 hover:bg-transparent">
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Job Name
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Type
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Total Runs
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Success Rate
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Avg Duration
              </TableHead>
              <TableHead className="py-2 text-xs font-medium uppercase tracking-wide text-gray-500">
                Risk Trend
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedJobs.map((job) => (
              <TableRow
                key={job.id}
                className="border-gray-200 hover:bg-gray-50"
              >
                <TableCell className="py-2 font-medium text-gray-900">
                  {job.name}
                </TableCell>
                <TableCell className="py-2 text-gray-600">{job.type}</TableCell>
                <TableCell className="py-2 text-gray-900">
                  {job.totalRuns.toLocaleString()}
                </TableCell>
                <TableCell className="py-2">
                  <span
                    className={`font-medium ${
                      job.successRate >= 98
                        ? "text-green-600"
                        : job.successRate >= 95
                        ? "text-yellow-600"
                        : "text-red-600"
                    }`}
                  >
                    {job.successRate}%
                  </span>
                </TableCell>
                <TableCell className="py-2 text-gray-600">
                  {job.avgDuration}
                </TableCell>
                <TableCell className="py-2">
                  <RiskTrendIndicator trend={job.riskTrend} />
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
            Showing {startIndex + 1} to {Math.min(endIndex, filteredJobs.length)} of{" "}
            {filteredJobs.length} jobs
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
