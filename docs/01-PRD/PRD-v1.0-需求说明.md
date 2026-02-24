# PRD v1.0 - Coolaw DeskFlow 产品需求说明书

> **版本**: v1.0
> **日期**: 2026-02-21
> **状态**: 待确认
> **作者**: Planner Agent
> **参考**: source/architecture-analysis.md (OpenAkita 架构分析报告)

---

## 1. 产品概述

### 1.1 产品定位

**Coolaw DeskFlow** 是一个**自进化 AI Agent 桌面框架**，定位为 OpenAkita 的优化替代方案。产品的核心理念是构建一个能够持续学习、自主进化的智能助手，同时解决 OpenAkita 中已识别的性能瓶颈、耦合问题和扩展性限制。

**一句话描述**: 一个模块化、高性能、可扩展的自进化 AI Agent 框架，提供桌面应用 + CLI + 多平台 IM 全渠道接入。

### 1.2 目标用户

| 用户群体 | 核心需求 | 使用场景 |
|---------|---------|---------|
| **个人开发者** | AI 编程助手、自动化脚本、日常事务管理 | 桌面 App + CLI |
| **技术团队** | 多 Agent 协同、代码审查、知识管理 | CLI + IM 通道 |
| **企业用户** | 多平台客服、工单自动处理、知识库查询 | IM 通道为主 |
| **内容创作者** | 调研写作、文档处理、多媒体辅助 | 桌面 App |

### 1.3 产品价值主张

与 OpenAkita 相比，Coolaw DeskFlow 的差异化优势：

| 维度       | OpenAkita (参考)  | Coolaw DeskFlow (目标)          |
| -------- | --------------- | ----------------------------- |
| **架构**   | 单进程多线程，组件强耦合    | 微内核 + 插件化，依赖注入，进程隔离           |
| **性能**   | 记忆检索无缓存，工具串行执行  | 多级缓存 + HNSW 索引，工具依赖图并行        |
| **安全**   | 技能无沙箱隔离         | 技能沙箱化运行，权限细粒度控制               |
| **类型安全** | mypy 宽松模式       | 严格类型检查，运行时验证                  |
| **错误处理** | 通用 Exception 捕获 | 细粒度异常体系，结构化错误日志               |
| **可测试性** | 缺少 e2e 测试       | 完整测试体系 (unit/integration/e2e) |
| **可观测性** | 无监控告警           | OpenTelemetry + Prometheus 集成 |

---

## 2. 功能需求

### 2.1 核心功能模块

#### P0 - 必须实现（MVP）

##### 2.1.1 核心引擎 (Core Engine)

| 功能                  | 描述                               | 验收标准                                                |
| ------------------- | -------------------------------- | --------------------------------------------------- |
| **Agent 主控制器**      | 协调所有组件的核心控制器                     | 能接收消息、编排流程、返回响应                                     |
| **Brain (LLM 客户端)** | 多模型支持，故障转移                       | 支持 Anthropic Claude / OpenAI Compatible / DashScope |
| **Prompt 组装器**      | 动态组装 System Prompt，支持 Token 预算控制 | Prompt 不超过模型上下文窗口                                   |
| **工具执行器**           | 调用内置/外部工具                        | 支持 Shell/File/Web 基础工具                              |
| **Ralph Loop**      | "永不放弃"循环，任务未完成自动重试               | 支持最大重试次数配置，支持中断                                     |

##### 2.1.2 记忆系统 (Memory)

| 功能 | 描述 | 验收标准 |
|------|------|---------|
| **统一存储** | SQLite 持久化所有记忆数据 | 支持 CRUD，数据不丢失 |
| **多路召回** | 语义检索 + 情节检索 + 时间衰减 | 相关性 Top-K 准确率 > 80% |
| **记忆缓存** | LRU 缓存 + HNSW 近似最近邻索引 | 重复查询响应 < 10ms |
| **每日巩固** | 定时提取洞察，压缩长期记忆 | 自动执行，生成可读摘要 |

##### 2.1.3 桌面应用 (Desktop App)

