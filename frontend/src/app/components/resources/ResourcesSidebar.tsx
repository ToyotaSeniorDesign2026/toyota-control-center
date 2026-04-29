import { FilterType } from "../../pages/Jobs";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  XCircle,
} from "lucide-react";
import { useState, useEffect } from "react";

interface JobsSidebarProps {
  activeFilter: FilterType;
  onFilterChange: (filter: FilterType) => void;
}

interface Counts {
  all: number;
  high_risk: number;
  failed: number;
  needs_approval: number;
  recently_updated: number;
}

export function JobsSidebar({
  activeFilter,
  onFilterChange,
}: JobsSidebarProps) {
  const [counts, setCounts] = useState<Counts>({
    all: 0,
    high_risk: 0,
    failed: 0,
    needs_approval: 0,
    recently_updated: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCounts = async () => {
      try {
        const token = typeof window !== "undefined" ? window.localStorage.getItem("control-center-auth-token") : null;
        const headers: HeadersInit = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        const response = await fetch(
          "http://localhost:8000/analytics/jobs/counts",
          {
            headers,
          }
        );
        if (!response.ok) {
          throw new Error("Failed to fetch counts");
        }
        const data = await response.json();
        setCounts(data);
      } catch (err) {
        console.error("Error fetching counts:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchCounts();
  }, []);

  const filters = [
    { id: "all" as FilterType, label: "All Jobs", icon: FileText, count: counts.all },
    { id: "high-risk" as FilterType, label: "High Risk", icon: AlertTriangle, count: counts.high_risk },
    { id: "failed" as FilterType, label: "Failed", icon: XCircle, count: counts.failed },
    { id: "needs-approval" as FilterType, label: "Needs Approval", icon: Clock, count: counts.needs_approval },
    { id: "recent" as FilterType, label: "Recently Updated", icon: FileText, count: counts.recently_updated },
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