import { MessageSquare } from "lucide-react";
import { useAI } from "../contexts/AIContext";

export function FloatingAIButton() {
  const { setIsAIChatOpen, messages } = useAI();

  return (
    <button
      onClick={() => setIsAIChatOpen(true)}
      className="fixed bottom-8 right-8 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-[#ed0923] text-white shadow-lg hover:bg-[#d10820] hover:shadow-xl transition-all hover:scale-110 group"
      aria-label="Open AI Assistant"
    >
      <MessageSquare className="h-6 w-6" />
      {messages.length > 0 && (
        <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-xs font-bold text-white border-2 border-white">
          {messages.length > 9 ? "9+" : messages.length}
        </span>
      )}
      <span className="absolute right-full mr-3 whitespace-nowrap rounded-lg bg-gray-900 px-3 py-2 text-sm font-medium text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        Ask AI Assistant
      </span>
    </button>
  );
}
