import { useEffect, useMemo, useState } from "react";
import { Download, RefreshCw, Search } from "lucide-react";
import { Button } from "../components/ui/button";
import { getRunLogs, listRuns, type RunLogsResponse, type RunRecord } from "../lib/controlCenterApi";

function statusPillClass(status: string) {
  const normalized = status.toLowerCase();
  if (["completed", "succeeded", "approved"].includes(normalized)) return "bg-green-100 text-green-700";
  if (["failed", "error", "blocked", "cancelled"].includes(normalized)) return "bg-red-100 text-red-700";
  if (["running", "executing", "queued", "pending", "pending_approval"].includes(normalized)) return "bg-yellow-100 text-yellow-800";
  return "bg-gray-100 text-gray-700";
}

function riskPillClass(riskLevel: string) {
  const normalized = riskLevel.toLowerCase();
  if (normalized === "critical") return "bg-red-100 text-red-700";
  if (normalized === "high") return "bg-orange-100 text-orange-700";
  if (normalized === "medium") return "bg-yellow-100 text-yellow-800";
  return "bg-emerald-100 text-emerald-700";
}

export default function Runs() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRun, setSelectedRun] = useState<RunRecord | null>(null);
  const [runLogs, setRunLogs] = useState<RunLogsResponse | null>(null);
  const [logsLoading, setLogsLoading] = useState(false);

  const loadRuns = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const response = await listRuns();
      setRuns(response.items);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load runs.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadRuns();
  }, []);

  const filteredRuns = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return [...runs]
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .filter((run) => {
        if (!query) return true;
        return run.id.toLowerCase().includes(query) || run.resource_id.toLowerCase().includes(query);
      });
  }, [runs, searchQuery]);

  const metrics = useMemo(() => ({
    total: runs.length,
    running: runs.filter((run) => ["running", "executing", "queued"].includes(run.status.toLowerCase())).length,
    failed: runs.filter((run) => ["failed", "blocked", "error", "cancelled"].includes(run.status.toLowerCase())).length,
    approval: runs.filter((run) => run.requires_approval).length,
  }), [runs]);

  const openRun = async (run: RunRecord) => {
    setSelectedRun(run);
    setLogsLoading(true);
    try {
      const logs = await getRunLogs(run.id);
      setRunLogs(logs);
    } catch {
      setRunLogs(null);
    } finally {
      setLogsLoading(false);
    }
  };

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Runs</h1>
          <p className="mt-1 text-sm text-gray-600">Live execution history and run outcomes directly from the backend database.</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" className="h-9 gap-2 border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50">
            <Download className="h-4 w-4" />
            Export Run Data
          </Button>
          <Button onClick={() => void loadRuns(true)} className="bg-[#ed0923] text-white hover:bg-[#c3081d]" disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {error ? <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div> : null}

      <div className="mb-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Total Runs</div><div className="mt-2 text-3xl font-bold text-gray-900">{metrics.total}</div></div>
        <div className="rounded-lg border border-yellow-200 bg-yellow-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Running / Queued</div><div className="mt-2 text-3xl font-bold text-yellow-800">{metrics.running}</div></div>
        <div className="rounded-lg border border-red-200 bg-red-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Failed / Blocked</div><div className="mt-2 text-3xl font-bold text-red-700">{metrics.failed}</div></div>
        <div className="rounded-lg border border-orange-200 bg-orange-50/40 p-4 shadow-sm"><div className="text-sm font-medium text-gray-600">Approval Required</div><div className="mt-2 text-3xl font-bold text-orange-700">{metrics.approval}</div></div>
      </div>

      <div className="mb-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by job ID or run ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Run ID</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Job</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Environment</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Status</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Risk</th>
                <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-600">Updated</th>
                <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-gray-600">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {loading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">Loading runs...</td></tr>
              ) : filteredRuns.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-sm text-gray-500">No runs found in the backend.</td></tr>
              ) : (
                filteredRuns.map((run) => (
                  <tr key={run.id} className="hover:bg-gray-50/60">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{run.id}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{run.resource_id}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{run.target_environment}</td>
                    <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(run.status)}`}>{run.status}</span></td>
                    <td className="px-4 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(run.risk_level)}`}>{run.risk_level} ({run.risk_score})</span></td>
                    <td className="px-4 py-3 text-sm text-gray-700">{new Date(run.updated_at).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right"><Button variant="outline" onClick={() => void openRun(run)}>View</Button></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedRun ? (
        <>
          <div className="fixed inset-0 z-40 bg-black/30" onClick={() => setSelectedRun(null)} />
          <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-gray-200 bg-white shadow-2xl">
            <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Run Details</h2>
                  <p className="mt-1 text-sm font-mono text-gray-600">{selectedRun.id}</p>
                </div>
                <Button variant="outline" onClick={() => setSelectedRun(null)}>Close</Button>
              </div>
            </div>
            <div className="flex-1 space-y-6 overflow-y-auto p-6">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><p className="text-xs font-medium uppercase text-gray-500">Job</p><p className="mt-1 font-semibold text-gray-900">{selectedRun.resource_id}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Status</p><span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusPillClass(selectedRun.status)}`}>{selectedRun.status}</span></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Environment</p><p className="mt-1 font-semibold text-gray-900">{selectedRun.target_environment}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Risk</p><span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-medium ${riskPillClass(selectedRun.risk_level)}`}>{selectedRun.risk_level} ({selectedRun.risk_score})</span></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Approval Required</p><p className="mt-1 font-semibold text-gray-900">{selectedRun.requires_approval ? "Yes" : "No"}</p></div>
                <div><p className="text-xs font-medium uppercase text-gray-500">Updated</p><p className="mt-1 font-semibold text-gray-900">{new Date(selectedRun.updated_at).toLocaleString()}</p></div>
              </div>

              <div>
                <h3 className="mb-3 text-sm font-semibold text-gray-900">Run Logs</h3>
                {logsLoading ? (
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">Loading logs...</div>
                ) : runLogs?.logs?.length ? (
                  <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
                    <div className="max-h-96 overflow-y-auto divide-y divide-gray-200">
                      {runLogs.logs.map((log, index) => (
                        <div key={`${log.timestamp}-${index}`} className="px-4 py-3 text-sm">
                          <div className="flex items-center justify-between gap-4">
                            <span className="font-medium text-gray-900">{log.level}</span>
                            <span className="text-xs text-gray-500">{new Date(log.timestamp).toLocaleString()}</span>
                          </div>
                          <p className="mt-1 text-gray-700">{log.message}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">No logs available for this run.</div>
                )}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </>
  );
}
