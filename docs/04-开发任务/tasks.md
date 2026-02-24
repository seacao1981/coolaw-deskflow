# Coolaw DeskFlow - MVP 开发任务规划

> **版本**: v1.0
> **日期**: 2026-02-21
> **状态**: 待确认
> **作者**: Planner Agent
> **范围**: Phase 1 MVP (P0 功能)
> **总工期**: 28 个工作日

---

## 任务总览

```
Phase 1 MVP 开发路线图 (28 天)

Week 1 (Day 1-5):   基础设施 + 核心引擎
Week 2 (Day 6-10):  记忆系统 + 工具系统 + API 层
Week 3 (Day 11-15): 桌面应用 + CLI
Week 4 (Day 16-20): 集成联调 + 测试
Buffer (Day 21-28): 修复 + 优化 + 文档
```

---

## Sprint 1: 基础设施 + 核心引擎 (Day 1-5)

### TASK-001: 项目初始化与基础设施搭建
- **优先级**: P0
- **工时**: 1 天
- **负责**: Coder
- **依赖**: 无

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 001-1 | 初始化 Python 项目 (pyproject.toml, ruff, mypy) | `pyproject.toml`, `ruff.toml`, `mypy.ini` | `ruff check .` 和 `mypy .` 通过 |
| 001-2 | 创建项目目录结构 (src/deskflow/ 所有子目录) | `src/deskflow/**/__init__.py` | 所有模块可导入 |
| 001-3 | 配置管理 (Pydantic Settings, .env 支持) | `src/deskflow/config.py` | 支持 base/dev/prod 配置加载 |
| 001-4 | 异常体系 (细粒度异常层次) | `src/deskflow/errors/exceptions.py` | 所有异常类定义完整 |
| 001-5 | 日志系统 (structlog 初始化) | `src/deskflow/observability/logging.py` | JSON 结构化日志输出正常 |
| 001-6 | .gitignore + .env.example | `.gitignore`, `.env.example` | 敏感文件不被追踪 |
| 001-7 | Git 仓库初始化 + 首次提交 | - | 仓库初始化完成 |

---

### TASK-002: 核心协议定义 (Protocol Interfaces)
- **优先级**: P0
- **工时**: 0.5 天
- **负责**: Coder
- **依赖**: TASK-001

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 002-1 | BrainProtocol (LLM 客户端接口) | `src/deskflow/core/protocols.py` | 定义 chat/stream/embed 方法签名 |
| 002-2 | MemoryProtocol (记忆系统接口) | 同上 | 定义 store/retrieve/search 方法签名 |
| 002-3 | ToolRegistryProtocol (工具注册接口) | 同上 | 定义 register/get/execute 方法签名 |
| 002-4 | IdentityProtocol (人格系统接口) | 同上 | 定义 get_system_prompt/get_persona 方法签名 |
| 002-5 | 基础数据模型 (Message, ToolCall, ToolResult) | `src/deskflow/core/models.py` | Pydantic v2 模型，序列化/反序列化测试通过 |

---

### TASK-003: LLM 抽象层
- **优先级**: P0
- **工时**: 1.5 天
- **负责**: Coder
- **依赖**: TASK-002

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 003-1 | LLM 适配器基类 | `src/deskflow/llm/adapter.py` | 定义抽象方法: chat, stream, count_tokens |
| 003-2 | Anthropic Claude 适配器 | `src/deskflow/llm/providers/anthropic.py` | 支持 chat + stream + tool_use |
| 003-3 | OpenAI Compatible 适配器 | `src/deskflow/llm/providers/openai_compat.py` | 支持 chat + stream + function_calling |
| 003-4 | DashScope 适配器 | `src/deskflow/llm/providers/dashscope.py` | 支持 Qwen 系列模型 |
| 003-5 | 统一 LLM 客户端 (故障转移 + 重试) | `src/deskflow/llm/client.py` | 主模型失败自动切换到 fallback |
| 003-6 | 能力检测 (模型支持的功能) | `src/deskflow/llm/capabilities.py` | 返回模型支持的 tool_use/vision/embed 能力 |
| 003-7 | 单元测试 | `tests/unit/test_llm/` | 覆盖率 >= 90%, mock 外部 API |

