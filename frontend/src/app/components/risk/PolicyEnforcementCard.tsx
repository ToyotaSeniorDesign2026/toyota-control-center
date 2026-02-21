import { useState } from "react";
import { ShieldAlert, XCircle, AlertTriangle, Info, ChevronDown } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const violationData = [
  { policy: "Data Access", count: 8 },
  { policy: "Cost Limits", count: 6 },
  { policy: "Schedule Freq", count: 5 },
  { policy: "External API", count: 4 },
];

const stats = [
  {
    label: "Blocked Promotions",
    value: "12",
    icon: XCircle,
    color: "text-red-600",
    bgColor: "bg-red-50",
  },
  {
    label: "Failed Policy Checks",
    value: "23",
    icon: ShieldAlert,
    color: "text-orange-600",
    bgColor: "bg-orange-50",
  },
  {
    label: "Warning-Level Violations",
    value: "15",
    icon: AlertTriangle,
    color: "text-yellow-600",
    bgColor: "bg-yellow-50",
  },
  {
    label: "Most Common Violation",
    value: "Data Access Control",
    icon: Info,
    color: "text-blue-600",
    bgColor: "bg-blue-50",
  },
];

export function PolicyEnforcementCard() {
  const [isViolationsExpanded, setIsViolationsExpanded] = useState(false);

  return (
    <div className="space-y-4">
      {/* Policy Enforcement Stats Strip */}
      <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">
          Policy Enforcement Activity
        </h3>

        {/* Compact Horizontal Stat Strip */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <div
                key={stat.label}
                className={`rounded-lg border border-gray-200 p-2 ${stat.bgColor}`}
              >
                <div className="flex items-start justify-between mb-1">
                  <div className="text-xs font-medium text-gray-600 uppercase">
                    {stat.label}
                  </div>
                  <Icon className={`h-4 w-4 ${stat.color}`} />
                </div>
                <div className={`text-lg font-bold ${stat.color}`}>
                  {stat.value}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Policy Violations by Type - Collapsible */}
      <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <button
          onClick={() => setIsViolationsExpanded(!isViolationsExpanded)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
        >
          <h4 className="text-lg font-semibold text-gray-900">
            Policy Violations by Type
          </h4>
          <ChevronDown
            className={`h-4 w-4 text-gray-400 transition-transform ${
              isViolationsExpanded ? "rotate-180" : ""
            }`}
          />
        </button>

        {isViolationsExpanded && (
          <div className="border-t border-gray-200 p-4">
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={violationData}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    type="number"
                    tick={{ fill: "#6b7280", fontSize: 12 }}
                    axisLine={{ stroke: "#d1d5db" }}
                  />
                  <YAxis
                    type="category"
                    dataKey="policy"
                    tick={{ fill: "#6b7280", fontSize: 12 }}
                    axisLine={{ stroke: "#d1d5db" }}
                    width={90}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#ffffff",
                      border: "1px solid #e5e7eb",
                      borderRadius: "8px",
                      boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                    }}
                  />
                  <Bar dataKey="count" fill="#EF4444" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
