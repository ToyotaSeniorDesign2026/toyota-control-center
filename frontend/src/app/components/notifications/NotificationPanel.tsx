import { X, AlertTriangle, XCircle, Shield, AlertCircle, CheckCircle, Clock } from "lucide-react";
import { Button } from "../ui/button";

interface NotificationPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface Notification {
  id: string;
  type: "critical" | "warning" | "info";
  category: "risk" | "job" | "violation" | "approval" | "system";
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

export function NotificationPanel({ isOpen, onClose }: NotificationPanelProps) {
  // Mock notifications data
  const notifications: Notification[] = [
    {
      id: "1",
      type: "critical",
      category: "risk",
      title: "Critical Risk Detected",
      message: "Resource 'prod-api-gateway' has exceeded critical risk threshold (score: 8.7/10)",
      timestamp: "2 minutes ago",
      read: false,
    },
    {
      id: "2",
      type: "critical",
      category: "job",
      title: "Job Execution Failed",
      message: "Job 'daily-data-sync' failed with exit code 1. View logs for details.",
      timestamp: "15 minutes ago",
      read: false,
    },
    {
      id: "3",
      type: "warning",
      category: "violation",
      title: "Policy Violation Detected",
      message: "Resource modified without approval in production environment",
      timestamp: "1 hour ago",
      read: false,
    },
    {
      id: "4",
      type: "warning",
      category: "approval",
      title: "Approval Request Pending",
      message: "3 high-priority changes awaiting your approval",
      timestamp: "2 hours ago",
      read: true,
    },
    {
      id: "5",
      type: "critical",
      category: "job",
      title: "Multiple Job Failures",
      message: "5 jobs failed in the last hour. System performance may be degraded.",
      timestamp: "3 hours ago",
      read: true,
    },
    {
      id: "6",
      type: "warning",
      category: "risk",
      title: "Elevated Risk Score",
      message: "Resource 'user-database' risk score increased from 4.2 to 6.8",
      timestamp: "5 hours ago",
      read: true,
    },
    {
      id: "7",
      type: "info",
      category: "system",
      title: "System Maintenance Scheduled",
      message: "Scheduled maintenance window: Feb 15, 2:00 AM - 4:00 AM UTC",
      timestamp: "1 day ago",
      read: true,
    },
  ];

  const unreadCount = notifications.filter(n => !n.read).length;

  const getNotificationIcon = (type: string, category: string) => {
    if (category === "risk") {
      return <Shield className="h-4 w-4" />;
    }
    if (category === "violation") {
      return <AlertTriangle className="h-4 w-4" />;
    }
    if (category === "job") {
      return <XCircle className="h-4 w-4" />;
    }
    if (category === "approval") {
      return <Clock className="h-4 w-4" />;
    }
    return <AlertCircle className="h-4 w-4" />;
  };

  const getNotificationColor = (type: string) => {
    switch (type) {
      case "critical":
        return "bg-red-50 border-red-200 text-red-700";
      case "warning":
        return "bg-yellow-50 border-yellow-200 text-yellow-700";
      case "info":
        return "bg-blue-50 border-blue-200 text-blue-700";
      default:
        return "bg-gray-50 border-gray-200 text-gray-700";
    }
  };

  const getIconColor = (type: string) => {
    switch (type) {
      case "critical":
        return "text-red-600";
      case "warning":
        return "text-yellow-600";
      case "info":
        return "text-blue-600";
      default:
        return "text-gray-600";
    }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 z-50 h-full w-full max-w-lg bg-white shadow-2xl flex flex-col">
        {/* Header */}
        <div className="sticky top-0 border-b border-gray-200 bg-white px-6 py-4 z-10">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                Notifications
              </h2>
              {unreadCount > 0 && (
                <p className="mt-0.5 text-sm text-gray-600">
                  {unreadCount} unread notification{unreadCount !== 1 ? 's' : ''}
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Action Buttons */}
          {unreadCount > 0 && (
            <div className="mt-3 flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs"
              >
                Mark all as read
              </Button>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full px-6 py-12 text-center">
              <CheckCircle className="h-12 w-12 text-gray-400 mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                All caught up!
              </h3>
              <p className="text-sm text-gray-600">
                You don't have any notifications at the moment.
              </p>
            </div>
          ) : (
            <div className="p-4 space-y-3">
              {notifications.map((notification) => (
                <div
                  key={notification.id}
                  className={`rounded-lg border p-4 transition-all hover:shadow-sm cursor-pointer ${
                    notification.read
                      ? "bg-white border-gray-200"
                      : getNotificationColor(notification.type)
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`mt-0.5 ${notification.read ? 'text-gray-400' : getIconColor(notification.type)}`}>
                      {getNotificationIcon(notification.type, notification.category)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <h4 className={`text-sm font-semibold ${
                            notification.read ? 'text-gray-900' : 'text-gray-900'
                          }`}>
                            {notification.title}
                          </h4>
                          {!notification.read && (
                            <span className="flex h-2 w-2 rounded-full bg-blue-500" />
                          )}
                        </div>
                      </div>
                      <p className={`mt-1 text-sm ${
                        notification.read ? 'text-gray-600' : 'text-gray-700'
                      }`}>
                        {notification.message}
                      </p>
                      <div className="mt-2 flex items-center gap-3">
                        <span className="text-xs text-gray-500">
                          {notification.timestamp}
                        </span>
                        <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${
                          notification.type === "critical"
                            ? "bg-red-100 text-red-700"
                            : notification.type === "warning"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-blue-100 text-blue-700"
                        }`}>
                          {notification.category.charAt(0).toUpperCase() + notification.category.slice(1)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 border-t border-gray-200 bg-white px-6 py-4">
          <Button
            variant="outline"
            className="w-full text-sm"
          >
            View All Notifications
          </Button>
        </div>
      </div>
    </>
  );
}