---

### TASK-004: Prompt 组装器
- **优先级**: P0
- **工时**: 1 天
- **负责**: Coder
- **依赖**: TASK-002, TASK-003

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 004-1 | Prompt 组装器核心 | `src/deskflow/core/prompt_assembler.py` | 动态组装 system prompt + 上下文 |
| 004-2 | Token 预算管理器 | 同上 | 限制 prompt 在模型上下文窗口内 |
| 004-3 | 上下文注入: 人格定义 | 同上 | 从 Identity 加载 SOUL/AGENT/USER |
| 004-4 | 上下文注入: 记忆摘要 | 同上 | 将相关记忆注入 prompt |
| 004-5 | 上下文注入: 工具定义 | 同上 | 将可用工具列表注入 prompt |
| 004-6 | 单元测试 | `tests/unit/test_core/test_prompt_assembler.py` | Token 预算控制正确, 各注入源测试 |

---

### TASK-005: Agent 主控制器 + Ralph Loop
- **优先级**: P0
- **工时**: 1 天
- **负责**: Coder
- **依赖**: TASK-002, TASK-003, TASK-004

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 005-1 | Agent 主控制器 | `src/deskflow/core/agent.py` | 接收消息 -> 组装 prompt -> 调用 LLM -> 执行工具 -> 返回响应 |
| 005-2 | Ralph Loop (自动重试循环) | `src/deskflow/core/ralph.py` | 支持 max_retries 配置, 支持手动中断 |
| 005-3 | 任务监控器 | `src/deskflow/core/task_monitor.py` | 记录任务状态、耗时、Token 消耗 |
| 005-4 | Agent 依赖注入容器 | `src/deskflow/core/container.py` | 根据配置自动装配所有组件 |
| 005-5 | 集成测试 (Agent 端到端) | `tests/integration/test_agent_flow.py` | mock LLM, 验证完整对话循环 |

---

## Sprint 2: 记忆系统 + 工具系统 + API (Day 6-10)

### TASK-006: 记忆存储层 (SQLite)
- **优先级**: P0
- **工时**: 1.5 天
- **负责**: Coder
- **依赖**: TASK-001

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 006-1 | 数据库 Schema 设计 (DDL) | `src/deskflow/memory/storage.py` | conversations, messages, memories, insights 表 |
| 006-2 | 异步 SQLite 操作 (aiosqlite) | 同上 | CRUD 操作全部异步 |
| 006-3 | FTS5 全文搜索配置 | 同上 | 支持中英文全文检索 |
| 006-4 | 数据迁移工具 | `src/deskflow/memory/migrations.py` | 支持 schema 版本升级 |
| 006-5 | 单元测试 | `tests/unit/test_memory/test_storage.py` | CRUD + FTS5 检索测试通过 |

---

### TASK-007: 记忆检索器 (多路召回 + 缓存)
- **优先级**: P0
- **工时**: 1.5 天
- **负责**: Coder
- **依赖**: TASK-006

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 007-1 | LRU 内存缓存 (L1) | `src/deskflow/memory/cache.py` | 缓存命中响应 < 1ms |
| 007-2 | FTS5 全文检索 (L3) | `src/deskflow/memory/retriever.py` | 关键词匹配检索正常 |
| 007-3 | 语义检索 (嵌入向量 + 余弦相似度) | 同上 | 语义相关性检索正常 |
| 007-4 | 多路召回合并排序 | 同上 | 综合排序，去重，Top-K 返回 |
| 007-5 | 时间衰减因子 | 同上 | 近期记忆权重更高 |
| 007-6 | 记忆管理器 (统一入口) | `src/deskflow/memory/manager.py` | 封装 store + retrieve + lifecycle |
| 007-7 | 单元测试 | `tests/unit/test_memory/test_retriever.py` | 缓存/FTS5/语义检索分别测试 |

