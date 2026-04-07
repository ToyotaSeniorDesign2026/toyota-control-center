import { FilterType } from "../../pages/Jobs";
import {
  MoreVertical,
  Play,
  Edit,
  FileText,
  ArrowUpCircle,
  Eye,
  Trash2,
  Bot,
  Database,
  BarChart3,
  Code,
  FileSpreadsheet,
  Presentation,
  Workflow,
  Package,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Badge } from "../ui/badge";
import { Avatar, AvatarFallback } from "../ui/avatar";
import { useState } from "react";

interface JobsCardsProps {
  searchQuery: string;
  typeFilter: string;
  statusFilter: string;
  riskFilter: string;
  activeFilter: FilterType;
}

interface Job {
  id: string;
  name: string;
  type: "AI Agent" | "Airflow" | "dbt" | "SQL" | "BI" | "Excel" | "PowerPoint";
  environment: string;
  lastRun: string;
  status: "healthy" | "warning" | "failed";
  riskScore: number;
  schedule: string;
  owner: string;
  ownerInitials: string;
  tags?: string[];
}

const mockJobs: Job[] = [
  {
    id: "1",
    name: "customer_churn_predictor",
    type: "AI Agent",
    environment: "Prod",
    lastRun: "5 min ago",
    status: "healthy",
    riskScore: 12,
    schedule: "Every 6 hours",
    owner: "Sarah Chen",
    ownerInitials: "SC",
    tags: ["ml", "customer"],
  },
  {
    id: "2",
    name: "dbt_daily_model",
    type: "dbt",
    environment: "Semi-Prod",
    lastRun: "1 hour ago",
    status: "failed",
    riskScore: 78,
    schedule: "Daily at 6am",
    owner: "Mike Johnson",
    ownerInitials: "MJ",
    tags: ["data", "etl"],
  },
  {
    id: "3",
    name: "revenue_dashboard",
    type: "BI",
    environment: "Prod",
    lastRun: "30 min ago",
    status: "healthy",
    riskScore: 8,
    schedule: "Every hour",
    owner: "Emily Davis",
    ownerInitials: "ED",
    tags: ["reporting"],
  },
  {
    id: "4",
    name: "airflow_etl_pipeline",
    type: "Airflow",
    environment: "Prod",
    lastRun: "15 min ago",
    status: "warning",
    riskScore: 45,
    schedule: "Every 2 hours",
    owner: "David Park",
    ownerInitials: "DP",
    tags: ["pipeline"],
  },
  {
    id: "5",
    name: "customer_summary_agent",
    type: "AI Agent",
    environment: "Dev",
    lastRun: "2 hours ago",
    status: "healthy",
    riskScore: 15,
    schedule: "Every 12 hours",
    owner: "Sarah Chen",
    ownerInitials: "SC",
    tags: ["ml", "summary"],
  },
  {
    id: "6",
    name: "sales_forecast_query",
    type: "SQL",
    environment: "Prod",
    lastRun: "45 min ago",
    status: "healthy",
    riskScore: 22,
    schedule: "Daily at 8am",
    owner: "Mike Johnson",
    ownerInitials: "MJ",
    tags: ["analytics"],
  },
  {
    id: "7",
    name: "inventory_optimizer",
    type: "AI Agent",
    environment: "Semi-Prod",
    lastRun: "3 hours ago",
    status: "warning",
    riskScore: 52,
    schedule: "Every 4 hours",
    owner: "Emily Davis",
    ownerInitials: "ED",
    tags: ["ml", "optimization"],
  },
  {
    id: "8",
    name: "quarterly_report_deck",
    type: "PowerPoint",
    environment: "Prod",
    lastRun: "1 day ago",
    status: "healthy",
    riskScore: 5,
    schedule: "Quarterly",
    owner: "David Park",
    ownerInitials: "DP",
    tags: ["reporting"],
  },
  {
    id: "9",
    name: "financial_model_spreadsheet",
    type: "Excel",
    environment: "Prod",
    lastRun: "2 hours ago",
    status: "healthy",
    riskScore: 18,
    schedule: "Weekly Mon",
    owner: "Sarah Chen",
    ownerInitials: "SC",
    tags: ["finance"],
  },
  {
    id: "10",
    name: "dbt_staging_models",
    type: "dbt",
    environment: "Dev",
    lastRun: "10 min ago",
    status: "healthy",
    riskScore: 10,
    schedule: "Every 3 hours",
    owner: "David Park",
    ownerInitials: "DP",
    tags: ["data", "staging"],
  },
];

function getTypeIcon(type: Job["type"]) {
  switch (type) {
    case "AI Agent":
      return <Bot className="h-4 w-4" />;
    case "Airflow":
      return <Workflow className="h-4 w-4" />;
    case "dbt":
      return <Database className="h-4 w-4" />;
    case "SQL":
      return <Code className="h-4 w-4" />;
    case "BI":
      return <BarChart3 className="h-4 w-4" />;
    case "Excel":
      return <FileSpreadsheet className="h-4 w-4" />;
    case "PowerPoint":
      return <Presentation className="h-4 w-4" />;
  }
}

