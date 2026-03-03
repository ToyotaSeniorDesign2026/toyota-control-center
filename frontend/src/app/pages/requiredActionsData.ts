export type RequiredActionItem = {
  id: string;
  state: "pending" | "success" | "failed";
  subject: string;
  runAfter: string;
  mapIndex: number;
  respondedAt: string;
};

export const requiredActionItems: RequiredActionItem[] = [
  {
    id: "act-101",
    state: "pending",
    subject: "Provide deployment input: dealer_scorecard_pipeline",
    runAfter: "Mar 3, 2026 10:15 AM",
    mapIndex: 2,
    respondedAt: "--",
  },
  {
    id: "act-102",
    state: "success",
    subject: "Review retry policy: monthly_board_presentation",
    runAfter: "Mar 2, 2026 08:30 AM",
    mapIndex: 0,
    respondedAt: "Mar 2, 2026 09:02 AM",
  },
  {
    id: "act-103",
    state: "failed",
    subject: "Resolve data policy exception: finance_reporting_query",
    runAfter: "Mar 1, 2026 05:45 PM",
    mapIndex: 4,
    respondedAt: "Mar 1, 2026 06:12 PM",
  },
];

export function pendingRequiredActionsCount() {
  return requiredActionItems.filter((item) => item.state === "pending").length;
}

export function requiredActionStateBadge(state: RequiredActionItem["state"]) {
  if (state === "pending") return "bg-amber-100 text-amber-700";
  if (state === "success") return "bg-green-100 text-green-700";
  return "bg-red-100 text-red-700";
}
