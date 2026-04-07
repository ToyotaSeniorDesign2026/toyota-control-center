export type RequiredActionItem = {
  id: string;
  state: "pending" | "success" | "failed";
  subject: string;
  runAfter: string;
  mapIndex: number;
  respondedAt: string;
  urgency: "urgent" | "high" | "other";
  description: string;
  details: string[];
  suggestedResolution: string;
  jobName: string;
};

export const requiredActionItems: RequiredActionItem[] = [
  {
    id: "act-101",
    state: "pending",
    subject: "Provide deployment input: dealer_scorecard_pipeline",
    runAfter: "Mar 3, 2026 10:15 AM",
    mapIndex: 2,
    respondedAt: "--",
    urgency: "urgent",
    description: "Deployment requires additional configuration values.",
    details: ["dealer_region", "pipeline_mode", "runtime_environment"],
    suggestedResolution: "Provide the required configuration parameters in the deployment form.",
    jobName: "dealer_scorecard_pipeline",
  },
  {
    id: "act-102",
    state: "success",
    subject: "Review retry policy: monthly_board_presentation",
    runAfter: "Mar 2, 2026 08:30 AM",
    mapIndex: 0,
    respondedAt: "Mar 2, 2026 09:02 AM",
    urgency: "high",
    description: "The job has retried 3 times. Review the policy settings.",
    details: ["Current retry count: 3", "Max retries allowed: 5", "Wait time between retries: 30 seconds"],
    suggestedResolution: "Adjust retry policy settings or investigate the underlying error.",
    jobName: "monthly_board_presentation",
  },
  {
    id: "act-103",
    state: "failed",
    subject: "Resolve data policy exception: finance_reporting_query",
    runAfter: "Mar 1, 2026 05:45 PM",
    mapIndex: 4,
    respondedAt: "Mar 1, 2026 06:12 PM",
    urgency: "urgent",
    description: "A data governance policy violation was detected.",
    details: ["Policy: PII Data Access Control", "Violation: Unauthorized access attempt", "Affected records: 150"],
    suggestedResolution: "Review data access permissions and update the policy rules.",
    jobName: "finance_reporting_query",
  },
];

export function pendingRequiredActionsCount() {
  return requiredActionItems.filter((item) => item.state === "pending").length;
}

export function requiredActionUrgentCount() {
  return requiredActionItems.filter((item) => item.urgency === "urgent").length;
}

export function requiredActionStateBadge(state: RequiredActionItem["state"]) {
  if (state === "pending") return "bg-amber-100 text-amber-700";
  if (state === "success") return "bg-green-100 text-green-700";
  return "bg-red-100 text-red-700";
}

export function requiredActionUrgencyBadge(urgency: RequiredActionItem["urgency"]) {
  if (urgency === "urgent") return "bg-red-100 text-red-700";
  if (urgency === "high") return "bg-amber-100 text-amber-700";
  return "bg-blue-100 text-blue-700";
}

export function getUrgencyLabel(urgency: RequiredActionItem["urgency"]) {
  if (urgency === "urgent") return "Urgent";
  if (urgency === "high") return "High Priority";
  return "Other";
}
