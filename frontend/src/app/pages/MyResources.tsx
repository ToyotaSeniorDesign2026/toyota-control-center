import { useState } from "react";
import { Clock, CheckCircle, PlayCircle } from "lucide-react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { ResourceDetailModal } from "../components/ResourceDetailModal";

interface Resource {
  id: string;
  name: string;
  type: "AI Agent" | "SQL Query" | "dbt Model" | "API Connection";
  status: "pending" | "approved" | "running" | "completed";
  createdAt: string;
  environment?: string;
  description?: string;
  logs?: Array<{ timestamp: string; message: string; level: "info" | "warning" | "error" }>;
  policyChecks?: Array<{ name: string; status: "passed" | "failed" | "warning"; message: string }>;
}

const mockMyResources: Resource[] = [
  {
    id: "RES-001",
    name: "customer_data_analysis",
    type: "SQL Query",
    status: "approved",
    createdAt: "2024-02-20T10:00:00Z",
    environment: "Dev",
    description: "SQL query to analyze customer behavior patterns, identify churn risk factors, and generate actionable insights for the marketing team. This query joins customer transaction data with demographic information and calculates key metrics.",
    logs: [
      { timestamp: "2024-02-20T10:05:00Z", message: "Query validation completed successfully", level: "info" },
      { timestamp: "2024-02-20T10:03:00Z", message: "Performing security scan", level: "info" },
      { timestamp: "2024-02-20T10:01:00Z", message: "Resource created and queued for approval", level: "info" },
    ],
    policyChecks: [
      { name: "Data Access Policy", status: "passed", message: "User has appropriate permissions for queried tables" },
      { name: "PII Compliance", status: "passed", message: "No direct PII fields accessed" },
      { name: "Query Complexity", status: "warning", message: "Query execution time may exceed 30 seconds" },
    ],
  },
  {
    id: "RES-002",
    name: "sales_forecasting_agent",
    type: "AI Agent",
    status: "approved",
    createdAt: "2024-02-19T14:30:00Z",
    environment: "Dev",
    description: "AI-powered agent that analyzes historical sales data to predict future revenue trends. Uses machine learning models to identify seasonal patterns, market trends, and generate weekly forecasts with confidence intervals.",
    logs: [
      { timestamp: "2024-02-19T14:45:00Z", message: "Model training completed with 94% accuracy", level: "info" },
      { timestamp: "2024-02-19T14:35:00Z", message: "Initializing ML pipeline", level: "info" },
      { timestamp: "2024-02-19T14:31:00Z", message: "Agent configuration validated", level: "info" },
    ],
    policyChecks: [
      { name: "Model Governance", status: "passed", message: "Model meets bias and fairness standards" },
      { name: "Data Lineage", status: "passed", message: "All data sources properly documented" },
      { name: "Resource Limits", status: "passed", message: "Compute and memory allocation within limits" },
    ],
  },
  {
    id: "RES-003",
    name: "inventory_transform",
    type: "dbt Model",
    status: "approved",
    createdAt: "2024-02-18T09:15:00Z",
    environment: "Dev",
    description: "dbt transformation model that processes raw inventory data from multiple warehouses and creates clean, normalized tables for analytics. Includes data quality checks and incremental loading logic.",
    logs: [
      { timestamp: "2024-02-18T09:25:00Z", message: "Model compiled successfully", level: "info" },
      { timestamp: "2024-02-18T09:20:00Z", message: "Dependencies resolved", level: "info" },
      { timestamp: "2024-02-18T09:16:00Z", message: "Model registered in catalog", level: "info" },
    ],
    policyChecks: [
      { name: "Schema Validation", status: "passed", message: "Output schema matches specifications" },
      { name: "Data Quality", status: "passed", message: "All quality tests passed" },
      { name: "Documentation", status: "passed", message: "Model fully documented" },
    ],
  },
];

