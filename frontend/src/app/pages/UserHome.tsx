import { useState, useEffect, useRef } from "react";
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
import { CreateJobForm } from "../components/CreateJobForm";
import ExcelReportForm from "../components/user/ExcelReportForm";
import SQLJobForm from "../components/user/SQLJobForm";
import PowerPointForm from "../components/user/PowerPointForm";
import { useCalendarOverlay } from "../contexts/CalendarContext";
import { createJobFromForm, getCalendarEvents, getDraftForms, getMyJobs, getPendingPromotionResources, getSavedTemplates, mapJobToPendingPromotionResource, saveDraft, saveTemplate, subscribeToUserDashboardStore, withdrawPendingSubmission } from "../lib/userDashboardStore";
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
  getVisibleRequiredActions,
  markRequiredActionResolved,
  requiredActionItems,
  requiredActionStateBadge,
  requiredActionUrgencyBadge,
  getUrgencyLabel,
} from "./requiredActionsData";

const kpis = [
  { label: "My Active Jobs", value: 12, hint: "+2 this week", tone: "text-green-600" },
  { label: "Pending Approvals", value: 3, hint: "2 high priority", tone: "text-amber-600" },
  { label: "Failed Runs (24h)", value: 1, hint: "Investigate before noon", tone: "text-red-600" },
  { label: "Saved Jobs", value: 27, hint: "5 updated recently", tone: "text-[#ed0923]" },
];

const recentJobs = [
  { name: "Monthly Dealer KPI Deck", type: "PowerPoint", schedule: "Monthly, day 1", status: "Healthy" },
  { name: "Warranty Claims Rollup", type: "Excel", schedule: "Weekly, Mon 08:00", status: "Running" },
  { name: "Customer Churn Analysis", type: "SQL", schedule: "Daily, 06:00", status: "Needs Attention" },
  { name: "Quarterly Revenue Report", type: "PowerPoint", schedule: "Quarterly, day 1", status: "Healthy" },
];

type DashboardJobListItem = {
  id: string;
  name: string;
  type: string;
  schedule: string;
  status: "Healthy" | "Running" | "Needs Attention";
  payload?: WorkspaceJobPayload;
};

const draftJobs = [
  { id: "draft-001", name: "Customer Retention Workflow", type: "Workflow", lastEdited: "1 hour ago" },
  { id: "draft-002", name: "Dealer Forecast Pipeline", type: "SQL", lastEdited: "3 hours ago" },
  { id: "draft-003", name: "Revenue Summary Agent", type: "AI Agent", lastEdited: "Yesterday" },
];

const retiredJobs = [
  { id: "retired-001", name: "Legacy Revenue Dashboard", type: "Dashboard", retiredDate: "Feb 15, 2026" },
  { id: "retired-002", name: "Old Churn Monitor", type: "Python Script", retiredDate: "Jan 30, 2026" },
  { id: "retired-003", name: "Archive Claims Summary", type: "Excel", retiredDate: "Jan 20, 2026" },
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
  jobName: string;
  jobType: "PowerPoint" | "Excel" | "SQL" | "Custom";
  status: "scheduled" | "running" | "completed" | "failed";
  scheduledTime: Date;
  completedTime?: Date;
}

const mockUpcomingRuns: RunItem[] = [
  {
    id: "run-001",
    jobName: "Monthly Dealer KPI Deck",
    jobType: "PowerPoint",
    status: "scheduled",
    scheduledTime: new Date(Date.now() + 24 * 60 * 60 * 1000), // Tomorrow 8:00 AM
  },
  {
    id: "run-002",
    jobName: "Customer Churn Analysis",
    jobType: "SQL",
    status: "scheduled",
    scheduledTime: new Date(Date.now() + 18 * 60 * 60 * 1000), // Today 6:00 PM
  },
  {
    id: "run-003",
    jobName: "Quarterly Revenue Report",
    jobType: "PowerPoint",
    status: "scheduled",
    scheduledTime: new Date(Date.now() + 22 * 24 * 60 * 60 * 1000), // Apr 1, 9:00 AM
  },
];

const mockRecentRuns: RunItem[] = [
  {
    id: "run-004",
    jobName: "Warranty Claims Rollup",
    jobType: "Excel",
    status: "completed",
    scheduledTime: new Date(Date.now() - 30 * 60 * 1000), // 30 minutes ago
    completedTime: new Date(Date.now() - 10 * 60 * 1000), // 10 minutes ago
  },
  {
    id: "run-005",
    jobName: "Customer Churn Analysis",
    jobType: "SQL",
    status: "failed",
    scheduledTime: new Date(Date.now() - 90 * 60 * 1000), // 90 minutes ago
    completedTime: new Date(Date.now() - 60 * 60 * 1000), // 1 hour ago
  },
  {
    id: "run-006",
    jobName: "Monthly Dealer KPI Deck",
    jobType: "PowerPoint",
    status: "completed",
    scheduledTime: new Date(Date.now() - 24 * 60 * 60 * 1000 - 2 * 60 * 60 * 1000), // Yesterday 2 hours earlier
    completedTime: new Date(Date.now() - 24 * 60 * 60 * 1000), // Yesterday
  },
];

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

const createDashboardJobs = (): DashboardJobListItem[] => {
  const storedJobs = getMyJobs().map((job) => ({
    id: job.id,
    name: job.name,
    type: mapStoredJobTypeToDashboardType(job.type),
    schedule:
      job.logs?.find((entry) => entry.message.toLowerCase().includes("runs "))?.message ?? "Manual schedule",
    status: mapStoredJobStatusToDashboardStatus(job.status),
    payload: createWorkspaceJobPayloadFromStoredJob(job),
  }));

  const fallbackJobs = recentJobs
    .filter((job) => !storedJobs.some((storedJob) => storedJob.name === job.name))
    .map((job, index) => ({
      id: `fallback-job-${index + 1}`,
      ...job,
      payload: mockJobSpecs[job.name],
    }));

  return [...storedJobs, ...fallbackJobs];
};

const mapCalendarEventTypeToRunType = (jobType?: string): RunItem["jobType"] => {
  if (jobType === "PowerPoint Deck") return "PowerPoint";
  if (jobType === "Excel Report") return "Excel";
  if (jobType === "Custom Job") return "Custom";
  return "SQL";
};

