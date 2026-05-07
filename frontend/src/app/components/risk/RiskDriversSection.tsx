import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";

const riskDriversData = [
  { name: "Data Sensitivity", value: 28, color: "#EF4444" },
  { name: "Environment", value: 22, color: "#F59E0B" },
  { name: "Schedule/Concurrency", value: 18, color: "#F97316" },
  { name: "External Egress", value: 14, color: "#8B5CF6" },
  { name: "Connector/Tooling", value: 12, color: "#3B82F6" },
  { name: "Cost Estimate", value: 6, color: "#6366F1" },
];

type TrendPoint = { date: string; score: number };

const FALLBACK_TREND: TrendPoint[] = [
  { date: "Feb 1", score: 58 },
  { date: "Feb 3", score: 61 },
  { date: "Feb 5", score: 59 },
  { date: "Feb 7", score: 64 },
  { date: "Feb 9", score: 62 },
  { date: "Feb 11", score: 65 },
  { date: "Feb 13", score: 62 },
];

const RADIAN = Math.PI / 180;
const renderCustomizedLabel = ({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
}: any) => {
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={12}
      fontWeight={600}
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

interface RiskDriversSectionProps {
  runs?: { risk_score: number; created_at: string }[];
}

function buildTrendData(runs: { risk_score: number; created_at: string }[]): TrendPoint[] {
  const now = new Date();
  const buckets: Record<string, number[]> = {};

  for (let i = 13; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    buckets[key] = [];
  }

  for (const run of runs) {
    const key = run.created_at.slice(0, 10);
    if (key in buckets) buckets[key].push(run.risk_score);
  }

  return Object.entries(buckets)
    .filter(([, scores]) => scores.length > 0)
    .map(([key, scores]) => {
      const d = new Date(key);
      const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      return { date: label, score: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) };
    });
}

export function RiskDriversSection({ runs }: RiskDriversSectionProps) {
  const hasRealData = runs && runs.length > 0;
  const riskTrendData = hasRealData ? buildTrendData(runs) : FALLBACK_TREND;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Left: Risk Breakdown by Driver */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-3">
          <h3 className="text-lg font-semibold text-gray-900">
            Risk Breakdown by Driver
          </h3>
          <p className="mt-1 text-sm text-gray-600">
            Primary factors contributing to system risk
          </p>
        </div>

        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={riskDriversData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={renderCustomizedLabel}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {riskDriversData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#ffffff",
                  border: "1px solid #e5e7eb",
                  borderRadius: "8px",
                  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                }}
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                iconType="circle"
                wrapperStyle={{ fontSize: "12px" }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Right: Risk Trend Over Time */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-3">
          <h3 className="text-lg font-semibold text-gray-900">
            Risk Trend Over Time
          </h3>
          <p className="mt-1 text-sm text-gray-600">
            System-wide average risk score over the past 14 days
          </p>
        </div>

        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              key={hasRealData ? "real" : "fallback"}
              data={riskTrendData}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#6b7280", fontSize: 12 }}
                axisLine={{ stroke: "#d1d5db" }}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "#6b7280", fontSize: 12 }}
                axisLine={{ stroke: "#d1d5db" }}
                label={{
                  value: "Risk Score",
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
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#3B82F6"
                strokeWidth={3}
                dot={{ fill: "#3B82F6", r: 4 }}
                activeDot={{ r: 6 }}
                animationBegin={0}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}