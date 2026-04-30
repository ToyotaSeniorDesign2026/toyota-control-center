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
  ChevronLeft,
  ChevronRight,
  Package,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { Badge } from "../ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";
import { useState, useEffect } from "react";

interface JobsTableProps {
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

function StatusBadge({ status }: { status: Job["status"] }) {
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
  const label =
    score < 30 ? "Low risk" : score < 60 ? "Medium risk" : "High risk";

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-2 cursor-help">
            <span className={`h-2 w-2 rounded-full ${color}`} />
            <span className="text-sm font-medium text-gray-700">{score}</span>
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p>{label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
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

export function JobsTable({
  searchQuery,
  typeFilter,
  statusFilter,
  riskFilter,
  activeFilter,
}: JobsTableProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const itemsPerPage = 10;

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
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-200 hover:bg-transparent">
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Job Name
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
                Schedule
              </TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Owner
              </TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedJobs.map((job) => (
              <TableRow
                key={job.id}
                className="border-gray-200 hover:bg-gray-50"
              >
                <TableCell className="font-medium text-gray-900">
                  <button className="hover:text-blue-600 transition-colors">
                    {job.name}
                  </button>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2 text-gray-700">
                    {getTypeIcon(job.type)}
                    <span className="text-sm">{job.type}</span>
                  </div>
                </TableCell>
                <TableCell className="text-gray-600">
                  {job.environment}
                </TableCell>
                <TableCell className="text-gray-600">{job.lastRun}</TableCell>
                <TableCell>
                  <StatusBadge status={job.status} />
                </TableCell>
                <TableCell>
                  <RiskScore score={job.riskScore} />
                </TableCell>
                <TableCell className="font-mono text-xs text-gray-600">
                  {job.schedule}
                </TableCell>
                <TableCell className="text-gray-600">{job.owner}</TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="rounded p-1 hover:bg-gray-100 transition-colors">
                        <MoreVertical className="h-4 w-4 text-gray-500" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem>
                        <Play className="mr-2 h-4 w-4" />
                        Run
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Edit className="mr-2 h-4 w-4" />
                        Edit
                      </DropdownMenuItem>
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
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between px-4 py-3 bg-white border-t border-gray-200 sm:px-6">
        <div className="flex-1 flex justify-between sm:hidden">
          <button
            className="relative inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            onClick={() => setCurrentPage(currentPage - 1)}
            disabled={currentPage === 1}
          >
            Previous
          </button>
          <button
            className="ml-3 relative inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            onClick={() => setCurrentPage(currentPage + 1)}
            disabled={currentPage === totalPages}
          >
            Next
          </button>
        </div>
        <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
          <div>
            <p className="text-sm text-gray-700">
              Showing{" "}
              <span className="font-medium">
                {startIndex + 1}-{endIndex}
              </span>{" "}
              of <span className="font-medium">{filteredJobs.length}</span>{" "}
              results
            </p>
          </div>
          <div>
            <nav
              className="relative z-0 inline-flex -space-x-px rounded-md shadow-sm"
              aria-label="Pagination"
            >
              <button
                className="relative inline-flex items-center px-2 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 rounded-l-md hover:bg-gray-50"
                onClick={() => setCurrentPage(currentPage - 1)}
                disabled={currentPage === 1}
              >
                <span className="sr-only">Previous</span>
                <ChevronLeft className="h-5 w-5" />
              </button>
              {Array.from({ length: totalPages }, (_, index) => (
                <button
                  key={index + 1}
                  className={`relative inline-flex items-center px-4 py-2 text-sm font-medium ${
                    currentPage === index + 1 ? "bg-blue-500 text-white" : "bg-white text-gray-500"
                  } border border-gray-300 hover:bg-gray-50`}
                  onClick={() => setCurrentPage(index + 1)}
                >
                  {index + 1}
                </button>
              ))}
              <button
                className="relative inline-flex items-center px-2 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 rounded-r-md hover:bg-gray-50"
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={currentPage === totalPages}
              >
                <span className="sr-only">Next</span>
                <ChevronRight className="h-5 w-5" />
              </button>
            </nav>
          </div>
        </div>
      </div>
    </div>
  );
}