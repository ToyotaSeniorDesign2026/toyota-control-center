import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { ChevronDown } from "lucide-react";

const data = [
  {
    environment: "Dev",
    Low: 45,
    Medium: 28,
    High: 12,
    Critical: 3,
  },
  {
    environment: "Semi-Prod",
    Low: 32,
    Medium: 24,
    High: 15,
    Critical: 6,
  },
  {
    environment: "Production",
    Low: 28,
    Medium: 18,
    High: 18,
    Critical: 8,
  },
];

export function RiskDistributionChart() {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
      >
        <div className="text-left">
          <h3 className="text-lg font-semibold text-gray-900">
            Risk Distribution by Environment
          </h3>
          <p className="mt-1 text-sm text-gray-600">
            Job risk levels across deployment environments
          </p>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-gray-400 transition-transform ${
            isExpanded ? "rotate-180" : ""
          }`}
        />
      </button>

      {isExpanded && (
        <div className="border-t border-gray-200 p-4">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data}
                margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="environment"
                  tick={{ fill: "#6b7280", fontSize: 12 }}
                  axisLine={{ stroke: "#d1d5db" }}
                />
                <YAxis
                  tick={{ fill: "#6b7280", fontSize: 12 }}
                  axisLine={{ stroke: "#d1d5db" }}
                  label={{
                    value: "Number of Jobs",
                    angle: -90,
                    position: "insideLeft",
                    style: { fill: "#6b7280", fontSize: 12 },
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#ffffff",
                    border: "1px solid #e5e7eb",
                    borderRadius: "8px",
                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                  }}
                  cursor={{ fill: "rgba(59, 130, 246, 0.1)" }}
                />
                <Legend
                  wrapperStyle={{ paddingTop: "20px" }}
                  iconType="circle"
                />
                <Bar dataKey="Low" stackId="a" fill="#22C55E" radius={[0, 0, 0, 0]} />
                <Bar dataKey="Medium" stackId="a" fill="#F59E0B" radius={[0, 0, 0, 0]} />
                <Bar dataKey="High" stackId="a" fill="#F97316" radius={[0, 0, 0, 0]} />
                <Bar dataKey="Critical" stackId="a" fill="#EF4444" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
