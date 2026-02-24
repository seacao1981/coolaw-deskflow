import { useAppStore } from "../../stores/appStore";
import { useChatStore } from "../../stores/chatStore";

/**
 * Bottom status bar showing connection, model, and memory info.
 */
export function StatusBar() {
  const isConnected = useAppStore((s) => s.isConnected);
  const isStreaming = useChatStore((s) => s.isStreaming);

  return (
    <div className="h-7 bg-bg-deep border-t border-surface flex items-center px-4 text-xs text-text-m shrink-0 select-none">
      <div className="flex items-center gap-1.5">
        <span
          className={`w-2 h-2 rounded-full ${isConnected ? "bg-accent" : "bg-error"}`}
        />
        <span>{isConnected ? "Connected" : "Disconnected"}</span>
      </div>
      <span className="mx-3 text-surface-el">|</span>
      <span>Model: claude-3.5-sonnet</span>
      <span className="mx-3 text-surface-el">|</span>
      <span>Tools: 3 available</span>
      {isStreaming && (
        <>
          <span className="mx-3 text-surface-el">|</span>
          <span className="text-accent">Generating...</span>
        </>
      )}
      <span className="ml-auto font-code">v0.1.0</span>
    </div>
  );
}
