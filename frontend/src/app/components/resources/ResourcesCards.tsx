import { FilterType } from "../../pages/Jobs";
import { formatSchedule } from "../../lib/formatSchedule";
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
import { useState, useEffect } from "react";

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
  type: string;
  environment: string;
  lastRun: string;
  status: "healthy" | "warning" | "failed";
  riskScore: number;
  schedule: string;
  owner: string;
  tags?: string[];
  last_run_at?: string;
  last_run_status?: string;
  risk_level?: string;
  owner_name?: string;
}

// Helper function to convert API response to UI Job format
function mapApiJobToUIJob(apiJob: any): Job {
  const riskScore = apiJob.risk_score ?? 0;
  const riskLevel = riskScore < 30 ? "low" : riskScore < 60 ? "medium" : "high";
  const status = 
    apiJob.last_run_status?.toLowerCase() === "failed"
      ? "failed"
      : apiJob.last_run_status?.toLowerCase() === "succeeded"
      ? "healthy"
      : "warning";

  return {
    id: apiJob.id,
    name: apiJob.name,
    type: apiJob.type,
    environment: apiJob.environment,
    lastRun: apiJob.last_run_at || "Never",
    status,
    riskScore,
    schedule: "", // Not available from API
    owner: apiJob.owner_name || "Unknown",
    tags: apiJob.tags || [],
    last_run_at: apiJob.last_run_at,
    last_run_status: apiJob.last_run_status,
    risk_level: riskLevel,
    owner_name: apiJob.owner_name,
  };
}

// Helper function to convert API response to UI Job format
function getTypeIcon(type: string) {
  const typeMap: Record<string, JSX.Element> = {
    "ai-agent": <Bot className="h-4 w-4" />,
    "AI Agent": <Bot className="h-4 w-4" />,
    airflow: <Workflow className="h-4 w-4" />,
    Airflow: <Workflow className="h-4 w-4" />,
    dbt: <Database className="h-4 w-4" />,
    sql: <Code className="h-4 w-4" />,
    SQL: <Code className="h-4 w-4" />,
    bi: <BarChart3 className="h-4 w-4" />,
    BI: <BarChart3 className="h-4 w-4" />,
    excel: <FileSpreadsheet className="h-4 w-4" />,
    Excel: <FileSpreadsheet className="h-4 w-4" />,
    powerpoint: <Presentation className="h-4 w-4" />,
    PowerPoint: <Presentation className="h-4 w-4" />,
  };
  return typeMap[type] || <Code className="h-4 w-4" />;
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
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const itemsPerPage = 6;

  // Fetch jobs from API on component mount
  useEffect(() => {
    const fetchJobs = async () => {
      try {
        setLoading(true);
        const token = typeof window !== "undefined" ? window.localStorage.getItem("control-center-auth-token") : null;
        const headers: HeadersInit = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        const response = await fetch("http://localhost:8000/jobs", {
          headers,
        });
        if (!response.ok) {
          throw new Error("Failed to fetch jobs");
        }
        const data = await response.json();
        const uiJobs = data.items.map(mapApiJobToUIJob);
        setJobs(uiJobs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    fetchJobs();
  }, []);

  // Filter jobs based on all criteria
  const filteredJobs = jobs.filter((job) => {
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
    if (activeFilter === "needs-approval") {
      // This would require backend to return approval status at job level
      // For now, this filter is prepared but needs Job model update
    }
    if (activeFilter === "recent") {
      // Check if updated in last 24 hours
      if (!job.last_run_at) return false;
      const lastRunTime = new Date(job.last_run_at).getTime();
      const now = new Date().getTime();
      const twentyFourHoursMs = 24 * 60 * 60 * 1000;
      if (now - lastRunTime > twentyFourHoursMs) return false;
    }

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

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-12 text-center shadow-sm">
        <p className="text-gray-600">Loading jobs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-12 text-center shadow-sm">
        <p className="text-red-600">Error loading jobs: {error}</p>
      </div>
    );
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
                  <span className="font-medium">Schedule:</span> {formatSchedule(job.schedule)}
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