---

### TASK-008: 工具系统 (注册 + 执行)
- **优先级**: P0
- **工时**: 1 天
- **负责**: Coder
- **依赖**: TASK-002

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 008-1 | 工具基类 (BaseTool) | `src/deskflow/tools/base.py` | 定义 name/description/parameters/execute |
| 008-2 | 工具注册表 (ToolRegistry) | `src/deskflow/tools/registry.py` | 支持注册/获取/列表/按名查找 |
| 008-3 | 并行工具执行器 | `src/deskflow/tools/executor.py` | 无依赖工具自动并行 (asyncio.gather) |
| 008-4 | 工具结果格式化 | `src/deskflow/tools/base.py` | ToolResult 标准格式 (success/error/output) |
| 008-5 | 单元测试 | `tests/unit/test_tools/test_registry.py` | 注册 + 获取 + 并行执行测试 |

---

### TASK-009: 内置工具实现
- **优先级**: P0
- **工时**: 1.5 天
- **负责**: Coder
- **依赖**: TASK-008

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 009-1 | Shell 工具 (命令执行 + 超时 + 输出捕获) | `src/deskflow/tools/builtin/shell.py` | 支持超时、工作目录、环境变量 |
| 009-2 | File 工具 (读/写/列目录/搜索) | `src/deskflow/tools/builtin/file.py` | 支持文本读写、目录遍历、Glob 搜索 |
| 009-3 | Web 工具 (HTTP 请求 + 网页抓取) | `src/deskflow/tools/builtin/web.py` | 支持 GET/POST, HTML 提取正文 |
| 009-4 | 安全限制 (路径白名单、命令黑名单) | 各工具内部 | Shell 禁止 rm -rf /, File 限制访问范围 |
| 009-5 | 单元测试 | `tests/unit/test_tools/test_builtin/` | 每个工具正常路径 + 异常路径测试 |

---

### TASK-010: API 层 (FastAPI + WebSocket)
- **优先级**: P0
- **工时**: 1.5 天
- **负责**: Coder
- **依赖**: TASK-005

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 010-1 | FastAPI 应用工厂 | `src/deskflow/app.py` | 中间件 + 路由 + 生命周期管理 |
| 010-2 | Chat API (POST /api/chat) | `src/deskflow/api/routes/chat.py` | 接收消息, 返回 AI 响应 |
| 010-3 | WebSocket 流式输出 (WS /api/chat/stream) | 同上 | 逐 Token 推送, 支持中断 |
| 010-4 | Config API (GET/PUT /api/config) | `src/deskflow/api/routes/config.py` | 读取/更新配置 |
| 010-5 | Health API (GET /api/health) | `src/deskflow/api/routes/health.py` | 返回各组件健康状态 |
| 010-6 | API 数据模型 (Request/Response Schemas) | `src/deskflow/api/schemas/` | Pydantic 模型, 自动 OpenAPI 文档 |
| 010-7 | 速率限制中间件 | `src/deskflow/api/middleware/rate_limit.py` | 限制请求频率 |
| 010-8 | 集成测试 (API 端到端) | `tests/integration/test_api.py` | httpx.AsyncClient 测试所有端点 |

---

## Sprint 3: 桌面应用 + CLI (Day 11-15)

