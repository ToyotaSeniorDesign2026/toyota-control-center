import { useEffect, useMemo, useState } from "react";
import { BarChart3, RefreshCw, ShieldAlert, TrendingUp } from "lucide-react";
import { Button } from "../components/ui/button";
import { getPolicyChecks, listApprovals, listJobs, listRuns, type ApprovalRecord, type JobRecord, type PolicyEvaluation, type RunRecord } from "../lib/controlCenterApi";

type PolicyChecksByRun = Record<string, PolicyEvaluation | null>;

function statusPillClass(status: string) {
  const normalized = status.toLowerCase();
  if (["completed", "succeeded", "approved"].includes(normalized)) return "bg-green-100 text-green-700";
  if (["failed", "error", "blocked", "rejected"].includes(normalized)) return "bg-red-100 text-red-700";
  if (["pending", "queued", "running", "executing", "pending_approval"].includes(normalized)) {
    return "bg-yellow-100 text-yellow-800";
  }
  return "bg-gray-100 text-gray-700";
}

export default function Research() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [policyChecksByRun, setPolicyChecksByRun] = useState<PolicyChecksByRun>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadResearch = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [jobsResponse, runsResponse, approvalsResponse] = await Promise.all([
        listJobs(),
        listRuns(),
        listApprovals(),
      ]);
      setJobs(jobsResponse.items);
      setRuns(runsResponse.items);
      setApprovals(approvalsResponse);

      const policyEntries = await Promise.all(
        runsResponse.items.slice(0, 40).map(async (run) => {
          try {
            const evaluation = await getPolicyChecks(run.id);
            return [run.id, evaluation] as const;
          } catch {
            return [run.id, null] as const;
          }
        }),
      );
      setPolicyChecksByRun(Object.fromEntries(policyEntries));
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Unable to load research data.";
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadResearch();
  }, []);

  const environmentCounts = useMemo(() => {
    const counts = new Map<string, number>();
    jobs.forEach((job) => {
      counts.set(job.environment, (counts.get(job.environment) ?? 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [jobs]);

  const topRiskJobs = useMemo(
    () => [...jobs].filter((job) => ["high", "critical"].includes((job.risk_level ?? "").toLowerCase())).slice(0, 6),
    [jobs],
  );

  const policyPressure = useMemo(() => {
    const counts = new Map<string, number>();
    Object.values(policyChecksByRun).forEach((evaluation) => {
      evaluation?.checks.forEach((check) => {
        if (check.result !== "FAIL") return;
        counts.set(check.category, (counts.get(check.category) ?? 0) + 1);
      });
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [policyChecksByRun]);

  const runStatusCounts = useMemo(() => {
    const counts = new Map<string, number>();
    runs.forEach((run) => {
      const key = run.status.toLowerCase();
      counts.set(key, (counts.get(key) ?? 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [runs]);

  const pendingApprovals = useMemo(() => approvals.filter((approval) => approval.status.toLowerCase() === "pending").length, [approvals]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Research & Insights</h1>
          <p className="mt-1 text-sm text-gray-600">
            Backend-driven visibility into environment mix, run outcomes, approval load, and policy pressure.
          </p>
        </div>
        <Button onClick={() => void loadResearch(true)} className="bg-[#ed0923] text-white hover:bg-[#c3081d]" disabled={refreshing}>
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error ? <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-gray-500"><BarChart3 className="h-4 w-4" /> Total Jobs</div>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{jobs.length}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-gray-500"><TrendingUp className="h-4 w-4" /> Total Runs</div>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{runs.length}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-gray-500"><ShieldAlert className="h-4 w-4" /> Pending Approvals</div>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{pendingApprovals}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm text-gray-500"><ShieldAlert className="h-4 w-4" /> High-Risk Jobs</div>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{topRiskJobs.length}</p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Environment Distribution</h2>
            <p className="mt-1 text-sm text-gray-500">How backend jobs are currently distributed across environments.</p>
          </div>
          <div className="space-y-3 px-6 py-4">
            {environmentCounts.length === 0 ? (
              <p className="text-sm text-gray-500">No job environment data was returned.</p>
            ) : (
              environmentCounts.map(([environment, count]) => (
                <div key={environment}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium text-gray-900">{environment}</span>
                    <span className="text-gray-500">{count}</span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-100">
                    <div
                      className="h-2 rounded-full bg-[#ed0923]"
                      style={{ width: `${Math.max(8, (count / Math.max(jobs.length, 1)) * 100)}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Run Status Distribution</h2>
            <p className="mt-1 text-sm text-gray-500">Current run outcome mix from the backend.</p>
          </div>
          <div className="space-y-3 px-6 py-4">
            {runStatusCounts.length === 0 ? (
              <p className="text-sm text-gray-500">No run status data was returned.</p>
            ) : (
              runStatusCounts.map(([status, count]) => (
                <div key={status} className="flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(status)}`}>{status}</span>
                  <span className="text-sm font-medium text-gray-900">{count}</span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Top Policy Drivers</h2>
            <p className="mt-1 text-sm text-gray-500">Most common failing policy categories in recent backend evaluations.</p>
          </div>
          <div className="space-y-3 px-6 py-4">
            {policyPressure.length === 0 ? (
              <p className="text-sm text-gray-500">No failing policy checks were returned.</p>
            ) : (
              policyPressure.map(([category, count]) => (
                <div key={category} className="flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  <span className="font-medium capitalize text-gray-900">{category}</span>
                  <span className="text-sm font-medium text-gray-700">{count} failures</span>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
          <div className="border-b border-gray-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-gray-900">Top High-Risk Jobs</h2>
            <p className="mt-1 text-sm text-gray-500">High and critical jobs from the backend resource inventory.</p>
          </div>
          <div className="space-y-3 px-6 py-4">
            {topRiskJobs.length === 0 ? (
              <p className="text-sm text-gray-500">No high-risk jobs were returned.</p>
            ) : (
              topRiskJobs.map((job) => (
                <div key={job.id} className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-gray-900">{job.name}</p>
                      <p className="mt-1 text-xs text-gray-500">{job.id}</p>
                    </div>
                    <span className="inline-flex rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700">{job.risk_level}</span>
                  </div>
                  <p className="mt-2 text-xs text-gray-500">{job.environment} • {job.owner_domain}</p>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
