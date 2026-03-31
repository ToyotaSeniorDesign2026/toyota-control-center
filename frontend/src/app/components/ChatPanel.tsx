import { MessageSquare, X, Send, Clock, Plus, XCircle } from "lucide-react";
import { useState, useRef, useEffect } from "react";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
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

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
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
    content: "What would you like help with today? You can ask me to:\n• Create a new job\n• Troubleshoot errors\n• Explain features\n• Draft job specifications",
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

export function ChatPanel({ isOpen, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [inputValue, setInputValue] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatThread[]>(mockChatHistory);
  const [selectedModel, setSelectedModel] = useState("GPT-4o");
  const [isDragOverInput, setIsDragOverInput] = useState(false);
  const [attachedItems, setAttachedItems] = useState<AttachedItem[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-adjust textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 300) + "px";
    }
  }, [inputValue]);

  const handleSendMessage = () => {
    if (!inputValue.trim() && attachedItems.length === 0) return;

    const messageContent = attachedItems.length > 0
      ? `${inputValue}\n\n[Attached: ${attachedItems.map(item => item.name).join(", ")}]`
      : inputValue;

    const newUserMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: messageContent,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, newUserMessage]);
    setInputValue("");
    setAttachedItems([]);

    // Simulate assistant response
    setTimeout(() => {
      const assistantResponse: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content:
          "I understand. In a production environment, I would process your request using AI models to help you with job creation, troubleshooting, and workflow optimization.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantResponse]);
    }, 1000);
  };

  const handleNewChat = () => {
    setMessages(initialMessages);
    setInputValue("");
    setAttachedItems([]);
    setShowHistory(false);
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
              <div
                className={`rounded-lg px-4 py-3 text-sm flex-shrink-0 max-w-[90%] shadow-sm ${
                  message.role === "user"
                    ? "bg-[#ed0923] text-white rounded-br-none"
                    : "bg-gray-100 text-gray-900 rounded-bl-none"
                }`}
              >
                <p className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</p>
              </div>
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
              disabled={!inputValue.trim() && attachedItems.length === 0}
              className="rounded-lg bg-[#ed0923] px-3 py-2 text-white hover:bg-[#d10820] disabled:bg-gray-300 disabled:cursor-not-allowed transition flex-shrink-0 font-medium text-xs"
              title="Send message (Shift+Enter for new line)"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Model Selector */}
        <div className="flex items-center gap-3 pt-1">
          <label className="text-xs text-gray-700 font-medium">Model:</label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="flex-1 text-xs border border-gray-300 rounded-md px-3 py-2 text-gray-700 bg-white focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923] transition"
          >
            <option value="GPT-4.1">GPT-4.1</option>
            <option value="GPT-4o">GPT-4o</option>
            <option value="Claude-3.7">Claude 3.7</option>
            <option value="Gemini-2.0">Gemini 2.0</option>
          </select>
        </div>
      </div>
    </aside>
  );
}
