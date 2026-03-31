import { AlertTriangle, Database, Clock, GitBranch, Globe, DollarSign } from "lucide-react";

interface RiskFactor {
  id: string;
  icon: React.ReactNode;
  label: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
}

const riskFactors: RiskFactor[] = [
  {
    id: "data-sensitivity",
    icon: <Database className="h-4 w-4" />,
    label: "Data Sensitivity Increase",
    description: "Job now accesses PII data",
    severity: "high",
  },
  {
    id: "schedule-change",
    icon: <Clock className="h-4 w-4" />,
    label: "Schedule Change",
    description: "Frequency increased to every 5 minutes",
    severity: "medium",
  },
  {
    id: "environment-escalation",
    icon: <GitBranch className="h-4 w-4" />,
    label: "Environment Escalation",
    description: "Promoting from Dev → Production",
    severity: "high",
  },
  {
    id: "external-egress",
    icon: <Globe className="h-4 w-4" />,
    label: "External Egress Enabled",
    description: "New external API connection added",
    severity: "critical",
  },
  {
    id: "cost-change",
    icon: <DollarSign className="h-4 w-4" />,
    label: "Estimated Cost Change",
    description: "+$450/month projected increase",
    severity: "medium",
  },
];

const severityColors = {
  low: {
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-700",
    badge: "bg-green-100 text-green-700",
  },
  medium: {
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    text: "text-yellow-700",
    badge: "bg-yellow-100 text-yellow-700",
  },
  high: {
    bg: "bg-orange-50",
    border: "border-orange-200",
    text: "text-orange-700",
    badge: "bg-orange-100 text-orange-700",
  },
  critical: {
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-700",
    badge: "bg-red-100 text-red-700",
  },
};

export function RiskVisibilityPanel() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-orange-500" />
        <h3 className="text-sm font-semibold text-gray-900">
          Why This Change Requires Approval
        </h3>
      </div>
      
      <div className="space-y-3">
        {riskFactors.map((factor) => {
          const colors = severityColors[factor.severity];
          return (
            <div
              key={factor.id}
              className={`rounded-lg border p-3 ${colors.bg} ${colors.border}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-start gap-2 flex-1">
                  <div className={`mt-0.5 ${colors.text}`}>
                    {factor.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900">
                      {factor.label}
                    </div>
                    <div className="mt-0.5 text-xs text-gray-600">
                      {factor.description}
                    </div>
                  </div>
                </div>
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium uppercase ${colors.badge}`}
                >
                  {factor.severity}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
