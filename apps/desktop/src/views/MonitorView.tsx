import { useEffect, useState, useCallback, useRef } from "react";
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
  Terminal,
  X,
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
  status?: string;  // running, sleeping, zombie, etc.
  start_time?: string;  // ISO format
  threads?: number;
  open_files?: number;
  connections?: number;
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
  const [showLogStream, setShowLogStream] = useState(false);

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
            <button
              onClick={() => setShowLogStream(true)}
              className="px-3 py-1.5 rounded-lg border border-surface-el text-text-s hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1.5"
              title="实时日志流"
            >
              <Terminal className="w-4 h-4" />
              <span className="text-xs">日志流</span>
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

      {/* Log Stream Panel */}
      {showLogStream && <LogStreamPanel onClose={() => setShowLogStream(false)} />}
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

  // 格式化运行时间
  const formatUptime = (seconds?: number) => {
    if (!seconds) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h}h ${m}m ${s}s`;
  };

  // 格式化启动时间
  const formatStartTime = (startTime?: string) => {
    if (!startTime) return '-';
    try {
      return new Date(startTime).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return startTime;
    }
  };

  return (
    <div className="bg-surface border border-surface-el rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
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
        </div>
      </div>

      {/* 进程详情信息 */}
      {isRunning && serviceStatus && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-surface-el">
          <div className="bg-bg-base rounded-lg p-2">
            <div className="text-xs text-text-s mb-1">运行时长</div>
            <div className="text-sm font-code text-text-p">{formatUptime(serviceStatus.uptime_seconds)}</div>
          </div>
          <div className="bg-bg-base rounded-lg p-2">
            <div className="text-xs text-text-s mb-1">启动时间</div>
            <div className="text-sm font-code text-text-p">{formatStartTime(serviceStatus.start_time)}</div>
          </div>
          <div className="bg-bg-base rounded-lg p-2">
            <div className="text-xs text-text-s mb-1">进程状态</div>
            <div className="text-sm font-code text-text-p capitalize">{serviceStatus.status || '-'}</div>
          </div>
          <div className="bg-bg-base rounded-lg p-2">
            <div className="text-xs text-text-s mb-1">CPU 使用</div>
            <div className="text-sm font-code text-text-p">{serviceStatus.cpu_percent?.toFixed(1) || '-'}%</div>
          </div>
          <div className="bg-bg-base rounded-lg p-2">
            <div className="text-xs text-text-s mb-1">内存使用</div>
            <div className="text-sm font-code text-text-p">{serviceStatus.memory_mb?.toFixed(1) || '-'} MB</div>
          </div>
          <div className="bg-bg-base rounded-lg p-2">
            <div className="text-xs text-text-s mb-1">线程数</div>
            <div className="text-sm font-code text-text-p">{serviceStatus.threads || '-'}</div>
          </div>
          <div className="bg-bg-base rounded-lg p-2">
            <div className="text-xs text-text-s mb-1">打开文件</div>
            <div className="text-sm font-code text-text-p">{serviceStatus.open_files || '-'}</div>
          </div>
          <div className="bg-bg-base rounded-lg p-2">
            <div className="text-xs text-text-s mb-1">网络连接</div>
            <div className="text-sm font-code text-text-p">{serviceStatus.connections || '-'}</div>
          </div>
        </div>
      )}
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

// 日志条目类型
interface LogEntry {
  timestamp: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  message: string;
  [key: string]: unknown;
}

// 实时日志流组件
function LogStreamPanel({
  onClose,
}: {
  onClose: () => void;
}) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filterLevel, setFilterLevel] = useState<string>("all");
  const [connected, setConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    // 连接 SSE 流
    const eventSource = new EventSource("http://127.0.0.1:8420/api/logs/stream");

    eventSource.onopen = () => {
      setConnected(true);
      console.log("Log stream connected");
    };

    eventSource.addEventListener("log", (event) => {
      try {
        const logEntry: LogEntry = JSON.parse(event.data);
        setLogs((prev) => [...prev.slice(-99), logEntry]); // 保留最新 100 条
      } catch (e) {
        console.error("Failed to parse log entry:", e);
      }
    });

    eventSource.addEventListener("connected", (event) => {
      console.log("Stream status:", event.data);
    });

    eventSource.onerror = (error) => {
      console.error("Log stream error:", error);
      setConnected(false);
      eventSource.close();
    };

    eventSourceRef.current = eventSource;

    return () => {
      eventSource.close();
    };
  }, []);

  const filteredLogs = filterLevel === "all"
    ? logs
    : logs.filter((log) => log.level === filterLevel);

  const getLevelColor = (level: string) => {
    switch (level) {
      case "DEBUG": return "text-text-s";
      case "INFO": return "text-info";
      case "WARNING": return "text-warning";
      case "ERROR": return "text-rose-500";
      default: return "text-text-p";
    }
  };

  const getLevelBg = (level: string) => {
    switch (level) {
      case "DEBUG": return "bg-bg-base";
      case "INFO": return "bg-info/10";
      case "WARNING": return "bg-warning/10";
      case "ERROR": return "bg-rose-500/10";
      default: return "bg-surface";
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-bg-deep rounded-xl border border-surface w-full max-w-4xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface">
          <div className="flex items-center gap-3">
            <Terminal className="w-5 h-5 text-accent" />
            <h2 className="text-lg font-semibold text-text-p">实时日志流</h2>
            <span className={`text-xs px-2 py-0.5 rounded-full ${connected ? "bg-accent/20 text-accent" : "bg-text-m/20 text-text-m"}`}>
              {connected ? "已连接" : "未连接"}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {/* Level Filter */}
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              className="px-2 py-1 bg-bg-base border border-surface rounded text-xs text-text-s focus:outline-none focus:border-accent"
            >
              <option value="all">全部</option>
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
            <button
              onClick={() => setLogs([])}
              className="p-1.5 text-text-s hover:bg-bg-base rounded transition-colors"
              title="清空日志"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-text-s hover:bg-bg-base rounded transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Log Content */}
        <div className="flex-1 overflow-auto p-4 font-mono text-xs bg-bg-base">
          {filteredLogs.length === 0 ? (
            <div className="text-center text-text-s py-8">
              <Terminal className="w-12 h-12 mx-auto mb-2 opacity-20" />
              <p>等待日志...</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {filteredLogs.map((log, index) => (
                <div
                  key={index}
                  className={`px-2 py-1 rounded ${getLevelBg(log.level)} hover:bg-surface-el/50`}
                >
                  <span className="text-text-s mr-2">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className={`font-semibold mr-2 ${getLevelColor(log.level)}`}>
                    {log.level}
                  </span>
                  <span className="text-text-p">{log.message}</span>
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>

        {/* Footer Stats */}
        <div className="px-4 py-2 border-t border-surface flex items-center justify-between text-xs text-text-s">
          <span>显示 {filteredLogs.length} / {logs.length} 条日志</span>
          <span className="font-code">SSE 实时流</span>
        </div>
      </div>
    </div>
  );
}
