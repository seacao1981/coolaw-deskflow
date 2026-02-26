import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Plus,
  Trash2,
  Edit,
  Check,
  X,
  MessageSquare,
  Building,
  Phone,
  Bot,
  Wifi,
  WifiOff,
  Send,
} from "lucide-react";
import { useAppStore } from "../stores/appStore";

// IM 渠道类型
type ImChannelType =
  | "telegram"
  | "feishu"
  | "wechat_work"
  | "dingtalk"
  | "qq_bot"
  | "onebot";

interface ImChannelConfig {
  id: string;
  type: ImChannelType;
  name: string;
  enabled: boolean;
  status: "connected" | "disconnected" | "connecting";
  config: Record<string, string>;
  lastActive?: number;
}

// 渠道类型配置
const CHANNEL_TYPES: {
  type: ImChannelType;
  name: string;
  icon: React.ReactNode;
  color: string;
  description: string;
}[] = [
  {
    type: "telegram",
    name: "Telegram",
    icon: <Send className="w-5 h-5" />,
    color: "bg-blue-500",
    description: "Telegram 机器人",
  },
  {
    type: "feishu",
    name: "飞书",
    icon: <Building className="w-5 h-5" />,
    color: "bg-indigo-500",
    description: "飞书机器人",
  },
  {
    type: "wechat_work",
    name: "企业微信",
    icon: <MessageSquare className="w-5 h-5" />,
    color: "bg-green-500",
    description: "企业微信机器人",
  },
  {
    type: "dingtalk",
    name: "钉钉",
    icon: <Phone className="w-5 h-5" />,
    color: "bg-cyan-500",
    description: "钉钉机器人",
  },
  {
    type: "qq_bot",
    name: "QQ 机器人",
    icon: <Bot className="w-5 h-5" />,
    color: "bg-yellow-500",
    description: "QQ 群机器人",
  },
  {
    type: "onebot",
    name: "OneBot",
    icon: <Bot className="w-5 h-5" />,
    color: "bg-purple-500",
    description: "OneBot 协议机器人",
  },
];

/**
 * IM 通道管理视图
 */
