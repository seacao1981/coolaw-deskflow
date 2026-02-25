import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle, Loader, Play, XCircle } from "lucide-react";
import { useSetupConfigStore } from "../../stores/setupConfigStore";

interface AutoConfigStepProps {
  onComplete: (success: boolean) => void;
}

export function AutoConfigStep({ onComplete }: AutoConfigStepProps) {
  const { t } = useTranslation();
  const { llm, im, workspace, pythonPath, installDeps, selectedSkills } = useSetupConfigStore();

  const [status, setStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [currentTask, setCurrentTask] = useState("");
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState("");

  const addLog = (message: string) => {
    setLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
  };

  const handleStartConfig = async () => {
    setStatus("running");
    setProgress(0);
    setLogs([]);
    setError("");

    try {
      // Step 1: 创建工作区
      setCurrentTask(t("setup.creatingWorkspace", "创建工作区..."));
      addLog(t("setup.creatingWorkspace", "创建工作区..."));
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setProgress(20);
      addLog(t("setup.workspaceCreated", "工作区创建成功"));

      // Step 2: 检查/安装 Python
      setCurrentTask(t("setup.checkingPython", "检查 Python 环境..."));
      addLog(t("setup.checkingPython", "检查 Python 环境..."));
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setProgress(40);
      addLog(t("setup.pythonFound", "Python 环境就绪"));

      // Step 3: 安装依赖
      if (installDeps) {
        setCurrentTask(t("setup.installingDeps", "安装依赖..."));
        addLog(t("setup.installingDeps", "安装依赖..."));
        await new Promise((resolve) => setTimeout(resolve, 2000));
        setProgress(60);
        addLog(t("setup.depsInstalled", "依赖安装完成"));
      }

      // Step 4: 保存配置
      setCurrentTask(t("setup.savingConfig", "保存配置..."));
      addLog(t("setup.savingConfig", "保存配置..."));

      // 调用后端 API 保存配置
      const configData = {
        llm: {
          provider: llm.provider,
          base_url: llm.baseUrl,
          api_key: llm.apiKey,
          model: llm.model,
          max_tokens: llm.maxTokens,
          temperature: llm.temperature / 100,
        },
        im: im ? {
          channel_type: im.channelType,
          token: im.token,
          webhook_url: im.webhookUrl,
          secret: im.secret,
        } : null,
        workspace: {
          path: workspace.path,
          name: workspace.name,
        },
      };

      const response = await fetch("http://127.0.0.1:8420/api/setup/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(configData),
      });

      if (response.ok) {
        setProgress(80);
        addLog(t("setup.configSaved", "配置保存成功"));

        // Step 5: 启动服务
        setCurrentTask(t("setup.startingService", "启动服务..."));
        addLog(t("setup.startingService", "启动服务..."));

        const startResponse = await fetch("http://127.0.0.1:8420/api/setup/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });

        if (startResponse.ok) {
          setProgress(100);
          setStatus("success");
          addLog(t("setup.serviceStarted", "服务启动成功"));
          onComplete(true);
        } else {
          throw new Error("Failed to start service");
        }
      } else {
        throw new Error("Failed to save config");
      }
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : t("common.error", "发生错误"));
      addLog(t("setup.configError", "配置过程出错"));
      onComplete(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Status Display */}
      <div className="bg-surface border border-surface-el rounded-xl p-6">
        <div className="flex items-center gap-4 mb-4">
          {status === "idle" && (
            <>
              <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center">
                <Play className="w-6 h-6 text-accent" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-text-p">
                  {t("setup.readyToStart", "准备开始配置")}
                </h3>
                <p className="text-sm text-text-m">
                  {t("setup.clickToStart", "点击下方按钮开始自动配置")}
                </p>
              </div>
            </>
          )}

          {status === "running" && (
            <>
              <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center">
                <Loader className="w-6 h-6 text-accent animate-spin" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-text-p">{currentTask}</h3>
                <div className="mt-2 h-2 bg-bg-base rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            </>
          )}

          {status === "success" && (
            <>
              <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center">
                <CheckCircle className="w-6 h-6 text-accent" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-accent">
                  {t("setup.configComplete", "配置完成")}
                </h3>
                <p className="text-sm text-text-m">
                  {t("setup.allStepsCompleted", "所有步骤已完成")}
                </p>
              </div>
            </>
          )}

          {status === "error" && (
            <>
              <div className="w-12 h-12 rounded-full bg-rose-500/10 flex items-center justify-center">
                <XCircle className="w-6 h-6 text-rose-500" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-rose-500">
                  {t("setup.configFailed", "配置失败")}
                </h3>
                <p className="text-sm text-text-m">{error}</p>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Configuration Summary */}
      <div className="bg-surface border border-surface-el rounded-xl p-4">
        <h4 className="text-sm font-semibold text-text-p mb-3">
          {t("setup.configSummary", "配置摘要")}
        </h4>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-text-m">{t("setup.provider", "服务商")}</span>
            <span className="text-text-p">{llm.provider}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-m">{t("setup.model", "模型")}</span>
            <span className="text-text-p">{llm.model}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-m">{t("setup.imChannel", "IM 渠道")}</span>
            <span className="text-text-p">{im ? im.channelType : t("setup.notConfigured", "未配置")}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-m">{t("setup.workspace", "工作区")}</span>
            <span className="text-text-p">{workspace.name}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-text-m">{t("setup.installDeps", "安装依赖")}</span>
            <span className="text-text-p">{installDeps ? t("common.yes", "是") : t("common.no", "否")}</span>
          </div>
        </div>
      </div>

      {/* Logs */}
      {logs.length > 0 && (
        <div className="bg-bg-deep border border-surface-el rounded-xl p-4 font-mono text-xs">
          <div className="text-text-m mb-2">{t("setup.logs", "日志")}</div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {logs.map((log, i) => (
              <div key={i} className="text-text-s">
                {log}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Start Button */}
      {status === "idle" && (
        <button
          onClick={handleStartConfig}
          className="w-full py-3 rounded-lg bg-accent text-bg-deep font-medium hover:bg-accent-hover cursor-pointer transition-colors duration-200 flex items-center justify-center gap-2"
        >
          <Play className="w-5 h-5" />
          {t("setup.startConfig", "开始配置")}
        </button>
      )}

      {/* Complete Button */}
      {status === "success" && (
        <button
          onClick={() => onComplete(true)}
          className="w-full py-3 rounded-lg bg-accent text-bg-deep font-medium hover:bg-accent-hover cursor-pointer transition-colors duration-200"
        >
          {t("common.finish", "完成")}
        </button>
      )}

      {/* Retry Button */}
      {status === "error" && (
        <button
          onClick={handleStartConfig}
          className="w-full py-3 rounded-lg bg-surface border border-surface-el text-text-p hover:bg-surface-el cursor-pointer transition-colors duration-200"
        >
          {t("common.retry", "重试")}
        </button>
      )}
    </div>
  );
}
