export interface PromotionResource {
  id: string;
  name: string;
  type: "AI Agent" | "SQL Query" | "dbt Model" | "API Connection";
  status: "approved" | "pending_promotion" | "rejected" | "promoted";
  currentEnvironment: string;
  targetEnvironment?: string;
  createdAt: string;
  lastModified?: string;
  rejectionReason?: string;
  description?: string;
}

export const mockReadyForPromotion: PromotionResource[] = [
  {
    id: "RES-001",
    name: "customer_data_analysis",
    type: "SQL Query",
    status: "approved",
    currentEnvironment: "Dev",
    createdAt: "2024-02-20T10:00:00Z",
    description: "SQL query to analyze customer behavior patterns and churn risk factors.",
  },
  {
    id: "RES-002",
    name: "sales_forecasting_agent",
    type: "AI Agent",
    status: "approved",
    currentEnvironment: "Staging",
    createdAt: "2024-02-19T14:30:00Z",
    description: "AI-powered agent that analyzes historical sales data to predict future revenue trends.",
  },
  {
    id: "RES-003",
    name: "inventory_transform",
    type: "dbt Model",
    status: "approved",
    currentEnvironment: "Dev",
    createdAt: "2024-02-18T09:15:00Z",
    description: "dbt transformation model that processes raw inventory data from multiple warehouses.",
  },
];

export const mockPendingPromotions: PromotionResource[] = [
  {
    id: "RES-006",
    name: "revenue_dashboard_query",
    type: "SQL Query",
    status: "pending_promotion",
    currentEnvironment: "Staging",
    targetEnvironment: "Production",
    createdAt: "2024-02-19T10:00:00Z",
    lastModified: "2024-02-20T14:00:00Z",
    description: "Query for executive revenue dashboard with YoY comparisons.",
  },
  {
    id: "RES-007",
    name: "support_ticket_classifier",
    type: "AI Agent",
    status: "pending_promotion",
    currentEnvironment: "Staging",
    targetEnvironment: "Production",
    createdAt: "2024-02-18T16:00:00Z",
    lastModified: "2024-02-20T12:30:00Z",
    description: "ML model to automatically classify and route support tickets.",
  },
];

export const mockRejectedPromotions: PromotionResource[] = [
  {
    id: "RES-008",
    name: "customer_sentiment_agent",
    type: "AI Agent",
    status: "rejected",
    currentEnvironment: "Dev",
    targetEnvironment: "Production",
    createdAt: "2024-02-17T11:30:00Z",
    lastModified: "2024-02-19T15:00:00Z",
    rejectionReason: "Missing comprehensive error handling and logging requirements for production deployment.",
    description: "NLP agent to analyze customer sentiment from support tickets.",
  },
  {
    id: "RES-009",
    name: "financial_reporting_query",
    type: "SQL Query",
    status: "rejected",
    currentEnvironment: "Staging",
    targetEnvironment: "Production",
    createdAt: "2024-02-16T08:45:00Z",
    lastModified: "2024-02-19T10:00:00Z",
    rejectionReason: "Query performance does not meet production SLA requirements. Needs optimization.",
    description: "Comprehensive financial reporting query for executive dashboard.",
  },
];

export const mockRecentlyPromoted: PromotionResource[] = [
  {
    id: "RES-010",
    name: "user_analytics_model",
    type: "dbt Model",
    status: "promoted",
    currentEnvironment: "Production",
    targetEnvironment: "Production",
    createdAt: "2024-02-15T09:00:00Z",
    lastModified: "2024-02-19T16:00:00Z",
    description: "User behavior analytics transformation model.",
  },
];

export function formatPromotionDate(dateString: string) {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function getPromotionTypeColor(type: string) {
  switch (type) {
    case "AI Agent":
      return "text-purple-600";
    case "SQL Query":
      return "text-green-600";
    case "dbt Model":
      return "text-orange-600";
    case "API Connection":
      return "text-blue-600";
    default:
      return "text-gray-600";
  }
}
