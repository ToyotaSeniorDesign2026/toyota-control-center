import { X, Calendar, Server, Activity, FileText, Shield, Clock } from "lucide-react";
import { Button } from "./ui/button";

interface Job {
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

interface JobDetailModalProps {
  job: Job | null;
  isOpen: boolean;
  onClose: () => void;
}

export function JobDetailModal({ job, isOpen, onClose }: JobDetailModalProps) {
  if (!isOpen || !job) return null;

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
        return "text-purple-600 bg-purple-50";
      case "SQL Query":
        return "text-green-600 bg-green-50";
      case "dbt Model":
        return "text-orange-600 bg-orange-50";
      case "API Connection":
        return "text-blue-600 bg-blue-50";
      default:
        return "text-gray-600 bg-gray-50";
    }
  };

  const getPolicyStatusColor = (status: string) => {
    switch (status) {
      case "passed":
        return "text-green-700 bg-green-50 border-green-200";
      case "failed":
        return "text-red-700 bg-red-50 border-red-200";
      case "warning":
        return "text-yellow-700 bg-yellow-50 border-yellow-200";
      default:
        return "text-gray-700 bg-gray-50 border-gray-200";
    }
  };

  const getLogLevelColor = (level: string) => {
    switch (level) {
      case "error":
        return "text-red-600";
      case "warning":
        return "text-yellow-600";
      case "info":
        return "text-blue-600";
      default:
        return "text-gray-600";
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatLogTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="relative w-full max-w-4xl max-h-[90vh] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl">
        {/* Header */}
        <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-semibold text-gray-900">{job.name}</h2>
                <span className={`rounded-full px-3 py-1 text-xs font-medium ${getTypeColor(job.type)}`}>
                  {job.type}
                </span>
                <span className={`rounded border px-3 py-1 text-xs font-medium ${getStatusColor(job.status)}`}>
                  {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                </span>
              </div>
              <p className="mt-1 text-sm text-gray-600">Job ID: {job.id}</p>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="overflow-y-auto max-h-[calc(90vh-200px)] p-6 space-y-6">
          {/* Description */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <FileText className="h-5 w-5 text-gray-400" />
              <h3 className="font-semibold text-gray-900">Description</h3>
            </div>
            <p className="text-sm text-gray-700 leading-relaxed">
              {job.description || "No description provided."}
            </p>
          </div>

          {/* Job Details Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Calendar className="h-4 w-4 text-gray-400" />
                <span className="text-xs font-medium text-gray-600">Created</span>
              </div>
              <p className="text-sm font-semibold text-gray-900">{formatDate(job.createdAt)}</p>
            </div>

            {job.environment && (
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Server className="h-4 w-4 text-gray-400" />
                  <span className="text-xs font-medium text-gray-600">Environment</span>
                </div>
                <p className="text-sm font-semibold text-gray-900">{job.environment}</p>
              </div>
            )}

            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="h-4 w-4 text-gray-400" />
                <span className="text-xs font-medium text-gray-600">Status</span>
              </div>
              <p className="text-sm font-semibold text-gray-900">
                {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
              </p>
            </div>

            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="h-4 w-4 text-gray-400" />
                <span className="text-xs font-medium text-gray-600">Type</span>
              </div>
              <p className="text-sm font-semibold text-gray-900">{job.type}</p>
            </div>
          </div>

          {/* Policy Checks */}
          {job.policyChecks && job.policyChecks.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Shield className="h-5 w-5 text-gray-400" />
                <h3 className="font-semibold text-gray-900">Policy Checks</h3>
              </div>
              <div className="space-y-2">
                {job.policyChecks.map((check, index) => (
                  <div
                    key={index}
                    className={`rounded-lg border p-3 ${getPolicyStatusColor(check.status)}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium">{check.name}</span>
                      <span className="text-xs font-semibold uppercase">
                        {check.status}
                      </span>
                    </div>
                    <p className="text-xs">{check.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Logs/History */}
          {job.logs && job.logs.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Clock className="h-5 w-5 text-gray-400" />
                <h3 className="font-semibold text-gray-900">Recent Activity</h3>
              </div>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 max-h-60 overflow-y-auto space-y-2">
                {job.logs.map((log, index) => (
                  <div key={index} className="flex items-start gap-3 text-sm">
                    <span className="text-xs text-gray-500 font-mono min-w-[80px]">
                      {formatLogTime(log.timestamp)}
                    </span>
                    <span className={`text-xs font-semibold uppercase min-w-[60px] ${getLogLevelColor(log.level)}`}>
                      {log.level}
                    </span>
                    <span className="text-xs text-gray-700 flex-1">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 bg-gray-50 px-6 py-4">
          <div className="flex justify-end">
            <Button
              onClick={onClose}
              className="bg-[#ed0923] text-white hover:bg-[#d10820]"
            >
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
