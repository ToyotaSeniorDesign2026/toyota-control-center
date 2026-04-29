import { MessageSquare, X, Send, Clock, Plus, XCircle, Loader } from "lucide-react";
import { useState, useRef, useEffect } from "react";

const MODEL_OPTIONS = [
  { label: "GPT-4.1", value: "gpt-4.1" },
  { label: "GPT-4o", value: "gpt-4o" },
  { label: "GPT-4o mini", value: "gpt-4o-mini" },
] as const;

interface AssistantActivityStep {
  id: string;
  label: string;
  status: "pending" | "in-progress" | "completed" | "error";
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "activity";
  content: string;
  timestamp: Date;
  activitySteps?: AssistantActivityStep[];
  completedUpdates?: Record<string, any>;
}

interface AttachedItem {
  id: string;
  name: string;
  type: "job" | "template";
  metadata?: {
    jobType?: string;
    schedule?: string;
    status?: string;
    category?: string;
    description?: string;
  };
}

interface ChatThread {
  id: string;
  title: string;
  preview: string;
  timestamp: Date;
  messages: ChatMessage[];
}

interface ResourceSummary {
  id: string;
  name: string;
  type: string;
  connector?: string;
  config?: Record<string, any>;
}

interface SecretRequest {
  kind: "github_personal_access_token";
  prompt: string;
  submit_label?: string;
}

interface RepositoryOption {
  full_name: string;
  owner: string;
  name: string;
  default_branch?: string | null;
  private: boolean;
}

interface ConfigRequestField {
  key: string;
  label: string;
  placeholder?: string | null;
  secret: boolean;
  required: boolean;
  group?: string | null;
}

interface ConfigRequest {
  kind: "sql_session_env";
  prompt: string;
  submit_label?: string;
  fields: ConfigRequestField[];
  repository_hints?: string[] | null;
}

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onJobCreationIntent?: () => void;
  onFieldsExtracted?: (fields: Record<string, any>) => void;
  currentDraftData?: Record<string, any>;
  assistantNotices?: Array<{ id: string; content: string }>;
  onConsoleEvent?: (
    type: "intent_detected" | "draft_created" | "extracted_fields" | "draft_updated" | "missing_fields_identified",
    message: string,
    data?: Record<string, any>,
    previousValues?: Record<string, any>
  ) => void;
  resources?: ResourceSummary[];
  onRunStarted?: (runId: string) => void;
}

const initialMessages: ChatMessage[] = [
  {
    id: "1",
    role: "assistant",
    content: "Hi! I'm CC Assistant 👋 I can help you create jobs, troubleshoot issues, and answer questions about your workflows.",
    timestamp: new Date(Date.now() - 10 * 60 * 1000),
  },
  {
    id: "2",
    role: "assistant",
    content: "What would you like help with today? You can ask me to:\n• Create a new job\n• Run a job (e.g. \"run Customer Churn Analysis\")\n• Troubleshoot errors\n• Explain features\n• Draft job specifications",
    timestamp: new Date(),
  },
];

const mockChatHistory: ChatThread[] = [
  {
    id: "chat-1",
    title: "Create churn workflow",
    preview: "Discussion about setting up a customer churn detection workflow",
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
    messages: [
      {
        id: "h1-1",
        role: "user",
        content: "How do I create a churn workflow?",
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000),
      },
      {
        id: "h1-2",
        role: "assistant",
        content: "I can help you create a customer churn detection workflow...",
        timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000 + 10000),
      },
    ],
  },
  {
    id: "chat-2",
    title: "Troubleshoot warranty claims job",
    preview: "Debugging issues with the warranty claims rollup job",
    timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000),
    messages: [
      {
        id: "h2-1",
        role: "user",
        content: "Why is my warranty claims job failing?",
        timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000),
      },
      {
        id: "h2-2",
        role: "assistant",
        content: "Let me help you debug that. Can you share the error logs?",
        timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000 + 10000),
      },
    ],
  },
  {
    id: "chat-3",
    title: "Monthly dealer KPI draft",
    preview: "Creating a PowerPoint template for monthly dealer KPI reports",
    timestamp: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000),
    messages: [
      {
        id: "h3-1",
        role: "user",
        content: "Help me create a KPI deck template",
        timestamp: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000),
      },
      {
        id: "h3-2",
        role: "assistant",
        content: "I'll help you draft a professional KPI deck...",
        timestamp: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000 + 10000),
      },
    ],
  },
  {
    id: "chat-4",
    title: "Retry policy question",
    preview: "Understanding retry policies and error handling",
    timestamp: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
    messages: [
      {
        id: "h4-1",
        role: "user",
        content: "What's the best retry policy for API calls?",
        timestamp: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
      },
      {
        id: "h4-2",
        role: "assistant",
        content: "Great question! Let me explain exponential backoff strategies...",
        timestamp: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000 + 10000),
      },
    ],
  },
];


