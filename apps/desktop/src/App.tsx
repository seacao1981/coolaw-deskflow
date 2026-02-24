import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { TitleBar } from "./components/layout/TitleBar";
import { Sidebar } from "./components/layout/Sidebar";
import { StatusBar } from "./components/layout/StatusBar";
import { useAppStore } from "./stores/appStore";
import { useLocaleStore } from "./stores/localeStore";
import ChatView from "./views/ChatView";
import SkillsView from "./views/SkillsView";
import MonitorView from "./views/MonitorView";
import SettingsView from "./views/SettingsView";

function App() {
  const currentView = useAppStore((s) => s.currentView);
  const serverUrl = useAppStore((s) => s.serverUrl);
  const setConnected = useAppStore((s) => s.setConnected);
  const { i18n } = useTranslation();
  const locale = useLocaleStore((s) => s.locale);

  // Sync locale with store
  useEffect(() => {
    i18n.changeLanguage(locale);
  }, [locale, i18n]);

  // Health check polling
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${serverUrl}/api/health`, {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });
        setConnected(response.ok);
      } catch (error) {
        setConnected(false);
      }
    };

    // Initial check
    checkHealth();

    // Poll every 5 seconds
    const interval = setInterval(checkHealth, 5000);

    return () => clearInterval(interval);
  }, [serverUrl, setConnected]);

  return (
    <>
      {/* Title Bar */}
      <TitleBar />

      {/* Main Layout */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 flex flex-col overflow-hidden">
          {currentView === "chat" && <ChatView />}
          {currentView === "skills" && <SkillsView />}
          {currentView === "monitor" && <MonitorView />}
          {currentView === "settings" && <SettingsView />}
        </main>
      </div>

      {/* Status Bar */}
      <StatusBar />
    </>
  );
}

export default App;
