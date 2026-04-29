import { useEffect, useState } from "react";
import { Plus, Search, RefreshCw, Link2, Database, GitBranch, Cloud } from "lucide-react";
import { Button } from "../components/ui/button";
import { listConnectors, type ConnectorRecord } from "../lib/controlCenterApi";

function getConnectorIcon(connectorType: string) {
  if (connectorType === "github") return <GitBranch className="h-5 w-5 text-gray-700" />;
  if (connectorType === "sql") return <Database className="h-5 w-5 text-blue-600" />;
  return <Cloud className="h-5 w-5 text-gray-500" />;
}

function getStatusBadge(status: string) {
  if (status === "active") {
    return (
      <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
        Active
      </span>
    );
  }
  if (status === "inactive") {
    return (
      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-600">
        Inactive
      </span>
    );
  }
  return (
    <span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-700">
      {status}
    </span>
  );
}

export default function Connectors() {
  const [connectors, setConnectors] = useState<ConnectorRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listConnectors();
      setConnectors(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load connectors.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const filtered = connectors.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.connector_type.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Connectors</h1>
          <p className="mt-2 text-sm text-gray-600">
            Manage external systems and tools that jobs connect to — databases, GitHub repos, cloud
            services, and more.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="h-9 gap-2 border-gray-200 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50"
            onClick={() => void load()}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button className="h-9 gap-2 bg-[#ed0923] text-sm font-medium text-white hover:bg-[#c8071e]">
            <Plus className="h-4 w-4" />
            New Connector
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or type..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
          />
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && connectors.length === 0 ? (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-sm text-gray-500">
          Loading connectors...
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center">
          <Link2 className="mx-auto mb-3 h-10 w-10 text-gray-300" />
          <p className="text-sm font-medium text-gray-700">
            {search ? "No connectors match your search." : "No connectors configured yet."}
          </p>
          {!search && (
            <p className="mt-1 text-xs text-gray-500">
              Add a connector to link external systems to your jobs.
            </p>
          )}
        </div>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Environment</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Shared</th>
                <th className="px-5 py-3">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((connector) => (
                <tr key={connector.id} className="hover:bg-gray-50">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      {getConnectorIcon(connector.connector_type)}
                      <span className="font-medium text-gray-900">{connector.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3 text-gray-600">{connector.connector_type}</td>
                  <td className="px-5 py-3">
                    <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                      {connector.environment}
                    </span>
                  </td>
                  <td className="px-5 py-3">{getStatusBadge(connector.status)}</td>
                  <td className="px-5 py-3 text-gray-600">
                    {connector.is_shared ? (
                      <span className="text-xs font-medium text-green-700">Shared</span>
                    ) : (
                      <span className="text-xs text-gray-400">Private</span>
                    )}
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {new Date(connector.updated_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
