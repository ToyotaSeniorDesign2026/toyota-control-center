import { Activity, AlertTriangle, CheckCircle2, Clock, ShieldAlert, TrendingUp } from "lucide-react";

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext: string;
  status: "success" | "warning" | "error" | "info";
  icon: React.ReactNode;
}

function MetricCard({ label, value, subtext, status, icon }: MetricCardProps) {
  const colorMap: Record<string, string> = {
    success: "text-green-600",
    warning: "text-yellow-600",
    error: "text-red-600",
    info: "text-[#ed0923]",
  };

  const bgColorMap: Record<string, string> = {
    success: "bg-green-50",
    warning: "bg-yellow-50",
    error: "bg-red-50",
    info: "bg-red-50",
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
            {label}
          </p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
          <p className="mt-1 text-sm text-gray-600">{subtext}</p>
        </div>
        <div className={`rounded-lg p-2 ${bgColorMap[status]}`}>
          <div className={colorMap[status]}>{icon}</div>
        </div>
      </div>
    </div>
  );
}

export function MetricsBar() {
  const metrics = [
    {
      label: "Active Jobs",
      value: 148,
      subtext: "+12 this month",
      status: "success" as const,
      icon: <Activity className="h-5 w-5" />,
    },
    {
      label: "Running Now",
      value: 24,
      subtext: "Across all environments",
      status: "info" as const,
      icon: <TrendingUp className="h-5 w-5" />,
    },
    {
      label: "Failed (Last 24h)",
      value: 3,
      subtext: "2 require attention",
      status: "error" as const,
      icon: <AlertTriangle className="h-5 w-5" />,
    },
    {
      label: "Pending Approvals",
      value: 7,
      subtext: "Waiting for review",
      status: "warning" as const,
      icon: <Clock className="h-5 w-5" />,
    },
    {
      label: "Risk Alerts",
      value: 5,
      subtext: "3 high priority",
      status: "warning" as const,
      icon: <ShieldAlert className="h-5 w-5" />,
    },
    {
      label: "SLA Violations",
      value: 0,
      subtext: "Great job!",
      status: "success" as const,
      icon: <CheckCircle2 className="h-5 w-5" />,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {metrics.map((metric) => (
        <MetricCard key={metric.label} {...metric} />
      ))}
    </div>
  );
}