const mockPendingApprovals: Resource[] = [
  {
    id: "RES-004",
    name: "customer_sentiment_agent",
    type: "AI Agent",
    status: "pending",
    createdAt: "2024-02-20T11:30:00Z",
    description: "Natural language processing agent to analyze customer support tickets and social media mentions. Classifies sentiment as positive, negative, or neutral and identifies trending issues.",
    logs: [
      { timestamp: "2024-02-20T11:32:00Z", message: "Awaiting admin approval", level: "info" },
      { timestamp: "2024-02-20T11:31:00Z", message: "Policy checks completed", level: "info" },
      { timestamp: "2024-02-20T11:30:00Z", message: "Resource submitted for review", level: "info" },
    ],
    policyChecks: [
      { name: "External API Access", status: "warning", message: "Requires approval for third-party API connections" },
      { name: "Data Classification", status: "passed", message: "Handles only non-sensitive customer feedback" },
      { name: "Cost Estimation", status: "passed", message: "Estimated monthly cost: $120" },
    ],
  },
  {
    id: "RES-005",
    name: "financial_reporting_query",
    type: "SQL Query",
    status: "pending",
    createdAt: "2024-02-20T08:45:00Z",
    description: "Comprehensive SQL query to generate monthly financial reports including revenue, expenses, profit margins, and year-over-year comparisons for executive dashboard.",
    logs: [
      { timestamp: "2024-02-20T08:47:00Z", message: "Security review in progress", level: "info" },
      { timestamp: "2024-02-20T08:46:00Z", message: "Query complexity analyzed", level: "warning" },
      { timestamp: "2024-02-20T08:45:00Z", message: "Submitted for approval", level: "info" },
    ],
    policyChecks: [
      { name: "Financial Data Access", status: "warning", message: "Requires CFO approval for financial table access" },
      { name: "Query Performance", status: "passed", message: "Estimated execution time: 12 seconds" },
      { name: "Audit Logging", status: "passed", message: "All accesses will be logged" },
    ],
  },
];

const mockRunningResources: Resource[] = [
  {
    id: "RES-001",
    name: "customer_data_analysis",
    type: "SQL Query",
    status: "running",
    createdAt: "2024-02-20T10:00:00Z",
    environment: "Dev",
    description: "SQL query to analyze customer behavior patterns, identify churn risk factors, and generate actionable insights for the marketing team. This query joins customer transaction data with demographic information and calculates key metrics.",
    logs: [
      { timestamp: "2024-02-20T15:22:00Z", message: "Processing 2.3M records", level: "info" },
      { timestamp: "2024-02-20T15:20:00Z", message: "Query execution started", level: "info" },
      { timestamp: "2024-02-20T15:19:00Z", message: "Connection to database established", level: "info" },
    ],
    policyChecks: [
      { name: "Data Access Policy", status: "passed", message: "User has appropriate permissions for queried tables" },
      { name: "PII Compliance", status: "passed", message: "No direct PII fields accessed" },
      { name: "Query Complexity", status: "warning", message: "Query execution time may exceed 30 seconds" },
    ],
  },
  {
    id: "RES-002",
    name: "sales_forecasting_agent",
    type: "AI Agent",
    status: "running",
    createdAt: "2024-02-19T14:30:00Z",
    environment: "Dev",
    description: "AI-powered agent that analyzes historical sales data to predict future revenue trends. Uses machine learning models to identify seasonal patterns, market trends, and generate weekly forecasts with confidence intervals.",
    logs: [
      { timestamp: "2024-02-20T15:25:00Z", message: "Generating forecast for Q2 2024", level: "info" },
      { timestamp: "2024-02-20T15:20:00Z", message: "Model inference in progress", level: "info" },
      { timestamp: "2024-02-20T15:18:00Z", message: "Agent execution triggered", level: "info" },
    ],
    policyChecks: [
      { name: "Model Governance", status: "passed", message: "Model meets bias and fairness standards" },
      { name: "Data Lineage", status: "passed", message: "All data sources properly documented" },
      { name: "Resource Limits", status: "passed", message: "Compute and memory allocation within limits" },
    ],
  },
];

