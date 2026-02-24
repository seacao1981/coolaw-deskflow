# Settings UI 改进方案

## 📅 日期: 2026-02-21
## 🎯 目标: 增强 LLM 配置的灵活性和易用性

---

## 🐛 当前问题

### 问题 1: Base URL 未在 UI 暴露

**现状**：
- 后端配置支持 `openai_base_url`（默认: `https://api.openai.com/v1`）
- 前端 UI **没有** Base URL 输入框
- 用户只能通过修改 `.env` 文件或环境变量配置

**影响**：
- 无法在 UI 中使用自定义 API 地址
- 无法使用本地部署的模型（如 Ollama：`http://localhost:11434/v1`）
- 无法使用第三方兼容 API（如 Azure OpenAI、国内 API 服务等）

### 问题 2: 模型列表硬编码

**现状**：
- 模型列表是静态的 `<option>` 元素
- 每个 Provider 的模型列表写死在前端代码中

**影响**：
- 切换 Provider 时需要手动更新选项
- 无法根据实际 API 获取可用模型列表
- 新模型发布后需要修改代码

---

## ✅ 改进方案

### 方案 1: 添加 Base URL 配置 (高优先级)

#### 1.1 前端 UI 修改

**文件**: `apps/desktop/src/views/SettingsView.tsx`

在 "Provider" 和 "API Key" 之间添加：

```tsx
<FormField
  label="Base URL"
  hint="API endpoint URL. Leave default for official APIs, or enter custom URL for self-hosted models (e.g., http://localhost:11434/v1 for Ollama)."
>
  <input
    type="url"
    defaultValue="https://api.openai.com/v1"
    className="setting-input"
    placeholder="https://api.openai.com/v1"
  />
</FormField>
```

**位置**: 第70行之后

#### 1.2 后端 API 修改

**文件**: `src/deskflow/api/routes/config.py`

确保 `/api/config` 端点支持读取和更新 `base_url`：

```python
class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    api_key: str | None = None
    base_url: str | None = None  # ✅ 添加这一行
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
```

#### 1.3 UI 显示逻辑

根据 Provider 显示/隐藏 Base URL：

```tsx
{provider === "openai" && (
  <FormField label="Base URL" hint="...">
    <input type="url" defaultValue={baseUrl} className="setting-input" />
  </FormField>
)}
```

**显示条件**：
- **OpenAI Compatible**: 显示（必需）
- **Anthropic**: 隐藏（官方固定 URL）
- **DashScope**: 隐藏（官方固定 URL）

---

### 方案 2: 动态模型列表 (中优先级)

#### 2.1 后端 API 新增端点

**文件**: `src/deskflow/api/routes/config.py`

新增 `/api/models` 端点：

```python
@router.get("/api/models")
async def list_models(
    provider: str,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, list[str]]:
    """Fetch available models from the provider's API.

    Returns:
        {"models": ["model-id-1", "model-id-2", ...]}
    """
    if provider == "anthropic":
        # Anthropic 没有 list models API，返回已知模型列表
        return {
            "models": [
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229",
                "claude-3-haiku-20240307",
            ]
        }

    elif provider == "openai":
        # 调用 OpenAI /v1/models API
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.models.list()
            models = [m.id for m in response.data]
            return {"models": models}
        except Exception as e:
            logger.error("failed_to_fetch_models", error=str(e))
            # 返回默认列表
            return {
                "models": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
            }

    elif provider == "dashscope":
        # DashScope 模型列表
        return {
            "models": ["qwen-max", "qwen-plus", "qwen-turbo"]
        }

    return {"models": []}
```

#### 2.2 前端实现

**文件**: `apps/desktop/src/views/SettingsView.tsx`

1. **添加状态管理**：

```tsx
const [models, setModels] = useState<string[]>([]);
const [loadingModels, setLoadingModels] = useState(false);
const [provider, setProvider] = useState("anthropic");
const [apiKey, setApiKey] = useState("");
const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
```

2. **添加获取模型函数**：

```tsx
const fetchModels = async () => {
  setLoadingModels(true);
  try {
    const params = new URLSearchParams({
      provider,
      ...(apiKey && { api_key: apiKey }),
      ...(baseUrl && { base_url: baseUrl }),
    });

    const response = await fetch(`${serverUrl}/api/models?${params}`);
    const data = await response.json();
    setModels(data.models || []);
  } catch (error) {
    console.error("Failed to fetch models:", error);
    // 使用默认列表
    setModels(getDefaultModels(provider));
  } finally {
    setLoadingModels(false);
  }
};
```

3. **触发时机**：

```tsx
// 当 Provider/API Key/Base URL 改变时自动获取
useEffect(() => {
  if (apiKey) {
    fetchModels();
  }
}, [provider, apiKey, baseUrl]);
```

4. **UI 更新**：

```tsx
<FormField label="Model">
  <div className="relative">
    <select className="setting-input" disabled={loadingModels}>
      {loadingModels ? (
        <option>Loading models...</option>
      ) : (
        models.map((model) => (
          <option key={model} value={model}>{model}</option>
        ))
      )}
    </select>
    {loadingModels && (
      <div className="absolute right-10 top-1/2 -translate-y-1/2">
        <LoadingSpinner size="sm" />
      </div>
    )}
  </div>
  <button
    onClick={fetchModels}
    className="mt-2 text-xs text-accent hover:text-accent-hover"
  >
    Refresh models
  </button>
</FormField>
```

