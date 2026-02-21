import { ArrowDown, ArrowUp, Activity } from "lucide-react";

export function RunsMetrics() {
  const metrics = [
    {
      label: "Total Runs",
      value: "3,847",
      trend: "up" as const,
      trendValue: "+12%",
      subtext: "vs last 7 days",
    },
    {
      label: "Success Rate",
      value: "96.2%",
      trend: "up" as const,
      trendValue: "+1.8%",
      subtext: "vs last 7 days",
      color: "text-green-600",
    },
    {
      label: "Failed Runs",
      value: "147",
      trend: "down" as const,
      trendValue: "-8%",
      subtext: "vs last 7 days",
      color: "text-red-600",
    },
    {
      label: "Avg Duration",
      value: "4.2 min",
      trend: "down" as const,
      trendValue: "-15%",
      subtext: "vs last 7 days",
    },
    {
      label: "Active Runs",
      value: "8",
      trend: "up" as const,
      trendValue: "",
      subtext: "running now",
      color: "text-[#ed0923]",
      live: true,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              {metric.label}
            </p>
            {metric.live && (
              <div className="flex items-center gap-1">
                <span className="h-2 w-2 animate-pulse rounded-full bg-[#ed0923]" />
                <Activity className="h-3 w-3 text-[#ed0923]" />
              </div>
            )}
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <p className={`text-2xl font-bold ${metric.color || "text-gray-900"}`}>
              {metric.value}
            </p>
            {metric.trendValue && (
              <div
                className={`flex items-center gap-1 text-xs font-medium ${
                  metric.trend === "up" ? "text-green-600" : "text-red-600"
                }`}
              >
                {metric.trend === "up" ? (
                  <ArrowUp className="h-3 w-3" />
                ) : (
                  <ArrowDown className="h-3 w-3" />
                )}
                {metric.trendValue}
              </div>
            )}
          </div>
          <p className="mt-1 text-xs text-gray-500">{metric.subtext}</p>
        </div>
      ))}
    </div>
  );
}