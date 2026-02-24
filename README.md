# Coolaw DeskFlow

一个自演化的 AI Agent 桌面框架。DeskFlow 提供一个智能助手，通过记忆、工具使用和自适应身份不断提升能力 - 所有功能都在你的本地桌面上运行。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Tests](https://img.shields.io/badge/tests-287%20tests-83%2525%20coverage-green.svg)

## 功能特性

- **多 LLM 支持** - Anthropic Claude、OpenAI（及兼容 API）、DashScope 通义千问，支持自动故障转移
- **持久化记忆** - SQLite + FTS5 全文搜索，配备 LRU 缓存和时间衰减排序
- **可扩展工具** - Shell、文件和网络工具，具备安全沙箱和超时保护
- **桌面应用** - Tauri 2 + React 前端，支持明暗主题和多语言（中文/英文）
- **REST + WebSocket API** - FastAPI 服务器，支持实时流式聊天
- **CLI 命令行** - 功能完整的 Typer CLI，支持终端优先的工作流程
- **自演化能力** - Ralph Loop 指数退避重试机制
- **任务监控** - 对话追踪、工具调用记录和 Token 使用统计

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 20+（桌面应用需要）
- Rust（Tauri 桌面构建需要）

### 安装

```bash
# 克隆仓库
git clone https://github.com/coolaw/coolaw-deskflow.git
cd coolaw-deskflow

# 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate

# 以开发模式安装 Python 包
pip install -e ".[dev]"

# 运行初始化向导
deskflow init
```

### 配置

`deskflow init` 命令会创建包含你的设置的 `.env` 文件。你也可以手动配置：

```bash
# 必需：LLM 提供商和 API 密钥
DESKFLOW_LLM_PROVIDER=anthropic
DESKFLOW_ANTHROPIC_API_KEY=sk-ant-...

# 或使用 DashScope（阿里通义千问）
DESKFLOW_LLM_PROVIDER=dashscope
DESKFLOW_DASHSCOPE_API_KEY=sk-...
DESKFLOW_DASHSCOPE_MODEL=qwen3.5-plus

# 可选：服务器设置
DESKFLOW_HOST=127.0.0.1
DESKFLOW_PORT=8420

# 可选：记忆和工具设置
DESKFLOW_DB_PATH=data/db/deskflow.db
DESKFLOW_MEMORY_CACHE_SIZE=1000
DESKFLOW_TOOL_TIMEOUT=30
DESKFLOW_TOOL_MAX_PARALLEL=3
DESKFLOW_ALLOWED_PATHS=~/Projects,~/Documents
```

完整配置参考 [docs/configuration.md](docs/configuration.md)

### 使用方法

#### 方式 1：使用 CLI（推荐）

```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动 API 服务器
deskflow serve

# 启动交互式聊天会话
deskflow chat

# 检查系统状态
deskflow status

# 查看配置
deskflow config show
deskflow config list
```

#### 方式 2：直接运行（CLI 不可用时）

```bash
# 使用虚拟环境 Python 直接启动
.venv/bin/python -m deskflow serve

# 或使用完整路径
/path/to/coolaw-deskflow/.venv/bin/python -m deskflow serve
```

### 桌面应用

桌面应用需要安装 Rust 才能使用 Tauri。

```bash
cd apps/desktop

# 安装依赖
npm install

# 开发模式（同时运行 Vite 开发服务器和 Tauri）
npm run dev

# 构建生产版桌面应用
npm run build

# 纯 Web 开发（不含 Tauri 封装）
npm run dev:web
```

**注意**：桌面应用集成 Python 后端 API，地址为 `http://127.0.0.1:8420`。启动桌面应用前，请确保后端服务器正在运行。

### 主题和语言设置

桌面应用支持主题切换和语言选择：

- **主题**：在设置页面点击主题切换按钮，可在明亮和黑暗模式间切换
- **语言**：在设置页面的语言下拉框中选择首选语言（中文/English）

主题和语言偏好会本地保存，并在应用重启后恢复。

## 架构

```
coolaw-deskflow/
├── src/deskflow/           # Python backend
│   ├── core/               # Agent, brain, identity, task monitor
│   ├── llm/                # Multi-provider LLM adapters
│   ├── memory/             # SQLite + FTS5 + LRU cache
│   ├── tools/              # Tool registry + built-in tools
│   ├── api/                # FastAPI routes + middleware
│   ├── cli/                # Typer CLI commands
│   └── app.py              # Application factory
├── apps/desktop/           # Tauri + React frontend
│   └── src/
│       ├── components/     # Layout and chat components
│       ├── stores/         # Zustand state management
│       ├── hooks/          # WebSocket chat hook
│       └── views/          # Chat, Skills, Monitor, Settings
├── tests/                  # Test suite (287 tests, 83% coverage)
│   ├── unit/               # Unit tests per module
│   └── integration/        # End-to-end integration tests
└── docs/                   # Documentation
```

### 核心组件

| 组件 | 用途 |
|------|------|
| **Agent** | 中央协调器 - 使用工具循环协调大脑、记忆、工具和身份系统 |
| **Brain (LLM 客户端)** | 多 LLM 提供商，具备自动故障转移和重试机制 |
| **Memory** | 两级存储：L1 LRU 缓存 (~1ms) + L2 FTS5 SQLite 搜索 (~5ms)，智能排序 |
| **Tools** | 注册表模式，内置 Shell、文件和网络工具，具备安全沙箱 |
| **Identity** | 人格系统，从 SOUL.md / AGENT.md / USER.md 文件加载 |
| **Ralph Loop** | "永不放弃" 重试机制，具备指数退避和容错能力 |
| **Task Monitor** | 实时追踪对话、工具调用、Token 使用和运行时间指标 |
| **Protocol 接口** | 通过 Python Protocols 实现依赖注入，提升可测试性和模块化 |

### 核心架构模式

- **依赖注入**：所有组件依赖于 Protocol 接口而非具体类
- **工具使用循环**：Agent 迭代调用工具（最多 10 轮）后再响应
- **多级记忆**：先查询 L1 缓存，再查询 L2 FTS5 搜索，按关键词重叠度、重要性、时间衰减和频率排序
- **LLM 故障转移**：自动回退到备用提供商，使用 tenacity 进行重试
- **安全优先**：工具执行沙箱隔离，包含命令黑名单、路径限制和超时限制

详细架构文档请参阅 [docs/developer-guide.md](docs/developer-guide.md)

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+, FastAPI, aiosqlite, Pydantic v2, structlog |
| 前端 | Tauri 2, React 18, TypeScript, Tailwind CSS, Zustand, i18next |
| LLM | Anthropic Claude, OpenAI 兼容，DashScope 通义千问 |
| 数据库 | SQLite + FTS5 全文搜索，hnswlib 向量索引 |
| CLI | Typer + Rich 终端输出 |
| 测试 | pytest, pytest-asyncio, pytest-cov (83% 覆盖率) |
| 代码质量 | Ruff (linting/formatting), mypy (严格类型检查) |

## 开发

### 运行测试

```bash
# 运行所有测试
pytest

# 带覆盖率运行
pytest --cov=src/deskflow --cov-report=term-missing

# 运行特定测试模块
pytest tests/unit/test_core/test_agent.py

# 仅运行集成测试
pytest tests/integration/
```

### 代码质量

```bash
# Lint 和格式化
ruff check src/
ruff format src/

# 类型检查
mypy src/deskflow/

# TypeScript 检查（桌面应用）
cd apps/desktop && npx tsc --noEmit
```

### API 文档

服务器运行时可访问：
- Swagger UI: http://127.0.0.1:8420/docs
- OpenAPI JSON: http://127.0.0.1:8420/openapi.json

完整 API 参考 [docs/api.md](docs/api.md)

## 文档

- **[API 参考](docs/api.md)** - 完整的 REST + WebSocket API 文档
- **[配置指南](docs/configuration.md)** - 所有环境变量和设置
- **[开发者指南](docs/developer-guide.md)** - 架构、开发流程和贡献指南
- **[身份系统](docs/identity/AGENT.md)** - 人格和身份配置

## License

MIT
