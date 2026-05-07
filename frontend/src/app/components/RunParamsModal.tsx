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

type ConnectorKind = "sql-mcp" | "github";
type DbDriver = "postgresql+psycopg" | "sqlite" | "snowflake";

export function connectorNeedsRunParams(job: JobRecord): boolean {
  const connector = (job.connector ?? "").toLowerCase();
  if (connector === "github") return true;
  if (connector === "sql-mcp") {
    const cfg = job.config ?? {};
    const driver = (cfg.db_driver ?? "").toLowerCase();
    if (driver === "sqlite") return !cfg.database;
    return ["host", "database", "username", "password"].some((k) => !cfg[k]);
  }
  return false;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : String(v ?? "");
}

const DB_DRIVER_LABELS: Record<DbDriver, string> = {
  "postgresql+psycopg": "PostgreSQL",
  sqlite: "SQLite",
  snowflake: "Snowflake",
};

export function RunParamsModal({ job, onClose, onSubmit, isSubmitting }: RunParamsModalProps) {
  const connector = (job.connector ?? "").toLowerCase() as ConnectorKind;
  const cfg = job.config ?? {};

  const inferredDriver = (): DbDriver => {
    const d = (cfg.db_driver ?? "").toLowerCase();
    if (d === "sqlite") return "sqlite";
    if (d === "snowflake") return "snowflake";
    return "postgresql+psycopg";
  };

  const [dbDriver, setDbDriver] = useState<DbDriver>(inferredDriver);

  const [fields, setFields] = useState<Record<string, string>>(() => {
    if (connector === "sql-mcp") {
      const driver = inferredDriver();
      if (driver === "sqlite") {
        return { database: str(cfg.database) };
      }
      return {
        host: str(cfg.host),
        port: str(cfg.port) || (driver === "snowflake" ? "" : "5432"),
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

  const handleDriverChange = (driver: DbDriver) => {
    setDbDriver(driver);
    if (driver === "sqlite") {
      setFields({ database: "" });
    } else {
      setFields({
        host: "",
        port: driver === "snowflake" ? "" : "5432",
        database: "",
        username: "",
        password: "",
      });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ ...fields, db_driver: dbDriver });
  };

  const isValid = () => {
    if (connector === "sql-mcp") {
      if (dbDriver === "sqlite") return !!fields.database?.trim();
      return ["host", "database", "username", "password"].every((k) => fields[k]?.trim());
    }
    if (connector === "github") {
      return !!(fields.github_token?.trim() && fields.repo?.trim());
    }
    return true;
  };

  const isSql = connector === "sql-mcp";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative w-full max-w-md rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
          <div className="flex items-center gap-2">
            {isSql ? (
              <Database className="h-4 w-4 text-blue-600" />
            ) : (
              <Github className="h-4 w-4 text-gray-700" />
            )}
            <span className="font-semibold text-gray-900 text-sm">
              {isSql ? "Database connection" : "GitHub credentials"}
            </span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-3">
          <p className="text-xs text-gray-500 mb-3">
            {isSql
              ? `Enter the database credentials to run "${job.name}". These are used only for this run.`
              : `Enter a GitHub personal access token with repo write access to run "${job.name}".`}
          </p>

          {isSql && (
            <>
              <div className="space-y-1">
                <label className="block text-xs font-medium text-gray-700">Database type</label>
                <div className="flex gap-2">
                  {(Object.keys(DB_DRIVER_LABELS) as DbDriver[]).map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => handleDriverChange(d)}
                      className={`flex-1 rounded-md border px-2 py-1.5 text-xs font-medium transition-colors ${
                        dbDriver === d
                          ? "border-blue-500 bg-blue-50 text-blue-700"
                          : "border-gray-200 text-gray-600 hover:border-gray-300"
                      }`}
                    >
                      {DB_DRIVER_LABELS[d]}
                    </button>
                  ))}
                </div>
              </div>

              {dbDriver === "sqlite" ? (
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Database file path
                  </label>
                  <input
                    type="text"
                    value={fields.database}
                    onChange={(e) => set("database", e.target.value)}
                    placeholder="/path/to/file.db"
                    className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                    autoFocus
                  />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        {dbDriver === "snowflake" ? "Account" : "Host"}
                      </label>
                      <input
                        type="text"
                        value={fields.host}
                        onChange={(e) => set("host", e.target.value)}
                        placeholder={
                          dbDriver === "snowflake"
                            ? "account.snowflakecomputing.com"
                            : "localhost"
                        }
                        className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        required
                      />
                    </div>
                    {dbDriver !== "snowflake" && (
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Port</label>
                        <input
                          type="text"
                          value={fields.port}
                          onChange={(e) => set("port", e.target.value)}
                          placeholder="5432"
                          className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    )}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      {dbDriver === "snowflake" ? "Database / Schema" : "Database"}
                    </label>
                    <input
                      type="text"
                      value={fields.database}
                      onChange={(e) => set("database", e.target.value)}
                      placeholder={dbDriver === "snowflake" ? "MY_DB/PUBLIC" : "my_database"}
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
                        type="text"
                        value={fields.password}
                        onChange={(e) => set("password", e.target.value)}
                        placeholder="••••••••"
                        autoComplete="off"
                        style={{ WebkitTextSecurity: "disc" } as React.CSSProperties}
                        className="w-full rounded-md border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        required
                      />
                    </div>
                  </div>
                </>
              )}
            </>
          )}

          {connector === "github" && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Personal access token
                </label>
                <input
                  type="text"
                  value={fields.github_token}
                  onChange={(e) => set("github_token", e.target.value)}
                  placeholder="github_pat_..."
                  autoComplete="off"
                  style={{ WebkitTextSecurity: "disc" } as React.CSSProperties}
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