export default function MyResources() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  const handleResourceClick = (resource: Resource) => {
    setSelectedResource(resource);
    setIsDetailModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsDetailModalOpen(false);
    setTimeout(() => setSelectedResource(null), 300);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-yellow-100 text-yellow-700 border-yellow-200";
      case "approved":
        return "bg-green-100 text-green-700 border-green-200";
      case "running":
        return "bg-blue-100 text-blue-700 border-blue-200";
      case "completed":
        return "bg-gray-100 text-gray-700 border-gray-200";
      default:
        return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case "AI Agent":
        return "text-purple-600";
      case "SQL Query":
        return "text-green-600";
      case "dbt Model":
        return "text-orange-600";
      case "API Connection":
        return "text-blue-600";
      default:
        return "text-gray-600";
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation 
        activePage="My Resources"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          {/* Page Header */}
          <div>
            <h1 className="text-3xl font-bold text-gray-900">My Resources</h1>
            <p className="mt-1 text-sm text-gray-600">
              View and manage your created resources, approvals, and running jobs
            </p>
          </div>

          {/* Three Column Grid */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* My Resources */}
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  <h3 className="font-semibold text-gray-900">My Resources</h3>
                </div>
                <p className="mt-1 text-xs text-gray-600">
                  {mockMyResources.length} total resources
                </p>
              </div>
              <div className="divide-y divide-gray-200">
                {mockMyResources.map((resource) => (
                  <div 
                    key={resource.id} 
                    className="p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => handleResourceClick(resource)}
                  >
                    <div className="mb-2 flex items-start justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-gray-900 text-sm">
                          {resource.name}
                        </div>
                        <div
                          className={`mt-1 text-xs font-medium ${getTypeColor(
                            resource.type
                          )}`}
                        >
                          {resource.type}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">
                        {formatDate(resource.createdAt)}
                      </span>
                      {resource.environment && (
                        <span className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
                          {resource.environment}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Pending Approvals */}
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-yellow-600" />
                  <h3 className="font-semibold text-gray-900">Pending Approvals</h3>
                </div>
                <p className="mt-1 text-xs text-gray-600">
                  {mockPendingApprovals.length} awaiting admin review
                </p>
              </div>
              <div className="divide-y divide-gray-200">
                {mockPendingApprovals.map((resource) => (
                  <div 
                    key={resource.id} 
                    className="p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => handleResourceClick(resource)}
                  >
                    <div className="mb-2 flex items-start justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-gray-900 text-sm">
                          {resource.name}
                        </div>
                        <div
                          className={`mt-1 text-xs font-medium ${getTypeColor(
                            resource.type
                          )}`}
                        >
                          {resource.type}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">
                        {formatDate(resource.createdAt)}
                      </span>
                      <span
                        className={`rounded border px-2 py-1 text-xs font-medium ${getStatusColor(
                          resource.status
                        )}`}
                      >
                        Pending
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Running Resources */}
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <PlayCircle className="h-5 w-5 text-blue-600" />
                  <h3 className="font-semibold text-gray-900">Running Resources</h3>
                </div>
                <p className="mt-1 text-xs text-gray-600">
                  {mockRunningResources.length} currently active
                </p>
              </div>
              <div className="divide-y divide-gray-200">
                {mockRunningResources.map((resource) => (
                  <div 
                    key={resource.id} 
                    className="p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => handleResourceClick(resource)}
                  >
                    <div className="mb-2 flex items-start justify-between">
                      <div className="flex-1">
                        <div className="font-medium text-gray-900 text-sm">
                          {resource.name}
                        </div>
                        <div
                          className={`mt-1 text-xs font-medium ${getTypeColor(
                            resource.type
                          )}`}
                        >
                          {resource.type}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">
                        {formatDate(resource.createdAt)}
                      </span>
                      <div className="flex items-center gap-2">
                        {resource.environment && (
                          <span className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">
                            {resource.environment}
                          </span>
                        )}
                        <div className="flex items-center gap-1">
                          <div className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
                          <span className="text-xs font-medium text-blue-700">
                            Running
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
      
      <UserProfilePanel 
        isOpen={isProfileOpen} 
        onClose={() => setIsProfileOpen(false)} 
      />
      
      <ResourceDetailModal 
        resource={selectedResource}
        isOpen={isDetailModalOpen}
        onClose={handleCloseModal}
      />
    </div>
  );
}