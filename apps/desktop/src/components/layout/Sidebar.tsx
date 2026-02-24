import {
  MessageSquare,
  Puzzle,
  Activity,
  Settings,
  User,
  Brain,
  PanelLeft,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useAppStore } from "../../stores/appStore";
import type { ViewName } from "../../types";

interface NavItem {
  view: ViewName;
  labelKey: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { view: "chat", labelKey: "nav.chat", icon: <MessageSquare className="w-5 h-5" /> },
  { view: "skills", labelKey: "nav.skills", icon: <Puzzle className="w-5 h-5" /> },
  { view: "monitor", labelKey: "nav.monitor", icon: <Activity className="w-5 h-5" /> },
  { view: "settings", labelKey: "nav.settings", icon: <Settings className="w-5 h-5" /> },
];

/**
 * Left sidebar navigation with expand/collapse.
 */
export function Sidebar() {
  const { t } = useTranslation();
  const currentView = useAppStore((s) => s.currentView);
  const setCurrentView = useAppStore((s) => s.setCurrentView);
  const expanded = useAppStore((s) => s.sidebarExpanded);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);

  return (
    <aside
      className={`bg-bg-deep border-r border-surface flex flex-col shrink-0 transition-all duration-200 ${
        expanded ? "w-56" : "w-14"
      }`}
    >
      {/* Logo */}
      <div className="px-3 py-4 border-b border-surface">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
            <Brain className="w-5 h-5 text-bg-deep" />
          </div>
          {expanded && (
            <div className="min-w-0">
              <div className="text-sm font-semibold font-code text-text-p">Coolaw DeskFlow</div>
              <div className="text-xs text-text-m truncate">AI Agent Framework</div>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 px-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = currentView === item.view;
          return (
            <button
              key={item.view}
              onClick={() => setCurrentView(item.view)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-200 ${
                isActive
                  ? "bg-accent-dim border-l-2 border-accent"
                  : "hover:bg-surface border-l-2 border-transparent"
              }`}
              title={t(item.labelKey)}
            >
              <span className={isActive ? "text-accent" : "text-text-s"}>
                {item.icon}
              </span>
              {expanded && (
                <span
                  className={`text-sm ${
                    isActive ? "text-text-p font-medium" : "text-text-s"
                  }`}
                >
                  {t(item.labelKey)}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom: User + Collapse */}
      <div className="px-2 py-3 border-t border-surface space-y-1">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-8 h-8 rounded-full bg-surface-el flex items-center justify-center shrink-0">
            <User className="w-4 h-4 text-text-s" />
          </div>
          {expanded && (
            <div className="flex-1 min-w-0">
              <div className="text-sm text-text-p truncate">{t("nav.user") || "User"}</div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-accent animate-pulse-dot" />
                <span className="text-xs text-text-m">{t("status.online") || "Online"}</span>
              </div>
            </div>
          )}
        </div>
        <button
          onClick={toggleSidebar}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer text-text-m hover:bg-surface hover:text-text-s transition-all duration-200"
          title={expanded ? (t("sidebar.collapse") || "Collapse sidebar") : (t("sidebar.expand") || "Expand sidebar")}
        >
          <PanelLeft className={`w-5 h-5 transition-transform duration-200 ${expanded ? "" : "rotate-180"}`} />
          {expanded && <span className="text-sm">{t("sidebar.collapse") || "Collapse"}</span>}
        </button>
      </div>
    </aside>
  );
}