function getTypeColor(type: Job["type"]) {
  switch (type) {
    case "AI Agent":
      return "bg-purple-100 text-purple-700";
    case "Airflow":
      return "bg-blue-100 text-blue-700";
    case "dbt":
      return "bg-green-100 text-green-700";
    case "SQL":
      return "bg-indigo-100 text-indigo-700";
    case "BI":
      return "bg-orange-100 text-orange-700";
    case "Excel":
      return "bg-teal-100 text-teal-700";
    case "PowerPoint":
      return "bg-pink-100 text-pink-700";
  }
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="flex flex-col items-center justify-center py-16">
        <div className="rounded-full bg-gray-100 p-4">
          <Package className="h-12 w-12 text-gray-400" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-gray-900">
          No jobs yet.
        </h3>
        <p className="mt-2 text-sm text-gray-600">
          Create your first AI agent or automation job to get started.
        </p>
        <button className="mt-6 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Play className="h-4 w-4" />
          Create Job
        </button>
      </div>
    </div>
  );
}

export function JobsCards({
  searchQuery,
  typeFilter,
  statusFilter,
  riskFilter,
  activeFilter,
}: JobsCardsProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 6;

  // Filter jobs based on all criteria
  const filteredJobs = mockJobs.filter((job) => {
    // Search filter
    if (
      searchQuery &&
      !job.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !job.owner.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !job.tags?.some((tag) =>
        tag.toLowerCase().includes(searchQuery.toLowerCase())
      )
    ) {
      return false;
    }

    // Type filter
    if (typeFilter !== "All Types" && job.type !== typeFilter) {
      return false;
    }

    // Status filter
    if (
      statusFilter !== "All Status" &&
      job.status !== statusFilter.toLowerCase()
    ) {
      return false;
    }

    // Risk filter
    if (riskFilter === "Low" && job.riskScore >= 30) return false;
    if (
      riskFilter === "Medium" &&
      (job.riskScore < 30 || job.riskScore >= 60)
    )
      return false;
    if (riskFilter === "High" && job.riskScore < 60) return false;

    // Sidebar filter
    if (activeFilter === "high-risk" && job.riskScore < 60) return false;
    if (activeFilter === "failed" && job.status !== "failed") return false;

    return true;
  });

  // Pagination calculations
  const totalPages = Math.ceil(filteredJobs.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedJobs = filteredJobs.slice(startIndex, endIndex);

  // Reset to page 1 when filters change
  if (currentPage > totalPages && totalPages > 0) {
    setCurrentPage(1);
  }

  if (filteredJobs.length === 0 && searchQuery === "" && typeFilter === "All Types") {
    return <EmptyState />;
  }

  if (filteredJobs.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-12 text-center shadow-sm">
        <p className="text-gray-600">No jobs match your filters.</p>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {paginatedJobs.map((job) => {
          const statusColor =
            job.status === "healthy"
              ? "bg-green-500"
              : job.status === "warning"
              ? "bg-yellow-500"
              : "bg-red-500";

          const riskColor =
            job.riskScore < 30
              ? "bg-green-50 text-green-700 border-green-200"
              : job.riskScore < 60
              ? "bg-yellow-50 text-yellow-700 border-yellow-200"
              : "bg-red-50 text-red-700 border-red-200";

          return (
            <div
              key={job.id}
              className="group relative rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              {/* Status Indicator */}
              <div className="absolute right-4 top-4">
                <span className={`h-2 w-2 rounded-full ${statusColor}`} />
              </div>

              {/* Type Badge */}
              <div
                className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium ${getTypeColor(
                  job.type
                )}`}
              >
                {getTypeIcon(job.type)}
                {job.type}
              </div>

              {/* Job Name */}
              <h3 className="mt-3 font-semibold text-gray-900 group-hover:text-blue-600 transition-colors cursor-pointer">
                {job.name}
              </h3>

              {/* Environment */}
              <p className="mt-1 text-xs text-gray-500">{job.environment}</p>

              {/* Risk Score */}
              <div className="mt-3">
                <Badge variant="outline" className={`${riskColor} border`}>
                  Risk: {job.riskScore}
                </Badge>
              </div>

              {/* Schedule & Last Run */}
              <div className="mt-4 space-y-1 border-t border-gray-100 pt-4">
                <p className="text-xs text-gray-600">
                  <span className="font-medium">Schedule:</span> {job.schedule}
                </p>
                <p className="text-xs text-gray-600">
                  <span className="font-medium">Last run:</span> {job.lastRun}
                </p>
              </div>

              {/* Owner & Actions */}
              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Avatar className="h-6 w-6">
                    <AvatarFallback className="bg-gray-200 text-xs text-gray-700">
                      {job.ownerInitials}
                    </AvatarFallback>
                  </Avatar>
                  <span className="text-xs text-gray-600">{job.owner}</span>
                </div>

                <div className="flex items-center gap-1">
                  <button className="rounded p-1 hover:bg-gray-100 transition-colors">
                    <Play className="h-4 w-4 text-gray-500" />
                  </button>
                  <button className="rounded p-1 hover:bg-gray-100 transition-colors">
                    <Edit className="h-4 w-4 text-gray-500" />
                  </button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="rounded p-1 hover:bg-gray-100 transition-colors">
                        <MoreVertical className="h-4 w-4 text-gray-500" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem>
                        <FileText className="mr-2 h-4 w-4" />
                        View Logs
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <ArrowUpCircle className="mr-2 h-4 w-4" />
                        Promote
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Eye className="mr-2 h-4 w-4" />
                        View Spec
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem className="text-red-600 focus:text-red-600">
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center">
          <button
            className="mr-2 rounded p-1 hover:bg-gray-100 transition-colors"
            onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-gray-500">
            Page {currentPage} of {totalPages}
          </span>
          <button
            className="ml-2 rounded p-1 hover:bg-gray-100 transition-colors"
            onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
            disabled={currentPage === totalPages}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </>
  );
}