| 功能 | 描述 | 验收标准 |
|------|------|---------|
| **Chat UI** | 对话界面，支持流式输出 | 首字响应 < 500ms，Markdown 渲染 |
| **Setup Center** | LLM / 通道 / 技能的可视化配置 | 无需编辑配置文件即可完成设置 |
| **Status Monitor** | Agent 状态、任务进度、资源监控 | 实时刷新，延迟 < 1s |

##### 2.1.4 CLI 交互

| 功能 | 描述 | 验收标准 |
|------|------|---------|
| **交互式命令行** | 类似 ChatGPT CLI 的对话体验 | Rich 美化输出，支持 Markdown |
| **服务管理** | 启动/停止/状态查看 | 支持后台运行、守护进程模式 |
| **配置初始化** | `deskflow init` 一键初始化 | 引导式配置，验证 API Key |

#### P1 - 重要功能

##### 2.1.5 技能系统 (Skills)

| 功能 | 描述 | 验收标准 |
|------|------|---------|
| **技能注册表** | 管理内置和用户技能 | 支持 CRUD、版本管理 |
| **技能安装** | 从 GitHub / 本地安装技能 | 支持 `deskflow skill install <url>` |
| **技能沙箱** | 隔离运行技能代码 | 限制文件系统/网络访问，资源配额 |
| **自动生成** | LLM 自动生成技能代码 | 生成代码通过沙箱测试后自动安装 |

##### 2.1.6 人格系统 (Identity)

| 功能 | 描述 | 验收标准 |
|------|------|---------|
| **人格定义** | SOUL.md / AGENT.md / USER.md 三层定义 | 人格可自定义、可切换 |
| **预设人格** | 提供 4-6 种预设人格 | 默认/管家/技术专家/商务 |
| **主动问候** | 基于时间/事件的主动消息 | 支持生物钟感知，不在深夜打扰 |

##### 2.1.7 自进化系统 (Evolution)

| 功能 | 描述 | 验收标准 |
|------|------|---------|
| **每日自检** | 健康检查、性能指标收集 | 自动生成日报，异常告警 |
| **错误分析** | 聚合错误日志，LLM 诊断根因 | 高频错误自动归类 |
| **技能进化** | 根据错误自动生成修复技能 | 生成 -> 测试 -> 安装闭环 |

#### P2 - 扩展功能

##### 2.1.8 IM 通道 (Channels)

| 功能         | 描述                             | 优先级       |
| ---------- | ------------------------------ | --------- |
| **飞书**     | 事件订阅、卡片消息                      | P2-High   |
| **企业微信**   | 智能机器人模式                        | P2-Medium |
| **钉钉**     | Stream 模式                      | P2-Medium |


##### 2.1.9 多 Agent 协同

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **Master/Worker 架构** | 任务分发与结果聚合 | P2-High |
| **ZeroMQ 消息总线** | PUB/SUB + REQ/REP | P2-High |
| **Worker 注册发现** | 动态注册、健康检查 | P2-Medium |
| **负载均衡** | 按能力/负载分配任务 | P2-Low |

##### 2.1.10 MCP 集成

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **MCP 客户端** | 连接 MCP 兼容服务 | P2-High |
| **MCP 服务端** | 将 DeskFlow 暴露为 MCP 服务 | P2-Medium |

---

## 3. 非功能需求

### 3.1 性能要求

| 指标 | 目标值 | 测量方法 |
|------|--------|---------|
| **Chat 首字响应** | < 500ms (不含 LLM 延迟) | 从消息接收到首字输出 |
| **记忆检索 (缓存命中)** | < 10ms | 重复查询 P99 延迟 |
| **记忆检索 (缓存未命中)** | < 200ms (10 万条记忆) | 冷查询 P99 延迟 |
| **工具并行执行** | 默认 3 并发，最大 10 | 无依赖工具并行加速比 |
| **桌面应用启动** | < 3s | 冷启动到可交互 |
| **内存占用 (空闲)** | < 200MB | 无活跃任务时 |
| **内存占用 (峰值)** | < 1GB | 多工具并行时 |

### 3.2 安全要求

| 要求 | 描述 |
|------|------|
| **密钥管理** | 所有 API Key / Token 通过环境变量或加密配置文件管理，不硬编码 |
| **技能沙箱** | 第三方技能在隔离环境运行，限制文件系统/网络/系统调用 |
| **输入验证** | 所有用户输入参数化处理，防止注入攻击 |
| **传输加密** | 所有外部通信使用 HTTPS/TLS |
| **最小权限** | 工具/技能仅获取必要的系统权限 |
| **审计日志** | 所有工具执行、技能安装记录审计日志 |

