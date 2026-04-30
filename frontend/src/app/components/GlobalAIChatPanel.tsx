import { X, Send, Sparkles, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import { useState } from "react";
import { useAI } from "../contexts/AIContext";
import { sendAgentMessage, type AgentChatMessage } from "../lib/controlCenterApi";

const examplePrompts = [
  "Show job trends",
  "Graph approval times",
  "Summarize risks",
  "Analyze recent job failures",
  "Compare this month vs last month",
  "Show top performing jobs",
];

export function GlobalAIChatPanel() {
  const { messages, addMessage, clearMessages, isAIChatOpen, setIsAIChatOpen } = useAI();
  const [message, setMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async (text: string) => {
    addMessage({ role: "user", content: text, timestamp: new Date() });

    const history: AgentChatMessage[] = messages.map((m) => ({
      role: m.role === "user" ? "user" : "assistant",
      content: m.content,
    }));

    setIsLoading(true);
    try {
      const result = await sendAgentMessage({ message: text, conversation_history: history });
      addMessage({ role: "ai", content: result.response, timestamp: new Date() });
    } catch (err) {
      addMessage({
        role: "ai",
        content: err instanceof Error ? err.message : "Something went wrong. Please try again.",
        timestamp: new Date(),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = () => {
    if (message.trim() && !isLoading) {
      const text = message.trim();
      setMessage("");
      sendMessage(text);
    }
  };

  const handlePromptClick = (prompt: string) => {
    if (!isLoading) sendMessage(prompt);
  };

  const handleClearChat = () => {
    if (confirm("Are you sure you want to clear the conversation history?")) {
      clearMessages();
    }
  };

  if (!isAIChatOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/30 transition-opacity"
        onClick={() => setIsAIChatOpen(false)}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 z-50 h-full w-full max-w-md bg-white shadow-2xl flex flex-col animate-slide-in-right">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#ed0923]">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">AI Assistant</h2>
              <p className="text-xs text-gray-500">Ask me anything about your data</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={handleClearChat}
                className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
                title="Clear conversation"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
            <button
              onClick={() => setIsAIChatOpen(false)}
              className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Example Prompts (shown when no messages) */}
        {messages.length === 0 && (
          <div className="p-6 space-y-4">
            <p className="text-sm font-medium text-gray-700">Try asking:</p>
            <div className="space-y-2">
              {examplePrompts.map((prompt, index) => (
                <button
                  key={index}
                  onClick={() => handlePromptClick(prompt)}
                  className="w-full rounded-lg border border-gray-200 bg-white p-4 text-left text-sm text-gray-700 hover:border-[#ed0923] hover:bg-red-50 transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
            <div className="mt-6 rounded-lg bg-gray-50 border border-gray-200 p-4">
              <p className="text-xs text-gray-600">
                💡 <span className="font-medium">Pro tip:</span> Your conversation history persists as you navigate between pages, so you can continue your analysis seamlessly.
              </p>
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4 flex flex-col">
          {messages.map((msg, index) => (
            <div
              key={index}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`rounded-lg p-4 text-sm flex-shrink-0 max-w-[85%] ${
                  msg.role === "user"
                    ? "bg-[#ed0923] text-white"
                    : "bg-gray-100 text-gray-900"
                }`}
              >
                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Loading indicator */}
        {isLoading && (
          <div className="px-6 pb-2 flex items-center gap-2 text-xs text-gray-400">
            <div className="flex gap-1">
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            CC Assistant is thinking…
          </div>
        )}

        {/* Input */}
        <div className="border-t border-gray-200 p-4 flex-shrink-0 w-full">
          <div className="flex gap-2 w-full">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSend()}
              placeholder="Type your message..."
              disabled={isLoading}
              className="flex-1 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923] min-w-0 disabled:opacity-60"
            />
            <Button
              onClick={handleSend}
              disabled={!message.trim() || isLoading}
              className="h-auto rounded-lg bg-[#ed0923] px-4 py-3 hover:bg-[#d10820] disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
            >
              <Send className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
