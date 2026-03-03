import { useState } from "react";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Database, Code2, Workflow, Brain, Zap, Send, Play, Save, Check, AlertTriangle, Activity, Shield, Circle, Plus, Search, Trash2, MoreVertical, ChevronRight, ChevronLeft, Code, CheckCircle, Clock } from "lucide-react";
import { Button } from "../components/ui/button";

interface JobTemplate {
  id: string;
  name: string;
  type: "Airflow" | "Database" | "Script" | "ML" | "API";
  icon: React.ReactNode;
}

interface AIWorker {
  id: string;
  name: string;
  role: string;
  status: "Idle" | "Thinking" | "Active";
  icon: React.ReactNode;
}

type Message = { role: "user" | "worker"; content: string; workerName?: string };

interface JobSpec {
  name: string;
  type?: "Airflow" | "Database" | "Script" | "ML" | "API";
  riskScore?: number;
  riskLabel?: string;
}

interface ChatThread {
  id: string;
  title: string;
  preview: string;
  timestamp: string;
  messages: Message[];
  jobSpec?: JobSpec;
}

const jobTemplates: JobTemplate[] = [
  { id: "airflow", name: "Airflow Pipeline", type: "Airflow", icon: <Workflow className="h-5 w-5" /> },
  { id: "database", name: "Database Query", type: "Database", icon: <Database className="h-5 w-5" /> },
  { id: "script", name: "Python Script", type: "Script", icon: <Code2 className="h-5 w-5" /> },
  { id: "ml", name: "ML Model Training", type: "ML", icon: <Brain className="h-5 w-5" /> },
  { id: "api", name: "API Integration", type: "API", icon: <Zap className="h-5 w-5" /> },
];

const aiWorkers: AIWorker[] = [
  { id: "orchestration", name: "Orchestration Worker", role: "Job Config", status: "Active", icon: <Activity className="h-5 w-5" /> },
  { id: "risk", name: "Risk Analysis Worker", role: "Compliance", status: "Active", icon: <AlertTriangle className="h-5 w-5" /> },
  { id: "database", name: "Database Worker", role: "Connection", status: "Idle", icon: <Database className="h-5 w-5" /> },
];

const suggestions = [
  { icon: "📊", text: "Daily customer analytics report" },
  { icon: "🔄", text: "Sync data between databases" },
  { icon: "🤖", text: "Train ML model on new data" },
  { icon: "✅", text: "Data quality validation job" },
];

const mockChatThreads: ChatThread[] = [
  {
    id: "chat-1",
    title: "Daily Customer Report",
    preview: "How should I set up the email notification?",
    timestamp: "Today",
    messages: [
      { role: "user", content: "I need to create a daily customer report job" },
      { role: "worker", content: "Great! I can help with that. What type of data will this report contain?", workerName: "Orchestration Worker" },
      { role: "user", content: "How should I set up the email notification?" },
      { role: "worker", content: "You can configure email notifications in the approval requirements section.", workerName: "Risk Analysis Worker" },
    ],
  },
  {
    id: "chat-2",
    title: "ML Model Training Setup",
    preview: "Which framework should I use?",
    timestamp: "Feb 24",
    messages: [
      { role: "user", content: "Setting up ML Model Training job" },
      { role: "worker", content: "I recommend PyTorch or TensorFlow. Which one do you prefer?", workerName: "Orchestration Worker" },
      { role: "user", content: "Which framework should I use?" },
      { role: "worker", content: "Both are excellent. PyTorch is great for research, TensorFlow for production.", workerName: "Risk Analysis Worker" },
    ],
  },
  {
    id: "chat-3",
    title: "Database Backup Job",
    preview: "What's the risk score for this configuration?",
    timestamp: "Feb 23",
    messages: [
      { role: "user", content: "Creating a database backup job" },
      { role: "worker", content: "Database backups are critical. Let's configure this properly.", workerName: "Database Worker" },
      { role: "user", content: "What's the risk score for this configuration?" },
      { role: "worker", content: "Your backup job has a low risk score of 25. All checks passed.", workerName: "Risk Analysis Worker" },
    ],
  },
  {
    id: "chat-4",
    title: "API Integration Sync",
    preview: "Do I need approvals for this?",
    timestamp: "Feb 22",
    messages: [
      { role: "user", content: "Need help with API integration" },
      { role: "worker", content: "What endpoint will you be connecting to?", workerName: "Orchestration Worker" },
      { role: "user", content: "Do I need approvals for this?" },
      { role: "worker", content: "Yes, API integration requires data lead approval due to the medium risk score.", workerName: "Risk Analysis Worker" },
    ],
  },
  {
    id: "chat-5",
    title: "ETL Pipeline Configuration",
    preview: "When should this run?",
    timestamp: "Feb 21",
    messages: [
      { role: "user", content: "Setting up new ETL pipeline" },
      { role: "worker", content: "Let's configure your ETL job. What data sources will you use?", workerName: "Orchestration Worker" },
    ],
  },
];

