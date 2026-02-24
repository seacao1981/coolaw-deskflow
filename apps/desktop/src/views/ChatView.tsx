import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Brain } from "lucide-react";
import { useChatStore } from "../stores/chatStore";
import { useChat } from "../hooks/useChat";
import { MessageBubble } from "../components/chat/MessageBubble";
import { ChatInput } from "../components/chat/ChatInput";

export default function ChatView() {
  const { t } = useTranslation();
  const messages = useChatStore((s) => s.messages);
  const { sendMessage, stopGeneration, isStreaming, connect } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-connect to backend on mount
  useEffect(() => {
    const ws = connect();
    return () => {
      ws.close();
    };
  }, [connect]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
        {messages.length === 0 && <EmptyState t={t} />}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <ChatInput onSend={sendMessage} onStop={stopGeneration} isStreaming={isStreaming} />
    </div>
  );
}

function EmptyState({ t }: { t: (key: string) => string }) {
  return (
    <div className="flex-1 flex items-center justify-center min-h-[300px]">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
          <Brain className="w-8 h-8 text-accent" />
        </div>
        <h2 className="text-lg font-semibold font-code mb-2">{t("chat.agentName")}</h2>
        <p className="text-sm text-text-s leading-relaxed">
          {t("chat.agentDescription")}
        </p>
      </div>
    </div>
  );
}
