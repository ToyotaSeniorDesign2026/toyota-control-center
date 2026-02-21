import { FilterType } from "../../pages/Resources";
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
import { useState } from "react";

interface ResourcesTableProps {
  searchQuery: string;
  typeFilter: string;
  statusFilter: string;
  riskFilter: string;
  activeFilter: FilterType;
}

interface Resource {
  id: string;
  name: string;
  type: "AI Agent" | "Airflow" | "dbt" | "SQL" | "BI" | "Excel" | "PowerPoint";
  environment: string;
  lastRun: string;
  status: "healthy" | "warning" | "failed";
  riskScore: number;
  schedule: string;
  owner: string;
  tags?: string[];
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
    schedule: "0 */6 * * *",
    owner: "Sarah Chen",
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
    schedule: "0 6 * * *",
    owner: "Mike Johnson",
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
    schedule: "0 */1 * * *",
    owner: "Emily Davis",
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
    schedule: "0 */2 * * *",
    owner: "David Park",
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
    schedule: "0 */12 * * *",
    owner: "Sarah Chen",
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
    schedule: "0 8 * * *",
    owner: "Mike Johnson",
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
    schedule: "0 */4 * * *",
    owner: "Emily Davis",
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
    schedule: "0 9 1 */3 *",
    owner: "David Park",
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
    schedule: "0 10 * * 1",
    owner: "Sarah Chen",
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
    schedule: "0 */3 * * *",
    owner: "David Park",
    tags: ["data", "staging"],
  },
];

function getTypeIcon(type: Resource["type"]) {
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
          No resources yet.
        </h3>
        <p className="mt-2 text-sm text-gray-600">
          Create your first AI agent or automation job to get started.
        </p>
        <button className="mt-6 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Play className="h-4 w-4" />
          Create Resource
        </button>
      </div>
    </div>
  );
}

export function ResourcesTable({
  searchQuery,
  typeFilter,
  statusFilter,
  riskFilter,
  activeFilter,
}: ResourcesTableProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Filter resources based on all criteria
  const filteredResources = mockResources.filter((resource) => {
    // Search filter
    if (
      searchQuery &&
      !resource.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !resource.owner.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !resource.tags?.some((tag) =>
        tag.toLowerCase().includes(searchQuery.toLowerCase())
      )
    ) {
      return false;
    }

    // Type filter
    if (typeFilter !== "All Types" && resource.type !== typeFilter) {
      return false;
    }

    // Status filter
    if (
      statusFilter !== "All Status" &&
      resource.status !== statusFilter.toLowerCase()
    ) {
      return false;
    }

    // Risk filter
    if (riskFilter === "Low" && resource.riskScore >= 30) return false;
    if (
      riskFilter === "Medium" &&
      (resource.riskScore < 30 || resource.riskScore >= 60)
    )
      return false;
    if (riskFilter === "High" && resource.riskScore < 60) return false;

    // Sidebar filter
    if (activeFilter === "high-risk" && resource.riskScore < 60) return false;
    if (activeFilter === "failed" && resource.status !== "failed") return false;

    return true;
  });

  // Pagination calculations
  const totalPages = Math.ceil(filteredResources.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedResources = filteredResources.slice(startIndex, endIndex);

  // Reset to page 1 when filters change
  if (currentPage > totalPages && totalPages > 0) {
    setCurrentPage(1);
  }

  if (filteredResources.length === 0 && searchQuery === "" && typeFilter === "All Types") {
    return <EmptyState />;
  }

  if (filteredResources.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-12 text-center shadow-sm">
        <p className="text-gray-600">No resources match your filters.</p>
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
                Schedule
              </TableHead>
              <TableHead className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Owner
              </TableHead>
              <TableHead className="w-12"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedResources.map((resource) => (
              <TableRow
                key={resource.id}
                className="border-gray-200 hover:bg-gray-50"
              >
                <TableCell className="font-medium text-gray-900">
                  <button className="hover:text-blue-600 transition-colors">
                    {resource.name}
                  </button>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2 text-gray-700">
                    {getTypeIcon(resource.type)}
                    <span className="text-sm">{resource.type}</span>
                  </div>
                </TableCell>
                <TableCell className="text-gray-600">
                  {resource.environment}
                </TableCell>
                <TableCell className="text-gray-600">{resource.lastRun}</TableCell>
                <TableCell>
                  <StatusBadge status={resource.status} />
                </TableCell>
                <TableCell>
                  <RiskScore score={resource.riskScore} />
                </TableCell>
                <TableCell className="font-mono text-xs text-gray-600">
                  {resource.schedule}
                </TableCell>
                <TableCell className="text-gray-600">{resource.owner}</TableCell>
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
              of <span className="font-medium">{filteredResources.length}</span>{" "}
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