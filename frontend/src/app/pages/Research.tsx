import {
  ArrowDown,
  ArrowUp,
  Calendar,
  Download,
  TrendingUp,
} from "lucide-react";
import { Button } from "../components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import { ChevronDown } from "lucide-react";
import { InsightMetrics } from "../components/research/InsightMetrics";
import { AutomationTrendsChart } from "../components/research/AutomationTrendsChart";
import { RiskDistribution } from "../components/research/RiskDistribution";
import { ProductivityImpact } from "../components/research/ProductivityImpact";
import { EnvironmentComparison } from "../components/research/EnvironmentComparison";
import { TopPerformingResources } from "../components/research/TopPerformingResources";

export default function Research() {
  return (
    <>
      {/* Page Header */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">
            Research & Insights
          </h1>
          <p className="mt-1 text-sm text-gray-600">
            Visibility into automation usage, performance trends, and system
            risk.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Date Range Selector */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                className="h-9 gap-2 border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                <Calendar className="h-4 w-4" />
                Last 7 days
                <ChevronDown className="h-4 w-4 text-gray-400" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem>Last 7 days</DropdownMenuItem>
              <DropdownMenuItem>Last 30 days</DropdownMenuItem>
              <DropdownMenuItem>Last 90 days</DropdownMenuItem>
              <DropdownMenuItem>Custom range</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Export Button */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                className="h-9 gap-2 border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                <Download className="h-4 w-4" />
                Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-32">
              <DropdownMenuItem>Export CSV</DropdownMenuItem>
              <DropdownMenuItem>Export PDF</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Insight Summary Cards */}
      <div className="mb-4">
        <InsightMetrics />
      </div>

      {/* Automation Trends Chart */}
      <div className="mb-4">
        <AutomationTrendsChart />
      </div>

      {/* Risk Distribution */}
      <div className="mb-4">
        <RiskDistribution />
      </div>

      {/* Productivity Impact */}
      <div className="mb-4">
        <ProductivityImpact />
      </div>

      {/* Environment Comparison */}
      <div className="mb-4">
        <EnvironmentComparison />
      </div>

      {/* Top Performing Resources */}
      <div>
        <TopPerformingResources />
      </div>
    </>
  );
}