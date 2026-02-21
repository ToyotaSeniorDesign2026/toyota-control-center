import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Button } from "../ui/button";
import { ChevronDown } from "lucide-react";

const mockData = [
  { date: "Feb 5", total: 420, failed: 12, aiAgent: 180, dataPipeline: 150, biTasks: 90 },
  { date: "Feb 6", total: 445, failed: 15, aiAgent: 195, dataPipeline: 155, biTasks: 95 },
  { date: "Feb 7", total: 390, failed: 8, aiAgent: 170, dataPipeline: 140, biTasks: 80 },
  { date: "Feb 8", total: 520, failed: 18, aiAgent: 220, dataPipeline: 180, biTasks: 120 },
  { date: "Feb 9", total: 485, failed: 10, aiAgent: 210, dataPipeline: 165, biTasks: 110 },
  { date: "Feb 10", total: 550, failed: 14, aiAgent: 240, dataPipeline: 190, biTasks: 120 },
  { date: "Feb 11", total: 510, failed: 9, aiAgent: 220, dataPipeline: 175, biTasks: 115 },
  { date: "Feb 12", total: 580, failed: 16, aiAgent: 255, dataPipeline: 200, biTasks: 125 },
];

type FilterType = "all" | "aiAgents" | "dataJobs" | "biTasks";

export function AutomationTrendsChart() {
  const [activeFilter, setActiveFilter] = useState<FilterType>("all");
  const [isExpanded, setIsExpanded] = useState(false);

  const filters: { label: string; value: FilterType }[] = [
    { label: "All", value: "all" },
    { label: "AI Agents", value: "aiAgents" },
    { label: "Data Jobs", value: "dataJobs" },
    { label: "BI Tasks", value: "biTasks" },
  ];

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
      >
        <h2 className="text-lg font-semibold text-gray-900">
          Automation Activity Over Time
        </h2>
        <div className="flex items-center gap-3">
          {/* Filter Chips (always visible) */}
          <div className="flex gap-2">
            {filters.map((filter) => (
              <span
                key={filter.value}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  activeFilter === filter.value
                    ? "bg-[#ed0923] text-white"
                    : "bg-gray-100 text-gray-600"
                }`}
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveFilter(filter.value);
                }}
              >
                {filter.label}
              </span>
            ))}
          </div>
          <ChevronDown
            className={`h-4 w-4 text-gray-400 transition-transform ${
              isExpanded ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-gray-200 p-4">
          <div className="h-64 w-full min-h-[256px]">
            <ResponsiveContainer width="100%" height={256}>
              <LineChart data={mockData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis
                  dataKey="date"
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
                <Legend
                  wrapperStyle={{ fontSize: "12px", paddingTop: "20px" }}
                />
                {(activeFilter === "all" || activeFilter === "aiAgents") && (
                  <Line
                    type="monotone"
                    dataKey="total"
                    stroke="#3B82F6"
                    strokeWidth={2}
                    name="Total Runs"
                    dot={{ fill: "#3B82F6", r: 4 }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="failed"
                  stroke="#EF4444"
                  strokeWidth={2}
                  name="Failed Runs"
                  dot={{ fill: "#EF4444", r: 4 }}
                />
                {(activeFilter === "all" || activeFilter === "aiAgents") && (
                  <Line
                    type="monotone"
                    dataKey="aiAgent"
                    stroke="#8B5CF6"
                    strokeWidth={2}
                    name="AI Agent Executions"
                    dot={{ fill: "#8B5CF6", r: 4 }}
                  />
                )}
                {(activeFilter === "all" || activeFilter === "dataJobs") && (
                  <Line
                    type="monotone"
                    dataKey="dataPipeline"
                    stroke="#10B981"
                    strokeWidth={2}
                    name="Data Pipeline Runs"
                    dot={{ fill: "#10B981", r: 4 }}
                  />
                )}
                {(activeFilter === "all" || activeFilter === "biTasks") && (
                  <Line
                    type="monotone"
                    dataKey="biTasks"
                    stroke="#F59E0B"
                    strokeWidth={2}
                    name="BI Tasks"
                    dot={{ fill: "#F59E0B", r: 4 }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
