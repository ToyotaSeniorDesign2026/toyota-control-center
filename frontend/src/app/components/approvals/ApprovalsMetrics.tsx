import { TrendingUp, TrendingDown } from "lucide-react";

const metrics = [
  {
    label: "Pending Approvals",
    value: "12",
    trend: "+3 from last week",
    trendUp: true,
    highlight: true,
  },
  {
    label: "High Risk Changes",
    value: "4",
    trend: "+2 from last week",
    trendUp: true,
    highlight: true,
    critical: true,
  },
  {
    label: "Avg Approval Time",
    value: "2.4h",
    trend: "-0.5h from last week",
    trendUp: false,
  },
  {
    label: "Blocked Promotions",
    value: "2",
    trend: "Same as last week",
    trendUp: false,
  },
];

export function ApprovalsMetrics() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className={`rounded-lg border bg-white p-4 shadow-sm ${
            metric.critical
              ? "border-red-200 bg-red-50/30"
              : "border-gray-200"
          }`}
        >
          <div className="text-sm font-medium text-gray-600">
            {metric.label}
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <div
              className={`text-3xl font-bold ${
                metric.critical ? "text-red-600" : "text-gray-900"
              }`}
            >
              {metric.value}
            </div>
            {metric.critical && (
              <div className="h-2 w-2 rounded-full bg-red-500" />
            )}
          </div>
          <div className="mt-2 flex items-center gap-1 text-xs">
            {metric.trendUp ? (
              <TrendingUp className="h-3 w-3 text-red-500" />
            ) : (
              <TrendingDown className="h-3 w-3 text-green-500" />
            )}
            <span className="text-gray-500">{metric.trend}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