### TASK-011: Tauri 项目初始化
- **优先级**: P0
- **工时**: 0.5 天
- **负责**: Coder
- **依赖**: 无 (可并行)

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 011-1 | Tauri 2.x + React + Vite 项目初始化 | `apps/desktop/` | `npm run tauri dev` 启动正常 |
| 011-2 | Tailwind CSS + shadcn/ui 配置 | `apps/desktop/tailwind.config.ts` | 设计系统色彩 token 可用 |
| 011-3 | Fira Code + Fira Sans 字体配置 | `apps/desktop/src/styles/` | 字体正确加载渲染 |
| 011-4 | Lucide React 图标安装 | `apps/desktop/package.json` | 图标正常显示 |
| 011-5 | 设计系统 CSS 变量 | `apps/desktop/src/styles/design-tokens.css` | 所有 MASTER.md 变量可用 |

---

### TASK-012: App Shell (布局框架)
- **优先级**: P0
- **工时**: 1 天
- **负责**: Coder
- **依赖**: TASK-011

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 012-1 | Title Bar (Tauri 拖拽区域 + 窗口控制) | `apps/desktop/src/components/layout/TitleBar.tsx` | 可拖拽移动窗口, 按钮可用 |
| 012-2 | Sidebar (导航 + 收缩/展开) | `apps/desktop/src/components/layout/Sidebar.tsx` | 4 个导航项, 收起 56px 展开 240px |
| 012-3 | Status Bar (底部状态栏) | `apps/desktop/src/components/layout/StatusBar.tsx` | 显示连接状态、模型、记忆数 |
| 012-4 | View Router (视图切换) | `apps/desktop/src/App.tsx` | Chat/Skills/Monitor/Settings 切换 |
| 012-5 | Zustand 全局状态 (导航/连接/主题) | `apps/desktop/src/stores/appStore.ts` | 状态管理正确 |
| 012-6 | Tauri 命令: 窗口管理 | `apps/desktop/src-tauri/src/commands.rs` | minimize/maximize/close |

---

### TASK-013: Chat View (核心对话界面)
- **优先级**: P0
- **工时**: 2 天
- **负责**: Coder
- **依赖**: TASK-012, TASK-010

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 013-1 | Chat Header (Agent 信息 + 操作按钮) | `apps/desktop/src/components/chat/ChatHeader.tsx` | Agent 名称、状态指示灯、新建/历史按钮 |
| 013-2 | Message List (消息列表 + 自动滚动) | `apps/desktop/src/components/chat/MessageList.tsx` | AI/User 消息正确渲染, 自动滚动到底部 |
| 013-3 | AI Message Bubble (Markdown + 代码高亮) | `apps/desktop/src/components/chat/AiMessage.tsx` | Markdown 渲染, 代码块语法高亮 + 复制 |
| 013-4 | User Message Bubble | `apps/desktop/src/components/chat/UserMessage.tsx` | 用户消息显示, 代码块支持 |
| 013-5 | Tool Execution Card (折叠/展开) | `apps/desktop/src/components/chat/ToolCard.tsx` | 显示工具名称、状态、耗时, 可展开详情 |
| 013-6 | Streaming Display (流式文字 + 光标) | `apps/desktop/src/components/chat/StreamingText.tsx` | 逐字渲染, 绿色闪烁光标 |
| 013-7 | Chat Input (输入框 + 发送 + 停止) | `apps/desktop/src/components/chat/ChatInput.tsx` | Enter 发送, Shift+Enter 换行, 自适应高度 |
| 013-8 | WebSocket 连接管理 | `apps/desktop/src/hooks/useChat.ts` | 连接/断线重连/发送/接收 |
| 013-9 | Chat Store (Zustand) | `apps/desktop/src/stores/chatStore.ts` | 消息列表、发送状态、流式状态 |

---

