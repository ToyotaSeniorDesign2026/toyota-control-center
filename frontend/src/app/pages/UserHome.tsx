import { useState } from "react";
import { Send, Sparkles, PenSquare } from "lucide-react";
import { Button } from "../components/ui/button";
import { UserNavigation } from "../components/UserNavigation";
import { UserProfilePanel } from "../components/user/UserProfilePanel";
import { ManualResourceCreationModal } from "../components/ManualResourceCreationModal";

const suggestedPrompts = [
  "Create a SQL query to analyze customer churn",
  "Build an AI agent to summarize support tickets",
  "Set up a dbt model for daily sales metrics",
  "Connect to our CRM API for data sync",
];

export default function UserHome() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<
    Array<{ role: "user" | "ai"; content: string }>
  >([]);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);

  const handleSend = () => {
    if (message.trim()) {
      setMessages([...messages, { role: "user", content: message }]);
      setMessage("");

      // Simulate AI response
      setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            role: "ai",
            content:
              "I'll help you create that resource. Let me guide you through the process step by step. First, what would you like to name this resource?",
          },
        ]);
      }, 1000);
    }
  };

  const handlePromptClick = (prompt: string) => {
    setMessages([...messages, { role: "user", content: prompt }]);

    // Simulate AI response
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          role: "ai",
          content:
            "Great choice! I'll help you create that. Let me gather a few details to get started. What would you like to name this resource?",
        },
      ]);
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <UserNavigation
        activePage="Dashboard"
        onProfileClick={() => setIsProfileOpen(true)}
      />
      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <div className="space-y-6">
          {/* Page Header */}
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Create Resource with AI</h1>
            <p className="mt-1 text-sm text-gray-600">
              Describe what you need and I'll guide you through creating it step by step
            </p>
          </div>

          {/* AI Creation Section */}
          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 bg-gradient-to-r from-[#ed0923]/5 to-transparent p-6">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#ed0923]">
                  <Sparkles className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-semibold text-gray-900">
                    AI Resource Assistant
                  </h2>
                  <p className="text-sm text-gray-600">
                    Create SQL queries, AI agents, dbt models, and API connections
                  </p>
                </div>
              </div>
            </div>

            <div className="p-6">
              {/* Messages */}
              {messages.length > 0 && (
                <div className="mb-4 max-h-[600px] space-y-4 overflow-y-auto rounded-lg border border-gray-200 bg-gray-50 p-4">
                  {messages.map((msg, index) => (
                    <div
                      key={index}
                      className={`flex ${
                        msg.role === "user" ? "justify-end" : "justify-start"
                      }`}
                    >
                      <div
                        className={`max-w-[80%] rounded-lg px-4 py-3 ${
                          msg.role === "user"
                            ? "bg-[#ed0923] text-white"
                            : "bg-white border border-gray-200 text-gray-900"
                        }`}
                      >
                        <p className="text-sm">{msg.content}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Suggested Prompts - Only show when no messages */}
              {messages.length === 0 && (
                <div className="mb-4">
                  <p className="mb-3 text-sm font-medium text-gray-700">
                    Try asking:
                  </p>
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {suggestedPrompts.map((prompt, index) => (
                      <button
                        key={index}
                        onClick={() => handlePromptClick(prompt)}
                        className="rounded-lg border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 transition-colors hover:border-[#ed0923] hover:bg-red-50"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="What would you like to create?"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  className="flex-1 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923]"
                />
                <Button
                  onClick={handleSend}
                  disabled={!message.trim()}
                  className="h-auto gap-2 bg-[#ed0923] px-6 py-3 text-white hover:bg-[#d10820]"
                >
                  <Send className="h-4 w-4" />
                  Send
                </Button>
              </div>
            </div>
          </div>

          {/* Manual Resource Creation Section */}
          <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white shadow-sm">
            <div className="p-6">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100 border border-gray-200">
                    <PenSquare className="h-5 w-5 text-gray-600" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">
                      Manual Resource Creation
                    </h2>
                    <p className="text-sm text-gray-600 mt-1">
                      Prefer to fill out a form? Create your resource step-by-step
                    </p>
                  </div>
                </div>
                <Button
                  onClick={() => setIsManualModalOpen(true)}
                  className="gap-2 bg-gray-900 text-white hover:bg-gray-800"
                >
                  <PenSquare className="h-4 w-4" />
                  Create Manually
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>

      <UserProfilePanel
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
      />

      <ManualResourceCreationModal
        isOpen={isManualModalOpen}
        onClose={() => setIsManualModalOpen(false)}
      />
    </div>
  );
}
