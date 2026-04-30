import { useEffect, useMemo, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { Button } from "../components/ui/button";
import { getPolicyChecks, listJobs, listRuns, type JobRecord, type PolicyEvaluation, type RunRecord } from "../lib/controlCenterApi";

type PolicyChecksByRun = Record<string, PolicyEvaluation | null>;

function riskPillClass(riskLevel: string) {
  const normalized = riskLevel.toLowerCase();
  if (normalized === "critical") return "bg-red-100 text-red-700";
  if (normalized === "high") return "bg-orange-100 text-orange-700";
  if (normalized === "medium") return "bg-yellow-100 text-yellow-800";
  return "bg-emerald-100 text-emerald-700";
}

export default function Risk() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [policyChecksByRun, setPolicyChecksByRun] = useState<PolicyChecksByRun>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobRecord | null>(null);

  const loadRiskData = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const [jobsResponse, runsResponse] = await Promise.all([listJobs(), listRuns()]);
      setJobs(jobsResponse.items);
      setRuns(runsResponse.items);
      const highRiskRuns = runsResponse.items.filter((run) => ["high", "critical"].includes(run.risk_level.toLowerCase()));
      const policyEntries = await Promise.all(
        highRiskRuns.map(async (run) => {
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
      setError(loadError instanceof Error ? loadError.message : "Unable to load risk data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadRiskData();
  }, []);

  const highRiskJobs = useMemo(
    () => jobs.filter((job) => ["high", "critical"].includes((job.risk_level ?? "").toLowerCase())).sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0)),
    [jobs],
  );

  const metrics = useMemo(() => {
    const scoredJobs = jobs.filter((job) => typeof job.risk_score === "number");
    const averageRisk = scoredJobs.length ? Math.round(scoredJobs.reduce((sum, job) => sum + (job.risk_score ?? 0), 0) / scoredJobs.length) : 0;
    const policyViolations = Object.values(policyChecksByRun).reduce((count, evaluation) => count + (evaluation?.checks.filter((check) => check.result.toLowerCase() === "failed").length ?? 0), 0);
    const approvalRequired = runs.filter((run) => run.requires_approval).length;
    return {
      averageRisk,
      highRisk: highRiskJobs.length,
      approvalRequired,
      policyViolations,
    };
  }, [jobs, highRiskJobs.length, policyChecksByRun, runs]);

  const distribution = useMemo(() => {
    const buckets = {
      Dev: { low: 0, medium: 0, high: 0, critical: 0 },
      "Semi-Prod": { low: 0, medium: 0, high: 0, critical: 0 },
      Production: { low: 0, medium: 0, high: 0, critical: 0 },
    } as Record<string, Record<string, number>>;

    jobs.forEach((job) => {
      const env = job.environment === "prod" ? "Production" : job.environment === "semi-prod" ? "Semi-Prod" : job.environment === "dev" ? "Dev" : job.environment;
      if (!buckets[env]) buckets[env] = { low: 0, medium: 0, high: 0, critical: 0 };
      const level = (job.risk_level ?? "low").toLowerCase();
      if (level in buckets[env]) buckets[env][level] += 1;
    });

    return buckets;
  }, [jobs]);

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Risk & Governance</h1>
          <p className="mt-1 text-sm text-gray-600">Backend-driven view of risk levels, policy outcomes, and approval pressure.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" className="h-9 gap-2 border-gray-200 bg-white text-sm text-gray-700 hover:bg-gray-50">
            <Download className="h-4 w-4" />
            Export Risk Report
          </Button>
          <Button onClick={() => void loadRiskData(true)} className="bg-[#ed0923] text-white hover:bg-[#c3081d]" disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {error ? <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-orange-200 bg-orange-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Average Risk Score</div><div className="mt-2 text-3xl font-bold text-orange-700">{metrics.averageRisk}</div></div>
        <div className="rounded-lg border border-red-200 bg-red-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">High-Risk Jobs</div><div className="mt-2 text-3xl font-bold text-red-700">{metrics.highRisk}</div></div>
        <div className="rounded-lg border border-yellow-200 bg-yellow-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Approval Required Runs</div><div className="mt-2 text-3xl font-bold text-yellow-800">{metrics.approvalRequired}</div></div>
        <div className="rounded-lg border border-red-200 bg-red-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Policy Check Failures</div><div className="mt-2 text-3xl font-bold text-red-700">{metrics.policyViolations}</div></div>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900">Risk Distribution by Environment</h3>
          <p className="mt-1 text-sm text-gray-600">Counts of job risk levels across environments from backend job records.</p>
          <div className="mt-4 space-y-4 text-sm">
            {Object.entries(distribution).map(([env, levels]) => (
              <div key={env} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <p className="font-semibold text-gray-900">{env}</p>
                <div className="mt-2 grid grid-cols-2 gap-2 lg:grid-cols-4">
                  {Object.entries(levels).map(([level, count]) => (
                    <div key={level} className="rounded bg-white px-3 py-2 text-gray-700">
                      <span className="font-medium capitalize">{level}</span>: {count}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900">Top Policy Drivers</h3>
          <p className="mt-1 text-sm text-gray-600">Most common failing check categories pulled from backend policy evaluations.</p>
          <div className="mt-4 space-y-3 text-sm">
            {Object.values(policyChecksByRun).flatMap((evaluation) => evaluation?.checks ?? []).filter((check) => check.result.toLowerCase() === "failed").slice(0, 8).map((check, index) => (
              <div key={`${check.id}-${index}`} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <p className="font-medium text-gray-900">{check.check_name}</p>
                <p className="mt-1 text-gray-600">{check.reason}</p>
                <p className="mt-2 text-xs uppercase tracking-wide text-gray-500">{check.category} • severity {check.severity}</p>
              </div>
            ))}
            {!loading && Object.values(policyChecksByRun).flatMap((evaluation) => evaluation?.checks ?? []).filter((check) => check.result.toLowerCase() === "failed").length === 0 ? (
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-gray-600">No failed policy checks found in the current backend dataset.</div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mb-4 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
          <h3 className="text-lg font-semibold text-gray-900">High-Risk Jobs</h3>
          <p className="mt-1 text-sm text-gray-600">Jobs with elevated backend risk scores that may need attention.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Job</th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Type</th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Environment</th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Risk</th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Owner</th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Approval Pressure</th>
                <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-gray-600">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {loading ? (
                <tr><td colSpan={7} className="px-3 py-8 text-center text-sm text-gray-500">Loading risk data...</td></tr>
              ) : highRiskJobs.length === 0 ? (
                <tr><td colSpan={7} className="px-3 py-8 text-center text-sm text-gray-500">No high-risk jobs found in the backend.</td></tr>
              ) : (
                highRiskJobs.map((job) => {
                  const relatedApprovalRuns = runs.filter((run) => run.resource_id === job.id && run.requires_approval).length;
                  return (
                    <tr key={job.id} className="hover:bg-gray-50/60">
                      <td className="px-3 py-3"><div className="text-sm font-medium text-gray-900">{job.name}</div><div className="mt-1 text-xs text-gray-500">{job.id}</div></td>
                      <td className="px-3 py-3 text-sm text-gray-700">{job.type}</td>
                      <td className="px-3 py-3 text-sm text-gray-700">{job.environment}</td>
                      <td className="px-3 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(job.risk_level ?? "low")}`}>{job.risk_level ?? "low"}{job.risk_score ? ` (${job.risk_score})` : ""}</span></td>
                      <td className="px-3 py-3 text-sm text-gray-700">{job.owner_name ?? job.owner_id}</td>
                      <td className="px-3 py-3 text-sm text-gray-700">{relatedApprovalRuns > 0 ? `${relatedApprovalRuns} pending approval run(s)` : "No current approval holds"}</td>
                      <td className="px-3 py-3 text-right"><Button variant="outline" onClick={() => setSelectedJob(job)}>View</Button></td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedJob ? (
        <>
          <div className="fixed inset-0 z-40 bg-black/30" onClick={() => setSelectedJob(null)} />
          <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-gray-200 bg-white shadow-2xl">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Risk Details</h2>
                  <p className="mt-1 text-sm font-mono text-gray-600">{selectedJob.id}</p>
                </div>
                <Button variant="outline" onClick={() => setSelectedJob(null)}>Close</Button>
              </div>
            </div>
            <div className="flex-1 space-y-6 overflow-y-auto p-6">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><p className="text-xs font-medium uppercase text-gray-500">Job</p><p className="mt-1 font-semibold text-gray-900">{selectedJob.name}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Type</p><p className="mt-1 font-semibold text-gray-900">{selectedJob.type}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Environment</p><p className="mt-1 font-semibold text-gray-900">{selectedJob.environment}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Risk</p><span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(selectedJob.risk_level ?? "low")}`}>{selectedJob.risk_level ?? "low"}{selectedJob.risk_score ? ` (${selectedJob.risk_score})` : ""}</span></div>
              </div>
              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Configuration Snapshot</h3>
                <pre className="overflow-x-auto rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs text-gray-700">{JSON.stringify(selectedJob.config, null, 2)}</pre>
              </div>
              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Recent Approval-Relevant Runs</h3>
                <div className="space-y-3">
                  {runs.filter((run) => run.resource_id === selectedJob.id).slice(0, 6).map((run) => (
                    <div key={run.id} className="rounded-lg border border-gray-200 bg-white p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="font-medium text-gray-900">{run.id}</p>
                          <p className="mt-1 text-sm text-gray-600">{run.target_environment} • {new Date(run.updated_at).toLocaleString()}</p>
                        </div>
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(run.risk_level)}`}>{run.risk_level}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