// Helper function to generate unique thread ID
const generateThreadId = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `thread-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

// Helper function to derive title from first message (first 5 words + "…")
const deriveTitleFromMessage = (content: string): string => {
  const words = content.split(" ");
  if (words.length > 5) {
    return words.slice(0, 5).join(" ") + "…";
  }
  return content;
};

// Helper function to get timestamp
const getCurrentTimestamp = (): string => {
  const now = new Date();
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const messageDate = new Date(now);
  messageDate.setHours(0, 0, 0, 0);

  if (messageDate.getTime() === today.getTime()) {
    return "Today";
  }
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (messageDate.getTime() === yesterday.getTime()) {
    return "Yesterday";
  }
  return now.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

// Helper function to get header title based on active thread state
const getHeaderTitle = (activeThread: ChatThread | null | undefined): string => {
  if (!activeThread || activeThread.messages.length === 0) {
    return "Create a job";
  }
  if (activeThread.jobSpec?.name) {
    return activeThread.jobSpec.name;
  }
  return activeThread.title;
};

// Helper function to get icon based on jobSpec type
const getJobSpecIcon = (type?: string): React.ReactNode => {
  if (!type) return null;
  switch (type) {
    case "Airflow":
      return <Workflow className="h-5 w-5" />;
    case "Database":
      return <Database className="h-5 w-5" />;
    case "Script":
      return <Code2 className="h-5 w-5" />;
    case "ML":
      return <Brain className="h-5 w-5" />;
    case "API":
      return <Zap className="h-5 w-5" />;
    default:
      return null;
  }
};

// Mock data for panels
const mockApprovals = [
  { id: "1", approver: "Data Lead", role: "Data Governance", status: "pending" },
  { id: "2", approver: "Security Officer", role: "Compliance", status: "pending" },
];

const mockActivityLogs = [
  { id: "1", timestamp: "14:32", action: "Job created", details: "Daily Customer Report" },
  { id: "2", timestamp: "14:31", action: "Configuration updated", details: "Schedule set to daily" },
  { id: "3", timestamp: "14:30", action: "Risk assessment completed", details: "Risk score: 45 (Medium)" },
];

const jobSpecPreview = {
  name: "Daily Customer Report",
  type: "Airflow Pipeline",
  schedule: "0 6 * * *",
  notifications: {
    onSuccess: ["team@example.com"],
    onFailure: ["alerts@example.com"],
  },
  riskScore: 45,
  approvals: ["data-lead"],
};

// Panel configuration
interface PanelConfig {
  id: string;
  label: string;
  icon: React.ReactNode;
  component: () => React.ReactNode;
}

export default function CreateJob() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<JobTemplate>(jobTemplates[0]);
  const [jobName, setJobName] = useState("");
  const [message, setMessage] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [threads, setThreads] = useState<ChatThread[]>(mockChatThreads);
  const [activeThreadId, setActiveThreadId] = useState<string | null>("chat-1");
  const [openMenuThreadId, setOpenMenuThreadId] = useState<string | null>(null);
  const [activePanelId, setActivePanelId] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("createJobActivePanelId") || "workers";
    }
    return "workers";
  });
  const [isDockCollapsed, setIsDockCollapsed] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("createJobDockCollapsed") === "true";
    }
    return false;
  });

  // Current thread and messages (derived from state)
  const activeThread = activeThreadId ? threads.find((t) => t.id === activeThreadId) : null;
  const currentMessages = activeThread?.messages || [];

  const filteredChats = threads.filter((chat) =>
    chat.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    chat.preview.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelectChat = (chatId: string) => {
    setActiveThreadId(chatId);
  };

  const handleNewChat = () => {
    setActiveThreadId(null);
    setMessage("");
  };

  const handleSend = (messageText?: string) => {
    const textToSend = messageText || message;
    if (!textToSend.trim()) return;

    const userMessage: Message = { role: "user", content: textToSend };
    let currentThreadId = activeThreadId;

    // If no active thread (null), create a new thread
    if (activeThreadId === null) {
      const newThreadId = generateThreadId();
      currentThreadId = newThreadId;
      const newThread: ChatThread = {
        id: newThreadId,
        title: deriveTitleFromMessage(textToSend),
        preview: textToSend.substring(0, 60),
        timestamp: getCurrentTimestamp(),
        messages: [userMessage],
      };
      setThreads((prev) => [newThread, ...prev]);
      setActiveThreadId(newThreadId);
    } else {
      // Append to existing thread
      setThreads((prev) =>
        prev.map((t) =>
          t.id === activeThreadId
            ? { ...t, messages: [...t.messages, userMessage], timestamp: getCurrentTimestamp() }
            : t
        )
      );
    }

    setMessage("");

    // Simulate worker response after a delay
    setTimeout(() => {
      const workerMessage: Message = {
        role: "worker",
        content: "I've updated your job configuration. The risk analysis shows this job requires one approval.",
        workerName: "Risk Analysis Worker",
      };

      setThreads((prev) =>
        prev.map((t) =>
          t.id === currentThreadId
            ? { ...t, messages: [...t.messages, workerMessage] }
            : t
        )
      );
    }, 800);
  };

  // Update localStorage when panel or collapsed state changes
  const handleSetActivePanelId = (id: string) => {
    setActivePanelId(id);
    if (typeof window !== "undefined") {
      localStorage.setItem("createJobActivePanelId", id);
    }
  };

  const handleSetIsDockCollapsed = (collapsed: boolean) => {
    setIsDockCollapsed(collapsed);
    if (typeof window !== "undefined") {
      localStorage.setItem("createJobDockCollapsed", collapsed ? "true" : "false");
    }
  };

  // Helper functions for status colors (must be defined before use in panels)
  const getStatusColor = (status: AIWorker["status"]) => {
    switch (status) {
      case "Active": return "bg-green-500";
      case "Thinking": return "bg-yellow-500 animate-pulse";
      case "Idle": return "bg-gray-300";
    }
  };

  const getStatusTextColor = (status: AIWorker["status"]) => {
    switch (status) {
      case "Active": return "text-green-700";
      case "Thinking": return "text-yellow-700";
      case "Idle": return "text-gray-500";
    }
  };

  // Panel components (as functions to defer evaluation)
  const renderWorkersPanel = () => (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {aiWorkers.map((worker) => (
          <button key={worker.id} className="w-full rounded-lg border border-gray-200 bg-white p-4 text-left hover:border-[#ed0923] hover:shadow-md transition-all">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 text-gray-700 flex-shrink-0">{worker.icon}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-sm font-semibold text-gray-900 truncate">{worker.name}</h3>
                  <div className={`h-2 w-2 rounded-full flex-shrink-0 ${getStatusColor(worker.status)}`} />
                </div>
                <div className="text-xs text-gray-600 mb-2">{worker.role}</div>
                <div className={`text-xs font-medium ${getStatusTextColor(worker.status)}`}>{worker.status}</div>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="border-t border-gray-200 bg-gray-50 p-4">
        <div className="text-xs font-medium text-gray-700 mb-3 uppercase tracking-wide">Summary</div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-600">Active</span>
            <span className="font-semibold text-green-700">{aiWorkers.filter((w) => w.status === "Active").length}</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-600">Idle</span>
            <span className="font-semibold text-gray-500">{aiWorkers.filter((w) => w.status === "Idle").length}</span>
          </div>
        </div>
      </div>
    </div>
  );

  const renderApprovalsPanel = () => (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {mockApprovals.map((approval) => (
          <div key={approval.id} className="rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-100 text-yellow-700 flex-shrink-0">
                <Clock className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-gray-900">{approval.approver}</h3>
                <p className="text-xs text-gray-600">{approval.role}</p>
                <span className="inline-block mt-2 px-2 py-1 rounded text-xs font-medium bg-yellow-50 text-yellow-700">Pending</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderPreviewPanel = () => (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-4">
        <pre className="text-xs bg-gray-50 border border-gray-200 rounded p-3 overflow-x-auto">
          {JSON.stringify(jobSpecPreview, null, 2)}
        </pre>
      </div>
    </div>
  );

  const renderActivityPanel = () => (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {mockActivityLogs.map((log) => (
          <div key={log.id} className="flex gap-3 pb-3 border-b border-gray-100 last:border-0">
            <div className="flex-shrink-0 text-xs text-gray-500 font-medium w-12">{log.timestamp}</div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-gray-900 font-semibold">{log.action}</p>
              <p className="text-xs text-gray-600">{log.details}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const panels: PanelConfig[] = [
    { id: "workers", label: "Workers", icon: <Activity className="h-4 w-4" />, component: renderWorkersPanel },
    { id: "approvals", label: "Approvals", icon: <CheckCircle className="h-4 w-4" />, component: renderApprovalsPanel },
    { id: "preview", label: "Preview", icon: <Code className="h-4 w-4" />, component: renderPreviewPanel },
    { id: "activity", label: "Activity", icon: <Clock className="h-4 w-4" />, component: renderActivityPanel },
  ];

  const activePanel = panels.find((p) => p.id === activePanelId);

  const hasUserMessages = currentMessages.some((msg) => msg.role === "user");

  const handleDeleteThread = (threadId: string) => {
    if (!confirm("Delete this chat? This action cannot be undone.")) {
      return;
    }

    setThreads((prev) => prev.filter((t) => t.id !== threadId));
    setOpenMenuThreadId(null);

    // If deleted thread is active, switch to null (empty state) or next thread
    if (activeThreadId === threadId) {
      const remaining = threads.filter((t) => t.id !== threadId);
      setActiveThreadId(remaining.length > 0 ? remaining[0].id : null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation activePage="Create Job" onProfileClick={() => setIsProfileOpen(true)} />

      <div className="h-[calc(100vh-64px)] relative">
        <PanelGroup direction="horizontal">
          {/* Left Sidebar - Chats */}
          <Panel id="chats" order={1} defaultSize={20} minSize={15} maxSize={30}>
            <div className="h-full flex flex-col border-r border-gray-200 bg-white">
              {/* Header */}
              <div className="border-b border-gray-200 p-4">
                <h2 className="text-sm font-semibold text-gray-900 mb-3">Chats</h2>
                <Button
                  onClick={handleNewChat}
                  className="w-full gap-2 bg-gray-900 text-white hover:bg-gray-800 text-sm"
                >
                  <Plus className="h-4 w-4" />
                  New Chat
                </Button>
              </div>

              {/* Search */}
              <div className="px-4 py-3 border-b border-gray-200">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search chats..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg bg-gray-50 placeholder:text-gray-500 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                  />
                </div>
              </div>

              {/* Chat List */}
              <div className="flex-1 overflow-y-auto">
                {filteredChats.map((chat) => (
                  <div key={chat.id} className="relative border-b border-gray-100">
                    <button
                      onClick={() => handleSelectChat(chat.id)}
                      className={`w-full p-4 text-left transition-colors hover:bg-gray-50 group ${
                        activeThreadId === chat.id ? "bg-gray-100 border-l-4 border-l-[#ed0923] pl-3" : ""
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h3 className="text-sm font-semibold text-gray-900 flex-1 truncate">{chat.title}</h3>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenMenuThreadId(openMenuThreadId === chat.id ? null : chat.id);
                          }}
                          className="flex-shrink-0 p-1 text-gray-400 opacity-0 group-hover:opacity-100 hover:text-gray-600 transition-opacity"
                          aria-label="Thread actions"
                        >
                          <MoreVertical className="h-4 w-4" />
                        </button>
                      </div>
                      <p className="text-xs text-gray-600 truncate mb-2">{chat.preview}</p>
                      <p className="text-xs text-gray-500">{chat.timestamp}</p>
                    </button>

                    {/* Dropdown Menu */}
                    {openMenuThreadId === chat.id && (
                      <div className="absolute right-0 top-12 bg-white border border-gray-200 rounded-lg shadow-md z-50 w-48">
                        <button
                          onClick={() => {
                            handleDeleteThread(chat.id);
                          }}
                          className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2 transition-colors first:rounded-t-lg last:rounded-b-lg"
                        >
                          <Trash2 className="h-4 w-4" />
                          Delete chat
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </Panel>

          <PanelResizeHandle className="w-1 bg-gray-200 hover:bg-[#ed0923] transition-colors" />

          {/* Center - Job Workspace */}
          <Panel id="workspace" order={2} defaultSize={60} minSize={50}>
            <div className="h-full flex flex-col bg-white">
              {/* Header */}
              <div className="border-b border-gray-200 bg-white px-6 py-4">
                <div className="flex items-center gap-3 mb-2">
                  {activeThread?.jobSpec?.type && getJobSpecIcon(activeThread.jobSpec.type)}
                  <h1 className="text-2xl font-semibold text-gray-900">{getHeaderTitle(activeThread)}</h1>
                </div>
                <div className="flex items-center gap-3">
                  {activeThread?.jobSpec?.type && (
                    <span className="rounded-lg bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700">{activeThread.jobSpec.type}</span>
                  )}
                  {activeThread?.jobSpec?.riskScore !== undefined && (
                    <span className="rounded-lg bg-yellow-100 px-3 py-1 text-xs font-semibold text-yellow-700 border border-yellow-200">
                      {activeThread.jobSpec.riskLabel || "Medium"} Risk ({activeThread.jobSpec.riskScore})
                    </span>
                  )}
                </div>
              </div>

              {/* Chat + Form Split */}
              <div className="flex-1 flex overflow-hidden">
                {/* Chat Area */}
                <div className="flex-1 flex flex-col">
                  {!hasUserMessages ? (
                    // Empty State
                    <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
                      <h2 className="text-4xl font-semibold text-gray-900 mb-3 text-center">What do you want to automate?</h2>
                      <p className="text-lg text-gray-600 mb-12 text-center max-w-md">Describe a job and I'll turn it into a runnable workflow.</p>

                      {/* Suggestions Grid */}
                      <div className="grid grid-cols-2 gap-3 mb-8 w-full max-w-2xl">
                        {suggestions.map((suggestion, idx) => (
                          <button
                            key={idx}
                            onClick={() => handleSend(suggestion.text)}
                            className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4 text-left hover:border-[#ed0923] hover:bg-red-50 transition-all"
                          >
                            <span className="text-xl">{suggestion.icon}</span>
                            <span className="text-sm text-gray-700 font-medium">{suggestion.text}</span>
                          </button>
                        ))}
                      </div>

                      {/* Input Area */}
                      <div className="w-full max-w-[700px]">
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            onKeyPress={(e) => e.key === "Enter" && handleSend()}
                            placeholder="Ask about configuration or requirements..."
                            className="flex-1 rounded-lg border border-gray-200 px-4 py-3 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                          />
                          <Button onClick={() => handleSend()} disabled={!message.trim()} className="bg-[#ed0923] text-white hover:bg-[#d10820]">
                            <Send className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    // Chat Messages
                    <>
                      <div className="flex-1 overflow-y-auto p-6 space-y-4">
                        {currentMessages.map((msg, index) => (
                          <div key={index} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                            <div className={`max-w-[70%] rounded-lg p-4 ${msg.role === "user" ? "bg-[#ed0923] text-white" : "bg-gray-50 border border-gray-200 text-gray-900"}`}>
                              {msg.role === "worker" && msg.workerName && <div className="text-xs font-semibold mb-2 text-gray-600">{msg.workerName}</div>}
                              <p className="text-sm">{msg.content}</p>
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="border-t border-gray-200 bg-white p-4">
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            onKeyPress={(e) => e.key === "Enter" && handleSend()}
                            placeholder="Ask about configuration or requirements..."
                            className="flex-1 rounded-lg border border-gray-200 px-4 py-2 text-sm focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                          />
                          <Button onClick={() => handleSend()} disabled={!message.trim()} className="bg-[#ed0923] text-white hover:bg-[#d10820]">
                            <Send className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </Panel>

          <PanelResizeHandle className="w-1 bg-gray-200 hover:bg-[#ed0923] transition-colors" />

          {/* Right Sidebar - Docked Panels */}
          {!isDockCollapsed && (
            <>
              <Panel id="dock" order={3} defaultSize={20} minSize={18} maxSize={30}>
                <div className="h-full border-l border-gray-200 bg-white flex flex-col">
                  {/* Header with Tabs and Collapse Button */}
                  <div className="bg-white flex items-center justify-between px-4 py-3 border-b border-gray-200">
                    {/* Tabs - left side */}
                    <div className="flex items-center overflow-x-auto gap-1">
                      {panels.map((panel) => (
                        <button
                          key={panel.id}
                          onClick={() => handleSetActivePanelId(panel.id)}
                          className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-all whitespace-nowrap text-sm font-medium ${
                            activePanelId === panel.id
                              ? "border-b-[#ed0923] text-gray-900"
                              : "border-b-transparent text-gray-600 hover:text-gray-900"
                          }`}
                        >
                          {panel.icon}
                          {panel.label}
                        </button>
                      ))}
                    </div>

                    {/* Collapse Button - right side */}
                    <button
                      onClick={() => handleSetIsDockCollapsed(true)}
                      className="flex items-center justify-center h-8 w-8 rounded-full bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 shadow-sm transition-colors flex-shrink-0"
                      aria-label="Collapse dock"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>

                  {/* Panel Content */}
                  <div className="flex-1 overflow-hidden">{activePanel?.component()}</div>
                </div>
              </Panel>
            </>
          )}

          {/* Expand Button - When dock is collapsed */}
          {isDockCollapsed && (
            <button
              onClick={() => handleSetIsDockCollapsed(false)}
              className="absolute top-4 right-4 flex items-center justify-center h-8 w-8 rounded-full bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 shadow-sm transition-colors z-50"
              aria-label="Expand dock"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          )}
        </PanelGroup>
      </div>

      <UserProfilePanel isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </div>
  );
}
