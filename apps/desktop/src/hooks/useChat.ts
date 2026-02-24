import { useCallback, useRef } from "react";
import { useChatStore } from "../stores/chatStore";
import { useAppStore } from "../stores/appStore";
import type { StreamChunk } from "../types";

/**
 * Hook for managing WebSocket chat connection and message sending.
 */
export function useChat() {
  const wsRef = useRef<WebSocket | null>(null);
  const pendingMessageRef = useRef<{ message: string; conversationId: string | null } | null>(null);
  const serverUrl = useAppStore((s) => s.serverUrl);
  const setConnected = useAppStore((s) => s.setConnected);

  const {
    conversationId,
    addUserMessage,
    startAssistantMessage,
    appendToLastMessage,
    addToolCallToLastMessage,
    addToolResultToLastMessage,
    finishStreaming,
    isStreaming,
    setConversationId,
  } = useChatStore();

  const handleChunk = useCallback(
    (chunk: StreamChunk) => {
      console.log('[useChat] Received chunk:', chunk.type, chunk);
      switch (chunk.type) {
        case "conversation_id":
          // 保存后端返回的 conversation_id
          if (chunk.content) {
            setConversationId(chunk.content);
          }
          break;
        case "text":
          appendToLastMessage(chunk.content || "");
          break;
        case "tool_start":
          if (chunk.tool_call) {
            addToolCallToLastMessage(chunk.tool_call);
          }
          break;
        case "tool_end":
          if (chunk.tool_call) {
            addToolCallToLastMessage({
              ...chunk.tool_call,
              status: "completed",
            });
          }
          break;
        case "tool_result":
          if (chunk.tool_result) {
            addToolResultToLastMessage(chunk.tool_result);
          }
          break;
        case "error":
          appendToLastMessage(`\n\n**Error:** ${chunk.content || "Unknown error"}`);
          finishStreaming();
          break;
        case "done":
          finishStreaming();
          break;
      }
    },
    [appendToLastMessage, addToolCallToLastMessage, addToolResultToLastMessage, finishStreaming, setConversationId]
  );

  const sendPendingMessage = useCallback(() => {
    const ws = wsRef.current;
    const pending = pendingMessageRef.current;
    console.log('[useChat] sendPendingMessage:', pending);
    if (ws && ws.readyState === WebSocket.OPEN && pending) {
      ws.send(JSON.stringify({
        message: pending.message,
        conversation_id: pending.conversationId,
      }));
      pendingMessageRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    const wsUrl = serverUrl.replace("http", "ws") + "/api/chat/stream";
    console.log('[useChat] Connecting to:', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[useChat] WebSocket connected');
      setConnected(true);
      // Send pending message if exists
      sendPendingMessage();
    };

    ws.onclose = () => {
      console.log('[useChat] WebSocket closed');
      setConnected(false);
      wsRef.current = null;
    };

    ws.onerror = () => {
      console.log('[useChat] WebSocket error');
      setConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const chunk: StreamChunk = JSON.parse(event.data);
        handleChunk(chunk);
      } catch (e) {
        console.error('[useChat] Failed to parse chunk:', e);
      }
    };

    wsRef.current = ws;
    return ws;
  }, [serverUrl, setConnected, handleChunk, sendPendingMessage]);

  const sendMessage = useCallback(
    (content: string) => {
      console.log('[useChat] sendMessage called, isStreaming:', isStreaming, 'content:', content);
      if (!content.trim() || isStreaming) {
        console.log('[useChat] Aborting send: content empty or streaming');
        return;
      }

      addUserMessage(content);
      startAssistantMessage();

      let ws = wsRef.current;
      console.log('[useChat] WebSocket state:', ws?.readyState);
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        // Store pending message and connect
        console.log('[useChat] WebSocket not ready, storing pending message');
        pendingMessageRef.current = {
          message: content,
          conversationId: conversationId,
        };
        connect();
      } else {
        console.log('[useChat] Sending message via WebSocket');
        ws.send(JSON.stringify({
          message: content,
          conversation_id: conversationId,
        }));
      }
    },
    [isStreaming, conversationId, addUserMessage, startAssistantMessage, connect]
  );

  const stopGeneration = useCallback(() => {
    // Close and reconnect to stop streaming
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    finishStreaming();
  }, [finishStreaming]);

  return { sendMessage, stopGeneration, connect, isStreaming };
}
