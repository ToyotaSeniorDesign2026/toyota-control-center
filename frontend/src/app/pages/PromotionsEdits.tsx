import { useState } from "react";
import { ArrowUpCircle, Clock, XCircle, CheckCircle2, Edit } from "lucide-react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { Button } from "../components/ui/button";
import { RevisionModal } from "../components/RevisionModal";

interface Resource {
  id: string;
  name: string;
  type: "AI Agent" | "SQL Query" | "dbt Model" | "API Connection";
  status: "approved" | "pending_promotion" | "rejected" | "promoted";
  currentEnvironment: string;
  targetEnvironment?: string;
  createdAt: string;
  lastModified?: string;
  rejectionReason?: string;
  description?: string;
}

const mockReadyForPromotion: Resource[] = [
  {
    id: "RES-001",
    name: "customer_data_analysis",
    type: "SQL Query",
    status: "approved",
    currentEnvironment: "Dev",
    createdAt: "2024-02-20T10:00:00Z",
    description: "SQL query to analyze customer behavior patterns and churn risk factors.",
  },
  {
    id: "RES-002",
    name: "sales_forecasting_agent",
    type: "AI Agent",
    status: "approved",
    currentEnvironment: "Staging",
    createdAt: "2024-02-19T14:30:00Z",
    description: "AI-powered agent that analyzes historical sales data to predict future revenue trends.",
  },
  {
    id: "RES-003",
    name: "inventory_transform",
    type: "dbt Model",
    status: "approved",
    currentEnvironment: "Dev",
    createdAt: "2024-02-18T09:15:00Z",
    description: "dbt transformation model that processes raw inventory data from multiple warehouses.",
  },
];

const mockPendingPromotions: Resource[] = [
  {
    id: "RES-006",
    name: "revenue_dashboard_query",
    type: "SQL Query",
    status: "pending_promotion",
    currentEnvironment: "Staging",
    targetEnvironment: "Production",
    createdAt: "2024-02-19T10:00:00Z",
    lastModified: "2024-02-20T14:00:00Z",
    description: "Query for executive revenue dashboard with YoY comparisons.",
  },
  {
    id: "RES-007",
    name: "support_ticket_classifier",
    type: "AI Agent",
    status: "pending_promotion",
    currentEnvironment: "Staging",
    targetEnvironment: "Production",
    createdAt: "2024-02-18T16:00:00Z",
    lastModified: "2024-02-20T12:30:00Z",
    description: "ML model to automatically classify and route support tickets.",
  },
];

const mockRejectedPromotions: Resource[] = [
  {
    id: "RES-008",
    name: "customer_sentiment_agent",
    type: "AI Agent",
    status: "rejected",
    currentEnvironment: "Dev",
    targetEnvironment: "Production",
    createdAt: "2024-02-17T11:30:00Z",
    lastModified: "2024-02-19T15:00:00Z",
    rejectionReason: "Missing comprehensive error handling and logging requirements for production deployment.",
    description: "NLP agent to analyze customer sentiment from support tickets.",
  },
  {
    id: "RES-009",
    name: "financial_reporting_query",
    type: "SQL Query",
    status: "rejected",
    currentEnvironment: "Staging",
    targetEnvironment: "Production",
    createdAt: "2024-02-16T08:45:00Z",
    lastModified: "2024-02-19T10:00:00Z",
    rejectionReason: "Query performance does not meet production SLA requirements. Needs optimization.",
    description: "Comprehensive financial reporting query for executive dashboard.",
  },
];

const mockRecentlyPromoted: Resource[] = [
  {
    id: "RES-010",
    name: "user_analytics_model",
    type: "dbt Model",
    status: "promoted",
    currentEnvironment: "Production",
    targetEnvironment: "Production",
    createdAt: "2024-02-15T09:00:00Z",
    lastModified: "2024-02-19T16:00:00Z",
    description: "User behavior analytics transformation model.",
  },
];

