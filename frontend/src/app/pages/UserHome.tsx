import { useMemo, useState, useEffect, useRef } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  PlayCircle,
  Sparkles,
  Briefcase,
  Calendar,
  CheckSquare,
  FileText,
  MessageSquare,
  ChevronRight,
  ChevronLeft,
  Send,
  Wand2,
  X,
  Code,
  ChevronUp,
  ChevronDown,
  GitMerge,
  Plus,
} from "lucide-react";
import { useNavigate } from "react-router";
import { Button } from "../components/ui/button";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { ChatPanel } from "../components/ChatPanel";
import ExcelReportForm from "../components/user/ExcelReportForm";
import SQLJobForm from "../components/user/SQLJobForm";
import PowerPointForm from "../components/user/PowerPointForm";
import { useCalendarOverlay } from "../contexts/CalendarContext";
import { useJobRuns } from "../contexts/JobRunContext";
import {
  createResource,
  createResourceRun,
  getRunLogs,
  listMcpRepoBundles,
  listMcpServers,
  type MCPConnectionBundleSummary,
  type MCPServerSummary,
  type ResourceCreatePayload,
  type ResourceRecord,
  type RunCreatePayload,
  type RunLogEntry,
  type RunRecord,
} from "../lib/controlCenterApi";
import { createScheduledRunProjections, type ScheduledOccurrence } from "../lib/scheduleOccurrences";
import { createJobFromForm, getDraftForms, getPendingPromotionResources, getSavedTemplates, mapJobToPendingPromotionResource, saveDraft, saveTemplate, subscribeToUserDashboardStore } from "../lib/userDashboardStore";
import type { Job as StoredJob } from "./resourcesData";
import {
  mockReadyForPromotion,
  mockPendingPromotions,
  mockRejectedPromotions,
  mockRecentlyPromoted,
  formatPromotionDate,
  getPromotionTypeColor,
} from "./promotionsData";
import {
  pendingRequiredActionsCount,
  requiredActionItems,
  requiredActionStateBadge,
  requiredActionUrgencyBadge,
  getUrgencyLabel,
} from "./requiredActionsData";

const MS_IN_24_HOURS = 24 * 60 * 60 * 1000;
const RESOURCE_SCHEDULES_UPDATED_EVENT = "control-center-resource-schedules-updated";

const isWithinLast24Hours = (date?: Date) => {
  if (!date) return false;
  const ageMs = Date.now() - date.getTime();
  return ageMs >= 0 && ageMs <= MS_IN_24_HOURS;
};

type DashboardJobListItem = {
  id: string;
  name: string;
  type: string;
  schedule: string;
  status: "Ready" | "Healthy" | "Running" | "Needs Attention";
  updatedAt: string;
  payload?: WorkspaceJobPayload;
};

const draftJobs = [
  { id: "draft-001", name: "Customer Retention Workflow", type: "Workflow", lastEdited: "1 hour ago" },
  { id: "draft-002", name: "Dealer Forecast Pipeline", type: "SQL", lastEdited: "3 hours ago" },
  { id: "draft-003", name: "Revenue Summary Agent", type: "AI Agent", lastEdited: "Yesterday" },
];

const activityTimeline = [
  { action: "Warranty Claims Rollup completed", timestamp: "10 minutes ago", icon: "✓" },
  { action: "Draft saved: Dealer Forecast Pipeline", timestamp: "2 hours ago", icon: "💾" },
  { action: "Customer Churn Analysis failed", timestamp: "1 hour ago", icon: "✕" },
  { action: "Retry policy review resolved", timestamp: "3 hours ago", icon: "✓" },
  { action: "Monthly Dealer KPI Deck scheduled", timestamp: "Yesterday", icon: "📅" },
];

// Mock run data for Runs/Calendar panel
interface RunItem {
  id: string;
  resourceId?: string;
  jobName: string;
  jobType: string;
  status: "scheduled" | "running" | "completed" | "failed";
  scheduledTime: Date;
  completedTime?: Date;
}

const formatRunTime = (date: Date): string => {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

const formatScheduledTime = (date: Date): string => {
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  
  const diffMs = date.getTime() - now.getTime();
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffHours < 24) return `Today, ${date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}`;
  if (diffDays === 1) return `Tomorrow, ${date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}`;
  
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};

const getJobTypeColor = (type: string): string => {
  switch (type) {
    case "PowerPoint":
      return "bg-orange-100 text-orange-700";
    case "Excel":
      return "bg-green-100 text-green-700";
    case "SQL":
      return "bg-blue-100 text-blue-700";
    case "Custom":
      return "bg-indigo-100 text-indigo-700";
    default:
      return "bg-gray-100 text-gray-700";
  }
};

const getRunStatusColor = (status: string): string => {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-700";
    case "running":
      return "bg-blue-100 text-blue-700";
    case "failed":
      return "bg-red-100 text-red-700";
    case "scheduled":
      return "bg-gray-100 text-gray-700";
    default:
      return "bg-gray-100 text-gray-700";
  }
};

const deriveWorkspaceSchedule = (draft?: Record<string, unknown>) => {
  if (!draft) return "Manual schedule";
  const scheduleType = typeof draft.scheduleType === "string" ? draft.scheduleType : "manual";
  const scheduleDay = typeof draft.scheduleDay === "string" ? draft.scheduleDay : "";
  const scheduleTime = typeof draft.scheduleTime === "string" ? draft.scheduleTime : "";
  const scheduleExpectation = typeof draft.scheduleExpectation === "string" ? draft.scheduleExpectation : "";

  if (scheduleType === "on-demand") return "On demand";
  if (scheduleType === "monthly") return `Monthly${scheduleDay ? `, day ${scheduleDay}` : ""}${scheduleTime ? ` at ${scheduleTime}` : ""}`;
  if (scheduleType === "weekly") return `Weekly${scheduleDay ? `, ${scheduleDay}` : ""}${scheduleTime ? ` at ${scheduleTime}` : ""}`;
  if (scheduleType === "daily") return `Daily${scheduleTime ? ` at ${scheduleTime}` : ""}`;
  if (scheduleExpectation.trim()) return scheduleExpectation;
  return "Manual schedule";
};

const weekdayOptions = [
  { label: "Sun", value: "0" },
  { label: "Mon", value: "1" },
  { label: "Tue", value: "2" },
  { label: "Wed", value: "3" },
  { label: "Thu", value: "4" },
  { label: "Fri", value: "5" },
  { label: "Sat", value: "6" },
];

const formatCustomScheduleSummary = (form: CustomFormBuilderState) => {
  if (form.scheduleCadence === "on-demand") return "Runs on demand";

  const stopSummary =
    form.stopCondition === "on-date" && form.endDate
      ? ` until ${form.endDate}`
      : form.stopCondition === "after-runs" && form.maxRuns
        ? ` for ${form.maxRuns} runs`
        : "";

  if (form.scheduleCadence === "daily") {
    return `Runs daily at ${form.scheduleTime}${stopSummary}`;
  }

  if (form.scheduleCadence === "weekly") {
    const selectedDays = weekdayOptions
      .filter((option) => form.weeklyDays.includes(option.value))
      .map((option) => option.label)
      .join(", ");
    return `Runs weekly on ${selectedDays || "selected days"} at ${form.scheduleTime}${stopSummary}`;
  }

  return `Runs monthly on day ${form.monthlyDay || "1"} at ${form.scheduleTime}${stopSummary}`;
};

const createWorkspaceJobPayload = (job: Record<string, unknown>, formCategory: string, draft?: Record<string, unknown>): WorkspaceJobPayload => {
  const name = typeof job.name === "string" ? job.name : "New Job";
  const type = formCategory === "PowerPoint" ? "PowerPoint" : formCategory === "Excel" ? "Excel" : "SQL";
  return {
    job_id: typeof job.id === "string" ? job.id : `job-${Date.now()}`,
    name,
    type,
    schedule: deriveWorkspaceSchedule(draft),
    status: "Healthy",
    description: typeof job.description === "string" ? job.description : `${formCategory} job created from the embedded form flow.`,
    inputs: [
      typeof draft?.owner === "string" ? `Owner: ${draft.owner}` : "Owner configured",
      `Form type: ${formCategory}`,
      "Submitted from user dashboard workspace",
    ],
    outputs: [
      type === "PowerPoint" ? `${name}.pptx` : type === "Excel" ? `${name}.xlsx` : `${name}.csv`,
      "Dashboard job record",
    ],
    steps: [
      { id: "step-1", name: "Validate form inputs", action: "Check required fields and configuration" },
      { id: "step-2", name: "Create job record", action: "Register the job in the workspace" },
      { id: "step-3", name: "Prepare schedule", action: "Apply execution cadence and delivery settings" },
      { id: "step-4", name: "Queue for execution", action: "Send the job to the next workflow stage" },
    ],
  };
};

const createCustomFormDraftPayload = (form: CustomFormBuilderState) => ({
  scheduleType: form.scheduleCadence,
  scheduleDay:
    form.scheduleCadence === "weekly"
      ? form.weeklyDays[0] ?? "1"
      : form.scheduleCadence === "monthly"
        ? form.monthlyDay || "1"
        : "",
  scheduleTime: form.scheduleCadence === "on-demand" ? "" : form.scheduleTime,
  scheduleDays: form.weeklyDays,
  scheduleStartDate: form.startDate,
  scheduleStopCondition: form.stopCondition,
  scheduleEndDate: form.stopCondition === "on-date" ? form.endDate : "",
  scheduleMaxRuns: form.stopCondition === "after-runs" ? form.maxRuns : "",
  scheduleExpectation: formatCustomScheduleSummary(form),
  jobName: form.formName,
  description: form.purpose,
  customJobType: form.jobType,
  targetUsers: form.targetUsers,
  outputDestination: form.outputDestination,
  requiredFields: form.requiredFields,
});

const mapStoredJobTypeToDashboardType = (type: StoredJob["type"]) => {
  if (type === "PowerPoint Deck") return "PowerPoint";
  if (type === "Excel Report") return "Excel";
  if (type === "Custom Job") return "Custom";
  if (type === "SQL Query") return "SQL";
  return type;
};

const mapStoredJobStatusToDashboardStatus = (status: StoredJob["status"]): DashboardJobListItem["status"] => {
  if (status === "running") return "Running";
  if (status === "pending") return "Needs Attention";
  return "Healthy";
};

const mapStoredJobToWorkspaceType = (type: StoredJob["type"]): "PowerPoint" | "Excel" | "SQL" => {
  if (type === "PowerPoint Deck") return "PowerPoint";
  if (type === "Excel Report") return "Excel";
  return "SQL";
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const getString = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value.trim() : null;

const titleCase = (value: string) =>
  value
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());

const normalizeResourceType = (type?: string | null) => {
  const normalized = type?.toLowerCase();
  if (normalized === "powerpoint" || normalized === "powerpoint deck") return "PowerPoint";
  if (normalized === "excel" || normalized === "excel report") return "Excel";
  if (normalized === "sql" || normalized === "sql query") return "SQL";
  if (normalized === "mcp") return "MCP";
  if (normalized === "research") return "Research";
  return type ? titleCase(type) : "Custom";
};

const getNestedRecord = (record: Record<string, unknown> | null | undefined, key: string) => {
  const value = record?.[key];
  return isRecord(value) ? value : null;
};

const getRunMetadata = (run: RunRecord) => {
  const submitted = isRecord(run.submitted_config_json) ? run.submitted_config_json : null;
  const resolved = isRecord(run.resolved_job_spec_json) ? run.resolved_job_spec_json : null;
  const draft = getNestedRecord(submitted, "draft");
  const jobConfig = getNestedRecord(submitted, "job_config");
  const metadata = getNestedRecord(jobConfig, "metadata");

  return { submitted, resolved, draft, jobConfig, metadata };
};

const resolveRunJobName = (run: RunRecord, resource?: ResourceRecord) => {
  const { resolved, draft, metadata } = getRunMetadata(run);
  return (
    getString(resource?.name) ||
    getString(resolved?.name) ||
    getString(draft?.name) ||
    getString(metadata?.name) ||
    getString(metadata?.job_name) ||
    `Run ${run.id}`
  );
};

const resolveRunJobType = (run: RunRecord, resource?: ResourceRecord) => {
  const { draft, metadata } = getRunMetadata(run);
  return normalizeResourceType(
    getString(resource?.type) ||
      getString(draft?.jobType) ||
      getString(metadata?.job_type) ||
      getString(run.execution_backend) ||
      "Custom"
  );
};

const resolveRunSchedule = (run: RunRecord, resource?: ResourceRecord) => {
  const { resolved, jobConfig } = getRunMetadata(run);
  const resourceConfig = isRecord(resource?.config) ? resource.config : null;
  return (
    getString(resolved?.schedule) ||
    getString(jobConfig?.schedule) ||
    getString(resourceConfig?.schedule) ||
    (run.trigger_source === "schedule" ? "Scheduled run" : "On demand")
  );
};

const mapRunStatusToDashboardStatus = (status: string): DashboardJobListItem["status"] => {
  const normalized = status.toLowerCase();
  if (["queued", "running", "executing", "in_progress"].includes(normalized)) return "Running";
  if (["failed", "stopped", "cancelled", "canceled", "blocked", "requires_approval"].includes(normalized)) {
    return "Needs Attention";
  }
  return "Healthy";
};

const mapRunStatusToRunItemStatus = (status: string): RunItem["status"] => {
  const normalized = status.toLowerCase();
  if (["queued", "scheduled", "pending"].includes(normalized)) return "scheduled";
  if (["running", "executing", "in_progress"].includes(normalized)) return "running";
  if (["failed", "stopped", "cancelled", "canceled", "blocked"].includes(normalized)) return "failed";
  return "completed";
};

const getDashboardJobStatusClasses = (status: DashboardJobListItem["status"]) => {
  if (status === "Ready") return "bg-amber-100 text-amber-700";
  if (status === "Healthy") return "bg-green-100 text-green-700";
  if (status === "Running") return "bg-blue-100 text-blue-700";
  return "bg-red-100 text-red-700";
};

const createWorkspaceJobPayloadFromStoredJob = (job: StoredJob): WorkspaceJobPayload => {
  const scheduleMessage =
    job.logs?.find((entry) => entry.message.toLowerCase().includes("runs "))?.message ?? "Manual schedule";

  return {
    job_id: job.id,
    name: job.name,
    type: mapStoredJobToWorkspaceType(job.type),
    schedule: scheduleMessage,
    status: mapStoredJobStatusToDashboardStatus(job.status),
    description: job.description ?? `${job.type} job created from the user workspace.`,
    inputs: [
      `Job type: ${job.type}`,
      `Environment: ${job.environment ?? "Dev"}`,
      "Submitted from user dashboard workspace",
    ],
    outputs: [
      mapStoredJobToWorkspaceType(job.type) === "PowerPoint"
        ? `${job.name}.pptx`
        : mapStoredJobToWorkspaceType(job.type) === "Excel"
          ? `${job.name}.xlsx`
          : `${job.name}.csv`,
      "Dashboard job record",
    ],
    steps: [
      { id: "step-1", name: "Validate form inputs", action: "Check required fields and configuration" },
      { id: "step-2", name: "Create job record", action: "Register the job in the workspace" },
      { id: "step-3", name: "Prepare schedule", action: "Apply execution cadence and delivery settings" },
      { id: "step-4", name: "Queue for execution", action: "Send the job to the next workflow stage" },
    ],
  };
};

const createWorkspaceJobPayloadFromRun = (run: RunRecord, resource?: ResourceRecord): WorkspaceJobPayload => {
  const name = resolveRunJobName(run, resource);
  const type = resolveRunJobType(run, resource);
  const schedule = resolveRunSchedule(run, resource);
  const status = mapRunStatusToDashboardStatus(run.status);
  const { resolved } = getRunMetadata(run);
  const tasks = Array.isArray(resolved?.tasks) ? resolved.tasks : [];

  return {
    job_id: resource?.id ?? run.resource_id,
    name,
    type: type as WorkspaceJobPayload["type"],
    schedule,
    status,
    description:
      getString(resolved?.description) ||
      getString(resolved?.intent) ||
      `Latest database run ${run.id} for ${name}.`,
    inputs: [
      `Resource ID: ${run.resource_id}`,
      `Environment: ${run.target_environment}`,
      `Action: ${run.action}`,
    ],
    outputs: [
      run.connector_run_id ? `Connector run: ${run.connector_run_id}` : "Control Center run record",
      run.workflow_url ? `Workflow: ${run.workflow_url}` : "Execution metadata",
    ],
    steps:
      tasks.length > 0
        ? tasks.map((task, index) => ({
            id: `task-${index + 1}`,
            name: String(task),
            action: "Run task from resolved job spec",
          }))
        : [
            { id: "step-1", name: "Create run", action: `Submitted by ${run.requested_by}` },
            { id: "step-2", name: "Evaluate risk", action: `${run.risk_level} risk, score ${run.risk_score}` },
            { id: "step-3", name: "Execute", action: run.error || `Current status: ${run.status}` },
          ],
  };
};

const createWorkspaceJobPayloadFromResource = (resource: ResourceRecord): WorkspaceJobPayload => {
  const config = resource.config ?? {};
  const schedule = getString(config.schedule) || "Manual run";
  const type = normalizeResourceType(resource.type);

  return {
    job_id: resource.id,
    name: resource.name,
    type: type as WorkspaceJobPayload["type"],
    schedule,
    status: "Healthy",
    description: getString(config.description) || `Registered ${type} resource ready to run.`,
    inputs: [
      `Resource ID: ${resource.id}`,
      `Environment: ${resource.environment}`,
      `Connector: ${resource.connector}`,
    ],
    outputs: ["Control Center run record", "Execution metadata"],
    steps: [
      { id: "step-1", name: "Registered", action: "Saved in the Control Center resources table" },
      { id: "step-2", name: "Ready", action: "Available for manual or chatbot-triggered runs" },
    ],
  };
};

const createDashboardJobs = (runs: RunRecord[], resources: ResourceRecord[]): DashboardJobListItem[] => {
  const jobResources = resources.filter((resource) => resource.type !== "repo_connection");
  const resourceById = new Map(jobResources.map((resource) => [resource.id, resource]));
  const latestRunByResource = new Map<string, RunRecord>();

  [...runs]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .forEach((run) => {
      if (!latestRunByResource.has(run.resource_id)) {
        latestRunByResource.set(run.resource_id, run);
      }
    });

  return jobResources.map((resource) => {
    const run = latestRunByResource.get(resource.id);
    if (!run) {
      const payload = createWorkspaceJobPayloadFromResource(resource);
      return {
        id: resource.id,
        name: resource.name,
        type: payload.type,
        schedule: payload.schedule,
        status: "Ready" as const,
        updatedAt: resource.updated_at,
        payload,
      };
    }

    const resolvedResource = resourceById.get(run.resource_id);
    const payload = createWorkspaceJobPayloadFromRun(run, resolvedResource);
    return {
      id: run.resource_id,
      name: payload.name,
      type: payload.type,
      schedule: payload.schedule,
      status: payload.status as DashboardJobListItem["status"],
      updatedAt: run.updated_at,
      payload,
    };
  });
};

type RepoConnectionFormState = {
  repo: string;
  ref: string;
  path: string;
  displayName: string;
  description: string;
};

const DEFAULT_REPO_CONNECTION_FORM: RepoConnectionFormState = {
  repo: "",
  ref: "",
  path: "",
  displayName: "",
  description: "",
};

