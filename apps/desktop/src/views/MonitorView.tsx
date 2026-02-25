import { useEffect, useState, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useAppStore } from "../stores/appStore";
import {
  RefreshCw,
  Download,
  Database,
  Brain,
  Wrench,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
  Cpu,
  Play,
  Square,
  Server,
  FileText,
} from "lucide-react";

interface SystemStatus {
  cpu: { percent: number; cores: number };
  memory: { used_mb: number; total_mb: number; percent: number };
  disk: { used_gb: number; total_gb: number; percent: number };
  data_disk: { used_gb: number; total_gb: number; percent: number };
  uptime_seconds: number;
  platform: string;
}

interface LLMStats {
  provider: string;
  model: string;
  memory_count: number;
  active_tools: number;
  total_tokens: number;
  today_tokens: number;
}

interface Activity {
  id: string;
  time: string;
  type: "llm_call" | "tool_execution" | "memory_operation" | "system_event" | "user_action";
  icon: string;
  text: string;
  tag: string;
  tagColor: string;
}

interface ServiceStatus {
  running: boolean;
  pid?: number;
  uptime?: number;
  logFile?: string;
}

function formatUptime(seconds: number): string {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  return `${hrs}h ${mins}m ${secs}s`;
}

function getActivityIcon(type: Activity["type"]): string {
  switch (type) {
    case "llm_call":
      return "brain";
    case "tool_execution":
      return "wrench";
    case "memory_operation":
      return "database";
    case "system_event":
      return "alert";
    case "user_action":
      return "check";
    default:
      return "info";
  }
}

function getActivityTagColor(type: Activity["type"]): string {
  switch (type) {
    case "llm_call":
      return "bg-accent/10 text-accent";
    case "tool_execution":
      return "bg-warning/10 text-warning";
    case "memory_operation":
      return "bg-info/10 text-info";
    case "system_event":
      return "bg-rose-500/10 text-rose-500";
    case "user_action":
      return "bg-green-500/10 text-green-500";
    default:
      return "bg-gray-500/10 text-gray-500";
  }
}

/**
 * Monitor view with real-time system status and service control.
 */
