# Coolaw DeskFlow - 技术架构文档

**版本**: v1.0
**最后更新**: 2026-02-24
**状态**: 已完成

---

## 📋 目录

1. [架构概览](#架构概览)
2. [核心模块](#核心模块)
3. [数据流](#数据流)
4. [技术决策](#技术决策)
5. [部署架构](#部署架构)

---

## 架构概览

### 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    用户交互层 (Presentation)                  │
├─────────────────────────────────────────────────────────────┤
│  Desktop App (Tauri + React)  │  CLI (Typer + Rich)         │
│  - Chat UI                    │  - 交互式命令行              │
│  - Setup Center               │  - 服务管理模式              │
│  - Status Monitor             │                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    API 网关层 (API Gateway)                   │
├─────────────────────────────────────────────────────────────┤
│  FastAPI (HTTP + WebSocket)                                   │
│  - REST API: /api/chat, /api/health, /api/config            │
│  - WebSocket: /api/chat/stream (流式输出)                    │
│  - 速率限制中间件                                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    核心引擎层 (Core Engine)                   │
├─────────────────────────────────────────────────────────────┤
│  Agent (主控制器)                                            │
│  ├─ Brain (LLM Client)     ├─ Identity (人格系统)          │
│  ├─ Prompt Assembler       ├─ Ralph Loop (永不放弃循环)    │
│  └─ Task Monitor                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    能力扩展层 (Extension)                     │
├─────────────────────────────────────────────────────────────┤
│  Tools Catalog            │  Skills Catalog                 │
│  ├─ Shell/File/Web        │  ├─ System Skills (内置)       │
│  └─ Browser Automation    │  └─ User Skills (可扩展)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    基础设施层 (Infrastructure)                │
├─────────────────────────────────────────────────────────────┤
│  LLM Providers            │  Memory Storage                 │
│  ├─ Anthropic Claude      │  ├─ SQLite (统一存储)          │
│  ├─ OpenAI Compatible     │  ├─ FTS5 (全文检索)            │
│  └─ DashScope (阿里)      │  └─ LRU Cache (L1 缓存)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心模块

### 1. Agent 主控制器

**文件**: `src/deskflow/core/agent.py`

**职责**: 协调所有组件，处理用户消息并返回响应

**核心流程**:
```
用户消息
    ↓
组装 Prompt (系统提示 + 记忆 + 工具 + 历史)
    ↓
调用 LLM
    ↓
解析响应 (文本 或 工具调用)
    ↓
执行工具 (如果有)
    ↓
循环 (最多 10 轮)
    ↓
返回最终响应
```

**关键方法**:
```python
async def chat(self, message: str, conversation_id: Optional[str] = None) -> ChatResponse:
    """处理用户消息并返回响应"""

async def stream(self, message: str, conversation_id: Optional[str] = None) -> AsyncGenerator[StreamChunk, None]:
    """流式输出响应"""
```

### 2. Brain (LLM 客户端)

**文件**: `src/deskflow/llm/client.py`

**职责**: 统一 LLM 调用，支持多提供商故障转移

**支持的提供商**:
| 提供商 | 适配器 | 模型示例 |
|--------|--------|----------|
| Anthropic | `anthropic.py` | claude-3-5-sonnet-20241022 |
| OpenAI 兼容 | `openai_compat.py` | gpt-4o, gpt-3.5-turbo |
| DashScope | `dashscope.py` | qwen-max, qwen-plus |

**故障转移逻辑**:
```
主模型 (Anthropic)
    │ 失败 (重试 3 次)
    ▼
备用模型 1 (OpenAI)
    │ 失败 (重试 3 次)
    ▼
备用模型 2 (DashScope)
    │ 失败
    ▼
抛出 LLMAllProvidersFailedError
```

### 3. Memory 系统

**文件**: `src/deskflow/memory/`

**架构**:
```
┌─────────────────────────────────────┐
│         Memory Manager              │
│  (统一入口：add/store/retrieve)     │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│  L1    │ │  L2    │ │  L3    │
│ Cache  │ │ FTS5   │ │ SQLite │
│ (LRU)  │ │ Search │ │ Store  │
│ ~1ms   │ │ ~5ms   │ │ ~10ms  │
└────────┘ └────────┘ └────────┘
```

**检索策略**:
1. 查询 L1 缓存 (LRU, 1000 条)
2. 未命中 → FTS5 全文搜索
3. 合并结果，按相关性排序
4. 应用时间衰减因子
5. 返回 Top-K 结果

### 4. Tool 系统

**文件**: `src/deskflow/tools/`

**内置工具**:
| 工具 | 功能 | 安全限制 |
|------|------|----------|
| Shell | 执行 Shell 命令 | 命令黑名单、输出大小限制 |
| File | 文件读写、目录操作 | 路径白名单、禁止路径遍历 |
| Web | HTTP 请求、网页抓取 | URL 验证、响应大小限制 |

**工具注册**:
```python
@tools.register
class ShellTool(BaseTool):
    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute a shell command"

    async def execute(self, command: str, timeout: float = 30.0) -> ToolResult:
        # 实现
```

---

## 数据流

### 对话数据流

```
用户输入
    │
    ▼
┌─────────────────┐
│  Desktop App    │
│  (React/Tauri)  │
└────────┬────────┘
         │ WebSocket / HTTP
         ▼
┌─────────────────┐
│   FastAPI       │
│   (API Layer)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Agent        │
│  (Core Engine)  │
└────────┬────────┘
         │
    ┌────┴────┬────────────┐
    │         │            │
    ▼         ▼            ▼
┌──────┐  ┌──────┐    ┌──────┐
│Brain │  │Memory│    │Tools │
└──┬───┘  └──┬───┘    └──┬───┘
   │         │            │
   ▼         ▼            ▼
 LLM API   SQLite      Shell/
           FTS5        File/Web
```

### 记忆存储流程

```
对话完成
    │
    ▼
┌─────────────────┐
│ MemoryManager   │
│ .add_interaction│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Storage Layer  │
│  (SQLite)       │
├─────────────────┤
│ - conversations │
│ - messages      │
│ - memories      │
│ - insights      │
└─────────────────┘
```

---

## 技术决策

### ADR-001: 选择 FastAPI 作为 Web 框架

**上下文**: 需要高性能异步 API 框架

**决策**: 使用 FastAPI

**理由**:
- 异步优先，支持 HTTP/2
- 自动 OpenAPI 文档
- Pydantic 集成，自动验证
- 高性能 (接近 Node.js)

**后果**:
- ✅ API 文档自动生成
- ✅ 类型安全
- ⚠️ 需要异步编程知识

### ADR-002: 使用 SQLite + FTS5 作为记忆存储

**上下文**: 需要持久化存储对话和记忆

**决策**: 使用 SQLite + FTS5 全文搜索

**理由**:
- 零配置，嵌入式
- FTS5 支持中英文全文搜索
- 无需外部数据库服务
- 适合单用户场景

**后果**:
- ✅ 部署简单
- ✅ 性能足够 (百万条记录)
- ⚠️ 多用户并发需要迁移到 PostgreSQL

### ADR-003: Tauri 作为桌面框架

**上下文**: 需要跨平台桌面应用

**决策**: 使用 Tauri 2.x + React

**理由**:
- 轻量 (比 Electron 小 10 倍)
- Rust 后端，安全性高
- 支持系统托盘、原生菜单
- 前端可使用 React 生态

**后果**:
- ✅ Bundle 大小仅 4.7MB
- ✅ 启动时间 < 3 秒
- ⚠️ 需要 Rust 知识
- ⚠️ Windows/Linux 需要额外适配

### ADR-004: Protocol 接口实现依赖注入

**上下文**: 需要提高可测试性和模块解耦

**决策**: 使用 Python Protocol 定义接口

**理由**:
- 结构类型检查 (鸭子类型)
- 易于单元测试 (Mock 实现)
- 支持替换实现

**后果**:
- ✅ 模块解耦
- ✅ 测试容易
- ✅ 代码可维护性提高

---

## 部署架构

### 本地部署 (默认)

```
┌─────────────────────────────────────┐
│         用户计算机                   │
│                                     │
│  ┌─────────────┐  ┌───────────────┐│
│  │ Desktop App │  │ Python Backend││
│  │ (Tauri)     │←→│ (FastAPI)     ││
│  │             │  │               ││
│  │ - React UI  │  │ - Agent       ││
│  │ - Tray Icon │  │ - Memory      ││
│  └─────────────┘  │ - Tools       ││
│                   └───────────────┘│
│                          │         │
│                          ▼         │
│                   ┌───────────────┐│
│                   │ SQLite DB     ││
│                   │ (data/db/)    ││
│                   └───────────────┘│
└─────────────────────────────────────┘
```

### 远程部署 (可选)

```
┌─────────────────────────────────────────────────┐
│                  云服务器                        │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │           Python Backend                 │   │
│  │           (FastAPI + Uvicorn)            │   │
│  │                                          │   │
│  │  - Agent (多实例，负载均衡)              │   │
│  │  - Memory (PostgreSQL + Redis)           │   │
│  │  - Tools (分布式执行)                    │   │
│  └─────────────────────────────────────────┘   │
│                      │                          │
│                      ▼                          │
│              ┌─────────────────┐               │
│              │ PostgreSQL      │               │
│              │ + Redis Cache   │               │
│              └─────────────────┘               │
└─────────────────────────────────────────────────┘
           ▲
           │ HTTPS
           │
    ┌──────┴──────┐
    │ Desktop App │
    │   (本地)    │
    └─────────────┘
```

---

## 性能优化

### 已实施优化

| 优化点 | 方法 | 效果 |
|--------|------|------|
| 记忆检索 | L1 LRU 缓存 | 重复查询 < 1ms |
| 工具执行 | 并行执行 (无依赖) | 加速 2-3 倍 |
| Prompt 组装 | Token 预算控制 | 避免上下文溢出 |
| 流式输出 | WebSocket 逐 Token 推送 | 首字 < 500ms |

### 待实施优化

| 优化点 | 计划 | 预期效果 |
|--------|------|----------|
| 向量索引 | HNSW 近似最近邻 | 10 万条记忆 < 100ms |
| 连接池 | 数据库连接池 | 并发能力提升 |
| 响应压缩 | gzip 压缩 | 网络传输减少 70% |

---

## 安全设计

### 密钥管理

- API Key 存储在 `.env` 文件
- `.env` 加入 `.gitignore`
- `/api/config` 接口红API Key

### 工具安全

**Shell 工具**:
- 命令黑名单：`rm -rf /`, `mkfs`, `dd`, `shutdown` 等
- 输出大小限制：1MB
- 超时限制：30 秒

**File 工具**:
- 路径白名单：`DESKFLOW_ALLOWED_PATHS`
- 禁止路径遍历：`/etc/passwd` 等系统文件

### 输入验证

- 所有用户输入通过 Pydantic 验证
- 防止 SQL 注入 (参数化查询)
- 防止 XSS (输出转义)

---

**编制**: Architect Agent
**审阅**: 待技术负责人确认
**许可**: MIT License