### 3.3 可扩展性要求

| 要求 | 描述 |
|------|------|
| **插件化架构** | 通道/工具/技能均可独立开发和部署 |
| **依赖注入** | 核心组件通过接口交互，支持替换实现 |
| **配置层级** | base -> dev -> prod 三级配置继承 |
| **多租户预留** | 架构设计考虑未来多用户隔离 |

### 3.4 可观测性要求

| 要求 | 描述 |
|------|------|
| **结构化日志** | JSON 格式日志，支持日志聚合 |
| **Metrics 暴露** | Prometheus 格式的 `/metrics` 端点 |
| **Tracing** | OpenTelemetry 分布式追踪 |
| **健康检查** | `/health` 端点，返回各组件状态 |

### 3.5 兼容性要求

| 平台 | 版本 |
|------|------|
| **macOS** | 12+ (Monterey) |
| **Windows** | 10+ (1903) |
| **Linux** | Ubuntu 20.04+ / Fedora 36+ |
| **Python** | 3.11+ |
| **Node.js** | 18+ (构建工具链) |
| **Rust** | 1.75+ (Tauri 编译) |

---

## 4. 技术架构

### 4.1 架构概览

采用**微内核 + 插件化**架构，解决 OpenAkita 的耦合和扩展性问题：

```
+---------------------------------------------------------------+
|                     Presentation Layer                         |
|  +------------------+  +---------------+  +----------------+  |
|  | Desktop App      |  | CLI           |  | IM Channels    |  |
|  | (Tauri + React)  |  | (Typer + Rich)|  | (Adapters)     |  |
|  +------------------+  +---------------+  +----------------+  |
+---------------------------------------------------------------+
                              |
                              v
+---------------------------------------------------------------+
|                      API Gateway Layer                         |
|  +---------------------------+  +---------------------------+ |
|  | HTTP API (FastAPI)        |  | WebSocket (Stream Output) | |
|  | - RESTful endpoints       |  | - Real-time chat          | |
|  | - Health/Metrics          |  | - Status updates          | |
|  +---------------------------+  +---------------------------+ |
+---------------------------------------------------------------+
                              |
                              v
+---------------------------------------------------------------+
|                      Core Kernel Layer                         |
|  +----------+  +----------+  +----------+  +-------------+   |
|  | Agent    |  | Brain    |  | Memory   |  | Identity    |   |
|  | (控制器) |  | (LLM)   |  | (记忆)   |  | (人格)      |   |
|  +----------+  +----------+  +----------+  +-------------+   |
|  +----------+  +----------+  +----------+  +-------------+   |
|  | Prompt   |  | Ralph    |  | Task     |  | Reasoning   |   |
|  | (组装器) |  | (循环)   |  | (监控)   |  | (推理)      |   |
|  +----------+  +----------+  +----------+  +-------------+   |
+---------------------------------------------------------------+
                              |
                              v
+---------------------------------------------------------------+
|                     Extension Layer                            |
|  +------------------+  +------------------+  +-----------+    |
|  | Tool Registry    |  | Skill Registry   |  | MCP Bus   |   |
|  | (工具注册)       |  | (技能注册)       |  | (协议总线)|   |
|  | - Shell/File/Web |  | - System Skills  |  |           |   |
|  | - Browser        |  | - User Skills    |  |           |   |
|  | - Desktop Ctrl   |  | - Auto-generated |  |           |   |
|  +------------------+  +------------------+  +-----------+    |
+---------------------------------------------------------------+
                              |
                              v
+---------------------------------------------------------------+
|                    Infrastructure Layer                        |
|  +----------+  +----------+  +----------+  +-------------+   |
|  | LLM      |  | Storage  |  | Evolution|  | Observability|  |
|  | Providers|  | (SQLite) |  | Engine   |  | (OTel)       |  |
|  | (多端点) |  | (Vector) |  | (自进化) |  | (Prometheus) |  |
|  +----------+  +----------+  +----------+  +-------------+   |
+---------------------------------------------------------------+
```

