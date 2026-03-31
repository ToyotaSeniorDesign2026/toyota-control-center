export interface Job {
  id: string;
  name: string;
  type:
    | "AI Agent"
    | "SQL Query"
    | "dbt Model"
    | "API Connection"
    | "Excel Report"
    | "PowerPoint Deck"
    | "MCP Job";
  status: "pending" | "approved" | "running" | "completed" | "failed";
  createdAt: string;
  environment?: string;
  description?: string;
  logs?: Array<{ timestamp: string; message: string; level: "info" | "warning" | "error" }>;
  policyChecks?: Array<{ name: string; status: "passed" | "failed" | "warning"; message: string }>;
}

export const mockMyJobs: Job[] = [
  {
    id: "RES-001",
    name: "customer_data_analysis",
    type: "SQL Query",
    status: "approved",
    createdAt: "2024-02-20T10:00:00Z",
    environment: "Dev",
    description:
      "SQL query to analyze customer behavior patterns, identify churn risk factors, and generate actionable insights for the marketing team. This query joins customer transaction data with demographic information and calculates key metrics.",
    logs: [
      { timestamp: "2024-02-20T10:05:00Z", message: "Query validation completed successfully", level: "info" },
      { timestamp: "2024-02-20T10:03:00Z", message: "Performing security scan", level: "info" },
      { timestamp: "2024-02-20T10:01:00Z", message: "Job created and queued for approval", level: "info" },
    ],
    policyChecks: [
      { name: "Data Access Policy", status: "passed", message: "User has appropriate permissions for queried tables" },
      { name: "PII Compliance", status: "passed", message: "No direct PII fields accessed" },
      { name: "Query Complexity", status: "warning", message: "Query execution time may exceed 30 seconds" },
    ],
  },
  {
    id: "RES-002",
    name: "sales_forecasting_agent",
    type: "AI Agent",
    status: "approved",
    createdAt: "2024-02-19T14:30:00Z",
    environment: "Dev",
    description:
      "AI-powered agent that analyzes historical sales data to predict future revenue trends. Uses machine learning models to identify seasonal patterns, market trends, and generate weekly forecasts with confidence intervals.",
    logs: [
      { timestamp: "2024-02-19T14:45:00Z", message: "Model training completed with 94% accuracy", level: "info" },
      { timestamp: "2024-02-19T14:35:00Z", message: "Initializing ML pipeline", level: "info" },
      { timestamp: "2024-02-19T14:31:00Z", message: "Agent configuration validated", level: "info" },
    ],
    policyChecks: [
      { name: "Model Governance", status: "passed", message: "Model meets bias and fairness standards" },
      { name: "Data Lineage", status: "passed", message: "All data sources properly documented" },
      { name: "Job Job Limits", status: "passed", message: "Compute and memory allocation within limits" },
    ],
  },
  {
    id: "RES-003",
    name: "inventory_transform",
    type: "dbt Model",
    status: "approved",
    createdAt: "2024-02-18T09:15:00Z",
    environment: "Dev",
    description:
      "dbt transformation model that processes raw inventory data from multiple warehouses and creates clean, normalized tables for analytics. Includes data quality checks and incremental loading logic.",
    logs: [
      { timestamp: "2024-02-18T09:25:00Z", message: "Model compiled successfully", level: "info" },
      { timestamp: "2024-02-18T09:20:00Z", message: "Dependencies resolved", level: "info" },
      { timestamp: "2024-02-18T09:16:00Z", message: "Model registered in catalog", level: "info" },
    ],
    policyChecks: [
      { name: "Schema Validation", status: "passed", message: "Output schema matches specifications" },
      { name: "Data Quality", status: "passed", message: "All quality tests passed" },
      { name: "Documentation", status: "passed", message: "Model fully documented" },
    ],
  },
];

