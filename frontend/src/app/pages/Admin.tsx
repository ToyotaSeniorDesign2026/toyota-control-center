import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Database, RefreshCw, ShieldCheck, TimerReset } from "lucide-react";
import {
  approveApproval,
  getCurrentUser,
  getPolicyChecks,
  listApprovals,
  listAuditEvents,
  listJobs,
  listRuns,
  rejectApproval,
  type ApprovalRecord,
  type AuditEventRecord,
  type JobRecord,
  type PolicyEvaluation,
  type RunRecord,
  type UserRecord,
} from "../lib/controlCenterApi";
import { Button } from "../components/ui/button";

type PolicyChecksByRun = Record<string, PolicyEvaluation | null>;
type RunsById = Record<string, RunRecord>;

function statusPillClass(status: string) {
  const normalized = status.toLowerCase();
  if (["completed", "succeeded", "approved"].includes(normalized)) return "bg-green-100 text-green-700";
  if (["failed", "error", "blocked", "rejected"].includes(normalized)) return "bg-red-100 text-red-700";
  if (["pending", "queued", "running", "executing", "pending_approval"].includes(normalized)) {
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

export default function Admin() {
  const [adminUser, setAdminUser] = useState<UserRecord | null>(null);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventRecord[]>([]);
  const [policyChecksByRun, setPolicyChecksByRun] = useState<PolicyChecksByRun>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [approvingApprovalId, setApprovingApprovalId] = useState<string | null>(null);
  const [rejectingApprovalId, setRejectingApprovalId] = useState<string | null>(null);

  const loadAdminData = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [user, jobsResponse, runsResponse, approvalsResponse, auditResponse] = await Promise.all([
        getCurrentUser(),
        listJobs(),
        listRuns(),
        listApprovals(),
        listAuditEvents(40),
      ]);

      setAdminUser(user);
      setJobs(jobsResponse.items);
      setRuns(runsResponse.items);
      setApprovals(approvalsResponse);
      setAuditEvents(auditResponse);

      const pendingRuns = approvalsResponse
        .filter((approval) => approval.status.toLowerCase() === "pending")
        .map((approval) => approval.run_id);
      const policyEntries = await Promise.all(
        pendingRuns.map(async (runId) => {
          try {
            const evaluation = await getPolicyChecks(runId);
            return [runId, evaluation] as const;
          } catch {
            return [runId, null] as const;
          }
        }),
      );
      setPolicyChecksByRun(Object.fromEntries(policyEntries));
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load admin data.";
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadAdminData();
  }, []);

  const runsById = useMemo<RunsById>(() => Object.fromEntries(runs.map((run) => [run.id, run])), [runs]);

  const pendingApprovals = useMemo(
    () => approvals.filter((approval) => approval.status.toLowerCase() === "pending"),
    [approvals],
  );

  const recentRuns = useMemo(
    () => [...runs].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 8),
    [runs],
  );

  const highRiskJobs = useMemo(
    () => jobs.filter((job) => ["high", "critical"].includes((job.risk_level ?? "").toLowerCase())).length,
    [jobs],
  );

  const activeEnvironments = useMemo(
    () => Array.from(new Set(jobs.map((job) => job.environment))).filter(Boolean),
    [jobs],
  );

  const ownerDomains = useMemo(
    () => Array.from(new Set(jobs.map((job) => job.owner_domain))).filter(Boolean),
    [jobs],
  );

  const handleApprove = async (approval: ApprovalRecord) => {
    setApprovingApprovalId(approval.id);
    setActionMessage(null);
    try {
      await approveApproval(approval.id);
      await loadAdminData(true);
      setActionMessage(`Approved ${approval.id} successfully.`);
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
      await rejectApproval(approval.id, "Rejected from the admin dashboard review queue.");
      await loadAdminData(true);
      setActionMessage(`Rejected ${approval.id} successfully.`);
    } catch (rejectError) {
      const message = rejectError instanceof Error ? rejectError.message : "Unable to reject request.";
      setActionMessage(message);
    } finally {
      setRejectingApprovalId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Admin Control Center</h1>
          <p className="mt-2 max-w-3xl text-sm text-gray-600">
            This view is connected to backend jobs, runs, approvals, and audit history so admins can review,
            approve, and track changes from one place.
          </p>
        </div>
        <Button
          onClick={() => void loadAdminData(true)}
          className="bg-[#ed0923] text-white hover:bg-[#c3081d]"
          disabled={refreshing}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : null}

      {actionMessage ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{actionMessage}</div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-blue-100 p-2 text-blue-700">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Signed In As</p>
              <p className="text-lg font-semibold text-gray-900">{adminUser?.email ?? (loading ? "Loading..." : "Unavailable")}</p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-slate-100 p-2 text-slate-700">
              <Database className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Registered Jobs</p>
              <p className="text-2xl font-semibold text-gray-900">{jobs.length}</p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-yellow-100 p-2 text-yellow-800">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Pending Approvals</p>
              <p className="text-2xl font-semibold text-gray-900">{pendingApprovals.length}</p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="rounded-xl bg-red-100 p-2 text-red-700">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-gray-500">High-Risk Jobs</p>
              <p className="text-2xl font-semibold text-gray-900">{highRiskJobs}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Approval Queue</h2>
            <p className="mt-1 text-sm text-gray-500">Dedicated backend approval records waiting on admin review.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-6 py-3">Approval</th>
                  <th className="px-6 py-3">Job</th>
                  <th className="px-6 py-3">Risk</th>
                  <th className="px-6 py-3">Policy</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {pendingApprovals.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-sm text-gray-500">
                      No pending approval records were returned from the backend.
                    </td>
                  </tr>
                ) : (
                  pendingApprovals.map((approval) => {
                    const run = runsById[approval.run_id];
                    const policy = policyChecksByRun[approval.run_id];
                    return (
                      <tr key={approval.id}>
                        <td className="px-6 py-4 align-top">
                          <div className="font-medium text-gray-900">{approval.id}</div>
                          <div className="mt-1 text-xs text-gray-500">Run {approval.run_id}</div>
                        </td>
                        <td className="px-6 py-4 align-top">
                          <div className="font-medium text-gray-900">{run?.resource_id ?? "Unknown job"}</div>
                          <div className="mt-1 text-xs text-gray-500">
                            {run ? `${run.target_environment} • ${run.updated_at}` : `Requested ${approval.created_at}`}
                          </div>
                        </td>
                        <td className="px-6 py-4 align-top">
                          <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(approval.risk_level)}`}>
                            {approval.risk_level}
                            {run ? ` (${run.risk_score})` : ""}
                          </span>
                        </td>
                        <td className="px-6 py-4 align-top text-sm text-gray-600">
                          {policy ? (
                            <div>
                              <div className="font-medium text-gray-900">{policy.overall_status}</div>
                              <div className="mt-1 text-xs text-gray-500">
                                {policy.checks.length} checks • approval {policy.requires_approval ? "required" : "not required"}
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-500">No policy details loaded</span>
                          )}
                        </td>
                        <td className="px-6 py-4 align-top text-right">
                          <div className="flex flex-wrap justify-end gap-2">
                            <Button
                              onClick={() => void handleApprove(approval)}
                              disabled={approvingApprovalId === approval.id}
                              className="bg-[#ed0923] text-white hover:bg-[#c3081d]"
                            >
                              {approvingApprovalId === approval.id ? "Approving..." : "Approve"}
                            </Button>
                            <Button
                              variant="outline"
                              onClick={() => void handleReject(approval)}
                              disabled={rejectingApprovalId === approval.id}
                              className="border-red-200 text-red-700 hover:bg-red-50"
                            >
                              {rejectingApprovalId === approval.id ? "Rejecting..." : "Reject"}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="space-y-6">
          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 px-6 py-4">
              <h2 className="text-lg font-semibold text-gray-900">Management Snapshot</h2>
              <p className="mt-1 text-sm text-gray-500">Backend-backed context for admins managing environments and domains.</p>
            </div>
            <div className="grid gap-4 px-6 py-4 text-sm text-gray-700 sm:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Role</p>
                <p className="mt-1 font-medium text-gray-900">{adminUser?.role ?? "Unknown"}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Domain</p>
                <p className="mt-1 font-medium text-gray-900">{adminUser?.domain ?? "Unknown"}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Tracked Environments</p>
                <p className="mt-1 font-medium text-gray-900">{activeEnvironments.join(", ") || "No environments returned"}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Owner Domains</p>
                <p className="mt-1 font-medium text-gray-900">{ownerDomains.join(", ") || "No owner domains returned"}</p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 px-6 py-4">
              <h2 className="text-lg font-semibold text-gray-900">Recent Audit Activity</h2>
              <p className="mt-1 text-sm text-gray-500">Live audit events from the backend API.</p>
            </div>
            <div className="space-y-3 px-6 py-4">
              {auditEvents.length === 0 ? (
                <p className="text-sm text-gray-500">No audit events were returned.</p>
              ) : (
                auditEvents.slice(0, 8).map((event) => (
                  <div key={event.id} className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{formatAction(event.action)}</p>
                        <p className="mt-1 text-xs text-gray-500">Actor {event.actor_id ?? "system"}</p>
                      </div>
                      <div className="flex items-center gap-1 text-xs text-gray-500">
                        <TimerReset className="h-3.5 w-3.5" />
                        {new Date(event.created_at).toLocaleString()}
                      </div>
                    </div>
                    {Object.keys(event.metadata ?? {}).length > 0 ? (
                      <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-xs text-gray-700">
                        {JSON.stringify(event.metadata, null, 2)}
                      </pre>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Runs</h2>
            <p className="mt-1 text-sm text-gray-500">Latest run records directly from the backend.</p>
          </div>
          <div className="space-y-3 px-6 py-4">
            {recentRuns.length === 0 ? (
              <p className="text-sm text-gray-500">No runs were returned from the backend.</p>
            ) : (
              recentRuns.map((run) => (
                <div key={run.id} className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium text-gray-900">{run.resource_id}</p>
                      <p className="mt-1 text-xs text-gray-500">{run.id}</p>
                    </div>
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(run.status)}`}>
                      {run.status}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-600">
                    <span>{run.target_environment}</span>
                    <span>•</span>
                    <span>{new Date(run.updated_at).toLocaleString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Registered Jobs</h2>
            <p className="mt-1 text-sm text-gray-500">Backend-backed resource inventory available to admins.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-6 py-3">Job</th>
                  <th className="px-6 py-3">Owner</th>
                  <th className="px-6 py-3">Environment</th>
                  <th className="px-6 py-3">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">
                      No jobs were returned from the backend.
                    </td>
                  </tr>
                ) : (
                  jobs.slice(0, 8).map((job) => (
                    <tr key={job.id}>
                      <td className="px-6 py-4 align-top">
                        <div className="font-medium text-gray-900">{job.name}</div>
                        <div className="mt-1 text-xs text-gray-500">{job.id}</div>
                      </td>
                      <td className="px-6 py-4 align-top text-sm text-gray-700">{job.owner_id}</td>
                      <td className="px-6 py-4 align-top text-sm text-gray-700">{job.environment}</td>
                      <td className="px-6 py-4 align-top">
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(job.risk_level ?? "low")}`}>
                          {job.risk_level ?? "low"}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
