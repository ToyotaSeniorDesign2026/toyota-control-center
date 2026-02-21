import { ArrowDown, ArrowUp, Clock, Gauge, Target, TrendingUp } from "lucide-react";
import { LineChart, Line, ResponsiveContainer } from "recharts";

interface InsightCardProps {
  label: string;
  value: string | number;
  trend: "up" | "down";
  trendValue: string;
  sparklineData: Array<{ value: number }>;
  unit?: string;
}

const sparklineData = [
  { value: 20 },
  { value: 35 },
  { value: 28 },
  { value: 45 },
  { value: 38 },
  { value: 52 },
  { value: 48 },
];

function InsightCard({
  label,
  value,
  trend,
  trendValue,
  sparklineData,
  unit = "",
}: InsightCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </p>
      <div className="mt-2 flex items-baseline gap-2">
        <p className="text-2xl font-bold text-gray-900">
          {value}
          {unit && <span className="text-lg text-gray-600">{unit}</span>}
        </p>
        <div
          className={`flex items-center gap-1 text-xs font-medium ${
            trend === "up" ? "text-green-600" : "text-red-600"
          }`}
        >
          {trend === "up" ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )}
          {trendValue}
        </div>
      </div>
      <p className="mt-1 text-xs text-gray-500">vs last period</p>
      
      {/* Sparkline */}
      <div className="mt-2 h-8 w-full min-h-[32px]">
        <ResponsiveContainer width="100%" height={32}>
          <LineChart data={sparklineData}>
            <Line
              type="monotone"
              dataKey="value"
              stroke={trend === "up" ? "#22C55E" : "#EF4444"}
              strokeWidth={1.5}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function InsightMetrics() {
  const metrics = [
    {
      label: "Total Runs",
      value: "12,847",
      trend: "up" as const,
      trendValue: "18%",
      sparklineData: sparklineData,
    },
    {
      label: "Avg. Run Success Rate",
      value: "94.2",
      unit: "%",
      trend: "up" as const,
      trendValue: "2.1%",
      sparklineData: [
        { value: 91 },
        { value: 92 },
        { value: 91 },
        { value: 93 },
        { value: 94 },
        { value: 93 },
        { value: 94 },
      ],
    },
    {
      label: "Avg. Risk Score",
      value: "28",
      trend: "down" as const,
      trendValue: "12%",
      sparklineData: [
        { value: 42 },
        { value: 38 },
        { value: 35 },
        { value: 32 },
        { value: 30 },
        { value: 29 },
        { value: 28 },
      ],
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {metrics.map((metric) => (
        <InsightCard key={metric.label} {...metric} />
      ))}
    </div>
  );
}