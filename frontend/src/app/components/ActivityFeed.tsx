import {
  AlertTriangle,
  ArrowUp,
  CheckCircle2,
  ShieldAlert,
  XCircle,
} from "lucide-react";

interface ActivityItem {
  id: string;
  type: "error" | "success" | "warning" | "info";
  message: string;
  timestamp: string;
  icon: React.ReactNode;
}

const mockActivities: ActivityItem[] = [
  {
    id: "1",
    type: "error",
    message: "dbt_daily_model failed in Semi-Prod",
    timestamp: "5 min ago",
    icon: <XCircle className="h-4 w-4" />,
  },
  {
    id: "2",
    type: "success",
    message: "Agent_customer_summary promoted to Prod",
    timestamp: "15 min ago",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  {
    id: "3",
    type: "warning",
    message: "Risk score increased due to schedule change",
    timestamp: "1 hour ago",
    icon: <ArrowUp className="h-4 w-4" />,
  },
  {
    id: "4",
    type: "info",
    message: "Policy check blocked promotion",
    timestamp: "2 hours ago",
    icon: <ShieldAlert className="h-4 w-4" />,
  },
  {
    id: "5",
    type: "success",
    message: "airflow_etl_pipeline completed successfully",
    timestamp: "3 hours ago",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  {
    id: "6",
    type: "warning",
    message: "Approaching SLA threshold for revenue_dashboard",
    timestamp: "4 hours ago",
    icon: <AlertTriangle className="h-4 w-4" />,
  },
];

export function ActivityFeed() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
      </div>
      <div className="p-4">
        <div className="space-y-4">
          {mockActivities.map((activity, index) => (
            <div key={activity.id}>
              <div className="flex gap-3">
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    activity.type === "error"
                      ? "bg-red-50 text-red-600"
                      : activity.type === "success"
                      ? "bg-green-50 text-green-600"
                      : activity.type === "warning"
                      ? "bg-yellow-50 text-yellow-600"
                      : "bg-red-50 text-[#ed0923]"
                  }`}
                >
                  {activity.icon}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-gray-900">{activity.message}</p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    {activity.timestamp}
                  </p>
                </div>
              </div>
              {index < mockActivities.length - 1 && (
                <div className="ml-4 mt-4 border-t border-gray-100" />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}