import { useState, useRef, useCallback, KeyboardEvent } from "react";
import { ArrowUp, Square, Paperclip, Wrench } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop: () => void;
  isStreaming: boolean;
}

/**
 * Chat input with auto-resize, send button, and stop button.
 */
export function ChatInput({ onSend, onStop, isStreaming }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "44px";
    }
  }, [value, isStreaming, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleInput = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "44px";
      el.style.height = Math.min(el.scrollHeight, 160) + "px";
    }
  }, []);

  return (
    <div className="border-t border-surface px-6 py-4 shrink-0">
      <div className="max-w-3xl mx-auto flex items-end gap-3">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              handleInput();
            }}
            onKeyDown={handleKeyDown}
            className="w-full bg-surface border border-surface-el rounded-xl px-4 py-3 pl-20 text-sm resize-none font-sans text-text-p placeholder:text-text-m focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15 transition-all duration-200"
            rows={1}
            placeholder="Type a message... (Shift+Enter for new line)"
            style={{ minHeight: 44, maxHeight: 160 }}
            disabled={isStreaming}
          />
          <div className="absolute bottom-3 left-3 flex items-center gap-1">
            <button
              className="w-7 h-7 rounded-lg flex items-center justify-center text-text-m hover:text-text-s hover:bg-surface-el cursor-pointer transition-colors duration-200"
              title="Attach file"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <button
              className="w-7 h-7 rounded-lg flex items-center justify-center text-text-m hover:text-text-s hover:bg-surface-el cursor-pointer transition-colors duration-200"
              title="Select tool"
            >
              <Wrench className="w-4 h-4" />
            </button>
          </div>
        </div>

        {isStreaming ? (
          <button
            onClick={onStop}
            className="w-10 h-10 rounded-xl bg-red-500/20 border border-red-500/30 flex items-center justify-center cursor-pointer shrink-0 hover:bg-red-500/30 transition-colors duration-200"
            title="Stop generation (Cmd+.)"
          >
            <Square className="w-4 h-4 text-red-400" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!value.trim()}
            className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center cursor-pointer shrink-0 hover:bg-accent-hover transition-colors duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Send message"
          >
            <ArrowUp className="w-5 h-5 text-bg-deep" />
          </button>
        )}
      </div>
    </div>
  );
}
