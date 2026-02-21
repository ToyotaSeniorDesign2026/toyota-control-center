import { CheckCircle2, Clock, Repeat, Sparkles } from "lucide-react";

export function ProductivityImpact() {
  const metrics = [
    {
      icon: <Sparkles className="h-4 w-4" />,
      label: "Runs automated this week",
      value: "2,847",
      color: "bg-red-50 text-[#ed0923]",
    },
    {
      icon: <Repeat className="h-4 w-4" />,
      label: "Manual overrides required",
      value: "34",
      color: "bg-yellow-50 text-yellow-600",
    },
    {
      icon: <Clock className="h-4 w-4" />,
      label: "Estimated manual hours saved",
      value: "342 hrs",
      color: "bg-green-50 text-green-600",
    },
    {
      icon: <CheckCircle2 className="h-4 w-4" />,
      label: "Context switches reduced",
      value: "1,284",
      color: "bg-purple-50 text-purple-600",
    },
  ];

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
      <h2 className="mb-3 text-lg font-semibold text-gray-900">
        Productivity Impact
      </h2>

      {/* Compact Horizontal Stat Strip */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 p-2"
          >
            <div className={`rounded p-1.5 ${metric.color}`}>
              {metric.icon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-lg font-bold text-gray-900">
                {metric.value}
              </p>
              <p className="text-xs text-gray-600 truncate">{metric.label}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