export default function MonitorView() {
  const { t } = useTranslation();
  const serverUrl = useAppStore((s) => s.serverUrl);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [llmStats, setLlmStats] = useState<LLMStats | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [serviceActionLoading, setServiceActionLoading] = useState(false);

  // Fetch status data
  const fetchStatus = useCallback(async () => {
    try {
      const [statusRes, llmRes, activityRes, serviceRes] = await Promise.all([
        fetch(`${serverUrl}/api/monitor/status`),
        fetch(`${serverUrl}/api/monitor/llm-stats`),
        fetch(`${serverUrl}/api/monitor/activity`),
        fetch(`${serverUrl}/api/monitor/service-status`),
      ]);

      if (statusRes.ok) {
        const data = await statusRes.json();
        setStatus(data);
      }

      if (llmRes.ok) {
        const data = await llmRes.json();
        setLlmStats(data);
      }

      if (activityRes.ok) {
        const data = await activityRes.json();
        setActivities(data.activities || []);
      }

      if (serviceRes.ok) {
        const data = await serviceRes.json();
        setServiceStatus(data);
      }

      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError(t("common.error"));
    } finally {
      setLoading(false);
    }
  }, [t, serverUrl]);

  // Service control actions
  const handleStartService = async () => {
    setServiceActionLoading(true);
    try {
      const response = await fetch(`${serverUrl}/api/monitor/service/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        fetchStatus();
      }
    } catch (err) {
      console.error("Failed to start service:", err);
    } finally {
      setServiceActionLoading(false);
    }
  };

  const handleStopService = async () => {
    setServiceActionLoading(true);
    try {
      const response = await fetch(`${serverUrl}/api/monitor/service/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        fetchStatus();
      }
    } catch (err) {
      console.error("Failed to stop service:", err);
    } finally {
      setServiceActionLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // WebSocket connection for real-time activity updates
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connectWebSocket = () => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/monitor/ws/activity`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log(t("monitor.websocketConnected"));
        };

        ws.onclose = () => {
          console.log(t("monitor.websocketDisconnected"));
          reconnectTimeout = setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (error) => {
          console.error(t("monitor.websocketError"), error);
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);

            if (message.type === 'new_activity' && message.activity) {
              const newActivity: Activity = {
                id: message.activity.id,
                time: new Date(message.activity.timestamp).toLocaleTimeString(),
                type: message.activity.type,
                icon: getActivityIcon(message.activity.type),
                text: message.activity.summary,
                tag: message.activity.type,
                tagColor: getActivityTagColor(message.activity.type),
              };

              setActivities((prev) => {
                const first = prev[0];
                if (first && first.id === newActivity.id) {
                  return prev;
                }
                return [newActivity, ...prev].slice(0, 50);
              });
            }
          } catch (err) {
            console.error(t("monitor.parseMessageError"), err);
          }
        };
      } catch (err) {
        console.error(t("monitor.connectError"), err);
      }
    };

    connectWebSocket();

    return () => {
      if (ws) {
        ws.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, [t]);

  const handleExport = () => {
    const data = {
      timestamp: new Date().toISOString(),
      system: status,
      llm: llmStats,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `deskflow-status-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filterButtons = [
    { key: "all", label: t("monitor.filters.all") },
    { key: "llm", label: t("monitor.filters.llm") },
    { key: "tools", label: t("monitor.filters.tools") },
    { key: "memory", label: t("monitor.filters.memory") },
  ];

  return (
    <div className="flex-1 flex flex-col">
      {/* Header */}
      <div className="h-14 border-b border-surface flex items-center px-6 shrink-0">
        <h1 className="text-lg font-semibold font-code">{t("monitor.title")}</h1>
        <div className="ml-auto flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-text-m">
              {t("monitor.updated")}{lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchStatus}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-sm text-text-s border border-surface-el hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1.5 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> {t("monitor.refresh")}
          </button>
          <button
            onClick={handleExport}
            className="px-3 py-1.5 rounded-lg text-sm text-text-s border border-surface-el hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1.5"
          >
            <Download className="w-3.5 h-3.5" /> {t("monitor.export")}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading && !status ? (
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 text-text-m animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-500">
            <p>{error}</p>
          </div>
        ) : (
          <div className="max-w-5xl space-y-6">
            {/* Service Control Card - NEW */}
            <ServiceControlCard
              serviceStatus={serviceStatus}
              onStart={handleStartService}
              onStop={handleStopService}
              loading={serviceActionLoading}
              t={t}
            />

            {/* Status Cards */}
            <div className="grid grid-cols-4 gap-4">
              <StatusCard
                label={t("monitor.agent")}
                value={llmStats?.provider === "none" ? t("monitor.offline") : t("monitor.online")}
                detail={llmStats?.model || t("monitor.noLlmConfigured")}
                dotColor={llmStats?.provider === "none" ? "bg-text-m" : "bg-accent animate-pulse-dot"}
              />
              <StatusCard
                label={t("monitor.memory")}
                value={llmStats?.memory_count.toString() || "0"}
                detail={t("monitor.entriesStored")}
                icon={<Database className="w-4 h-4 text-info" />}
              />
              <StatusCard
                label={t("monitor.llm")}
                value={llmStats?.provider === "DashScope" ? "Qwen" : llmStats?.provider || "-"}
                detail={llmStats?.model || t("monitor.notConfigured")}
                icon={<Brain className="w-4 h-4 text-accent" />}
              />
              <StatusCard
                label={t("monitor.tools")}
                value={llmStats?.active_tools.toString() || "0"}
                detail={t("monitor.available")}
                icon={<Wrench className="w-4 h-4 text-warning" />}
              />
            </div>

            {/* Activity + Resources */}
            <div className="grid grid-cols-5 gap-4">
              {/* Timeline */}
              <div className="col-span-3 bg-surface border border-surface-el rounded-xl">
                <div className="px-4 py-3 border-b border-surface-el flex items-center justify-between">
                  <span className="text-sm font-semibold font-code">{t("monitor.activityTimeline")}</span>
                  <div className="flex items-center gap-2">
                    {filterButtons.map((f) => (
                      <button
                        key={f.key}
                        className={`px-2 py-1 rounded text-xs cursor-pointer transition-colors duration-200 ${
                          f.key === "all" ? "bg-accent/10 text-accent" : "text-text-m hover:bg-surface-el"
                        }`}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="divide-y divide-surface-el max-h-64 overflow-y-auto">
                  {activities.length === 0 ? (
                    <div className="px-4 py-8 text-center text-sm text-text-m">
                      {t("monitor.noRecentActivity")}
                    </div>
                  ) : (
                    activities.map((a, i) => (
                      <div key={i} className="px-4 py-2.5 flex items-center gap-3 hover:bg-bg-base/50 transition-colors duration-200">
                        <span className="text-xs text-text-m font-code w-12 shrink-0">{a.time}</span>
                        {a.icon === "check" && <CheckCircle className="w-4 h-4 text-accent" />}
                        {a.icon === "database" && <Database className="w-4 h-4 text-info" />}
                        {a.icon === "brain" && <Brain className="w-4 h-4 text-accent" />}
                        {a.icon === "wrench" && <Wrench className="w-4 h-4 text-warning" />}
                        {a.icon === "warning" && <AlertTriangle className="w-4 h-4 text-warning" />}
                        {a.icon === "alert" && <AlertTriangle className="w-4 h-4 text-rose-500" />}
                        {a.icon === "info" && <CheckCircle className="w-4 h-4 text-info" />}
                        <span className="text-sm text-text-s">{a.text}</span>
                        <span className={`ml-auto inline-flex items-center px-2 py-0.5 rounded text-xs font-code font-medium ${a.tagColor}`}>
                          {a.tag}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Resources */}
              <div className="col-span-2 bg-surface border border-surface-el rounded-xl">
                <div className="px-4 py-3 border-b border-surface-el flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-accent" />
                  <span className="text-sm font-semibold font-code">{t("monitor.resources")}</span>
                </div>
                <div className="p-4 space-y-4">
                  <ResourceBar
                    label={t("monitor.cpu")}
                    value={`${status?.cpu.percent.toFixed(1)}%`}
                    percentage={status?.cpu.percent || 0}
                    color="bg-accent"
                  />
                  <ResourceBar
                    label={t("monitor.memory")}
                    value={`${status?.memory.used_mb.toFixed(0)} MB / ${status?.memory.total_mb.toFixed(0)} MB`}
                    percentage={status?.memory.percent || 0}
                    color="bg-info"
                  />
                  <ResourceBar
                    label={t("monitor.disk")}
                    value={`${status?.disk.used_gb.toFixed(1)} GB / ${status?.disk.total_gb.toFixed(1)} GB`}
                    percentage={status?.disk.percent || 0}
                    color="bg-warning"
                  />
                  <div className="pt-3 border-t border-surface-el">
                    <ResourceBar
                      label={t("monitor.dataDisk")}
                      value={`${status?.data_disk.used_gb.toFixed(1)} GB / ${status?.data_disk.total_gb.toFixed(1)} GB`}
                      percentage={status?.data_disk.percent || 0}
                      color="bg-purple-500"
                    />
                  </div>
                  <div className="pt-3 border-t border-surface-el space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-text-s">{t("monitor.uptime")}</span>
                      <span className="text-xs font-code text-text-p">
                        {status ? formatUptime(status.uptime_seconds) : "-"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-text-s">{t("monitor.platform")}</span>
                      <span className="text-xs font-code text-text-p">{status?.platform || "-"}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Evolution */}
            <div className="bg-surface border border-surface-el rounded-xl">
              <div className="px-4 py-3 border-b border-surface-el flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-accent" />
                <span className="text-sm font-semibold font-code">{t("monitor.evolutionStatus")}</span>
              </div>
              <div className="grid grid-cols-3 divide-x divide-surface-el">
                <EvolutionCard
                  label={t("monitor.lastSelfCheck")}
                  value={status ? formatUptime(status.uptime_seconds) : "-"}
                  detail={t("monitor.systemHealthy")}
                  ok
                />
                <EvolutionCard
                  label={t("monitor.memoryEntries")}
                  value={llmStats?.memory_count.toString() || "0"}
                  detail={t("monitor.conversationHistory")}
                />
                <EvolutionCard
                  label={t("monitor.activeTools")}
                  value={llmStats?.active_tools.toString() || "0"}
                  detail={t("monitor.skillsAvailable")}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Service Control Card Component
function ServiceControlCard({
  serviceStatus,
  onStart,
  onStop,
  loading,
  t,
}: {
  serviceStatus: ServiceStatus | null;
  onStart: () => void;
  onStop: () => void;
  loading: boolean;
  t: (key: string) => string;
}) {
  const isRunning = serviceStatus?.running ?? false;

  return (
    <div className="bg-surface border border-surface-el rounded-xl p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${isRunning ? 'bg-accent/10' : 'bg-surface-el'}`}>
            <Server className={`w-5 h-5 ${isRunning ? 'text-accent' : 'text-text-m'}`} />
          </div>
          <div>
            <div className="text-sm font-semibold font-code text-text-p">
              {t("monitor.service.title", "后端服务")}
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-accent animate-pulse-dot' : 'bg-text-m'}`} />
              <span className="text-xs text-text-m">
                {isRunning ? t("monitor.service.running", "运行中") : t("monitor.service.stopped", "已停止")}
              </span>
              {serviceStatus?.pid && (
                <span className="text-xs text-text-s font-code">
                  PID: {serviceStatus.pid}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isRunning ? (
            <button
              onClick={onStart}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-accent text-bg-deep font-medium hover:bg-accent-hover cursor-pointer transition-colors duration-200 flex items-center gap-2 disabled:opacity-50"
            >
              <Play className="w-4 h-4" /> {t("monitor.service.start", "启动")}
            </button>
          ) : (
            <button
              onClick={onStop}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-rose-500/20 border border-rose-500/30 text-rose-500 font-medium hover:bg-rose-500/30 cursor-pointer transition-colors duration-200 flex items-center gap-2 disabled:opacity-50"
            >
              <Square className="w-4 h-4" /> {t("monitor.service.stop", "停止")}
            </button>
          )}
          {serviceStatus?.logFile && (
            <button
              className="px-3 py-2 rounded-lg border border-surface-el text-text-s hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1.5"
              title={t("monitor.service.viewLogs", "查看日志")}
            >
              <FileText className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusCard({ label, value, detail, dotColor, icon }: {
  label: string; value: string; detail: string; dotColor?: string; icon?: React.ReactNode;
}) {
  return (
    <div className="bg-surface border border-surface-el rounded-xl p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-m font-medium uppercase tracking-wider">{label}</span>
        {dotColor ? <span className={`w-2 h-2 rounded-full ${dotColor}`} /> : icon}
      </div>
      <div className="mt-2 text-xl font-semibold font-code">{value}</div>
      <div className="text-xs text-text-s mt-1">{detail}</div>
    </div>
  );
}

function ResourceBar({ label, value, percentage, color }: {
  label: string; value: string; percentage: number; color: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-text-s">{label}</span>
        <span className="text-xs font-code text-text-p">{value}</span>
      </div>
      <div className="h-2 bg-bg-base rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

function EvolutionCard({ label, value, detail, ok }: {
  label: string; value: string; detail: string; ok?: boolean;
}) {
  return (
    <div className="p-4">
      <div className="text-xs text-text-m uppercase tracking-wider">{label}</div>
      <div className="text-sm font-code mt-1">{value}</div>
      <div className="flex items-center gap-1.5 mt-1">
        {ok && <CheckCircle className="w-3.5 h-3.5 text-accent" />}
        <span className={`text-xs ${ok ? "text-accent" : "text-text-s"}`}>{detail}</span>
      </div>
    </div>
  );
}
