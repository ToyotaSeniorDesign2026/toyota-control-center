import { X, TrendingUp, TrendingDown } from "lucide-react";
import { RiskJob } from "./HighRiskJobsTable";

interface RiskDetailDrawerProps {
  job: RiskJob | null;
  onClose: () => void;
}

const riskFactors = [
  {
    id: "data-sensitivity",
    label: "Data Sensitivity",
    weight: 35,
    value: "PII & Financial Data",
    description: "Job accesses personally identifiable information and financial records",
    level: "critical",
  },
  {
    id: "environment",
    label: "Environment",
    weight: 25,
    value: "Production",
    description: "Deployed in production environment with customer-facing impact",
    level: "high",
  },
  {
    id: "schedule",
    label: "Schedule Frequency",
    weight: 15,
    value: "Every 5 minutes",
    description: "High-frequency execution may impact system jobs",
    level: "medium",
  },
  {
    id: "connector",
    label: "Connector Type",
    weight: 10,
    value: "External API + Database",
    description: "Connects to external third-party services and internal databases",
    level: "medium",
  },
  {
    id: "external",
    label: "External Calls",
    weight: 10,
    value: "2 endpoints",
    description: "Makes API calls to external services outside the organization",
    level: "low",
  },
  {
    id: "cost",
    label: "Cost Estimate",
    weight: 5,
    value: "+$450/month",
    description: "Recent changes increased estimated monthly operational costs",
    level: "low",
  },
];

const riskHistory = [
  { date: "Feb 13, 2024", score: 92, change: "+5", event: "External API added" },
  { date: "Feb 10, 2024", score: 87, change: "+12", event: "Schedule frequency increased" },
  { date: "Feb 5, 2024", score: 75, change: "+3", event: "Data sensitivity updated" },
  { date: "Feb 1, 2024", score: 72, change: "-2", event: "Minor configuration change" },
  { date: "Jan 28, 2024", score: 74, change: "+8", event: "Promoted to Production" },
];

const levelColors = {
  critical: {
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-700",
    bar: "bg-red-500",
  },
  high: {
    bg: "bg-orange-50",
    border: "border-orange-200",
    text: "text-orange-700",
    bar: "bg-orange-500",
  },
  medium: {
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-700",
    bar: "bg-yellow-500",
  },
  low: {
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-700",
    bar: "bg-green-500",
  },
};

export function RiskDetailDrawer({ job, onClose }: RiskDetailDrawerProps) {
  if (!job) return null;

  const riskColor =
    job.riskLevel === "Critical"
      ? "text-red-600"
      : job.riskLevel === "High"
      ? "text-orange-600"
      : job.riskLevel === "Medium"
      ? "text-yellow-600"
      : "text-green-600";

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white shadow-2xl border-l border-gray-200 flex flex-col overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 border-b border-gray-200 bg-gray-50 px-6 py-4 z-10">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-gray-900">
                Risk Analysis
              </h2>
              <span
                className={`rounded px-2 py-0.5 text-xs font-semibold ${riskColor} bg-opacity-10`}
              >
                {job.riskLevel}
              </span>
            </div>
            <div className="mt-1 text-sm text-gray-600 font-mono">
              {job.id}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Key Info */}
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">
              Job Name
            </div>
            <div className="mt-1 text-sm font-semibold text-gray-900">
              {job.name}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">
              Risk Score
            </div>
            <div className={`mt-1 text-2xl font-bold ${riskColor}`}>
              {job.riskScore}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">
              Type
            </div>
            <div className="mt-1 text-sm font-semibold text-gray-900">
              {job.type}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">
              Environment
            </div>
            <div className="mt-1 text-sm font-semibold text-gray-900">
              {job.environment}
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6 space-y-6">
        {/* Risk Factors */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-4">
            Risk Factors
          </h3>
          <div className="space-y-3">
            {riskFactors.map((factor) => {
              const colors = levelColors[factor.level as keyof typeof levelColors];
              return (
                <div
                  key={factor.id}
                  className={`rounded-lg border p-4 ${colors.bg} ${colors.border}`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <div className="text-sm font-semibold text-gray-900">
                          {factor.label}
                        </div>
                        <span className={`text-xs font-medium ${colors.text}`}>
                          {factor.weight}% weight
                        </span>
                      </div>
                      <div className="text-sm font-medium text-gray-700">
                        {factor.value}
                      </div>
                    </div>
                  </div>

                  {/* Weight Bar */}
                  <div className="mb-2 h-2 w-full rounded-full bg-gray-200">
                    <div
                      className={`h-2 rounded-full ${colors.bar}`}
                      style={{ width: `${factor.weight}%` }}
                    />
                  </div>

                  <p className="text-xs text-gray-600">{factor.description}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Risk History */}
        <div>
          <h3 className="text-sm font-semibold text-gray-900 mb-4">
            Risk History
          </h3>
          <div className="space-y-3">
            {riskHistory.map((entry, index) => {
              const isIncrease = entry.change.startsWith("+");
              return (
                <div
                  key={index}
                  className="flex items-start gap-4 rounded-lg border border-gray-200 bg-white p-4"
                >
                  {/* Timeline Dot */}
                  <div className="flex flex-col items-center">
                    <div
                      className={`h-3 w-3 rounded-full ${
                        index === 0 ? "bg-blue-500" : "bg-gray-300"
                      }`}
                    />
                    {index < riskHistory.length - 1 && (
                      <div className="w-0.5 flex-1 bg-gray-200 h-8" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between mb-1">
                      <div className="text-sm font-medium text-gray-900">
                        {entry.event}
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="text-lg font-bold text-gray-900">
                          {entry.score}
                        </div>
                        <div
                          className={`flex items-center gap-0.5 text-xs font-medium ${
                            isIncrease ? "text-red-600" : "text-green-600"
                          }`}
                        >
                          {isIncrease ? (
                            <TrendingUp className="h-3 w-3" />
                          ) : (
                            <TrendingDown className="h-3 w-3" />
                          )}
                          {entry.change}
                        </div>
                      </div>
                    </div>
                    <div className="text-xs text-gray-500">{entry.date}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Additional Info */}
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs font-medium text-gray-500 uppercase">
                Owner
              </div>
              <div className="mt-1 text-sm font-medium text-gray-900">
                {job.owner}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-gray-500 uppercase">
                Primary Risk Driver
              </div>
              <div className="mt-1 text-sm font-medium text-gray-900">
                {job.primaryDriver}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-gray-500 uppercase">
                Approval Required
              </div>
              <div className="mt-1 text-sm font-medium text-gray-900">
                {job.approvalRequired ? "Yes" : "No"}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-gray-500 uppercase">
                Last Modified
              </div>
              <div className="mt-1 text-sm font-medium text-gray-900">
                {new Date(job.lastModified).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
