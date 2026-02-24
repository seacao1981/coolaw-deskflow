import { Brain, User, CheckCircle, Loader2, XCircle, Copy, ChevronDown } from "lucide-react";
import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import type { ChatMessage, ToolCallInfo, ToolResultInfo } from "../../types";

interface MessageBubbleProps {
  message: ChatMessage;
}

/** Renders a single chat message bubble (user or assistant). */
export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === "user") {
    return <UserBubble content={message.content} timestamp={message.timestamp} />;
  }
  return (
    <AssistantBubble
      content={message.content}
      timestamp={message.timestamp}
      toolCalls={message.toolCalls}
      toolResults={message.toolResults}
      isStreaming={message.isStreaming}
    />
  );
}

function UserBubble({ content, timestamp }: { content: string; timestamp: number }) {
  return (
    <div className="flex gap-3 max-w-3xl ml-auto flex-row-reverse">
      <div className="w-8 h-8 rounded-full bg-surface-el flex items-center justify-center shrink-0 mt-1">
        <User className="w-4 h-4 text-text-s" />
      </div>
      <div className="flex-1 flex flex-col items-end">
        <div className="bg-accent/10 border border-accent/20 rounded-xl rounded-tr-sm px-4 py-3 max-w-full">
          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{content}</p>
        </div>
        <TimeStamp ts={timestamp} />
      </div>
    </div>
  );
}

function AssistantBubble({
  content,
  timestamp,
  toolCalls,
  toolResults,
  isStreaming,
}: {
  content: string;
  timestamp: number;
  toolCalls?: ToolCallInfo[];
  toolResults?: ToolResultInfo[];
  isStreaming?: boolean;
}) {
  // 过滤掉 think 标签内容（Claude 思考过程）
  const filteredContent = content.replace(/<think>[\s\S]*?<\/think>/g, '').trim();

  // Generate stable unique keys for tool calls
  const getToolCallKey = (tc: ToolCallInfo, index: number): string => {
    // Always prefer tool_call.id if available (it's unique across all tool calls)
    if (tc.id) {
      return tc.id;
    }
    // Fallback: use name + index + timestamp
    return `${tc.name}-${index}-${timestamp}`;
  };

  return (
    <div className="flex gap-3 max-w-3xl">
      <div className="w-8 h-8 rounded-lg bg-surface flex items-center justify-center shrink-0 mt-1">
        <Brain className="w-4 h-4 text-accent" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="bg-surface border border-surface-el rounded-xl rounded-tl-sm px-4 py-3">
          {/* Tool call cards */}
          {toolCalls && toolCalls.length > 0 && (
            <div className="space-y-2 mb-3">
              {toolCalls.map((tc, i) => {
                // 通过 tool_call_id 匹配对应的 result
                const matchedResult = toolResults?.find(r => r.tool_call_id === tc.id);
                return (
                  <ToolCallCard key={getToolCallKey(tc, i)} toolCall={tc} result={matchedResult} />
                );
              })}
            </div>
          )}

          {/* Message content */}
          <div className="prose-sm text-sm leading-relaxed">
            <ReactMarkdown
              components={{
                code: ({ children, className }) => {
                  const isBlock = className?.includes("language-");
                  if (isBlock) {
                    return <CodeBlock language={className?.replace("language-", "")}>{String(children)}</CodeBlock>;
                  }
                  return (
                    <code className="bg-bg-deep px-1.5 py-0.5 rounded text-xs font-code text-accent">
                      {children}
                    </code>
                  );
                },
                p: ({ children }) => <p className="text-text-p mb-2 last:mb-0">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside text-text-s mb-2 space-y-1">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside text-text-s mb-2 space-y-1">{children}</ol>,
                li: ({ children }) => <li className="text-sm">{children}</li>,
                strong: ({ children }) => <strong className="text-text-p font-semibold">{children}</strong>,
                h3: ({ children }) => <h3 className="text-sm font-semibold font-code text-text-p mt-3 mb-1">{children}</h3>,
              }}
            >
              {filteredContent}
            </ReactMarkdown>
          </div>

          {/* Streaming cursor */}
          {isStreaming && (
            <span className="inline-block w-2 h-4 bg-accent animate-blink ml-0.5 align-middle" />
          )}
        </div>
        <TimeStamp ts={timestamp} />
      </div>
    </div>
  );
}

function ToolCallCard({ toolCall, result }: { toolCall: ToolCallInfo; result?: ToolResultInfo }) {
  const [expanded, setExpanded] = useState(true); // 默认展开，方便查看结果
  const isRunning = toolCall.status === "running";
  const isFailed = toolCall.status === "failed" || (result && !result.success);

  // 始终显示内容区域，根据 result 是否存在显示不同信息
  const displayContent = result ? (result.success ? result.output : result.error) : (isRunning ? "执行中..." : "无结果");

  return (
    <div className="bg-bg-deep border border-surface rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-surface/50 transition-colors duration-200 cursor-pointer"
        title={expanded ? "点击收起详情" : "点击展开详情"}
      >
        {isRunning ? (
          <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />
        ) : isFailed ? (
          <XCircle className="w-4 h-4 text-error shrink-0" />
        ) : (
          <CheckCircle className="w-4 h-4 text-accent shrink-0" />
        )}
        <span className="text-xs font-code text-accent shrink-0">{toolCall.name}</span>
        {result && (
          <span className="text-xs font-code text-text-m">
            {result.duration_ms.toFixed(0)}ms
          </span>
        )}
        <span className="ml-auto text-xs text-text-m opacity-60">
          {expanded ? "收起" : "展开"}
        </span>
        <ChevronDown
          className={`w-3 h-3 text-text-m transition-transform duration-200 shrink-0 ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded && (
        <div className="px-3 py-2 border-t border-surface text-xs font-code text-text-s max-h-40 overflow-y-auto whitespace-pre-wrap">
          {displayContent}
        </div>
      )}
    </div>
  );
}

function CodeBlock({ children, language }: { children: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [children]);

  return (
    <div className="relative group my-2">
      <div className="bg-bg-deep border border-surface rounded-lg overflow-hidden">
        {language && (
          <div className="px-3 py-1 border-b border-surface text-xs text-text-m font-code">
            {language}
          </div>
        )}
        <pre className="px-3 py-2 overflow-x-auto">
          <code className="text-xs font-code text-slate-300 leading-relaxed">{children}</code>
        </pre>
      </div>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 w-7 h-7 rounded flex items-center justify-center text-text-m hover:text-text-p hover:bg-surface cursor-pointer opacity-0 group-hover:opacity-100 transition-all duration-200"
        title="Copy code"
      >
        {copied ? (
          <CheckCircle className="w-3.5 h-3.5 text-accent" />
        ) : (
          <Copy className="w-3.5 h-3.5" />
        )}
      </button>
    </div>
  );
}

function TimeStamp({ ts }: { ts: number }) {
  const date = new Date(ts);
  const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return <span className="text-xs text-text-m mt-1 inline-block">{time}</span>;
}