### TASK-014: Settings View (配置界面)
- **优先级**: P0
- **工时**: 1 天
- **负责**: Coder
- **依赖**: TASK-012, TASK-010

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 014-1 | Settings 侧边导航 (LLM/Channels/Identity/System) | `apps/desktop/src/views/SettingsView.tsx` | 导航切换正常 |
| 014-2 | LLM 配置表单 | `apps/desktop/src/components/setup/LlmSettings.tsx` | Provider/API Key/Model/Temperature |
| 014-3 | API Key 安全输入 (遮罩 + Show toggle) | 同上 | 默认遮罩, 点击显示/隐藏 |
| 014-4 | Test Connection 按钮 | 同上 | 调用后端 API 验证, Toast 反馈 |
| 014-5 | Save 按钮 + Toast 通知 | 同上 | 保存成功/失败 Toast |
| 014-6 | Settings API 对接 | `apps/desktop/src/hooks/useSettings.ts` | GET/PUT 配置 |

---

### TASK-015: Monitor View (状态监控)
- **优先级**: P0
- **工时**: 0.5 天
- **负责**: Coder
- **依赖**: TASK-012

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 015-1 | Status Cards (Agent/Memory/LLM/Tools) | `apps/desktop/src/views/MonitorView.tsx` | 4 张状态卡片, 实时数据 |
| 015-2 | Activity Timeline | `apps/desktop/src/components/monitor/ActivityTimeline.tsx` | 时间线列表, 类型筛选 |
| 015-3 | Resource Bars (CPU/Memory/Disk/Token) | `apps/desktop/src/components/monitor/ResourceMonitor.tsx` | 进度条 + 数值显示 |

---

### TASK-016: CLI 交互
- **优先级**: P0
- **工时**: 1.5 天
- **负责**: Coder
- **依赖**: TASK-005, TASK-010

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 016-1 | CLI 框架 (Typer + Rich) | `src/deskflow/__main__.py` | `python -m deskflow --help` 正常 |
| 016-2 | `deskflow init` (引导式初始化) | `src/deskflow/cli/init.py` | 交互式配置, 验证 API Key |
| 016-3 | `deskflow chat` (交互式对话) | `src/deskflow/cli/chat.py` | Rich Markdown 渲染, 流式输出 |
| 016-4 | `deskflow serve` (启动 API 服务) | `src/deskflow/cli/serve.py` | 启动 FastAPI, 支持后台/守护进程 |
| 016-5 | `deskflow status` (查看状态) | `src/deskflow/cli/status.py` | 显示 Agent/Memory/LLM 状态 |
| 016-6 | `deskflow config` (配置管理) | `src/deskflow/cli/config.py` | get/set/list 配置项 |

---

## Sprint 4: 集成联调 + 测试 (Day 16-20)

### TASK-017: 前后端联调
- **优先级**: P0
- **工时**: 2 天
- **负责**: Coder
- **依赖**: TASK-010, TASK-013, TASK-014, TASK-015

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 017-1 | Chat 流式对话端到端 | - | Desktop App 发送消息, 流式收到 AI 响应 |
| 017-2 | 工具调用展示端到端 | - | 工具执行结果在 Tool Card 正确显示 |
| 017-3 | Settings 配置端到端 | - | 修改 LLM 配置后立即生效 |
| 017-4 | Monitor 数据端到端 | - | 实时状态更新到 Monitor 页面 |
| 017-5 | CLI chat 端到端 | - | CLI 对话流式输出 + Markdown 渲染 |
| 017-6 | 错误场景处理 | - | LLM 超时/断线/配置错误均有合理提示 |

---

### TASK-018: 单元测试补充
- **优先级**: P0
- **工时**: 1.5 天
- **负责**: Tester
- **依赖**: TASK-001 ~ TASK-016

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 018-1 | Core 模块测试 (Agent, Ralph, Prompt) | `tests/unit/test_core/` | 覆盖率 >= 90% |
| 018-2 | Memory 模块测试 (Storage, Retriever, Cache) | `tests/unit/test_memory/` | 覆盖率 >= 90% |
| 018-3 | Tools 模块测试 (Registry, Executor, Builtin) | `tests/unit/test_tools/` | 覆盖率 >= 85% |
| 018-4 | LLM 模块测试 (Client, Adapters) | `tests/unit/test_llm/` | 覆盖率 >= 85% |
| 018-5 | API 模块测试 (Routes, Schemas) | `tests/unit/test_api/` | 覆盖率 >= 85% |
| 018-6 | Config 模块测试 | `tests/unit/test_config.py` | 覆盖率 >= 90% |

