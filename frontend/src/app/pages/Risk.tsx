import { useState } from "react";
import { Download, Calendar } from "lucide-react";
import { Button } from "../components/ui/button";
import { RiskMetrics } from "../components/risk/RiskMetrics";
import { RiskDistributionChart } from "../components/risk/RiskDistributionChart";
import { RiskDriversSection } from "../components/risk/RiskDriversSection";
import { HighRiskResourcesTable, RiskResource } from "../components/risk/HighRiskResourcesTable";
import { RiskDetailDrawer } from "../components/risk/RiskDetailDrawer";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import { ChevronDown } from "lucide-react";

export default function Risk() {
  const [dateRange, setDateRange] = useState("Last 7 Days");
  const [selectedResource, setSelectedResource] = useState<RiskResource | null>(null);

  return (
    <>
      {/* Page Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Risk & Governance</h1>
          <p className="mt-1 text-sm text-gray-600">
            Visibility into system-wide risk, policy enforcement, and environment safety.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Date Range Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50"
              >
                <Calendar className="h-4 w-4" />
                {dateRange}
                <ChevronDown className="h-4 w-4 text-gray-400" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem onClick={() => setDateRange("Last 7 Days")}>
                Last 7 Days
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setDateRange("Last 14 Days")}>
                Last 14 Days
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setDateRange("Last 30 Days")}>
                Last 30 Days
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setDateRange("Last 90 Days")}>
                Last 90 Days
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Export Button */}
          <Button
            variant="outline"
            className="h-9 gap-2 border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Download className="h-4 w-4" />
            Export Risk Report
          </Button>
        </div>
      </div>

      {/* Top Risk Summary Metrics */}
      <div className="mb-4">
        <RiskMetrics />
      </div>

      {/* Risk Distribution Chart */}
      <div className="mb-4">
        <RiskDistributionChart />
      </div>

      {/* Risk Drivers Section (2 Column Grid) */}
      <div className="mb-4">
        <RiskDriversSection />
      </div>

      {/* High-Risk Resources Table */}
      <div className="mb-4">
        <HighRiskResourcesTable
          resources={[]}
          onViewDetails={setSelectedResource}
        />
      </div>

      {/* Risk Detail Drawer */}
      {selectedResource && (
        <>
          {/* Overlay */}
          <div
            className="fixed inset-0 z-40 bg-black/30"
            onClick={() => setSelectedResource(null)}
          />
          {/* Drawer */}
          <RiskDetailDrawer
            resource={selectedResource}
            onClose={() => setSelectedResource(null)}
          />
        </>
      )}
    </>
  );
}