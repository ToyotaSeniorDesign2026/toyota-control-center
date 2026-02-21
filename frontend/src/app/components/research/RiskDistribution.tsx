import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

const riskScoreData = [
  { name: "Low Risk", value: 45, color: "#22C55E" },
  { name: "Medium Risk", value: 32, color: "#F59E0B" },
  { name: "High Risk", value: 18, color: "#EF4444" },
  { name: "Critical", value: 5, color: "#7C3AED" },
];

const riskDriversData = [
  { name: "Schedule changes", value: 28, color: "#3B82F6" },
  { name: "Data sensitivity", value: 24, color: "#8B5CF6" },
  { name: "Connector usage", value: 22, color: "#10B981" },
  { name: "Environment", value: 16, color: "#F59E0B" },
  { name: "External egress", value: 10, color: "#EF4444" },
];

export function RiskDistribution() {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* Risk Score Distribution */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Risk Score Distribution
        </h2>
        <div className="h-56 w-full min-h-[224px]">
          <ResponsiveContainer width="100%" height={224}>
            <BarChart data={riskScoreData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis
                dataKey="name"
                tick={{ fill: "#6B7280", fontSize: 12 }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#6B7280", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#FFFFFF",
                  border: "1px solid #E5E7EB",
                  borderRadius: "8px",
                  fontSize: "12px",
                }}
              />
              <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                {riskScoreData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Risk Drivers */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Risk Drivers
        </h2>
        <div className="flex items-center gap-6">
          <div className="h-56 w-full flex-1 min-h-[224px]">
            <ResponsiveContainer width="100%" height={224}>
              <PieChart>
                <Pie
                  data={riskDriversData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {riskDriversData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#FFFFFF",
                    border: "1px solid #E5E7EB",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          
          {/* Legend */}
          <div className="space-y-2">
            {riskDriversData.map((item) => (
              <div key={item.name} className="flex items-center gap-2">
                <div
                  className="h-3 w-3 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <div className="flex-1">
                  <p className="text-xs text-gray-700">{item.name}</p>
                  <p className="text-xs text-gray-500">{item.value}%</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}