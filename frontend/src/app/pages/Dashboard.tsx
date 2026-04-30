import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Database, RefreshCw, ShieldCheck, TimerReset } from "lucide-react";
import { Button } from "../components/ui/button";
import {
  getCurrentUser,
  listApprovals,
  listAuditEvents,
  listJobs,
  listRuns,
  type ApprovalRecord,
  type AuditEventRecord,
  type JobRecord,
  type RunRecord,
  type UserRecord,
} from "../lib/controlCenterApi";

function statusPillClass(status: string) {
  const normalized = status.toLowerCase();
  if (["completed", "succeeded", "approved"].includes(normalized)) return "bg-green-100 text-green-700";
  if (["failed", "error", "blocked", "rejected"].includes(normalized)) return "bg-red-100 text-red-700";
  if (["pending", "queued", "running", "executing", "pending_approval"].includes(normalized)) {
    return "bg-yellow-100 text-yellow-800";
  }
  return "bg-gray-100 text-gray-700";
}

export default function Dashboard() {
  const [user, setUser] = useState<UserRecord | null>(null);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [me, jobsResponse, runsResponse, approvalsResponse, auditResponse] = await Promise.all([
        getCurrentUser(),
        listJobs(),
        listRuns(),
        listApprovals(),
        listAuditEvents(20),
      ]);
      setUser(me);
      setJobs(jobsResponse.items);
      setRuns(runsResponse.items);
      setApprovals(approvalsResponse);
      setAuditEvents(auditResponse);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load dashboard.";
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
  }, []);

  const pendingApprovals = useMemo(() => approvals.filter((item) => item.status.toLowerCase() === "pending"), [approvals]);
  const highRiskJobs = useMemo(
    () => jobs.filter((job) => ["high", "critical"].includes((job.risk_level ?? "").toLowerCase())),
    [jobs],
  );
  const recentRuns = useMemo(() => [...runs].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 6), [runs]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-2 text-sm text-gray-600">
            Live backend snapshot for admins reviewing jobs, approvals, runs, and audit activity.
          </p>
        </div>
        <Button onClick={() => void loadDashboard(true)} className="bg-[#ed0923] text-white hover:bg-[#c3081d]" disabled={refreshing}>
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error ? <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-gray-500">Admin User</p>
          <p className="mt-2 text-lg font-semibold text-gray-900">{user?.email ?? (loading ? "Loading..." : "Unavailable")}</p>
          <p className="mt-1 text-xs text-gray-500">{user?.role ?? ""} • {user?.domain ?? ""}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-gray-500"><Database className="h-4 w-4" /> Jobs</div>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{jobs.length}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-gray-500"><ShieldCheck className="h-4 w-4" /> Pending Approvals</div>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{pendingApprovals.length}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-gray-500"><AlertTriangle className="h-4 w-4" /> High-Risk Jobs</div>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{highRiskJobs.length}</p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Pending Approval Queue</h2>
            <p className="mt-1 text-sm text-gray-500">Dedicated approval records waiting on admin review.</p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-6 py-3">Approval</th>
                  <th className="px-6 py-3">Run</th>
                  <th className="px-6 py-3">Risk</th>
                  <th className="px-6 py-3">Submitted</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {pendingApprovals.length === 0 ? (
                  <tr><td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">No pending approval records were returned.</td></tr>
                ) : (
                  pendingApprovals.map((approval) => (
                    <tr key={approval.id}>
                      <td className="px-6 py-4 align-top font-medium text-gray-900">{approval.id}</td>
                      <td className="px-6 py-4 align-top text-sm text-gray-700">{approval.run_id}</td>
                      <td className="px-6 py-4 align-top text-sm text-gray-700">{approval.risk_level}</td>
                      <td className="px-6 py-4 align-top text-sm text-gray-700">{new Date(approval.created_at).toLocaleString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Audit Activity</h2>
            <p className="mt-1 text-sm text-gray-500">Latest backend audit events.</p>
          </div>
          <div className="space-y-3 px-6 py-4">
            {auditEvents.length === 0 ? (
              <p className="text-sm text-gray-500">No audit events were returned.</p>
            ) : (
              auditEvents.slice(0, 6).map((event) => (
                <div key={event.id} className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{event.action.replaceAll("_", " ").toLowerCase()}</p>
                      <p className="mt-1 text-xs text-gray-500">Actor {event.actor_id ?? "system"}</p>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <TimerReset className="h-3.5 w-3.5" />
                      {new Date(event.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Runs</h2>
            <p className="mt-1 text-sm text-gray-500">Latest backend execution records.</p>
          </div>
          <div className="space-y-3 px-6 py-4">
            {recentRuns.length === 0 ? (
              <p className="text-sm text-gray-500">No runs were returned from the backend.</p>
            ) : (
              recentRuns.map((run) => (
                <div key={run.id} className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-gray-900">{run.resource_id}</p>
                      <p className="mt-1 text-xs text-gray-500">{run.id}</p>
                    </div>
                    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(run.status)}`}>{run.status}</span>
                  </div>
                  <p className="mt-2 text-xs text-gray-500">{run.target_environment} • {new Date(run.updated_at).toLocaleString()}</p>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">High-Risk Jobs</h2>
            <p className="mt-1 text-sm text-gray-500">Jobs currently flagged high or critical.</p>
          </div>
          <div className="space-y-3 px-6 py-4">
            {highRiskJobs.length === 0 ? (
              <p className="text-sm text-gray-500">No high-risk jobs were returned.</p>
            ) : (
              highRiskJobs.slice(0, 6).map((job) => (
                <div key={job.id} className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-gray-900">{job.name}</p>
                      <p className="mt-1 text-xs text-gray-500">{job.id}</p>
                    </div>
                    <span className="inline-flex rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700">{job.risk_level}</span>
                  </div>
                  <p className="mt-2 text-xs text-gray-500">{job.environment} • owner {job.owner_id}</p>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
