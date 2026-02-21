import { Eye, AlertCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Button } from "../ui/button";

export interface RiskResource {
  id: string;
  name: string;
  type: "AI Agent" | "Airflow" | "dbt" | "SQL" | "BI";
  environment: "Dev" | "Semi-Prod" | "Production";
  riskScore: number;
  riskLevel: "Low" | "Medium" | "High" | "Critical";
  primaryDriver: string;
  owner: string;
  lastModified: string;
  approvalRequired: boolean;
}

interface HighRiskResourcesTableProps {
  resources: RiskResource[];
  onViewDetails: (resource: RiskResource) => void;
}

const mockResources: RiskResource[] = [
  {
    id: "RES-1847",
    name: "customer_pii_extraction_agent",
    type: "AI Agent",
    environment: "Production",
    riskScore: 92,
    riskLevel: "Critical",
    primaryDriver: "Data Sensitivity",
    owner: "Sarah Chen",
    lastModified: "2024-02-13T10:30:00Z",
    approvalRequired: true,
  },
  {
    id: "RES-1846",
    name: "realtime_fraud_detection",
    type: "Airflow",
    environment: "Production",
    riskScore: 88,
    riskLevel: "High",
    primaryDriver: "External Egress",
    owner: "Mike Johnson",
    lastModified: "2024-02-13T09:15:00Z",
    approvalRequired: true,
  },
  {
    id: "RES-1845",
    name: "financial_reporting_transform",
    type: "dbt",
    environment: "Production",
    riskScore: 85,
    riskLevel: "High",
    primaryDriver: "Data Sensitivity",
    owner: "Emily Zhang",
    lastModified: "2024-02-12T16:45:00Z",
    approvalRequired: true,
  },
  {
    id: "RES-1844",
    name: "high_frequency_market_data",
    type: "SQL",
    environment: "Semi-Prod",
    riskScore: 78,
    riskLevel: "High",
    primaryDriver: "Schedule Changes",
    owner: "David Kim",
    lastModified: "2024-02-12T14:20:00Z",
    approvalRequired: false,
  },
  {
    id: "RES-1843",
    name: "customer_analytics_dashboard",
    type: "BI",
    environment: "Production",
    riskScore: 72,
    riskLevel: "High",
    primaryDriver: "Connector Usage",
    owner: "Lisa Brown",
    lastModified: "2024-02-12T11:00:00Z",
    approvalRequired: false,
  },
  {
    id: "RES-1842",
    name: "ml_training_pipeline",
    type: "Airflow",
    environment: "Semi-Prod",
    riskScore: 68,
    riskLevel: "Medium",
    primaryDriver: "Cost Increase",
    owner: "Tom Wilson",
    lastModified: "2024-02-11T15:30:00Z",
    approvalRequired: false,
  },
];

const riskLevelColors = {
  Low: {
    bg: "bg-green-50",
    text: "text-green-700",
    dot: "bg-green-500",
    border: "border-green-200",
  },
  Medium: {
    bg: "bg-yellow-50",
    text: "text-yellow-700",
    dot: "bg-yellow-500",
    border: "border-yellow-200",
  },
  High: {
    bg: "bg-orange-50",
    text: "text-orange-700",
    dot: "bg-orange-500",
    border: "border-orange-200",
  },
  Critical: {
    bg: "bg-red-50",
    text: "text-red-700",
    dot: "bg-red-500",
    border: "border-red-200",
  },
};

const typeColors = {
  "AI Agent": "text-purple-600",
  Airflow: "text-blue-600",
  dbt: "text-orange-600",
  SQL: "text-green-600",
  BI: "text-pink-600",
};

const envColors = {
  Dev: "bg-gray-100 text-gray-700",
  "Semi-Prod": "bg-blue-100 text-blue-700",
  Production: "bg-purple-100 text-purple-700",
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInHours = Math.floor(
    (now.getTime() - date.getTime()) / (1000 * 60 * 60)
  );

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

export function HighRiskResourcesTable({
  resources,
  onViewDetails,
}: HighRiskResourcesTableProps) {
  const displayResources = resources.length > 0 ? resources : mockResources;
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const totalPages = Math.ceil(displayResources.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedResources = displayResources.slice(startIndex, endIndex);

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
        <h3 className="text-lg font-semibold text-gray-900">
          High-Risk Resources
        </h3>
        <p className="mt-1 text-sm text-gray-600">
          Resources with elevated risk scores requiring attention
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Resource Name
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Type
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Environment
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Risk Score
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Primary Driver
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Owner
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Last Modified
              </th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Approval
              </th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {paginatedResources.map((resource) => {
              const riskColor = riskLevelColors[resource.riskLevel];
              const typeColor = typeColors[resource.type];
              const envColor = envColors[resource.environment];

              return (
                <tr
                  key={resource.id}
                  className={`group hover:bg-gray-50 transition-colors cursor-pointer ${
                    resource.riskLevel === "Critical" || resource.riskLevel === "High"
                      ? "bg-red-50/30"
                      : ""
                  }`}
                  onClick={() => onViewDetails(resource)}
                >
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      {resource.approvalRequired && (
                        <AlertCircle className="h-4 w-4 text-orange-500" />
                      )}
                      <div className="text-sm font-medium text-gray-900">
                        {resource.name}
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className={`text-sm font-medium ${typeColor}`}>
                      {resource.type}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex rounded px-2 py-1 text-xs font-medium ${envColor}`}
                    >
                      {resource.environment}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <div className={`h-2 w-2 rounded-full ${riskColor.dot}`} />
                      <span className="text-sm font-bold text-gray-900">
                        {resource.riskScore}
                      </span>
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-medium ${riskColor.bg} ${riskColor.text}`}
                      >
                        {resource.riskLevel}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="text-sm text-gray-700">
                      {resource.primaryDriver}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="text-sm text-gray-700">{resource.owner}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="text-sm text-gray-600">
                      {formatDate(resource.lastModified)}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex rounded px-2 py-1 text-xs font-medium ${
                        resource.approvalRequired
                          ? "bg-orange-100 text-orange-700"
                          : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {resource.approvalRequired ? "Required" : "Not Required"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => {
                        e.stopPropagation();
                        onViewDetails(resource);
                      }}
                    >
                      <Eye className="h-4 w-4 mr-1" />
                      View
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3">
          <div className="text-sm text-gray-600">
            Showing {startIndex + 1} to {Math.min(endIndex, displayResources.length)} of{" "}
            {displayResources.length} resources
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                <button
                  key={page}
                  onClick={() => setCurrentPage(page)}
                  className={`h-8 w-8 rounded-md text-sm font-medium transition-colors ${
                    currentPage === page
                      ? "bg-[#ed0923] text-white"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  {page}
                </button>
              ))}
            </div>
            <button
              onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
