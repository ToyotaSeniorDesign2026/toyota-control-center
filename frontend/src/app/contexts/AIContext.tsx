import { createContext, useContext, useState, ReactNode } from "react";

interface Message {
  role: "user" | "ai";
  content: string;
  timestamp: Date;
}

interface AIContextType {
  messages: Message[];
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  isAIChatOpen: boolean;
  setIsAIChatOpen: (open: boolean) => void;
}

const AIContext = createContext<AIContextType | undefined>(undefined);

export function AIProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isAIChatOpen, setIsAIChatOpen] = useState(false);

  const addMessage = (message: Message) => {
    setMessages((prev) => [...prev, message]);
  };

  const clearMessages = () => {
    setMessages([]);
  };

  return (
    <AIContext.Provider
      value={{
        messages,
        addMessage,
        clearMessages,
        isAIChatOpen,
        setIsAIChatOpen,
      }}
    >
      {children}
    </AIContext.Provider>
  );
}

export function useAI() {
  const context = useContext(AIContext);
  if (context === undefined) {
    throw new Error("useAI must be used within an AIProvider");
  }
  return context;
}
