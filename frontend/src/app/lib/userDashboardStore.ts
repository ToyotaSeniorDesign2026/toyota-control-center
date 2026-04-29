import { mockMyJobs, type Job } from "../pages/resourcesData";
import type { PromotionResource } from "../pages/promotionsData";

export type UserFormType = "Excel" | "SQL" | "PowerPoint" | "Custom";

export type SavedTemplateRecord = {
  id: string;
  name: string;
  type: UserFormType;
  lastEdited: string;
  progress: string;
  route: string;
  draft: Record<string, unknown>;
};

export type DraftFormRecord = {
  id: string;
  jobName: string;
  type: UserFormType;
  lastEdited: string;
  progress: string;
  route: string;
  draft: Record<string, unknown>;
};

export type UserCalendarEvent = {
  id: string;
  jobId: string;
  title: string;
  date: string;
  time: string;
  kind: "past" | "scheduled";
  jobType: Job["type"];
};

const SAVED_TEMPLATES_KEY = "toyota_user_saved_templates";
const DRAFT_FORMS_KEY = "toyota_user_draft_forms";
const CREATED_JOBS_KEY = "toyota_user_created_jobs";
const DASHBOARD_STORE_EVENT = "toyota-user-dashboard-store-updated";

const defaultSavedTemplates: SavedTemplateRecord[] = [
  {
    id: "sf-001",
    name: "q2_dealer_scorecard",
    type: "SQL",
    lastEdited: "Mar 3, 2026 11:20 AM",
    progress: "60%",
    route: "/sql-job",
    draft: {
      jobName: "q2_dealer_scorecard",
      description: "Quarterly dealer scorecard and KPI ranking output.",
      owner: "dealer.analytics@toyota.com",
      reportTemplate: "dealer_performance",
      dateRange: "90",
      regionFilter: "all",
      departmentFilter: "all",
      minAmount: "5000",
      outputDestination: "email",
      emailRecipients: "dealer.analytics@toyota.com",
      dataSensitivity: "internal",
    },
  },
  {
    id: "sf-002",
    name: "monthly_exec_finance_deck",
    type: "PowerPoint",
    lastEdited: "Mar 2, 2026 04:05 PM",
    progress: "45%",
    route: "/powerpoint",
    draft: {
      jobName: "monthly_exec_finance_deck",
      description: "Executive finance summary with revenue and margin charts.",
      owner: "finance.ops@toyota.com",
      presentationType: "executive_dashboard",
      dataSource: "financial_database",
      includeTables: true,
      includeCharts: true,
      includeImages: false,
      outputFormat: "pptx",
      emailRecipients: "finance.ops@toyota.com",
      dataSensitivity: "internal",
    },
  },
  {
    id: "sf-003",
    name: "warranty_claims_monthly_export",
    type: "Excel",
    lastEdited: "Mar 1, 2026 09:42 AM",
    progress: "80%",
    route: "/excel-report",
    draft: {
      jobName: "warranty_claims_monthly_export",
      description: "Monthly warranty claims export with trend charts.",
      owner: "quality.ops@toyota.com",
      scheduleType: "monthly",
      scheduleDay: "1",
      scheduleTime: "09:00",
      outputFormat: "xlsx",
      emailRecipients: "quality.ops@toyota.com",
      includeCharts: true,
      dataSensitivity: "internal",
    },
  },
];

