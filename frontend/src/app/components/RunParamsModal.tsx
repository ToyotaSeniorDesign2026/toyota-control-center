import { useState } from "react";
import { X, Database, Github } from "lucide-react";
import { Button } from "./ui/button";
import type { JobRecord } from "../lib/controlCenterApi";

interface RunParamsModalProps {
  job: JobRecord;
  onClose: () => void;
  onSubmit: (params: Record<string, string>) => void;
  isSubmitting: boolean;
}

type ConnectorKind = "sql-dab" | "github";

export function connectorNeedsRunParams(job: JobRecord): boolean {
  const connector = (job.connector ?? "").toLowerCase();
  if (connector === "github") return true;
  if (connector === "sql-dab") {
    const cfg = job.config ?? {};
    return ["host", "port", "database", "username", "password"].some((k) => !cfg[k]);
  }
  return false;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : String(v ?? "");
}

export function RunParamsModal({ job, onClose, onSubmit, isSubmitting }: RunParamsModalProps) {
  const connector = (job.connector ?? "").toLowerCase() as ConnectorKind;
  const cfg = job.config ?? {};

  const [fields, setFields] = useState<Record<string, string>>(() => {
    if (connector === "sql-dab") {
      return {
        host: str(cfg.host),
        port: str(cfg.port) || "5432",
        database: str(cfg.database),
        username: str(cfg.username),
        password: str(cfg.password),
      };
    }
    if (connector === "github") {
      return {
        github_token: "",
        repo: str(cfg.repo),
        branch: str(cfg.branch) || str(cfg.ref) || "main",
      };
    }
    return {};
  });

  const set = (key: string, value: string) =>
    setFields((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(fields);
  };

  const isValid = () => {
    if (connector === "sql-dab") {
      return ["host", "port", "database", "username", "password"].every(
        (k) => fields[k]?.trim()
      );
    }
    if (connector === "github") {
      return !!(fields.github_token?.trim() && fields.repo?.trim());
    }
    return true;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative w-full max-w-md rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <div className="flex items-center gap-2">
            {connector === "sql-dab" ? (
              <Database className="h-4 w-4 text-blue-600" />
            ) : (
              <Github className="h-4 w-4 text-gray-700" />
            )}
            <span className="font-semibold text-gray-900 text-sm">
              {connector === "sql-dab" ? "Database connection" : "GitHub credentials"}
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-3">
          <p className="text-xs text-gray-500 mb-3">
            {connector === "sql-dab"
              ? `Enter the database credentials to run "${job.name}". These are used only for this run.`
              : `Enter a GitHub personal access token with repo write access to run "${job.name}".`}
          </p>

          {connector === "sql-dab" && (
            <>
              <div className="grid grid-cols-3 gap-2">
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-gray-700 mb-1">Host</label>
                  <input
                    type="text"
                    value={fields.host}
                    onChange={(e) => set("host", e.target.value)}
                    placeholder="localhost"
                    className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Port</label>
                  <input
                    type="text"
                    value={fields.port}
                    onChange={(e) => set("port", e.target.value)}
                    placeholder="5432"
                    className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Database</label>
                <input
                  type="text"
                  value={fields.database}
                  onChange={(e) => set("database", e.target.value)}
                  placeholder="my_database"
                  className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Username</label>
                  <input
                    type="text"
                    value={fields.username}
                    onChange={(e) => set("username", e.target.value)}
                    placeholder="postgres"
                    className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Password</label>
                  <input
                    type="password"
                    value={fields.password}
                    onChange={(e) => set("password", e.target.value)}
                    placeholder="••••••••"
                    className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
              </div>
            </>
          )}

          {connector === "github" && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Personal access token
                </label>
                <input
                  type="password"
                  value={fields.github_token}
                  onChange={(e) => set("github_token", e.target.value)}
                  placeholder="github_pat_..."
                  className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Repository</label>
                <input
                  type="text"
                  value={fields.repo}
                  onChange={(e) => set("repo", e.target.value)}
                  placeholder="owner/repo"
                  className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Branch</label>
                <input
                  type="text"
                  value={fields.branch}
                  onChange={(e) => set("branch", e.target.value)}
                  placeholder="main"
                  className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              {cfg.path && (
                <p className="text-xs text-gray-400">
                  Will write to <span className="font-mono">{str(cfg.path)}</span>
                </p>
              )}
            </>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={!isValid() || isSubmitting}>
              {isSubmitting ? "Starting…" : "Run job"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