### 4.2 对 OpenAkita 问题的针对性优化

#### 4.2.1 解耦 -- 依赖注入容器

```python
# 问题: OpenAkita 中 Agent 直接实例化 ToolCatalog（强耦合）
# 方案: 引入依赖注入容器

from typing import Protocol

class ToolRegistryProtocol(Protocol):
    """工具注册表协议，任何实现此协议的类都可以注入"""
    async def get_tool(self, name: str) -> Tool: ...
    async def execute(self, name: str, args: dict) -> ToolResult: ...

class Agent:
    def __init__(
        self,
        brain: BrainProtocol,
        memory: MemoryProtocol,
        tools: ToolRegistryProtocol,
        identity: IdentityProtocol,
    ):
        self._brain = brain
        self._memory = memory
        self._tools = tools
        self._identity = identity
```

#### 4.2.2 性能 -- 记忆多级缓存

```python
# 问题: 无缓存，大规模记忆检索慢
# 方案: L1 (LRU 内存) -> L2 (HNSW 索引) -> L3 (SQLite FTS5)

class CachedMemoryRetriever:
    def __init__(self):
        self._l1_cache = LRUCache(capacity=1000)      # 热点查询
        self._l2_index = HNSWIndex(dim=768, ef=200)    # 近似最近邻
        self._l3_store = SQLiteFTS5Store()              # 全文检索

    async def retrieve(self, query: str, top_k: int = 5) -> list[Memory]:
        # L1: 内存缓存
        if cached := self._l1_cache.get(query):
            return cached

        # L2: 向量索引（快速近似搜索）
        results = await self._l2_index.search(query, top_k)

        # L3: 全文检索（补充精确匹配）
        fts_results = await self._l3_store.search(query, top_k)

        merged = self._merge_and_rank(results, fts_results, top_k)
        self._l1_cache.put(query, merged)
        return merged
```

#### 4.2.3 安全 -- 技能沙箱

```python
# 问题: 技能在主进程运行，无隔离
# 方案: subprocess + 资源限制

class SandboxedSkillExecutor:
    """技能沙箱执行器"""

    async def execute(
        self,
        skill: BaseSkill,
        args: dict,
        timeout: float = 30.0,
        max_memory_mb: int = 256,
    ) -> SkillResult:
        # 在子进程中运行，限制资源
        result = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "deskflow.sandbox.runner",
            "--skill", skill.name,
            "--args", json.dumps(args),
            "--max-memory", str(max_memory_mb),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # 超时控制
        stdout, stderr = await asyncio.wait_for(
            result.communicate(), timeout=timeout
        )
        return SkillResult.from_subprocess(stdout, stderr, result.returncode)
```

#### 4.2.4 工具并行 -- 依赖图分析

```python
# 问题: 工具默认串行执行
# 方案: 分析工具调用依赖关系，无依赖的自动并行

class ParallelToolExecutor:
    async def execute_all(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        dep_graph = self._analyze_dependencies(tool_calls)
        execution_layers = dep_graph.topological_layers()

        results = []
        for layer in execution_layers:
            # 同一层的工具无依赖，并行执行
            layer_results = await asyncio.gather(
                *[self._execute_single(call) for call in layer]
            )
            results.extend(layer_results)
        return results
```

#### 4.2.5 错误处理 -- 细粒度异常体系

```python
# 问题: 大量 try-except Exception 吞掉具体异常
# 方案: 定义异常层次结构

class DeskFlowError(Exception):
    """基础异常"""
    def __init__(self, message: str, code: str, details: dict = None):
        self.code = code
        self.details = details or {}
        super().__init__(message)

class LLMError(DeskFlowError):
    """LLM 相关错误"""
    pass

class LLMRateLimitError(LLMError):
    """速率限制"""
    pass

class LLMContextOverflowError(LLMError):
    """上下文超长"""
    pass

class ToolExecutionError(DeskFlowError):
    """工具执行错误"""
    pass

class MemoryRetrievalError(DeskFlowError):
    """记忆检索错误"""
    pass

class SkillSandboxError(DeskFlowError):
    """技能沙箱错误"""
    pass
```

### 4.3 技术栈确认

