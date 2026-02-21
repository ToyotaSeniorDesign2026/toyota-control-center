import { Clock, ChevronDown } from "lucide-react";
import { useState } from "react";

interface ScheduledJob {
  id: string;
  name: string;
  nextRun: string;
  environment: string;
  slaTarget: string;
}

const mockJobs: ScheduledJob[] = [
  {
    id: "1",
    name: "dbt_daily_model",
    nextRun: "Today at 6:00 AM",
    environment: "Prod",
    slaTarget: "< 30 min",
  },
  {
    id: "2",
    name: "customer_churn_predictor",
    nextRun: "Today at 8:00 AM",
    environment: "Prod",
    slaTarget: "< 15 min",
  },
  {
    id: "3",
    name: "revenue_dashboard",
    nextRun: "Today at 9:00 AM",
    environment: "Prod",
    slaTarget: "< 10 min",
  },
  {
    id: "4",
    name: "airflow_etl_pipeline",
    nextRun: "Today at 12:00 PM",
    environment: "Prod",
    slaTarget: "< 45 min",
  },
  {
    id: "5",
    name: "inventory_optimizer",
    nextRun: "Today at 2:00 PM",
    environment: "Semi-Prod",
    slaTarget: "< 20 min",
  },
];

export function ScheduledJobs() {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full border-b border-gray-200 p-5 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <h2 className="text-lg font-semibold text-gray-900">
          Upcoming Scheduled Runs
        </h2>
        <ChevronDown
          className={`h-5 w-5 text-gray-400 transition-transform ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </button>
      {isExpanded && (
        <div className="p-4">
          <div className="space-y-4">
            {mockJobs.map((job, index) => (
              <div key={job.id}>
                <div className="flex items-center justify-between">
                  <div className="flex items-start gap-3 flex-1">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-50">
                      <Clock className="h-4 w-4 text-[#ed0923]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {job.name}
                      </p>
                      <p className="mt-0.5 text-xs text-gray-500">
                        {job.nextRun}
                      </p>
                    </div>
                  </div>
                  <div className="text-right ml-4">
                    <p className="text-xs font-medium text-gray-600">
                      {job.environment}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500">{job.slaTarget}</p>
                  </div>
                </div>
                {index < mockJobs.length - 1 && (
                  <div className="ml-4 mt-4 border-t border-gray-100" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}