---

### TASK-019: 集成测试
- **优先级**: P0
- **工时**: 1 天
- **负责**: Tester
- **依赖**: TASK-017

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 019-1 | Agent 完整对话流程测试 | `tests/integration/test_agent_flow.py` | 消息 -> LLM -> 工具 -> 记忆 -> 响应 |
| 019-2 | Memory 存储+检索 round-trip | `tests/integration/test_memory_flow.py` | 存储后检索到正确内容 |
| 019-3 | 工具执行安全边界测试 | `tests/integration/test_tool_safety.py` | 危险命令被拦截 |
| 019-4 | API 端到端测试 | `tests/integration/test_api_e2e.py` | HTTP + WebSocket 全流程 |
| 019-5 | 故障转移测试 (LLM failover) | `tests/integration/test_llm_failover.py` | 主模型失败切换到备用 |

---

### TASK-020: 安全审查
- **优先级**: P0
- **工时**: 0.5 天
- **负责**: Security Reviewer
- **依赖**: TASK-017

**子任务**:

| ID | 描述 | 验收标准 |
|----|------|---------|
| 020-1 | 无硬编码密钥扫描 | `grep -rn "sk-" --include="*.py" src/` 返回空 |
| 020-2 | 无 console.log/print 残留 | 仅 structlog 输出 |
| 020-3 | 输入验证审查 | 所有用户输入经过 Pydantic 验证 |
| 020-4 | Shell 工具安全审查 | 命令注入防护到位 |
| 020-5 | 文件工具路径审查 | 路径遍历攻击防护到位 |

---

## Buffer: 修复 + 优化 + 文档 (Day 21-28)

### TASK-021: Bug 修复 + 性能优化
- **优先级**: P0
- **工时**: 3 天
- **负责**: Coder
- **依赖**: TASK-017 ~ TASK-020

**子任务**:

| ID | 描述 | 验收标准 |
|----|------|---------|
| 021-1 | 修复集成测试暴露的 Bug | 所有测试通过 |
| 021-2 | 修复安全审查发现的问题 | 安全检查清单全部通过 |
| 021-3 | 首字响应性能优化 | Chat 首字响应 < 500ms (不含 LLM 延迟) |
| 021-4 | 记忆检索性能优化 | 缓存命中 < 10ms, 未命中 < 200ms |
| 021-5 | 桌面应用启动优化 | 冷启动 < 3s |

---

### TASK-022: 文档编写
- **优先级**: P1
- **工时**: 2 天
- **负责**: Doc Writer
- **依赖**: TASK-021

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 022-1 | README.md (快速开始) | `README.md` | 安装 + 配置 + 运行步骤清晰 |
| 022-2 | API 文档 (自动生成 + 补充) | OpenAPI /docs | 所有端点有描述和示例 |
| 022-3 | 开发者指南 (架构 + 贡献指南) | `docs/development.md` | 架构图 + 模块说明 + 本地开发步骤 |
| 022-4 | 配置参考手册 | `docs/configuration.md` | 所有配置项说明 + 默认值 |

---

### TASK-023: 验证循环 (6 阶段)
- **优先级**: P0
- **工时**: 1 天
- **负责**: Verifier
- **依赖**: TASK-021

**子任务**:

| ID | 描述 | 验收标准 |
|----|------|---------|
| 023-1 | Phase 1: Build Verification | `npm run build` + Python 构建通过 |
| 023-2 | Phase 2: Type Check | `mypy .` 严格模式通过, `npx tsc --noEmit` 通过 |
| 023-3 | Phase 3: Lint Check | `ruff check .` 通过, `npm run lint` 通过 |
| 023-4 | Phase 4: Test Suite | 覆盖率 >= 80% |
| 023-5 | Phase 5: Security Scan | 无硬编码密钥, 无 console.log |
| 023-6 | Phase 6: Diff Review | 无意外变更 |