#### 后端 (Python 3.11+)

| 类别 | 选型 | 理由 |
|------|------|------|
| **LLM 客户端** | `anthropic` + `openai` | 官方 SDK，覆盖主流模型 |
| **Web 框架** | `FastAPI` + `uvicorn` | 异步高性能，自动 OpenAPI 文档 |
| **CLI** | `typer` + `rich` | 类型安全 + 美化输出 |
| **数据库** | `aiosqlite` | 嵌入式，零配置 |
| **向量搜索** | `hnswlib` (轻量) / `chromadb` (全功能) | 按需选择 |
| **数据验证** | `pydantic` v2 | 运行时类型检查 |
| **异步 HTTP** | `httpx` | HTTP/2 支持 |
| **重试** | `tenacity` | 可配置重试策略 |
| **日志** | `structlog` | 结构化 JSON 日志 |
| **监控** | `prometheus-client` + `opentelemetry` | 行业标准 |
| **测试** | `pytest` + `pytest-asyncio` + `pytest-cov` | 异步测试 + 覆盖率 |
| **代码检查** | `ruff` | 快速 Linter + Formatter |
| **类型检查** | `mypy` (strict mode) | 严格模式 |

#### 前端 (Desktop App)

| 类别 | 选型 | 理由 |
|------|------|------|
| **框架** | Tauri 2.x | Rust 内核，轻量跨平台 |
| **UI** | React 18 + TypeScript 5 | 生态成熟 |
| **构建** | Vite 5 | 快速 HMR |
| **状态管理** | Zustand | 轻量、类型安全 |
| **UI 组件** | shadcn/ui + Tailwind CSS | 可定制、现代化 |
| **图标** | Lucide React | 开源 SVG 图标库 |
| **i18n** | i18next | 成熟的国际化方案 |
| **图表** | Recharts | React 原生图表库 |

---

## 5. 项目范围与排期

### 5.1 MVP 范围 (Phase 1 -- 4 周)

| 模块 | 功能 | 工时估算 |
|------|------|---------|
| **Core Engine** | Agent + Brain + Prompt + Ralph Loop | 5 天 |
| **Memory** | SQLite 存储 + FTS5 检索 + LRU 缓存 | 4 天 |
| **Tools** | Shell + File + Web 基础工具 | 3 天 |
| **Desktop App** | Chat UI + Setup Center (基础) | 5 天 |
| **CLI** | 交互式命令行 + 服务管理 | 2 天 |
| **API Layer** | FastAPI + WebSocket 流式输出 | 2 天 |
| **Testing** | 单元测试 + 集成测试 (覆盖率 80%) | 3 天 |
| **Buffer** | 联调、修复、文档 | 4 天 |
| **合计** | | **28 天** |

### 5.2 Phase 2 -- 扩展功能 (4 周)

| 模块 | 功能 |
|------|------|
| **Identity** | 人格系统 + 预设人格 + 主动问候 |
| **Skills** | 技能注册 + 安装 + 沙箱 + 自动生成 |
| **Evolution** | 每日自检 + 错误分析 + 技能进化 |
| **Memory 增强** | HNSW 向量索引 + 每日巩固 |
| **Observability** | 结构化日志 + Prometheus Metrics |

### 5.3 Phase 3 -- IM 通道 (4 周)

| 模块 | 功能 |
|------|------|
| **Gateway** | 统一消息网关 + Session 管理 |
| **Telegram** | 长轮询/Webhook |
| **飞书** | 事件订阅 + 卡片消息 |
| **企业微信** | 智能机器人 |
| **钉钉** | Stream 模式 |

### 5.4 Phase 4 -- 多 Agent (4 周)

| 模块 | 功能 |
|------|------|
| **Orchestration** | Master/Worker 架构 |
| **ZMQ Bus** | PUB/SUB + REQ/REP 消息总线 |
| **Registry** | Worker 注册发现 |
| **MCP** | MCP 客户端/服务端 |

---

## 6. 项目目录结构

### 6.1 后端代码 (Python)

