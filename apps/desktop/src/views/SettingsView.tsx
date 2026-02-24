import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Play, Save, Plus, Eye, EyeOff, CheckCircle, XCircle, Loader, Sun, Moon } from "lucide-react";
import { useAppStore } from "../stores/appStore";
import { useThemeStore } from "../stores/themeStore";
import { useLocaleStore } from "../stores/localeStore";

type SettingsSection = "llm" | "channels" | "identity" | "system";
type SaveStatus = "idle" | "saving" | "success" | "error";
type TestStatus = "idle" | "testing" | "success" | "error";

interface ConfigData {
  llm_provider: string;
  llm_model: string;
  llm_temperature: number;
  llm_max_tokens: number;
  has_api_key: boolean;
  openai_base_url: string;
  server_host: string;
  server_port: number;
  memory_cache_size: number;
  tool_timeout: number;
}

interface ModelList {
  models: string[];
  provider: string;
  base_url: string | null;
}

interface TestResult {
  success: boolean;
  message: string;
  model?: string;
  provider?: string;
  latency_ms?: number;
}

interface ChannelConfig {
  channel_type: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  is_enabled: boolean;
  config: Record<string, any>;
  config_fields?: Array<{
    name: string;
    label: string;
    type: string;
    required: boolean;
  }>;
}

/**
 * Settings view with section navigation and configuration forms.
 */
