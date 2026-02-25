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
  uptime_seconds?: number;
  memory_mb?: number;
  cpu_percent?: number;
  logFile?: string;
}

interface MonitorViewProps {
  // Add props if needed
}

export function MonitorView({}: MonitorViewProps) {
  const { t } = useTranslation();
  const isConnected = useAppStore((s) => s.isConnected);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [llmStats, setLlmStats] = useState<LLMStats | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [serviceLoading, setServiceLoading] = useState(false);
  const [filter, setFilter] = useState<"all" | "llm" | "tools" | "memory">("all");

  // Fetch system status
  const fetchStatus = useCallback(async () => {
    try {
      const [statusRes, llmRes, activityRes, serviceRes] = await Promise.all([
        fetch("http://127.0.0.1:8420/api/monitor/status"),
        fetch("http://127.0.0.1:8420/api/monitor/llm-stats"),
        fetch("http://127.0.0.1:8420/api/monitor/activity?limit=10"),
        fetch("http://127.0.0.1:8420/api/monitor/service/status"),
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
    } catch (error) {
      console.error("Failed to fetch status:", error);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Service control
  const handleStartService = async () => {
    setServiceLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8420/api/monitor/service/start", {
        method: "POST",
      });
      if (res.ok) {
        await fetchStatus();
      }
    } catch (error) {
      console.error("Failed to start service:", error);
    }
    setServiceLoading(false);
  };

  const handleStopService = async () => {
    setServiceLoading(true);
    try {
      const res = await fetch("http://127.0.0.1:8420/api/monitor/service/stop", {
        method: "POST",
      });
      if (res.ok) {
        await fetchStatus();
      }
    } catch (error) {
      console.error("Failed to stop service:", error);
    }
    setServiceLoading(false);
  };

  // Filter activities - fixed type comparison
  const filteredActivities = activities.filter((activity) => {
    if (filter === "all") return true;
    // Map filter to activity type
    const typeMap: Record<string, string> = {
      llm: "llm_call",
      tools: "tool_execution",
      memory: "memory_operation",
    };
    return activity.type === typeMap[filter];
  });

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  };

  return (
    <div className="flex-1 bg-bg-deep p-6 overflow-y-auto">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold font-code text-text-p">{t("monitor.title", "系统监控")}</h1>
            <p className="text-sm text-text-m mt-0.5">
              {t("monitor.updated", "更新于：")} {new Date().toLocaleTimeString()}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchStatus}
              className="px-3 py-1.5 rounded-lg border border-surface-el text-text-s hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1.5"
            >
              <RefreshCw className="w-4 h-4" />
              {t("monitor.refresh", "刷新")}
            </button>
            <button
              className="px-3 py-1.5 rounded-lg border border-surface-el text-text-s hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1.5"
            >
              <Download className="w-4 h-4" />
              {t("monitor.export", "导出")}
            </button>
          </div>
        </div>

        {/* Service Control Card */}
        <div className="mb-6">
          <ServiceControlCard
            serviceStatus={serviceStatus}
            onStart={handleStartService}
            onStop={handleStopService}
            loading={serviceLoading}
            t={t}
          />
        </div>

        {/* Status Cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatusCard
            label={t("monitor.agent", "Agent")}
            value={isConnected ? t("monitor.online", "在线") : t("monitor.offline", "离线")}
            detail={isConnected ? t("monitor.systemHealthy", "系统正常") : t("monitor.disconnected", "未连接")}
            dotColor={isConnected ? "bg-accent" : "bg-text-m"}
          />
          <StatusCard
            label={t("monitor.memory", "记忆")}
            value={llmStats?.memory_count?.toString() || "-"}
            detail={t("monitor.memoryEntries", "记忆条目")}
            icon={<Database className="w-4 h-4 text-text-m" />}
          />
          <StatusCard
            label={t("monitor.llm", "LLM")}
            value={llmStats?.provider ? t("monitor.connected", "已连接") : t("monitor.notConfigured", "未配置")}
            detail={llmStats?.model || "-"}
            dotColor={llmStats?.provider ? "bg-accent" : "bg-text-m"}
          />
          <StatusCard
            label={t("monitor.tools", "工具")}
            value={llmStats?.active_tools?.toString() || "-"}
            detail={t("monitor.skillsAvailable", "可用技能")}
            icon={<Wrench className="w-4 h-4 text-text-m" />}
          />
        </div>

        {/* Resource Monitor & Activity Timeline */}
        <div className="grid grid-cols-3 gap-6">
          {/* Resource Monitor */}
          <div className="col-span-1">
            <div className="bg-surface border border-surface-el rounded-xl p-4">
              <h3 className="text-sm font-semibold text-text-p mb-4">{t("monitor.resources", "资源")}</h3>
              {status && (
                <>
                  <div className="mb-4">
                    <ResourceBar
                      label={t("monitor.cpu", "CPU")}
                      value={`${status.cpu.percent}%`}
                      percentage={status.cpu.percent}
                      color="bg-accent"
                    />
                  </div>
                  <div className="mb-4">
                    <ResourceBar
                      label={t("monitor.memory", "内存")}
                      value={`${Math.round(status.memory.percent)}%`}
                      percentage={status.memory.percent}
                      color="bg-info"
                    />
                  </div>
                  <div className="mb-4">
                    <ResourceBar
                      label={t("monitor.disk", "磁盘")}
                      value={`${Math.round(status.disk.percent)}%`}
                      percentage={status.disk.percent}
                      color="bg-warning"
                    />
                  </div>
                  <div className="mb-4">
                    <ResourceBar
                      label={t("monitor.dataDisk", "数据盘")}
                      value={`${Math.round(status.data_disk.percent)}%`}
                      percentage={status.data_disk.percent}
                      color="bg-success"
                    />
                  </div>
                  <div className="pt-3 border-t border-surface-el">
                    <div className="flex items-center justify-between text-xs text-text-s">
                      <span>{t("monitor.uptime", "运行时间")}</span>
                      <span className="font-code">{formatUptime(status.uptime_seconds)}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs text-text-s mt-1">
                      <span>{t("monitor.platform", "平台")}</span>
                      <span className="font-code">{status.platform}</span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Activity Timeline */}
          <div className="col-span-2">
            <div className="bg-surface border border-surface-el rounded-xl p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-text-p">{t("monitor.activityTimeline", "活动时间线")}</h3>
                <div className="flex items-center gap-1">
                  {(["all", "llm", "tools", "memory"] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => setFilter(f)}
                      className={`px-2 py-1 rounded text-xs cursor-pointer transition-colors ${
                        filter === f
                          ? "bg-accent/20 text-accent"
                          : "text-text-s hover:bg-surface"
                      }`}
                    >
                      {t(`monitor.filters.${f}`, f)}
                    </button>
                  ))}
                </div>
              </div>

              {filteredActivities.length > 0 ? (
                <div className="space-y-3">
                  {filteredActivities.slice(0, 8).map((activity) => (
                    <div key={activity.id} className="flex items-start gap-3">
                      <div className="w-8 h-8 rounded-lg bg-surface-el flex items-center justify-center shrink-0">
                        {activity.icon === "brain" && <Brain className="w-4 h-4 text-text-m" />}
                        {activity.icon === "wrench" && <Wrench className="w-4 h-4 text-text-m" />}
                        {activity.icon === "database" && <Database className="w-4 h-4 text-text-m" />}
                        {activity.icon === "check" && <CheckCircle className="w-4 h-4 text-accent" />}
                        {activity.icon === "alert" && <AlertTriangle className="w-4 h-4 text-warning" />}
                        {activity.icon === "trending" && <TrendingUp className="w-4 h-4 text-info" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-text-p">{activity.text}</div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-text-s">{activity.time}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded ${activity.tagColor}`}>
                            {activity.tag}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-text-m">
                  <RefreshCw className="w-8 h-8 mx-auto mb-2 opacity-20" />
                  <p className="text-sm">{t("monitor.noRecentActivity", "暂无最近活动")}</p>
                </div>
              )}
            </div>
          </div>
        </div>
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
  t: ReturnType<typeof useTranslation>["t"];
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
      <div className="h-1.5 bg-bg-base rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-300`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}
