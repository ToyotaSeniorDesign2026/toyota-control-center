import { Filter, Plus, Search } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "./ui/table";

interface Resource {
  id: string;
  name: string;
  type: string;
  environment: string;
  lastRun: string;
  status: "healthy" | "warning" | "failed";
  riskScore: number;
  owner: string;
}

const mockResources: Resource[] = [
  {
    id: "1",
    name: "customer_churn_predictor",
    type: "AI Agent",
    environment: "Prod",
    lastRun: "5 min ago",
    status: "healthy",
    riskScore: 12,
    owner: "Sarah Chen",
  },
  {
    id: "2",
    name: "dbt_daily_model",
    type: "dbt",
    environment: "Semi-Prod",
    lastRun: "1 hour ago",
    status: "failed",
    riskScore: 78,
    owner: "Mike Johnson",
  },
  {
    id: "3",
    name: "revenue_dashboard",
    type: "BI",
    environment: "Prod",
    lastRun: "30 min ago",
    status: "healthy",
    riskScore: 8,
    owner: "Emily Davis",
  },
  {
    id: "4",
    name: "airflow_etl_pipeline",
    type: "Airflow",
    environment: "Prod",
    lastRun: "15 min ago",
    status: "warning",
    riskScore: 45,
    owner: "David Park",
  },
  {
    id: "5",
    name: "customer_summary_agent",
    type: "AI Agent",
    environment: "Dev",
    lastRun: "2 hours ago",
    status: "healthy",
    riskScore: 15,
    owner: "Sarah Chen",
  },
  {
    id: "6",
    name: "sales_forecast_query",
    type: "SQL",
    environment: "Prod",
    lastRun: "45 min ago",
    status: "healthy",
    riskScore: 22,
    owner: "Mike Johnson",
  },
  {
    id: "7",
    name: "inventory_optimizer",
    type: "AI Agent",
    environment: "Semi-Prod",
    lastRun: "3 hours ago",
    status: "warning",
    riskScore: 52,
    owner: "Emily Davis",
  },
  {
    id: "8",
    name: "dbt_staging_models",
    type: "dbt",
    environment: "Dev",
    lastRun: "10 min ago",
    status: "healthy",
    riskScore: 10,
    owner: "David Park",
  },
];

function StatusBadge({ status }: { status: Resource["status"] }) {
  const variants = {
    healthy: "bg-green-50 text-green-700 border-green-200",
    warning: "bg-yellow-50 text-yellow-700 border-yellow-200",
    failed: "bg-red-50 text-red-700 border-red-200",
  };

  const labels = {
    healthy: "Healthy",
    warning: "Warning",
    failed: "Failed",
  };

  return (
    <Badge variant="outline" className={`${variants[status]} border`}>
      {labels[status]}
    </Badge>
  );
}

function RiskScore({ score }: { score: number }) {
  const color =
    score < 30 ? "bg-green-500" : score < 60 ? "bg-yellow-500" : "bg-red-500";

  return (
    <div className="flex items-center gap-2">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      <span className="text-sm text-gray-700">{score}</span>
    </div>
  );
}

export function ResourcesTable() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-900">My Resources</h2>
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search resources..."
              className="h-9 w-64 rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
            />
          </div>
          {/* Filter */}
          <Button variant="outline" className="h-9 gap-2">
            <Filter className="h-4 w-4" />
            Filter
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-200 hover:bg-transparent">
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Resource Name
              </TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Type
              </TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Environment
              </TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Last Run
              </TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Status
              </TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Risk Score
              </TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Owner
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {mockResources.map((resource) => (
              <TableRow
                key={resource.id}
                className="border-gray-200 hover:bg-gray-50"
              >
                <TableCell className="font-medium text-gray-900">
                  {resource.name}
                </TableCell>
                <TableCell className="text-gray-600">{resource.type}</TableCell>
                <TableCell className="text-gray-600">
                  {resource.environment}
                </TableCell>
                <TableCell className="text-gray-600">
                  {resource.lastRun}
                </TableCell>
                <TableCell>
                  <StatusBadge status={resource.status} />
                </TableCell>
                <TableCell>
                  <RiskScore score={resource.riskScore} />
                </TableCell>
                <TableCell className="text-gray-600">{resource.owner}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}