import { ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "../ui/button";
import { useState } from "react";

export interface Approval {
  id: string;
  resourceName: string;
  changeType: "Create" | "Update" | "Delete" | "Promote";
  fromEnvironment: string;
  toEnvironment: string;
  riskScore: number;
  riskLevel: "Low" | "Medium" | "High" | "Critical";
  submittedBy: string;
  submittedAt: string;
  status: "Pending" | "Approved" | "Rejected" | "Needs Changes";
}

interface ApprovalsTableProps {
  approvals: Approval[];
  onViewApproval: (approval: Approval) => void;
}

const mockApprovals: Approval[] = [
  {
    id: "APR-2024-1847",
    resourceName: "customer_segmentation_model",
    changeType: "Promote",
    fromEnvironment: "Semi-Prod",
    toEnvironment: "Production",
    riskScore: 87,
    riskLevel: "High",
    submittedBy: "Sarah Chen",
    submittedAt: "2024-02-13T10:30:00Z",
    status: "Pending",
  },
  {
    id: "APR-2024-1846",
    resourceName: "etl_customer_data_pipeline",
    changeType: "Update",
    fromEnvironment: "Dev",
    toEnvironment: "Dev",
    riskScore: 92,
    riskLevel: "Critical",
    submittedBy: "Mike Johnson",
    submittedAt: "2024-02-13T09:15:00Z",
    status: "Pending",
  },
  {
    id: "APR-2024-1845",
    resourceName: "sales_forecast_dbt",
    changeType: "Create",
    fromEnvironment: "Dev",
    toEnvironment: "Semi-Prod",
    riskScore: 45,
    riskLevel: "Medium",
    submittedBy: "Emily Zhang",
    submittedAt: "2024-02-12T16:45:00Z",
    status: "Approved",
  },
  {
    id: "APR-2024-1844",
    resourceName: "user_retention_agent",
    changeType: "Promote",
    fromEnvironment: "Dev",
    toEnvironment: "Production",
    riskScore: 78,
    riskLevel: "High",
    submittedBy: "David Kim",
    submittedAt: "2024-02-12T14:20:00Z",
    status: "Pending",
  },
  {
    id: "APR-2024-1843",
    resourceName: "legacy_reporting_sql",
    changeType: "Delete",
    fromEnvironment: "Production",
    toEnvironment: "Production",
    riskScore: 65,
    riskLevel: "Medium",
    submittedBy: "Lisa Brown",
    submittedAt: "2024-02-12T11:00:00Z",
    status: "Rejected",
  },
  {
    id: "APR-2024-1842",
    resourceName: "inventory_sync_airflow",
    changeType: "Update",
    fromEnvironment: "Semi-Prod",
    toEnvironment: "Semi-Prod",
    riskScore: 38,
    riskLevel: "Low",
    submittedBy: "Tom Wilson",
    submittedAt: "2024-02-11T15:30:00Z",
    status: "Approved",
  },
];

const statusColors = {
  Pending: {
    bg: "bg-blue-50",
    text: "text-blue-700",
    border: "border-blue-200",
    dot: "bg-blue-500",
  },
  Approved: {
    bg: "bg-green-50",
    text: "text-green-700",
    border: "border-green-200",
    dot: "bg-green-500",
  },
  Rejected: {
    bg: "bg-red-50",
    text: "text-red-700",
    border: "border-red-200",
    dot: "bg-red-500",
  },
  "Needs Changes": {
    bg: "bg-yellow-50",
    text: "text-yellow-700",
    border: "border-yellow-200",
    dot: "bg-yellow-500",
  },
};

const riskLevelColors = {
  Low: {
    bg: "bg-green-50",
    text: "text-green-700",
    dot: "bg-green-500",
  },
  Medium: {
    bg: "bg-yellow-50",
    text: "text-yellow-700",
    dot: "bg-yellow-500",
  },
  High: {
    bg: "bg-orange-50",
    text: "text-orange-700",
    dot: "bg-orange-500",
  },
  Critical: {
    bg: "bg-red-50",
    text: "text-red-700",
    dot: "bg-red-500",
  },
};

const changeTypeColors = {
  Create: "text-blue-600",
  Update: "text-purple-600",
  Delete: "text-red-600",
  Promote: "text-green-600",
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60));
  
  if (diffInHours < 1) {
    return "Just now";
  } else if (diffInHours < 24) {
    return `${diffInHours}h ago`;
  } else if (diffInHours < 48) {
    return "Yesterday";
  } else {
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }
}

