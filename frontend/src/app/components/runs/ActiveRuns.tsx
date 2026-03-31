import { Progress } from "../ui/progress";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

export function ActiveRuns() {
  const activeRuns = [
    {
      id: "run-7f3a8b",
      jobName: "customer_churn_predictor",
      environment: "Prod",
      duration: "2m 34s",
      progress: 65,
    },
    {
      id: "run-9c2e1d",
      jobName: "dbt_daily_model",
      environment: "Semi-Prod",
      duration: "5m 12s",
      progress: 45,
    },
    {
      id: "run-4b8f3a",
      jobName: "airflow_etl_pipeline",
      environment: "Prod",
      duration: "1m 08s",
      progress: 85,
    },
  ];

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 3;

  if (activeRuns.length === 0) return null;

  const totalPages = Math.ceil(activeRuns.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedRuns = activeRuns.slice(startIndex, endIndex);

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 shadow-sm">
      <div className="flex items-center justify-between border-b border-red-200 bg-white px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 animate-pulse rounded-full bg-[#ed0923]" />
          <h3 className="text-sm font-semibold text-gray-900">Currently Running</h3>
          <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-xs font-medium text-[#b8071c]">
            {activeRuns.length}
          </span>
        </div>
        
        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              className="rounded p-1 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="h-4 w-4 text-gray-600" />
            </button>
            <span className="text-xs text-gray-600">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              className="rounded p-1 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="h-4 w-4 text-gray-600" />
            </button>
          </div>
        )}
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-max p-2">
          <div className="space-y-1.5">
            {paginatedRuns.map((run) => (
              <div
                key={run.id}
                className="flex items-center gap-3 rounded bg-white px-3 py-2 border border-blue-200"
              >
                {/* Job Name */}
                <div className="min-w-[220px]">
                  <p className="text-sm font-medium text-gray-900">{run.jobName}</p>
                </div>

                {/* Environment */}
                <div className="min-w-[90px]">
                  <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                    {run.environment}
                  </span>
                </div>

                {/* Duration */}
                <div className="min-w-[70px]">
                  <span className="font-mono text-xs text-gray-600">{run.duration}</span>
                </div>

                {/* Progress Bar */}
                <div className="min-w-[200px]">
                  <Progress value={run.progress} className="h-1.5" />
                </div>

                {/* Percentage */}
                <div className="min-w-[50px] text-right">
                  <span className="text-xs font-medium text-gray-700">{run.progress}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}