---

### 方案 3: 完整配置流程优化 (低优先级)

#### 3.1 引导式配置向导

首次启动时显示配置向导：

```
Step 1: 选择 Provider
  [ ] Anthropic (Claude)
  [ ] OpenAI Compatible
  [ ] DashScope (Qwen)

Step 2: 输入凭证
  API Key: [________]
  Base URL (可选): [________]

  [Test Connection]

Step 3: 选择模型
  Model: [下拉列表，动态获取]

  [Save & Start]
```

#### 3.2 快速配置模板

提供常见配置的快速模板：

```tsx
<FormField label="Quick Setup">
  <div className="space-y-2">
    <button onClick={() => applyTemplate("openai-official")}>
      OpenAI Official API
    </button>
    <button onClick={() => applyTemplate("ollama-local")}>
      Ollama (Local)
    </button>
    <button onClick={() => applyTemplate("azure-openai")}>
      Azure OpenAI
    </button>
  </div>
</FormField>
```

**模板内容**：

```typescript
const templates = {
  "openai-official": {
    provider: "openai",
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o",
  },
  "ollama-local": {
    provider: "openai",
    base_url: "http://localhost:11434/v1",
    model: "llama2",
  },
  "azure-openai": {
    provider: "openai",
    base_url: "https://<your-resource-name>.openai.azure.com/",
    model: "gpt-4",
  },
};
```

---

## 📋 实施优先级

| 优先级 | 功能 | 理由 | 工作量 |
|--------|------|------|--------|
| **P0** | 添加 Base URL 输入框 | 解锁自定义 API 使用场景 | 1-2 小时 |
| **P1** | 动态获取模型列表 | 提升用户体验，自动发现新模型 | 3-4 小时 |
| **P2** | 引导式配置向导 | 首次使用体验优化 | 4-6 小时 |
| **P2** | 快速配置模板 | 降低配置门槛 | 2-3 小时 |

---

## 🛠 技术实现细节

### Base URL 验证

前端验证：

```typescript
const validateBaseUrl = (url: string): boolean => {
  try {
    new URL(url);
    return url.startsWith("http://") || url.startsWith("https://");
  } catch {
    return false;
  }
};
```

### 模型列表缓存

避免频繁请求：

```typescript
// 使用 React Query 或本地缓存
const { data: models, isLoading, refetch } = useQuery({
  queryKey: ["models", provider, apiKey, baseUrl],
  queryFn: fetchModels,
  staleTime: 5 * 60 * 1000, // 5 分钟缓存
  enabled: !!apiKey, // 只在有 API Key 时获取
});
```

### 错误处理

```tsx
{error && (
  <div className="text-xs text-error mt-1">
    Failed to fetch models: {error.message}
    <button onClick={refetch} className="ml-2 underline">
      Retry
    </button>
  </div>
)}
```

---

## ✅ 验收标准

### Base URL 功能

- [ ] UI 中显示 Base URL 输入框
- [ ] 支持 HTTP/HTTPS URL 验证
- [ ] 保存后端点可用
- [ ] 配置持久化到后端
- [ ] 支持 Ollama 等本地模型

### 动态模型列表

- [ ] 切换 Provider 时自动更新模型列表
- [ ] 输入 API Key 后自动获取模型
- [ ] 显示加载状态
- [ ] 错误时显示默认列表
- [ ] 支持手动刷新
- [ ] 模型列表缓存 5 分钟

---

## 🎯 用例测试

### 用例 1: 使用官方 OpenAI API

1. Provider: "OpenAI Compatible"
2. Base URL: "https://api.openai.com/v1" (默认)
3. API Key: "sk-xxxx"
4. 点击输入框 → 自动获取模型列表
5. 选择 "gpt-4o"
6. Save

**预期**: 配置成功，可以正常对话

### 用例 2: 使用本地 Ollama

1. Provider: "OpenAI Compatible"
2. Base URL: "http://localhost:11434/v1"
3. API Key: (留空，Ollama 不需要)
4. 点击输入框 → 自动获取本地模型列表
5. 选择 "llama2"
6. Save

**预期**: 配置成功，可以与本地模型对话

### 用例 3: 使用第三方兼容 API

1. Provider: "OpenAI Compatible"
2. Base URL: "https://api.deepseek.com/v1"
3. API Key: "sk-xxxx"
4. 获取模型列表
5. 选择 "deepseek-chat"
6. Save

**预期**: 配置成功，可以使用第三方 API

---

## 📚 参考资料

- OpenAI API Models List: `GET https://api.openai.com/v1/models`
- Ollama API: `http://localhost:11434/api/tags`
- Azure OpenAI: `https://<resource>.openai.azure.com/openai/deployments?api-version=2023-05-15`

---

**文档版本**: v1.0
**创建日期**: 2026-02-21
**状态**: 待实施
**预计工作量**: 6-10 小时