export function ApprovalsTable({ approvals, onViewApproval }: ApprovalsTableProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const displayApprovals = approvals.length > 0 ? approvals : mockApprovals;

  // Pagination calculations
  const totalPages = Math.ceil(displayApprovals.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedApprovals = displayApprovals.slice(startIndex, endIndex);

  // Reset to page 1 when filters change
  if (currentPage > totalPages && totalPages > 0) {
    setCurrentPage(1);
  }

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const maxVisiblePages = 5;
    
    if (totalPages <= maxVisiblePages) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);
      
      if (currentPage > 3) {
        pages.push('...');
      }
      
      // Show current page and surrounding pages
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);
      
      for (let i = start; i <= end; i++) {
        pages.push(i);
      }
      
      if (currentPage < totalPages - 2) {
        pages.push('...');
      }
      
      // Always show last page
      pages.push(totalPages);
    }
    
    return pages;
  };

  return (
    <>
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Approval ID
                </th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Resource Name
                </th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Environment Flow
                </th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Risk
                </th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Submitted By
                </th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Submitted
                </th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {paginatedApprovals.map((approval) => {
                const statusColor = statusColors[approval.status];
                const riskColor = riskLevelColors[approval.riskLevel];
                const changeColor = changeTypeColors[approval.changeType];

                return (
                  <tr
                    key={approval.id}
                    className="group hover:bg-gray-50 transition-colors cursor-pointer"
                    onClick={() => onViewApproval(approval)}
                  >
                    <td className="px-4 py-2.5">
                      <div className="text-sm font-mono font-medium text-blue-600">
                        {approval.id}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="text-sm font-medium text-gray-900">
                        {approval.resourceName}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-medium text-gray-700">
                          {approval.fromEnvironment}
                        </span>
                        <ArrowRight className="h-3 w-3 text-gray-400" />
                        <span className="font-medium text-gray-700">
                          {approval.toEnvironment}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${riskColor.dot}`} />
                        <span className="text-sm font-medium text-gray-900">
                          {approval.riskScore}
                        </span>
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-medium ${riskColor.bg} ${riskColor.text}`}
                        >
                          {approval.riskLevel}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="text-sm text-gray-700">
                        {approval.submittedBy}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="text-sm text-gray-600">
                        {formatDate(approval.submittedAt)}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${statusColor.dot}`} />
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-medium ${statusColor.bg} ${statusColor.text}`}
                        >
                          {approval.status}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      <div className="flex items-center justify-between px-4 py-3 bg-white border-t border-gray-200 sm:px-6">
        <div className="flex-1 flex justify-between sm:hidden">
          <Button
            variant="ghost"
            size="sm"
            className="relative inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            onClick={() => setCurrentPage(currentPage - 1)}
            disabled={currentPage === 1}
          >
            <ChevronLeft className="h-5 w-5" />
            Previous
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="relative inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            onClick={() => setCurrentPage(currentPage + 1)}
            disabled={currentPage === totalPages}
          >
            Next
            <ChevronRight className="h-5 w-5" />
          </Button>
        </div>
        <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
          <div>
            <p className="text-sm text-gray-700">
              Showing
              <span className="font-medium"> {startIndex + 1} </span>
              to
              <span className="font-medium"> {endIndex} </span>
              of
              <span className="font-medium"> {displayApprovals.length} </span>
              results
            </p>
          </div>
          <div>
            <nav className="relative z-0 inline-flex shadow-sm -space-x-px" aria-label="Pagination">
              <Button
                variant="ghost"
                size="sm"
                className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                onClick={() => setCurrentPage(currentPage - 1)}
                disabled={currentPage === 1}
              >
                <ChevronLeft className="h-5 w-5" />
              </Button>
              {getPageNumbers().map((page) => {
                if (page === '...') {
                  return (
                    <span key={page} className="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">
                      {page}
                    </span>
                  );
                }
                return (
                  <Button
                    key={page}
                    variant="ghost"
                    size="sm"
                    className={`relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium ${currentPage === page ? 'text-blue-600' : 'text-gray-500'} hover:bg-gray-50`}
                    onClick={() => setCurrentPage(page as number)}
                  >
                    {page}
                  </Button>
                );
              })}
              <Button
                variant="ghost"
                size="sm"
                className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50"
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={currentPage === totalPages}
              >
                <ChevronRight className="h-5 w-5" />
              </Button>
            </nav>
          </div>
        </div>
      </div>
    </>
  );
}