```
src/deskflow/
|-- __init__.py
|-- __main__.py              # CLI 入口
|-- app.py                   # FastAPI 应用工厂
|-- config.py                # 配置管理 (Pydantic Settings)
|
|-- core/                    # 核心引擎
|   |-- __init__.py
|   |-- agent.py             # Agent 主控制器
|   |-- brain.py             # LLM 客户端封装
|   |-- identity.py          # 人格系统
|   |-- ralph.py             # Ralph Loop (永不放弃循环)
|   |-- prompt_assembler.py  # Prompt 组装器
|   |-- reasoning.py         # 推理引擎
|   |-- task_monitor.py      # 任务监控
|   `-- protocols.py         # 核心接口协议 (Protocol classes)
|
|-- memory/                  # 记忆系统
|   |-- __init__.py
|   |-- manager.py           # 记忆管理器
|   |-- storage.py           # 统一存储 (SQLite)
|   |-- retriever.py         # 多路召回检索器
|   |-- cache.py             # 多级缓存 (LRU + HNSW)
|   |-- extractor.py         # 洞察提取器
|   |-- consolidator.py      # 每日巩固
|   `-- lifecycle.py         # 记忆生命周期
|
|-- tools/                   # 工具系统
|   |-- __init__.py
|   |-- registry.py          # 工具注册表
|   |-- executor.py          # 并行工具执行器
|   |-- builtin/             # 内置工具
|   |   |-- shell.py
|   |   |-- file.py
|   |   |-- web.py
|   |   `-- browser.py
|   `-- sandbox/             # 沙箱执行器
|       |-- runner.py
|       `-- policy.py
|
|-- skills/                  # 技能系统
|   |-- __init__.py
|   |-- registry.py          # 技能注册表
|   |-- loader.py            # 技能加载器
|   |-- generator.py         # 技能自动生成
|   `-- base.py              # 技能基类
|
|-- llm/                     # LLM 抽象层
|   |-- __init__.py
|   |-- client.py            # 统一 LLM 客户端
|   |-- adapter.py           # 提供商适配器接口
|   |-- providers/           # 各厂商实现
|   |   |-- anthropic.py
|   |   |-- openai_compat.py
|   |   `-- dashscope.py
|   `-- capabilities.py      # 能力检测
|
|-- channels/                # IM 通道 (Phase 3)
|   |-- __init__.py
|   |-- gateway.py           # 统一网关
|   |-- session.py           # 会话管理
|   `-- adapters/            # 通道适配器
|
|-- evolution/               # 自进化系统 (Phase 2)
|   |-- __init__.py
|   |-- self_check.py
|   |-- log_analyzer.py
|   `-- skill_generator.py
|
|-- orchestration/           # 多 Agent 协同 (Phase 4)
|   |-- __init__.py
|   |-- master.py
|   |-- worker.py
|   `-- bus.py
|
|-- api/                     # HTTP API
|   |-- __init__.py
|   |-- routes/
|   |   |-- chat.py          # 对话 API
|   |   |-- config.py        # 配置 API
|   |   |-- health.py        # 健康检查
|   |   `-- metrics.py       # 监控指标
|   |-- middleware/
|   |   |-- auth.py
|   |   `-- rate_limit.py
|   `-- schemas/             # API 数据模型
|
|-- errors/                  # 异常体系
|   |-- __init__.py
|   `-- exceptions.py        # 细粒度异常定义
|
`-- observability/           # 可观测性
    |-- __init__.py
    |-- logging.py           # structlog 配置
    |-- metrics.py           # Prometheus 指标
    `-- tracing.py           # OpenTelemetry 追踪
```

### 6.2 前端代码 (Tauri + React)

```
apps/desktop/
|-- src-tauri/               # Tauri Rust 后端
|   |-- Cargo.toml
|   |-- src/
|   |   |-- main.rs          # Rust 入口
|   |   |-- tray.rs          # 系统托盘
|   |   `-- commands.rs      # Tauri 命令
|   `-- tauri.conf.json
|
`-- src/                     # React 前端
    |-- main.tsx             # 入口
    |-- App.tsx              # 根组件
    |-- components/          # 通用组件
    |   |-- ui/              # shadcn/ui 组件
    |   |-- chat/            # 对话组件
    |   |-- setup/           # 设置组件
    |   `-- monitor/         # 监控组件
    |-- views/               # 页面视图
    |   |-- ChatView.tsx
    |   |-- SetupView.tsx
    |   `-- MonitorView.tsx
    |-- stores/              # Zustand 状态
    |-- hooks/               # 自定义 Hooks
    |-- utils/               # 工具函数
    |-- types/               # TypeScript 类型
    |-- i18n/                # 国际化
    `-- styles/              # 全局样式