export default function PromotionsEdits() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedResources, setSelectedResources] = useState<string[]>([]);
  const [revisionResource, setRevisionResource] = useState<Resource | null>(null);
  const [isRevisionModalOpen, setIsRevisionModalOpen] = useState(false);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
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

  const handleToggleSelection = (resourceId: string) => {
    setSelectedResources((prev) =>
      prev.includes(resourceId)
        ? prev.filter((id) => id !== resourceId)
        : [...prev, resourceId]
    );
  };

  const handleRequestPromotion = () => {
    console.log("Requesting promotion for:", selectedResources);
    // Handle promotion request
    setSelectedResources([]);
  };

  const handleRevise = (resource: Resource) => {
    setRevisionResource(resource);
    setIsRevisionModalOpen(true);
  };

  const handleCloseRevisionModal = () => {
    setIsRevisionModalOpen(false);
    setTimeout(() => setRevisionResource(null), 300);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Promotions & Edits"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          {/* Page Header */}
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Promotions & Edits</h1>
            <p className="mt-1 text-sm text-gray-600">
              Manage resource promotions, track approval status, and revise rejected resources
            </p>
          </div>

          {/* Ready for Promotion Section */}
          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <ArrowUpCircle className="h-5 w-5 text-blue-600" />
                    <h3 className="font-semibold text-gray-900">Ready for Promotion</h3>
                  </div>
                  <p className="mt-1 text-xs text-gray-600">
                    Select resources to promote to production
                  </p>
                </div>
                {selectedResources.length > 0 && (
                  <Button
                    onClick={handleRequestPromotion}
                    className="gap-2 bg-[#ed0923] text-white hover:bg-[#d10820]"
                  >
                    <ArrowUpCircle className="h-4 w-4" />
                    Request Promotion ({selectedResources.length})
                  </Button>
                )}
              </div>
            </div>
            <div className="divide-y divide-gray-200">
              {mockReadyForPromotion.map((resource) => (
                <div
                  key={resource.id}
                  className="p-6 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start gap-4">
                    <input
                      type="checkbox"
                      checked={selectedResources.includes(resource.id)}
                      onChange={() => handleToggleSelection(resource.id)}
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-[#ed0923] focus:ring-[#ed0923]"
                    />
                    <div className="flex-1">
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <div className="font-semibold text-gray-900">
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
                        <span className="rounded bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">
                          {resource.currentEnvironment}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">
                        {resource.description}
                      </p>
                      <div className="text-xs text-gray-500">
                        Created: {formatDate(resource.createdAt)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Grid for Pending and Rejected */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* Pending Promotions */}
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-yellow-600" />
                  <h3 className="font-semibold text-gray-900">Pending Promotions</h3>
                </div>
                <p className="mt-1 text-xs text-gray-600">
                  {mockPendingPromotions.length} awaiting approval
                </p>
              </div>
              <div className="divide-y divide-gray-200">
                {mockPendingPromotions.map((resource) => (
                  <div key={resource.id} className="p-4">
                    <div className="mb-2">
                      <div className="font-medium text-gray-900 text-sm mb-1">
                        {resource.name}
                      </div>
                      <div
                        className={`text-xs font-medium ${getTypeColor(
                          resource.type
                        )}`}
                      >
                        {resource.type}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="rounded bg-blue-100 px-2 py-1 text-xs font-medium text-blue-700">
                        {resource.currentEnvironment}
                      </span>
                      <span className="text-xs text-gray-400">→</span>
                      <span className="rounded bg-green-100 px-2 py-1 text-xs font-medium text-green-700">
                        {resource.targetEnvironment}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500">
                      Requested: {formatDate(resource.lastModified || resource.createdAt)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Rejected Promotions */}
            <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
              <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <XCircle className="h-5 w-5 text-red-600" />
                  <h3 className="font-semibold text-gray-900">Rejected Promotions</h3>
                </div>
                <p className="mt-1 text-xs text-gray-600">
                  {mockRejectedPromotions.length} need revision
                </p>
              </div>
              <div className="divide-y divide-gray-200">
                {mockRejectedPromotions.map((resource) => (
                  <div key={resource.id} className="p-4">
                    <div className="mb-2">
                      <div className="font-medium text-gray-900 text-sm mb-1">
                        {resource.name}
                      </div>
                      <div
                        className={`text-xs font-medium ${getTypeColor(
                          resource.type
                        )}`}
                      >
                        {resource.type}
                      </div>
                    </div>
                    {resource.rejectionReason && (
                      <div className="rounded-lg bg-red-50 border border-red-200 p-3 mb-3">
                        <p className="text-xs text-red-800">
                          <span className="font-semibold">Reason: </span>
                          {resource.rejectionReason}
                        </p>
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-gray-500">
                        Rejected: {formatDate(resource.lastModified || resource.createdAt)}
                      </div>
                      <Button
                        onClick={() => handleRevise(resource)}
                        variant="outline"
                        size="sm"
                        className="gap-2 text-[#ed0923] border-[#ed0923] hover:bg-red-50"
                      >
                        <Edit className="h-3 w-3" />
                        Revise
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recently Promoted Section */}
          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                <h3 className="font-semibold text-gray-900">Recently Promoted</h3>
              </div>
              <p className="mt-1 text-xs text-gray-600">
                Successfully promoted to production
              </p>
            </div>
            <div className="divide-y divide-gray-200">
              {mockRecentlyPromoted.map((resource) => (
                <div key={resource.id} className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="font-medium text-gray-900 text-sm mb-1">
                        {resource.name}
                      </div>
                      <div
                        className={`text-xs font-medium ${getTypeColor(
                          resource.type
                        )}`}
                      >
                        {resource.type}
                      </div>
                      <p className="text-xs text-gray-600 mt-2">
                        {resource.description}
                      </p>
                    </div>
                    <span className="rounded bg-green-100 px-3 py-1 text-xs font-medium text-green-700">
                      {resource.currentEnvironment}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    Promoted: {formatDate(resource.lastModified || resource.createdAt)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>

      <UserProfilePanel
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />

      <RevisionModal
        resource={revisionResource}
        isOpen={isRevisionModalOpen}
        onClose={handleCloseRevisionModal}
      />
    </div>
  );
}
