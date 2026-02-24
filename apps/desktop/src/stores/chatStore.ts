import { create } from "zustand";
import type { ChatMessage, ToolCallInfo, ToolResultInfo } from "../types";

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  conversationId: string | null;
  addUserMessage: (content: string) => string;
  startAssistantMessage: () => string;
  appendToLastMessage: (text: string) => void;
  addToolCallToLastMessage: (toolCall: ToolCallInfo) => void;
  addToolResultToLastMessage: (result: ToolResultInfo) => void;
  finishStreaming: () => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;
  setConversationId: (id: string) => void;
}

// Use timestamp + counter for unique IDs (more robust against HMR resets)
let nextId = 1;
const makeId = () => `msg-${Date.now()}-${nextId++}`;

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  conversationId: null,

  addUserMessage: (content: string) => {
    const id = makeId();
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id,
          role: "user",
          content,
          timestamp: Date.now(),
        },
      ],
    }));
    return id;
  },

  startAssistantMessage: () => {
    const id = makeId();
    set((s) => ({
      isStreaming: true,
      messages: [
        ...s.messages,
        {
          id,
          role: "assistant",
          content: "",
          timestamp: Date.now(),
          toolCalls: [],
          toolResults: [],
          isStreaming: true,
        },
      ],
    }));
    return id;
  },

  appendToLastMessage: (text: string) => {
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, content: last.content + text };
      }
      return { messages: msgs };
    });
  },

  addToolCallToLastMessage: (toolCall: ToolCallInfo) => {
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        const existingCalls = last.toolCalls || [];
        // 如果已存在相同 ID 的 toolCall，则更新它
        const existingIndex = existingCalls.findIndex(tc => tc.id === toolCall.id);
        let newToolCalls;
        if (existingIndex >= 0) {
          // 更新已存在的 toolCall
          newToolCalls = [...existingCalls];
          newToolCalls[existingIndex] = toolCall;
        } else {
          // 添加新的 toolCall
          newToolCalls = [...existingCalls, toolCall];
        }
        msgs[msgs.length - 1] = {
          ...last,
          toolCalls: newToolCalls,
        };
      }
      return { messages: msgs };
    });
  },

  addToolResultToLastMessage: (result: ToolResultInfo) => {
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = {
          ...last,
          toolResults: [...(last.toolResults || []), result],
        };
      }
      return { messages: msgs };
    });
  },

  finishStreaming: () => {
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "assistant") {
        msgs[msgs.length - 1] = { ...last, isStreaming: false };
      }
      return { messages: msgs, isStreaming: false };
    });
  },

  setStreaming: (streaming: boolean) => set({ isStreaming: streaming }),

  clearMessages: () => set({ messages: [], conversationId: null }),

  setConversationId: (id: string) => set({ conversationId: id }),
}));