export const mockPendingApprovals: Job[] = [
  {
    id: "RES-004",
    name: "customer_sentiment_agent",
    type: "AI Agent",
    status: "pending",
    createdAt: "2024-02-20T11:30:00Z",
    description:
      "Natural language processing agent to analyze customer support tickets and social media mentions. Classifies sentiment as positive, negative, or neutral and identifies trending issues.",
    logs: [
      { timestamp: "2024-02-20T11:32:00Z", message: "Awaiting admin approval", level: "info" },
      { timestamp: "2024-02-20T11:31:00Z", message: "Policy checks completed", level: "info" },
      { timestamp: "2024-02-20T11:30:00Z", message: "Job submitted for review", level: "info" },
    ],
    policyChecks: [
      { name: "External API Access", status: "warning", message: "Requires approval for third-party API connections" },
      { name: "Data Classification", status: "passed", message: "Handles only non-sensitive customer feedback" },
      { name: "Cost Estimation", status: "passed", message: "Estimated monthly cost: $120" },
    ],
  },
  {
    id: "RES-005",
    name: "financial_reporting_query",
    type: "SQL Query",
    status: "pending",
    createdAt: "2024-02-20T08:45:00Z",
    description:
      "Comprehensive SQL query to generate monthly financial reports including revenue, expenses, profit margins, and year-over-year comparisons for executive dashboard.",
    logs: [
      { timestamp: "2024-02-20T08:47:00Z", message: "Security review in progress", level: "info" },
      { timestamp: "2024-02-20T08:46:00Z", message: "Query complexity analyzed", level: "warning" },
      { timestamp: "2024-02-20T08:45:00Z", message: "Submitted for approval", level: "info" },
    ],
    policyChecks: [
      { name: "Financial Data Access", status: "warning", message: "Requires CFO approval for financial table access" },
      { name: "Query Performance", status: "passed", message: "Estimated execution time: 12 seconds" },
      { name: "Audit Logging", status: "passed", message: "All accesses will be logged" },
    ],
  },
];

export const mockRunningJobs: Job[] = [
  {
    id: "RES-001",
    name: "customer_data_analysis",
    type: "SQL Query",
    status: "running",
    createdAt: "2024-02-20T10:00:00Z",
    environment: "Dev",
    description:
      "SQL query to analyze customer behavior patterns, identify churn risk factors, and generate actionable insights for the marketing team. This query joins customer transaction data with demographic information and calculates key metrics.",
    logs: [
      { timestamp: "2024-02-20T15:22:00Z", message: "Processing 2.3M records", level: "info" },
      { timestamp: "2024-02-20T15:20:00Z", message: "Query execution started", level: "info" },
      { timestamp: "2024-02-20T15:19:00Z", message: "Connection to database established", level: "info" },
    ],
    policyChecks: [
      { name: "Data Access Policy", status: "passed", message: "User has appropriate permissions for queried tables" },
      { name: "PII Compliance", status: "passed", message: "No direct PII fields accessed" },
      { name: "Query Complexity", status: "warning", message: "Query execution time may exceed 30 seconds" },
    ],
  },
  {
    id: "RES-002",
    name: "sales_forecasting_agent",
    type: "AI Agent",
    status: "running",
    createdAt: "2024-02-19T14:30:00Z",
    environment: "Dev",
    description:
      "AI-powered agent that analyzes historical sales data to predict future revenue trends. Uses machine learning models to identify seasonal patterns, market trends, and generate weekly forecasts with confidence intervals.",
    logs: [
      { timestamp: "2024-02-20T15:25:00Z", message: "Generating forecast for Q2 2024", level: "info" },
      { timestamp: "2024-02-20T15:20:00Z", message: "Model inference in progress", level: "info" },
      { timestamp: "2024-02-20T15:18:00Z", message: "Agent execution triggered", level: "info" },
    ],
    policyChecks: [
      { name: "Model Governance", status: "passed", message: "Model meets bias and fairness standards" },
      { name: "Data Lineage", status: "passed", message: "All data sources properly documented" },
      { name: "Job Job Limits", status: "passed", message: "Compute and memory allocation within limits" },
    ],
  },
];

export function formatJobDate(dateString: string) {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function getJobStatusColor(status: string) {
  switch (status) {
    case "pending":
      return "bg-yellow-100 text-yellow-700 border-yellow-200";
    case "approved":
      return "bg-green-100 text-green-700 border-green-200";
    case "running":
      return "bg-blue-100 text-blue-700 border-blue-200";
    case "completed":
      return "bg-gray-100 text-gray-700 border-gray-200";
    case "failed":
      return "bg-red-100 text-red-700 border-red-200";
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
}

export function getJobTypeColor(type: string) {
  switch (type) {
    case "AI Agent":
      return "text-purple-600";
    case "SQL Query":
      return "text-green-600";
    case "dbt Model":
      return "text-orange-600";
    case "API Connection":
      return "text-blue-600";
    case "Excel Report":
      return "text-emerald-600";
    case "PowerPoint Deck":
      return "text-orange-600";
    case "MCP Job":
      return "text-violet-600";
    default:
      return "text-gray-600";
  }
}