export function ChatPanel({ isOpen, onClose, onJobCreationIntent, onFieldsExtracted, currentDraftData, assistantNotices, onConsoleEvent, resources, onRunStarted }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatThread[]>(mockChatHistory);
  const [selectedModel, setSelectedModel] = useState<(typeof MODEL_OPTIONS)[number]["value"]>("gpt-4o");
  const [isDragOverInput, setIsDragOverInput] = useState(false);
  const [attachedItems, setAttachedItems] = useState<AttachedItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingSecretRequest, setPendingSecretRequest] = useState<(SecretRequest & { originalMessage: string }) | null>(null);
  const [secretInputValue, setSecretInputValue] = useState("");
  const [sessionGitHubToken, setSessionGitHubToken] = useState("");
  const [repositoryOptions, setRepositoryOptions] = useState<RepositoryOption[]>([]);
  const [pendingConfigRequest, setPendingConfigRequest] = useState<(ConfigRequest & { originalMessage: string }) | null>(null);
  const [configInputValues, setConfigInputValues] = useState<Record<string, string>>({});
  const [sessionEnv, setSessionEnv] = useState<Record<string, string>>({});
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const seenNoticeIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!assistantNotices?.length) return;

    const newNotices = assistantNotices.filter((notice) => !seenNoticeIdsRef.current.has(notice.id));
    if (newNotices.length === 0) return;

    newNotices.forEach((notice) => seenNoticeIdsRef.current.add(notice.id));
    setMessages((prev) => [
      ...prev,
      ...newNotices.map((notice) => ({
        id: notice.id,
        role: "assistant" as const,
        content: notice.content,
        timestamp: new Date(),
      })),
    ]);
  }, [assistantNotices]);

  // Auto-adjust textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 300) + "px";
    }
  }, [inputValue]);

  // Classify a message as workflow-heavy or simple chat
  const isWorkflowMessage = (text: string): boolean => {
    const workflowKeywords = [
      // Job creation/management
      "create", "new", "job", "workflow", "pipeline", "draft",
      // Updates/modifications
      "update", "edit", "change", "modify", "set", "add", "update",
      // Field/form operations
      "field", "input", "output", "source", "destination", "schedule", "timeout", "retry",
      // Troubleshooting/analysis
      "troubleshoot", "debug", "error", "fix", "issue", "problem", "failed", "failing",
      "not working", "help me", "investigate",
      // Configuration
      "config", "configure", "settings", "parameter", "enable", "disable",
      // Extraction/parsing intent
      "extract", "parse", "get", "fetch", "retrieve", "what fields", "what details",
      // Complex structure
      "sql", "query", "dag", "airflow", "snowflake", "s3", "database", "table",
      // Intent markers
      "i want to", "can you", "could you", "help me create", "help me set",
    ];

    const lowerText = text.toLowerCase().trim();
    
    // Check for workflow keywords
    const hasWorkflowKeyword = workflowKeywords.some((keyword) =>
      lowerText.includes(keyword)
    );

    // Simple/casual chat patterns - these are NOT workflow messages
    const casualPatterns = [
      /^(hi|hey|hello|thanks|thank you|great|good|ok|okay|yes|no|what|why|how)[\s?!.]*$/i,
      /^(bye|goodbye|see you|later)[\s?!.]*$/i,
      /^(can you help|what can you do|what features|capabilities)[\s?!.]*$/i,
      /^(tell me about|explain|remind me)[\s?!.]*$/i,
    ];

    const isCasualChat = casualPatterns.some((pattern) =>
      pattern.test(lowerText)
    );

    // If it matches casual patterns, it's definitely simple chat
    if (isCasualChat) return false;

    // If it has workflow keywords, it's workflow-heavy
    if (hasWorkflowKeyword) return true;

    // Multi-sentence messages are likely workflow-related
    if (lowerText.length > 100) return true;

    // Default to simple chat for short, neutral messages
    return false;
  };

  const sendChatRequest = async ({
    requestMessage,
    renderedMessage,
    includeUserMessage,
    githubPersonalAccessToken,
    sessionEnvOverride,
  }: {
    requestMessage: string;
    renderedMessage: string;
    includeUserMessage: boolean;
    githubPersonalAccessToken?: string;
    sessionEnvOverride?: Record<string, string>;
  }) => {
    const isWorkflow = isWorkflowMessage(requestMessage.trim());
    
    const activityMessageId = (Date.now() + 0.5).toString();
    
    let activityMessage: ChatMessage;
    
    if (isWorkflow) {
      // Rich activity card for workflow messages
      const initialActivitySteps: AssistantActivityStep[] = [
        { id: "understand", label: "Understanding request", status: "in-progress" },
        { id: "detect", label: "Detecting intent", status: "pending" },
        { id: "extract", label: "Extracting details", status: "pending" },
        { id: "prepare", label: "Preparing response", status: "pending" },
      ];

      activityMessage = {
        id: activityMessageId,
        role: "activity",
        content: "CC Assistant is working...",
        timestamp: new Date(),
        activitySteps: initialActivitySteps,
        completedUpdates: {},
      };
    } else {
      // Simple loading state for casual chat
      activityMessage = {
        id: activityMessageId,
        role: "activity",
        content: "CC Assistant is responding...",
        timestamp: new Date(),
        // No activitySteps indicates simple loading mode
        completedUpdates: {},
      };
    }

    if (includeUserMessage) {
      const newUserMessage: ChatMessage = {
        id: Date.now().toString(),
        role: "user",
        content: renderedMessage,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, newUserMessage, activityMessage]);
    } else {
      setMessages((prev) => [...prev, activityMessage]);
    }
    setIsLoading(true);

    const updateActivityStep = (stepIndex: number, newStatus: "in-progress" | "completed" | "error") => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === activityMessageId && msg.role === "activity" && msg.activitySteps
            ? {
                ...msg,
                activitySteps: msg.activitySteps.map((step, idx) => {
                  if (idx === stepIndex) {
                    return { ...step, status: newStatus };
                  } else if (idx < stepIndex && newStatus === "in-progress") {
                    return { ...step, status: "completed" };
                  }
                  return step;
                }),
              }
            : msg
        )
      );
    };

    try {
      updateActivityStep(0, "in-progress");
      await new Promise((resolve) => setTimeout(resolve, 300));
      updateActivityStep(0, "completed");
      updateActivityStep(1, "in-progress");

      const conversationHistory = messages
        .filter(msg => (msg.role === "user" || msg.role === "assistant") && msg.role !== "activity")
        .map(msg => ({
          role: msg.role,
          content: msg.content,
        }));

      updateActivityStep(1, "completed");
      updateActivityStep(2, "in-progress");

      const response = await fetch("/api/chat/send", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: requestMessage,
          conversation_history: conversationHistory,
          model: selectedModel,
          current_draft_data: currentDraftData,
          available_resources: resources ?? [],
          github_personal_access_token: githubPersonalAccessToken ?? (sessionGitHubToken || undefined),
          session_env: sessionEnvOverride ?? sessionEnv,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.secret_request) {
        setPendingSecretRequest({
          ...data.secret_request,
          originalMessage: requestMessage,
        });
        setSecretInputValue("");
      } else {
        setPendingSecretRequest(null);
        setSecretInputValue("");
      }
      if (data.config_request) {
        setPendingConfigRequest({
          ...data.config_request,
          originalMessage: requestMessage,
        });
        setConfigInputValues((previous) => {
          const next: Record<string, string> = {};
          for (const field of data.config_request.fields) {
            const existingValue =
              previous[field.key] ??
              (sessionEnvOverride ?? sessionEnv)[field.key] ??
              "";
            if (existingValue) {
              next[field.key] = existingValue;
            }
          }
          return next;
        });
      } else {
        setPendingConfigRequest(null);
        setConfigInputValues({});
      }
      setRepositoryOptions(Array.isArray(data.repository_options) ? data.repository_options : []);
      
      updateActivityStep(2, "completed");
      updateActivityStep(3, "in-progress");
      
      await new Promise((resolve) => setTimeout(resolve, 200));
      updateActivityStep(3, "completed");

      // Small delay to show completion state
      await new Promise((resolve) => setTimeout(resolve, 400));

      // Replace activity message with final response
      const assistantResponse: ChatMessage = {
        id: (Date.now() + 2).toString(),
        role: "assistant",
        content: data.response,
        timestamp: new Date(),
      };
      
      // If there are extracted fields, add them to the activity summary
      if (data.extracted_fields && Object.keys(data.extracted_fields).length > 0) {
        assistantResponse.completedUpdates = data.extracted_fields;
      }

      setMessages((prev) => {
        // Replace the activity message with the final response
        const filtered = prev.filter((msg) => msg.id !== activityMessageId);
        return [...filtered, assistantResponse];
      });
      
      // Emit console events for job creation workflow
      if (data.job_creation_intent) {
        onConsoleEvent?.("intent_detected", "Job creation intent detected", {
          intent: "create_job",
          message: requestMessage,
        });
      }
      
      // Detect job creation intent and trigger callback
      if (data.job_creation_intent && onJobCreationIntent) {
        setTimeout(() => {
          onJobCreationIntent();
          onConsoleEvent?.("draft_created", "Draft opened for job creation", {
            draft_type: "job",
            timestamp: new Date().toISOString(),
          });
        }, 200);
      }
      
      // Notify parent if a run was started by the backend
      if (data.run_id) {
        onRunStarted?.(data.run_id);
      }

      // Handle extracted fields from the message
      if (data.reset_draft && onFieldsExtracted) {
        onFieldsExtracted({ __reset_draft__: true });
        onConsoleEvent?.("draft_updated", "Draft reset — user switched tasks", {});
      } else if (data.extracted_fields && onFieldsExtracted) {
        onConsoleEvent?.("extracted_fields", "Fields extracted from user message", data.extracted_fields);
        onFieldsExtracted(data.extracted_fields);
        onConsoleEvent?.("draft_updated", `Draft updated with ${Object.keys(data.extracted_fields).length} field(s)`, {
          updated_fields: Object.keys(data.extracted_fields),
          values: data.extracted_fields,
        });
      }
    } catch (error) {
      console.error("Error sending message:", error);
      
      // Mark the failed step as error and show error message
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === activityMessageId && msg.role === "activity"
            ? {
                ...msg,
                activitySteps: msg.activitySteps?.map((step) => ({
                  ...step,
                  status: step.status === "completed" ? "completed" : "error",
                })),
              }
            : msg
        )
      );

      // Add error response after a short delay
      await new Promise((resolve) => setTimeout(resolve, 800));

      const errorResponse: ChatMessage = {
        id: (Date.now() + 2).toString(),
        role: "assistant",
        content: `I encountered an error: ${error instanceof Error ? error.message : "Unknown error"}. Please check that the OpenAI API is configured and available.`,
        timestamp: new Date(),
      };
      
      setMessages((prev) => {
        const filtered = prev.filter((msg) => msg.id !== activityMessageId);
        return [...filtered, errorResponse];
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim() && attachedItems.length === 0) return;

    const messageContent = attachedItems.length > 0
      ? `${inputValue}\n\n[Attached: ${attachedItems.map(item => item.name).join(", ")}]`
      : inputValue;
    const requestMessage = inputValue.trim() || "Please help with the attached item";

    setInputValue("");
    setAttachedItems([]);
    await sendChatRequest({
      requestMessage,
      renderedMessage: messageContent,
      includeUserMessage: true,
    });
  };

  const handleSubmitSecretRequest = async () => {
    if (!pendingSecretRequest || !secretInputValue.trim()) return;
    const token = secretInputValue.trim();
    setSessionGitHubToken(token);

    await sendChatRequest({
      requestMessage: pendingSecretRequest.originalMessage,
      renderedMessage: pendingSecretRequest.originalMessage,
      includeUserMessage: false,
      githubPersonalAccessToken: token,
    });
  };

  const handleSubmitConfigRequest = async () => {
    if (!pendingConfigRequest) return;

    const nextSessionEnv = {
      ...sessionEnv,
      ...Object.fromEntries(
        Object.entries(configInputValues)
          .map(([key, value]) => [key, value.trim()])
          .filter(([, value]) => value),
      ),
    };

    const sqlHost = nextSessionEnv.SQL_DB_HOST;
    const sqlPort = nextSessionEnv.SQL_DB_PORT;
    const sqlDatabase = nextSessionEnv.SQL_DB_DATABASE;
    const sqlUsername = nextSessionEnv.SQL_DB_USERNAME;
    const sqlPassword = nextSessionEnv.SQL_DB_PASSWORD;
    if (sqlHost && sqlPort && sqlDatabase && sqlUsername && sqlPassword) {
      nextSessionEnv.SQL_CONNECTION_STRING =
        `Host=${sqlHost};Port=${sqlPort};Database=${sqlDatabase};Username=${sqlUsername};Password=${sqlPassword}`;
    }

    for (const field of pendingConfigRequest.fields) {
      if (field.required && !nextSessionEnv[field.key]) {
        return;
      }
    }

    setSessionEnv(nextSessionEnv);
    await sendChatRequest({
      requestMessage: pendingConfigRequest.originalMessage,
      renderedMessage: pendingConfigRequest.originalMessage,
      includeUserMessage: false,
      sessionEnvOverride: nextSessionEnv,
    });
  };

  const handleRepositoryOptionClick = async (repository: RepositoryOption) => {
    const message = `Connect the GitHub repo ${repository.full_name}${repository.default_branch ? ` branch ${repository.default_branch}` : ""}`;
    setRepositoryOptions([]);
    await sendChatRequest({
      requestMessage: message,
      renderedMessage: message,
      includeUserMessage: true,
    });
  };

  const handleNewChat = () => {
    setMessages(initialMessages);
    setInputValue("");
    setAttachedItems([]);
    setShowHistory(false);
    setPendingSecretRequest(null);
    setSecretInputValue("");
    setRepositoryOptions([]);
    setPendingConfigRequest(null);
    setConfigInputValues({});
    setSessionEnv({});
    setSessionGitHubToken("");
  };

  const handleLoadChatThread = (thread: ChatThread) => {
    setMessages(thread.messages);
    setInputValue("");
    setAttachedItems([]);
    setShowHistory(false);
  };

  const handleInputDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOverInput(true);
  };

  const handleInputDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOverInput(false);
  };

  const handleInputDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOverInput(false);

    // Try to extract job or template data from the drag event
    try {
      const jobData = e.dataTransfer.getData("application/json");
      if (jobData) {
        const parsed = JSON.parse(jobData);
        const name = parsed.name || parsed.jobName || parsed.title;
        
        if (name) {
          const newAttachment: AttachedItem = {
            id: Date.now().toString(),
            name: name,
            type: parsed.type === "template" ? "template" : "job",
            metadata: {
              jobType: parsed.type,
              schedule: parsed.schedule,
              status: parsed.status,
              category: parsed.category,
              description: parsed.description,
            },
          };
          
          setAttachedItems((prev) => [...prev, newAttachment]);
          return;
        }
      }
    } catch (err) {
      // Fall back to plain text
    }

    // If no JSON data, try plain text
    const text = e.dataTransfer.getData("text/plain");
    if (text && text.trim()) {
      const newAttachment: AttachedItem = {
        id: Date.now().toString(),
        name: text.substring(0, 50), // Use first 50 chars as name
        type: "job",
        metadata: {},
      };
      setAttachedItems((prev) => [...prev, newAttachment]);
    }
  };

  const handleRemoveAttachment = (id: string) => {
    setAttachedItems((prev) => prev.filter((item) => item.id !== id));
  };

  const formatTime = (date: Date) => {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  // Always render as a layout element with conditional width
  return (
    <aside className="flex-shrink-0 bg-white border-l border-gray-200 flex flex-col overflow-hidden w-full h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b-2 border-gray-100 bg-gradient-to-r from-gray-50 to-white flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ed0923]/15">
            <MessageSquare className="h-5 w-5 text-[#ed0923]" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 text-sm leading-tight">Chat Assistant</h3>
            <p className="text-xs text-gray-500 leading-tight">AI-powered job support</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition"
            title="View chat history"
          >
            <Clock className="h-4 w-4" />
          </button>
          <button
            onClick={handleNewChat}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition"
            title="Start new chat"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition"
            title="Close panel"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Messages or History Area */}
      {showHistory ? (
        <div className="flex-1 overflow-y-auto p-4 space-y-2 flex flex-col">
          <h4 className="font-semibold text-sm text-gray-900 mb-2">Recent Chats</h4>
          {chatHistory.map((thread) => (
            <button
              key={thread.id}
              onClick={() => handleLoadChatThread(thread)}
              className="rounded-lg p-3 text-left hover:bg-gray-50 transition border border-transparent hover:border-gray-200"
            >
              <p className="font-medium text-sm text-gray-900 mb-1 truncate">{thread.title}</p>
              <p className="text-xs text-gray-500 mb-2 line-clamp-2">{thread.preview}</p>
              <p className="text-xs text-gray-400">{formatTime(thread.timestamp)}</p>
            </button>
          ))}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-4 flex flex-col">
          {messages.map((message) => (
            <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
              {message.role === "activity" ? (
                // Activity message with conditional rendering based on message type
                message.activitySteps ? (
                  // Rich activity card for workflow-heavy messages
                  <div className="rounded-lg px-4 py-3 text-sm flex-shrink-0 max-w-[85%] bg-blue-50 border border-blue-200 rounded-bl-none">
                    <div className="flex items-center gap-2 mb-3">
                      <Loader className="h-4 w-4 text-blue-600 animate-spin" />
                      <span className="font-medium text-blue-900">{message.content}</span>
                    </div>
                    <div className="space-y-2">
                      {message.activitySteps.map((step) => (
                        <div key={step.id} className="flex items-center gap-2 text-xs">
                          {step.status === "completed" && (
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-green-500 text-white flex-shrink-0">
                              ✓
                            </span>
                          )}
                          {step.status === "in-progress" && (
                            <span className="inline-flex h-5 w-5 items-center justify-center text-blue-600 flex-shrink-0 animate-pulse">
                              ⏳
                            </span>
                          )}
                          {step.status === "pending" && (
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-gray-200 text-gray-500 flex-shrink-0 text-[10px]">
                              ○
                            </span>
                          )}
                          {step.status === "error" && (
                            <span className="inline-flex h-5 w-5 items-center justify-center text-red-600 flex-shrink-0">
                              ✕
                            </span>
                          )}
                          <span
                            className={`${
                              step.status === "completed"
                                ? "text-green-700 line-through"
                                : step.status === "in-progress"
                                ? "text-blue-900 font-medium"
                                : step.status === "error"
                                ? "text-red-700"
                                : "text-gray-600"
                            }`}
                          >
                            {step.label}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  // Simple loading indicator for casual chat
                  <div className="rounded-lg px-4 py-3 text-sm flex-shrink-0 max-w-[85%] bg-gray-100 border border-gray-200 rounded-bl-none flex items-center gap-2">
                    <span className="inline-flex gap-1">
                      <span className="inline-block h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="inline-block h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="inline-block h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                    </span>
                    <span className="text-gray-600">{message.content}</span>
                  </div>
                )
              ) : (
                // Regular user or assistant message
                <div
                  className={`rounded-lg px-4 py-3 text-sm flex-shrink-0 max-w-[90%] shadow-sm ${
                    message.role === "user"
                      ? "bg-[#ed0923] text-white rounded-br-none"
                      : "bg-gray-100 text-gray-900 rounded-bl-none"
                  }`}
                >
                  <p className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</p>
                  {message.role === "assistant" && message.completedUpdates && Object.keys(message.completedUpdates).length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-300 text-xs opacity-75">
                      <p className="font-medium text-gray-600 mb-1">Updated fields:</p>
                      <ul className="space-y-1">
                        {Object.entries(message.completedUpdates).map(([key, value]) => (
                          <li key={key} className="text-gray-600">
                            • {key}: <span className="font-semibold">{typeof value === "object" ? JSON.stringify(value) : String(value)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Composer Section */}
      <div className="border-t border-gray-200 bg-gray-50/50 flex-shrink-0 w-full flex flex-col space-y-4 px-5 py-4">
        {/* Instructional Tip */}
        <div className="text-xs text-gray-600 leading-relaxed">
          <p>💡 Drag job cards or templates into the input below to add context to your questions.</p>
        </div>

        {/* Attached Items Display */}
        {attachedItems.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {attachedItems.map((item) => (
              <div
                key={item.id}
                className="inline-flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs"
              >
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-blue-500" />
                  <span className="text-gray-700 font-medium truncate max-w-[120px]">{item.name}</span>
                  <span className="text-gray-500 text-xs">({item.type})</span>
                </div>
                <button
                  onClick={() => handleRemoveAttachment(item.id)}
                  className="text-gray-400 hover:text-gray-600 transition flex-shrink-0"
                  title="Remove attachment"
                >
                  <XCircle className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        {pendingSecretRequest && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-xs font-medium text-amber-900">{pendingSecretRequest.prompt}</p>
            <div className="mt-3 flex gap-2">
              <input
                type="password"
                value={secretInputValue}
                onChange={(e) => setSecretInputValue(e.target.value)}
                placeholder="GitHub personal access token"
                className="flex-1 rounded-md border border-amber-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
              />
              <button
                onClick={() => void handleSubmitSecretRequest()}
                disabled={!secretInputValue.trim() || isLoading}
                className="rounded-md bg-[#ed0923] px-3 py-2 text-xs font-medium text-white hover:bg-[#d10820] disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                {pendingSecretRequest.submit_label ?? "Use token"}
              </button>
            </div>
            <p className="mt-2 text-[11px] text-amber-800">
              This token is sent only for the current live GitHub MCP request and is not added to the chat transcript.
            </p>
          </div>
        )}

        {repositoryOptions.length > 0 && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
            <p className="text-xs font-medium text-blue-900">Available repositories</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {repositoryOptions.map((repository) => (
                <button
                  key={repository.full_name}
                  onClick={() => void handleRepositoryOptionClick(repository)}
                  disabled={isLoading}
                  className="rounded-md border border-blue-300 bg-white px-3 py-2 text-left text-xs text-blue-900 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <div className="font-medium">{repository.full_name}</div>
                  <div className="mt-1 text-[11px] text-blue-700">
                    {repository.private ? "Private" : "Public"}
                    {repository.default_branch ? ` • ${repository.default_branch}` : ""}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {pendingConfigRequest && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
            <p className="text-[11px] font-medium text-emerald-900 mb-2">{pendingConfigRequest.prompt}</p>
            <div className="space-y-1.5">
              {/* Host + Port on one row */}
              {pendingConfigRequest.fields.some((f) => f.key === "SQL_DB_HOST") && (
                <div className="flex gap-2">
                  {["SQL_DB_HOST", "SQL_DB_PORT"].map((key) => {
                    const field = pendingConfigRequest.fields.find((f) => f.key === key);
                    if (!field) return null;
                    return (
                      <div key={field.key} className={key === "SQL_DB_HOST" ? "flex-1" : "w-24"}>
                        <label className="block text-[10px] font-medium text-emerald-900 mb-0.5">
                          {field.label}{field.required ? " *" : ""}
                        </label>
                        <input
                          type="text"
                          value={configInputValues[field.key] ?? sessionEnv[field.key] ?? ""}
                          onChange={(e) => setConfigInputValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                          placeholder={field.placeholder ?? ""}
                          className="w-full rounded border border-emerald-300 bg-white px-2 py-1 text-xs text-gray-900 placeholder-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                        />
                      </div>
                    );
                  })}
                </div>
              )}
              {/* Database name */}
              {pendingConfigRequest.fields.filter((f) => f.key === "SQL_DB_DATABASE").map((field) => (
                <div key={field.key}>
                  <label className="block text-[10px] font-medium text-emerald-900 mb-0.5">
                    {field.label}{field.required ? " *" : ""}
                  </label>
                  <input
                    type="text"
                    value={configInputValues[field.key] ?? sessionEnv[field.key] ?? ""}
                    onChange={(e) => setConfigInputValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={field.placeholder ?? ""}
                    className="w-full rounded border border-emerald-300 bg-white px-2 py-1 text-xs text-gray-900 placeholder-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                  />
                </div>
              ))}
              {/* Username + Password on one row */}
              {pendingConfigRequest.fields.some((f) => f.key === "SQL_DB_USERNAME") && (
                <div className="flex gap-2">
                  {["SQL_DB_USERNAME", "SQL_DB_PASSWORD"].map((key) => {
                    const field = pendingConfigRequest.fields.find((f) => f.key === key);
                    if (!field) return null;
                    return (
                      <div key={field.key} className="flex-1">
                        <label className="block text-[10px] font-medium text-emerald-900 mb-0.5">
                          {field.label}{field.required ? " *" : ""}
                        </label>
                        <input
                          type={field.secret ? "password" : "text"}
                          value={configInputValues[field.key] ?? sessionEnv[field.key] ?? ""}
                          onChange={(e) => setConfigInputValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                          placeholder={field.placeholder ?? ""}
                          className="w-full rounded border border-emerald-300 bg-white px-2 py-1 text-xs text-gray-900 placeholder-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                        />
                      </div>
                    );
                  })}
                </div>
              )}
              {/* Remaining fields (e.g. optional Connection ID) */}
              {pendingConfigRequest.fields
                .filter((f) => !["SQL_DB_HOST","SQL_DB_PORT","SQL_DB_DATABASE","SQL_DB_USERNAME","SQL_DB_PASSWORD"].includes(f.key))
                .map((field) => (
                  <div key={field.key}>
                    <label className="block text-[10px] font-medium text-emerald-900 mb-0.5">
                      {field.label}{field.required ? " *" : ""}
                    </label>
                    <input
                      type={field.secret ? "password" : "text"}
                      value={configInputValues[field.key] ?? sessionEnv[field.key] ?? ""}
                      onChange={(e) => setConfigInputValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                      placeholder={field.placeholder ?? ""}
                      className="w-full rounded border border-emerald-300 bg-white px-2 py-1 text-xs text-gray-900 placeholder-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                    />
                  </div>
                ))}
            </div>
            {pendingConfigRequest.repository_hints && pendingConfigRequest.repository_hints.length > 0 && (
              <div className="mt-2 rounded border border-emerald-200 bg-white/70 px-2 py-1.5">
                <p className="text-[10px] font-medium text-emerald-900">Repository hints</p>
                <ul className="mt-0.5 space-y-0.5 text-[10px] text-emerald-800">
                  {pendingConfigRequest.repository_hints.map((hint) => (
                    <li key={hint}>• {hint}</li>
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-2 flex items-center justify-between">
              <p className="text-[10px] text-emerald-700">Session-only — not stored.</p>
              <button
                onClick={() => void handleSubmitConfigRequest()}
                disabled={
                  isLoading ||
                  pendingConfigRequest.fields.some((field) => field.required && !(configInputValues[field.key] ?? "").trim())
                }
                className="rounded bg-[#ed0923] px-3 py-1 text-xs font-medium text-white hover:bg-[#d10820] disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                {pendingConfigRequest.submit_label ?? "Use settings"}
              </button>
            </div>
          </div>
        )}

        {/* Chat Input with Drag-and-Drop Support */}
        <div
          className={`flex flex-col gap-2 w-full px-4 py-3 rounded-lg border-2 transition bg-white ${
            isDragOverInput
              ? "border-[#ed0923] ring-1 ring-[#ed0923]/20 bg-red-50/30"
              : "border-gray-300 hover:border-gray-400"
          }`}
          onDragOver={handleInputDragOver}
          onDragLeave={handleInputDragLeave}
          onDrop={handleInputDrop}
          title={isDragOverInput ? "Drop here to add context" : "Drag job or template cards here"}
        >
          <textarea
            ref={textareaRef}
            placeholder="Ask me anything..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            className="w-full bg-transparent border-0 px-0 py-0 text-sm placeholder-gray-500 focus:outline-none focus:ring-0 resize-none overflow-hidden"
            style={{ minHeight: "40px", maxHeight: "300px", height: "40px" }}
          />
          <div className="flex justify-end">
            <button
              onClick={handleSendMessage}
              disabled={(!inputValue.trim() && attachedItems.length === 0) || isLoading}
              className="rounded-lg bg-[#ed0923] px-3 py-2 text-white hover:bg-[#d10820] disabled:bg-gray-300 disabled:cursor-not-allowed transition flex-shrink-0 font-medium text-xs"
              title="Send message (Shift+Enter for new line)"
            >
              {isLoading ? (
                <span className="inline-block animate-spin h-4 w-4">⏳</span>
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {/* Model Selector */}
        <div className="flex items-center gap-3 pt-1">
          <label className="text-xs text-gray-700 font-medium">Model:</label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value as (typeof MODEL_OPTIONS)[number]["value"])}
            className="flex-1 text-xs border border-gray-300 rounded-md px-3 py-2 text-gray-700 bg-white focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923] transition"
          >
            {MODEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </aside>
  );
}
