import { Brain } from "lucide-react";

/**
 * Tauri-compatible title bar with drag region and window controls.
 */
export function TitleBar() {
  return (
    <div
      className="h-10 bg-bg-deep border-b border-surface flex items-center px-4 shrink-0 select-none"
      data-tauri-drag-region
    >
      <div className="flex items-center gap-2" data-tauri-drag-region="false">
        <div className="w-3 h-3 rounded-full bg-red-500 cursor-pointer hover:brightness-110 transition-all duration-200" />
        <div className="w-3 h-3 rounded-full bg-yellow-500 cursor-pointer hover:brightness-110 transition-all duration-200" />
        <div className="w-3 h-3 rounded-full bg-green-500 cursor-pointer hover:brightness-110 transition-all duration-200" />
      </div>
      <div className="ml-4 flex items-center gap-2">
        <Brain className="w-4 h-4 text-accent" />
        <span className="text-text-s text-xs font-code">Coolaw DeskFlow</span>
      </div>
      <span className="ml-auto text-text-m text-xs font-code">v0.1.0</span>
    </div>
  );
}
