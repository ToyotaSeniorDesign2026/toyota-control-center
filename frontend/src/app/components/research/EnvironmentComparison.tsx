import { AlertCircle, CheckCircle2, Shield, ChevronDown } from "lucide-react";
import { useState } from "react";

interface EnvironmentCardProps {
  name: string;
  color: string;
  stats: {
    totalResources: number;
    successRate: number;
    avgRiskScore: number;
    openApprovals: number;
    slaViolations: number;
  };
}

function EnvironmentCard({ name, color, stats }: EnvironmentCardProps) {
  const healthColor =
    stats.successRate >= 95
      ? "text-green-600"
      : stats.successRate >= 85
      ? "text-yellow-600"
      : "text-red-600";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`h-3 w-3 rounded-full ${color}`} />
          <h3 className="font-semibold text-gray-900">{name}</h3>
        </div>
        <div className={healthColor}>
          {stats.successRate >= 95 ? (
            <CheckCircle2 className="h-5 w-5" />
          ) : (
            <AlertCircle className="h-5 w-5" />
          )}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <span className="text-xs text-gray-600">Total Resources</span>
          <span className="text-sm font-semibold text-gray-900">
            {stats.totalResources}
          </span>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <span className="text-xs text-gray-600">Success Rate</span>
          <span className={`text-sm font-semibold ${healthColor}`}>
            {stats.successRate}%
          </span>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <span className="text-xs text-gray-600">Avg Risk Score</span>
          <div className="flex items-center gap-2">
            <span
              className={`h-2 w-2 rounded-full ${
                stats.avgRiskScore < 30
                  ? "bg-green-500"
                  : stats.avgRiskScore < 60
                  ? "bg-yellow-500"
                  : "bg-red-500"
              }`}
            />
            <span className="text-sm font-semibold text-gray-900">
              {stats.avgRiskScore}
            </span>
          </div>
        </div>

        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <span className="text-xs text-gray-600">Open Approvals</span>
          <span className="text-sm font-semibold text-gray-900">
            {stats.openApprovals}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-600">SLA Violations</span>
          <span
            className={`text-sm font-semibold ${
              stats.slaViolations === 0 ? "text-green-600" : "text-red-600"
            }`}
          >
            {stats.slaViolations}
          </span>
        </div>
      </div>
    </div>
  );
}

export function EnvironmentComparison() {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const environments = [
    {
      name: "Dev",
      color: "bg-[#ed0923]",
      stats: {
        totalResources: 89,
        successRate: 91,
        avgRiskScore: 15,
        openApprovals: 0,
        slaViolations: 0,
      },
    },
    {
      name: "Semi-Prod",
      color: "bg-yellow-500",
      stats: {
        totalResources: 64,
        successRate: 94,
        avgRiskScore: 28,
        openApprovals: 7,
        slaViolations: 1,
      },
    },
    {
      name: "Prod",
      color: "bg-green-500",
      stats: {
        totalResources: 148,
        successRate: 97,
        avgRiskScore: 12,
        openApprovals: 2,
        slaViolations: 0,
      },
    },
  ];

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
      >
        <h2 className="text-lg font-semibold text-gray-900">
          Environment Comparison
        </h2>
        <ChevronDown
          className={`h-4 w-4 text-gray-400 transition-transform ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </button>

      {isExpanded && (
        <div className="border-t border-gray-200 p-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {environments.map((env) => (
              <EnvironmentCard key={env.name} {...env} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