const normalizeGithubRepoInput = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) return "";

  const httpsMatch = trimmed.match(/github\.com\/([^/\s]+\/[^/\s#?]+?)(?:\.git)?(?:[#?].*)?$/i);
  if (httpsMatch) return httpsMatch[1].replace(/\/+$/, "");

  const sshMatch = trimmed.match(/github\.com:([^/\s]+\/[^/\s]+?)(?:\.git)?$/i);
  if (sshMatch) return sshMatch[1].replace(/\/+$/, "");

  return trimmed.replace(/^(https?:\/\/)?github\.com\//i, "").replace(/\.git$/i, "").replace(/^\/+|\/+$/g, "");
};

const isValidGithubRepoSlug = (value: string): boolean => /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(value);

const getRepoConnectionName = (repoSlug: string, explicitName?: string): string => {
  const preferredName = explicitName.trim();
  if (preferredName) return preferredName;
  const repoName = repoSlug.split("/")[1] ?? repoSlug;
  return `${repoName}-repo`;
};

const createDashboardRuns = (runs: RunRecord[], resources: ResourceRecord[], scheduledOccurrences: ScheduledOccurrence[] = []) => {
  const resourceById = new Map(resources.map((resource) => [resource.id, resource]));
  const mappedRuns = runs.map((run) => {
    const resource = resourceById.get(run.resource_id);
    const status = mapRunStatusToRunItemStatus(run.status);
    const scheduledTime = new Date(run.created_at);
    return {
      id: run.id,
      resourceId: run.resource_id,
      jobName: resolveRunJobName(run, resource),
      jobType: resolveRunJobType(run, resource),
      status,
      scheduledTime,
      completedTime: status === "scheduled" || status === "running" ? undefined : new Date(run.updated_at),
    };
  });
  const projectedRuns = scheduledOccurrences.map((occurrence) => ({
    id: occurrence.id,
    resourceId: occurrence.resourceId,
    jobName: occurrence.jobName,
    jobType: occurrence.jobType,
    status: "scheduled" as const,
    scheduledTime: occurrence.scheduledTime,
  }));

  const upcomingRuns = [...mappedRuns, ...projectedRuns]
    .filter((run) => run.status === "scheduled" || run.status === "running")
    .sort((a, b) => a.scheduledTime.getTime() - b.scheduledTime.getTime());

  const recentRuns = mappedRuns
    .filter((run) => run.status === "completed" || run.status === "failed")
    .sort((a, b) => (b.completedTime?.getTime() ?? b.scheduledTime.getTime()) - (a.completedTime?.getTime() ?? a.scheduledTime.getTime()));

  return { upcomingRuns, recentRuns };
};

const mockTemplates = [
  { 
    id: "template-001", 
    name: "Monthly Dealer KPI Deck", 
    category: "PowerPoint",
    description: "Executive summary with dealer performance KPIs",
    useCase: "Monthly dealer reporting"
  },
  { 
    id: "template-002", 
    name: "Executive Dashboard Report", 
    category: "Dashboard",
    description: "Real-time KPI dashboard with charts and metrics",
    useCase: "Executive dashboards"
  },
  { 
    id: "template-003", 
    name: "Customer Retention Workflow", 
    category: "Workflow",
    description: "Automated workflow for identifying at-risk customers",
    useCase: "Customer retention strategy"
  },
  { 
    id: "template-004", 
    name: "SQL Data Quality Check", 
    category: "SQL",
    description: "Comprehensive data quality validation script",
    useCase: "Data validation and auditing"
  },
  { 
    id: "template-005", 
    name: "Retry Policy Review Form", 
    category: "Form",
    description: "Form for reviewing and approving retry policies",
    useCase: "Policy management"
  },
  { 
    id: "template-006", 
    name: "Weekly Sales Performance Deck", 
    category: "PowerPoint",
    description: "Sales performance analysis with trend analysis",
    useCase: "Weekly sales reporting"
  },
  { 
    id: "template-007", 
    name: "Inventory Forecast Model", 
    category: "SQL",
    description: "Machine learning model for inventory forecasting",
    useCase: "Supply chain optimization"
  },
  { 
    id: "template-008", 
    name: "Financial Reconciliation Workflow", 
    category: "Workflow",
    description: "Automated financial data reconciliation",
    useCase: "Financial reporting"
  },
];

const preBuiltForms = [
  {
    id: "prebuilt-excel",
    name: "Excel Report Form",
    category: "Excel",
    description: "Build scheduled Excel exports and report deliveries.",
    route: "/excel-report",
    useCase: "Recurring Excel-based reporting",
  },
  {
    id: "prebuilt-sql",
    name: "SQL Job Form",
    category: "SQL",
    description: "Create SQL-based reporting and transformation jobs.",
    route: "/sql-job",
    useCase: "Query and transformation workflows",
  },
  {
    id: "prebuilt-powerpoint",
    name: "PowerPoint Job Form",
    category: "PowerPoint",
    description: "Generate presentation jobs for executive and business reporting.",
    route: "/powerpoint",
    useCase: "Presentation and deck generation",
  },
];

interface JobStep {
  id: string;
  name: string;
  action: string;
}

interface JobSpec {
  job_id: string;
  name: string;
  type: string;
  schedule: string;
  status: "Healthy" | "Running" | "Needs Attention" | "Failed";
  inputs: string[];
  outputs: string[];
  steps: JobStep[];
}

type WorkspaceJobPayload = JobSpec & {
  description?: string;
};

const mockJobSpecs: Record<string, JobSpec> = {
  "Monthly Dealer KPI Deck": {
    job_id: "job-001",
    name: "Monthly Dealer KPI Deck",
    type: "PowerPoint",
    schedule: "Monthly, day 1",
    status: "Healthy",
    inputs: ["Sales data", "Dealer metrics", "Regional targets"],
    outputs: ["KPI_Deck_202602.pptx", "Performance metrics"],
    steps: [
      { id: "step-1", name: "Extract dealer data", action: "Query dealer database" },
      { id: "step-2", name: "Calculate KPIs", action: "Aggregate metrics" },
      { id: "step-3", name: "Generate slides", action: "Create PowerPoint" },
      { id: "step-4", name: "Send to stakeholders", action: "Email distribution" },
    ],
  },
  "Warranty Claims Rollup": {
    job_id: "job-002",
    name: "Warranty Claims Rollup",
    type: "Excel",
    schedule: "Weekly, Mon 08:00",
    status: "Running",
    inputs: ["Claims database", "Service records"],
    outputs: ["Weekly_Claims_Report.xlsx"],
    steps: [
      { id: "step-1", name: "Extract claims", action: "Query claims system" },
      { id: "step-2", name: "Validate data", action: "Data quality check" },
      { id: "step-3", name: "Create summary", action: "Build Excel workbook" },
      { id: "step-4", name: "Distribute", action: "Email to team" },
    ],
  },
  "Customer Churn Analysis": {
    job_id: "job-003",
    name: "Customer Churn Analysis",
    type: "SQL",
    schedule: "Daily, 06:00",
    status: "Needs Attention",
    inputs: ["Customer interactions", "Purchase history", "Support tickets"],
    outputs: ["churn_risk_scores.csv", "alerts.json"],
    steps: [
      { id: "step-1", name: "Load customer data", action: "SQL query" },
      { id: "step-2", name: "Calculate churn risk", action: "Apply ML model" },
      { id: "step-3", name: "Generate alerts", action: "Identify high-risk customers" },
      { id: "step-4", name: "Store results", action: "Save to database" },
    ],
  },
  "Quarterly Revenue Report": {
    job_id: "job-004",
    name: "Quarterly Revenue Report",
    type: "PowerPoint",
    schedule: "Quarterly, day 1",
    status: "Healthy",
    inputs: ["Revenue data", "Expense reports", "Growth metrics"],
    outputs: ["Q1_Revenue_Report.pptx", "Financial summary"],
    steps: [
      { id: "step-1", name: "Aggregate revenue", action: "Query financial database" },
      { id: "step-2", name: "Calculate metrics", action: "Compute growth rates" },
      { id: "step-3", name: "Create presentation", action: "Build PowerPoint slides" },
      { id: "step-4", name: "Executive review", action: "Prepare for board meeting" },
    ],
  },
};

interface AIMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: Date;
}

interface WorkspaceTab {
  id: string;
  type: "dashboard" | "job" | "required-action" | "template" | "promotion" | "revision" | "create-job" | "active-jobs" | "pending-approvals" | "failed-runs" | "saved-jobs";
  title: string;
  closable: boolean;
  jobName?: string;
  actionId?: string;
  templateId?: string;
  templateName?: string;
  promotionId?: string;
  revisionJobName?: string;
  revisionJobType?: string;
  revisionRejectionReason?: string;
  payload?: Record<string, any>;
}

type FormWorkspacePayload = {
  id: string;
  name: string;
  category: string;
  description: string;
  useCase: string;
  route: string;
  origin?: "saved-template" | "prebuilt-form" | "draft-form" | "blank-form";
  progress?: string;
  lastEdited?: string;
  draft?: Record<string, unknown>;
};

type CustomFormBuilderState = {
  formName: string;
  purpose: string;
  jobType: string;
  targetUsers: string;
  outputDestination: string;
  scheduleCadence: "on-demand" | "daily" | "weekly" | "monthly";
  scheduleTime: string;
  weeklyDays: string[];
  monthlyDay: string;
  startDate: string;
  stopCondition: "never" | "on-date" | "after-runs";
  endDate: string;
  maxRuns: string;
  requiredFields: string;
};

interface WorkspacePane {
  tabs: WorkspaceTab[];
  activeTabId: string;
}

interface WorkspaceState {
  mode: "single" | "split";
  primary: WorkspacePane;
  secondary: WorkspacePane;
  secondaryPosition: "left" | "right";
}

export default function UserHome() {
  const navigate = useNavigate();
  const {
    resources,
    runs,
    loading: jobRunsLoading,
    error: jobRunsError,
    refresh: refreshJobRuns,
  } = useJobRuns();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [activePanelId, setActivePanelId] = useState<string | null>(null);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [jobDetailTab, setJobDetailTab] = useState<"overview" | "runs" | "settings">("overview");
  
  // Panel resize state
  const [jobsPanelWidth, setJobsPanelWidth] = useState(280);
  const [chatPanelWidth, setChatPanelWidth] = useState(400);
  const [workspacePaneAWidth, setWorkspacePaneAWidth] = useState(500);
  const [isResizing, setIsResizing] = useState<"jobs" | "workspace" | "chat" | null>(null);
  const lastResizeX = useRef<number>(0);
  
  // Workspace state - supports both single and split modes
  const [workspace, setWorkspace] = useState<WorkspaceState>({
    mode: "single",
    primary: {
      tabs: [{ id: "dashboard", type: "dashboard", title: "Dashboard", closable: false }],
      activeTabId: "dashboard",
    },
    secondary: {
      tabs: [],
      activeTabId: "",
    },
    secondaryPosition: "right",
  });
  
  // Job draft state - holds data being created via chat
  const [jobDraft, setJobDraft] = useState<Record<string, any>>({});
  const [isRegisteringJob, setIsRegisteringJob] = useState(false);
  const [chatAssistantNotices, setChatAssistantNotices] = useState<Array<{ id: string; content: string }>>([]);
  const autoRegisteredDraftKeyRef = useRef<string | null>(null);
  
  // Console events for live job creation workflow tracking
  interface ConsoleEvent {
    id: string;
    timestamp: Date;
    type: "intent_detected" | "draft_created" | "extracted_fields" | "draft_updated" | "missing_fields_identified";
    message: string;
    data?: Record<string, any>;
    previousValues?: Record<string, any>;
  }
  const [consoleEvents, setConsoleEvents] = useState<ConsoleEvent[]>([]);
  
  const [isAIPanelOpen, setIsAIPanelOpen] = useState(false);
  const [isChatPanelOpen, setIsChatPanelOpen] = useState(true);
  const [templateSearch, setTemplateSearch] = useState("");
  const [jobSearch, setJobSearch] = useState("");
  const [jobSort, setJobSort] = useState<"name" | "status" | "type" | "recently-updated">("name");
  const [jobFilter, setJobFilter] = useState<string>("all");
  const [runningJobIds, setRunningJobIds] = useState<string[]>([]);
  const [templateSort, setTemplateSort] = useState<"name" | "category" | "recently-used" | "recommended">("name");
  const [templateFilter, setTemplateFilter] = useState<"all" | "PowerPoint" | "Excel" | "SQL" | "Workflow" | "Form" | "Dashboard">("all");
  const [selectedPromotions, setSelectedPromotions] = useState<string[]>([]);
  const [highlightedPendingPromotionId, setHighlightedPendingPromotionId] = useState<string | null>(null);
  const [promotionSubmissionMessage, setPromotionSubmissionMessage] = useState<string | null>(null);
  const [rejectedPromotionsState, setRejectedPromotionsState] = useState(mockRejectedPromotions);
  const [pendingPromotionsState, setPendingPromotionsState] = useState(mockPendingPromotions);
  const [submittedPromotions, setSubmittedPromotions] = useState(() => getPendingPromotionResources());
  const [availableMcpServers, setAvailableMcpServers] = useState<MCPServerSummary[]>([]);
  const [repoConnectionBundles, setRepoConnectionBundles] = useState<MCPConnectionBundleSummary[]>([]);
  const [repoConnectionForm, setRepoConnectionForm] = useState<RepoConnectionFormState>(DEFAULT_REPO_CONNECTION_FORM);
  const [repoConnectionError, setRepoConnectionError] = useState<string | null>(null);
  const [repoConnectionSuccess, setRepoConnectionSuccess] = useState<string | null>(null);
  const [isSavingRepoConnection, setIsSavingRepoConnection] = useState(false);
  const [consoleHeight, setConsoleHeight] = useState(50);
  const [consoleActiveTab, setConsoleActiveTab] = useState<"json" | "logs" | "events">("json");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runLogs, setRunLogs] = useState<RunLogEntry[]>([]);
  const [expandedActionId, setExpandedActionId] = useState<string | null>(null);
  const [isResizingConsole, setIsResizingConsole] = useState(false);
  const lastResizeY = useRef<number>(0);
  const workspaceRef = useRef<HTMLDivElement>(null);
  const [isDraggingOverWorkspace, setIsDraggingOverWorkspace] = useState(false);
  const [isDraggingOverSplitZone, setIsDraggingOverSplitZone] = useState<"left" | "right" | false>(false);
  const [isDraggingOverPane, setIsDraggingOverPane] = useState<"left" | "right" | false>(false);
  const [aiMessages, setAiMessages] = useState<AIMessage[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hi! I'm your AI Assistant. I can help you modify this job specification. What would you like to change?",
      timestamp: new Date(Date.now() - 5000),
    },
    {
      id: "2",
      role: "user",
      content: "How can you help me?",
      timestamp: new Date(Date.now() - 3000),
    },
    {
      id: "3",
      role: "assistant",
      content: "I can help you:\n• Modify job inputs and outputs\n• Adjust the execution schedule\n• Update job steps and actions\n• Change job parameters and settings\n\nJust tell me what you'd like to change in natural language!",
      timestamp: new Date(),
    },
  ]);
  const [aiInput, setAiInput] = useState("");
  const baseDashboardJobs = useMemo(() => createDashboardJobs(runs, resources), [runs, resources]);
  const connectedRepoResources = useMemo(
    () => resources.filter((resource) => resource.type === "repo_connection"),
    [resources],
  );
  const dashboardJobs = useMemo(
    () =>
      baseDashboardJobs.map((job) =>
        runningJobIds.includes(job.id)
          ? {
              ...job,
              status: "Running" as const,
            }
          : job,
      ),
    [baseDashboardJobs, runningJobIds],
  );
  const scheduledRunProjections = useMemo(() => createScheduledRunProjections(resources), [resources]);
  const dashboardRuns = useMemo(() => createDashboardRuns(runs, resources, scheduledRunProjections), [runs, resources, scheduledRunProjections]);
  const activeDashboardJobs = useMemo(
    () => dashboardJobs.filter((job) => job.status === "Running" || job.status === "Healthy"),
    [dashboardJobs],
  );
  const runningDashboardJobs = useMemo(
    () => dashboardJobs.filter((job) => job.status === "Running"),
    [dashboardJobs],
  );
  const githubMcpServer = useMemo(
    () => availableMcpServers.find((server) => server.name === "github") ?? null,
    [availableMcpServers],
  );
  const preferredRepoBundle = useMemo(
    () => repoConnectionBundles.find((bundle) => bundle.primary_server === "github") ?? null,
    [repoConnectionBundles],
  );
  const failedRunsLast24h = useMemo(
    () =>
      dashboardRuns.recentRuns.filter(
        (run) => run.status === "failed" && isWithinLast24Hours(run.completedTime ?? run.scheduledTime),
      ),
    [dashboardRuns.recentRuns],
  );
  const pendingApprovalPromotions = useMemo(
    () => [...submittedPromotions, ...pendingPromotionsState],
    [submittedPromotions, pendingPromotionsState],
  );
  const promotionQueueCounts = useMemo(
    () => ({
      ready: mockReadyForPromotion.length,
      pending: pendingApprovalPromotions.length,
      needsRevision: rejectedPromotionsState.length,
    }),
    [pendingApprovalPromotions.length, rejectedPromotionsState.length],
  );
  const urgentActionCount = useMemo(
    () => requiredActionItems.filter((action) => action.urgency === "urgent").length,
    [],
  );
  const dashboardKpis = useMemo(
    () => [
      {
        label: "My Active Jobs",
        value: activeDashboardJobs.length,
        hint: `${runningDashboardJobs.length} running, ${activeDashboardJobs.length - runningDashboardJobs.length} healthy`,
        tone: "text-green-600",
        tabType: "active-jobs" as const,
      },
      {
        label: "Pending Approvals",
        value: pendingApprovalPromotions.length,
        hint: `${pendingApprovalPromotions.length === 1 ? "1 request" : `${pendingApprovalPromotions.length} requests`} waiting`,
        tone: "text-amber-600",
        tabType: "pending-approvals" as const,
      },
      {
        label: "Failed Runs (24h)",
        value: failedRunsLast24h.length,
        hint: failedRunsLast24h.length === 0 ? "No failures in view" : "Needs review",
        tone: "text-red-600",
        tabType: "failed-runs" as const,
      },
      {
        label: "Saved Jobs",
        value: dashboardJobs.length,
        hint: `${dashboardJobs.filter((job) => job.status === "Ready").length} ready to run`,
        tone: "text-[#ed0923]",
        tabType: "saved-jobs" as const,
      },
    ],
    [activeDashboardJobs, dashboardJobs, failedRunsLast24h.length, pendingApprovalPromotions.length, runningDashboardJobs.length],
  );
  const filteredDashboardRuns = useMemo(() => {
    if (!selectedResourceId) return dashboardRuns;
    const filtered = runs.filter((r) => r.resource_id === selectedResourceId);
    const projected = scheduledRunProjections.filter((run) => run.resourceId === selectedResourceId);
    return createDashboardRuns(filtered, resources, projected);
  }, [runs, resources, selectedResourceId, dashboardRuns, scheduledRunProjections]);
  const selectedResourceName = useMemo(
    () => resources.find((r) => r.id === selectedResourceId)?.name ?? null,
    [resources, selectedResourceId]
  );
  const [customFormBuilder, setCustomFormBuilder] = useState<CustomFormBuilderState>({
    formName: "",
    purpose: "",
    jobType: "",
    targetUsers: "",
    outputDestination: "",
    scheduleCadence: "weekly",
    scheduleTime: "09:00",
    weeklyDays: ["1"],
    monthlyDay: "1",
    startDate: new Date().toISOString().slice(0, 10),
    stopCondition: "never",
    endDate: "",
    maxRuns: "12",
    requiredFields: "",
  });
  const draftForms = getDraftForms();
  const savedTemplates = getSavedTemplates();
  const customFormDraftPayload = createCustomFormDraftPayload(customFormBuilder);

  useEffect(() => {
    setSubmittedPromotions(getPendingPromotionResources());
    return subscribeToUserDashboardStore(() => {
      setSubmittedPromotions(getPendingPromotionResources());
    });
  }, []);

  useEffect(() => {
    const token = getAuthToken();
    void Promise.all([
      listMcpServers(token).catch(() => ({ items: [] as MCPServerSummary[] })),
      listMcpRepoBundles("dev", token).catch(() => ({ items: [] as MCPConnectionBundleSummary[] })),
    ]).then(([serversResponse, bundlesResponse]) => {
      setAvailableMcpServers(serversResponse.items);
      setRepoConnectionBundles(bundlesResponse.items);
    });
  }, []);

  const handleCustomFormFieldChange = (field: keyof CustomFormBuilderState, value: string) => {
    setCustomFormBuilder((prev) => ({ ...prev, [field]: value }));
  };

  const handleWeeklyDayToggle = (dayValue: string) => {
    setCustomFormBuilder((prev) => {
      const alreadySelected = prev.weeklyDays.includes(dayValue);
      const nextDays = alreadySelected
        ? prev.weeklyDays.filter((day) => day !== dayValue)
        : [...prev.weeklyDays, dayValue].sort();

      return {
        ...prev,
        weeklyDays: nextDays.length > 0 ? nextDays : [dayValue],
      };
    });
  };

  const handleCustomFormSaveDraft = () => {
    saveDraft("Custom", customFormDraftPayload);
    openFormTab({
      id: "forms-hub",
      name: "Forms Hub",
      category: "Forms Hub",
      description: "Browse drafts, saved templates, and pre-built job forms.",
      useCase: "Start or resume a form workflow",
      route: "/forms",
    });
  };

  const handleCustomFormSaveTemplate = () => {
    saveTemplate("Custom", customFormDraftPayload);
    openFormTab({
      id: "saved-templates-hub",
      name: "Saved Templates",
      category: "Forms Hub",
      description: "Browse and reuse saved form templates created by users.",
      useCase: "Reusable AI-assisted form templates",
      route: "/forms/saved-templates",
      origin: "saved-template",
    });
  };

  const handleSubmittedForApproval = (job: StoredJob, fallbackName: string) => {
    const promotionPayload = mapJobToPendingPromotionResource(job);
    setActivePanelId("promotions-edits");
    setHighlightedPendingPromotionId(promotionPayload.id);
    setPromotionSubmissionMessage(`${promotionPayload.name || fallbackName} was submitted for approval.`);
    handleOpenTabInPane(
      {
        type: "promotion",
        name: promotionPayload.name || fallbackName,
        id: promotionPayload.id,
        payload: promotionPayload,
      },
      "primary"
    );
  };

  const handleCustomFormCreateJob = () => {
    const createdJob = createJobFromForm("Custom", customFormDraftPayload);
    handleSubmittedForApproval(createdJob, "New Custom Job");
  };

  // Console helper functions
  const getConsoleJSON = () => {
    // If there are active console events (job creation workflow), show the latest event
    if (consoleEvents.length > 0) {
      const latestEvent = consoleEvents[consoleEvents.length - 1];
      return {
        event: latestEvent.type,
        message: latestEvent.message,
        timestamp: latestEvent.timestamp.toISOString(),
        ...latestEvent.data,
        ...(latestEvent.previousValues && { previous_values: latestEvent.previousValues }),
      };
    }

    // Otherwise show the current job spec or template
    if (activeTab?.type === "job" && jobSpec) {
      return {
        job_id: jobSpec.job_id,
        name: jobSpec.name,
        type: jobSpec.type,
        schedule: jobSpec.schedule,
        status: jobSpec.status,
        inputs: jobSpec.inputs,
        outputs: jobSpec.outputs,
        steps: jobSpec.steps,
      };
    }
    if (activeTab?.type === "template") {
      const template = (activeTab.payload as FormWorkspacePayload | undefined) ?? mockTemplates.find((t) => t.id === activeTab.templateId);
      if (template) {
        return {
          template_id: template.id,
          name: template.name,
          category: template.category,
          description: template.description,
          useCase: template.useCase,
          route: "route" in template ? template.route : undefined,
          created_at: new Date().toISOString(),
          last_modified: new Date().toISOString(),
        };
      }
    }

    // Show current draft if one is active
    if (Object.keys(jobDraft).length > 0) {
      return {
        draft_status: "active",
        fields: jobDraft,
        event_count: consoleEvents.length,
      };
    }

    return { message: "No item selected. Open a job or template to inspect its structure." };
  };

  const getConsoleLogs = () => {
    // Prefer real run logs when available
    if (runLogs.length > 0) {
      return runLogs.map((log) => ({
        time: (() => { try { return new Date(log.timestamp).toLocaleTimeString(); } catch { return log.timestamp; } })(),
        message: log.message,
        level: log.level,
      }));
    }
    // Fall back to workflow console events
    if (consoleEvents.length > 0) {
      return consoleEvents.map((event) => ({
        time: formatConsoleTime(event.timestamp),
        message: event.message,
        level: "INFO",
      }));
    }
    return [];
  };

  const getConsoleEvents = () => {
    // If there are workflow events, show them as structured events
    if (consoleEvents.length > 0) {
      return consoleEvents.map((event) => ({
        action: event.message,
        timestamp: formatConsoleTime(event.timestamp),
        type: event.type,
        details: event.data ? JSON.stringify(event.data, null, 2) : undefined,
      }));
    }

    // Otherwise show default system events
    return [
      { action: "User opened job", timestamp: "2 minutes ago" },
      { action: "System triggered scheduled run", timestamp: "5 minutes ago" },
      { action: "User modified job schedule", timestamp: "15 minutes ago" },
      { action: "Job validation passed", timestamp: "1 hour ago" },
      { action: "User added new input source", timestamp: "2 hours ago" },
      { action: "System backed up job configuration", timestamp: "3 hours ago" },
    ];
  };

  // Fetch run logs whenever activeRunId changes, polling until the run reaches a terminal state
  useEffect(() => {
    if (!activeRunId) return;
    let stopped = false;

    const fetchLogs = async () => {
      try {
        const result = await getRunLogs(activeRunId, getAuthToken());
        if (!stopped) {
          setRunLogs(result.logs);
          // Stop polling once the run is in a terminal state
          const terminal = ["completed", "failed", "stopped", "cancelled", "canceled"];
          if (terminal.includes(result.status.toLowerCase())) stopped = true;
        }
      } catch {
        // ignore fetch errors silently
      }
    };

    void fetchLogs();
    const interval = setInterval(() => { if (!stopped) void fetchLogs(); }, 2500);
    return () => { stopped = true; clearInterval(interval); };
  }, [activeRunId]);

  const CONSOLE_COLLAPSED_HEIGHT = 50;
  const CONSOLE_EXPANDED_HEIGHT = 300;
  const CONSOLE_MIN_HEIGHT = 40;
  // Console max height is capped to 60% of viewport to ensure workspace remains usable
  const CONSOLE_MAX_HEIGHT = Math.min(800, Math.max(300, window.innerHeight * 0.6));

  const toggleConsole = () => {
    if (consoleHeight <= 80) {
      setConsoleHeight(CONSOLE_EXPANDED_HEIGHT);
    } else {
      setConsoleHeight(CONSOLE_COLLAPSED_HEIGHT);
    }
  };

  const handleConsoleResizeStart = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsResizingConsole(true);
    lastResizeY.current = e.clientY;
  };

  useEffect(() => {
    if (!isResizingConsole) return;

    const handleMouseMove = (e: MouseEvent) => {
      e.preventDefault();
      const delta = lastResizeY.current - e.clientY;
      const newHeight = Math.max(CONSOLE_MIN_HEIGHT, Math.min(CONSOLE_MAX_HEIGHT, consoleHeight + delta));
      setConsoleHeight(newHeight);
      lastResizeY.current = e.clientY;
    };

    const handleMouseUp = () => {
      setIsResizingConsole(false);
      document.body.style.userSelect = "auto";
      document.body.style.cursor = "auto";
    };

    // Use capture phase to ensure events are caught even if blocked by nested elements
    document.addEventListener("mousemove", handleMouseMove, true);
    document.addEventListener("mouseup", handleMouseUp, true);
    
    // Prevent text selection while resizing
    document.body.style.userSelect = "none";
    document.body.style.cursor = "row-resize";

    return () => {
      document.removeEventListener("mousemove", handleMouseMove, true);
      document.removeEventListener("mouseup", handleMouseUp, true);
      document.body.style.userSelect = "auto";
      document.body.style.cursor = "auto";
    };
  }, [isResizingConsole, consoleHeight]);

  // Emit a console event for live job creation workflow tracking
  const emitConsoleEvent = (
    type: "intent_detected" | "draft_created" | "extracted_fields" | "draft_updated" | "missing_fields_identified",
    message: string,
    data?: Record<string, any>,
    previousValues?: Record<string, any>
  ) => {
    const event: ConsoleEvent = {
      id: Date.now().toString(),
      timestamp: new Date(),
      type,
      message,
      data,
      previousValues,
    };
    setConsoleEvents((prev) => [...prev, event]);
  };

  // Helper function to format time for console logs
  const formatConsoleTime = (date: Date): string => {
    return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  // Filter and sort helper functions
  const getFilteredAndSortedJobs = () => {
    let filtered = dashboardJobs.filter((job) => {
      const matchesSearch =
        job.name.toLowerCase().includes(jobSearch.toLowerCase()) ||
        job.type.toLowerCase().includes(jobSearch.toLowerCase()) ||
        job.status.toLowerCase().includes(jobSearch.toLowerCase());
      
      const matchesFilter =
        jobFilter === "all" ||
        job.type === jobFilter ||
        job.status === jobFilter;
      
      return matchesSearch && matchesFilter;
    });

    // Apply sorting
    const sorted = [...filtered].sort((a, b) => {
      switch (jobSort) {
        case "name":
          return a.name.localeCompare(b.name);
        case "type":
          return a.type.localeCompare(b.type);
        case "status":
          const statusOrder = { "Ready": 0, "Healthy": 1, "Running": 2, "Needs Attention": 3 };
          return (statusOrder[a.status as keyof typeof statusOrder] || 4) - (statusOrder[b.status as keyof typeof statusOrder] || 4);
        case "recently-updated":
          return b.updatedAt.localeCompare(a.updatedAt);
        default:
          return 0;
      }
    });

    return sorted;
  };

  const normalizedTemplateSearch = templateSearch.trim().toLowerCase();
  const filteredSavedTemplates = savedTemplates.filter((template) => {
    if (!normalizedTemplateSearch) return true;
    return (
      template.name.toLowerCase().includes(normalizedTemplateSearch) ||
      template.type.toLowerCase().includes(normalizedTemplateSearch)
    );
  });
  const filteredPreBuiltForms = preBuiltForms.filter((form) => {
    if (!normalizedTemplateSearch) return true;
    return (
      form.name.toLowerCase().includes(normalizedTemplateSearch) ||
      form.category.toLowerCase().includes(normalizedTemplateSearch) ||
      form.description.toLowerCase().includes(normalizedTemplateSearch)
    );
  });
  const openFormTab = (payload: FormWorkspacePayload) => {
    handleOpenTabInPane(
      {
        type: "template",
        id: payload.id,
        name: payload.name,
        payload,
      },
      "primary"
    );
  };

  const requiredActionPreview = requiredActionItems.slice(0, 3);
  const pendingCount = pendingRequiredActionsCount();

  // Get active tab and related data from primary pane
  const activeTab = workspace.primary.tabs.find((tab) => tab.id === workspace.primary.activeTabId);
  const activeJobName = activeTab?.type === "job" ? activeTab.jobName : null;
  const jobSpec = activeTab?.type === "job"
    ? ((activeTab.payload as WorkspaceJobPayload | undefined) ?? (activeJobName ? mockJobSpecs[activeJobName] : null))
    : null;

  // Get current promotion
  const promotionId = activeTab?.type === "promotion" ? activeTab.id : null;
  const allPromotions = [...mockReadyForPromotion, ...submittedPromotions, ...pendingPromotionsState, ...rejectedPromotionsState, ...mockRecentlyPromoted];
  const currentPromotion = promotionId
    ? allPromotions.find((p) => p.id === promotionId) ?? (activeTab?.payload as typeof allPromotions[number] | undefined) ?? null
    : null;

  // Workspace pane management functions
  const handleOpenTabInPane = (item: { 
    type: string; 
    name: string; 
    id: string;
    revisionJobType?: string;
    revisionRejectionReason?: string;
    payload?: Record<string, any>;
  }, paneKey: "primary" | "secondary") => {
    setWorkspace((prev) => {
      const updated = { ...prev };
      const targetPane = updated[paneKey];
      
      let newTab: WorkspaceTab;
      let existingTab: WorkspaceTab | undefined;
      let tabId: string;
      
      if (item.type === "job") {
        // Generate consistent tab ID for deduplication
        tabId = `job-${item.id.replace(/\s+/g, "-").toLowerCase()}`;
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "job",
            title: item.name,
            closable: true,
            jobName: item.name,
            payload: item.payload,
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      } else if (item.type === "required-action") {
        // Generate consistent tab ID for deduplication
        tabId = `action-${item.id}`;
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          const action = requiredActionItems.find((a) => a.id === item.id);
          newTab = {
            id: tabId,
            type: "required-action",
            title: item.name,
            closable: true,
            actionId: item.id,
            payload: action,
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      } else if (item.type === "template") {
        // Generate consistent tab ID for deduplication
        tabId = `template-${item.id.replace(/\s+/g, "-").toLowerCase()}`;
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "template",
            title: item.name,
            closable: true,
            templateId: item.id,
            templateName: item.name,
            payload: item.payload,
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      } else if (item.type === "revision") {
        // Generate consistent tab ID for deduplication
        tabId = item.id;
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "revision",
            title: `${item.name} (Revision)`,
            closable: true,
            revisionJobName: item.name,
            revisionJobType: item.revisionJobType || "",
            revisionRejectionReason: item.revisionRejectionReason || "",
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      } else if (item.type === "create-job") {
        // Generate consistent tab ID for deduplication
        tabId = item.id;
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "create-job",
            title: item.name,
            closable: true,
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      } else if (item.type === "active-jobs") {
        // Generate consistent tab ID for deduplication
        tabId = "active-jobs";
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "active-jobs",
            title: "My Active Jobs",
            closable: true,
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      } else if (item.type === "pending-approvals") {
        // Generate consistent tab ID for deduplication
        tabId = "pending-approvals";
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "pending-approvals",
            title: "Pending Approvals",
            closable: true,
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      } else if (item.type === "failed-runs") {
        // Generate consistent tab ID for deduplication
        tabId = "failed-runs";
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "failed-runs",
            title: "Failed Runs (24h)",
            closable: true,
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      } else if (item.type === "saved-jobs") {
        // Generate consistent tab ID for deduplication
        tabId = "saved-jobs";
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);
        
        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "saved-jobs",
            title: "Saved Jobs",
            closable: true,
          };
          targetPane.tabs = [...targetPane.tabs, newTab];
        }
        targetPane.activeTabId = tabId;
      }
      
      return updated;
    });
  };

  const handleCloseTabInPane = (tabId: string, paneKey: "primary" | "secondary") => {
    setWorkspace((prev) => {
      const updated = { ...prev };
      const targetPane = updated[paneKey];
      
      const newTabs = targetPane.tabs.filter((tab) => tab.id !== tabId);
      targetPane.tabs = newTabs;
      
      // Handle active tab closure
      if (targetPane.activeTabId === tabId) {
        if (newTabs.length > 0) {
          // Activate remaining tab
          const closedIndex = targetPane.tabs.findIndex((tab) => tab.id === tabId);
          const nextTab = newTabs[closedIndex - 1] || newTabs[closedIndex] || newTabs[0];
          targetPane.activeTabId = nextTab.id;
        } else {
          // No tabs left in secondary pane - collapse split view
          if (paneKey === "secondary") {
            updated.mode = "single";
            updated.secondary = { tabs: [], activeTabId: "" };
          } else {
            // Primary pane empty - add back dashboard
            updated.primary.tabs = [{ id: "dashboard", type: "dashboard", title: "Dashboard", closable: false }];
            updated.primary.activeTabId = "dashboard";
          }
        }
      }
      
      return updated;
    });
  };

  const handleActivateTabInPane = (tabId: string, paneKey: "primary" | "secondary") => {
    setWorkspace((prev) => {
      const updated = { ...prev };
      updated[paneKey].activeTabId = tabId;
      return updated;
    });
  };

  const handleEnableSplitMode = (position: "left" | "right" = "right") => {
    setWorkspace((prev) => ({
      ...prev,
      mode: "split",
      secondaryPosition: position,
    }));
  };

  const handleCollapseSplitMode = () => {
    setWorkspace((prev) => ({
      ...prev,
      mode: "single",
      secondary: { tabs: [], activeTabId: "" },
    }));
  };

  const handleSubmitRevision = (promotionId: string) => {
    // Find the promotion in rejected state
    const promotion = rejectedPromotionsState.find((p) => p.id === promotionId);
    if (!promotion) return;

    // Move from rejected to pending
    setRejectedPromotionsState((prev) => prev.filter((p) => p.id !== promotionId));
    setPendingPromotionsState((prev) => [
      ...prev,
      {
        ...promotion,
        status: "pending_promotion",
        lastModified: new Date().toISOString(),
      },
    ]);

    // Close the tab
    handleCloseTabInPane(promotionId, "primary");
  };

  // Drag and drop handlers
  const handleJobDragStart = (e: React.DragEvent<HTMLButtonElement>, jobName: string) => {
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("application/json", JSON.stringify({ type: "job", id: jobName, name: jobName }));
  };

  const handleWorkspaceDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    
    const rect = e.currentTarget.getBoundingClientRect();
    const relativeX = e.clientX - rect.left;
    
    setIsDraggingOverWorkspace(true);
    
    if (workspace.mode === "split") {
      // In split mode: detect which pane (left 50% vs right 50%)
      const midPoint = rect.width * 0.5;
      const paneTarget = relativeX < midPoint ? "left" : "right";
      setIsDraggingOverPane(paneTarget);
      setIsDraggingOverSplitZone(false);
    } else {
      // In single mode: detect split zone edges (left 30%, right 30%)
      const leftThreshold = rect.width * 0.3;
      const rightThreshold = rect.width * 0.7;
      
      let splitZone: "left" | "right" | false = false;
      if (relativeX < leftThreshold) {
        splitZone = "left";
      } else if (relativeX > rightThreshold) {
        splitZone = "right";
      }
      
      setIsDraggingOverSplitZone(splitZone);
      setIsDraggingOverPane(false);
    }
  };

  const handleWorkspaceDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    if (e.currentTarget === e.target) {
      setIsDraggingOverWorkspace(false);
      setIsDraggingOverSplitZone(false);
      setIsDraggingOverPane(false);
    }
  };

  const handleRequiredActionDragStart = (e: React.DragEvent<HTMLButtonElement>, actionId: string, subject: string) => {
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("application/json", JSON.stringify({ type: "required-action", id: actionId, name: subject }));
  };

  const handleTemplateDragStart = (
    e: React.DragEvent<HTMLElement>,
    templateId: string,
    templateName: string,
    metadata?: Record<string, unknown>
  ) => {
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData(
      "application/json",
      JSON.stringify({ type: "template", id: templateId, name: templateName, ...metadata })
    );
  };

  const handleWorkspaceDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingOverWorkspace(false);
    setIsDraggingOverSplitZone(false);
    setIsDraggingOverPane(false);

    try {
      const data = e.dataTransfer.getData("application/json");
      const payload = JSON.parse(data);

      if (workspace.mode === "split") {
        // In split mode: route to pane based on which side was dropped on
        const rect = e.currentTarget.getBoundingClientRect();
        const relativeX = e.clientX - rect.left;
        const midPoint = rect.width * 0.5;
        const dropSide = relativeX < midPoint ? "left" : "right";
        
        // Determine which pane is on which side
        const leftPaneKey = workspace.secondaryPosition === "left" ? "secondary" : "primary";
        const rightPaneKey = workspace.secondaryPosition === "left" ? "primary" : "secondary";
        
        const targetPane = dropSide === "left" ? leftPaneKey : rightPaneKey;
        handleOpenTabInPane(payload, targetPane as "primary" | "secondary");
      } else {
        // In single mode: detect split zone edges to create splits
        const rect = e.currentTarget.getBoundingClientRect();
        const leftThreshold = rect.width * 0.3;
        const rightThreshold = rect.width * 0.7;
        const relativeX = e.clientX - rect.left;
        
        let dropZone: "left" | "right" | "center" = "center";
        if (relativeX < leftThreshold) {
          dropZone = "left";
        } else if (relativeX > rightThreshold) {
          dropZone = "right";
        }

        if (dropZone === "left") {
          // Dragged to left split zone - enable split left and open in secondary
          handleEnableSplitMode("left");
          setTimeout(() => {
            handleOpenTabInPane(payload, "secondary");
          }, 0);
        } else if (dropZone === "right") {
          // Dragged to right split zone - enable split right and open in secondary
          handleEnableSplitMode("right");
          setTimeout(() => {
            handleOpenTabInPane(payload, "secondary");
          }, 0);
        } else {
          // Center drop - open in primary pane
          handleOpenTabInPane(payload, "primary");
        }
      }
    } catch (error) {
      // Silently ignore invalid drag data
    }
  };

  // Resize handlers
  const handleResizeMouseDown = (panelType: "jobs" | "workspace" | "chat") => (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(panelType);
  };

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const delta = e.clientX - (lastResizeX.current || e.clientX);
      lastResizeX.current = e.clientX;

      if (isResizing === "jobs") {
        setJobsPanelWidth((prev) => Math.max(220, prev + delta));
      } else if (isResizing === "chat") {
        setChatPanelWidth((prev) => Math.max(280, prev - delta));
      } else if (isResizing === "workspace") {
        setWorkspacePaneAWidth((prev) => Math.max(350, prev + delta));
      }
    };

    const handleMouseUp = () => {
      setIsResizing(null);
      lastResizeX.current = 0;
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  const requiredActionsCount = requiredActionItems.length;
  const badgeLabel = requiredActionsCount > 9 ? "9+" : String(requiredActionsCount);

  const panels = [
    { id: "jobs", label: "Jobs", icon: <Briefcase className="h-5 w-5" /> },
    { id: "runs", label: "Runs/Calendar", icon: <Calendar className="h-5 w-5" /> },
    { id: "templates", label: "Forms", icon: <FileText className="h-5 w-5" /> },
    { id: "promotions-edits", label: "Promotions & Edits", icon: <GitMerge className="h-5 w-5" /> },
    { id: "chat", label: "Chat", icon: <MessageSquare className="h-5 w-5" /> },
    { id: "required-actions", label: "Required Actions", icon: <AlertTriangle className="h-5 w-5" /> },
  ];

  const handlePanelToggle = (panelId: string) => {
    // Chat is handled separately as a right-side panel
    if (panelId === "chat") {
      setIsChatPanelOpen(!isChatPanelOpen);
      return;
    }
    setActivePanelId(activePanelId === panelId ? null : panelId);
  };

  const handleSendAIMessage = () => {
    if (!aiInput.trim()) return;

    const newUserMessage: AIMessage = {
      id: Date.now().toString(),
      role: "user",
      content: aiInput,
      timestamp: new Date(),
    };

    setAiMessages((prev) => [...prev, newUserMessage]);
    setAiInput("");

    // Simulate assistant response after 1 second
    setTimeout(() => {
      const assistantResponse: AIMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "I understand. I'm processing your request. In a production environment, this would use an AI model to suggest modifications to your job specification.",
        timestamp: new Date(),
      };
      setAiMessages((prev) => [...prev, assistantResponse]);
    }, 1000);
  };

  const normalizeExtractedJobFields = (fields: Record<string, any>) => {
    const config = typeof fields.config === "object" && fields.config !== null ? fields.config : {};
    const params = typeof fields.params === "object" && fields.params !== null ? fields.params : {};
    const parseSqlConnectionString = (value: any) => {
      if (typeof value !== "string") return {};
      const parts = value
        .split(";")
        .map((segment) => segment.trim())
        .filter(Boolean);
      const entries = Object.fromEntries(
        parts.map((segment) => {
          const separatorIndex = segment.indexOf("=");
          if (separatorIndex < 0) return ["", ""];
          const key = segment.slice(0, separatorIndex).trim().toLowerCase();
          const rawValue = segment.slice(separatorIndex + 1).trim();
          return [key, rawValue];
        }).filter(([key]) => key),
      );
      return {
        host: typeof entries.host === "string" ? entries.host : "",
        port: typeof entries.port === "string" ? entries.port : "",
        database: typeof entries.database === "string" ? entries.database : "",
        username: typeof entries.username === "string" ? entries.username : "",
      };
    };
    const normalizeEnv = (value: any) => {
      if (typeof value !== "string") return value;
      const normalized = value.trim().toLowerCase();
      return normalized === "production" ? "prod" : normalized;
    };
    const sqlConnectors = ["sql-dab", "sql-dab-analytics"];
    const defaultConnectionIdForConnector = (connector: string) => {
      if (connector === "sql-dab") return "postgres";
      if (connector === "sql-dab-analytics") return "analytics";
      return "";
    };
    const normalizeConnector = (connector: any) => {
      const normalized = typeof connector === "string" ? connector.trim().toLowerCase() : "";
      return sqlConnectors.includes(normalized) ? normalized : "sql-dab";
    };
    const normalizedType = String(fields.job_type ?? fields.type ?? "").trim().toLowerCase();
    const isSql =
      normalizedType === "sql" ||
      normalizedType === "query" ||
      Boolean(fields.query || config.query || params.query || fields.connection_id || config.connection_id);

    const normalized: Record<string, any> = {
      ...fields,
      ...(fields.name && !fields.job_name ? { job_name: fields.name } : {}),
      ...(fields.environment !== undefined ? { environment: normalizeEnv(fields.environment) } : {}),
      ...(fields.target_environment !== undefined ? { target_environment: normalizeEnv(fields.target_environment) } : {}),
      ...(fields.schedule === undefined && config.schedule !== undefined ? { schedule: config.schedule } : {}),
    };
    const normalizedSchedule = typeof normalized.schedule === "string" ? normalized.schedule.trim() : "";
    if (normalizedSchedule && normalized.run_type !== "scheduled") {
      normalized.run_type = "scheduled";
    }

    if (isSql) {
      const connector = normalizeConnector(fields.connector ?? config.connector);
      const explicitConnectionId = fields.connection_id ?? config.connection_id;
      const parsedConnection = parseSqlConnectionString(config.sql_connection_string);
      const database =
        fields.database ??
        config.database ??
        parsedConnection.database;
      normalized.job_type = "SQL";
      normalized.kind = fields.kind ?? "runtime";
      normalized.type = "sql";
      normalized.data_sensitivity = fields.data_sensitivity ?? "low";
      normalized.connector = connector;
      normalized.connection_id = explicitConnectionId ?? defaultConnectionIdForConnector(connector);
      normalized.database = database ?? "";
      normalized.target_environment = normalized.target_environment ?? normalized.environment ?? "dev";
      normalized.query = fields.query ?? params.query ?? config.query ?? "";
      normalized.output_destination = fields.output_destination ?? config.output_destination ?? "";
      normalized.result_limit = fields.result_limit ?? config.result_limit ?? "";
      normalized.config = {
        ...config,
        connection_id: normalized.connection_id,
        ...(normalized.database ? { database: normalized.database } : {}),
        ...(parsedConnection.host ? { host: config.host ?? parsedConnection.host } : {}),
        ...(parsedConnection.port ? { port: config.port ?? parsedConnection.port } : {}),
        ...(parsedConnection.username ? { username: config.username ?? parsedConnection.username } : {}),
        query: normalized.query,
        schedule: normalized.schedule,
        target_environment: normalized.target_environment,
        output_destination: normalized.output_destination,
        result_limit: normalized.result_limit,
      };
      normalized.params = {
        ...params,
        query: normalized.query,
        connection_id: normalized.connection_id,
        ...(normalized.database ? { database: normalized.database } : {}),
      };
    }

    return normalized;
  };

  const mergeDraftValues = (previous: Record<string, any>, next: Record<string, any>): Record<string, any> => {
    const merged: Record<string, any> = { ...previous };

    for (const [key, value] of Object.entries(next)) {
      if (value === undefined || value === null) {
        continue;
      }

      if (typeof value === "string") {
        if (value.trim() === "") {
          continue;
        }
        merged[key] = value;
        continue;
      }

      if (Array.isArray(value)) {
        if (value.length === 0) {
          continue;
        }
        merged[key] = value;
        continue;
      }

      if (typeof value === "object") {
        const previousObject = typeof previous[key] === "object" && previous[key] !== null ? previous[key] : {};
        merged[key] = mergeDraftValues(previousObject, value);
        continue;
      }

      merged[key] = value;
    }

    return merged;
  };

  const handleChatFieldsExtracted = (fields: Record<string, any>) => {
    const normalized = normalizeExtractedJobFields(fields);
    const isRepoConnectionDraft =
      normalized.connection_intent === "connect_repo" ||
      normalized.type === "repo_connection" ||
      normalized.connector === "github" ||
      Boolean(normalized.repo);

    if (isRepoConnectionDraft) {
      applyRepoConnectionFields(normalized);
      if (normalizeGithubRepoInput(String(normalized.repo ?? ""))) {
        void registerRepoConnection(
          {
            repo: String(normalized.repo ?? ""),
            ref: String(normalized.ref ?? ""),
            path: String(normalized.path ?? ""),
            displayName: String(normalized.name ?? ""),
            description: String(normalized.description ?? ""),
          },
          "chat",
        ).catch((error) => {
          setRepoConnectionError(error instanceof Error ? error.message : "Unable to connect the GitHub repo.");
        });
      } else {
        setRepoConnectionError("Chat started a GitHub repo connection, but I still need the repo slug.");
      }
      return;
    }

    setJobDraft((prev) => mergeDraftValues(prev, normalized));
  };

  const isCreateJobDraftComplete = (draft: Record<string, any>) => {
    const jobType = String(draft.job_type ?? draft.type ?? "").trim();
    const schedule = String(draft.schedule ?? draft.config?.schedule ?? "").trim();
    const hasUniversalRequiredFields = Boolean(
      String(draft.job_name ?? draft.name ?? "").trim() &&
        String(draft.owner ?? "").trim()
    );

    if (!hasUniversalRequiredFields) {
      return false;
    }

    if (draft.run_type === "scheduled" && !schedule) {
      return false;
    }

    if (jobType === "SQL") {
      return Boolean(
        String(draft.connector ?? "").trim() &&
          String(draft.connection_id ?? draft.config?.connection_id ?? "").trim() &&
          String(draft.query ?? draft.config?.query ?? draft.params?.query ?? "").trim() &&
          String(draft.target_environment ?? draft.config?.target_environment ?? draft.environment ?? "").trim()
      );
    }

    if (jobType === "Airflow") {
      return Boolean(String(draft.dag_name ?? draft.config?.dag_id ?? "").trim());
    }

    if (jobType === "Excel") {
      return Boolean(String(draft.output_file_name ?? "").trim());
    }

    if (jobType === "PowerPoint") {
      return Boolean(String(draft.slide_template ?? "").trim());
    }

    return Boolean(jobType);
  };

  const getAuthToken = () => {
    if (typeof window === "undefined") return "u_analyst";
    return window.localStorage.getItem("control-center-auth-token") ?? "u_analyst";
  };

  const applyRepoConnectionFields = (fields: Record<string, any>) => {
    const repo = normalizeGithubRepoInput(String(fields.repo ?? fields.config?.repo ?? ""));
    const ref = String(fields.ref ?? fields.config?.ref ?? "").trim();
    const path = String(fields.path ?? fields.config?.path ?? "").trim();
    const displayName = String(fields.name ?? "").trim();
    const description = String(fields.description ?? fields.config?.description ?? "").trim();

    setRepoConnectionError(null);
    setRepoConnectionSuccess(null);
    setRepoConnectionForm((prev) => ({
      repo: repo || prev.repo,
      ref: ref || prev.ref,
      path: path || prev.path,
      displayName: displayName || prev.displayName,
      description: description || prev.description,
    }));
  };

  const buildRepoConnectionPayload = (form: RepoConnectionFormState): ResourceCreatePayload => {
    const repo = normalizeGithubRepoInput(form.repo);
    if (!isValidGithubRepoSlug(repo)) {
      throw new Error("Enter a GitHub repo as owner/repo or a full GitHub URL.");
    }

    const bundleServerNames = preferredRepoBundle?.server_names?.length ? preferredRepoBundle.server_names : ["github"];
    const companionServers = preferredRepoBundle?.companion_servers ?? [];

    return {
      name: getRepoConnectionName(repo, form.displayName),
      kind: "runtime",
      type: "repo_connection",
      connector: "github",
      environment: "dev",
      data_sensitivity: "low",
      tags: ["github", "repo-connection", "mcp"],
      config: {
        repo,
        provider: "github",
        ...(form.ref.trim() ? { ref: form.ref.trim(), default_branch: form.ref.trim() } : {}),
        ...(form.path.trim() ? { path: form.path.trim() } : {}),
        ...(form.description.trim() ? { description: form.description.trim() } : {}),
        server_names: bundleServerNames,
        primary_server: "github",
        companion_servers: companionServers,
        connection_mode: "manual_or_chat",
      },
    };
  };

  const registerRepoConnection = async (form: RepoConnectionFormState, source: "manual" | "chat" = "manual") => {
    const payload = buildRepoConnectionPayload(form);
    const repo = String(payload.config.repo);
    const ref = String(payload.config.ref ?? "");
    const existing = connectedRepoResources.find((resource) => {
      const config = resource.config ?? {};
      return normalizeGithubRepoInput(String(config.repo ?? "")) === repo && String(config.ref ?? "") === ref;
    });

    setIsSavingRepoConnection(true);
    setRepoConnectionError(null);
    setRepoConnectionSuccess(null);

    try {
      const resource = existing ?? await createResource(payload, getAuthToken());
      await refreshJobRuns();
      setRepoConnectionForm((prev) => ({
        ...DEFAULT_REPO_CONNECTION_FORM,
        repo,
        ref,
        path: String(resource.config?.path ?? prev.path ?? ""),
        displayName: resource.name,
        description: String(resource.config?.description ?? prev.description ?? ""),
      }));
      setRepoConnectionSuccess(
        existing
          ? `Repo ${repo}${ref ? ` @ ${ref}` : ""} is already connected and ready for MCP workflows.`
          : `Connected ${repo}${ref ? ` @ ${ref}` : ""} for ${source === "chat" ? "chat and" : ""} future MCP workflows.`,
      );
      emitConsoleEvent("draft_updated", `Connected GitHub repo ${repo}`, {
        resource_id: resource.id,
        repo,
        server_names: resource.config?.server_names ?? ["github"],
        source,
      });
      return resource;
    } finally {
      setIsSavingRepoConnection(false);
    }
  };

  const handleManualRepoConnection = async () => {
    try {
      await registerRepoConnection(repoConnectionForm, "manual");
    } catch (error) {
      setRepoConnectionError(error instanceof Error ? error.message : "Unable to connect the GitHub repo.");
    }
  };

  const normalizeSqlConnectorForResource = (connector: unknown) => {
    const normalized = typeof connector === "string" ? connector.trim().toLowerCase() : "";
    if (normalized === "sql-dab" || normalized === "control center dev database" || normalized === "control-center dev database") {
      return "sql-dab";
    }
    if (normalized === "sql-dab-analytics" || normalized === "analytics reporting database") {
      return "sql-dab-analytics";
    }
    return "sql-dab";
  };

  const buildResourcePayloadFromDraft = (draft: Record<string, any>): ResourceCreatePayload => {
    const jobType = String(draft.job_type ?? "").trim();
    const schedule = String(draft.schedule ?? draft.config?.schedule ?? "").trim();
    const timezone = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "America/Chicago";
    const scheduleConfig = {
      ...(schedule ? { schedule } : {}),
      ...(schedule ? { timezone } : {}),
    };
    const basePayload = {
      name: String(draft.job_name ?? draft.name ?? "").trim(),
      kind: "runtime" as const,
      environment: String(draft.target_environment ?? draft.environment ?? "dev"),
      data_sensitivity: String(draft.data_sensitivity ?? "low"),
      tags: Array.isArray(draft.tags) ? draft.tags : [],
    };

    if (jobType === "SQL") {
      const connector = normalizeSqlConnectorForResource(draft.connector);
      const connectionId = String(draft.connection_id ?? draft.config?.connection_id ?? (connector === "sql-dab" ? "postgres" : "analytics")).trim();
      const query = String(draft.query ?? draft.config?.query ?? draft.params?.query ?? "").trim();
      return {
        ...basePayload,
        type: "sql",
        connector,
        config: {
          connection_id: connectionId,
          query,
          ...scheduleConfig,
        },
      };
    }

    if (jobType === "Excel") {
      return {
        ...basePayload,
        type: "excel",
        connector: String(draft.connector ?? draft.config?.connection_id ?? "filesystem"),
        config: {
          brief: String(draft.description ?? draft.input_data_sources ?? "Excel job").trim(),
          connection_id: String(draft.connection_id ?? draft.config?.connection_id ?? "filesystem"),
          ...scheduleConfig,
        },
      };
    }

    if (jobType === "PowerPoint") {
      return {
        ...basePayload,
        type: "powerpoint",
        connector: String(draft.connector ?? draft.config?.connection_id ?? "filesystem"),
        config: {
          brief: String(draft.description ?? draft.slide_template ?? "PowerPoint job").trim(),
          connection_id: String(draft.connection_id ?? draft.config?.connection_id ?? "filesystem"),
          ...scheduleConfig,
        },
      };
    }

    if (jobType === "Airflow") {
      return {
        ...basePayload,
        type: "airflow_dag",
        connector: String(draft.connector ?? "airflow"),
        config: {
          dag_id: String(draft.dag_name ?? draft.config?.dag_id ?? "").trim(),
          api_base_url: String(draft.api_base_url ?? draft.config?.api_base_url ?? "http://localhost:8080"),
          ...scheduleConfig,
        },
      };
    }

    throw new Error(`Job type '${jobType || "unknown"}' is not supported yet.`);
  };

  const registerJobResourceFromDraft = async (options: { askToRun?: boolean; autoRun?: boolean; closeTabId?: string } = {}) => {
    if (!isCreateJobDraftComplete(jobDraft)) {
      throw new Error("Fill the required SQL job fields before creating the job.");
    }

    const payload = buildResourcePayloadFromDraft(jobDraft);
    const existingResource = resources.find(
      (resource) => resource.name === payload.name && resource.type === payload.type && resource.connector === payload.connector
    );

    setIsRegisteringJob(true);
    try {
      const resource = existingResource ?? await createResource(payload, getAuthToken());
      setJobDraft((prev) => ({
        ...prev,
        resource_id: resource.id,
        name: resource.name,
        connector: resource.connector,
        connection_id: resource.config?.connection_id ?? prev.connection_id,
        query: resource.config?.query ?? prev.query,
        target_environment: prev.target_environment ?? prev.environment ?? "dev",
        config: {
          ...(prev.config ?? {}),
          ...(resource.config ?? {}),
        },
      }));
      await refreshJobRuns();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event(RESOURCE_SCHEDULES_UPDATED_EVENT));
      }
      emitConsoleEvent("draft_updated", `Registered ${resource.type} resource ${resource.name}`, {
        resource_id: resource.id,
        name: resource.name,
        connector: resource.connector,
      });

      if (options.autoRun) {
        const run = await createResourceRun(resource.id, buildRunPayloadFromResource(resource), getAuthToken());
        setActiveRunId(run.id);
        setRunLogs([]);
        setConsoleActiveTab("logs");
        setConsoleHeight(300);
        setChatAssistantNotices((prev) => [
          ...prev,
          {
            id: `resource-created-and-run-${resource.id}-${run.id}-${Date.now()}`,
            content: `Created SQL job \`${resource.name}\` and started run \`${run.id}\`.`,
          },
        ]);
      } else if (options.askToRun) {
        setChatAssistantNotices((prev) => [
          ...prev,
          {
            id: `resource-created-${resource.id}-${Date.now()}`,
            content: `Created ${resource.type.toUpperCase()} job \`${resource.name}\` and saved it as a Control Center resource. Do you want me to run it now?`,
          },
        ]);
      }

      if (options.closeTabId) {
        handleCloseTabInPane(options.closeTabId, "primary");
      }

      return resource;
    } finally {
      setIsRegisteringJob(false);
    }
  };

  const buildRunPayloadFromResource = (resource: ResourceRecord): RunCreatePayload => {
    const config = resource.config ?? {};
    return {
      action: "run",
      target_environment: resource.environment || "dev",
      params: {
        ...(config.query ? { query: config.query } : {}),
        ...(config.connection_id ? { connection_id: config.connection_id } : {}),
      },
      job_config: {
        intent: "run",
        schedule: typeof config.schedule === "string" ? config.schedule : null,
        metadata: {
          created_via: "user_home",
          job_type: resource.type,
        },
      },
      mcp_config: {
        server_names: resource.connector ? [resource.connector] : [],
        allow_auto_selection: false,
      },
    };
  };

  const runResourceFromUi = async (resourceId: string) => {
    const resource = resources.find((item) => item.id === resourceId);
    if (!resource) {
      emitConsoleEvent("missing_fields_identified", "Unable to run job because the resource was not found", { resource_id: resourceId });
      return;
    }

    setRunningJobIds((current) => Array.from(new Set([...current, resourceId])));
    emitConsoleEvent("draft_updated", `Started run for ${resource.name}`, { resource_id: resource.id });

    try {
      const run = await createResourceRun(resource.id, buildRunPayloadFromResource(resource), getAuthToken());
      setActiveRunId(run.id);
      setRunLogs([]);
      setConsoleActiveTab("logs");
      setConsoleHeight(300);
      await refreshJobRuns();
    } catch (err) {
      emitConsoleEvent("missing_fields_identified", `Unable to run ${resource.name}`, {
        resource_id: resource.id,
        error: err instanceof Error ? err.message : "Unknown error",
      });
    } finally {
      setRunningJobIds((current) => current.filter((id) => id !== resourceId));
    }
  };

  useEffect(() => {
    if (
      jobDraft.job_type !== "SQL" ||
      !jobDraft.creation_requested ||
      !isCreateJobDraftComplete(jobDraft) ||
      jobDraft.resource_id ||
      isRegisteringJob
    ) {
      return;
    }

    const payload = buildResourcePayloadFromDraft(jobDraft);
    const draftKey = JSON.stringify({
      name: payload.name,
      connector: payload.connector,
      connection_id: payload.config.connection_id,
      query: payload.config.query,
      target_environment: jobDraft.target_environment ?? jobDraft.environment ?? "dev",
    });

    if (autoRegisteredDraftKeyRef.current === draftKey) {
      return;
    }
    autoRegisteredDraftKeyRef.current = draftKey;
    void registerJobResourceFromDraft({
      askToRun: !Boolean(jobDraft.run_after_create || jobDraft.action === "run"),
      autoRun: Boolean(jobDraft.run_after_create || jobDraft.action === "run"),
    }).catch((err) => {
      emitConsoleEvent("missing_fields_identified", "Unable to register SQL resource", {
        error: err instanceof Error ? err.message : "Unknown error",
      });
      autoRegisteredDraftKeyRef.current = null;
    });
  }, [jobDraft, isRegisteringJob, resources]);

  // Render tab content - shared across all panes
  const renderTabContent = (tab: WorkspaceTab | undefined) => {
    if (!tab) return null;

    // Get job spec if needed
    const currentJobName = tab.type === "job" ? tab.jobName : null;
    const currentJobSpec = tab.type === "job"
      ? ((tab.payload as WorkspaceJobPayload | undefined) ?? (currentJobName ? mockJobSpecs[currentJobName] : null))
      : null;
    const currentJobResource = currentJobSpec
      ? resources.find((resource) => resource.id === currentJobSpec.job_id || resource.id === tab.id)
      : null;
    
    // Get template if needed
    const currentTemplate = tab.type === "template"
      ? ((tab.payload as FormWorkspacePayload | undefined) ?? mockTemplates.find((t) => t.id === tab.templateId))
      : null;

    const renderEmbeddedFormsHub = () => (
      <div className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Forms Hub</h1>
            <p className="mt-2 text-sm text-gray-600">
              Start a new form, continue a draft, or reopen a saved template without leaving the dashboard.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                onClick={() =>
                  openFormTab({
                    id: "blank-form-hub",
                    name: "Create New Form",
                    category: "Forms Hub",
                    description: "Choose a blank form type and start from scratch.",
                    useCase: "Create a new form from scratch",
                    route: "/forms/new",
                    origin: "blank-form",
                  })
                }
                className="rounded-lg bg-[#ed0923] px-4 py-2 text-sm font-semibold text-white hover:bg-[#d10820] transition"
              >
                Create New Form
              </button>
              <button
                onClick={() =>
                  openFormTab({
                    id: "draft-forms-hub",
                    name: "Continue Editing",
                    category: "Forms Hub",
                    description: "Review and continue all in-progress form drafts.",
                    useCase: "Resume saved form drafts",
                    route: "/forms/drafts",
                    origin: "draft-form",
                  })
                }
                className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-100 transition"
              >
                Continue Editing
              </button>
              <button
                onClick={() =>
                  openFormTab({
                    id: "prebuilt-forms-hub",
                    name: "Pre-Built Forms",
                    category: "Forms Hub",
                    description: "Open one of the standard Toyota job forms.",
                    useCase: "Start from a standard form",
                    route: "/forms/pre-built-forms",
                    origin: "prebuilt-form",
                  })
                }
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition"
              >
                Browse Form Types
              </button>
            </div>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Saved Templates</h2>
                <span className="text-xs font-medium text-gray-500">{savedTemplates.length} total</span>
              </div>
              <div className="space-y-3">
                {savedTemplates.slice(0, 4).map((template) => (
                  <button
                    key={template.id}
                    draggable
                    onDragStart={(e) =>
                      handleTemplateDragStart(e, template.id, template.name, {
                        category: template.type,
                        description: `${template.type} saved template ready to reuse.`,
                        origin: "saved-template",
                        route: template.route,
                      })
                    }
                    onClick={() =>
                      openFormTab({
                        id: template.id,
                        name: template.name,
                        category: template.type,
                        description: `${template.type} saved template ready to reuse.`,
                        useCase: "Resume and reuse a saved form template",
                        route: template.route,
                        origin: "saved-template",
                        progress: template.progress,
                        lastEdited: template.lastEdited,
                        draft: template.draft,
                      })
                    }
                    className="w-full rounded-lg border border-gray-200 bg-gray-50 p-4 text-left hover:border-[#ed0923] hover:bg-red-50 transition"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{template.name}</p>
                        <p className="mt-1 text-xs text-gray-500">{template.type} saved template</p>
                      </div>
                      <span className="rounded-full bg-gray-100 px-2 py-1 text-[10px] font-semibold text-gray-700">
                        {template.progress}
                      </span>
                    </div>
                    <div className="mt-3">
                      <span className="inline-flex rounded-md bg-[#ed0923] px-3 py-1.5 text-xs font-semibold text-white">
                        Create From Template
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Pre-Built Forms</h2>
                <span className="text-xs font-medium text-gray-500">{preBuiltForms.length} available</span>
              </div>
              <div className="space-y-3">
                {preBuiltForms.map((form) => (
                  <button
                    key={form.id}
                    draggable
                    onDragStart={(e) =>
                      handleTemplateDragStart(e, form.id, form.name, {
                        category: form.category,
                        description: form.description,
                        origin: "prebuilt-form",
                        route: form.route,
                      })
                    }
                    onClick={() =>
                      openFormTab({
                        id: form.id,
                        name: form.name,
                        category: form.category,
                        description: form.description,
                        useCase: form.useCase,
                        route: form.route,
                        origin: "prebuilt-form",
                      })
                    }
                    className="w-full rounded-lg border border-gray-200 bg-gray-50 p-4 text-left hover:border-[#ed0923] hover:bg-red-50 transition"
                  >
                    <p className="text-sm font-semibold text-gray-900">{form.name}</p>
                    <p className="mt-1 text-xs text-gray-500">{form.description}</p>
                    <div className="mt-3">
                      <span className="inline-flex rounded-md bg-[#ed0923] px-3 py-1.5 text-xs font-semibold text-white">
                        Create {form.category} Job
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );

    const renderEmbeddedPreBuiltForms = () => (
      <div className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Pre-Built Forms</h1>
            <p className="mt-2 text-sm text-gray-600">Open one of the standard Toyota forms directly in this workspace.</p>
          </div>
          <div className="space-y-4">
            {preBuiltForms.map((form) => (
              <div key={form.id} className="rounded-xl border border-red-200 bg-red-50 p-5">
                <div className="flex flex-wrap items-start justify-between gap-4 sm:flex-nowrap">
                  <div className="min-w-0 flex-1">
                    <h2 className="text-lg font-semibold text-gray-900">{form.name}</h2>
                    <p className="mt-1 text-sm text-gray-600">{form.description}</p>
                  </div>
                  <button
                    onClick={() =>
                      openFormTab({
                        id: form.id,
                        name: form.name,
                        category: form.category,
                        description: form.description,
                        useCase: form.useCase,
                        route: form.route,
                        origin: "prebuilt-form",
                      })
                    }
                    className="shrink-0 rounded-lg bg-[#ed0923] px-4 py-2 text-sm font-semibold text-white hover:bg-[#d10820] transition"
                  >
                    Create {form.category} Job
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );

    const renderEmbeddedDraftForms = () => (
      <div className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Continue Editing</h1>
            <p className="mt-2 text-sm text-gray-600">
              Reopen any saved in-progress form and continue working in the middle workspace.
            </p>
          </div>

          {draftForms.length > 0 ? (
            <div className="space-y-4">
              {draftForms.map((draft) => (
                <div
                  key={draft.id}
                  draggable
                  onDragStart={(e) =>
                    handleTemplateDragStart(e, draft.id, draft.jobName, {
                      category: draft.type,
                      description: "In-progress form draft saved from the user workflow.",
                      origin: "draft-form",
                      route: draft.route,
                      progress: draft.progress,
                    })
                  }
                  className="rounded-xl border border-amber-200 bg-amber-50 p-5 cursor-grab active:cursor-grabbing"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Draft Form</p>
                        <span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                          Drag into AI chat
                        </span>
                      </div>
                      <h2 className="mt-1 text-lg font-semibold text-gray-900">{draft.jobName}</h2>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-600">
                        <span className="rounded-full bg-white px-2 py-1 font-semibold text-gray-700">{draft.type}</span>
                        <span className="rounded-full bg-white px-2 py-1 font-semibold text-gray-700">{draft.progress} complete</span>
                        <span>Last edited {draft.lastEdited}</span>
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        openFormTab({
                          id: draft.id,
                          name: draft.jobName,
                          category: draft.type,
                          description: "In-progress form draft saved from the user workflow.",
                          useCase: "Continue editing your in-progress form",
                          route: draft.route,
                          origin: "draft-form",
                          progress: draft.progress,
                          lastEdited: draft.lastEdited,
                          draft: draft.draft,
                        })
                      }
                      className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-amber-700 border border-amber-300 hover:bg-amber-100 transition"
                    >
                      Continue Form
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-600">
              No saved drafts yet. Save a form as a draft and it will appear here.
            </div>
          )}
        </div>
      </div>
    );

    const renderEmbeddedBlankFormChooser = () => (
      <div className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Create New Form</h1>
            <p className="mt-2 text-sm text-gray-600">
              Build a completely new form from scratch for whatever job you need, then drag the draft into AI chat if you want help filling it out.
            </p>
          </div>

          <div className="grid gap-6">
            <div
              draggable
              onDragStart={(e) =>
                handleTemplateDragStart(
                  e,
                  "custom-form-draft",
                  customFormBuilder.formName || "Untitled Custom Form",
                  {
                    category: customFormBuilder.jobType || "Custom",
                    description: customFormBuilder.purpose || "Custom form draft created from scratch.",
                    origin: "blank-form",
                    route: "/forms/new",
                  }
                )
              }
              className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm cursor-grab active:cursor-grabbing"
            >
              <div className="grid gap-5 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-gray-900">Form Name</label>
                  <input
                    value={customFormBuilder.formName}
                    onChange={(e) => handleCustomFormFieldChange("formName", e.target.value)}
                    placeholder="Example: dealer launch readiness review"
                    className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-gray-900">What Is This Form's Purpose?</label>
                  <textarea
                    value={customFormBuilder.purpose}
                    onChange={(e) => handleCustomFormFieldChange("purpose", e.target.value)}
                    rows={4}
                    placeholder="Describe what this new form is meant to help users create or request."
                    className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-900">Job Type or Workflow</label>
                  <input
                    value={customFormBuilder.jobType}
                    onChange={(e) => handleCustomFormFieldChange("jobType", e.target.value)}
                    placeholder="Example: dealer onboarding workflow"
                    className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-900">Who Will Use It?</label>
                  <input
                    value={customFormBuilder.targetUsers}
                    onChange={(e) => handleCustomFormFieldChange("targetUsers", e.target.value)}
                    placeholder="Example: analysts, managers, finance ops"
                    className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-gray-900">Expected Output</label>
                  <input
                    value={customFormBuilder.outputDestination}
                    onChange={(e) => handleCustomFormFieldChange("outputDestination", e.target.value)}
                    placeholder="Example: dashboard, email, pdf package"
                    className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                  />
                </div>
                <div className="md:col-span-2 rounded-xl border border-gray-200 bg-gray-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-900">Schedule</label>
                      <p className="mt-1 text-xs text-gray-500">
                        Choose how often this job should run and when it should stop.
                      </p>
                    </div>
                    <span className="max-w-full rounded-full bg-white px-3 py-1 text-[11px] font-semibold leading-5 text-gray-700 break-words sm:max-w-[360px]">
                      {formatCustomScheduleSummary(customFormBuilder)}
                    </span>
                  </div>

                  <div className="mt-4 grid gap-5 lg:grid-cols-2">
                    <div>
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-600">Run cadence</label>
                      <div className="grid grid-cols-2 gap-2">
                        {[
                          { label: "On Demand", value: "on-demand" },
                          { label: "Daily", value: "daily" },
                          { label: "Weekly", value: "weekly" },
                          { label: "Monthly", value: "monthly" },
                        ].map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => handleCustomFormFieldChange("scheduleCadence", option.value)}
                            className={`rounded-lg border px-3 py-2 text-sm font-semibold transition ${
                              customFormBuilder.scheduleCadence === option.value
                                ? "border-[#ed0923] bg-[#fff5f5] text-[#ed0923]"
                                : "border-gray-200 bg-white text-gray-700 hover:bg-gray-100"
                            }`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-600">Start date</label>
                      <input
                        type="date"
                        value={customFormBuilder.startDate}
                        onChange={(e) => handleCustomFormFieldChange("startDate", e.target.value)}
                        className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      />
                    </div>

                    {customFormBuilder.scheduleCadence !== "on-demand" && (
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-600">Run time</label>
                        <input
                          type="time"
                          value={customFormBuilder.scheduleTime}
                          onChange={(e) => handleCustomFormFieldChange("scheduleTime", e.target.value)}
                          className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                        />
                      </div>
                    )}

                    {customFormBuilder.scheduleCadence === "monthly" && (
                      <div>
                        <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-600">Day of month</label>
                        <select
                          value={customFormBuilder.monthlyDay}
                          onChange={(e) => handleCustomFormFieldChange("monthlyDay", e.target.value)}
                          className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                        >
                          {Array.from({ length: 31 }, (_, index) => `${index + 1}`).map((day) => (
                            <option key={day} value={day}>
                              Day {day}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>

                  {customFormBuilder.scheduleCadence === "weekly" && (
                    <div className="mt-5">
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-600">Days of week</label>
                      <div className="flex flex-wrap gap-2">
                        {weekdayOptions.map((day) => (
                          <button
                            key={day.value}
                            type="button"
                            onClick={() => handleWeeklyDayToggle(day.value)}
                            className={`rounded-full border px-3 py-2 text-sm font-semibold transition ${
                              customFormBuilder.weeklyDays.includes(day.value)
                                ? "border-[#ed0923] bg-[#ed0923] text-white"
                                : "border-gray-200 bg-white text-gray-700 hover:bg-gray-100"
                            }`}
                          >
                            {day.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="mt-5">
                    <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-600">Stop running</label>
                    <div className="grid gap-3 md:grid-cols-3">
                      <button
                        type="button"
                        onClick={() => handleCustomFormFieldChange("stopCondition", "never")}
                        className={`rounded-lg border px-3 py-3 text-left text-sm transition ${
                          customFormBuilder.stopCondition === "never"
                            ? "border-[#ed0923] bg-[#fff5f5]"
                            : "border-gray-200 bg-white hover:bg-gray-100"
                        }`}
                      >
                        <p className="font-semibold text-gray-900">Never</p>
                        <p className="mt-1 text-xs text-gray-500">Keep the job active until someone stops it.</p>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCustomFormFieldChange("stopCondition", "on-date")}
                        className={`rounded-lg border px-3 py-3 text-left text-sm transition ${
                          customFormBuilder.stopCondition === "on-date"
                            ? "border-[#ed0923] bg-[#fff5f5]"
                            : "border-gray-200 bg-white hover:bg-gray-100"
                        }`}
                      >
                        <p className="font-semibold text-gray-900">On Date</p>
                        <p className="mt-1 text-xs text-gray-500">Choose the day this job should stop.</p>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleCustomFormFieldChange("stopCondition", "after-runs")}
                        className={`rounded-lg border px-3 py-3 text-left text-sm transition ${
                          customFormBuilder.stopCondition === "after-runs"
                            ? "border-[#ed0923] bg-[#fff5f5]"
                            : "border-gray-200 bg-white hover:bg-gray-100"
                        }`}
                      >
                        <p className="font-semibold text-gray-900">After N Runs</p>
                        <p className="mt-1 text-xs text-gray-500">Stop automatically after a fixed number of runs.</p>
                      </button>
                    </div>
                  </div>

                  {customFormBuilder.stopCondition === "on-date" && (
                    <div className="mt-5">
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-600">End date</label>
                      <input
                        type="date"
                        value={customFormBuilder.endDate}
                        onChange={(e) => handleCustomFormFieldChange("endDate", e.target.value)}
                        className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      />
                    </div>
                  )}

                  {customFormBuilder.stopCondition === "after-runs" && (
                    <div className="mt-5">
                      <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-600">Maximum runs</label>
                      <input
                        type="number"
                        min="1"
                        value={customFormBuilder.maxRuns}
                        onChange={(e) => handleCustomFormFieldChange("maxRuns", e.target.value)}
                        className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      />
                    </div>
                  )}
                </div>
                <div className="md:col-span-2">
                  <label className="mb-2 block text-sm font-medium text-gray-900">Required Fields</label>
                  <textarea
                    value={customFormBuilder.requiredFields}
                    onChange={(e) => handleCustomFormFieldChange("requiredFields", e.target.value)}
                    rows={3}
                    placeholder="List the inputs this new form should collect."
                    className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                  />
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3 border-t border-gray-200 pt-5">
                <button
                  onClick={handleCustomFormSaveDraft}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition"
                >
                  Save Draft
                </button>
                <button
                  onClick={handleCustomFormSaveTemplate}
                  className="rounded-lg border border-[#f6b5bc] bg-[#fff5f5] px-4 py-2 text-sm font-semibold text-[#ed0923] hover:bg-red-50 transition"
                >
                  Save as Template
                </button>
                <button
                  onClick={handleCustomFormCreateJob}
                  className="rounded-lg bg-[#ed0923] px-4 py-2 text-sm font-semibold text-white hover:bg-[#d10820] transition"
                >
                  Submit for Approval
                </button>
              </div>
              <div className="mt-4 rounded-lg border border-dashed border-[#ed0923] bg-red-50 px-4 py-3 text-sm text-gray-700">
                Drag this form into the AI chat if you want help refining the structure or filling it out.
              </div>
            </div>
          </div>
        </div>
      </div>
    );

    return (
      <>
        {tab.type === "create-job" ? (
          <div className="flex h-full items-center justify-center p-8 text-center">
            <div className="max-w-sm">
              <p className="text-lg font-semibold text-gray-700">Use the AI Chat Assistant</p>
              <p className="mt-2 text-sm text-gray-500">
                Job creation is handled through the chat panel. Describe the SQL job you want to create and the assistant will guide you.
              </p>
            </div>
          </div>
        ) : tab.type === "job" && currentJobSpec ? (
          /* Job Workspace View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              {/* Job Header */}
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <h1 className="text-3xl font-bold text-gray-900">{currentJobSpec.name}</h1>
                  <div className="flex items-center gap-3 mt-3">
                    <span className="rounded-lg bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">{currentJobSpec.type}</span>
                    <span className="text-sm text-gray-600">Schedule: {currentJobSpec.schedule}</span>
                    <span
                      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                        currentJobSpec.status === "Healthy"
                          ? "bg-green-100 text-green-700"
                          : currentJobSpec.status === "Running"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-red-100 text-red-700"
                      }`}
                    >
                      {currentJobSpec.status}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => {
                    if (currentJobResource) {
                      void runResourceFromUi(currentJobResource.id);
                    }
                  }}
                  disabled={!currentJobResource || runningJobIds.includes(currentJobResource.id)}
                  className="inline-flex items-center justify-center gap-2 rounded-md bg-[#ed0923] px-4 py-2 text-sm font-semibold text-white hover:bg-[#d10820] disabled:cursor-not-allowed disabled:bg-gray-300"
                  title={currentJobResource ? "Run this job manually" : "This job is not linked to a saved Control Center resource"}
                >
                  <PlayCircle className="h-4 w-4" />
                  {currentJobResource && runningJobIds.includes(currentJobResource.id) ? "Running..." : "Run Job"}
                </button>
              </div>

              {/* Tabs */}
              <div className="border-b border-gray-200">
                <div className="flex gap-8">
                  {(["overview", "runs", "settings"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setJobDetailTab(t)}
                      className={`px-0 py-3 text-sm font-medium capitalize transition ${
                        jobDetailTab === t
                          ? "text-gray-900 border-b-2 border-[#ed0923]"
                          : "text-gray-500 hover:text-gray-900"
                      }`}
                    >
                      {t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tab Content */}
              {jobDetailTab === "overview" && (
                <div className="rounded-xl border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Job Configuration</h2>
                  <div className="space-y-6">
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase">Type</p>
                        <p className="text-sm text-gray-900 mt-1">{currentJobSpec.type}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase">Schedule</p>
                        <p className="text-sm text-gray-900 mt-1">{currentJobSpec.schedule}</p>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-gray-500 uppercase">Status</p>
                        <p className="text-sm text-gray-900 mt-1">{currentJobSpec.status}</p>
                      </div>
                    </div>

                    <div className="border-t border-gray-200 pt-6">
                      <p className="text-sm font-semibold text-gray-900 mb-3">Inputs</p>
                      <ul className="space-y-2">
                        {currentJobSpec.inputs.map((input, idx) => (
                          <li key={idx} className="text-sm text-gray-700 flex items-center gap-2">
                            <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                            {input}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="border-t border-gray-200 pt-6">
                      <p className="text-sm font-semibold text-gray-900 mb-3">Outputs</p>
                      <ul className="space-y-2">
                        {currentJobSpec.outputs.map((output, idx) => (
                          <li key={idx} className="text-sm text-gray-700 flex items-center gap-2">
                            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                            {output}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="border-t border-gray-200 pt-6">
                      <p className="text-sm font-semibold text-gray-900 mb-3">Execution Steps</p>
                      <ul className="space-y-3">
                        {currentJobSpec.steps.map((step, idx) => (
                          <li key={step.id} className="flex gap-3 pb-3 border-b border-gray-100 last:border-0">
                            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-gray-100 text-xs font-semibold text-gray-700 flex-shrink-0">
                              {idx + 1}
                            </span>
                            <div>
                              <p className="text-sm font-medium text-gray-900">{step.name}</p>
                              <p className="text-xs text-gray-600">{step.action}</p>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {jobDetailTab === "runs" && (() => {
                const resourceId = tab.payload?.job_id as string | undefined;
                const jobRuns = resourceId
                  ? [...runs]
                      .filter((r) => r.resource_id === resourceId)
                      .sort((a, b) => b.created_at.localeCompare(a.created_at))
                  : [];

                const statusBadgeClass = (status: string) => {
                  const s = status.toLowerCase();
                  if (["running", "executing", "in_progress"].includes(s)) return "bg-blue-100 text-blue-700";
                  if (["failed", "stopped", "cancelled", "canceled", "blocked"].includes(s)) return "bg-red-100 text-red-700";
                  if (["queued", "pending", "scheduled"].includes(s)) return "bg-amber-100 text-amber-700";
                  return "bg-green-100 text-green-700";
                };

                return (
                  <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                    <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                      <h2 className="text-lg font-semibold text-gray-900">
                        Run History
                      </h2>
                      <span className="text-xs text-gray-500">{jobRuns.length} run{jobRuns.length !== 1 ? "s" : ""}</span>
                    </div>
                    {jobRuns.length === 0 ? (
                      <div className="px-6 py-12 text-center">
                        <p className="text-sm font-medium text-gray-500">No runs found for this job</p>
                        <p className="text-xs text-gray-400 mt-1">Runs will appear here once the job has been executed</p>
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="bg-gray-50 text-left">
                              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Run ID</th>
                              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Action</th>
                              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Environment</th>
                              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Trigger</th>
                              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Started</th>
                              <th className="px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Updated</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-100">
                            {jobRuns.map((run) => (
                              <tr key={run.id} className="hover:bg-gray-50 transition">
                                <td className="px-6 py-3">
                                  <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusBadgeClass(run.status)}`}>
                                    {run.status}
                                  </span>
                                </td>
                                <td className="px-6 py-3 font-mono text-xs text-gray-600">{run.id.slice(0, 8)}</td>
                                <td className="px-6 py-3 text-gray-700">{run.action}</td>
                                <td className="px-6 py-3 text-gray-600">{run.target_environment}</td>
                                <td className="px-6 py-3 text-gray-600 capitalize">{run.trigger_source ?? "manual"}</td>
                                <td className="px-6 py-3 text-gray-500 whitespace-nowrap">
                                  {new Date(run.created_at).toLocaleString()}
                                </td>
                                <td className="px-6 py-3 text-gray-500 whitespace-nowrap">
                                  {run.error
                                    ? <span className="text-red-600 font-mono text-xs" title={run.error}>{new Date(run.updated_at).toLocaleString()} — {run.error.slice(0, 60)}{run.error.length > 60 ? "…" : ""}</span>
                                    : new Date(run.updated_at).toLocaleString()
                                  }
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })()}

              {jobDetailTab === "settings" && (
                <div className="rounded-xl border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Settings</h2>
                  <div className="space-y-4">
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase">Resource ID</p>
                      <p className="text-sm font-mono text-gray-800 mt-1">{tab.payload?.job_id ?? "—"}</p>
                    </div>
                    <div className="border-t border-gray-100 pt-4">
                      <p className="text-xs font-semibold text-gray-500 uppercase">Description</p>
                      <p className="text-sm text-gray-700 mt-1">{currentJobSpec.description ?? "No description provided."}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : tab.type === "required-action" && tab.payload ? (
          /* Required Action Form View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">{tab.title}</h1>
                <p className="text-sm text-gray-600 mt-2 max-w-2xl">Resolve this action to allow the workflow to continue.</p>
              </div>

              {/* Action Form Card */}
              <div className="rounded-xl border border-gray-200 bg-white p-8 max-w-2xl">
                <div className="space-y-6">
                  {/* Action Status */}
                  <div>
                    <label className="text-sm font-semibold text-gray-900">Status</label>
                    <div className="mt-2 flex items-center gap-3">
                      <span
                        className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${requiredActionStateBadge(tab.payload.state)}`}
                      >
                        {tab.payload.state === "pending" ? "Pending" : tab.payload.state === "success" ? "Resolved" : "Failed"}
                      </span>
                      <span className="text-sm text-gray-600">{tab.payload.runAfter}</span>
                    </div>
                  </div>

                  {/* Workflow Context */}
                  <div className="border-t border-gray-200 pt-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-3">Workflow Context</h3>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-700">{tab.title}</p>
                    </div>
                  </div>

                  {/* Action Input Section */}
                  <div className="border-t border-gray-200 pt-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-3">Resolution</h3>
                    <div className="space-y-4">
                      {tab.title.includes("deployment") && (
                        <>
                          <div>
                            <label className="block text-sm font-medium text-gray-900 mb-2">Deployment Target</label>
                            <select className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#ed0923]">
                              <option>-- Select environment --</option>
                              <option>Development</option>
                              <option>Staging</option>
                              <option>Production</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-900 mb-2">Additional Parameters (JSON)</label>
                            <textarea className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#ed0923] font-mono" rows={4} placeholder='{"key": "value"}' />
                          </div>
                        </>
                      )}
                      {tab.title.includes("retry") && (
                        <>
                          <div>
                            <label className="block text-sm font-medium text-gray-900 mb-2">Retry Policy</label>
                            <select className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#ed0923]">
                              <option>-- Select policy --</option>
                              <option>Retry 1x after 1 hour</option>
                              <option>Retry 3x with exponential backoff</option>
                              <option>Skip on failure</option>
                              <option>Fail immediately</option>
                            </select>
                          </div>
                        </>
                      )}
                      {tab.title.includes("policy") && (
                        <>
                          <div>
                            <label className="block text-sm font-medium text-gray-900 mb-2">Policy Exception Reason</label>
                            <textarea className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#ed0923]" rows={3} placeholder="Explain why this exception is needed..." />
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="border-t border-gray-200 pt-6 flex gap-3">
                    <button className="flex-1 px-4 py-2 bg-[#ed0923] text-white rounded-lg font-medium hover:bg-[#d10820] transition">
                      Resolve Action
                    </button>
                    <button className="flex-1 px-4 py-2 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition">
                      Defer
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : tab.type === "template" && currentTemplate && currentTemplate.route === "/forms" ? (
          renderEmbeddedFormsHub()
        ) : tab.type === "template" && currentTemplate && currentTemplate.route === "/forms/drafts" ? (
          renderEmbeddedDraftForms()
        ) : tab.type === "template" && currentTemplate && currentTemplate.route === "/forms/pre-built-forms" ? (
          renderEmbeddedPreBuiltForms()
        ) : tab.type === "template" && currentTemplate && currentTemplate.route === "/forms/new" ? (
          renderEmbeddedBlankFormChooser()
        ) : tab.type === "template" && currentTemplate && currentTemplate.route === "/excel-report" ? (
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <ExcelReportForm
              embedded
              initialData={"draft" in currentTemplate ? currentTemplate.draft : undefined}
              aiPrompt={"origin" in currentTemplate && currentTemplate.origin === "draft-form" ? "Resume saved draft form" : "Resume saved form"}
              onCancel={() => openFormTab({ id: "forms-hub", name: "Forms Hub", category: "Forms Hub", description: "Browse drafts, saved templates, and pre-built job forms.", useCase: "Start or resume a form workflow", route: "/forms" })}
              onDraftSaved={() => openFormTab({ id: "forms-hub", name: "Forms Hub", category: "Forms Hub", description: "Browse drafts, saved templates, and pre-built job forms.", useCase: "Start or resume a form workflow", route: "/forms" })}
              onTemplateSaved={() => openFormTab({ id: "saved-templates-hub", name: "Saved Templates", category: "Forms Hub", description: "Browse and reuse saved form templates created by users.", useCase: "Reusable AI-assisted form templates", route: "/forms/saved-templates", origin: "saved-template" })}
              onJobCreated={(job) => handleSubmittedForApproval(job as unknown as StoredJob, "New Excel Job")}
            />
          </div>
        ) : tab.type === "template" && currentTemplate && currentTemplate.route === "/sql-job" ? (
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <SQLJobForm
              embedded
              initialData={"draft" in currentTemplate ? currentTemplate.draft : undefined}
              aiPrompt={"origin" in currentTemplate && currentTemplate.origin === "draft-form" ? "Resume saved draft form" : "Resume saved form"}
              onCancel={() => openFormTab({ id: "forms-hub", name: "Forms Hub", category: "Forms Hub", description: "Browse drafts, saved templates, and pre-built job forms.", useCase: "Start or resume a form workflow", route: "/forms" })}
              onDraftSaved={() => openFormTab({ id: "forms-hub", name: "Forms Hub", category: "Forms Hub", description: "Browse drafts, saved templates, and pre-built job forms.", useCase: "Start or resume a form workflow", route: "/forms" })}
              onTemplateSaved={() => openFormTab({ id: "saved-templates-hub", name: "Saved Templates", category: "Forms Hub", description: "Browse and reuse saved form templates created by users.", useCase: "Reusable AI-assisted form templates", route: "/forms/saved-templates", origin: "saved-template" })}
              onJobCreated={(job) => handleSubmittedForApproval(job as unknown as StoredJob, "New SQL Job")}
            />
          </div>
        ) : tab.type === "template" && currentTemplate && currentTemplate.route === "/powerpoint" ? (
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <PowerPointForm
              embedded
              initialData={"draft" in currentTemplate ? currentTemplate.draft : undefined}
              aiPrompt={"origin" in currentTemplate && currentTemplate.origin === "draft-form" ? "Resume saved draft form" : "Resume saved form"}
              onCancel={() => openFormTab({ id: "forms-hub", name: "Forms Hub", category: "Forms Hub", description: "Browse drafts, saved templates, and pre-built job forms.", useCase: "Start or resume a form workflow", route: "/forms" })}
              onDraftSaved={() => openFormTab({ id: "forms-hub", name: "Forms Hub", category: "Forms Hub", description: "Browse drafts, saved templates, and pre-built job forms.", useCase: "Start or resume a form workflow", route: "/forms" })}
              onTemplateSaved={() => openFormTab({ id: "saved-templates-hub", name: "Saved Templates", category: "Forms Hub", description: "Browse and reuse saved form templates created by users.", useCase: "Reusable AI-assisted form templates", route: "/forms/saved-templates", origin: "saved-template" })}
              onJobCreated={(job) => handleSubmittedForApproval(job as unknown as StoredJob, "New PowerPoint Job")}
            />
          </div>
        ) : tab.type === "template" && currentTemplate ? (
          /* Form Detail View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              {/* Form Header */}
              <div>
                <h1 className="text-3xl font-bold text-gray-900">{currentTemplate.name}</h1>
                <div className="flex items-center gap-3 mt-3">
                  <span className="rounded-lg bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">{currentTemplate.category}</span>
                  <span className="text-sm text-gray-600">{currentTemplate.useCase}</span>
                  {"origin" in currentTemplate && currentTemplate.origin && (
                    <span className="rounded-full bg-red-50 px-3 py-1 text-xs font-semibold text-[#ed0923]">
                      {currentTemplate.origin === "draft-form"
                        ? "Draft"
                        : currentTemplate.origin === "saved-template"
                          ? "Saved Template"
                          : currentTemplate.origin === "blank-form"
                            ? "Blank Form"
                          : "Pre-Built Form"}
                    </span>
                  )}
                </div>
              </div>

              {/* Form Description */}
              <div className="rounded-xl border border-gray-200 bg-white p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Form Details</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">Description</label>
                    <p className="text-sm text-gray-700">{currentTemplate.description}</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">Use Case</label>
                    <p className="text-sm text-gray-700">{currentTemplate.useCase}</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">Category</label>
                    <span className="inline-flex rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">
                      {currentTemplate.category}
                    </span>
                  </div>

                  {"progress" in currentTemplate && currentTemplate.progress && (
                    <div>
                      <label className="block text-sm font-medium text-gray-900 mb-2">Progress</label>
                      <span className="inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-700">
                        {currentTemplate.progress}
                      </span>
                    </div>
                  )}

                  {"lastEdited" in currentTemplate && currentTemplate.lastEdited && (
                    <div>
                      <label className="block text-sm font-medium text-gray-900 mb-2">Last Edited</label>
                      <p className="text-sm text-gray-700">{currentTemplate.lastEdited}</p>
                    </div>
                  )}

                  <div className="border-t border-gray-200 pt-4 mt-6">
                    <label className="block text-sm font-medium text-gray-900 mb-3">Preview</label>
                    <div className="bg-gray-50 rounded-lg p-6">
                      <div className="space-y-3">
                        <p className="text-sm text-gray-700">
                          📋 This form provides a structured approach to {currentTemplate.useCase.toLowerCase()}.
                        </p>
                        <p className="text-sm text-gray-700">
                          ✓ Ready to customize with your own data and parameters
                        </p>
                        <p className="text-sm text-gray-700">
                          🚀 Load this form to start creating your {currentTemplate.category.toLowerCase()}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <button
                  onClick={() =>
                    "route" in currentTemplate &&
                    openFormTab({
                      id: currentTemplate.id,
                      name: currentTemplate.name,
                      category: currentTemplate.category,
                      description: currentTemplate.description,
                      useCase: currentTemplate.useCase,
                      route: currentTemplate.route,
                      origin: currentTemplate.origin,
                      progress: "progress" in currentTemplate ? currentTemplate.progress : undefined,
                      lastEdited: "lastEdited" in currentTemplate ? currentTemplate.lastEdited : undefined,
                      draft: "draft" in currentTemplate ? currentTemplate.draft : undefined,
                    })
                  }
                  className="px-6 py-3 bg-[#ed0923] text-white rounded-lg font-medium hover:bg-[#d10820] transition"
                >
                  {"origin" in currentTemplate && currentTemplate.origin === "draft-form"
                    ? "Continue Form"
                    : "Start This Form"}
                </button>
                <button
                  onClick={() => setActivePanelId("templates")}
                  className="px-6 py-3 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition"
                >
                  Back to Forms
                </button>
              </div>
            </div>
          </div>
        ) : tab.type === "revision" ? (
          /* Revision Workspace View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              {/* Revision Header */}
              <div className="rounded-lg bg-red-50 border border-red-200 p-4">
                <h2 className="text-lg font-semibold text-red-900 mb-1">Revise Job: {tab.revisionJobName}</h2>
                <p className="text-sm text-red-700">Job Type: {tab.revisionJobType}</p>
              </div>

              {/* Rejection Reason Callout */}
              {tab.revisionRejectionReason && (
                <div className="rounded-lg bg-red-50 border border-red-200 p-4">
                  <h3 className="text-sm font-semibold text-red-900 mb-2">Rejection Reason</h3>
                  <p className="text-sm text-red-800">{tab.revisionRejectionReason}</p>
                </div>
              )}

              {/* Revision Configuration Card */}
              <div className="rounded-xl border border-gray-200 bg-white p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Revision Configuration</h2>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">Job Name</label>
                    <input
                      type="text"
                      defaultValue={tab.revisionJobName}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#ed0923]"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">Job Type</label>
                    <input
                      type="text"
                      defaultValue={tab.revisionJobType}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#ed0923]"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">Revision Notes</label>
                    <textarea
                      defaultValue=""
                      placeholder="Document the changes you've made to address the rejection reason..."
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#ed0923]"
                      rows={4}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-900 mb-2">Configuration</label>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600">Job configuration UI would be rendered here</p>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="border-t border-gray-200 pt-6 flex gap-3">
                    <button
                      onClick={() => handleSubmitRevision(tab.id.replace('revision-', ''))}
                      className="flex-1 px-4 py-2 bg-[#ed0923] text-white rounded-lg font-medium hover:bg-[#d10820] transition"
                    >
                      Submit Revision
                    </button>
                    <button
                      onClick={() => handleCloseTabInPane(tab.id, "primary")}
                      className="flex-1 px-4 py-2 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : tab.type === "promotion" && currentPromotion ? (
          /* Promotion Detail View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              {/* Revision View Header */}
              {currentPromotion.status === "rejected" && (
                <div className="rounded-lg bg-red-50 border border-red-200 p-4">
                  <h2 className="text-lg font-semibold text-red-900 mb-2">Revise: {currentPromotion.name}</h2>
                  <p className="text-sm text-red-700">Rejected on {formatPromotionDate(currentPromotion.lastModified || currentPromotion.createdAt)}</p>
                </div>
              )}

              {/* Promotion Header */}
              {currentPromotion.status !== "rejected" && (
                <div>
                  <h1 className="text-3xl font-bold text-gray-900">{currentPromotion.name}</h1>
                  <div className="flex items-center gap-3 mt-3">
                    <span className={`rounded-lg px-3 py-1 text-xs font-medium ${getPromotionTypeColor(currentPromotion.type)}`}>
                      {currentPromotion.type}
                    </span>
                    <span className="text-sm text-gray-600">Status: {currentPromotion.status}</span>
                  </div>
                </div>
              )}

              {/* Promotion Details Card */}
              <div className="rounded-xl border border-gray-200 bg-white p-8 max-w-3xl">
                <div className="space-y-6">
                  {/* Current Status */}
                  <div>
                    <label className="text-sm font-semibold text-gray-900">Promotion Status</label>
                    <div className="mt-2 flex items-center gap-3">
                      <span
                        className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                          currentPromotion.status === "approved"
                            ? "bg-blue-100 text-blue-700"
                            : currentPromotion.status === "pending_promotion"
                              ? "bg-yellow-100 text-yellow-700"
                              : currentPromotion.status === "rejected"
                                ? "bg-red-100 text-red-700"
                                : "bg-green-100 text-green-700"
                        }`}
                      >
                        {currentPromotion.status === "approved"
                          ? "Ready for Promotion"
                          : currentPromotion.status === "pending_promotion"
                            ? "Pending Approval"
                            : currentPromotion.status === "rejected"
                              ? "Needs Revision"
                              : "Promoted"}
                      </span>
                    </div>
                  </div>

                  {/* Environment Info */}
                  <div className="border-t border-gray-200 pt-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-3">Environment Path</h3>
                    <div className="flex items-center gap-2">
                      <div className="rounded-lg bg-blue-100 px-3 py-2 text-xs font-medium text-blue-700">
                        {currentPromotion.currentEnvironment}
                      </div>
                      <span className="text-gray-400">→</span>
                      <div className="rounded-lg bg-green-100 px-3 py-2 text-xs font-medium text-green-700">
                        {currentPromotion.targetEnvironment || "Production"}
                      </div>
                    </div>
                  </div>

                  {/* Description */}
                  {currentPromotion.description && (
                    <div className="border-t border-gray-200 pt-6">
                      <h3 className="text-sm font-semibold text-gray-900 mb-2">Description</h3>
                      <p className="text-sm text-gray-700">{currentPromotion.description}</p>
                    </div>
                  )}

                  {/* Rejection Reason if applicable */}
                  {currentPromotion.rejectionReason && (
                    <div className="border-t border-gray-200 border-red-200 bg-red-50 p-4 rounded-lg pt-6">
                      <h3 className="text-sm font-semibold text-red-900 mb-2">Rejection Reason</h3>
                      <p className="text-sm text-red-800">{currentPromotion.rejectionReason}</p>
                    </div>
                  )}

                  {/* Timeline */}
                  <div className="border-t border-gray-200 pt-6">
                    <h3 className="text-sm font-semibold text-gray-900 mb-3">Timeline</h3>
                    <div className="space-y-2 text-sm text-gray-600">
                      <div>Created: {formatPromotionDate(currentPromotion.createdAt)}</div>
                      {currentPromotion.lastModified && <div>Last Modified: {formatPromotionDate(currentPromotion.lastModified)}</div>}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="border-t border-gray-200 pt-6 flex gap-3">
                    {currentPromotion.status === "rejected" && (
                      <>
                        <button
                          onClick={() => handleSubmitRevision(currentPromotion.id)}
                          className="flex-1 px-4 py-2 bg-[#ed0923] text-white rounded-lg font-medium hover:bg-[#d10820] transition"
                        >
                          Submit Revision
                        </button>
                        <button
                          onClick={() => handleCloseTabInPane(tab.id, "primary")}
                          className="flex-1 px-4 py-2 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition"
                        >
                          Cancel
                        </button>
                      </>
                    )}
                    {(currentPromotion.status === "approved" || currentPromotion.status === "pending_promotion") && (
                      <button className="flex-1 px-4 py-2 bg-[#ed0923] text-white rounded-lg font-medium hover:bg-[#d10820] transition">
                        Request Promotion
                      </button>
                    )}
                    {currentPromotion.status !== "rejected" && (
                      <button className="flex-1 px-4 py-2 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition">
                        View Details
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : tab.type === "active-jobs" ? (
          /* Active Jobs View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">My Active Jobs</h1>
                <p className="mt-2 text-sm text-gray-600">Jobs currently running or healthy</p>
              </div>

              <div className="rounded-xl border border-gray-200 bg-white p-6">
                <div className="space-y-4">
                  {activeDashboardJobs.map((job) => (
                    <div key={job.id} className="flex items-start justify-between p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition">
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{job.name}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">{job.type}</span>
                          <span className="text-xs text-gray-500">Schedule: {job.schedule}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                            job.status === "Healthy"
                              ? "bg-green-100 text-green-700"
                              : "bg-blue-100 text-blue-700"
                          }`}
                        >
                          {job.status}
                        </span>
                        <button
                          onClick={() =>
                            handleOpenTabInPane(
                              { type: "job", name: job.name, id: job.id, payload: job.payload },
                              "primary"
                            )
                          }
                          className="px-3 py-1 text-xs text-[#ed0923] hover:bg-red-50 rounded transition"
                        >
                          View
                        </button>
                      </div>
                    </div>
                  ))}
                  {activeDashboardJobs.length === 0 && (
                    <div className="text-center py-8 text-gray-500">No active jobs at the moment</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : tab.type === "pending-approvals" ? (
          /* Pending Approvals View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Pending Approvals</h1>
                <p className="mt-2 text-sm text-gray-600">Jobs waiting for approval or promotion</p>
              </div>

              <div className="rounded-xl border border-gray-200 bg-white p-6">
                <div className="space-y-4">
                  {pendingApprovalPromotions.map((promotion) => (
                    <div key={promotion.id} className="flex items-start justify-between p-4 border border-amber-200 bg-amber-50 rounded-lg">
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{promotion.name}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded">{promotion.type}</span>
                          <span className="text-xs text-gray-500">
                            {promotion.currentEnvironment} → {promotion.targetEnvironment || "Production"}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-flex rounded-full px-3 py-1 text-xs font-semibold bg-yellow-100 text-yellow-700">
                          Pending
                        </span>
                        <button
                          onClick={() =>
                            handleOpenTabInPane(
                              { type: "promotion", name: promotion.name, id: promotion.id },
                              "primary"
                            )
                          }
                          className="px-3 py-1 text-xs text-[#ed0923] hover:bg-red-50 rounded transition"
                        >
                          Review
                        </button>
                      </div>
                    </div>
                  ))}
                  {pendingApprovalPromotions.length === 0 && (
                    <div className="text-center py-8 text-gray-500">No pending approvals</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : tab.type === "failed-runs" ? (
          /* Failed Runs View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Failed Runs (24h)</h1>
                <p className="mt-2 text-sm text-gray-600">Jobs that failed in the last 24 hours</p>
              </div>

              <div className="rounded-xl border border-gray-200 bg-white p-6">
                <div className="space-y-4">
                  {failedRunsLast24h.map((run) => (
                    <div key={run.id} className="flex items-start justify-between p-4 border border-red-200 bg-red-50 rounded-lg">
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{run.jobName}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded">{run.jobType}</span>
                          <span className="text-xs text-gray-500">
                            Failed {formatRunTime(run.completedTime ?? run.scheduledTime)}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-flex rounded-full px-3 py-1 text-xs font-semibold bg-red-100 text-red-700">
                          Failed
                        </span>
                        <button
                          onClick={() =>
                            handleOpenTabInPane(
                              { type: "job", name: run.jobName, id: run.jobName },
                              "primary"
                            )
                          }
                          className="px-3 py-1 text-xs text-[#ed0923] hover:bg-red-100 rounded transition"
                        >
                          Details
                        </button>
                      </div>
                    </div>
                  ))}
                  {failedRunsLast24h.length === 0 && (
                    <div className="text-center py-8 text-gray-500">No failed runs in the last 24 hours</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : tab.type === "saved-jobs" ? (
          /* Saved Jobs View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-6">
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Saved Jobs</h1>
                <p className="mt-2 text-sm text-gray-600">All your saved and drafted jobs</p>
              </div>

              <div className="rounded-xl border border-gray-200 bg-white p-6">
                <div className="space-y-4">
                  {dashboardJobs.map((job) => (
                    <div key={job.id} className="flex items-start justify-between p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition">
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{job.name}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded">{job.type}</span>
                          <span className="text-xs text-gray-500">Schedule: {job.schedule}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${getDashboardJobStatusClasses(job.status)}`}
                        >
                          {job.status}
                        </span>
                        <button
                          onClick={() =>
                            handleOpenTabInPane(
                              { type: "job", name: job.name, id: job.id, payload: job.payload },
                              "primary"
                            )
                          }
                          className="px-3 py-1 text-xs text-[#ed0923] hover:bg-red-50 rounded transition"
                        >
                          Open
                        </button>
                      </div>
                    </div>
                  ))}
                  {dashboardJobs.length === 0 && (
                    <div className="text-center py-8 text-gray-500">No saved jobs yet</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Dashboard View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            <div className="space-y-8">
              <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                  <h1 className="text-3xl font-bold text-gray-900">User Control Dashboard</h1>
                  <p className="mt-1 text-sm text-gray-600">
                    Track jobs, submit forms, and use AI assistance to draft workflow requests.
                  </p>
                </div>
              </div>

              {/* KPIs */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                {dashboardKpis.map((kpi) => {
                  return (
                    <button
                      key={kpi.tabType}
                      onClick={() => {
                        handleOpenTabInPane({ type: kpi.tabType, name: kpi.label, id: kpi.tabType }, "primary");
                      }}
                      className="rounded-xl border border-gray-200 bg-white p-6 hover:border-[#ed0923] hover:shadow-lg transition cursor-pointer"
                    >
                      <p className="text-sm font-medium text-gray-600">{kpi.label}</p>
                      <div className="mt-3">
                        <p className="text-3xl font-bold text-gray-900">{kpi.value}</p>
                        <p className={`mt-1 text-xs ${kpi.tone}`}>{kpi.hint}</p>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Today's Focus Summary */}
              <div className="rounded-xl border border-[#ed0923] bg-gradient-to-r from-[#ed0923]/5 to-[#ed0923]/0 p-6 mb-4">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">🎯 Today's Focus</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="flex items-center gap-3">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{urgentActionCount}</p>
                      <p className="text-xs text-gray-600">{urgentActionCount === 1 ? "Urgent action" : "Urgent actions"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <PlayCircle className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{runningDashboardJobs.length}</p>
                      <p className="text-xs text-gray-600">{runningDashboardJobs.length === 1 ? "Running job" : "Running jobs"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Sparkles className="h-5 w-5 text-amber-500" />
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{draftJobs.length}</p>
                      <p className="text-xs text-gray-600">{draftJobs.length === 1 ? "Draft pending" : "Drafts pending"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{promotionQueueCounts.ready}</p>
                      <p className="text-xs text-gray-600">{promotionQueueCounts.ready === 1 ? "Promotion ready" : "Promotions ready"}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid gap-6 lg:grid-cols-[1.3fr_0.9fr]">
                <div className="rounded-xl border border-gray-200 bg-white p-6">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900">Connect a GitHub Repo</h2>
                      <p className="mt-1 text-sm text-gray-600">
                        Save a repo once on the dashboard so chat and future multi-MCP workflows can reuse it.
                      </p>
                    </div>
                    <div className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600">
                      {githubMcpServer ? "GitHub MCP server available" : "GitHub MCP server not currently available"}
                    </div>
                  </div>

                  <div className="mt-5 grid gap-4 md:grid-cols-2">
                    <div className="md:col-span-2">
                      <label className="mb-2 block text-sm font-medium text-gray-900">GitHub repo</label>
                      <input
                        value={repoConnectionForm.repo}
                        onChange={(e) => {
                          setRepoConnectionError(null);
                          setRepoConnectionSuccess(null);
                          setRepoConnectionForm((prev) => ({ ...prev, repo: e.target.value }));
                        }}
                        placeholder="owner/repo or https://github.com/owner/repo"
                        className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-900">Default branch or ref</label>
                      <input
                        value={repoConnectionForm.ref}
                        onChange={(e) => setRepoConnectionForm((prev) => ({ ...prev, ref: e.target.value }))}
                        placeholder="main"
                        className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-900">Optional subpath</label>
                      <input
                        value={repoConnectionForm.path}
                        onChange={(e) => setRepoConnectionForm((prev) => ({ ...prev, path: e.target.value }))}
                        placeholder="models/marts"
                        className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-900">Display name</label>
                      <input
                        value={repoConnectionForm.displayName}
                        onChange={(e) => setRepoConnectionForm((prev) => ({ ...prev, displayName: e.target.value }))}
                        placeholder="dbt-core repo"
                        className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      />
                    </div>
                    <div>
                      <label className="mb-2 block text-sm font-medium text-gray-900">Description</label>
                      <input
                        value={repoConnectionForm.description}
                        onChange={(e) => setRepoConnectionForm((prev) => ({ ...prev, description: e.target.value }))}
                        placeholder="Used for dbt model work"
                        className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                      />
                    </div>
                  </div>

                  {repoConnectionError && (
                    <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                      {repoConnectionError}
                    </div>
                  )}
                  {repoConnectionSuccess && (
                    <div className="mt-4 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
                      {repoConnectionSuccess}
                    </div>
                  )}

                  <div className="mt-5 flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => void handleManualRepoConnection()}
                      disabled={isSavingRepoConnection || !githubMcpServer}
                      className="rounded-lg bg-[#ed0923] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#d10820] disabled:cursor-not-allowed disabled:bg-gray-300"
                    >
                      {isSavingRepoConnection ? "Connecting..." : "Connect Repo"}
                    </button>
                    <button
                      onClick={() => setIsChatPanelOpen(true)}
                      className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50"
                    >
                      Open Chat to Connect
                    </button>
                  </div>

                  <div className="mt-5 rounded-xl border border-dashed border-gray-200 bg-gray-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Chat Shortcut</p>
                    <p className="mt-2 text-sm text-gray-700">
                      Try: "Connect the GitHub repo <span className="font-mono">toyota-data/dbt-core</span> on branch <span className="font-mono">develop</span>."
                    </p>
                  </div>
                </div>

                <div className="rounded-xl border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900">Connected Repo Context</h2>
                  <p className="mt-1 text-sm text-gray-600">
                    Connected repos become reusable MCP-aware resources instead of one-off chat state.
                  </p>

                  <div className="mt-4 space-y-3">
                    {connectedRepoResources.length === 0 ? (
                      <div className="rounded-lg bg-gray-50 px-4 py-5 text-sm text-gray-500">
                        No GitHub repos connected yet.
                      </div>
                    ) : (
                      connectedRepoResources.map((resource) => {
                        const config = resource.config ?? {};
                        const serverNames = Array.isArray(config.server_names)
                          ? config.server_names.map((value) => String(value))
                          : [resource.connector];
                        return (
                          <div key={resource.id} className="rounded-lg border border-gray-200 p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-sm font-semibold text-gray-900">{String(config.repo ?? resource.name)}</p>
                                <p className="mt-1 text-xs text-gray-500">
                                  {String(config.ref ?? "default branch")}
                                  {config.path ? ` • ${String(config.path)}` : ""}
                                </p>
                              </div>
                              <span className="rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-semibold text-gray-700">
                                {resource.status}
                              </span>
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {serverNames.map((serverName) => (
                                <span key={serverName} className="rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-[#ed0923]">
                                  {serverName}
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>

                  {preferredRepoBundle && (
                    <div className="mt-5 rounded-xl bg-[#111827] p-4 text-white">
                      <p className="text-xs font-semibold uppercase tracking-wide text-red-200">Recommended MCP Bundle</p>
                      <p className="mt-2 text-sm font-semibold">{preferredRepoBundle.title}</p>
                      <p className="mt-1 text-sm text-gray-300">{preferredRepoBundle.summary}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {preferredRepoBundle.server_names.map((serverName) => (
                          <span key={serverName} className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-semibold text-white">
                            {serverName}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Dashboard Grid */}
              <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
                {/* Recent Jobs */}
                <div className="rounded-lg border border-gray-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Recent Jobs</h3>
                  <div className="space-y-2">
                    {dashboardJobs.slice(0, 3).map((job) => (
                      <button
                        key={job.id}
                        onClick={() =>
                          handleOpenTabInPane(
                            { type: "job", name: job.name, id: job.id, payload: job.payload },
                            "primary"
                          )
                        }
                        className="w-full p-2 bg-gray-50 rounded text-left hover:bg-gray-100 cursor-pointer transition text-xs"
                      >
                        <p className="font-medium text-gray-900 truncate">{job.name}</p>
                        <span className={`inline-block mt-1 rounded px-2 py-0.5 text-[9px] font-semibold ${getDashboardJobStatusClasses(job.status)}`}>
                          {job.status}
                        </span>
                      </button>
                    ))}
                    {dashboardJobs.length === 0 && (
                      <p className="p-2 text-xs text-gray-500">No saved jobs found</p>
                    )}
                  </div>
                </div>

                {/* Drafts Snapshot */}
                <div className="rounded-lg border border-gray-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">✍️ Drafts ({draftJobs.length})</h3>
                  <div className="space-y-2">
                    {draftJobs.slice(0, 2).map((draft) => (
                      <div key={draft.id} className="p-2 bg-amber-50 rounded text-left hover:bg-amber-100 cursor-pointer transition text-xs">
                        <p className="font-medium text-gray-900 truncate">{draft.name}</p>
                        <p className="text-gray-500 text-[9px]">{draft.lastEdited}</p>
                      </div>
                    ))}
                    {draftJobs.length > 2 && <p className="text-xs text-[#ed0923] font-medium mt-2">+{draftJobs.length - 2} more</p>}
                  </div>
                </div>

                {/* Promotions Queue */}
                <div className="rounded-lg border border-gray-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">📤 Promotions</h3>
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center justify-between p-2 bg-blue-50 rounded">
                      <span className="text-gray-700">Ready</span>
                      <span className="font-bold text-blue-700">{promotionQueueCounts.ready}</span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-yellow-50 rounded">
                      <span className="text-gray-700">Pending</span>
                      <span className="font-bold text-yellow-700">{promotionQueueCounts.pending}</span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-red-50 rounded">
                      <span className="text-gray-700">Needs Revision</span>
                      <span className="font-bold text-red-700">{promotionQueueCounts.needsRevision}</span>
                    </div>
                  </div>
                </div>

                {/* Upcoming Runs */}
                <div className="rounded-lg border border-gray-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">📅 Next Runs</h3>
                  <div className="space-y-2">
                    {dashboardRuns.upcomingRuns.slice(0, 2).map((run) => (
                      <div key={run.id} className="p-2 bg-blue-50 rounded text-left text-xs">
                        <p className="font-medium text-gray-900 truncate">{run.jobName}</p>
                        <p className="text-gray-500 text-[9px]">{formatScheduledTime(run.scheduledTime)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Activity Timeline & Required Actions */}
              <div className="grid grid-cols-2 gap-6">
                {/* Activity Feed */}
                <div className="rounded-lg border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h2>
                  <div className="space-y-3">
                    {activityTimeline.map((item, idx) => (
                      <div key={idx} className="flex gap-3 pb-3 border-b border-gray-100 last:border-0 last:pb-0">
                        <div className="text-lg">{item.icon}</div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900">{item.action}</p>
                          <p className="text-xs text-gray-500">{item.timestamp}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Required Actions Queue */}
                <div className="rounded-lg border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Required Actions</h2>
                  <div className="space-y-3">
                    {requiredActionPreview.map((item) => (
                      <div key={item.id} className="flex items-start gap-3 pb-3 border-b border-gray-100 last:border-0 last:pb-0">
                        <div className="mt-0.5">
                          {item.state === "pending" && <AlertTriangle className="h-4 w-4 text-red-500" />}
                          {item.state === "success" && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 line-clamp-2">{item.subject}</p>
                          <p className="text-xs text-gray-500 mt-0.5">{item.runAfter}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </>
    );
  };

  const renderPanelContent = () => {
    switch (activePanelId) {
      case "jobs":
        const filteredAndSortedJobs = getFilteredAndSortedJobs();
        const readyJobs = filteredAndSortedJobs.filter((job) => job.status === "Ready");
        const currentJobs = filteredAndSortedJobs.filter((job) => job.status !== "Ready");
        const jobTypeFilters = Array.from(new Set(dashboardJobs.map((job) => job.type))).sort();
        return (
          <div className="p-4 space-y-3 flex flex-col h-full">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Runs Table</p>
                <p className="text-xs text-gray-500">{runs.length} database runs loaded</p>
              </div>
              <button
                onClick={() => void refreshJobRuns()}
                className="rounded-md border border-gray-300 px-2.5 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Refresh
              </button>
            </div>
            {jobRunsError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {jobRunsError}
              </div>
            )}

            {/* Search Input */}
            <div>
              <input
                type="text"
                placeholder="Search jobs..."
                value={jobSearch}
                onChange={(e) => setJobSearch(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
              />
            </div>

            {/* Sort Control */}
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-600">Sort:</label>
              <select
                value={jobSort}
                onChange={(e) => setJobSort(e.target.value as any)}
                className="flex-1 px-2 py-1.5 border border-gray-300 rounded text-xs text-gray-700 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
              >
                <option value="name">Name (A–Z)</option>
                <option value="type">Type</option>
                <option value="status">Status</option>
                <option value="recently-updated">Recently Updated</option>
              </select>
            </div>

            {/* Filter Controls */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-600">Filter:</label>
              <div className="flex flex-wrap gap-1.5">
                {["all", ...jobTypeFilters].map((filterOption) => (
                  <button
                    key={filterOption}
                    onClick={() => setJobFilter(filterOption as any)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                      jobFilter === filterOption
                        ? "bg-[#ed0923] text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    {filterOption === "all" ? "All" : filterOption}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {["Ready", "Healthy", "Running", "Needs Attention"].map((filterOption) => (
                  <button
                    key={filterOption}
                    onClick={() => setJobFilter(filterOption as any)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                      jobFilter === filterOption
                        ? "bg-[#ed0923] text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    {filterOption}
                  </button>
                ))}
              </div>
            </div>

            {/* Ready Jobs Section */}
            <div className="border-t border-gray-200 pt-3 mt-2">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wide">
                  Ready ({readyJobs.length})
                </h3>
              </div>
              <div className="space-y-1.5">
                {readyJobs.map((job) => (
                  <div
                    key={job.id}
                    className={`w-full p-3 rounded-lg text-left border ${
                      activeJobName === job.name
                        ? "bg-[#ed0923]/10 border-[#ed0923]"
                        : "bg-amber-50 border-amber-100"
                    }`}
                  >
                    <button
                      draggable
                      onDragStart={(e) => handleJobDragStart(e, job.name)}
                      onClick={() => {
                        setSelectedResourceId(job.id);
                        handleOpenTabInPane(
                          { type: "job", name: job.name, id: job.id, payload: job.payload },
                          "primary"
                        );
                      }}
                      className="w-full cursor-move text-left"
                    >
                      <p className="text-sm font-medium text-gray-900">{job.name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-500">{job.type}</span>
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${getDashboardJobStatusClasses(job.status)}`}>
                          {job.status}
                        </span>
                      </div>
                    </button>
                    <button
                      onClick={() => void runResourceFromUi(job.id)}
                      className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-md bg-[#ed0923] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#d10820] disabled:cursor-not-allowed disabled:bg-gray-300"
                      disabled={runningJobIds.includes(job.id)}
                    >
                      <PlayCircle className="h-3.5 w-3.5" />
                      {runningJobIds.includes(job.id) ? "Running..." : "Run manually"}
                    </button>
                  </div>
                ))}
                {readyJobs.length === 0 && (
                  <p className="rounded-lg bg-gray-50 px-3 py-4 text-center text-sm text-gray-500">No ready jobs</p>
                )}
              </div>
            </div>

            {/* Current Jobs Section - Always visible and prioritized */}
            <div className="border-t border-gray-200 pt-3 mt-2">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wide">
                  My Current Jobs ({currentJobs.length})
                </h3>
              </div>
              <div className="flex-1 overflow-y-auto space-y-1.5">
                {jobRunsLoading && dashboardJobs.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-sm text-gray-500">Loading runs from Control Center...</p>
                  </div>
                ) : currentJobs.length > 0 ? (
                  currentJobs.map((job) => (
                    <div
                      key={job.id}
                      draggable
                      onDragStart={(e) => handleJobDragStart(e, job.name)}
                      className={`w-full p-3 rounded-lg transition text-left ${
                        activeJobName === job.name
                          ? "bg-[#ed0923]/10 border border-[#ed0923]"
                          : "bg-gray-50 hover:bg-gray-100 border border-transparent"
                      }`}
                    >
                      <button
                        onClick={() => {
                          setSelectedResourceId(job.id);
                          handleOpenTabInPane(
                            { type: "job", name: job.name, id: job.id, payload: job.payload },
                            "primary"
                          );
                        }}
                        className="w-full cursor-move text-left"
                      >
                        <p className="text-sm font-medium text-gray-900">{job.name}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-gray-500">{job.type}</span>
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${getDashboardJobStatusClasses(job.status)}`}
                          >
                            {job.status}
                          </span>
                        </div>
                      </button>
                      <div className="mt-3 flex items-center gap-2">
                        <button
                          onClick={() => void runResourceFromUi(job.id)}
                          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-[#ed0923] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#d10820] disabled:cursor-not-allowed disabled:bg-gray-300"
                          disabled={runningJobIds.includes(job.id)}
                        >
                          <PlayCircle className="h-3.5 w-3.5" />
                          {runningJobIds.includes(job.id) ? "Running..." : "Run manually"}
                        </button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8">
                    <p className="text-sm text-gray-500">
                      {dashboardJobs.length === 0 ? "No jobs found in the runs table" : "No jobs match your search"}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      case "runs":
        return (
          <div className="p-4 space-y-3 flex flex-col h-full overflow-y-auto">
            {/* Filter header */}
            {selectedResourceName ? (
              <div className="flex items-center justify-between gap-2 rounded-lg bg-[#ed0923]/5 border border-[#ed0923]/20 px-3 py-2">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-[#ed0923]">Filtered by job</p>
                  <p className="text-xs font-medium text-gray-800 truncate">{selectedResourceName}</p>
                </div>
                <button
                  onClick={() => setSelectedResourceId(null)}
                  className="shrink-0 text-[10px] font-medium text-gray-500 hover:text-gray-800 underline"
                >
                  Show all
                </button>
              </div>
            ) : (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">All Runs</p>
                <p className="text-[10px] text-gray-400">Click a job to filter</p>
              </div>
            )}

            {/* Upcoming Runs */}
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Upcoming Runs</h3>
              <div className="space-y-1.5">
                {filteredDashboardRuns.upcomingRuns.length > 0 ? (
                  filteredDashboardRuns.upcomingRuns.map((run) => (
                    <div key={run.id} className="p-2 rounded-lg bg-gray-50 border border-gray-200 text-left hover:bg-gray-100 transition cursor-pointer">
                      <p className="text-sm font-medium text-gray-900 truncate">{run.jobName}</p>
                      <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                        <span className={`inline-flex text-[10px] font-semibold rounded px-1.5 py-0.5 ${getJobTypeColor(run.jobType)}`}>
                          {run.jobType}
                        </span>
                        <span className={`inline-flex text-[10px] font-semibold rounded px-1.5 py-0.5 ${getRunStatusColor(run.status)}`}>
                          {run.status === "running" ? "Running" : "Scheduled"}
                        </span>
                        <span className="text-xs text-gray-500">{formatScheduledTime(run.scheduledTime)}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-400 py-2 text-center">No upcoming runs</p>
                )}
              </div>
            </div>

            {/* Divider */}
            <div className="border-t border-gray-200" />

            {/* Recent Runs */}
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Recent Runs</h3>
              <div className="space-y-1.5">
                {filteredDashboardRuns.recentRuns.length > 0 ? (
                  filteredDashboardRuns.recentRuns.map((run) => (
                    <div
                      key={run.id}
                      className="w-full p-2 rounded-lg bg-gray-50 border border-gray-200 text-left"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">{run.jobName}</p>
                          <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                            <span className={`inline-flex text-[10px] font-semibold rounded px-1.5 py-0.5 ${getJobTypeColor(run.jobType)}`}>
                              {run.jobType}
                            </span>
                            <span className={`inline-flex text-[10px] font-semibold rounded px-1.5 py-0.5 ${getRunStatusColor(run.status)}`}>
                              {run.status === "completed" ? "✓ Completed" : run.status === "failed" ? "✗ Failed" : "..."}
                            </span>
                          </div>
                        </div>
                        <span className="text-xs text-gray-500 whitespace-nowrap">{formatRunTime(run.completedTime || run.scheduledTime)}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-400 py-2 text-center">No recent runs</p>
                )}
              </div>
            </div>

            {/* Divider */}
            <div className="border-t border-gray-200 mt-3" />

            {/* Open Calendar Button */}
            <div className="pt-2">
              <CalendarButtonInner />
            </div>
          </div>
        );
      case "required-actions":
        // Organize actions by urgency
        const urgentActions = requiredActionItems.filter((a) => a.urgency === "urgent");
        const highPriorityActions = requiredActionItems.filter((a) => a.urgency === "high");
        const otherActions = requiredActionItems.filter((a) => a.urgency === "other");

        const renderActionSection = (
          title: string,
          actions: typeof requiredActionItems,
          isEmpty: boolean
        ) => {
          if (actions.length === 0) return null;

          return (
            <div key={title} className="space-y-2">
              <h4 className="text-xs font-bold text-gray-600 uppercase tracking-wide px-0.5">{title}</h4>
              <div className="space-y-1.5">
                {actions.map((action) => {
                  const isExpanded = expandedActionId === action.id;
                  return (
                    <div
                      key={action.id}
                      className="border border-gray-200 rounded-lg overflow-hidden bg-white"
                    >
                      {/* Collapsed/Header */}
                      <button
                        onClick={() => setExpandedActionId(isExpanded ? null : action.id)}
                        className="w-full p-3 text-left hover:bg-gray-50 transition flex items-start gap-3 group"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 group-hover:text-[#ed0923] transition">
                            {action.subject}
                          </p>
                          <div className="flex items-center gap-2 mt-1.5 flex-wrap gap-y-1">
                            <span className="text-xs text-gray-500">{action.runAfter}</span>
                            <span
                              className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${requiredActionStateBadge(
                                action.state
                              )}`}
                            >
                              {action.state === "pending"
                                ? "Pending"
                                : action.state === "success"
                                ? "Resolved"
                                : "Failed"}
                            </span>
                          </div>
                        </div>
                        <div
                          className={`text-gray-400 transition-transform flex-shrink-0 mt-0.5 ${
                            isExpanded ? "rotate-180" : ""
                          }`}
                        >
                          <ChevronDown className="h-4 w-4" />
                        </div>
                      </button>

                      {/* Expanded Content */}
                      {isExpanded && (
                        <div className="border-t border-gray-200 bg-gray-50 p-3 space-y-3">
                          {/* Description */}
                          <div>
                            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
                              Description
                            </p>
                            <p className="text-sm text-gray-700">{action.description}</p>
                          </div>

                          {/* Details */}
                          {action.details.length > 0 && (
                            <div>
                              <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
                                Details
                              </p>
                              <ul className="text-sm text-gray-700 space-y-1">
                                {action.details.map((detail, idx) => (
                                  <li key={idx} className="flex items-center gap-2">
                                    <span className="text-gray-400">•</span>
                                    <span>{detail}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* Suggested Resolution */}
                          <div>
                            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
                              Suggested Resolution
                            </p>
                            <p className="text-sm text-gray-700">{action.suggestedResolution}</p>
                          </div>

                          {/* Job Reference */}
                          <div>
                            <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">
                              Related Job
                            </p>
                            <p className="text-sm text-gray-700 font-mono bg-white p-2 rounded border border-gray-200">
                              {action.jobName}
                            </p>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex gap-2 pt-2">
                            <button
                              onClick={() =>
                                handleOpenTabInPane(
                                  { type: "required-action", id: action.id, name: action.subject },
                                  "primary"
                                )
                              }
                              className="flex-1 px-3 py-2 rounded text-sm font-medium bg-[#ed0923] text-white hover:bg-[#d10820] transition"
                            >
                              Open
                            </button>
                            <button className="flex-1 px-3 py-2 rounded text-sm font-medium bg-gray-200 text-gray-900 hover:bg-gray-300 transition">
                              Resolve
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        };

        return (
          <div className="p-4 space-y-4 flex flex-col h-full overflow-y-auto">
            <div className="space-y-3">
              {urgentActions.length > 0 && renderActionSection("Urgent Actions", urgentActions, false)}
              {highPriorityActions.length > 0 && renderActionSection("High Priority", highPriorityActions, false)}
              {otherActions.length > 0 && renderActionSection("Other Actions", otherActions, false)}
              {requiredActionItems.length === 0 && (
                <div className="text-center py-8">
                  <p className="text-sm text-gray-500">No required actions at this time.</p>
                </div>
              )}
            </div>
          </div>
        );
      case "templates": {
        return (
          <div className="p-4 space-y-4 flex flex-col h-full overflow-y-auto">
            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <h3 className="text-sm font-semibold text-gray-900">Create and reuse forms</h3>
              <p className="mt-1 text-xs text-gray-600">
                Start a new form, continue a saved draft, or open a reusable template.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() =>
                    openFormTab({
                      id: "forms-hub",
                      name: "Forms Hub",
                      category: "Forms Hub",
                      description: "Browse drafts, saved templates, and pre-built job forms.",
                      useCase: "Start or resume a form workflow",
                      route: "/forms",
                    })
                  }
                  className="rounded-lg bg-[#ed0923] px-3 py-2 text-xs font-semibold text-white hover:bg-[#d10820] transition"
                >
                  Open Forms Hub
                </button>
              </div>
            </div>

            <div>
              <input
                type="text"
                placeholder="Search forms, templates, or types..."
                value={templateSearch}
                onChange={(e) => setTemplateSearch(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
              />
            </div>

            <div className="space-y-4">
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-gray-600">Saved Templates</h3>
                  <button
                    onClick={() =>
                      openFormTab({
                        id: "saved-templates-hub",
                        name: "Saved Templates",
                        category: "Forms Hub",
                        description: "Browse and reuse saved form templates created by users.",
                        useCase: "Reusable AI-assisted form templates",
                        route: "/forms/saved-templates",
                        origin: "saved-template",
                      })
                    }
                    className="text-xs font-medium text-[#ed0923] hover:text-[#d10820]"
                  >
                    View all
                  </button>
                </div>
                <div className="space-y-2">
                  {filteredSavedTemplates.length > 0 ? (
                    filteredSavedTemplates.slice(0, 4).map((template) => (
                      <button
                        key={template.id}
                        onClick={() =>
                          openFormTab({
                            id: template.id,
                            name: template.name,
                            category: template.type,
                            description: `${template.type} saved template ready to reuse.`,
                            useCase: "Resume and reuse a saved form template",
                            route: template.route,
                            origin: "saved-template",
                            progress: template.progress,
                            lastEdited: template.lastEdited,
                            draft: template.draft,
                          })
                        }
                        className="w-full rounded-lg border border-gray-200 bg-white p-3 text-left hover:border-[#ed0923] hover:bg-red-50 transition"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-medium text-gray-900">{template.name}</p>
                            <p className="mt-1 text-xs text-gray-500">{template.type} saved template</p>
                          </div>
                          <span className="rounded-full bg-gray-100 px-2 py-1 text-[10px] font-semibold text-gray-700">
                            {template.progress}
                          </span>
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="rounded-lg border border-dashed border-gray-300 bg-white p-4 text-xs text-gray-500">
                      No saved templates match your search.
                    </div>
                  )}
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-gray-600">Pre-Built Forms</h3>
                  <button
                    onClick={() =>
                      openFormTab({
                        id: "prebuilt-forms-hub",
                        name: "Pre-Built Forms",
                        category: "Forms Hub",
                        description: "Open one of the standard Toyota job forms.",
                        useCase: "Start from a standard form",
                        route: "/forms/pre-built-forms",
                        origin: "prebuilt-form",
                      })
                    }
                    className="text-xs font-medium text-[#ed0923] hover:text-[#d10820]"
                  >
                    View all
                  </button>
                </div>
                <div className="space-y-2">
                  {filteredPreBuiltForms.length > 0 ? (
                    filteredPreBuiltForms.map((form) => (
                      <button
                        key={form.id}
                        onClick={() =>
                          openFormTab({
                            id: form.id,
                            name: form.name,
                            category: form.category,
                            description: form.description,
                            useCase: form.useCase,
                            route: form.route,
                            origin: "prebuilt-form",
                          })
                        }
                        className="w-full rounded-lg border border-gray-200 bg-gray-50 p-3 text-left hover:border-[#ed0923] hover:bg-red-50 transition"
                      >
                        <p className="text-sm font-medium text-gray-900">{form.name}</p>
                        <div className="mt-2 flex items-center gap-2">
                          <span className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700">
                            {form.category}
                          </span>
                          <span className="text-xs text-gray-500">{form.description}</span>
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="rounded-lg border border-dashed border-gray-300 bg-white p-4 text-xs text-gray-500">
                      No pre-built forms match your search.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      }
      case "promotions-edits": {
        const allPendingPromotions = [...submittedPromotions, ...pendingPromotionsState];
        return (
          <div className="p-4 space-y-3 flex flex-col h-full overflow-y-auto">
            {promotionSubmissionMessage && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
                {promotionSubmissionMessage}
              </div>
            )}
            {/* Ready for Promotion */}
            <div className="space-y-2">
              <div className="flex items-center justify-between sticky top-0 bg-white/95 z-10 py-1">
                <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Ready for Promotion</h3>
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-medium">{mockReadyForPromotion.length}</span>
              </div>
              <div className="space-y-1.5">
                {mockReadyForPromotion.map((item) => (
                  <div
                    key={item.id}
                    className="p-2 rounded-lg bg-gray-50 hover:bg-gray-100 border border-gray-200 transition flex items-start gap-2"
                  >
                    <input
                      type="checkbox"
                      checked={selectedPromotions.includes(item.id)}
                      onChange={() =>
                        setSelectedPromotions((prev) =>
                          prev.includes(item.id) ? prev.filter((id) => id !== item.id) : [...prev, item.id]
                        )
                      }
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-[#ed0923] focus:ring-[#ed0923]"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
                      <div className="flex items-center gap-1 mt-0.5 flex-wrap">
                        <span className={`text-xs font-medium ${getPromotionTypeColor(item.type)}`}>{item.type}</span>
                        <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">{item.currentEnvironment}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              {selectedPromotions.length > 0 && (
                <button
                  onClick={() => {
                    console.log("Requesting promotion for:", selectedPromotions);
                    setSelectedPromotions([]);
                  }}
                  className="w-full mt-2 px-2 py-1.5 bg-[#ed0923] text-white text-xs font-medium rounded-lg hover:bg-[#d10820] transition"
                >
                  Request Promotion ({selectedPromotions.length})
                </button>
              )}
            </div>

            {/* Pending Promotions */}
            {allPendingPromotions.length > 0 && (
              <div className="space-y-2 border-t border-gray-200 pt-3">
                <div className="flex items-center justify-between sticky top-12 bg-white/95 z-10 py-1">
                  <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Pending Promotions</h3>
                  <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded font-medium">{allPendingPromotions.length}</span>
                </div>
                <div className="space-y-1.5">
                  {allPendingPromotions.map((item) => (
                    <div
                      key={item.id}
                      className={`p-2 rounded-lg border transition ${
                        highlightedPendingPromotionId === item.id
                          ? "bg-yellow-50 border-yellow-300 shadow-sm"
                          : "bg-gray-50 border-gray-200"
                      }`}
                    >
                      <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
                      <div className="flex items-center gap-1 mt-0.5">
                        <span className={`text-xs font-medium ${getPromotionTypeColor(item.type)}`}>{item.type}</span>
                        <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">{item.currentEnvironment}</span>
                        <span className="text-xs text-gray-400">→</span>
                        <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">{item.targetEnvironment}</span>
                      </div>
                      {highlightedPendingPromotionId === item.id && (
                        <div className="mt-2 text-xs font-semibold text-yellow-800">Newly submitted</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Rejected / Needs Revision */}
            {rejectedPromotionsState.length > 0 && (
              <div className="space-y-2 border-t border-gray-200 pt-3">
                <div className="flex items-center justify-between sticky top-24 bg-white/95 z-10 py-1">
                  <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Needs Revision</h3>
                  <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded font-medium">{rejectedPromotionsState.length}</span>
                </div>
                <div className="space-y-1.5">
                  {rejectedPromotionsState.map((item) => (
                    <div key={item.id} className="p-2 rounded-lg bg-red-50 border border-red-200">
                      <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
                      <p className="text-xs text-red-700 mt-0.5 line-clamp-2">{item.rejectionReason}</p>
                      <div className="flex items-center gap-1 mt-1.5">
                        <span className={`text-xs font-medium ${getPromotionTypeColor(item.type)}`}>{item.type}</span>
                        <span className="text-xs text-gray-500">{formatPromotionDate(item.lastModified || item.createdAt)}</span>
                      </div>
                      <button
                        onClick={() => handleOpenTabInPane({
                          type: "revision",
                          id: `revision-${item.id}`,
                          name: item.name,
                          revisionJobType: item.type,
                          revisionRejectionReason: item.rejectionReason,
                        }, "primary")}
                        className="w-full mt-2 px-2 py-1 text-xs font-medium bg-red-200 text-red-900 rounded hover:bg-red-300 transition"
                      >
                        Revise
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recently Promoted */}
            {mockRecentlyPromoted.length > 0 && (
              <div className="space-y-2 border-t border-gray-200 pt-3">
                <div className="flex items-center justify-between sticky top-32 bg-white/95 z-10 py-1">
                  <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Recently Promoted</h3>
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded font-medium">{mockRecentlyPromoted.length}</span>
                </div>
                <div className="space-y-1.5">
                  {mockRecentlyPromoted.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => handleOpenTabInPane({ type: "promotion", id: item.id, name: item.name }, "primary")}
                      className="w-full p-2 rounded-lg bg-gray-50 hover:bg-gray-100 border border-gray-200 transition text-left"
                    >
                      <p className="text-sm font-medium text-gray-900 truncate">{item.name}</p>
                      <div className="flex items-center gap-1 mt-0.5">
                        <span className={`text-xs font-medium ${getPromotionTypeColor(item.type)}`}>{item.type}</span>
                        <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">{item.currentEnvironment}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      }
      default:
        return null;
    }
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      <UserNavigation
        activePage={activeTab?.type === "job" ? "Jobs" : "Dashboard"}
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Left Icon Rail */}
        <div className="w-16 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col items-center py-4 gap-2">
          {panels.map((panel) => (
            <button
              key={panel.id}
              onClick={() => handlePanelToggle(panel.id)}
              className={`p-3 rounded-lg transition-colors relative ${
                activePanelId === panel.id
                  ? "bg-[#ed0923]/10 text-[#ed0923]"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
              }`}
              title={panel.label}
            >
              {panel.icon}
              {/* Required Actions Badge */}
              {panel.id === "required-actions" && requiredActionsCount > 0 && (
                <div className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shadow-md">
                  {badgeLabel}
                </div>
              )}
            </button>
          ))}
        </div>

        {/* Left Panel with Resize Handle */}
        {activePanelId && (
          <>
            <div 
              className="flex-shrink-0 bg-white border-r border-gray-200 overflow-y-auto"
              style={{ width: `${jobsPanelWidth}px` }}
            >
              <div className="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">
                  {panels.find((p) => p.id === activePanelId)?.label}
                </h2>
                <button
                  onClick={() => setActivePanelId(null)}
                  className="text-gray-500 hover:text-gray-900 transition"
                  title="Close panel"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
              </div>
              {renderPanelContent()}
            </div>

            {/* Jobs Panel Resize Handle */}
            <div 
              className={`w-1 flex-shrink-0 bg-gray-300 hover:bg-blue-500 cursor-col-resize transition-colors ${isResizing === "jobs" ? "bg-blue-500" : ""}`}
              onMouseDown={handleResizeMouseDown("jobs")}
              title="Drag to resize Jobs panel"
            />
          </>
        )}

        {/* Main Content with Tab System - Split View Support */}
        <main className="flex-1 flex flex-col overflow-hidden min-h-0">
          {workspace.mode === "single" ? (
            // SINGLE PANE MODE
            <>
              {/* Tab Bar - Primary Pane */}
              <div className="flex-shrink-0 bg-white border-b border-gray-200 flex items-center gap-1 px-4 py-0 overflow-x-auto justify-between">
                <div className="flex items-center gap-1 flex-1 overflow-x-auto">
                  {workspace.primary.tabs.map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => handleActivateTabInPane(tab.id, "primary")}
                      className={`flex items-center gap-2 px-3 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition ${
                        workspace.primary.activeTabId === tab.id
                          ? "text-[#ed0923] border-[#ed0923]"
                          : "text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50"
                      }`}
                    >
                      {tab.title}
                      {tab.closable && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCloseTabInPane(tab.id, "primary");
                          }}
                          className="rounded hover:bg-gray-200 p-0.5 text-gray-400 hover:text-gray-600 transition"
                          title="Close tab"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Workspace - Main flex container for content + console */}
              <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                {/* CONTENT PANEL - Form or other workspace content */}
                {activeTab?.type === "create-job" ? (
                  <div className="flex-1 flex items-center justify-center p-8 text-center">
                    <div className="max-w-sm">
                      <p className="text-lg font-semibold text-gray-700">Use the AI Chat Assistant</p>
                      <p className="mt-2 text-sm text-gray-500">
                        Job creation is handled through the chat panel. Describe the SQL job you want to create and the assistant will guide you.
                      </p>
                    </div>
                  </div>
                ) : (
                  /* OTHER CONTENT PANEL */
                  <div 
                    className={`flex-1 overflow-y-auto transition-all relative min-h-0 ${
                      isDraggingOverWorkspace 
                        ? isDraggingOverSplitZone === "left" 
                          ? 'bg-purple-50 border-l-4 border-purple-400'
                          : isDraggingOverSplitZone === "right"
                          ? 'bg-purple-50 border-r-4 border-purple-400'
                          : 'bg-blue-50 border-2 border-blue-300'
                        : ''
                    }`}
                    onDragOver={handleWorkspaceDragOver}
                    onDragLeave={handleWorkspaceDragLeave}
                    onDrop={handleWorkspaceDrop}
                  >
                    {/* Drag and Drop Hint */}
                    {isDraggingOverWorkspace && (
                      <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                        {isDraggingOverSplitZone === "left" ? (
                          <div className="text-center">
                            <p className="text-lg font-semibold text-purple-900">Drop here to create left split pane</p>
                            <p className="text-sm text-purple-700 mt-1">This item opens on the left</p>
                          </div>
                        ) : isDraggingOverSplitZone === "right" ? (
                          <div className="text-center">
                            <p className="text-lg font-semibold text-purple-900">Drop here to create right split pane</p>
                            <p className="text-sm text-purple-700 mt-1">This item opens on the right</p>
                          </div>
                        ) : (
                          <div className="text-center bg-blue-50/80">
                            <p className="text-lg font-semibold text-blue-900">Drop job here to open in workspace</p>
                            <p className="text-sm text-blue-700 mt-1">Center = primary pane | Edges = split pane</p>
                          </div>
                        )}
                      </div>
                    )}

                    {renderTabContent(activeTab)}
                  </div>
                )}

                {/* Console Panel - Always Visible Bottom Panel with constrained height */}
                <>
                  {/* Resize Handle - Top Edge (Draggable) - Higher z-index to ensure it's always clickable */}
                  <div
                    onMouseDown={handleConsoleResizeStart}
                    className={`h-1.5 flex-shrink-0 transition-colors pointer-events-auto relative z-50 ${
                      isResizingConsole 
                        ? "bg-blue-500 cursor-row-resize" 
                        : "bg-gray-300 hover:bg-blue-400 cursor-row-resize"
                    }`}
                    title="Drag to resize console - drag up to expand, down to collapse"
                    style={{ touchAction: "none" }}
                  />
                  
                  {/* Console Panel - Flex-shrink-0 prevents it from being squeezed by flex layout */}
                  <div
                    className="flex-shrink-0 bg-white border-t border-gray-200 overflow-hidden flex flex-col relative"
                    style={{ height: `${consoleHeight}px`, maxHeight: `${consoleHeight}px` }}
                  >
                    {/* Console Header - Clickable to Toggle */}
                    <div
                      onClick={toggleConsole}
                      className="flex items-center justify-between px-4 py-2.5 border-b border-gray-200 flex-shrink-0 bg-gray-50 cursor-pointer hover:bg-gray-100 transition select-none"
                      title="Click to collapse/expand console"
                    >
                      <div className="flex items-center gap-3">
                        {consoleHeight <= 80 ? (
                          <ChevronUp className="h-4 w-4 text-gray-600" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-gray-600" />
                        )}
                        <span className="text-sm font-semibold text-gray-700">Console</span>
                      </div>
                      
                      {consoleHeight > 80 && (
                        <div className="flex items-center gap-1 border-l border-gray-300 pl-3">
                          {["json", "logs", "events"].map((tab) => (
                            <button
                              key={tab}
                              onClick={(e) => {
                                e.stopPropagation();
                                setConsoleActiveTab(tab as any);
                              }}
                              className={`px-2.5 py-1 text-xs font-medium rounded transition ${
                                consoleActiveTab === tab
                                  ? "text-[#ed0923] bg-[#ed0923]/10"
                                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                              }`}
                            >
                              {tab.toUpperCase()}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Console Content - Only visible when expanded - flex-1 ensures it fills available space */}
                    {consoleHeight > 80 && (
                      <div className="flex-1 overflow-y-auto font-mono text-sm p-3 bg-white min-h-0">
                        {consoleActiveTab === "json" && (
                          <div className="bg-white rounded border border-gray-200 p-3">
                            <pre className="text-gray-800 whitespace-pre-wrap break-words text-xs leading-relaxed">
                              {JSON.stringify(getConsoleJSON(), null, 2)}
                            </pre>
                          </div>
                        )}
                        {consoleActiveTab === "logs" && (
                          <div className="bg-white rounded border border-gray-200 p-3 space-y-1 font-mono">
                            {getConsoleLogs().length > 0 ? getConsoleLogs().map((log, idx) => (
                              <div key={idx} className="flex gap-2 text-xs leading-relaxed">
                                <span className="text-gray-400 shrink-0">{log.time}</span>
                                <span className={`shrink-0 font-semibold w-16 ${
                                  (log as any).level === "ERROR" ? "text-red-600" :
                                  (log as any).level === "WARNING" ? "text-amber-600" :
                                  (log as any).level === "DEBUG" ? "text-gray-400" :
                                  "text-blue-600"
                                }`}>{(log as any).level ?? "INFO"}</span>
                                <span className="text-gray-800 break-all">{log.message}</span>
                              </div>
                            )) : (
                              <p className="text-xs text-gray-400 py-2">No logs yet — run a job to see live output here.</p>
                            )}
                          </div>
                        )}
                        {consoleActiveTab === "events" && (
                          <div className="bg-white rounded border border-gray-200 p-3 space-y-1">
                            {getConsoleEvents().map((event, idx) => (
                              <div key={idx} className="text-gray-700 text-xs">
                                <span className="text-[#ed0923]">→</span> <span className="text-gray-800">{event.action}</span>
                                <span className="text-gray-500 ml-2">({event.timestamp})</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              </div>
            </>
          ) : (
            /* SPLIT PANE MODE */
            <>
              {/* Workspace Content with Console */}
              <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                {/* Workspace Split Container with Drag Handlers - Flex row for left/right panes */}
                <div 
                  className={`flex-1 flex gap-0 overflow-hidden transition-all relative min-h-0 ${isDraggingOverWorkspace ? (isDraggingOverPane === "left" ? 'border-l-4 border-blue-400' : isDraggingOverPane === "right" ? 'border-r-4 border-blue-400' : '') : ''}`}
                  onDragOver={handleWorkspaceDragOver}
                  onDragLeave={handleWorkspaceDragLeave}
                  onDrop={handleWorkspaceDrop}
                >
                {/* Drag and Drop Hint for Split Mode */}
                {isDraggingOverWorkspace && (
                  <div className="absolute inset-0 pointer-events-none flex items-center justify-center z-10">
                    {isDraggingOverPane === "left" ? (
                      <div className="text-center">
                        <p className="text-lg font-semibold text-blue-900">Drop here to open in left pane</p>
                        <p className="text-sm text-blue-700 mt-1">Item will open on the left</p>
                      </div>
                    ) : isDraggingOverPane === "right" ? (
                      <div className="text-center">
                        <p className="text-lg font-semibold text-blue-900">Drop here to open in right pane</p>
                        <p className="text-sm text-blue-700 mt-1">Item will open on the right</p>
                      </div>
                    ) : (
                      <div className="text-center">
                        <p className="text-lg font-semibold text-blue-900">Drop here to open in primary pane</p>
                        <p className="text-sm text-blue-700 mt-1">Center = primary | Edges = secondary</p>
                      </div>
                    )}
                  </div>
                )}

                {workspace.secondaryPosition === "left" ? (
                  <>
                    {/* Secondary Pane (Left Position) */}
                    <div 
                      className={`flex-shrink-0 flex flex-col overflow-hidden border-r border-gray-200 transition-colors min-h-0 ${isDraggingOverPane === "left" ? "bg-blue-50" : ""}`}
                      style={{ width: `${workspacePaneAWidth}px` }}
                    >
                      {/* Secondary Pane Header with Close */}
                      <div className="flex-shrink-0 bg-white border-b border-gray-200 flex items-center justify-between px-4 py-3">
                        <div className="flex items-center gap-1 overflow-x-auto flex-1">
                          {workspace.secondary.tabs.map((tab) => (
                            <button
                              key={tab.id}
                              onClick={() => handleActivateTabInPane(tab.id, "secondary")}
                              className={`flex items-center gap-2 px-3 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition ${
                                workspace.secondary.activeTabId === tab.id
                                  ? "text-[#ed0923] border-[#ed0923]"
                                  : "text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50"
                              }`}
                            >
                              {tab.title}
                              {tab.closable && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleCloseTabInPane(tab.id, "secondary");
                                  }}
                                  className="rounded hover:bg-gray-200 p-0.5 text-gray-400 hover:text-gray-600 transition"
                                  title="Close tab"
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              )}
                            </button>
                          ))}
                        </div>
                        <button
                          onClick={handleCollapseSplitMode}
                          className="ml-2 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition flex items-center gap-1.5"
                          title="Close split view and return to single pane"
                        >
                          <X className="h-3.5 w-3.5" />
                          Close Split
                        </button>
                      </div>

                      {/* Secondary Pane Content */}
                      <div className="flex-1 overflow-y-auto min-h-0">
                        {(() => {
                          const tab = workspace.secondary.tabs.find((t) => t.id === workspace.secondary.activeTabId);
                          return renderTabContent(tab);
                        })()}
                      </div>
                    </div>

                    {/* Workspace Pane Resize Handle */}
                    <div 
                      className={`w-1 flex-shrink-0 bg-gray-300 hover:bg-blue-500 cursor-col-resize transition-colors ${isResizing === "workspace" ? "bg-blue-500" : ""}`}
                      onMouseDown={handleResizeMouseDown("workspace")}
                      title="Drag to resize panes"
                    />

                    {/* Primary Pane (Right Position) */}
                    <div className={`flex-1 flex flex-col overflow-hidden transition-colors min-h-0 ${isDraggingOverPane === "right" ? "bg-blue-50" : ""}`}>
                      {/* Primary Pane Tab Bar */}
                      <div className="flex-shrink-0 bg-white border-b border-gray-200 flex items-center gap-1 px-4 py-0 overflow-x-auto">
                        {workspace.primary.tabs.map((tab) => (
                          <button
                            key={tab.id}
                            onClick={() => handleActivateTabInPane(tab.id, "primary")}
                            className={`flex items-center gap-2 px-3 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition ${
                              workspace.primary.activeTabId === tab.id
                                ? "text-[#ed0923] border-[#ed0923]"
                                : "text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50"
                            }`}
                          >
                            {tab.title}
                            {tab.closable && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCloseTabInPane(tab.id, "primary");
                                }}
                                className="rounded hover:bg-gray-200 p-0.5 text-gray-400 hover:text-gray-600 transition"
                                title="Close tab"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            )}
                          </button>
                        ))}
                      </div>

                      {/* Primary Pane Content */}
                      <div className="flex-1 overflow-y-auto min-h-0">
                        {(() => {
                          const tab = workspace.primary.tabs.find((t) => t.id === workspace.primary.activeTabId);
                          return renderTabContent(tab);
                        })()}
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    {/* Primary Pane (Left Position) */}
                    <div 
                      className={`flex-shrink-0 flex flex-col overflow-hidden border-r border-gray-200 transition-colors min-h-0 ${isDraggingOverPane === "left" ? "bg-blue-50" : ""}`}
                      style={{ width: `${workspacePaneAWidth}px` }}
                    >
                      {/* Primary Pane Tab Bar */}
                      <div className="flex-shrink-0 bg-white border-b border-gray-200 flex items-center gap-1 px-4 py-0 overflow-x-auto">
                        {workspace.primary.tabs.map((tab) => (
                          <button
                            key={tab.id}
                            onClick={() => handleActivateTabInPane(tab.id, "primary")}
                            className={`flex items-center gap-2 px-3 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition ${
                              workspace.primary.activeTabId === tab.id
                                ? "text-[#ed0923] border-[#ed0923]"
                                : "text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50"
                            }`}
                          >
                            {tab.title}
                            {tab.closable && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCloseTabInPane(tab.id, "primary");
                                }}
                                className="rounded hover:bg-gray-200 p-0.5 text-gray-400 hover:text-gray-600 transition"
                                title="Close tab"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            )}
                          </button>
                        ))}
                      </div>

                      {/* Primary Pane Content */}
                      <div className="flex-1 overflow-y-auto min-h-0">
                        {(() => {
                          const tab = workspace.primary.tabs.find((t) => t.id === workspace.primary.activeTabId);
                          return renderTabContent(tab);
                        })()}
                      </div>
                    </div>

                    {/* Workspace Pane Resize Handle */}
                    <div 
                      className={`w-1 flex-shrink-0 bg-gray-300 hover:bg-blue-500 cursor-col-resize transition-colors ${isResizing === "workspace" ? "bg-blue-500" : ""}`}
                      onMouseDown={handleResizeMouseDown("workspace")}
                      title="Drag to resize panes"
                    />

                    {/* Secondary Pane (Right Position) */}
                    <div className={`flex-1 flex flex-col overflow-hidden transition-colors min-h-0 ${isDraggingOverPane === "right" ? "bg-blue-50" : ""}`}>
                      {/* Secondary Pane Header with Close */}
                      <div className="flex-shrink-0 bg-white border-b border-gray-200 flex items-center justify-between px-4 py-3">
                        <div className="flex items-center gap-1 overflow-x-auto flex-1">
                          {workspace.secondary.tabs.map((tab) => (
                            <button
                              key={tab.id}
                              onClick={() => handleActivateTabInPane(tab.id, "secondary")}
                              className={`flex items-center gap-2 px-3 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition ${
                                workspace.secondary.activeTabId === tab.id
                                  ? "text-[#ed0923] border-[#ed0923]"
                                  : "text-gray-600 border-transparent hover:text-gray-900 hover:bg-gray-50"
                              }`}
                            >
                              {tab.title}
                              {tab.closable && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleCloseTabInPane(tab.id, "secondary");
                                  }}
                                  className="rounded hover:bg-gray-200 p-0.5 text-gray-400 hover:text-gray-600 transition"
                                  title="Close tab"
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              )}
                            </button>
                          ))}
                        </div>
                        <button
                          onClick={handleCollapseSplitMode}
                          className="ml-2 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition flex items-center gap-1.5"
                          title="Close split view and return to single pane"
                        >
                          <X className="h-3.5 w-3.5" />
                          Close Split
                        </button>
                      </div>

                      {/* Secondary Pane Content */}
                      <div className="flex-1 overflow-y-auto min-h-0">
                        {(() => {
                          const tab = workspace.secondary.tabs.find((t) => t.id === workspace.secondary.activeTabId);
                          return renderTabContent(tab);
                        })()}
                      </div>
                    </div>
                  </>
                )}
                </div>

                {/* Console Panel - Always Visible Bottom Panel with constrained height */}
                <>
                  {/* Resize Handle - Top Edge (Draggable) - Higher z-index to ensure it's always clickable */}
                  <div
                    onMouseDown={handleConsoleResizeStart}
                    className={`h-1.5 flex-shrink-0 transition-colors pointer-events-auto relative z-50 ${
                      isResizingConsole 
                        ? "bg-blue-500 cursor-row-resize" 
                        : "bg-gray-300 hover:bg-blue-400 cursor-row-resize"
                    }`}
                    title="Drag to resize console - drag up to expand, down to collapse"
                    style={{ touchAction: "none" }}
                  />
                  
                  {/* Console Panel - Flex-shrink-0 prevents it from being squeezed by flex layout */}
                  <div
                    className="flex-shrink-0 bg-white border-t border-gray-200 overflow-hidden flex flex-col relative"
                    style={{ height: `${consoleHeight}px`, maxHeight: `${consoleHeight}px` }}
                  >
                    {/* Console Header - Clickable to Toggle */}
                    <div
                      onClick={toggleConsole}
                      className="flex items-center justify-between px-4 py-2.5 border-b border-gray-200 flex-shrink-0 bg-gray-50 cursor-pointer hover:bg-gray-100 transition select-none"
                      title="Click to collapse/expand console"
                    >
                      <div className="flex items-center gap-3">
                        {consoleHeight <= 80 ? (
                          <ChevronUp className="h-4 w-4 text-gray-600" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-gray-600" />
                        )}
                        <span className="text-sm font-semibold text-gray-700">Console</span>
                      </div>
                      
                      {consoleHeight > 80 && (
                        <div className="flex items-center gap-1 border-l border-gray-300 pl-3">
                          {["json", "logs", "events"].map((tab) => (
                            <button
                              key={tab}
                              onClick={(e) => {
                                e.stopPropagation();
                                setConsoleActiveTab(tab as any);
                              }}
                              className={`px-2.5 py-1 text-xs font-medium rounded transition ${
                                consoleActiveTab === tab
                                  ? "text-[#ed0923] bg-[#ed0923]/10"
                                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
                              }`}
                            >
                              {tab.toUpperCase()}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Console Content - Only visible when expanded - flex-1 ensures it fills available space */}
                    {consoleHeight > 80 && (
                      <div className="flex-1 overflow-y-auto font-mono text-sm p-3 bg-white min-h-0">
                        {consoleActiveTab === "json" && (
                          <div className="bg-white rounded border border-gray-200 p-3">
                            <pre className="text-gray-800 whitespace-pre-wrap break-words text-xs leading-relaxed">
                              {JSON.stringify(getConsoleJSON(), null, 2)}
                            </pre>
                          </div>
                        )}
                        {consoleActiveTab === "logs" && (
                          <div className="bg-white rounded border border-gray-200 p-3 space-y-1 font-mono">
                            {getConsoleLogs().length > 0 ? getConsoleLogs().map((log, idx) => (
                              <div key={idx} className="flex gap-2 text-xs leading-relaxed">
                                <span className="text-gray-400 shrink-0">{log.time}</span>
                                <span className={`shrink-0 font-semibold w-16 ${
                                  (log as any).level === "ERROR" ? "text-red-600" :
                                  (log as any).level === "WARNING" ? "text-amber-600" :
                                  (log as any).level === "DEBUG" ? "text-gray-400" :
                                  "text-blue-600"
                                }`}>{(log as any).level ?? "INFO"}</span>
                                <span className="text-gray-800 break-all">{log.message}</span>
                              </div>
                            )) : (
                              <p className="text-xs text-gray-400 py-2">No logs yet — run a job to see live output here.</p>
                            )}
                          </div>
                        )}
                        {consoleActiveTab === "events" && (
                          <div className="bg-white rounded border border-gray-200 p-3 space-y-1">
                            {getConsoleEvents().map((event, idx) => (
                              <div key={idx} className="text-gray-700 text-xs">
                                <span className="text-[#ed0923]">→</span> <span className="text-gray-800">{event.action}</span>
                                <span className="text-gray-500 ml-2">({event.timestamp})</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </>
              </div>
            </>
          )}
        </main>

        {/* Workspace and Chat Resize Handle */}
        {isChatPanelOpen && (
          <div 
            className={`w-1 flex-shrink-0 bg-gray-300 hover:bg-blue-500 cursor-col-resize transition-colors ${isResizing === "chat" ? "bg-blue-500" : ""}`}
            onMouseDown={handleResizeMouseDown("chat")}
            title="Drag to resize Chat panel"
          />
        )}

        {/* Chat Panel - Right Side (Part of Flex Layout) */}
        {isChatPanelOpen && (
          <div style={{ width: `${chatPanelWidth}px`, flexShrink: 0 }}>
            <ChatPanel
              isOpen={isChatPanelOpen}
              onClose={() => setIsChatPanelOpen(false)}
              onJobCreationIntent={() => {
                handleOpenTabInPane({ type: "create-job", id: "create-job", name: "Create Job" }, "primary");
                setJobDraft((prev) => (Object.keys(prev).length > 0 ? prev : {}));
              }}
              onFieldsExtracted={handleChatFieldsExtracted}
              currentDraftData={jobDraft}
              assistantNotices={chatAssistantNotices}
              onConsoleEvent={emitConsoleEvent}
              resources={resources.map((r) => ({
                id: r.id,
                name: r.name,
                type: r.type ?? "Custom",
                connector: r.connector,
                config: r.config ?? {},
              }))}
              onRunStarted={(runId) => {
                setActiveRunId(runId);
                setRunLogs([]);
                setConsoleActiveTab("logs");
                setConsoleHeight(300);
                void refreshJobRuns();
              }}
            />
          </div>
        )}
      </div>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />

      {/* AI Assistant Panel */}
      {isAIPanelOpen && activeTab?.type === "job" && jobSpec && (
        <div className="fixed inset-y-0 right-0 w-80 bg-white shadow-xl border-l border-gray-200 flex flex-col z-50">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <Wand2 className="h-5 w-5 text-[#ed0923]" />
              <h3 className="font-semibold text-gray-900">AI Assistant</h3>
            </div>
            <button
              onClick={() => setIsAIPanelOpen(false)}
              className="text-gray-500 hover:text-gray-900 transition"
              title="Close panel"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 flex flex-col">
            {aiMessages.map((message) => (
              <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`rounded-lg px-4 py-2 text-sm flex-shrink-0 max-w-[85%] ${
                    message.role === "user"
                      ? "bg-[#ed0923] text-white"
                      : "bg-gray-100 text-gray-900"
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words">{message.content}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Input Area */}
          <div className="border-t border-gray-200 p-4 space-y-3 flex-shrink-0 w-full">
            <div className="flex gap-2 w-full">
              <input
                type="text"
                placeholder="Ask me anything..."
                value={aiInput}
                onChange={(e) => setAiInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendAIMessage();
                  }
                }}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923] min-w-0"
              />
              <button
                onClick={handleSendAIMessage}
                disabled={!aiInput.trim()}
                className="rounded-lg bg-[#ed0923] p-2 text-white hover:bg-[#d10820] disabled:bg-gray-300 transition flex-shrink-0"
                title="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <p className="text-xs text-gray-500">
              💡 Tip: Describe changes in natural language and I'll help modify your job spec
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function CalendarButtonInner() {
  const { openCalendar } = useCalendarOverlay();
  
  return (
    <button
      onClick={openCalendar}
      className="w-full text-center text-sm text-[#ed0923] hover:font-semibold transition py-2 px-3 rounded-lg hover:bg-red-50"
    >
      Open Calendar →
    </button>
  );
}
