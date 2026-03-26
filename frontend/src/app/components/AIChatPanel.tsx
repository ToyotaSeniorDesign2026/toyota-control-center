import { X, Send, Sparkles } from "lucide-react";
import { Button } from "./ui/button";
import { useState } from "react";

interface AIChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const examplePrompts = [
  "Show job trends",
  "Graph approval times",
  "Summarize risks",
];

export function AIChatPanel({ isOpen, onClose }: AIChatPanelProps) {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<Array<{ role: "user" | "ai"; content: string }>>([]);

  const handleSend = () => {
    if (message.trim()) {
      setMessages([...messages, { role: "user", content: message }]);
      setMessage("");
      
      // Simulate AI response
      setTimeout(() => {
        setMessages(prev => [...prev, { 
          role: "ai", 
          content: "I'm analyzing your request. This is a demo response from the AI assistant." 
        }]);
      }, 1000);
    }
  };

  const handlePromptClick = (prompt: string) => {
    setMessages([...messages, { role: "user", content: prompt }]);
    
    // Simulate AI response
    setTimeout(() => {
      setMessages(prev => [...prev, { 
        role: "ai", 
        content: `I'm processing your request: "${prompt}". This is a demo response.` 
      }]);
    }, 1000);
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/30 transition-opacity"
        onClick={onClose}
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
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
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

        {/* Input */}
        <div className="border-t border-gray-200 p-4 flex-shrink-0 w-full">
          <div className="flex gap-2 w-full">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSend()}
              placeholder="Type your message..."
              className="flex-1 rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm placeholder:text-gray-400 focus:border-[#ed0923] focus:outline-none focus:ring-1 focus:ring-[#ed0923] min-w-0"
            />
            <Button
              onClick={handleSend}
              className="h-auto rounded-lg bg-[#ed0923] px-4 py-3 hover:bg-[#d10820] flex-shrink-0"
            >
              <Send className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
