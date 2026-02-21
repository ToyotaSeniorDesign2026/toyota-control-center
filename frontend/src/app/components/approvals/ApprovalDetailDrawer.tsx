import { useState } from "react";
import { X, CheckCircle, XCircle, AlertTriangle, ArrowRight, User, Calendar, Shield, MessageSquare } from "lucide-react";
import { Button } from "../ui/button";
import { Approval } from "./ApprovalsTable";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../ui/tabs";
import { Textarea } from "../ui/textarea";

interface ApprovalDetailDrawerProps {
  approval: Approval | null;
  onClose: () => void;
}

const policyChecks = [
  {
    id: "1",
    name: "Data Classification Compliance",
    status: "passed",
    description: "Resource properly classifies sensitive data",
  },
  {
    id: "2",
    name: "Access Control Requirements",
    status: "passed",
    description: "All required permissions are properly scoped",
  },
  {
    id: "3",
    name: "Backup & Recovery Configuration",
    status: "warning",
    description: "Recovery time objective exceeds recommended threshold",
  },
  {
    id: "4",
    name: "Cost Threshold Policy",
    status: "passed",
    description: "Estimated costs within approved budget limits",
  },
  {
    id: "5",
    name: "External API Security Review",
    status: "failed",
    description: "New external endpoint requires security team approval",
  },
  {
    id: "6",
    name: "Schedule Frequency Limits",
    status: "warning",
    description: "High frequency schedule may impact system performance",
  },
];

const comments = [
  {
    id: "1",
    author: "Alex Rivera",
    timestamp: "2024-02-13T11:15:00Z",
    content: "The external API integration needs security review. Can you provide the endpoint documentation?",
    role: "Security Engineer",
  },
  {
    id: "2",
    author: "Sarah Chen",
    timestamp: "2024-02-13T11:30:00Z",
    content: "Documentation attached. The API uses OAuth 2.0 and all data is encrypted in transit. We've used this vendor before for similar integrations.",
    role: "Data Engineer",
  },
  {
    id: "3",
    author: "Mike Johnson",
    timestamp: "2024-02-13T12:00:00Z",
    content: "I've reviewed the security aspects. The integration looks good, but we should add rate limiting on our end to prevent issues.",
    role: "Platform Lead",
  },
];

const specDiff = {
  before: {
    schedule: "0 0 * * *",
    connectors: ["PostgreSQL: production_db"],
    dataSensitivity: "Internal",
    externalEndpoints: [],
    estimatedCost: "$120/month",
  },
  after: {
    schedule: "*/5 * * * *",
    connectors: ["PostgreSQL: production_db", "API: customer_enrichment"],
    dataSensitivity: "PII",
    externalEndpoints: ["https://api.customer-data.example.com"],
    estimatedCost: "$570/month",
  },
};