export function IMChannelsView() {
  const { t } = useTranslation();
  const serverUrl = useAppStore((s) => s.serverUrl);
  const [channels, setChannels] = useState<ImChannelConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingChannel, setEditingChannel] = useState<ImChannelConfig | null>(null);

  // 加载渠道列表
  useEffect(() => {
    fetchChannels();
  }, []);

  const fetchChannels = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${serverUrl}/api/im/channels`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        const data = await response.json();
        setChannels(data.channels || []);
      }
    } catch (error) {
      console.error("Failed to fetch IM channels:", error);
    } finally {
      setLoading(false);
    }
  };

  // 切换渠道状态
  const toggleChannel = async (channelId: string, enabled: boolean) => {
    try {
      const response = await fetch(`${serverUrl}/api/im/channels/${channelId}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (response.ok) {
        setChannels((prev) =>
          prev.map((ch) => (ch.id === channelId ? { ...ch, enabled } : ch))
        );
      }
    } catch (error) {
      console.error("Failed to toggle channel:", error);
    }
  };

  // 删除渠道
  const deleteChannel = async (channelId: string) => {
    if (!confirm("确定要删除此渠道吗？")) return;
    try {
      const response = await fetch(`${serverUrl}/api/im/channels/${channelId}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        setChannels((prev) => prev.filter((ch) => ch.id !== channelId));
      }
    } catch (error) {
      console.error("Failed to delete channel:", error);
    }
  };

  // 测试渠道连接
  const testChannel = async (channelId: string) => {
    try {
      const response = await fetch(`${serverUrl}/api/im/channels/${channelId}/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const result = await response.json();
      if (result.success) {
        alert("渠道连接测试成功！");
      } else {
        alert(`渠道连接测试失败：${result.error}`);
      }
    } catch (error) {
      console.error("Failed to test channel:", error);
      alert("渠道连接测试失败");
    }
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-bg-base">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-surface">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-text-p">
              {t("nav.imchannels") || "IM 通道"}
            </h1>
            <p className="text-sm text-text-s mt-1">
              管理和配置即时通讯渠道集成
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-accent text-bg-deep rounded-lg hover:bg-accent-hover transition-colors"
          >
            <Plus className="w-4 h-4" />
            <span>添加渠道</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-text-s">
              <div className="animate-spin w-8 h-8 border-2 border-accent border-t-transparent rounded-full mx-auto mb-4" />
              <div>加载中...</div>
            </div>
          </div>
        ) : channels.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-md">
              <MessageSquare className="w-16 h-16 text-text-m mx-auto mb-4" />
              <h3 className="text-lg font-medium text-text-p mb-2">
                暂无 IM 渠道
              </h3>
              <p className="text-text-s mb-4">
                点击上方"添加渠道"按钮来配置 IM 机器人集成
              </p>
              <button
                onClick={() => setShowAddModal(true)}
                className="px-6 py-2 bg-accent text-bg-deep rounded-lg hover:bg-accent-hover transition-colors"
              >
                添加第一个渠道
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {channels.map((channel) => {
              const channelType = CHANNEL_TYPES.find(
                (t) => t.type === channel.type
              );
              return (
                <div
                  key={channel.id}
                  className="bg-bg-deep rounded-xl border border-surface p-4 hover:border-accent transition-colors"
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-10 h-10 rounded-lg ${channelType?.color} flex items-center justify-center text-white`}
                      >
                        {channelType?.icon}
                      </div>
                      <div>
                        <h3 className="font-medium text-text-p">
                          {channel.name || channelType?.name}
                        </h3>
                        <p className="text-xs text-text-s">
                          {channelType?.description}
                        </p>
                      </div>
                    </div>
                    <div
                      className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${
                        channel.enabled
                          ? "bg-green-500/10 text-green-500"
                          : "bg-text-m/10 text-text-m"
                      }`}
                    >
                      {channel.enabled ? (
                        <>
                          <Wifi className="w-3 h-3" />
                          <span>已启用</span>
                        </>
                      ) : (
                        <>
                          <WifiOff className="w-3 h-3" />
                          <span>已禁用</span>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Status */}
                  <div className="flex items-center gap-2 mb-3">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        channel.status === "connected"
                          ? "bg-green-500"
                          : channel.status === "connecting"
                          ? "bg-yellow-500 animate-pulse"
                          : "bg-red-500"
                      }`}
                    />
                    <span className="text-xs text-text-s">
                      {channel.status === "connected"
                        ? "已连接"
                        : channel.status === "connecting"
                        ? "连接中..."
                        : "未连接"}
                    </span>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 pt-3 border-t border-surface">
                    <button
                      onClick={() => toggleChannel(channel.id, !channel.enabled)}
                      className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors ${
                        channel.enabled
                          ? "bg-bg-base text-text-s hover:bg-bg-base/50"
                          : "bg-accent text-bg-deep hover:bg-accent-hover"
                      }`}
                    >
                      {channel.enabled ? (
                        <>
                          <X className="w-3.5 h-3.5" />
                          <span>禁用</span>
                        </>
                      ) : (
                        <>
                          <Check className="w-3.5 h-3.5" />
                          <span>启用</span>
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => testChannel(channel.id)}
                      className="px-3 py-1.5 bg-bg-base text-text-s rounded-lg hover:bg-bg-base/50 transition-colors text-xs"
                    >
                      测试
                    </button>
                    <button
                      onClick={() => setEditingChannel(channel)}
                      className="p-1.5 text-text-s hover:bg-bg-base rounded transition-colors"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteChannel(channel.id)}
                      className="p-1.5 text-red-500 hover:bg-red-500/10 rounded transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Add Channel Modal */}
      {showAddModal && (
        <AddChannelModal
          onClose={() => setShowAddModal(false)}
          onAdd={(channel) => {
            setChannels((prev) => [...prev, channel]);
            setShowAddModal(false);
          }}
        />
      )}

      {/* Edit Channel Modal */}
      {editingChannel && (
        <EditChannelModal
          channel={editingChannel}
          onClose={() => setEditingChannel(null)}
          onSave={(channel) => {
            setChannels((prev) =>
              prev.map((ch) => (ch.id === channel.id ? channel : ch))
            );
            setEditingChannel(null);
          }}
        />
      )}
    </div>
  );
}

// 添加渠道弹窗组件
function AddChannelModal({
  onClose,
  onAdd,
}: {
  onClose: () => void;
  onAdd: (channel: ImChannelConfig) => void;
}) {
  const serverUrl = useAppStore((s) => s.serverUrl);
  const [selectedType, setSelectedType] = useState<ImChannelType | null>(null);
  const [name, setName] = useState("");
  const [config, setConfig] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const handleAdd = async () => {
    if (!selectedType || !name.trim()) return;

    try {
      setLoading(true);
      const response = await fetch(`${serverUrl}/api/im/channels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: selectedType,
          name,
          config,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        onAdd(data.channel);
      }
    } catch (error) {
      console.error("Failed to add channel:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-bg-deep rounded-xl border border-surface w-full max-w-lg mx-4">
        <div className="p-4 border-b border-surface">
          <h2 className="text-lg font-semibold text-text-p">添加 IM 渠道</h2>
        </div>

        <div className="p-4 space-y-4 max-h-96 overflow-auto">
          {/* 渠道类型选择 */}
          <div>
            <label className="block text-sm font-medium text-text-p mb-2">
              渠道类型
            </label>
            <div className="grid grid-cols-2 gap-2">
              {CHANNEL_TYPES.map((type) => (
                <button
                  key={type.type}
                  onClick={() => setSelectedType(type.type)}
                  className={`flex items-center gap-2 p-3 rounded-lg border transition-colors ${
                    selectedType === type.type
                      ? "border-accent bg-accent/10"
                      : "border-surface hover:border-accent/50"
                  }`}
                >
                  <div className={`w-8 h-8 rounded ${type.color} flex items-center justify-center text-white`}>
                    {type.icon}
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-medium text-text-p">
                      {type.name}
                    </div>
                    <div className="text-xs text-text-s">{type.description}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 渠道名称 */}
          {selectedType && (
            <div>
              <label className="block text-sm font-medium text-text-p mb-2">
                渠道名称
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：客服机器人"
                className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
              />
            </div>
          )}

          {/* 配置表单 - 根据类型显示不同字段 */}
          {selectedType && (
            <div className="space-y-3">
              {selectedType === "telegram" && (
                <>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      Bot Token
                    </label>
                    <input
                      type="password"
                      onChange={(e) =>
                        setConfig({ ...config, bot_token: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      Webhook URL (可选)
                    </label>
                    <input
                      type="text"
                      onChange={(e) =>
                        setConfig({ ...config, webhook_url: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                </>
              )}
              {selectedType === "feishu" && (
                <>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      App ID
                    </label>
                    <input
                      type="text"
                      onChange={(e) =>
                        setConfig({ ...config, app_id: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      App Secret
                    </label>
                    <input
                      type="password"
                      onChange={(e) =>
                        setConfig({ ...config, app_secret: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      Bot Webhook URL
                    </label>
                    <input
                      type="text"
                      onChange={(e) =>
                        setConfig({ ...config, webhook_url: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                </>
              )}
              {selectedType === "wechat_work" && (
                <>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      Corp ID
                    </label>
                    <input
                      type="text"
                      onChange={(e) =>
                        setConfig({ ...config, corp_id: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      Webhook URL
                    </label>
                    <input
                      type="text"
                      onChange={(e) =>
                        setConfig({ ...config, webhook_url: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      Secret
                    </label>
                    <input
                      type="password"
                      onChange={(e) =>
                        setConfig({ ...config, secret: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                </>
              )}
              {selectedType === "dingtalk" && (
                <>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      AppKey
                    </label>
                    <input
                      type="text"
                      onChange={(e) =>
                        setConfig({ ...config, app_key: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      Webhook URL
                    </label>
                    <input
                      type="text"
                      onChange={(e) =>
                        setConfig({ ...config, webhook_url: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-text-s mb-1">
                      AppSecret
                    </label>
                    <input
                      type="password"
                      onChange={(e) =>
                        setConfig({ ...config, app_secret: e.target.value })
                      }
                      className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="p-4 border-t border-surface flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-text-s hover:bg-bg-base rounded-lg transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleAdd}
            disabled={!selectedType || !name.trim() || loading}
            className="px-4 py-2 bg-accent text-bg-deep rounded-lg hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "添加中..." : "添加"}
          </button>
        </div>
      </div>
    </div>
  );
}

// 编辑渠道弹窗组件
function EditChannelModal({
  channel,
  onClose,
  onSave,
}: {
  channel: ImChannelConfig;
  onClose: () => void;
  onSave: (channel: ImChannelConfig) => void;
}) {
  const [name, setName] = useState(channel.name);

  const handleSave = () => {
    onSave({ ...channel, name });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-bg-deep rounded-xl border border-surface w-full max-w-md mx-4">
        <div className="p-4 border-b border-surface">
          <h2 className="text-lg font-semibold text-text-p">编辑渠道</h2>
        </div>

        <div className="p-4">
          <label className="block text-sm font-medium text-text-p mb-2">
            渠道名称
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2 bg-bg-base border border-surface rounded-lg text-text-p focus:outline-none focus:border-accent"
          />
        </div>

        <div className="p-4 border-t border-surface flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-text-s hover:bg-bg-base rounded-lg transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-accent text-bg-deep rounded-lg hover:bg-accent-hover transition-colors"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
