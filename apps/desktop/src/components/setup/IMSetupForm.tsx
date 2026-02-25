import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Eye, EyeOff } from "lucide-react";
import { useSetupConfigStore } from "../../stores/setupConfigStore";

// IM 渠道配置
const IM_CHANNELS = [
  { value: "none", label: "暂不配置", icon: "🚫" },
  { value: "telegram", label: "Telegram", icon: "✈️" },
  { value: "feishu", label: "飞书", icon: "📱" },
  { value: "wework", label: "企业微信", icon: "💼" },
  { value: "dingtalk", label: "钉钉", icon: "🔔" },
  { value: "qq", label: "QQ 机器人", icon: "🐧" },
  { value: "onebot", label: "OneBot", icon: "🤖" },
];

interface IMSetupFormProps {
  required?: boolean;
  onComplete?: (data: any) => void;
}

export function IMSetupForm({ required, onComplete }: IMSetupFormProps) {
  const { t } = useTranslation();
  const { im, setIMConfig } = useSetupConfigStore();

  const [showToken, setShowToken] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  const selectedChannel = IM_CHANNELS.find((c) => c.value === (im?.channelType || "none"));

  const handleChannelChange = (channelType: string) => {
    if (channelType === "none") {
      setIMConfig(null);
      onComplete?.({ channelType: "none" });
    } else {
      setIMConfig({
        channelType,
        token: "",
        webhookUrl: "",
        secret: "",
      });
    }
  };

  const handleFieldChange = (field: string, value: string) => {
    if (im) {
      setIMConfig({ [field]: value });
    }
  };

  // 根据渠道类型获取配置字段说明
  const getFieldLabels = (channelType: string) => {
    switch (channelType) {
      case "telegram":
        return {
          token: "Bot Token",
          webhookUrl: "Webhook URL (可选)",
          secret: "",
        };
      case "feishu":
        return {
          token: "App ID",
          webhookUrl: "Bot Webhook URL",
          secret: "App Secret",
        };
      case "wework":
        return {
          token: "Corp ID",
          webhookUrl: "Webhook URL",
          secret: "Secret",
        };
      case "dingtalk":
        return {
          token: "AppKey",
          webhookUrl: "Webhook URL",
          secret: "AppSecret",
        };
      case "qq":
      case "onebot":
        return {
          token: "Access Token",
          webhookUrl: "WS 地址",
          secret: "",
        };
      default:
        return { token: "Token", webhookUrl: "Webhook URL", secret: "Secret" };
    }
  };

  const fieldLabels = selectedChannel && selectedChannel.value !== "none"
    ? getFieldLabels(selectedChannel.value)
    : { token: "Token", webhookUrl: "Webhook URL", secret: "Secret" };

  return (
    <div className="space-y-4">
      {/* Channel Selection */}
      <div>
        <label className="block text-sm font-medium text-text-p mb-2">
          {t("setup.full.imChannel", "IM 渠道")}
        </label>
        <div className="grid grid-cols-2 gap-2">
          {IM_CHANNELS.map((channel) => (
            <button
              key={channel.value}
              onClick={() => handleChannelChange(channel.value)}
              className={`px-3 py-2 rounded-lg border text-sm transition-colors cursor-pointer flex items-center gap-2 ${
                (im?.channelType || "none") === channel.value
                  ? "bg-accent/10 border-accent text-accent"
                  : "bg-surface border-surface-el text-text-s hover:bg-surface-el"
              }`}
            >
              <span>{channel.icon}</span>
              {channel.label}
            </button>
          ))}
        </div>
      </div>

      {/* Channel Config Fields */}
      {selectedChannel && selectedChannel.value !== "none" && (
        <>
          {/* Token */}
          <div>
            <label className="block text-sm font-medium text-text-p mb-2">
              {fieldLabels.token}
            </label>
            <div className="relative">
              <input
                type={showToken ? "text" : "password"}
                value={im?.token || ""}
                onChange={(e) => handleFieldChange("token", e.target.value)}
                placeholder={`请输入${fieldLabels.token}`}
                className="w-full bg-surface border border-surface-el rounded-lg px-3 py-2 pr-10 text-sm text-text-p focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-text-m hover:text-text-p cursor-pointer transition-colors"
              >
                {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Webhook URL */}
          {fieldLabels.webhookUrl && (
            <div>
              <label className="block text-sm font-medium text-text-p mb-2">
                {fieldLabels.webhookUrl}
              </label>
              <input
                type="url"
                value={im?.webhookUrl || ""}
                onChange={(e) => handleFieldChange("webhookUrl", e.target.value)}
                placeholder={`请输入${fieldLabels.webhookUrl}`}
                className="w-full bg-surface border border-surface-el rounded-lg px-3 py-2 text-sm text-text-p focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15"
              />
            </div>
          )}

          {/* Secret */}
          {fieldLabels.secret && (
            <div>
              <label className="block text-sm font-medium text-text-p mb-2">
                {fieldLabels.secret}
              </label>
              <div className="relative">
                <input
                  type={showSecret ? "text" : "password"}
                  value={im?.secret || ""}
                  onChange={(e) => handleFieldChange("secret", e.target.value)}
                  placeholder={`请输入${fieldLabels.secret}`}
                  className="w-full bg-surface border border-surface-el rounded-lg px-3 py-2 pr-10 text-sm text-text-p focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/15"
                />
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-text-m hover:text-text-p cursor-pointer transition-colors"
                >
                  {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          )}

          {/* Help Text */}
          <div className="bg-info/10 border border-info/30 rounded-lg p-3">
            <p className="text-xs text-info">
              💡 {t("setup.imHelp", "如何获取配置信息？")}
            </p>
            <p className="text-xs text-text-m mt-1">
              {selectedChannel.value === "telegram" && "在 Telegram 中搜索 @BotFather 创建机器人并获取 Token"}
              {selectedChannel.value === "feishu" && "在飞书开放平台创建应用，配置机器人并获取 App ID 和 Secret"}
              {selectedChannel.value === "wework" && "在企业微信管理后台创建应用并获取 Corp ID 和 Secret"}
              {selectedChannel.value === "dingtalk" && "在钉钉开放平台创建机器人应用并获取 AppKey 和 AppSecret"}
              {selectedChannel.value === "qq" && "使用 OneBot 框架连接 QQ 机器人"}
              {selectedChannel.value === "onebot" && "配置 OneBot WS 地址和 Access Token"}
            </p>
          </div>
        </>
      )}

      {/* Skip Option */}
      {!required && (
        <div className="pt-2">
          <p className="text-xs text-text-m">
            {t("setup.imSkip", "也可以稍后在设置中配置 IM 渠道")}
          </p>
        </div>
      )}
    </div>
  );
}