function formatTimestamp(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

export function ApprovalDetailDrawer({
  approval,
  onClose,
}: ApprovalDetailDrawerProps) {
  const [comment, setComment] = useState("");
  const [activeTab, setActiveTab] = useState("overview");

  if (!approval) return null;

  const riskColor =
    approval.riskLevel === "Critical"
      ? "text-red-600"
      : approval.riskLevel === "High"
      ? "text-orange-600"
      : approval.riskLevel === "Medium"
      ? "text-yellow-600"
      : "text-green-600";

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white shadow-2xl border-l border-gray-200 flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-gray-900">
                Approval Review
              </h2>
              <span className={`rounded px-2 py-0.5 text-xs font-semibold ${riskColor} bg-opacity-10`}>
                Risk: {approval.riskScore}
              </span>
            </div>
            <div className="mt-1 text-sm text-gray-600 font-mono">
              {approval.id}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Key Info */}
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">
              Resource
            </div>
            <div className="mt-1 text-sm font-semibold text-gray-900">
              {approval.resourceName}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">
              Change Type
            </div>
            <div className="mt-1 text-sm font-semibold text-gray-900">
              {approval.changeType}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">
              Environment Flow
            </div>
            <div className="mt-1 flex items-center gap-2 text-sm font-semibold text-gray-900">
              {approval.fromEnvironment}
              <ArrowRight className="h-3 w-3 text-gray-400" />
              {approval.toEnvironment}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase">
              Submitted By
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-sm font-semibold text-gray-900">
              <User className="h-3.5 w-3.5 text-gray-400" />
              {approval.submittedBy}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex-1 overflow-y-auto">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full">
          <div className="border-b border-gray-200 bg-white px-6">
            <TabsList className="h-auto p-0 bg-transparent">
              <TabsTrigger
                value="overview"
                className="rounded-none border-b-2 border-transparent px-4 py-3 data-[state=active]:border-blue-600 data-[state=active]:bg-transparent"
              >
                Overview
              </TabsTrigger>
              <TabsTrigger
                value="diff"
                className="rounded-none border-b-2 border-transparent px-4 py-3 data-[state=active]:border-blue-600 data-[state=active]:bg-transparent"
              >
                Spec Diff
              </TabsTrigger>
              <TabsTrigger
                value="policy"
                className="rounded-none border-b-2 border-transparent px-4 py-3 data-[state=active]:border-blue-600 data-[state=active]:bg-transparent"
              >
                Policy Checks
              </TabsTrigger>
            </TabsList>
          </div>

          <div className="p-6">
            <TabsContent value="overview" className="mt-0">
              <div className="space-y-6">
                {/* Summary */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Change Summary
                  </h3>
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <p className="text-sm text-gray-700">
                      This change promotes the{" "}
                      <span className="font-semibold">
                        {approval.resourceName}
                      </span>{" "}
                      from {approval.fromEnvironment} to{" "}
                      {approval.toEnvironment}. The resource will now access PII
                      data and connect to an external API for customer
                      enrichment. Schedule frequency increases from daily to
                      every 5 minutes.
                    </p>
                  </div>
                </div>

                {/* Risk Breakdown */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Risk Breakdown
                  </h3>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3">
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-orange-500" />
                        <span className="text-sm font-medium text-gray-900">
                          Data Sensitivity
                        </span>
                      </div>
                      <span className="text-sm text-gray-600">
                        Internal → PII
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3">
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-yellow-500" />
                        <span className="text-sm font-medium text-gray-900">
                          Schedule Change
                        </span>
                      </div>
                      <span className="text-sm text-gray-600">
                        Daily → Every 5m
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-3">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                        <span className="text-sm font-medium text-gray-900">
                          External API Added
                        </span>
                      </div>
                      <span className="text-sm text-gray-600">+1 endpoint</span>
                    </div>
                  </div>
                </div>

                {/* Affected Resources */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Affected Connectors
                  </h3>
                  <div className="space-y-2">
                    <div className="rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-700">
                      PostgreSQL: production_db
                    </div>
                    <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 font-medium">
                      + API: customer_enrichment (New)
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="diff" className="mt-0">
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Specification Changes
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    {/* Before */}
                    <div>
                      <div className="mb-2 text-xs font-semibold text-gray-500 uppercase">
                        Before
                      </div>
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">
                            Schedule
                          </div>
                          <div className="text-sm font-mono text-gray-900">
                            {specDiff.before.schedule}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">
                            Connectors
                          </div>
                          {specDiff.before.connectors.map((conn, i) => (
                            <div
                              key={i}
                              className="text-sm font-mono text-gray-900"
                            >
                              {conn}
                            </div>
                          ))}
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">
                            Data Sensitivity
                          </div>
                          <div className="text-sm font-mono text-gray-900">
                            {specDiff.before.dataSensitivity}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">
                            External Endpoints
                          </div>
                          <div className="text-sm text-gray-500 italic">
                            None
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">
                            Est. Cost
                          </div>
                          <div className="text-sm font-mono text-gray-900">
                            {specDiff.before.estimatedCost}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* After */}
                    <div>
                      <div className="mb-2 text-xs font-semibold text-gray-500 uppercase">
                        After
                      </div>
                      <div className="rounded-lg border border-green-200 bg-green-50 p-4 space-y-3">
                        <div>
                          <div className="text-xs font-medium text-gray-700 mb-1">
                            Schedule
                          </div>
                          <div className="text-sm font-mono text-green-700 font-semibold">
                            {specDiff.after.schedule}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-700 mb-1">
                            Connectors
                          </div>
                          {specDiff.after.connectors.map((conn, i) => (
                            <div
                              key={i}
                              className={`text-sm font-mono ${
                                i === 1
                                  ? "text-green-700 font-semibold"
                                  : "text-gray-700"
                              }`}
                            >
                              {conn}
                              {i === 1 && (
                                <span className="ml-2 text-xs font-sans">
                                  (New)
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-700 mb-1">
                            Data Sensitivity
                          </div>
                          <div className="text-sm font-mono text-green-700 font-semibold">
                            {specDiff.after.dataSensitivity}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-700 mb-1">
                            External Endpoints
                          </div>
                          {specDiff.after.externalEndpoints.map((endpoint, i) => (
                            <div
                              key={i}
                              className="text-sm font-mono text-green-700 font-semibold break-all"
                            >
                              {endpoint}
                            </div>
                          ))}
                        </div>
                        <div>
                          <div className="text-xs font-medium text-gray-700 mb-1">
                            Est. Cost
                          </div>
                          <div className="text-sm font-mono text-green-700 font-semibold">
                            {specDiff.after.estimatedCost}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="policy" className="mt-0">
              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">
                    Policy Validation Results
                  </h3>
                  <div className="space-y-2">
                    {policyChecks.map((check) => (
                      <div
                        key={check.id}
                        className={`rounded-lg border p-3 ${
                          check.status === "passed"
                            ? "border-green-200 bg-green-50"
                            : check.status === "warning"
                            ? "border-yellow-200 bg-yellow-50"
                            : "border-red-200 bg-red-50"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-start gap-2 flex-1">
                            {check.status === "passed" ? (
                              <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                            ) : check.status === "warning" ? (
                              <AlertTriangle className="mt-0.5 h-4 w-4 text-yellow-600" />
                            ) : (
                              <XCircle className="mt-0.5 h-4 w-4 text-red-600" />
                            )}
                            <div className="flex-1">
                              <div className="text-sm font-medium text-gray-900">
                                {check.name}
                              </div>
                              <div className="mt-0.5 text-xs text-gray-600">
                                {check.description}
                              </div>
                            </div>
                          </div>
                          <span
                            className={`rounded px-2 py-0.5 text-xs font-medium uppercase ${
                              check.status === "passed"
                                ? "bg-green-100 text-green-700"
                                : check.status === "warning"
                                ? "bg-yellow-100 text-yellow-700"
                                : "bg-red-100 text-red-700"
                            }`}
                          >
                            {check.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </TabsContent>
          </div>
        </Tabs>
      </div>

      {/* Comments Section */}
      <div className="border-t border-gray-200 bg-gray-50 p-6">
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="h-4 w-4 text-gray-500" />
            <h3 className="text-sm font-semibold text-gray-900">
              Discussion ({comments.length})
            </h3>
          </div>
          <div className="space-y-3 max-h-48 overflow-y-auto">
            {comments.map((c) => (
              <div key={c.id} className="rounded-lg border border-gray-200 bg-white p-3">
                <div className="flex items-start justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-900">
                      {c.author}
                    </span>
                    <span className="text-xs text-gray-500">{c.role}</span>
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatTimestamp(c.timestamp)}
                  </span>
                </div>
                <p className="text-sm text-gray-700">{c.content}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="mb-4">
          <Textarea
            placeholder="Add a comment..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            className="min-h-[80px] resize-none"
          />
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <Button
            className="flex-1 bg-green-600 hover:bg-green-700 text-white"
            size="lg"
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            Approve
          </Button>
          <Button
            variant="outline"
            className="flex-1 border-red-200 text-red-600 hover:bg-red-50"
            size="lg"
          >
            <XCircle className="h-4 w-4 mr-2" />
            Reject
          </Button>
          <Button variant="outline" size="lg">
            Request Changes
          </Button>
        </div>
      </div>
    </div>
  );
}
