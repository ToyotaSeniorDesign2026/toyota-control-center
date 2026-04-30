import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Search } from "lucide-react";
import { Button } from "../components/ui/button";
import {
  approveApproval,
  getPolicyChecks,
  listApprovals,
  listAuditEvents,
  listRuns,
  rejectApproval,
  type ApprovalRecord,
  type AuditEventRecord,
  type PolicyEvaluation,
  type RunRecord,
} from "../lib/controlCenterApi";

type FilterTab = "all" | "pending-my-approval" | "approved" | "rejected" | "high-risk";
type PolicyChecksByRun = Record<string, PolicyEvaluation | null>;
type RunsById = Record<string, RunRecord>;

function statusPillClass(status: string) {
  const normalized = status.toLowerCase();
  if (["approved", "completed", "succeeded"].includes(normalized)) return "bg-green-100 text-green-700";
  if (["failed", "blocked", "rejected", "error"].includes(normalized)) return "bg-red-100 text-red-700";
  if (["pending", "pending_approval", "queued", "running", "executing"].includes(normalized)) {
    return "bg-yellow-100 text-yellow-800";
  }
  return "bg-gray-100 text-gray-700";
}

function riskPillClass(riskLevel: string) {
  const normalized = riskLevel.toLowerCase();
  if (normalized === "critical") return "bg-red-100 text-red-700";
  if (normalized === "high") return "bg-orange-100 text-orange-700";
  if (normalized === "medium") return "bg-yellow-100 text-yellow-800";
  return "bg-emerald-100 text-emerald-700";
}

function formatAction(action: string) {
  return action.toLowerCase().replaceAll("_", " ");
}

