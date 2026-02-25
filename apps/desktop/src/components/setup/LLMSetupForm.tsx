import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Eye, EyeOff, CheckCircle, XCircle, Loader } from "lucide-react";
import { useSetupConfigStore } from "../../stores/setupConfigStore";

// Provider 配置
const PROVIDERS = [
  { value: "dashscope", label: "通义千问 (DashScope)", defaultBaseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  { value: "openai", label: "OpenAI 兼容", defaultBaseUrl: "https://api.openai.com/v1" },
  { value: "anthropic", label: "Anthropic (Claude)", defaultBaseUrl: "" },
];

// 模型推荐列表
const RECOMMENDED_MODELS: Record<string, { id: string; note: string }[]> = {
  dashscope: [
    { id: "qwen3.5-plus", note: "推荐" },
    { id: "qwen-max", note: "" },
    { id: "qwen-plus", note: "" },
    { id: "qwen-turbo", note: "" },
  ],
  openai: [
    { id: "gpt-4o", note: "推荐" },
    { id: "gpt-4o-mini", note: "" },
    { id: "gpt-4-turbo", note: "" },
  ],
  anthropic: [
    { id: "claude-3-5-sonnet-20241022", note: "推荐" },
    { id: "claude-3-opus-20240229", note: "" },
    { id: "claude-3-haiku-20240307", note: "" },
  ],
};

interface LLMSetupFormProps {
  onComplete?: (data: any) => void;
  compact?: boolean;
}

export function LLMSetupForm({ onComplete, compact }: LLMSetupFormProps) {
  const { t } = useTranslation();
  const { llm, setLLMConfig } = useSetupConfigStore();

  const [showKey, setShowKey] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [testResult, setTestResult] = useState<string>("");

  // Update base URL when provider changes
  useEffect(() => {
    const provider = PROVIDERS.find(p => p.value === llm.provider);
    if (provider && provider.defaultBaseUrl) {
      setLLMConfig({ baseUrl: provider.defaultBaseUrl });
    }
  }, [llm.provider]);

  // Fetch models when provider/baseUrl/apiKey changes
  useEffect(() => {
    const fetchModels = async () => {
      if (llm.provider === "anthropic") {
        setModels([]);
        return;
      }

      setModelsLoading(true);
      try {
        // 这里调用后端 API 获取模型列表
        const params = new URLSearchParams({
          provider: llm.provider,
          base_url: llm.baseUrl,
        });
        if (llm.apiKey) {
          params.append("api_key", llm.apiKey);
        }

        // 使用后端 API
        const response = await fetch(`http://127.0.0.1:8420/api/llm/models?${params}`);
        if (response.ok) {
          const data = await response.json();
          setModels(data.models || []);

          // If current model is not in the list, select the first one
          if (!models.includes(llm.model) && data.models && data.models.length > 0) {
            setLLMConfig({ model: data.models[0] });
          }
        }
      } catch (error) {
        console.error("Failed to fetch models:", error);
        // 使用推荐模型列表
        const recommended = RECOMMENDED_MODELS[llm.provider];
        if (recommended) {
          setModels(recommended.map(m => m.id));
        }
      } finally {
        setModelsLoading(false);
      }
    };

    const timeoutId = setTimeout(fetchModels, 500);
    return () => clearTimeout(timeoutId);
  }, [llm.provider, llm.baseUrl, llm.apiKey]);

  // Test connection
  const handleTestConnection = async () => {
    setTestStatus("testing");
    try {
      const response = await fetch("http://127.0.0.1:8420/api/llm/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: llm.provider,
          base_url: llm.baseUrl,
          api_key: llm.apiKey,
          model: llm.model,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        setTestStatus("success");
        setTestResult(`连接成功！延迟：${result.latency_ms}ms`);
        onComplete?.({ success: true, ...result });
      } else {
        setTestStatus("error");
        setTestResult("连接失败，请检查配置");
      }
    } catch (error) {
      setTestStatus("error");
      setTestResult("无法连接到后端服务");
    }
  };

  const recommendedModels = RECOMMENDED_MODELS[llm.provider] || [];

  return (
    <div className="space-y-4">
      {/* Provider Selection */}
      <div>
        <label className="block text-sm font-medium text-text-p mb-2">
          {t("setup.full.llmProvider", "服务商")}
        </label>
        <select
          value={llm.provider}
          onChange={(e) => setLLMConfig({ provider: e.target.value })}
          className="w-full bg-surface border border-surface-el rounded-lg px-3 py-2 text-sm text-text-p focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15"
        >
          {PROVIDERS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      {/* Base URL */}
      {llm.provider !== "anthropic" && (
        <div>
          <label className="block text-sm font-medium text-text-p mb-2">
            {t("settings.baseUrl", "基础 URL")}
          </label>
          <input
            type="url"
            value={llm.baseUrl}
            onChange={(e) => setLLMConfig({ baseUrl: e.target.value })}
            placeholder={PROVIDERS.find(p => p.value === llm.provider)?.defaultBaseUrl}
            className="w-full bg-surface border border-surface-el rounded-lg px-3 py-2 text-sm text-text-p focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15"
          />
        </div>
      )}

      {/* API Key */}
      <div>
        <label className="block text-sm font-medium text-text-p mb-2">
          {t("settings.apiKey", "API 密钥")}
        </label>
        <div className="relative">
          <input
            type={showKey ? "text" : "password"}
            value={llm.apiKey}
            onChange={(e) => setLLMConfig({ apiKey: e.target.value })}
            placeholder={t("setup.enterApiKey", "请输入 API Key")}
            className="w-full bg-surface border border-surface-el rounded-lg px-3 py-2 pr-20 text-sm text-text-p focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-text-m hover:text-text-p cursor-pointer transition-colors"
          >
            {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Model Selection */}
      <div>
        <label className="block text-sm font-medium text-text-p mb-2">
          {t("settings.model", "模型")}
        </label>
        <select
          value={llm.model}
          onChange={(e) => setLLMConfig({ model: e.target.value })}
          disabled={modelsLoading}
          className="w-full bg-surface border border-surface-el rounded-lg px-3 py-2 text-sm text-text-p focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15 disabled:opacity-50"
        >
          {modelsLoading ? (
            <option>{t("common.loading", "加载中...")}</option>
          ) : models.length > 0 ? (
            models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))
          ) : (
            recommendedModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id} {m.note && `(${m.note})`}
              </option>
            ))
          )}
        </select>
        {recommendedModels.length > 0 && models.length === 0 && (
          <p className="mt-1 text-xs text-text-m">
            {t("setup.usingRecommended", "使用推荐模型列表")}
          </p>
        )}
      </div>

      {/* Temperature & Max Tokens */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-text-p mb-2">
            {t("settings.temperature", "温度")}
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={llm.temperature}
            onChange={(e) => setLLMConfig({ temperature: parseInt(e.target.value) })}
            className="w-full"
          />
          <div className="text-xs text-text-m mt-1">{(llm.temperature / 100).toFixed(1)}</div>
        </div>
        <div>
          <label className="block text-sm font-medium text-text-p mb-2">
            {t("settings.maxTokens", "最大 Token 数")}
          </label>
          <input
            type="number"
            value={llm.maxTokens}
            onChange={(e) => setLLMConfig({ maxTokens: parseInt(e.target.value) || 4096 })}
            className="w-full bg-surface border border-surface-el rounded-lg px-3 py-2 text-sm text-text-p focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15"
          />
        </div>
      </div>

      {/* Test Connection */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleTestConnection}
          disabled={testStatus === "testing" || !llm.apiKey}
          className="px-4 py-2 rounded-lg border border-surface-el text-sm text-text-s hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {testStatus === "testing" ? (
            <Loader className="w-4 h-4 animate-spin" />
          ) : testStatus === "success" ? (
            <CheckCircle className="w-4 h-4 text-accent" />
          ) : testStatus === "error" ? (
            <XCircle className="w-4 h-4 text-rose-500" />
          ) : (
            <CheckCircle className="w-4 h-4" />
          )}
          {t("settings.testConnection", "测试连接")}
        </button>
        {testResult && (
          <span className={`text-sm ${testStatus === "success" ? "text-accent" : testStatus === "error" ? "text-rose-500" : "text-text-m"}`}>
            {testResult}
          </span>
        )}
      </div>
    </div>
  );
}
