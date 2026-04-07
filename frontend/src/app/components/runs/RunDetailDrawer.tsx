import { Run } from "../../pages/Runs";
import { X, Clock, AlertCircle, Play } from "lucide-react";
import { Button } from "../ui/button";
import { useState } from "react";
import {
  Bot,
  Database,
  BarChart3,
  Code,
  FileSpreadsheet,
  Presentation,
  Workflow,
} from "lucide-react";

interface RunDetailDrawerProps {
  run: Run | null;
  open: boolean;
  onClose: () => void;
}

function getTypeIcon(type: Run["type"]) {
  switch (type) {
    case "AI Agent":
      return <Bot className="h-5 w-5" />;
    case "Airflow":
      return <Workflow className="h-5 w-5" />;
    case "dbt":
      return <Database className="h-5 w-5" />;
    case "SQL":
      return <Code className="h-5 w-5" />;
    case "BI":
      return <BarChart3 className="h-5 w-5" />;
    case "Excel":
      return <FileSpreadsheet className="h-5 w-5" />;
    case "PowerPoint":
      return <Presentation className="h-5 w-5" />;
  }
}

const mockLogs = `[2024-02-13 10:15:23] INFO: Starting execution
[2024-02-13 10:15:24] INFO: Loading configuration
[2024-02-13 10:15:25] INFO: Connecting to database
[2024-02-13 10:15:26] INFO: Connection established
[2024-02-13 10:15:27] INFO: Fetching data from source
[2024-02-13 10:15:45] INFO: Retrieved 12,847 records
[2024-02-13 10:15:46] INFO: Processing data
[2024-02-13 10:16:12] INFO: Applied transformations
[2024-02-13 10:16:15] INFO: Running model predictions
[2024-02-13 10:17:38] INFO: Predictions complete
[2024-02-13 10:17:39] INFO: Writing results to destination
[2024-02-13 10:17:47] SUCCESS: Execution completed successfully
[2024-02-13 10:17:47] INFO: Total duration: 3m 24s`;

export function RunDetailDrawer({ run, open, onClose }: RunDetailDrawerProps) {
  const [activeTab, setActiveTab] = useState<"logs" | "metadata" | "policy">("logs");

  if (!open || !run) return null;

  const statusColor =
    run.status === "succeeded"
      ? "text-green-600"
      : run.status === "failed"
      ? "text-red-600"
      : run.status === "running"
      ? "text-blue-600"
      : "text-gray-600";

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 z-40 animate-in fade-in"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-[600px] bg-white shadow-2xl z-50 overflow-y-auto animate-in slide-in-from-right">
        {/* Header */}
        <div className="sticky top-0 border-b border-gray-200 bg-white px-6 py-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h2 className="text-xl font-semibold text-gray-900">
                  {run.jobName}
                </h2>
                <span
                  className={`rounded-full px-3 py-1 text-sm font-medium ${
                    run.status === "succeeded"
                      ? "bg-green-50 text-green-700"
                      : run.status === "failed"
                      ? "bg-red-50 text-red-700"
                      : run.status === "running"
                      ? "bg-blue-50 text-blue-700"
                      : "bg-gray-50 text-gray-700"
                  }`}
                >
                  {run.status.charAt(0).toUpperCase() + run.status.slice(1)}
                </span>
              </div>
              <p className="mt-1 font-mono text-sm text-gray-500">{run.id}</p>
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
        <div className="p-6 space-y-6">
          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Type
              </p>
              <div className="mt-2 flex items-center gap-2 text-gray-900">
                {getTypeIcon(run.type)}
                <span className="font-medium">{run.type}</span>
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Environment
              </p>
              <p className="mt-2 font-medium text-gray-900">{run.environment}</p>
            </div>

            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Started At
              </p>
              <p className="mt-2 font-medium text-gray-900">{run.startedAt}</p>
            </div>

            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Duration
              </p>
              <p className="mt-2 font-mono font-medium text-gray-900">
                {run.duration}
              </p>
            </div>

            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Triggered By
              </p>
              <div className="mt-2">
                <p className="font-medium text-gray-900">{run.triggeredBy}</p>
                {run.triggerUser && (
                  <p className="text-sm text-gray-600">{run.triggerUser}</p>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Risk Score
              </p>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    run.riskScore < 30
                      ? "bg-green-500"
                      : run.riskScore < 60
                      ? "bg-yellow-500"
                      : "bg-red-500"
                  }`}
                />
                <span className="font-medium text-gray-900">{run.riskScore}</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <Button className="flex-1 gap-2 bg-blue-600 hover:bg-blue-700">
              <Play className="h-4 w-4" />
              Re-run
            </Button>
            <Button variant="outline" className="flex-1">
              View Job
            </Button>
          </div>

          {/* Tabs */}
          <div className="border-b border-gray-200">
            <div className="flex gap-6">
              <button
                onClick={() => setActiveTab("logs")}
                className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === "logs"
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-600 hover:text-gray-900"
                }`}
              >
                Logs
              </button>
              <button
                onClick={() => setActiveTab("metadata")}
                className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === "metadata"
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-600 hover:text-gray-900"
                }`}
              >
                Metadata
              </button>
              <button
                onClick={() => setActiveTab("policy")}
                className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === "policy"
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-600 hover:text-gray-900"
                }`}
              >
                Policy Checks
              </button>
            </div>
          </div>

          {/* Tab Content */}
          <div>
            {activeTab === "logs" && (
              <div className="rounded-lg border border-gray-200 bg-gray-900 p-4 overflow-x-auto">
                <pre className="font-mono text-xs text-green-400 whitespace-pre">
                  {mockLogs}
                </pre>
              </div>
            )}

            {activeTab === "metadata" && (
              <div className="space-y-3">
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <p className="text-sm font-medium text-gray-900">Git Commit</p>
                  <p className="mt-1 font-mono text-xs text-gray-600">
                    a7f3d2e9c1b8f4a6d2e8c9a1b3f5d7e9
                  </p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <p className="text-sm font-medium text-gray-900">Configuration</p>
                  <p className="mt-1 text-sm text-gray-600">
                    production-config-v2.yaml
                  </p>
                </div>
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <p className="text-sm font-medium text-gray-900">Compute Requirements</p>
                  <p className="mt-1 text-sm text-gray-600">
                    4 vCPUs, 16 GB RAM
                  </p>
                </div>
              </div>
            )}

            {activeTab === "policy" && (
              <div className="space-y-3">
                <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-4">
                  <AlertCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-green-900">
                      Data Sensitivity Check
                    </p>
                    <p className="mt-1 text-sm text-green-700">Passed</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-4">
                  <AlertCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-green-900">
                      Approval Requirements
                    </p>
                    <p className="mt-1 text-sm text-green-700">Passed</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-4">
                  <AlertCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-green-900">
                      Environment Validation
                    </p>
                    <p className="mt-1 text-sm text-green-700">Passed</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