const defaultDraftForms: DraftFormRecord[] = [
  {
    id: "draft-001",
    jobName: "dealer_scorecard_q2",
    type: "SQL",
    lastEdited: "Mar 31, 2026 10:15 AM",
    progress: "60%",
    route: "/sql-job",
    draft: {
      jobName: "dealer_scorecard_q2",
      description: "Quarterly dealer scorecard with regional KPI rollups.",
      owner: "dealer.analytics@toyota.com",
      reportTemplate: "dealer_performance",
      dateRange: "90",
      regionFilter: "all",
      departmentFilter: "all",
      minAmount: "5000",
      outputDestination: "email",
      emailRecipients: "dealer.analytics@toyota.com",
      dataSensitivity: "internal",
    },
  },
];

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readRecords<T>(key: string, fallback: T[]): T[] {
  if (!canUseStorage()) return fallback;
  const rawValue = window.localStorage.getItem(key);
  if (!rawValue) return fallback;

  try {
    const parsed = JSON.parse(rawValue) as T[];
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function writeRecords<T>(key: string, value: T[]) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

function notifyDashboardStoreChanged() {
  if (!canUseStorage()) return;
  window.dispatchEvent(new CustomEvent(DASHBOARD_STORE_EVENT));
}

function createId(prefix: string) {
  return `${prefix}-${Date.now()}`;
}

function formatTimestamp(date = new Date()) {
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function toDateKey(date: Date) {
  const y = date.getFullYear();
  const m = `${date.getMonth() + 1}`.padStart(2, "0");
  const d = `${date.getDate()}`.padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function clampDay(year: number, month: number, desiredDay: number) {
  const maxDay = new Date(year, month + 1, 0).getDate();
  return Math.min(Math.max(desiredDay, 1), maxDay);
}

function parseTimeParts(scheduleTime?: string) {
  const [hoursString = "9", minutesString = "00"] = (scheduleTime || "09:00").split(":");
  const hours = Math.min(23, Math.max(0, Number.parseInt(hoursString, 10) || 9));
  const minutes = Math.min(59, Math.max(0, Number.parseInt(minutesString, 10) || 0));
  return { hours, minutes };
}

function setTime(date: Date, scheduleTime?: string) {
  const next = new Date(date);
  const { hours, minutes } = parseTimeParts(scheduleTime);
  next.setHours(hours, minutes, 0, 0);
  return next;
}

function formatEventTime(date: Date) {
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function buildCalendarEvent(job: Job, when: Date, kind: "past" | "scheduled"): UserCalendarEvent {
  return {
    id: `${job.id}-${kind}-${toDateKey(when)}-${formatEventTime(when)}`,
    jobId: job.id,
    title: job.name,
    date: toDateKey(when),
    time: formatEventTime(when),
    kind,
    jobType: job.type,
  };
}

function formatRequestedRunDate(date: Date) {
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function parseScheduleStartDate(job: Job) {
  const raw = typeof job.scheduleStartDate === "string" && job.scheduleStartDate ? job.scheduleStartDate : job.createdAt;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? new Date(job.createdAt) : parsed;
}

function parseScheduleEndDate(job: Job) {
  if (typeof job.scheduleEndDate !== "string" || !job.scheduleEndDate) return null;
  const parsed = new Date(job.scheduleEndDate);
  if (Number.isNaN(parsed.getTime())) return null;
  parsed.setHours(23, 59, 59, 999);
  return parsed;
}

function parseMaxRuns(job: Job) {
  const value = Number.parseInt(job.scheduleMaxRuns || "", 10);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function getActiveWeekdays(job: Job) {
  if (Array.isArray(job.scheduleDays) && job.scheduleDays.length > 0) {
    return job.scheduleDays
      .map((day) => Number.parseInt(day, 10))
      .filter((day) => Number.isInteger(day) && day >= 0 && day <= 6);
  }

  const fallbackDay = Number.parseInt(job.scheduleDay || "1", 10);
  return Number.isInteger(fallbackDay) ? [Math.min(6, Math.max(0, fallbackDay))] : [1];
}

function withinScheduleBounds(date: Date, startDate: Date, endDate: Date | null) {
  return date >= startDate && (!endDate || date <= endDate);
}

function deriveScheduledOccurrences(job: Job, now = new Date()) {
  if (!job.scheduleType || job.scheduleType === "on-demand") return [];

  const startDate = setTime(parseScheduleStartDate(job), job.scheduleTime);
  const endDate = parseScheduleEndDate(job);
  const maxRuns = parseMaxRuns(job);
  const events: UserCalendarEvent[] = [];

  if (job.scheduleType === "daily") {
    for (let index = 0; index < 120; index += 1) {
      const occurrence = new Date(startDate.getTime() + index * 24 * 60 * 60 * 1000);
      if (!withinScheduleBounds(occurrence, startDate, endDate)) continue;
      if (maxRuns && index >= maxRuns) break;
      events.push(buildCalendarEvent(job, occurrence, occurrence <= now ? "past" : "scheduled"));
    }
    return events;
  }

  if (job.scheduleType === "weekly") {
    const weekdays = getActiveWeekdays(job);
    let generatedRuns = 0;
    for (let index = 0; index < 180; index += 1) {
      const occurrence = new Date(startDate);
      occurrence.setDate(startDate.getDate() + index);
      occurrence.setHours(startDate.getHours(), startDate.getMinutes(), 0, 0);
      if (!weekdays.includes(occurrence.getDay())) continue;
      if (!withinScheduleBounds(occurrence, startDate, endDate)) continue;
      generatedRuns += 1;
      if (maxRuns && generatedRuns > maxRuns) break;
      events.push(buildCalendarEvent(job, occurrence, occurrence <= now ? "past" : "scheduled"));
    }
    return events;
  }

  if (job.scheduleType === "monthly") {
    const desiredDay = Number.parseInt(job.scheduleDay || "1", 10) || 1;
    let generatedRuns = 0;
    for (let index = 0; index < 24; index += 1) {
      const baseMonth = new Date(startDate.getFullYear(), startDate.getMonth() + index, 1);
      const occurrence = setTime(
        new Date(
          baseMonth.getFullYear(),
          baseMonth.getMonth(),
          clampDay(baseMonth.getFullYear(), baseMonth.getMonth(), desiredDay)
        ),
        job.scheduleTime
      );
      if (!withinScheduleBounds(occurrence, startDate, endDate)) continue;
      generatedRuns += 1;
      if (maxRuns && generatedRuns > maxRuns) break;
      events.push(buildCalendarEvent(job, occurrence, occurrence <= now ? "past" : "scheduled"));
    }
    return events;
  }

  return events;
}

function routeForType(type: UserFormType) {
  if (type === "Excel") return "/excel-report";
  if (type === "PowerPoint") return "/powerpoint";
  if (type === "Custom") return "/forms/new";
  return "/sql-job";
}

function jobTypeForForm(type: UserFormType): Job["type"] {
  if (type === "Excel") return "Excel Report";
  if (type === "PowerPoint") return "PowerPoint Deck";
  if (type === "Custom") return "Custom Job";
  return "SQL Query";
}

function sanitizeDraft(draft: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(draft).filter(([, value]) => {
      if (value === null || value === undefined) return false;
      if (typeof File !== "undefined" && value instanceof File) return false;
      return true;
    })
  );
}

function deriveName(draft: Record<string, unknown>, fallback: string) {
  const jobName = draft.jobName;
  if (typeof jobName === "string" && jobName.trim()) return jobName.trim();
  return fallback;
}

function buildProgress(draft: Record<string, unknown>) {
  const values = Object.values(draft).filter((value) => {
    if (value === null || value === undefined) return false;
    if (typeof value === "string") return value.trim().length > 0;
    if (typeof value === "boolean") return value;
    return true;
  });

  const total = Math.max(Object.keys(draft).length, 1);
  const percent = Math.min(100, Math.max(15, Math.round((values.length / total) * 100)));
  return `${percent}%`;
}

export function getSavedTemplates() {
  return readRecords<SavedTemplateRecord>(SAVED_TEMPLATES_KEY, defaultSavedTemplates);
}

export function saveTemplate(type: UserFormType, draft: Record<string, unknown>) {
  const cleanDraft = sanitizeDraft(draft);
  const name = deriveName(cleanDraft, `${type.toLowerCase()}_template`);
  const nextTemplate: SavedTemplateRecord = {
    id: createId("template"),
    name,
    type,
    lastEdited: formatTimestamp(),
    progress: buildProgress(cleanDraft),
    route: routeForType(type),
    draft: cleanDraft,
  };

  const nextTemplates = [nextTemplate, ...getSavedTemplates().filter((template) => template.name !== name)];
  writeRecords(SAVED_TEMPLATES_KEY, nextTemplates);
  notifyDashboardStoreChanged();
  return nextTemplate;
}

export function getDraftForms() {
  return readRecords<DraftFormRecord>(DRAFT_FORMS_KEY, defaultDraftForms);
}

export function getLatestDraftForm() {
  return getDraftForms()[0] ?? null;
}

export function saveDraft(type: UserFormType, draft: Record<string, unknown>) {
  const cleanDraft = sanitizeDraft(draft);
  const jobName = deriveName(cleanDraft, `${type.toLowerCase()}_draft`);
  const nextDraft: DraftFormRecord = {
    id: createId("draft"),
    jobName,
    type,
    lastEdited: formatTimestamp(),
    progress: buildProgress(cleanDraft),
    route: routeForType(type),
    draft: cleanDraft,
  };

  const nextDrafts = [nextDraft, ...getDraftForms().filter((record) => record.jobName !== jobName)];
  writeRecords(DRAFT_FORMS_KEY, nextDrafts);
  notifyDashboardStoreChanged();
  return nextDraft;
}

export function getMyJobs() {
  const createdJobs = readRecords<Job>(CREATED_JOBS_KEY, []);
  const activeCreatedJobs = createdJobs.filter((job) => job.status !== "pending");
  return [...activeCreatedJobs, ...mockMyJobs];
}

function promotionEnvironmentForType(type: UserFormType) {
  if (type === "Custom") return "Draft";
  return "Dev";
}

export function mapJobToPendingPromotionResource(job: Job): PromotionResource {
  const requestedRunDates = deriveScheduledOccurrences(job, new Date(job.createdAt))
    .filter((event) => event.kind === "scheduled")
    .slice(0, 5)
    .map((event) => formatRequestedRunDate(new Date(`${event.date}T${event.time}:00`)));

  return {
    id: job.id,
    name: job.name,
    type: job.type,
    status: "pending_promotion",
    currentEnvironment: promotionEnvironmentForType(
      job.type === "Excel Report"
        ? "Excel"
        : job.type === "PowerPoint Deck"
          ? "PowerPoint"
          : job.type === "Custom Job"
            ? "Custom"
            : "SQL"
    ),
    targetEnvironment: "Production",
    createdAt: job.createdAt,
    lastModified: job.createdAt,
    description: job.description,
    scheduleSummary: getScheduleSummary(job as unknown as Record<string, unknown>),
    requestedRunDates,
  };
}

export function getPendingPromotionResources(): PromotionResource[] {
  const createdJobs = readRecords<Job>(CREATED_JOBS_KEY, []);
  return createdJobs
    .filter((job) => job.status === "pending")
    .map(mapJobToPendingPromotionResource);
}

export function withdrawPendingSubmission(jobId: string) {
  const createdJobs = readRecords<Job>(CREATED_JOBS_KEY, []);
  const nextJobs = createdJobs.filter((job) => !(job.id === jobId && job.status === "pending"));
  writeRecords(CREATED_JOBS_KEY, nextJobs);
  notifyDashboardStoreChanged();
}

export function subscribeToUserDashboardStore(listener: () => void) {
  if (!canUseStorage()) return () => undefined;

  const handleStorageEvent = (event: Event) => {
    if (event instanceof StorageEvent) {
      if (
        event.key &&
        event.key !== CREATED_JOBS_KEY &&
        event.key !== DRAFT_FORMS_KEY &&
        event.key !== SAVED_TEMPLATES_KEY
      ) {
        return;
      }
    }

    listener();
  };

  window.addEventListener(DASHBOARD_STORE_EVENT, handleStorageEvent);
  window.addEventListener("storage", handleStorageEvent);

  return () => {
    window.removeEventListener(DASHBOARD_STORE_EVENT, handleStorageEvent);
    window.removeEventListener("storage", handleStorageEvent);
  };
}

function getScheduleSummary(draft: Record<string, unknown>) {
  const scheduleType = typeof draft.scheduleType === "string" ? draft.scheduleType : "";
  const scheduleTime = typeof draft.scheduleTime === "string" ? draft.scheduleTime : "";
  const scheduleDay = typeof draft.scheduleDay === "string" ? draft.scheduleDay : "";
  const scheduleDays = Array.isArray(draft.scheduleDays) ? draft.scheduleDays.join(", ") : "";
  const scheduleStartDate = typeof draft.scheduleStartDate === "string" ? draft.scheduleStartDate : "";
  const scheduleEndDate = typeof draft.scheduleEndDate === "string" ? draft.scheduleEndDate : "";
  const scheduleMaxRuns = typeof draft.scheduleMaxRuns === "string" ? draft.scheduleMaxRuns : "";

  if (!scheduleType || scheduleType === "on-demand") {
    return "Runs on demand";
  }

  if (scheduleType === "daily") {
    return `Runs daily${scheduleTime ? ` at ${scheduleTime}` : ""}${scheduleStartDate ? ` starting ${scheduleStartDate}` : ""}${scheduleEndDate ? ` until ${scheduleEndDate}` : ""}${scheduleMaxRuns ? ` for ${scheduleMaxRuns} runs` : ""}`;
  }

  if (scheduleType === "weekly") {
    return `Runs weekly${scheduleDays ? ` on ${scheduleDays}` : scheduleDay ? ` on day ${scheduleDay}` : ""}${scheduleTime ? ` at ${scheduleTime}` : ""}${scheduleStartDate ? ` starting ${scheduleStartDate}` : ""}${scheduleEndDate ? ` until ${scheduleEndDate}` : ""}${scheduleMaxRuns ? ` for ${scheduleMaxRuns} runs` : ""}`;
  }

  if (scheduleType === "monthly") {
    return `Runs monthly${scheduleDay ? ` on day ${scheduleDay}` : ""}${scheduleTime ? ` at ${scheduleTime}` : ""}${scheduleStartDate ? ` starting ${scheduleStartDate}` : ""}${scheduleEndDate ? ` until ${scheduleEndDate}` : ""}${scheduleMaxRuns ? ` for ${scheduleMaxRuns} runs` : ""}`;
  }

  return "Schedule configured from form";
}

export function createJobFromForm(type: UserFormType, draft: Record<string, unknown>) {
  const cleanDraft = sanitizeDraft(draft);
  const name = deriveName(cleanDraft, `${type.toLowerCase()}_job`);
  const owner = typeof cleanDraft.owner === "string" ? cleanDraft.owner.trim() : "";
  const scheduleSummary = getScheduleSummary(cleanDraft);
  const createdJob: Job = {
    id: createId("JOB"),
    name,
    type: jobTypeForForm(type),
    status: "pending",
    createdAt: new Date().toISOString(),
    environment: "Dev",
    scheduleType:
      cleanDraft.scheduleType === "daily" ||
      cleanDraft.scheduleType === "weekly" ||
      cleanDraft.scheduleType === "monthly" ||
      cleanDraft.scheduleType === "on-demand"
        ? cleanDraft.scheduleType
        : undefined,
    scheduleDay: typeof cleanDraft.scheduleDay === "string" ? cleanDraft.scheduleDay : undefined,
    scheduleTime: typeof cleanDraft.scheduleTime === "string" ? cleanDraft.scheduleTime : undefined,
    scheduleDays: Array.isArray(cleanDraft.scheduleDays)
      ? cleanDraft.scheduleDays.filter((day): day is string => typeof day === "string")
      : undefined,
    scheduleStartDate:
      typeof cleanDraft.scheduleStartDate === "string" ? cleanDraft.scheduleStartDate : undefined,
    scheduleStopCondition:
      cleanDraft.scheduleStopCondition === "never" ||
      cleanDraft.scheduleStopCondition === "on-date" ||
      cleanDraft.scheduleStopCondition === "after-runs"
        ? cleanDraft.scheduleStopCondition
        : undefined,
    scheduleEndDate:
      typeof cleanDraft.scheduleEndDate === "string" ? cleanDraft.scheduleEndDate : undefined,
    scheduleMaxRuns:
      typeof cleanDraft.scheduleMaxRuns === "string" ? cleanDraft.scheduleMaxRuns : undefined,
    description:
      typeof cleanDraft.description === "string" && cleanDraft.description.trim()
        ? cleanDraft.description
        : `${type} job created from the user form flow.`,
    logs: [
      {
        timestamp: new Date().toISOString(),
        message: scheduleSummary,
        level: "info",
      },
      ...(owner
        ? [
            {
              timestamp: new Date().toISOString(),
              message: `Job owner set to ${owner}`,
              level: "info" as const,
            },
          ]
        : []),
      {
        timestamp: new Date().toISOString(),
        message: "Job created from user form submission",
        level: "info",
      },
    ],
    policyChecks: [
      {
        name: "Form Validation",
        status: "passed",
        message: "Required fields were completed before submission.",
      },
    ],
  };

  writeRecords(CREATED_JOBS_KEY, [createdJob, ...readRecords<Job>(CREATED_JOBS_KEY, [])]);
  writeRecords(
    DRAFT_FORMS_KEY,
    getDraftForms().filter((record) => record.jobName !== name)
  );
  notifyDashboardStoreChanged();
  return createdJob;
}

export function getCalendarEvents(now = new Date()) {
  return getMyJobs()
    .flatMap((job) => deriveScheduledOccurrences(job, now))
    .sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`));
}
