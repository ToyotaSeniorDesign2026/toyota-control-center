import { useEffect, useMemo, useState } from "react";
import { RefreshCw, Search, Upload } from "lucide-react";
import { Button } from "../components/ui/button";
import { listJobs, type JobRecord } from "../lib/controlCenterApi";

function statusPillClass(status: string) {
  const normalized = status.toLowerCase();
  if (["healthy", "approved", "active"].includes(normalized)) return "bg-green-100 text-green-700";
  if (["failed", "error", "blocked"].includes(normalized)) return "bg-red-100 text-red-700";
  if (["warning", "pending", "draft"].includes(normalized)) return "bg-yellow-100 text-yellow-800";
  return "bg-gray-100 text-gray-700";
}

function riskPillClass(riskLevel: string) {
  const normalized = riskLevel.toLowerCase();
  if (normalized === "critical") return "bg-red-100 text-red-700";
  if (normalized === "high") return "bg-orange-100 text-orange-700";
  if (normalized === "medium") return "bg-yellow-100 text-yellow-800";
  return "bg-emerald-100 text-emerald-700";
}

export type FilterType = "all" | "high-risk" | "failed" | "needs-approval";

export default function Jobs() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<FilterType>("all");
  const [selectedJob, setSelectedJob] = useState<JobRecord | null>(null);

  const loadJobs = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const response = await listJobs();
      setJobs(response.items);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load jobs.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadJobs();
  }, []);

  const filteredJobs = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return jobs.filter((job) => {
      if (query) {
        const matches = job.name.toLowerCase().includes(query) || job.id.toLowerCase().includes(query) || job.owner_name?.toLowerCase().includes(query);
        if (!matches) return false;
      }
      if (activeFilter === "high-risk" && !["high", "critical"].includes((job.risk_level ?? "").toLowerCase())) return false;
      if (activeFilter === "failed" && !["failed", "error", "blocked"].includes(job.status.toLowerCase())) return false;
      if (activeFilter === "needs-approval" && !(job.risk_score && job.risk_score >= 60)) return false;
      return true;
    });
  }, [jobs, searchQuery, activeFilter]);

  const metrics = useMemo(() => ({
    total: jobs.length,
    highRisk: jobs.filter((job) => ["high", "critical"].includes((job.risk_level ?? "").toLowerCase())).length,
    failed: jobs.filter((job) => ["failed", "error", "blocked"].includes(job.status.toLowerCase())).length,
  }), [jobs]);

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Jobs</h1>
          <p className="mt-2 text-sm text-gray-600">Backend-backed inventory of registered jobs and automation resources.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" className="h-9 gap-2 border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50">
            <Upload className="h-4 w-4" />
            Import from GitHub
          </Button>
          <Button onClick={() => void loadJobs(true)} className="bg-[#ed0923] text-white hover:bg-[#c3081d]" disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {error ? <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

      <div className="mb-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Registered Jobs</div><div className="mt-2 text-3xl font-bold text-gray-900">{metrics.total}</div></div>
        <div className="rounded-lg border border-orange-200 bg-orange-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">High-Risk Jobs</div><div className="mt-2 text-3xl font-bold text-orange-700">{metrics.highRisk}</div></div>
        <div className="rounded-lg border border-red-200 bg-red-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Failed / Blocked</div><div className="mt-2 text-3xl font-bold text-red-700">{metrics.failed}</div></div>
      </div>

      <div className="mb-6 flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, ID, or owner..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {[
            ["all", "All"],
            ["high-risk", "High Risk"],
            ["failed", "Failed"],
            ["needs-approval", "Needs Approval"],
          ].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setActiveFilter(id as FilterType)}
              className={`rounded-full px-3 py-2 text-sm font-medium ${activeFilter === id ? "bg-[#ed0923] text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Job</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Type</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Environment</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Status</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Risk</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Owner</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Last Run</th>
                <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-gray-600">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {loading ? (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-sm text-gray-500">Loading jobs...</td></tr>
              ) : filteredJobs.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-8 text-center text-sm text-gray-500">No backend jobs match the current filters.</td></tr>
              ) : (
                filteredJobs.map((job) => (
                  <tr key={job.id} className="hover:bg-gray-50/60">
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-gray-900">{job.name}</div>
                      <div className="mt-1 text-xs text-gray-500">{job.id}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{job.type}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{job.environment}</td>
                    <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(job.status)}`}>{job.status}</span></td>
                    <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(job.risk_level ?? "low")}`}>{job.risk_level ?? "low"}{job.risk_score ? ` (${job.risk_score})` : ""}</span></td>
                    <td className="px-4 py-3 text-sm text-gray-700">{job.owner_name ?? job.owner_id}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{job.last_run_at ? new Date(job.last_run_at).toLocaleString() : "No runs yet"}</td>
                    <td className="px-4 py-3 text-right"><Button variant="outline" onClick={() => setSelectedJob(job)}>View</Button></td>
                  </tr>
                ))
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
                  <h2 className="text-lg font-semibold text-gray-900">Job Details</h2>
                  <p className="mt-1 text-sm font-mono text-gray-600">{selectedJob.id}</p>
                </div>
                <Button variant="outline" onClick={() => setSelectedJob(null)}>Close</Button>
              </div>
            </div>
            <div className="flex-1 space-y-6 overflow-y-auto p-6">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><p className="text-xs font-medium uppercase text-gray-500">Name</p><p className="mt-1 font-semibold text-gray-900">{selectedJob.name}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Type</p><p className="mt-1 font-semibold text-gray-900">{selectedJob.type}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Environment</p><p className="mt-1 font-semibold text-gray-900">{selectedJob.environment}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Status</p><span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(selectedJob.status)}`}>{selectedJob.status}</span></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Risk</p><span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(selectedJob.risk_level ?? "low")}`}>{selectedJob.risk_level ?? "low"}{selectedJob.risk_score ? ` (${selectedJob.risk_score})` : ""}</span></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Owner</p><p className="mt-1 font-semibold text-gray-900">{selectedJob.owner_name ?? selectedJob.owner_id}</p></div>
              </div>
              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Configuration</h3>
                <pre className="overflow-x-auto rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs text-gray-700">{JSON.stringify(selectedJob.config, null, 2)}</pre>
              </div>
              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Tags</h3>
                <div className="flex flex-wrap gap-2">
                  {selectedJob.tags.length ? selectedJob.tags.map((tag) => <span key={tag} className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">{tag}</span>) : <span className="text-sm text-gray-500">No tags</span>}
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
