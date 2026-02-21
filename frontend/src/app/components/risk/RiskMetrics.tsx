import { TrendingUp, TrendingDown } from "lucide-react";

const metrics = [
  {
    label: "Average Risk Score",
    value: "62",
    trend: "+5 from last week",
    trendUp: true,
    color: "orange",
    icon: "⚠️",
  },
  {
    label: "High Risk Resources",
    value: "18",
    trend: "+3 from last week",
    trendUp: true,
    color: "red",
    icon: "🔴",
  },
  {
    label: "Critical Changes Pending",
    value: "4",
    trend: "+1 from last week",
    trendUp: true,
    color: "red",
    icon: "⚡",
  },
  {
    label: "Policy Violations (7d)",
    value: "23",
    trend: "-8 from last week",
    trendUp: false,
    color: "yellow",
    icon: "⚖️",
  },
  {
    label: "Environment Drift Incidents",
    value: "6",
    trend: "+2 from last week",
    trendUp: true,
    color: "yellow",
    icon: "🔄",
  },
];

const colorMap = {
  green: {
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-600",
  },
  yellow: {
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-600",
  },
  orange: {
    bg: "bg-orange-50",
    border: "border-orange-200",
    text: "text-orange-600",
  },
  red: {
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-600",
  },
};

export function RiskMetrics() {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3 lg:grid-cols-5">
      {metrics.map((metric) => {
        const colors = colorMap[metric.color as keyof typeof colorMap];
        return (
          <div
            key={metric.label}
            className={`rounded-lg border bg-white p-3 shadow-sm ${colors.border}`}
          >
            <div className="flex items-start justify-between">
              <div className="text-xs font-medium text-gray-600">
                {metric.label}
              </div>
              <span className="text-lg">{metric.icon}</span>
            </div>
            <div className="mt-2">
              <div className={`text-2xl font-bold ${colors.text}`}>
                {metric.value}
              </div>
            </div>
            <div className="mt-1 flex items-center gap-1 text-xs">
              {metric.trendUp ? (
                <TrendingUp className="h-3 w-3 text-red-500" />
              ) : (
                <TrendingDown className="h-3 w-3 text-green-500" />
              )}
              <span className="text-gray-500">{metric.trend}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}