---

### TASK-024: Obsidian 知识沉淀
- **优先级**: P1
- **工时**: 1 天
- **负责**: Obsidian Keeper
- **依赖**: TASK-023

**子任务**:

| ID | 描述 | 文件 | 验收标准 |
|----|------|------|---------|
| 024-1 | 开发日志 (Phase 1 总结) | `07-开发日志/2026-02-21.md` | 记录开发过程、问题、决策 |
| 024-2 | 架构决策记录 (ADR) | 知识库 | 记录关键技术选型理由 |
| 024-3 | 问题记录 (踩坑总结) | 知识库 | 记录开发中遇到的问题和解决方案 |

---

## 任务依赖图

```
TASK-001 (基础设施)
  |
  +---> TASK-002 (协议定义) ---> TASK-004 (Prompt 组装) --+
  |       |                                                |
  |       +---> TASK-003 (LLM 抽象层) ----+               |
  |       |                                |               |
  |       +---> TASK-008 (工具注册) ---+   |               |
  |                                    |   |               |
  |                                    v   v               v
  |                              TASK-005 (Agent 主控制器)
  |                                    |
  +---> TASK-006 (记忆存储) ---+       |
  |                            |       |
  |                            v       |
  |                      TASK-007 (记忆检索)
  |                                    |
  +---> TASK-008 ---> TASK-009 (内置工具)
  |                                    |
  +---> TASK-011 (Tauri 初始化)        |
         |                             v
         v                      TASK-010 (API 层)
   TASK-012 (App Shell)               |
         |                             |
         v                             |
   +-----+--------+--------+          |
   |     |        |        |          |
   v     v        v        v          v
 T-013 T-014   T-015   T-016 (CLI)
 (Chat) (Setup) (Monitor)             |
   |     |        |        |          |
   +-----+--------+--------+----------+
                   |
                   v
             TASK-017 (联调)
                   |
         +---------+---------+
         |         |         |
         v         v         v
      T-018     T-019     T-020
     (单测)    (集成测试) (安全审查)
         |         |         |
         +---------+---------+
                   |
                   v
             TASK-021 (修复/优化)
                   |
         +---------+---------+
         |                   |
         v                   v
      T-022              T-023
     (文档)            (验证循环)
                         |
                         v
                   TASK-024 (知识沉淀)
```

---

## 统计汇总

| 指标 | 数值 |
|------|------|
| **总任务数** | 24 |
| **总子任务数** | 约 120 |
| **预计工期** | 28 个工作日 |
| **核心文件数** | 约 80 个 Python 文件 + 30 个 TSX 文件 |
| **测试覆盖率目标** | >= 80% 整体, >= 90% 核心模块 |
| **开发顺序** | 后端优先 (Week 1-2) -> 前端 (Week 3) -> 联调 (Week 4) |

---

## 执行注意事项

1. **后端优先**: Week 1-2 集中实现后端核心逻辑，Week 3 开发前端，Week 4 联调
2. **接口先行**: TASK-002 定义的 Protocol 接口是所有模块的基础，必须最先完成
3. **测试驱动**: 每个任务完成时同步编写单元测试，不要留到最后
4. **安全意识**: API Key 使用环境变量，Shell 工具严格限制，文件工具路径验证
5. **设计系统**: 前端开发前必须读取 `design-system/coolaw-deskflow/MASTER.md`
6. **小步提交**: 每个子任务完成后提交一次，commit message 遵循 conventional commits

---

**文档编制**: Planner Agent
**审阅状态**: 待用户确认
**下一步**: 用户确认通过后进入阶段 4（正式开发）