```

### 6.3 项目根目录

```
coolaw-deskflow/
|-- CLAUDE.md                # 项目开发规范
|-- README.md                # 项目说明
|-- pyproject.toml           # Python 项目配置
|-- .env.example             # 环境变量示例
|-- .gitignore
|
|-- source/                  # 参考资料
|   |-- architecture-analysis.md
|   `-- screenshots/
|
|-- design-system/           # 设计系统
|   `-- MASTER.md
|
|-- src/                     # 后端源码
|   `-- deskflow/
|
|-- apps/                    # 前端应用
|   `-- desktop/
|
|-- tests/                   # 测试
|   |-- unit/
|   |-- integration/
|   `-- e2e/
|
|-- scripts/                 # 脚本
|   |-- dev.sh
|   `-- build.sh
|
|-- identity/                # 身份定义
|   |-- SOUL.md
|   |-- AGENT.md
|   |-- USER.md
|   |-- MEMORY.md
|   `-- personas/
|
|-- skills/                  # 技能目录
|   |-- system/              # 系统技能
|   `-- user/                # 用户技能
|
`-- data/                    # 运行时数据
    |-- db/                  # SQLite 数据库
    |-- logs/                # 日志文件
    `-- cache/               # 缓存文件
```

---

## 7. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| **Tauri 2.x 跨平台兼容问题** | 桌面端无法正常运行 | 中 | 优先开发 macOS 版本，后续适配 |
| **LLM API 延迟不稳定** | 用户体验差 | 高 | 多端点故障转移 + 流式输出 + 本地缓存 |
| **记忆数据量增长** | 检索性能下降 | 中 | 多级缓存 + 记忆压缩 + 定期清理 |
| **技能安全风险** | 恶意代码执行 | 低 | 沙箱隔离 + 权限白名单 + 代码审查 |
| **多 IM 平台 API 变更** | 通道失效 | 中 | 适配器模式隔离变化 + 监控告警 |

---

## 8. 成功指标

### 8.1 MVP 验收标准

- [ ] 通过桌面 App 能正常对话，流式输出
- [ ] 通过 CLI 能正常对话，支持 Markdown 渲染
- [ ] 支持至少 3 个 LLM 提供商切换
- [ ] 记忆系统正常工作（存储 + 检索 + 缓存）
- [ ] 基础工具 (Shell/File/Web) 可用
- [ ] Ralph Loop 正常运行（任务重试）
- [ ] 测试覆盖率 >= 80%
- [ ] 无安全漏洞（硬编码密钥、注入风险等）

### 8.2 长期目标

| 指标 | 6 个月目标 |
|------|-----------|
| **技能生态** | >= 20 个社区技能 |
| **IM 通道** | >= 4 个平台接入 |
| **记忆容量** | 支持 100 万条记忆高效检索 |
| **自进化成功率** | >= 60% 的错误能自动修复 |
| **多 Agent 任务** | 支持 5+ Worker 并行协同 |

---

## 附录 A: 术语表

| 术语 | 定义 |
|------|------|
| **Ralph Loop** | "永不放弃"机制，任务失败时自动重试并尝试新策略 |
| **Brain** | LLM 客户端抽象，封装模型调用细节 |
| **Skill** | 可安装/卸载的功能扩展单元 |
| **Tool** | 内置的基础操作能力（Shell/File/Web 等） |
| **Identity** | Agent 的人格定义，包含价值观、行为准则、用户偏好 |
| **Persona** | 人格预设，定义 Agent 的语气、风格、互动模式 |
| **MCP** | Model Context Protocol，模型上下文协议 |
| **HNSW** | Hierarchical Navigable Small World，近似最近邻搜索算法 |
| **FTS5** | SQLite 的全文搜索扩展模块 |

---

**文档编制**: Planner Agent
**审阅状态**: 待用户确认
**下一步**: 用户确认通过后进入阶段 2（原型设计）
