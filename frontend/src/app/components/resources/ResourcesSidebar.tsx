import { FilterType } from "../../pages/Resources";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  XCircle,
} from "lucide-react";

interface ResourcesSidebarProps {
  activeFilter: FilterType;
  onFilterChange: (filter: FilterType) => void;
}

export function ResourcesSidebar({
  activeFilter,
  onFilterChange,
}: ResourcesSidebarProps) {
  const filters = [
    { id: "all" as FilterType, label: "All Resources", icon: FileText, count: 148 },
    { id: "high-risk" as FilterType, label: "High Risk", icon: AlertTriangle, count: 12 },
    { id: "failed" as FilterType, label: "Failed", icon: XCircle, count: 3 },
    { id: "needs-approval" as FilterType, label: "Needs Approval", icon: Clock, count: 7 },
    { id: "recent" as FilterType, label: "Recently Updated", icon: FileText, count: 18 },
  ];

  return (
    <aside className="w-56 shrink-0">
      <div className="rounded-lg border border-gray-200 bg-white p-2 shadow-sm">
        <nav className="space-y-1">
          {filters.map((filter) => {
            const Icon = filter.icon;
            return (
              <button
                key={filter.id}
                onClick={() => onFilterChange(filter.id)}
                className={`flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  activeFilter === filter.id
                    ? "bg-red-50 text-[#b8071c]"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4" />
                  {filter.label}
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    activeFilter === filter.id
                      ? "bg-red-100 text-[#b8071c]"
                      : "bg-gray-100 text-gray-600"
                  }`}
                >
                  {filter.count}
                </span>
              </button>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}