export default function Approvals() {
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [runsById, setRunsById] = useState<RunsById>({});
  const [auditEvents, setAuditEvents] = useState<AuditEventRecord[]>([]);
  const [policyChecksByRun, setPolicyChecksByRun] = useState<PolicyChecksByRun>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedApproval, setSelectedApproval] = useState<ApprovalRecord | null>(null);
  const [approvingApprovalId, setApprovingApprovalId] = useState<string | null>(null);
  const [rejectingApprovalId, setRejectingApprovalId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const loadApprovals = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [approvalsResponse, runsResponse, auditResponse] = await Promise.all([
        listApprovals(),
        listRuns(),
        listAuditEvents(200),
      ]);
      setApprovals(approvalsResponse);
      setRunsById(Object.fromEntries(runsResponse.items.map((run) => [run.id, run])));
      setAuditEvents(auditResponse);

      const policyEntries = await Promise.all(
        approvalsResponse.map(async (approval) => {
          try {
            const evaluation = await getPolicyChecks(approval.run_id);
            return [approval.run_id, evaluation] as const;
          } catch {
            return [approval.run_id, null] as const;
          }
        }),
      );
      setPolicyChecksByRun(Object.fromEntries(policyEntries));
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load approvals.";
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadApprovals();
  }, []);

  const filteredApprovals = useMemo(() => {
    const byTab = approvals.filter((approval) => {
      const status = approval.status.toLowerCase();
      const risk = approval.risk_level.toLowerCase();
      if (activeTab === "pending-my-approval") return status === "pending";
      if (activeTab === "approved") return status === "approved";
      if (activeTab === "rejected") return status === "rejected";
      if (activeTab === "high-risk") return risk === "high" || risk === "critical";
      return true;
    });

    return byTab.filter((approval) => {
      const normalizedQuery = searchQuery.trim().toLowerCase();
      if (!normalizedQuery) return true;
      const run = runsById[approval.run_id];
      return (
        approval.id.toLowerCase().includes(normalizedQuery) ||
        approval.run_id.toLowerCase().includes(normalizedQuery) ||
        run?.resource_id?.toLowerCase().includes(normalizedQuery)
      );
    });
  }, [activeTab, approvals, runsById, searchQuery]);

  const metrics = useMemo(() => {
    const pending = approvals.filter((approval) => approval.status.toLowerCase() === "pending").length;
    const highRisk = approvals.filter((approval) => ["high", "critical"].includes(approval.risk_level.toLowerCase())).length;
    const approved = approvals.filter((approval) => approval.status.toLowerCase() === "approved").length;
    const rejected = approvals.filter((approval) => approval.status.toLowerCase() === "rejected").length;
    return { pending, highRisk, approved, rejected };
  }, [approvals]);

  const tabs: { id: FilterTab; label: string; count: number }[] = [
    { id: "all", label: "All", count: approvals.length },
    { id: "pending-my-approval", label: "Pending My Approval", count: metrics.pending },
    { id: "approved", label: "Approved", count: metrics.approved },
    { id: "rejected", label: "Rejected", count: metrics.rejected },
    { id: "high-risk", label: "High Risk", count: metrics.highRisk },
  ];

  const handleApprove = async (approval: ApprovalRecord) => {
    setApprovingApprovalId(approval.id);
    setActionMessage(null);
    try {
      await approveApproval(approval.id);
      await loadApprovals(true);
      setActionMessage(`Approved ${approval.id} successfully.`);
      setSelectedApproval(null);
    } catch (approveError) {
      const message = approveError instanceof Error ? approveError.message : "Unable to approve request.";
      setActionMessage(message);
    } finally {
      setApprovingApprovalId(null);
    }
  };

  const handleReject = async (approval: ApprovalRecord) => {
    setRejectingApprovalId(approval.id);
    setActionMessage(null);
    try {
      await rejectApproval(approval.id, rejectReason.trim() || "Rejected during admin review.");
      await loadApprovals(true);
      setActionMessage(`Rejected ${approval.id} successfully.`);
      setSelectedApproval(null);
      setRejectReason("");
    } catch (rejectError) {
      const message = rejectError instanceof Error ? rejectError.message : "Unable to reject request.";
      setActionMessage(message);
    } finally {
      setRejectingApprovalId(null);
    }
  };

  const selectedRun = selectedApproval ? runsById[selectedApproval.run_id] ?? null : null;
  const selectedPolicy = selectedApproval ? policyChecksByRun[selectedApproval.run_id] : null;
  const selectedAuditEvents = useMemo(() => {
    if (!selectedApproval) return [];
    return auditEvents.filter((event) => {
      const metadata = event.metadata ?? {};
      return metadata.approval_id === selectedApproval.id || metadata.run_id === selectedApproval.run_id;
    });
  }, [auditEvents, selectedApproval]);

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Approvals</h1>
          <p className="mt-2 text-sm text-gray-600">Review dedicated backend approval records, inspect policy details, and approve or reject from one queue.</p>
        </div>
        <Button onClick={() => void loadApprovals(true)} className="bg-[#ed0923] text-white hover:bg-[#c3081d]" disabled={refreshing}>
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error ? <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}
      {actionMessage ? <div className="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{actionMessage}</div> : null}

      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Pending Approvals</div><div className="mt-2 text-3xl font-bold text-gray-900">{metrics.pending}</div></div>
        <div className="rounded-lg border border-red-200 bg-red-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">High Risk Changes</div><div className="mt-2 text-3xl font-bold text-red-600">{metrics.highRisk}</div></div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Approved Requests</div><div className="mt-2 text-3xl font-bold text-gray-900">{metrics.approved}</div></div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Rejected Requests</div><div className="mt-2 text-3xl font-bold text-gray-900">{metrics.rejected}</div></div>
      </div>

      <div className="mb-6 border-b border-gray-200">
        <div className="flex gap-6 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`whitespace-nowrap border-b-2 px-1 pb-3 text-sm font-medium transition-colors ${
                activeTab === tab.id ? "border-blue-600 text-blue-600" : "border-transparent text-gray-600 hover:border-gray-300 hover:text-gray-900"
              }`}
            >
              {tab.label}
              <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${activeTab === tab.id ? "bg-blue-100 text-blue-600" : "bg-gray-100 text-gray-600"}`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by approval, run, or job ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="mb-6 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Approval ID</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Job</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Environment</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Risk</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Status</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Updated</th>
                <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-gray-600">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">Loading approvals...</td></tr>
              ) : filteredApprovals.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">No backend approval records match the current filter.</td></tr>
              ) : (
                filteredApprovals.map((approval) => {
                  const run = runsById[approval.run_id];
                  return (
                    <tr key={approval.id} className="hover:bg-gray-50/60">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{approval.id}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{run?.resource_id ?? "Unknown job"}</td>
                      <td className="px-4 py-3 text-sm text-gray-700">{run?.target_environment ?? "Unknown"}</td>
                      <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(approval.risk_level)}`}>{approval.risk_level}{run ? ` (${run.risk_score})` : ""}</span></td>
                      <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(approval.status)}`}>{approval.status}</span></td>
                      <td className="px-4 py-3 text-sm text-gray-700">{new Date((run?.updated_at ?? approval.reviewed_at ?? approval.created_at)).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right"><Button variant="outline" onClick={() => { setSelectedApproval(approval); setRejectReason(approval.comment ?? ""); }}>Review</Button></td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedApproval ? (
        <>
          <div className="fixed inset-0 z-40 bg-black/30" onClick={() => setSelectedApproval(null)} />
          <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-gray-200 bg-white shadow-2xl">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Approval Review</h2>
                  <p className="mt-1 text-sm font-mono text-gray-600">{selectedApproval.id}</p>
                </div>
                <Button variant="outline" onClick={() => setSelectedApproval(null)}>Close</Button>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div><p className="text-xs font-medium uppercase text-gray-500">Job</p><p className="mt-1 font-semibold text-gray-900">{selectedRun?.resource_id ?? "Unknown job"}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Environment</p><p className="mt-1 font-semibold text-gray-900">{selectedRun?.target_environment ?? "Unknown"}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Status</p><span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(selectedApproval.status)}`}>{selectedApproval.status}</span></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Risk</p><span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(selectedApproval.risk_level)}`}>{selectedApproval.risk_level}{selectedRun ? ` (${selectedRun.risk_score})` : ""}</span></div>
              </div>
            </div>

            <div className="flex-1 space-y-6 overflow-y-auto p-6">
              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Policy Summary</h3>
                {selectedPolicy ? (
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">
                    <p><span className="font-semibold text-gray-900">Overall Status:</span> {selectedPolicy.overall_status}</p>
                    <p className="mt-2"><span className="font-semibold text-gray-900">Policy Version:</span> {selectedPolicy.policy_version}</p>
                    <p className="mt-2"><span className="font-semibold text-gray-900">Evaluated At:</span> {new Date(selectedPolicy.evaluated_at).toLocaleString()}</p>
                    <p className="mt-2"><span className="font-semibold text-gray-900">Approval Required:</span> {selectedPolicy.requires_approval ? "Yes" : "No"}</p>
                  </div>
                ) : (
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">No policy evaluation details were returned for this approval.</div>
                )}
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Policy Checks</h3>
                <div className="space-y-3">
                  {selectedPolicy?.checks?.length ? (
                    selectedPolicy.checks.map((check) => (
                      <div key={check.id} className="rounded-lg border border-gray-200 bg-white p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="font-medium text-gray-900">{check.check_name}</p>
                            <p className="mt-1 text-sm text-gray-600">{check.reason}</p>
                          </div>
                          <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(check.result)}`}>{check.result}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">No individual policy checks available.</div>
                  )}
                </div>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Audit Trail</h3>
                <div className="space-y-3">
                  {selectedAuditEvents.length ? (
                    selectedAuditEvents.map((event) => (
                      <div key={event.id} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="font-medium text-gray-900">{formatAction(event.action)}</p>
                            <p className="mt-1 text-sm text-gray-600">Actor {event.actor_id ?? "system"}</p>
                          </div>
                          <span className="text-xs text-gray-500">{new Date(event.created_at).toLocaleString()}</span>
                        </div>
                        {Object.keys(event.metadata ?? {}).length ? (
                          <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-xs text-gray-700">{JSON.stringify(event.metadata, null, 2)}</pre>
                        ) : null}
                      </div>
                    ))
                  ) : (
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">No audit events are linked to this approval yet.</div>
                  )}
                </div>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Reject Notes</h3>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  rows={4}
                  placeholder="Document why this approval is being rejected so the requester has clear next steps."
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="border-t border-gray-200 px-6 py-4">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="text-sm text-gray-500">Use the backend approval record to approve or reject this request.</div>
                <div className="flex flex-wrap gap-3">
                  <Button
                    variant="outline"
                    onClick={() => void handleReject(selectedApproval)}
                    disabled={rejectingApprovalId === selectedApproval.id || selectedApproval.status.toLowerCase() !== "pending"}
                    className="border-red-200 text-red-700 hover:bg-red-50"
                  >
                    {rejectingApprovalId === selectedApproval.id ? "Rejecting..." : "Reject Request"}
                  </Button>
                  <Button
                    onClick={() => void handleApprove(selectedApproval)}
                    disabled={approvingApprovalId === selectedApproval.id || selectedApproval.status.toLowerCase() !== "pending"}
                    className="bg-[#ed0923] text-white hover:bg-[#c3081d]"
                  >
                    {approvingApprovalId === selectedApproval.id ? "Approving..." : "Approve Request"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