const createDashboardRuns = () => {
  const calendarEvents = getCalendarEvents();
  const mappedRuns = calendarEvents.map((event) => ({
    id: event.id,
    jobName: event.title,
    jobType: mapCalendarEventTypeToRunType(event.jobType),
    status: event.kind === "past" ? "completed" : "scheduled",
    scheduledTime: new Date(`${event.date}T${event.time}:00`),
  }));

  const upcomingRuns = [
    ...mappedRuns.filter((run) => run.status === "scheduled"),
    ...mockUpcomingRuns,
  ]
    .sort((a, b) => a.scheduledTime.getTime() - b.scheduledTime.getTime())
    .filter((run, index, array) => array.findIndex((candidate) => candidate.jobName === run.jobName && candidate.status === run.status) === index);

  const recentRuns = [
    ...mappedRuns
      .filter((run) => run.status === "completed")
      .map((run) => ({ ...run, completedTime: run.scheduledTime })),
    ...mockRecentRuns,
  ]
    .sort((a, b) => (b.completedTime?.getTime() ?? b.scheduledTime.getTime()) - (a.completedTime?.getTime() ?? a.scheduledTime.getTime()))
    .filter((run, index, array) => array.findIndex((candidate) => candidate.jobName === run.jobName && candidate.status === run.status) === index);

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
  type: "PowerPoint" | "Excel" | "SQL" | "Script" | "API";
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

const ICON_RAIL_WIDTH = 64;
const RESIZE_HANDLE_WIDTH = 4;

export default function UserHome() {
  const navigate = useNavigate();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [activePanelId, setActivePanelId] = useState<string | null>(null);
  
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
  const [dismissedActionIds, setDismissedActionIds] = useState<string[]>([]);
  const [requiredActionSuccessMessage, setRequiredActionSuccessMessage] = useState<string | null>(null);
  const [templateSearch, setTemplateSearch] = useState("");
  const [jobSearch, setJobSearch] = useState("");
  const [jobSort, setJobSort] = useState<"name" | "status" | "type" | "recently-updated">("name");
  const [jobFilter, setJobFilter] = useState<"all" | "PowerPoint" | "Excel" | "SQL" | "Healthy" | "Running" | "Needs Attention">("all");
  const [jobDetailTabById, setJobDetailTabById] = useState<Record<string, "overview" | "runs" | "preview" | "settings">>({});
  const [isDraftsExpanded, setIsDraftsExpanded] = useState(true);
  const [isRetiredJobsExpanded, setIsRetiredJobsExpanded] = useState(false);
  const [templateSort, setTemplateSort] = useState<"name" | "category" | "recently-used" | "recommended">("name");
  const [templateFilter, setTemplateFilter] = useState<"all" | "PowerPoint" | "Excel" | "SQL" | "Workflow" | "Form" | "Dashboard">("all");
  const [selectedPromotions, setSelectedPromotions] = useState<string[]>([]);
  const [highlightedPendingPromotionId, setHighlightedPendingPromotionId] = useState<string | null>(null);
  const [promotionSubmissionMessage, setPromotionSubmissionMessage] = useState<string | null>(null);
  const [rejectedPromotionsState, setRejectedPromotionsState] = useState(mockRejectedPromotions);
  const [pendingPromotionsState, setPendingPromotionsState] = useState(mockPendingPromotions);
  const [submittedPromotions, setSubmittedPromotions] = useState(() => getPendingPromotionResources());
  const [consoleHeight, setConsoleHeight] = useState(50);
  const [consoleActiveTab, setConsoleActiveTab] = useState<"json" | "logs" | "events">("json");
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
  const [dashboardJobs, setDashboardJobs] = useState<DashboardJobListItem[]>(() => createDashboardJobs());
  const [dashboardRuns, setDashboardRuns] = useState(() => createDashboardRuns());
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
    setDashboardJobs(createDashboardJobs());
    setDashboardRuns(createDashboardRuns());
    setSubmittedPromotions(getPendingPromotionResources());
    return subscribeToUserDashboardStore(() => {
      setDashboardJobs(createDashboardJobs());
      setDashboardRuns(createDashboardRuns());
      setSubmittedPromotions(getPendingPromotionResources());
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

  const handleResolveRequiredAction = (actionId: string, actionSubject: string, tabId: string) => {
    markRequiredActionResolved(actionId);
    setDismissedActionIds((prev) => (prev.includes(actionId) ? prev : [...prev, actionId]));
    setRequiredActionSuccessMessage(`Resolved successfully: ${actionSubject}.`);
    setActivePanelId("required-actions");
    handleCloseTabInPane(tabId, "primary");
  };

  const handleWithdrawSubmission = (promotionId: string, promotionName: string) => {
    withdrawPendingSubmission(promotionId);
    setHighlightedPendingPromotionId(null);
    setPromotionSubmissionMessage(`${promotionName} was withdrawn from Pending Promotions.`);
    setActivePanelId("promotions-edits");
    handleCloseTabInPane(`promotion-${promotionId.replace(/\s+/g, "-").toLowerCase()}`, "primary");
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
    // If there are console events, show them as logs
    if (consoleEvents.length > 0) {
      return consoleEvents.map((event) => ({
        time: formatConsoleTime(event.timestamp),
        message: event.message,
        type: event.type,
      }));
    }

    // Otherwise show default execution logs
    return [
      { time: "09:04:02", message: "Job execution started" },
      { time: "09:04:05", message: "Extracting data from source systems" },
      { time: "09:04:12", message: "Processing records: 15,240 rows" },
      { time: "09:04:18", message: "Validation: 99.8% data quality" },
      { time: "09:04:25", message: "Generating outputs: 3 files" },
      { time: "09:04:28", message: "Distribution: sent to 5 recipients" },
      { time: "09:04:30", message: "Job execution completed successfully" },
    ];
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
          const statusOrder = { "Healthy": 0, "Running": 1, "Needs Attention": 2 };
          return (statusOrder[a.status as keyof typeof statusOrder] || 3) - (statusOrder[b.status as keyof typeof statusOrder] || 3);
        case "recently-updated":
          return 0; // Would require timestamp data
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

  const visibleRequiredActions = getVisibleRequiredActions().filter((item) => !dismissedActionIds.includes(item.id));
  const requiredActionPreview = visibleRequiredActions.slice(0, 3);
  const pendingCount = visibleRequiredActions.filter((item) => item.state === "pending").length;

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
      } else if (item.type === "promotion") {
        // Generate consistent tab ID for deduplication
        tabId = `promotion-${item.id.replace(/\s+/g, "-").toLowerCase()}`;
        // Check if tab already exists in this pane by ID
        existingTab = targetPane.tabs.find((tab) => tab.id === tabId);

        if (!existingTab) {
          newTab = {
            id: tabId,
            type: "promotion",
            title: item.name,
            closable: true,
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

  useEffect(() => {
    const syncResponsiveLayout = () => {
      const viewportWidth = window.innerWidth;
      const isLeftPanelOpen = Boolean(activePanelId);
      const isChatOpen = isChatPanelOpen;

      const jobsFloor = viewportWidth < 1100 ? 180 : 220;
      const chatFloor = viewportWidth < 1100 ? 240 : 280;
      const workspaceFloor = viewportWidth < 1100 ? 320 : viewportWidth < 1360 ? 420 : 560;

      let nextJobsWidth = isLeftPanelOpen
        ? Math.min(Math.max(jobsPanelWidth, jobsFloor), Math.min(360, Math.floor(viewportWidth * 0.3)))
        : 0;
      let nextChatWidth = isChatOpen
        ? Math.min(Math.max(chatPanelWidth, chatFloor), Math.min(420, Math.floor(viewportWidth * 0.34)))
        : 0;

      const handleCount = (isLeftPanelOpen ? 1 : 0) + (isChatOpen ? 1 : 0);
      const availableForSidePanels =
        viewportWidth - ICON_RAIL_WIDTH - handleCount * RESIZE_HANDLE_WIDTH - workspaceFloor;

      let overflow = nextJobsWidth + nextChatWidth - Math.max(0, availableForSidePanels);

      if (overflow > 0 && isChatOpen) {
        const chatShrinkCapacity = nextChatWidth - chatFloor;
        const chatShrinkAmount = Math.min(chatShrinkCapacity, overflow);
        nextChatWidth -= chatShrinkAmount;
        overflow -= chatShrinkAmount;
      }

      if (overflow > 0 && isLeftPanelOpen) {
        const jobsShrinkCapacity = nextJobsWidth - jobsFloor;
        const jobsShrinkAmount = Math.min(jobsShrinkCapacity, overflow);
        nextJobsWidth -= jobsShrinkAmount;
        overflow -= jobsShrinkAmount;
      }

      if (isLeftPanelOpen && nextJobsWidth !== jobsPanelWidth) {
        setJobsPanelWidth(nextJobsWidth);
      }

      if (isChatOpen && nextChatWidth !== chatPanelWidth) {
        setChatPanelWidth(nextChatWidth);
      }

      const workspaceAvailableWidth =
        viewportWidth -
        ICON_RAIL_WIDTH -
        handleCount * RESIZE_HANDLE_WIDTH -
        nextJobsWidth -
        nextChatWidth;

      if (workspace.mode === "split") {
        const paneFloor = workspaceAvailableWidth < 900 ? 240 : 280;
        const paneCeiling = Math.max(paneFloor, workspaceAvailableWidth - paneFloor - RESIZE_HANDLE_WIDTH);
        const clampedPaneWidth = Math.min(Math.max(workspacePaneAWidth, paneFloor), paneCeiling);

        if (clampedPaneWidth !== workspacePaneAWidth) {
          setWorkspacePaneAWidth(clampedPaneWidth);
        }
      }
    };

    syncResponsiveLayout();
    window.addEventListener("resize", syncResponsiveLayout);

    return () => window.removeEventListener("resize", syncResponsiveLayout);
  }, [activePanelId, chatPanelWidth, isChatPanelOpen, jobsPanelWidth, workspace.mode, workspacePaneAWidth]);

  const requiredActionsCount = visibleRequiredActions.length;
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

  // Render tab content - shared across all panes
  const renderTabContent = (tab: WorkspaceTab | undefined) => {
    if (!tab) return null;

    // Get job spec if needed
    const currentJobName = tab.type === "job" ? tab.jobName : null;
    const currentJobSpec = tab.type === "job"
      ? ((tab.payload as WorkspaceJobPayload | undefined) ?? (currentJobName ? mockJobSpecs[currentJobName] : null))
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
          /* Create Job Form */
          <CreateJobForm
            draftData={jobDraft}
            onDraftDataChange={setJobDraft}
            onSubmit={(jobData) => {
              // Log the job data to console for now
              console.log("New job created:", jobData);
              
              // In a real app, you would send this to the backend API here
              // Example: 
              // await api.createJob(jobData)
              
              // Show a success toast/notification
              // You can add a toast notification here using a toast library
              
              // Reset the form state is handled by CreateJobForm
            }}
            onCancel={() => handleCloseTabInPane(tab.id, "primary")}
          />
        ) : tab.type === "job" && currentJobSpec ? (
          /* Job Workspace View */
          <div className="mx-auto max-w-[1600px] px-6 py-8">
            {(() => {
              const activeJobDetailTab = jobDetailTabById[tab.id] ?? "overview";
              const isAttentionJob = currentJobSpec.status === "Needs Attention";
              const relatedRunRecords = dashboardRuns.recentRuns.filter((run) => run.jobName === currentJobSpec.name);

              return (
                <div className="space-y-6">
              {/* Job Header */}
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

              {/* Tabs */}
              <div className="border-b border-gray-200">
                <div className="flex gap-8">
                  <button
                    onClick={() => setJobDetailTabById((prev) => ({ ...prev, [tab.id]: "overview" }))}
                    className={`px-0 py-3 text-sm font-medium border-b-2 transition ${
                      activeJobDetailTab === "overview"
                        ? "text-gray-900 border-[#ed0923]"
                        : "text-gray-600 border-transparent hover:text-gray-900"
                    }`}
                  >
                    Overview
                  </button>
                  <button
                    onClick={() => setJobDetailTabById((prev) => ({ ...prev, [tab.id]: "runs" }))}
                    className={`px-0 py-3 text-sm font-medium border-b-2 transition ${
                      activeJobDetailTab === "runs"
                        ? "text-gray-900 border-[#ed0923]"
                        : "text-gray-600 border-transparent hover:text-gray-900"
                    }`}
                  >
                    Runs
                  </button>
                  <button
                    onClick={() => setJobDetailTabById((prev) => ({ ...prev, [tab.id]: "preview" }))}
                    className={`px-0 py-3 text-sm font-medium border-b-2 transition ${
                      activeJobDetailTab === "preview"
                        ? "text-gray-900 border-[#ed0923]"
                        : "text-gray-600 border-transparent hover:text-gray-900"
                    }`}
                  >
                    Preview
                  </button>
                  <button
                    onClick={() => setJobDetailTabById((prev) => ({ ...prev, [tab.id]: "settings" }))}
                    className={`px-0 py-3 text-sm font-medium border-b-2 transition ${
                      activeJobDetailTab === "settings"
                        ? "text-gray-900 border-[#ed0923]"
                        : "text-gray-600 border-transparent hover:text-gray-900"
                    }`}
                  >
                    Settings
                  </button>
                </div>
              </div>

              {activeJobDetailTab === "overview" && (
                <div className="rounded-xl border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Job Configuration</h2>
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
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

              {activeJobDetailTab === "runs" && (
                <div className="rounded-xl border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Run History</h2>
                  <div className="space-y-3">
                    {relatedRunRecords.length > 0 ? (
                      relatedRunRecords.map((run) => (
                        <div key={run.id} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium text-gray-900">{run.jobName}</p>
                              <p className="text-xs text-gray-500 mt-1">
                                Scheduled {formatScheduledTime(run.scheduledTime)}
                              </p>
                            </div>
                            <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${getRunStatusColor(run.status)}`}>
                              {run.status === "completed" ? "Completed" : run.status === "failed" ? "Failed" : run.status}
                            </span>
                          </div>
                          {run.completedTime && (
                            <p className="mt-3 text-xs text-gray-500">
                              Last update: {formatRunTime(run.completedTime)}
                            </p>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4 text-sm text-gray-500">
                        No recent runs were found for this job.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeJobDetailTab === "preview" && (
                <div className="rounded-xl border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Execution Preview</h2>
                  <div className="space-y-4">
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <p className="text-sm font-medium text-gray-900">What this job is expected to produce</p>
                      <ul className="mt-3 space-y-2">
                        {currentJobSpec.outputs.map((output, idx) => (
                          <li key={idx} className="text-sm text-gray-700 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-500" />
                            {output}
                          </li>
                        ))}
                      </ul>
                    </div>
                    {isAttentionJob && (
                      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                        <p className="text-sm font-semibold text-red-900">Attention needed before the next run</p>
                        <p className="mt-2 text-sm text-red-800">
                          Review the latest failed run, confirm the inputs are still valid, and update any settings before retrying.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeJobDetailTab === "settings" && (
                <div className="rounded-xl border border-gray-200 bg-white p-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-4">Job Settings</h2>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Schedule</p>
                      <p className="mt-2 text-sm text-gray-900">{currentJobSpec.schedule}</p>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Status</p>
                      <p className="mt-2 text-sm text-gray-900">{currentJobSpec.status}</p>
                    </div>
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 md:col-span-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Owner Guidance</p>
                      <p className="mt-2 text-sm text-gray-700">
                        Settings are view-only in this demo. Use this tab to review scheduling and operational context before making changes in a future connected workflow.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
              );
            })()}
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
                  <div className="border-t border-gray-200 pt-6 flex flex-wrap gap-3">
                    {tab.payload.state === "pending" && (
                      <>
                        <button
                          onClick={() => handleResolveRequiredAction(tab.payload.id, tab.title, tab.id)}
                          className="flex-1 min-w-[150px] px-4 py-2 bg-[#ed0923] text-white rounded-lg font-medium hover:bg-[#d10820] transition"
                        >
                          Resolve Action
                        </button>
                        <button
                          onClick={() => handleCloseTabInPane(tab.id, "primary")}
                          className="flex-1 min-w-[150px] px-4 py-2 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition"
                        >
                          Defer
                        </button>
                      </>
                    )}

                    {tab.payload.state === "failed" && (
                      <>
                        <button
                          onClick={() =>
                            setDismissedActionIds((prev) =>
                              prev.includes(tab.payload.id) ? prev : [...prev, tab.payload.id]
                            )
                          }
                          className="flex-1 min-w-[150px] px-4 py-2 border border-red-300 text-red-700 rounded-lg font-medium hover:bg-red-50 transition"
                        >
                          Dismiss
                        </button>
                        <button
                          onClick={() => handleCloseTabInPane(tab.id, "primary")}
                          className="flex-1 min-w-[150px] px-4 py-2 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition"
                        >
                          Close
                        </button>
                      </>
                    )}

                    {tab.payload.state === "success" && (
                      <button
                        onClick={() => handleCloseTabInPane(tab.id, "primary")}
                        className="flex-1 min-w-[150px] px-4 py-2 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition"
                      >
                        Close
                      </button>
                    )}
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
                    <span className="text-sm text-gray-600">
                      {currentPromotion.status === "pending_promotion"
                        ? "Awaiting admin review"
                        : currentPromotion.status === "approved"
                          ? "Ready for admin promotion"
                          : "Promotion complete"}
                    </span>
                  </div>
                </div>
              )}

              {/* Promotion Details Card */}
              <div className="rounded-xl border border-gray-200 bg-white p-8 max-w-3xl">
                <div className="space-y-6">
                  {currentPromotion.status === "pending_promotion" && (
                    <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4">
                      <p className="text-sm font-semibold text-yellow-900">Awaiting admin review</p>
                      <p className="mt-1 text-sm text-yellow-800">
                        Your submission is in the approval queue. No action is needed from you right now.
                      </p>
                    </div>
                  )}

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

                  {currentPromotion.status === "pending_promotion" && (
                    <div className="border-t border-gray-200 pt-6">
                      <h3 className="text-sm font-semibold text-gray-900 mb-3">What happens next</h3>
                      <div className="space-y-3">
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 h-2.5 w-2.5 rounded-full bg-green-500" />
                          <div>
                            <p className="text-sm font-medium text-gray-900">Submitted</p>
                            <p className="text-xs text-gray-500">Your form has been created and sent to the approval queue.</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 h-2.5 w-2.5 rounded-full bg-yellow-500" />
                          <div>
                            <p className="text-sm font-medium text-gray-900">Admin review pending</p>
                            <p className="text-xs text-gray-500">An admin needs to review and promote this job before it becomes active.</p>
                          </div>
                        </div>
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 h-2.5 w-2.5 rounded-full bg-gray-300" />
                          <div>
                            <p className="text-sm font-medium text-gray-900">Activation</p>
                            <p className="text-xs text-gray-500">After approval, the job will appear in Active Jobs, Runs, and Calendar.</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

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

                  {(currentPromotion.scheduleSummary || currentPromotion.requestedRunDates?.length) && (
                    <div className="border-t border-gray-200 pt-6">
                      <h3 className="text-sm font-semibold text-gray-900 mb-3">Requested Schedule</h3>
                      {currentPromotion.scheduleSummary && (
                        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">
                          {currentPromotion.scheduleSummary}
                        </div>
                      )}
                      {currentPromotion.requestedRunDates && currentPromotion.requestedRunDates.length > 0 && (
                        <div className="mt-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Next requested runs</p>
                          <div className="mt-2 space-y-2">
                            {currentPromotion.requestedRunDates.map((runDate) => (
                              <div key={runDate} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700">
                                {runDate}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

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
                      <div>Submitted: {formatPromotionDate(currentPromotion.createdAt)}</div>
                      {currentPromotion.lastModified && <div>Last Updated: {formatPromotionDate(currentPromotion.lastModified)}</div>}
                    </div>
                  </div>

                  {currentPromotion.status === "pending_promotion" && (
                    <div className="border-t border-gray-200 pt-6">
                      <h3 className="text-sm font-semibold text-gray-900 mb-3">Approval Notes</h3>
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700">
                        This job is waiting for admin review before it can be promoted into an active scheduled job.
                      </div>
                    </div>
                  )}

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
                    {currentPromotion.status === "pending_promotion" && (
                      <button
                        onClick={() => handleWithdrawSubmission(currentPromotion.id, currentPromotion.name)}
                        className="flex-1 px-4 py-2 border border-red-300 text-red-700 rounded-lg font-medium hover:bg-red-50 transition"
                      >
                        Withdraw Submission
                      </button>
                    )}
                    {currentPromotion.status !== "rejected" && (
                      <button
                        onClick={() => setActivePanelId("promotions-edits")}
                        className="flex-1 px-4 py-2 border border-gray-300 text-gray-900 rounded-lg font-medium hover:bg-gray-50 transition"
                      >
                        Back to Pending Promotions
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
                <p className="mt-2 text-sm text-gray-600">Jobs currently running or scheduled</p>
              </div>

              <div className="rounded-xl border border-gray-200 bg-white p-6">
                <div className="space-y-4">
                  {dashboardJobs
                    .filter((job) => job.status === "Running" || job.status === "Healthy")
                    .map((job) => (
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
                  {dashboardJobs.filter((job) => job.status === "Running" || job.status === "Healthy").length === 0 && (
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
                  {pendingPromotionsState.map((promotion) => (
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
                              { type: "promotion", name: promotion.name, id: promotion.id, payload: promotion },
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
                  {pendingPromotionsState.length === 0 && (
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
                  {dashboardRuns.recentRuns
                    .filter((run) => run.status === "failed")
                    .map((run) => (
                      <div key={run.id} className="flex items-start justify-between p-4 border border-red-200 bg-red-50 rounded-lg">
                        <div className="flex-1">
                          <p className="font-medium text-gray-900">{run.jobName}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-xs bg-red-100 text-red-700 px-2 py-1 rounded">{run.jobType}</span>
                            <span className="text-xs text-gray-500">
                              Failed {formatRunTime(run.scheduledTime)}
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
                  {dashboardRuns.recentRuns.filter((run) => run.status === "failed").length === 0 && (
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
                          className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                            job.status === "Healthy"
                              ? "bg-green-100 text-green-700"
                              : job.status === "Running"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-red-100 text-red-700"
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
                {kpis.map((kpi, idx) => {
                  // Map KPI label to dashboard tab type
                  const getTabType = () => {
                    if (kpi.label === "My Active Jobs") return "active-jobs";
                    if (kpi.label === "Pending Approvals") return "pending-approvals";
                    if (kpi.label === "Failed Runs (24h)") return "failed-runs";
                    if (kpi.label === "Saved Jobs") return "saved-jobs";
                    return null;
                  };
                  
                  const tabType = getTabType();
                  
                  return (
                    <button
                      key={idx}
                      onClick={() => {
                        if (tabType) {
                          handleOpenTabInPane({ type: tabType, name: kpi.label, id: tabType }, "primary");
                        }
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
                      <p className="text-2xl font-bold text-gray-900">1</p>
                      <p className="text-xs text-gray-600">Urgent action</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <PlayCircle className="h-5 w-5 text-blue-500" />
                    <div>
                      <p className="text-2xl font-bold text-gray-900">2</p>
                      <p className="text-xs text-gray-600">Running jobs</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Sparkles className="h-5 w-5 text-amber-500" />
                    <div>
                      <p className="text-2xl font-bold text-gray-900">3</p>
                      <p className="text-xs text-gray-600">Drafts pending</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <div>
                      <p className="text-2xl font-bold text-gray-900">2</p>
                      <p className="text-xs text-gray-600">Promotions ready</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Dashboard Grid */}
              <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
                {/* Recent Jobs */}
                <div className="rounded-lg border border-gray-200 bg-white p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Recent Jobs</h3>
                  <div className="space-y-2">
                    {recentJobs.slice(0, 3).map((job) => (
                      <div key={job.name} className="p-2 bg-gray-50 rounded text-left hover:bg-gray-100 cursor-pointer transition text-xs">
                        <p className="font-medium text-gray-900 truncate">{job.name}</p>
                        <span className={`inline-block mt-1 rounded px-2 py-0.5 text-[9px] font-semibold ${job.status === "Healthy" ? "bg-green-100 text-green-700" : job.status === "Running" ? "bg-blue-100 text-blue-700" : "bg-red-100 text-red-700"}`}>
                          {job.status}
                        </span>
                      </div>
                    ))}
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
                      <span className="font-bold text-blue-700">2</span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-yellow-50 rounded">
                      <span className="text-gray-700">Pending</span>
                      <span className="font-bold text-yellow-700">1</span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-red-50 rounded">
                      <span className="text-gray-700">Needs Revision</span>
                      <span className="font-bold text-red-700">1</span>
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
        const jobTypeLists = {
          PowerPoint: dashboardJobs.filter(j => j.type === "PowerPoint").length,
          Excel: dashboardJobs.filter(j => j.type === "Excel").length,
          SQL: dashboardJobs.filter(j => j.type === "SQL").length,
        };
        const jobStatusLists = {
          Healthy: dashboardJobs.filter(j => j.status === "Healthy").length,
          Running: dashboardJobs.filter(j => j.status === "Running").length,
          "Needs Attention": dashboardJobs.filter(j => j.status === "Needs Attention").length,
        };
        return (
          <div className="p-4 space-y-3 flex flex-col h-full">
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
                {["all", "PowerPoint", "Excel", "SQL"].map((filterOption) => (
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
                {["Healthy", "Running", "Needs Attention"].map((filterOption) => (
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

            {/* Current Jobs Section - Always visible and prioritized */}
            <div className="border-t border-gray-200 pt-3 mt-2">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs font-bold text-gray-900 uppercase tracking-wide">
                  My Current Jobs ({filteredAndSortedJobs.length})
                </h3>
                <button
                  onClick={() => handleOpenTabInPane({ type: "create-job", id: "create-job", name: "Create Job" }, "primary")}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#ed0923] text-white rounded-md text-xs font-medium hover:bg-[#d10820] transition"
                  title="Create a new job"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Create
                </button>
              </div>
              <div className="flex-1 overflow-y-auto space-y-1.5">
                {filteredAndSortedJobs.length > 0 ? (
                  filteredAndSortedJobs.map((job) => (
                    <button
                      key={job.id}
                      draggable
                      onDragStart={(e) => handleJobDragStart(e, job.name)}
                      onClick={() =>
                        handleOpenTabInPane(
                          { type: "job", name: job.name, id: job.id, payload: job.payload },
                          "primary"
                        )
                      }
                      className={`w-full p-3 rounded-lg transition text-left cursor-move ${
                        activeJobName === job.name
                          ? "bg-[#ed0923]/10 border border-[#ed0923]"
                          : "bg-gray-50 hover:bg-gray-100 border border-transparent"
                      }`}
                    >
                      <p className="text-sm font-medium text-gray-900">{job.name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-500">{job.type}</span>
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            job.status === "Healthy"
                              ? "bg-green-100 text-green-700"
                              : job.status === "Running"
                                ? "bg-blue-100 text-blue-700"
                                : "bg-red-100 text-red-700"
                          }`}
                        >
                          {job.status}
                        </span>
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="text-center py-8">
                    <p className="text-sm text-gray-500">No jobs match your search</p>
                  </div>
                )}
              </div>
            </div>

            {/* Drafts Section - Collapsible, expanded by default */}
            <div className="border-t border-gray-200 pt-3">
              <button
                onClick={() => setIsDraftsExpanded(!isDraftsExpanded)}
                className="w-full flex items-center justify-between hover:bg-gray-50 px-1 py-1.5 rounded transition"
              >
                <div className="flex items-center gap-2">
                  {isDraftsExpanded ? (
                    <ChevronDown className="h-4 w-4 text-gray-600" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-gray-600" />
                  )}
                  <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Drafts</h3>
                </div>
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded font-medium">
                  {draftJobs.length}
                </span>
              </button>
              {isDraftsExpanded && (
                <div className="space-y-1.5 mt-2">
                  {draftJobs.map((draft) => (
                    <button
                      key={draft.id}
                      onClick={() => handleOpenTabInPane({ type: "job", name: draft.name, id: draft.name }, "primary")}
                      className="w-full p-3 rounded-lg transition text-left bg-amber-50 hover:bg-amber-100 border border-amber-200"
                    >
                      <p className="text-sm font-medium text-gray-900">{draft.name}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className={`text-xs font-medium ${getJobTypeColor(draft.type)}`}>{draft.type}</span>
                        <span className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold bg-amber-100 text-amber-700">
                          Draft
                        </span>
                        <span className="text-xs text-gray-500">{draft.lastEdited}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Retired Jobs Section - Collapsible, collapsed by default */}
            <div className="border-t border-gray-200 pt-3">
              <button
                onClick={() => setIsRetiredJobsExpanded(!isRetiredJobsExpanded)}
                className="w-full flex items-center justify-between hover:bg-gray-50 px-1 py-1.5 rounded transition"
              >
                <div className="flex items-center gap-2">
                  {isRetiredJobsExpanded ? (
                    <ChevronDown className="h-4 w-4 text-gray-600" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-gray-600" />
                  )}
                  <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Retired Jobs</h3>
                </div>
                <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded font-medium">
                  {retiredJobs.length}
                </span>
              </button>
              {isRetiredJobsExpanded && (
                <div className="space-y-1.5 mt-2">
                  {retiredJobs.map((retired) => (
                    <button
                      key={retired.id}
                      onClick={() => handleOpenTabInPane({ type: "job", name: retired.name, id: retired.name }, "primary")}
                      className="w-full p-3 rounded-lg transition text-left bg-gray-50 hover:bg-gray-100 border border-gray-300 opacity-75"
                    >
                      <p className="text-sm font-medium text-gray-900">{retired.name}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-xs font-medium text-gray-600">{retired.type}</span>
                        <span className="inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold bg-gray-200 text-gray-700">
                          Retired
                        </span>
                        <span className="text-xs text-gray-500">{retired.retiredDate}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      case "runs":
        return (
          <div className="p-4 space-y-3 flex flex-col h-full overflow-y-auto">
            {/* Upcoming Runs */}
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Upcoming Runs</h3>
              <div className="space-y-1.5">
                {dashboardRuns.upcomingRuns.map((run) => (
                  <div key={run.id} className="p-2 rounded-lg bg-gray-50 border border-gray-200 text-left hover:bg-gray-100 transition cursor-pointer">
                    <p className="text-sm font-medium text-gray-900 truncate">{run.jobName}</p>
                    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                      <span className={`inline-flex text-[10px] font-semibold rounded px-1.5 py-0.5 ${getJobTypeColor(run.jobType)}`}>
                        {run.jobType}
                      </span>
                      <span className="text-xs text-gray-500">{formatScheduledTime(run.scheduledTime)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Divider */}
            <div className="border-t border-gray-200" />

            {/* Recent Runs */}
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Recent Runs</h3>
              <div className="space-y-1.5">
                {dashboardRuns.recentRuns.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => handleOpenTabInPane({ type: "job", name: run.jobName, id: run.jobName }, "primary")}
                    className="w-full p-2 rounded-lg bg-gray-50 border border-gray-200 text-left hover:bg-gray-100 transition"
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
                      <span className="text-xs text-gray-500 whitespace-nowrap">{formatRunTime(run.completedTime || new Date())}</span>
                    </div>
                  </button>
                ))}
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
        const urgentActions = visibleRequiredActions.filter((a) => a.urgency === "urgent");
        const highPriorityActions = visibleRequiredActions.filter((a) => a.urgency === "high");
        const otherActions = visibleRequiredActions.filter((a) => a.urgency === "other");

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
                            <p className="min-w-0 text-sm text-gray-700 font-mono bg-white p-2 rounded border border-gray-200 whitespace-normal break-all">
                              {action.jobName}
                            </p>
                          </div>

                          {/* Action Buttons */}
                          <div className="flex flex-wrap gap-2 pt-2">
                            <button
                              onClick={() =>
                                handleOpenTabInPane(
                                  { type: "required-action", id: action.id, name: action.subject },
                                  "primary"
                                )
                              }
                              className="min-w-[120px] flex-1 px-3 py-2 rounded text-sm font-medium bg-[#ed0923] text-white hover:bg-[#d10820] transition"
                            >
                              Open
                            </button>
                            {action.state !== "pending" && (
                              <button
                                onClick={() =>
                                  setDismissedActionIds((prev) =>
                                    prev.includes(action.id) ? prev : [...prev, action.id]
                                  )
                                }
                                className="min-w-[120px] flex-1 px-3 py-2 rounded text-sm font-medium bg-gray-200 text-gray-900 hover:bg-gray-300 transition"
                              >
                                Dismiss
                              </button>
                            )}
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
            {requiredActionSuccessMessage && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">
                {requiredActionSuccessMessage}
              </div>
            )}
            <div className="space-y-3">
              {urgentActions.length > 0 && renderActionSection("Urgent Actions", urgentActions, false)}
              {highPriorityActions.length > 0 && renderActionSection("High Priority", highPriorityActions, false)}
              {otherActions.length > 0 && renderActionSection("Other Actions", otherActions, false)}
              {visibleRequiredActions.length === 0 && (
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

            <div className="min-w-0">
              <input
                type="text"
                placeholder="Search forms or templates..."
                value={templateSearch}
                onChange={(e) => setTemplateSearch(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
              />
            </div>

            <div className="space-y-4">
              <div>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                  <h3 className="min-w-0 text-xs font-bold uppercase tracking-wide text-gray-600">Saved Templates</h3>
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
                    className="shrink-0 text-xs font-medium text-[#ed0923] hover:text-[#d10820]"
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
                        className="w-full min-w-0 rounded-lg border border-gray-200 bg-white p-3 text-left hover:border-[#ed0923] hover:bg-red-50 transition"
                      >
                        <div className="flex min-w-0 items-start gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium leading-tight text-gray-900 [overflow-wrap:anywhere]">
                              {template.name}
                            </p>
                            <p className="mt-1 text-xs text-gray-500">{template.type} saved template</p>
                          </div>
                          <span className="shrink-0 self-start rounded-full bg-gray-100 px-2 py-1 text-[10px] font-semibold text-gray-700">
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
                <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                  <h3 className="min-w-0 text-xs font-bold uppercase tracking-wide text-gray-600">Pre-Built Forms</h3>
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
                    className="shrink-0 text-xs font-medium text-[#ed0923] hover:text-[#d10820]"
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
                        className="w-full min-w-0 rounded-lg border border-gray-200 bg-gray-50 p-3 text-left hover:border-[#ed0923] hover:bg-red-50 transition"
                      >
                        <p className="text-sm font-medium leading-tight text-gray-900 [overflow-wrap:anywhere]">{form.name}</p>
                        <div className="mt-2 flex flex-wrap items-start gap-2">
                          <span className="inline-flex shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700">
                            {form.category}
                          </span>
                          <span className="min-w-0 flex-1 text-xs text-gray-500 [overflow-wrap:anywhere]">{form.description}</span>
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
              <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 sticky top-0 bg-white/95 z-10 py-1">
                <h3 className="min-w-0 text-xs font-bold text-gray-700 uppercase tracking-wide">Ready for Promotion</h3>
                <span className="shrink-0 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-medium">{mockReadyForPromotion.length}</span>
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
                      <p className="text-sm font-medium leading-tight text-gray-900 [overflow-wrap:anywhere]">{item.name}</p>
                      <div className="mt-1 flex flex-wrap items-start gap-1.5">
                        <span className={`text-xs font-medium [overflow-wrap:anywhere] ${getPromotionTypeColor(item.type)}`}>{item.type}</span>
                        <span className="shrink-0 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">{item.currentEnvironment}</span>
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
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 sticky top-12 bg-white/95 z-10 py-1">
                  <h3 className="min-w-0 text-xs font-bold text-gray-700 uppercase tracking-wide">Pending Promotions</h3>
                  <span className="shrink-0 text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded font-medium">{allPendingPromotions.length}</span>
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
                      <p className="text-sm font-medium leading-tight text-gray-900 [overflow-wrap:anywhere]">{item.name}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5">
                        <span className={`text-xs font-medium [overflow-wrap:anywhere] ${getPromotionTypeColor(item.type)}`}>{item.type}</span>
                        <span className="shrink-0 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">{item.currentEnvironment}</span>
                        <span className="shrink-0 text-xs text-gray-400">→</span>
                        <span className="shrink-0 text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded">{item.targetEnvironment}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          onClick={() => handleOpenTabInPane({ type: "promotion", id: item.id, name: item.name, payload: item }, "primary")}
                          className="px-2 py-1 text-xs font-medium rounded border border-gray-300 text-gray-700 hover:bg-gray-100 transition"
                        >
                          View
                        </button>
                        <button
                          onClick={() => handleWithdrawSubmission(item.id, item.name)}
                          className="px-2 py-1 text-xs font-medium rounded border border-red-300 text-red-700 hover:bg-red-50 transition"
                        >
                          Withdraw
                        </button>
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
        <main className="flex-1 min-w-0 flex flex-col overflow-hidden min-h-0">
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
                  <div className="flex-1 min-h-0 overflow-hidden p-4">
                    <div className="h-full flex flex-col rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
                      {/* Form Content - Scrollable area inside panel */}
                      <div 
                        className={`flex-1 min-h-0 overflow-y-auto transition-all relative ${
                          isDraggingOverWorkspace 
                            ? isDraggingOverSplitZone === "left" 
                              ? 'bg-purple-50'
                              : isDraggingOverSplitZone === "right"
                              ? 'bg-purple-50'
                              : 'bg-blue-50'
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
                        
                        {/* Render form without footer */}
                        <CreateJobForm
                          hideFooter={true}
                          draftData={jobDraft}
                          onDraftDataChange={setJobDraft}
                          onSubmit={(jobData) => {
                            console.log("New job created:", jobData);
                          }}
                          onCancel={() => handleCloseTabInPane(activeTab.id, "primary")}
                        />
                      </div>

                      {/* Form Panel Footer - Inside the bordered panel */}
                      <div className="flex-shrink-0 border-t border-gray-200 bg-gray-50 px-4 py-4 flex gap-3">
                        <div className="w-full flex gap-3">
                          <Button
                            variant="outline"
                            onClick={() => handleCloseTabInPane(activeTab.id, "primary")}
                            className="flex-1"
                          >
                            Cancel
                          </Button>
                          <Button
                            onClick={() => {
                              // Get current form data from jobDraft
                              const currentTab = workspace.primary.tabs.find(t => t.id === activeTab.id);
                              if (currentTab && jobDraft.job_type) {
                                const payload: any = {
                                  universal: {
                                    job_name: jobDraft.job_name || "",
                                    description: jobDraft.description || "",
                                    owner: jobDraft.owner || "",
                                    environment: jobDraft.environment || "dev",
                                    schedule: jobDraft.schedule || "",
                                    approval_required: jobDraft.approval_required || false,
                                    tags: jobDraft.tags || [],
                                    run_type: jobDraft.run_type || "manual",
                                  },
                                  job_type: jobDraft.job_type,
                                  job_details: {},
                                };
                                
                                // Map type-specific fields based on job type
                                if (jobDraft.job_type === "Airflow") {
                                  payload.job_details = {
                                    dag_name: jobDraft.dag_name || "",
                                    tasks: jobDraft.tasks || [],
                                    dependencies_between_tasks: jobDraft.dependencies_between_tasks || "",
                                    scripts_sql: jobDraft.scripts_sql || "",
                                    data_sources: jobDraft.data_sources || "",
                                    data_destinations: jobDraft.data_destinations || "",
                                    retry_policy: jobDraft.retry_policy || "",
                                    execution_timeout: jobDraft.execution_timeout || "",
                                  };
                                } else if (jobDraft.job_type === "Excel") {
                                  payload.job_details = {
                                    input_data_sources: jobDraft.input_data_sources || "",
                                    transformations: jobDraft.transformations || "",
                                    filters: jobDraft.filters || "",
                                    pivot_tables: jobDraft.pivot_tables || false,
                                    formulas: jobDraft.formulas || "",
                                    output_file_name: jobDraft.output_file_name || "",
                                    file_location: jobDraft.file_location || "",
                                  };
                                } else if (jobDraft.job_type === "PowerPoint") {
                                  payload.job_details = {
                                    data_source: jobDraft.data_source || "",
                                    slide_template: jobDraft.slide_template || "",
                                    metrics_to_include: jobDraft.metrics_to_include || "",
                                    charts: jobDraft.charts || "",
                                    text_summary_placeholder: jobDraft.text_summary || "[AI will generate text summary here]",
                                    branding_theme: jobDraft.branding_theme || "",
                                    output_location: jobDraft.output_location || "",
                                  };
                                }
                                
                                console.log("New job created:", payload);
                                // Reset and close
                                setJobDraft({});
                                handleCloseTabInPane(activeTab.id, "primary");
                              }
                            }}
                            className="flex-1 bg-[#ed0923] hover:bg-[#d10820] text-white"
                          >
                            Create Job
                          </Button>
                        </div>
                      </div>
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
                          <div className="bg-white rounded border border-gray-200 p-3 space-y-1">
                            {getConsoleLogs().map((log, idx) => (
                              <div key={idx} className="text-gray-700 text-xs">
                                <span className="text-gray-500">{log.time}</span> <span className="text-gray-800">{log.message}</span>
                              </div>
                            ))}
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
                          <div className="bg-white rounded border border-gray-200 p-3 space-y-1">
                            {getConsoleLogs().map((log, idx) => (
                              <div key={idx} className="text-gray-700 text-xs">
                                <span className="text-gray-500">{log.time}</span> <span className="text-gray-800">{log.message}</span>
                              </div>
                            ))}
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
                setJobDraft({});
              }}
              onFieldsExtracted={(fields) => setJobDraft((prev) => ({ ...prev, ...fields }))}
              currentDraftData={jobDraft}
              onConsoleEvent={emitConsoleEvent}
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