export default function SettingsView() {
  const { t } = useTranslation();
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const locale = useLocaleStore((s) => s.locale);
  const setLocale = useLocaleStore((s) => s.setLocale);
  const [section, setSection] = useState<SettingsSection>("llm");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<ConfigData | null>(null);

  // Form state
  const [provider, setProvider] = useState("anthropic");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("claude-3-5-sonnet-20241022");
  const [maxTokens, setMaxTokens] = useState(4096);
  const [temperature, setTemperature] = useState(70);

  // System settings state
  const [serverPort, setServerPort] = useState(8420);
  const [logLevel, setLogLevel] = useState("INFO");
  const [memoryCacheSize, setMemoryCacheSize] = useState(1000);
  const [toolTimeout, setToolTimeout] = useState(30);

  // Model list state
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  // Channels state
  const [channels, setChannels] = useState<ChannelConfig[]>([]);
  const [channelsLoading, setChannelsLoading] = useState(false);
  const [channelConfig, setChannelConfig] = useState<Record<string, any>>({});

  // Status state
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [testStatus, setTestStatus] = useState<TestStatus>("idle");
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [saveMessage, setSaveMessage] = useState("");

  const serverUrl = useAppStore((s) => s.serverUrl);

  // Update base URL when provider changes
  useEffect(() => {
    if (provider === "dashscope") {
      setBaseUrl("https://dashscope.aliyuncs.com/compatible-mode/v1");
    } else if (provider === "openai") {
      setBaseUrl("https://api.openai.com/v1");
    }
  }, [provider]);

  // Fetch available models when provider, base_url, or api_key changes
  useEffect(() => {
    const fetchModels = async () => {
      if (provider === "anthropic") {
        // Anthropic doesn't have a models list API
        setModels([]);
        return;
      }

      setModelsLoading(true);
      try {
        const params = new URLSearchParams({
          provider,
          base_url: baseUrl,
        });
        if (apiKey) {
          params.append("api_key", apiKey);
        }

        const response = await fetch(`${serverUrl}/api/llm/models?${params}`);
        if (response.ok) {
          const data: ModelList = await response.json();
          setModels(data.models);
          // If current model is not in the list, select the first one
          if (!data.models.includes(model) && data.models.length > 0) {
            setModel(data.models[0] || model);
          }
        }
      } catch (error) {
        console.error("Failed to fetch models:", error);
      } finally {
        setModelsLoading(false);
      }
    };

    // Debounce model fetching
    const timeoutId = setTimeout(fetchModels, 500);
    return () => clearTimeout(timeoutId);
  }, [provider, baseUrl, apiKey, serverUrl]);

  // Fetch config on mount
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        const response = await fetch(`${serverUrl}/api/config`);
        if (response.ok) {
          const data = await response.json();
          setConfig(data);
          setProvider(data.llm_provider);
          setBaseUrl(data.openai_base_url || "https://api.openai.com/v1");
          setModel(data.llm_model);
          setMaxTokens(data.llm_max_tokens);
          setTemperature(Math.round(data.llm_temperature * 100));
          // System settings
          setServerPort(data.server_port || 8420);
          setLogLevel(data.log_level || "INFO");
          setMemoryCacheSize(data.memory_cache_size || 1000);
          setToolTimeout(data.tool_timeout || 30);
        }
      } catch (error) {
        console.error("Failed to fetch config:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, [serverUrl]);

  // Fetch channels when section changes to channels
  useEffect(() => {
    if (section === "channels" && !channels.length) {
      fetchChannels();
    }
  }, [section]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleTestConnection = async () => {
    setTestStatus("testing");
    setTestResult(null);

    try {
      const response = await fetch(`${serverUrl}/api/llm/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          model,
          api_key: apiKey,
          base_url: provider !== "anthropic" ? baseUrl : undefined,
          temperature: temperature / 100,
          max_tokens: 100,
        }),
      });

      const result: TestResult = await response.json();
      setTestResult(result);
      setTestStatus(result.success ? "success" : "error");

      // Reset status after 5 seconds
      setTimeout(() => {
        setTestStatus("idle");
        setTestResult(null);
      }, 5000);
    } catch (error) {
      setTestResult({
        success: false,
        message: `Connection failed: ${error}`,
      });
      setTestStatus("error");

      setTimeout(() => {
        setTestStatus("idle");
        setTestResult(null);
      }, 5000);
    }
  };

  // Fetch channels
  const fetchChannels = async () => {
    setChannelsLoading(true);
    try {
      const response = await fetch(`${serverUrl}/api/channels`);
      if (response.ok) {
        const data = await response.json();
        setChannels(data.channels || []);
      }
    } catch (error) {
      console.error("Failed to fetch channels:", error);
    } finally {
      setChannelsLoading(false);
    }
  };

  // Save channel config
  const saveChannelConfig = async (channelType: string, config: Record<string, any>) => {
    try {
      const response = await fetch(`${serverUrl}/api/channels/${channelType}/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config }),
      });
      if (response.ok) {
        fetchChannels();
        return { success: true };
      }
      return { success: false, error: "Failed to save" };
    } catch (error) {
      return { success: false, error: String(error) };
    }
  };

  // Toggle channel
  const toggleChannel = async (channelType: string, enable: boolean) => {
    try {
      const response = await fetch(`${serverUrl}/api/channels/${channelType}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: enable ? "enable" : "disable" }),
      });
      if (response.ok) {
        fetchChannels();
      }
    } catch (error) {
      console.error("Failed to toggle channel:", error);
    }
  };

  // Test channel connection
  const testChannelConnection = async (channelType: string) => {
    setTestStatus("testing");
    try {
      const response = await fetch(`${serverUrl}/api/channels/${channelType}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const result = await response.json();
      setTestStatus(result.success ? "success" : "error");
      setTestResult(result);
      setTimeout(() => {
        setTestStatus("idle");
        setTestResult(null);
      }, 5000);
    } catch (error) {
      setTestStatus("error");
      setTestResult({ success: false, message: "Connection test failed" });
      setTimeout(() => {
        setTestStatus("idle");
        setTestResult(null);
      }, 5000);
    }
  };

  const handleSave = async () => {
    setSaveStatus("saving");
    setSaveMessage("");

    try {
      const response = await fetch(`${serverUrl}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          llm_provider: provider,
          llm_model: model,
          llm_temperature: temperature / 100,
          llm_max_tokens: maxTokens,
          ...(apiKey && { api_key: apiKey }),
          ...(provider !== "anthropic" && { base_url: baseUrl }),
          // System settings
          server_port: serverPort,
          log_level: logLevel,
          memory_cache_size: memoryCacheSize,
          tool_timeout: toolTimeout,
        }),
      });

      if (response.ok) {
        setSaveStatus("success");
        setSaveMessage(t("settings.configurationSaved"));

        // Reload config after save to reflect changes
        // But keep the API key in state since backend doesn't return it
        const newConfig = await fetch(`${serverUrl}/api/config`);
        if (newConfig.ok) {
          const data = await newConfig.json();
          setConfig(data);
          // Don't clear apiKey from state - keep it for user convenience
          setProvider(data.llm_provider);
          setBaseUrl(data.openai_base_url || "https://api.openai.com/v1");
          setModel(data.llm_model);
          setMaxTokens(data.llm_max_tokens);
          setTemperature(Math.round(data.llm_temperature * 100));
        }

        // Reset status after 3 seconds
        setTimeout(() => {
          setSaveStatus("idle");
          setSaveMessage("");
        }, 3000);
      } else {
        const error = await response.json();
        setSaveStatus("error");
        setSaveMessage(error.detail || t("settings.failedToSave"));

        setTimeout(() => {
          setSaveStatus("idle");
          setSaveMessage("");
        }, 5000);
      }
    } catch (error) {
      setSaveStatus("error");
      setSaveMessage(`${t("common.error")}: ${error}`);

      setTimeout(() => {
        setSaveStatus("idle");
        setSaveMessage("");
      }, 5000);
    }
  };

  // Store API key in session storage to persist across page reloads
  useEffect(() => {
    if (apiKey) {
      sessionStorage.setItem(`llm_api_key_${provider}`, apiKey);
    }
  }, [apiKey, provider]);

  // Load API key from session storage on mount and when provider changes
  useEffect(() => {
    const storedKey = sessionStorage.getItem(`llm_api_key_${provider}`);
    if (storedKey) {
      setApiKey(storedKey);
    }
  }, [provider]);

  const NAV: { id: SettingsSection; label: string }[] = [
    { id: "llm", label: t("settings.llm") },
    { id: "channels", label: t("settings.channels") },
    { id: "identity", label: t("settings.identity") },
    { id: "system", label: t("settings.system") },
  ];

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="h-14 border-b border-surface flex items-center justify-between px-6 shrink-0">
        <h1 className="text-lg font-semibold font-code">{t("settings.title")}</h1>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* Section Nav */}
        <div className="w-48 border-r border-surface py-2 px-2 shrink-0">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setSection(item.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors duration-200 mt-0.5 ${
                section === item.id
                  ? "bg-accent/10 text-accent"
                  : "text-text-s hover:bg-surface"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>

        {/* Form */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="max-w-xl space-y-6 pb-8 p-6">
            {section === "llm" && (
              <>
                <div>
                  <h2 className="text-base font-semibold font-code">{t("settings.llmConfiguration")}</h2>
                  <p className="text-sm text-text-s mt-1">
                    {t("settings.configureProvider")}
                  </p>
                </div>

                {loading ? (
                  <div className="text-sm text-text-m">{t("common.loading")}</div>
                ) : (
                  <>
                    <FormField label={t("settings.provider")}>
                      <select
                        className="setting-input"
                        value={provider}
                        onChange={(e) => setProvider(e.target.value)}
                      >
                        <option value="anthropic">{t("settings.providerOptions.anthropic")}</option>
                        <option value="openai">{t("settings.providerOptions.openai")}</option>
                        <option value="dashscope">{t("settings.providerOptions.dashscope")}</option>
                      </select>
                    </FormField>

                    <FormField
                      label={t("settings.baseUrl")}
                      hint={
                        provider === "openai"
                          ? t("settings.baseUrlHint.openai")
                          : provider === "dashscope"
                          ? t("settings.baseUrlHint.dashscope")
                          : t("settings.baseUrlHint.anthropic")
                      }
                    >
                      <input
                        type="url"
                        value={baseUrl}
                        onChange={(e) => setBaseUrl(e.target.value)}
                        className="setting-input"
                        placeholder={
                          provider === "openai"
                            ? "https://api.openai.com/v1"
                            : provider === "dashscope"
                            ? "https://dashscope.aliyuncs.com/compatible-mode/v1"
                            : t("settings.notApplicable")
                        }
                        disabled={provider === "anthropic"}
                      />
                    </FormField>

                    <FormField label={t("settings.apiKey")} hint={t("settings.apiKeyHint")}>
                      <div className="relative">
                        <input
                          type={showKey ? "text" : "password"}
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                          placeholder={apiKey || config?.has_api_key ? "••••••••••••••••••••" : t("settings.enterApiKey")}
                          className="setting-input pr-20"
                        />
                        <button
                          onClick={() => setShowKey(!showKey)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 rounded text-xs text-text-m hover:text-text-p border border-surface-el hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-1"
                        >
                          {showKey ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                          {showKey ? t("common.hide") : t("common.show")}
                        </button>
                      </div>
                    </FormField>

                    <FormField
                      label={t("settings.model")}
                      hint={modelsLoading ? t("common.loading") : models.length > 0 ? t("settings.modelsLoaded", { count: models.length }) : t("settings.defaultModelList")}
                    >
                      <div className="relative">
                        <select
                          className="setting-input pr-10"
                          value={model}
                          onChange={(e) => setModel(e.target.value)}
                          disabled={modelsLoading}
                        >
                          {modelsLoading && <option>{t("common.loading")}</option>}
                          {!modelsLoading && models.length === 0 && provider === "anthropic" && (
                            <>
                              <option value="claude-3-5-sonnet-20241022">claude-3-5-sonnet-20241022</option>
                              <option value="claude-3-opus-20240229">claude-3-opus-20240229</option>
                              <option value="claude-3-haiku-20240307">claude-3-haiku-20240307</option>
                            </>
                          )}
                          {!modelsLoading && models.length === 0 && provider === "openai" && (
                            <>
                              <option value="gpt-4o">gpt-4o</option>
                              <option value="gpt-4o-mini">gpt-4o-mini</option>
                              <option value="gpt-4-turbo">gpt-4-turbo</option>
                              <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
                            </>
                          )}
                          {!modelsLoading && models.length === 0 && provider === "dashscope" && (
                            <>
                              <option value="qwen3.5-plus">qwen3.5-plus</option>
                              <option value="qwen-max">qwen-max</option>
                              <option value="qwen-plus">qwen-plus</option>
                              <option value="qwen-turbo">qwen-turbo</option>
                            </>
                          )}
                          {!modelsLoading && models.map((m) => (
                            <option key={m} value={m}>{m}</option>
                          ))}
                        </select>
                        {modelsLoading && (
                          <Loader className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-m animate-spin" />
                        )}
                      </div>
                    </FormField>

                    <FormField label={t("settings.maxTokens")}>
                      <input
                        type="number"
                        value={maxTokens}
                        onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                        className="setting-input"
                      />
                    </FormField>

                    <FormField label={t("settings.temperature")}>
                      <div className="flex items-center gap-3">
                        <input
                          type="range"
                          min="0"
                          max="200"
                          value={temperature}
                          onChange={(e) => setTemperature(parseInt(e.target.value))}
                          className="flex-1 accent-accent cursor-pointer"
                        />
                        <span className="text-sm font-code text-text-p w-10 text-right">
                          {(temperature / 100).toFixed(1)}
                        </span>
                      </div>
                    </FormField>

                    <FormField label={t("settings.fallbackProvider")}>
                      <button className="w-full px-4 py-2.5 rounded-lg border border-dashed border-surface-el text-sm text-text-m hover:border-text-m hover:text-text-s cursor-pointer transition-colors duration-200 flex items-center justify-center gap-2">
                        <Plus className="w-4 h-4" />
                        {t("settings.addFallbackProvider")}
                      </button>
                    </FormField>

                    {/* Test Connection Result */}
                    {testResult && (
                      <div className={`p-4 rounded-lg border ${
                        testResult.success
                          ? "bg-green-500/10 border-green-500/30"
                          : "bg-red-500/10 border-red-500/30"
                      }`}>
                        <div className="flex items-start gap-3">
                          {testResult.success ? (
                            <CheckCircle className="w-5 h-5 text-green-500 mt-0.5" />
                          ) : (
                            <XCircle className="w-5 h-5 text-red-500 mt-0.5" />
                          )}
                          <div className="flex-1">
                            <p className={`text-sm font-medium ${
                              testResult.success ? "text-green-500" : "text-red-500"
                            }`}>
                              {testResult.success ? t("settings.connectionSuccessful") : t("settings.connectionFailed")}
                            </p>
                            <p className="text-sm text-text-m mt-1">{testResult.message}</p>
                            {testResult.latency_ms && (
                              <p className="text-xs text-text-s mt-2">
                                {t("settings.latency")}: {testResult.latency_ms} ms
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Save Status Message */}
                    {saveMessage && (
                      <div className={`p-4 rounded-lg border ${
                        saveStatus === "success"
                          ? "bg-green-500/10 border-green-500/30"
                          : saveStatus === "error"
                          ? "bg-red-500/10 border-red-500/30"
                          : "bg-blue-500/10 border-blue-500/30"
                      }`}>
                        <div className="flex items-start gap-3">
                          {saveStatus === "success" && (
                            <CheckCircle className="w-5 h-5 text-green-500 mt-0.5" />
                          )}
                          {saveStatus === "error" && (
                            <XCircle className="w-5 h-5 text-red-500 mt-0.5" />
                          )}
                          {saveStatus === "saving" && (
                            <Loader className="w-5 h-5 text-blue-500 mt-0.5 animate-spin" />
                          )}
                          <p className={`text-sm font-medium ${
                            saveStatus === "success"
                              ? "text-green-500"
                              : saveStatus === "error"
                              ? "text-red-500"
                              : "text-blue-500"
                          }`}>
                            {saveMessage}
                          </p>
                        </div>
                      </div>
                    )}

                    <div className="flex items-center gap-3 pt-4 border-t border-surface-el">
                      <button
                        onClick={handleTestConnection}
                        disabled={testStatus === "testing" || !apiKey}
                        className="px-4 py-2 rounded-lg text-sm text-text-s border border-surface-el hover:bg-surface cursor-pointer transition-colors duration-200 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {testStatus === "testing" ? (
                          <Loader className="w-4 h-4 animate-spin" />
                        ) : (
                          <Play className="w-4 h-4" />
                        )}
                        {testStatus === "testing" ? t("settings.testing") : t("settings.testConnection")}
                      </button>
                      <button
                        onClick={handleSave}
                        disabled={saveStatus === "saving"}
                        className={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors duration-200 flex items-center gap-2 ${
                          saveStatus === "success"
                            ? "bg-green-500 text-white"
                            : saveStatus === "error"
                            ? "bg-red-500 text-white"
                            : "bg-accent text-bg-deep hover:bg-accent-hover"
                        } disabled:opacity-50 disabled:cursor-not-allowed`}
                      >
                        {saveStatus === "saving" ? (
                          <Loader className="w-4 h-4 animate-spin" />
                        ) : saveStatus === "success" ? (
                          <CheckCircle className="w-4 h-4" />
                        ) : (
                          <Save className="w-4 h-4" />
                        )}
                        {saveStatus === "saving"
                          ? t("common.saving")
                          : saveStatus === "success"
                          ? t("settings.saved")
                          : t("settings.save")}
                      </button>
                    </div>
                  </>
                )}
              </>
            )}

            {section === "channels" && (
              <div className="flex-1 overflow-y-auto">
                <div>
                  <h2 className="text-base font-semibold font-code">{t("settings.channelConfiguration")}</h2>
                  <p className="text-sm text-text-s mt-1">{t("settings.configureImChannels")}</p>
                </div>

                {/* Channel List */}
                <div className="mt-6 space-y-3">
                  {channelsLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader className="w-6 h-6 text-text-m animate-spin" />
                    </div>
                  ) : channels.length === 0 ? (
                    <div className="text-center py-12 text-text-m text-sm">
                      {t("settings.noChannelsConfigured")}
                    </div>
                  ) : (
                    channels.map((channel) => (
                      <div
                        key={channel.channel_type}
                        className="bg-surface border border-surface-el rounded-xl p-4"
                      >
                        <div className="flex items-center gap-4">
                          {/* Icon */}
                          <div className={`w-12 h-12 rounded-lg flex items-center justify-center bg-${channel.color}-500/10 text-${channel.color}-400`}>
                            <span className="text-lg font-bold capitalize">{channel.channel_type.slice(0, 2)}</span>
                          </div>

                          {/* Info */}
                          <div className="flex-1">
                            <h3 className="text-sm font-semibold font-code">{channel.name}</h3>
                            <p className="text-xs text-text-s mt-0.5">{channel.description}</p>
                          </div>

                          {/* Toggle */}
                          <button
                            onClick={() => toggleChannel(channel.channel_type, !channel.is_enabled)}
                            className={`w-12 h-6 rounded-full transition-colors duration-200 ${
                              channel.is_enabled ? "bg-accent" : "bg-text-m/30"
                            } flex items-center px-1`}
                          >
                            <div className={`w-4 h-4 rounded-full bg-bg-deep transition-transform duration-200 ${
                              channel.is_enabled ? "translate-x-6" : ""
                            }`} />
                          </button>
                        </div>

                        {/* Config Fields */}
                        {channel.is_enabled && (
                          <div className="mt-4 pt-4 border-t border-surface-el space-y-3">
                            {channel.config_fields?.map((field) => (
                              <div key={field.name}>
                                <label className="text-xs text-text-m block mb-1">{field.label}</label>
                                <input
                                  type={field.type === "password" ? "password" : "text"}
                                  placeholder={field.label}
                                  value={channelConfig[field.name] || ""}
                                  onChange={(e) => setChannelConfig({ ...channelConfig, [field.name]: e.target.value })}
                                  className="w-full bg-bg-base border border-surface-el rounded-lg px-3 py-2 text-sm focus:border-accent focus:outline-none"
                                />
                              </div>
                            ))}
                            <div className="flex gap-3 pt-2">
                              <button
                                onClick={() => saveChannelConfig(channel.channel_type, channelConfig)}
                                className="px-4 py-1.5 rounded-lg bg-accent text-bg-deep text-sm font-medium hover:bg-accent-hover transition-colors flex items-center gap-2"
                              >
                                <Save className="w-4 h-4" />
                                {t("settings.saveChannelConfig")}
                              </button>
                              <button
                                onClick={() => testChannelConnection(channel.channel_type)}
                                className="px-4 py-1.5 rounded-lg text-sm font-medium border border-surface-el hover:bg-surface transition-colors flex items-center gap-2"
                              >
                                {testStatus === "testing" ? (
                                  <Loader className="w-4 h-4 animate-spin" />
                                ) : testStatus === "success" ? (
                                  <CheckCircle className="w-4 h-4 text-accent" />
                                ) : (
                                  <Play className="w-4 h-4" />
                                )}
                                {t("settings.testConnection")}
                              </button>
                            </div>
                            {testResult && (
                              <div className={`text-xs ${testResult.success ? "text-accent" : "text-rose-500"}`}>
                                {testResult.message}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>

                {/* Add Channel Button */}
                <div className="mt-6">
                  <button
                    onClick={fetchChannels}
                    className="w-full py-3 rounded-xl border-2 border-dashed border-surface-el text-text-m hover:border-accent/50 hover:text-accent transition-colors flex items-center justify-center gap-2"
                  >
                    <Plus className="w-5 h-5" />
                    {t("settings.refreshChannels")}
                  </button>
                </div>
              </div>
            )}

            {section === "identity" && (
              <IdentitySection />
            )}

            {section === "system" && (
              <>
                <div>
                  <h2 className="text-base font-semibold font-code">{t("settings.general")}</h2>
                  <p className="text-sm text-text-s mt-1">{t("settings.generalApplicationSettings")}</p>
                </div>

                {/* Theme and Language Settings */}
                <div className="space-y-4 py-4 border-b border-surface-el">
                  <FormField label={t("settings.theme")} hint={`${t("settings.themeDark")} / ${t("settings.themeLight")}`}>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => theme !== "dark" && toggleTheme()}
                        className={`flex-1 py-2 px-3 rounded-lg border transition-colors flex items-center justify-center gap-2 ${
                          theme === "dark"
                            ? "bg-accent text-bg-deep border-accent"
                            : "border-surface-el text-text-s hover:bg-surface"
                        }`}
                      >
                        <Moon className="w-4 h-4" />
                        {t("settings.themeDark")}
                      </button>
                      <button
                        onClick={() => theme !== "light" && toggleTheme()}
                        className={`flex-1 py-2 px-3 rounded-lg border transition-colors flex items-center justify-center gap-2 ${
                          theme === "light"
                            ? "bg-accent text-bg-deep border-accent"
                            : "border-surface-el text-text-s hover:bg-surface"
                        }`}
                      >
                        <Sun className="w-4 h-4" />
                        {t("settings.themeLight")}
                      </button>
                    </div>
                  </FormField>

                  <FormField label={t("settings.language")} hint={`${t("settings.languageChinese")} / ${t("settings.languageEnglish")}`}>
                    <select
                      value={locale}
                      onChange={(e) => setLocale(e.target.value as "zh-CN" | "en-US")}
                      className="setting-input"
                    >
                      <option value="zh-CN">{t("settings.languageChinese")}</option>
                      <option value="en-US">{t("settings.languageEnglish")}</option>
                    </select>
                  </FormField>
                </div>

                <FormField label={t("settings.serverPort")} hint={t("settings.requiresRestart")}>
                  <input
                    type="number"
                    value={serverPort}
                    onChange={(e) => setServerPort(parseInt(e.target.value) || 8420)}
                    className="setting-input"
                  />
                </FormField>
                <FormField label={t("settings.logLevel")} hint={t("settings.logLevelHint")}>
                  <select
                    value={logLevel}
                    onChange={(e) => setLogLevel(e.target.value)}
                    className="setting-input"
                  >
                    <option>INFO</option>
                    <option>DEBUG</option>
                    <option>WARNING</option>
                    <option>ERROR</option>
                  </select>
                </FormField>
                <FormField label={t("settings.memoryCacheSize")} hint={t("settings.memoryCacheSizeHint")}>
                  <input
                    type="number"
                    value={memoryCacheSize}
                    onChange={(e) => setMemoryCacheSize(parseInt(e.target.value) || 1000)}
                    className="setting-input"
                  />
                </FormField>
                <FormField label={t("settings.toolTimeout")} hint={t("settings.toolTimeoutHint")}>
                  <input
                    type="number"
                    value={toolTimeout}
                    onChange={(e) => setToolTimeout(parseInt(e.target.value) || 30)}
                    className="setting-input"
                  />
                </FormField>
                <div className="flex items-center gap-3 pt-4 border-t border-surface-el">
                  <button
                    onClick={handleSave}
                    disabled={saveStatus === "saving"}
                    className={`px-4 py-2 rounded-lg text-sm font-medium cursor-pointer transition-colors duration-200 flex items-center gap-2 ${
                      saveStatus === "success"
                        ? "bg-green-500 text-white"
                        : saveStatus === "error"
                        ? "bg-red-500 text-white"
                        : "bg-accent text-bg-deep hover:bg-accent-hover"
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    {saveStatus === "saving" ? (
                      <Loader className="w-4 h-4 animate-spin" />
                    ) : saveStatus === "success" ? (
                      <CheckCircle className="w-4 h-4" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    {saveStatus === "saving"
                      ? t("common.saving")
                      : saveStatus === "success"
                      ? t("settings.saved")
                      : t("settings.save")}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-text-s block">{label}</label>
      {children}
      {hint && <p className="text-xs text-text-m">{hint}</p>}
    </div>
  );
}

// Identity Section Component
function IdentitySection() {
  const { t } = useTranslation();
  const [personas, setPersonas] = useState<any[]>([]);
  const [currentPersona, setCurrentPersona] = useState<string>("default");
  const [loading, setLoading] = useState(true);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const serverUrl = useAppStore((s) => s.serverUrl);

  useEffect(() => {
    fetchPersonas();
  }, []);

  const fetchPersonas = async () => {
    try {
      const response = await fetch(`${serverUrl}/api/identity`);
      if (response.ok) {
        const data = await response.json();
        setPersonas(data.personas || []);
      }
    } catch (error) {
      console.error("Failed to fetch personas:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleActivate = async (key: string) => {
    setSaveStatus("saving");
    try {
      const response = await fetch(`${serverUrl}/api/identity/${key}/activate`, {
        method: "POST",
      });
      if (response.ok) {
        setCurrentPersona(key);
        setSaveStatus("success");
        setTimeout(() => setSaveStatus("idle"), 2000);
      }
    } catch (error) {
      setSaveStatus("error");
      setTimeout(() => setSaveStatus("idle"), 2000);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-base font-semibold font-code">{t("settings.identityConfiguration")}</h2>
          <p className="text-sm text-text-s mt-1">{t("settings.selectPersona")}</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 rounded-lg bg-accent text-bg-deep text-sm font-medium hover:bg-accent-hover transition-colors flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          {t("settings.createPersona")}
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader className="w-6 h-6 text-text-m animate-spin" />
        </div>
      ) : personas.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-text-m text-sm">{t("settings.noPersonasFound")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {personas.map((persona) => (
            <div
              key={persona.key}
              className={`bg-surface border border-surface-el rounded-xl p-4 cursor-pointer transition-colors ${
                currentPersona === persona.key
                  ? "border-accent bg-accent/5"
                  : "hover:border-text-m"
              }`}
              onClick={() => handleActivate(persona.key)}
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold font-code">{persona.name}</h3>
                  <p className="text-xs text-text-s mt-1">{persona.description}</p>
                </div>
                {currentPersona === persona.key && (
                  <CheckCircle className="w-5 h-5 text-accent" />
                )}
              </div>
              <div className="mt-3 flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded ${
                  persona.is_custom ? "bg-purple-500/10 text-purple-400" : "bg-blue-500/10 text-blue-400"
                }`}>
                  {persona.is_custom ? t("settings.customPersona") : t("settings.builtInPersonas")}
                </span>
                {saveStatus === "success" && currentPersona === persona.key && (
                  <span className="text-xs text-green-500 ml-auto">{t("settings.activated")}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Persona Modal */}
      {showCreateModal && (
        <CreatePersonaModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            fetchPersonas();
          }}
        />
      )}
    </div>
  );
}

// Create Persona Modal Component
function CreatePersonaModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [soul, setSoul] = useState("");
  const [agent, setAgent] = useState("");
  const [user, setUser] = useState("");
  const [saving, setSaving] = useState(false);
  const serverUrl = useAppStore((s) => s.serverUrl);

  const handleCreate = async () => {
    if (!key) return;

    setSaving(true);
    try {
      const response = await fetch(`${serverUrl}/api/identity/custom`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          key,
          name,
          description,
          soul,
          agent,
          user,
        }),
      });

      if (response.ok) {
        onCreated();
      }
    } catch (error) {
      console.error("Failed to create persona:", error);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-surface border border-surface-el rounded-xl p-6 w-full max-w-lg max-h-[80vh] overflow-y-auto">
        <h2 className="text-lg font-semibold font-code mb-4">{t("settings.personaModal.title")}</h2>

        <div className="space-y-4">
          <FormField label={t("settings.personaModal.keyLabel")}>
            <input
              type="text"
              value={key}
              onChange={(e) => setKey(e.target.value.replace(/[^a-z0-9_]/gi, "_").toLowerCase())}
              placeholder={t("settings.personaModal.keyPlaceholder")}
              className="setting-input"
            />
          </FormField>

          <FormField label={t("settings.personaModal.nameLabel")}>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("settings.personaModal.namePlaceholder")}
              className="setting-input"
            />
          </FormField>

          <FormField label={t("settings.personaModal.descriptionLabel")}>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("settings.personaModal.descriptionPlaceholder")}
              className="setting-input"
            />
          </FormField>

          <FormField label={t("settings.personaModal.soulLabel")}>
            <textarea
              value={soul}
              onChange={(e) => setSoul(e.target.value)}
              placeholder={t("settings.personaModal.soulPlaceholder")}
              rows={4}
              className="setting-input"
            />
          </FormField>

          <FormField label={t("settings.personaModal.agentLabel")}>
            <textarea
              value={agent}
              onChange={(e) => setAgent(e.target.value)}
              placeholder={t("settings.personaModal.agentPlaceholder")}
              rows={4}
              className="setting-input"
            />
          </FormField>

          <FormField label={t("settings.personaModal.userLabel")}>
            <textarea
              value={user}
              onChange={(e) => setUser(e.target.value)}
              placeholder={t("settings.personaModal.userPlaceholder")}
              rows={3}
              className="setting-input"
            />
          </FormField>
        </div>

        <div className="flex gap-3 mt-6 pt-4 border-t border-surface-el">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 rounded-lg text-sm font-medium border border-surface-el hover:bg-surface transition-colors"
          >
            {t("common.cancel")}
          </button>
          <button
            onClick={handleCreate}
            disabled={saving || !key}
            className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-accent text-bg-deep hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {saving && <Loader className="w-4 h-4 animate-spin" />}
            {saving ? t("settings.personaModal.creating") : t("settings.personaModal.create")}
          </button>
        </div>
      </div>
    </div>
  );
}
