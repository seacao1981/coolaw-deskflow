/** Shared TypeScript types for the DeskFlow frontend. */

export type ViewName = "chat" | "skills" | "monitor" | "settings" | "imchannels";

export interface StreamChunk {
  type: "conversation_id" | "text" | "tool_start" | "tool_end" | "tool_result" | "error" | "done";
  content?: string;
  tool_call?: ToolCallInfo;
  tool_result?: ToolResultInfo;
}

export interface ToolCallInfo {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "pending" | "running" | "completed" | "failed";
}

export interface ToolResultInfo {
  tool_call_id: string;
  tool_name: string;
  success: boolean;
  output: string;
  error?: string;
  duration_ms: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  toolCalls?: ToolCallInfo[];
  toolResults?: ToolResultInfo[];
  isStreaming?: boolean;
}

export interface AgentStatus {
  is_online: boolean;
  is_busy: boolean;
  current_task: string | null;
  uptime_seconds: number;
  total_conversations: number;
  total_tool_calls: number;
  total_tokens_used: number;
  memory_count: number;
  active_tools: number;
  available_tools: number;
  llm_provider: string;
  llm_model: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  components: Record<string, { status: string; details: Record<string, unknown> }>;
}

export interface SkillInfo {
  name: string;
  description: string;
  type: "system" | "user" | "auto-gen";
  version: string;
  isActive: boolean;
  icon: string;
  color: string;
}
