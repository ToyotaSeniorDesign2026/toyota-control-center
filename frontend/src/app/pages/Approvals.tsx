import { useState } from "react";
import { Search, Filter, Bell, ShieldCheck } from "lucide-react";
import { Button } from "../components/ui/button";
import { ApprovalsMetrics } from "../components/approvals/ApprovalsMetrics";
import { ApprovalsTable, Approval } from "../components/approvals/ApprovalsTable";
import { ApprovalDetailDrawer } from "../components/approvals/ApprovalDetailDrawer";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import { ChevronDown } from "lucide-react";

type FilterTab = "all" | "pending-my-approval" | "approved" | "rejected" | "high-risk";

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

export default function Approvals() {
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [environmentFilter, setEnvironmentFilter] = useState("All Environments");
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null);

  // Filter approvals based on active tab
  const filteredApprovals = mockApprovals.filter((approval) => {
    if (activeTab === "pending-my-approval") {
      return approval.status === "Pending";
    }
    if (activeTab === "approved") {
      return approval.status === "Approved";
    }
    if (activeTab === "rejected") {
      return approval.status === "Rejected";
    }
    if (activeTab === "high-risk") {
      return approval.riskLevel === "High" || approval.riskLevel === "Critical";
    }
    return true; // "all" tab
  });

  // Apply search and additional filters
  const displayApprovals = filteredApprovals.filter((approval) => {
    const matchesSearch = 
      approval.resourceName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      approval.id.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesEnvironment =
      environmentFilter === "All Environments" ||
      approval.toEnvironment === environmentFilter;
    
    return matchesSearch && matchesEnvironment;
  });

  const tabs: { id: FilterTab; label: string; count?: number }[] = [
    { id: "all", label: "All", count: mockApprovals.length },
    { 
      id: "pending-my-approval", 
      label: "Pending My Approval", 
      count: mockApprovals.filter(a => a.status === "Pending").length 
    },
    { 
      id: "approved", 
      label: "Approved", 
      count: mockApprovals.filter(a => a.status === "Approved").length 
    },
    { 
      id: "rejected", 
      label: "Rejected", 
      count: mockApprovals.filter(a => a.status === "Rejected").length 
    },
    { 
      id: "high-risk", 
      label: "High Risk", 
      count: mockApprovals.filter(a => a.riskLevel === "High" || a.riskLevel === "Critical").length 
    },
  ];

  return (
    <>
      {/* Page Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Approvals</h1>
          <p className="mt-2 text-sm text-gray-600">
            Review and approve resource changes before promotion.
          </p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="mb-6 border-b border-gray-200">
        <div className="flex gap-6 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`whitespace-nowrap border-b-2 px-1 pb-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-900"
              }`}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span
                  className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${
                    activeTab === tab.id
                      ? "bg-blue-100 text-blue-600"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="mb-6">
        <ApprovalsMetrics />
      </div>

      {/* Filter & Search Bar */}
      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          {/* Left: Search and Filters */}
          <div className="flex flex-1 items-center gap-3">
            {/* Search */}
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search by resource name or approval ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Environment Filter */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50"
                >
                  {environmentFilter}
                  <ChevronDown className="h-4 w-4 text-gray-400" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-48">
                <DropdownMenuItem onClick={() => setEnvironmentFilter("All Environments")}>
                  All Environments
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setEnvironmentFilter("Dev")}>
                  Dev
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setEnvironmentFilter("Semi-Prod")}>
                  Semi-Prod
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setEnvironmentFilter("Production")}>
                  Production
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="mb-6">
        {/* Resources Needing Approval (Full Width) */}
        {displayApprovals.length > 0 ? (
          <ApprovalsTable
            approvals={displayApprovals}
            onViewApproval={setSelectedApproval}
          />
        ) : (
          /* Empty State */
          <div className="rounded-lg border border-gray-200 bg-white p-12 text-center shadow-sm">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <ShieldCheck className="h-8 w-8 text-green-600" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900">
              No pending approvals
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              All changes are up to date.
            </p>
          </div>
        )}
      </div>

      {/* Approval Detail Drawer */}
      {selectedApproval && (
        <>
          {/* Overlay */}
          <div
            className="fixed inset-0 z-40 bg-black/30"
            onClick={() => setSelectedApproval(null)}
          />
          {/* Drawer */}
          <ApprovalDetailDrawer
            approval={selectedApproval}
            onClose={() => setSelectedApproval(null)}
          />
        </>
      )}
    </>
  );
}