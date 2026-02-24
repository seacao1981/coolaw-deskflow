# Developer Guide

This guide covers the internal architecture, development workflow, and
contribution guidelines for Coolaw DeskFlow.

## Project Structure

```
src/deskflow/
├── __init__.py             # Package version
├── __main__.py             # CLI entry point (Typer)
├── app.py                  # FastAPI app factory + component initialization
├── config.py               # Pydantic Settings configuration
│
├── core/                   # Core engine
│   ├── agent.py            # Central orchestrator (chat + tool loop)
│   ├── identity.py         # Persona system (SOUL.md / AGENT.md / USER.md)
│   ├── models.py           # Pydantic v2 data models
│   ├── prompt_assembler.py # Dynamic system prompt construction
│   ├── protocols.py        # Protocol interfaces (dependency injection)
│   ├── ralph.py            # Retry loop with exponential backoff
│   └── task_monitor.py     # Runtime metrics tracking
│
├── llm/                    # LLM abstraction layer
│   ├── adapter.py          # BaseLLMAdapter abstract class
│   ├── client.py           # LLMClient with failover + create_adapter factory
│   └── providers/
│       ├── anthropic.py    # Anthropic Claude adapter
│       ├── openai_compat.py # OpenAI-compatible adapter
│       └── dashscope.py    # DashScope Qwen adapter
│
├── memory/                 # Persistent memory system
│   ├── storage.py          # SQLite + FTS5 storage backend
│   ├── cache.py            # Thread-safe LRU cache (L1)
│   ├── retriever.py        # Semantic retrieval + time-decay ranking
│   └── manager.py          # Unified memory interface
│
├── tools/                  # Tool execution framework
│   ├── base.py             # BaseTool abstract class
│   ├── registry.py         # ToolRegistry with timeout management
│   └── builtin/
│       ├── shell.py        # Shell command executor (with blocked-list)
│       ├── file.py         # File operations (with path sandboxing)
│       └── web.py          # HTTP requests + HTML text extraction
│
├── api/                    # REST + WebSocket API
│   ├── routes/
│   │   ├── chat.py         # POST /api/chat + WS /api/chat/stream
│   │   ├── health.py       # GET /api/health + /api/status
│   │   └── config.py       # GET /api/config
│   ├── middleware/
│   │   └── rate_limit.py   # Sliding-window IP rate limiter
│   └── schemas/
│       └── models.py       # Request/response Pydantic models
│
├── cli/                    # Command-line interface
│   ├── init.py             # deskflow init (guided wizard)
│   ├── chat.py             # deskflow chat (interactive REPL)
│   ├── serve.py            # deskflow serve (API server)
│   ├── status.py           # deskflow status
│   └── config_cmd.py       # deskflow config show/list
│
├── observability/
│   └── logging.py          # structlog setup (JSON + console)
│
├── errors/
│   └── exceptions.py       # Full exception hierarchy
│
├── channels/               # Future: multi-channel support
├── evolution/              # Future: self-evolution engine
├── orchestration/          # Future: multi-agent coordination
└── skills/                 # Future: skill marketplace
```

## Architecture Principles

### 1. Dependency Injection via Protocol

All core components depend on Protocol interfaces, not concrete classes:

```python
# core/protocols.py defines the contracts
class BrainProtocol(Protocol):
    async def chat(self, messages, tools, ...) -> Message: ...

class MemoryProtocol(Protocol):
    async def store(self, entry) -> str: ...
    async def retrieve(self, query, limit) -> list[MemoryEntry]: ...
```

The Agent constructor accepts any object satisfying these Protocols:

```python
agent = Agent(
    brain=llm_client,       # Satisfies BrainProtocol
    memory=memory_manager,  # Satisfies MemoryProtocol
    tools=tool_registry,    # Satisfies ToolRegistryProtocol
    identity=identity,      # Satisfies IdentityProtocol
)
```

### 2. Tool-Use Loop

The Agent implements a tool-use loop (max 10 rounds):

```
User message
    -> Assemble prompt (system + memory + tools + history + user)
    -> Send to LLM
    -> If LLM returns tool_calls:
        -> Execute each tool
        -> Append tool results to conversation
        -> Loop back to LLM
    -> If LLM returns text only:
        -> Return response
        -> Store interaction in memory
```

### 3. Multi-Level Memory

```
Query -> L1 LRU Cache (in-memory, ~1ms)
           |
           miss
           v
         L2 FTS5 Search (SQLite, ~5ms)
           |
         Rank by:
           - Keyword overlap (0.4)
           - Importance score (0.25)
           - Time decay (0.25)
           - Access frequency (0.1)
```

### 4. LLM Failover

```
Primary adapter (e.g., Anthropic)
    |
    fail (with retry via tenacity)
    v
Fallback adapter (e.g., OpenAI)
    |
    fail
    v
LLMAllProvidersFailedError
```

## Development Workflow

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in dev mode
pip install -e ".[dev]"

# Create configuration
deskflow init
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/deskflow --cov-report=term-missing

# Specific module
pytest tests/unit/test_core/test_agent.py -v

# Integration tests only
pytest tests/integration/ -v
```

### Code Quality

```bash
# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/

# Type check
mypy src/deskflow/

# All checks
ruff check src/ && ruff format --check src/ && mypy src/deskflow/
```

### Adding a New Tool

1. Create a new file in `src/deskflow/tools/builtin/`:

```python
from deskflow.core.models import ToolResult
from deskflow.tools.base import BaseTool

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Does something useful"

    @property
    def parameters(self) -> dict:
        return {"input": {"type": "string", "description": "Input text"}}

    @property
    def required_params(self) -> list[str]:
        return ["input"]

    async def execute(self, **kwargs) -> ToolResult:
        input_text = kwargs.get("input", "")
        # Your logic here
        return self._success(f"Processed: {input_text}")
```

2. Register it in `app.py`:

```python
from deskflow.tools.builtin.my_tool import MyTool
await tools.register(MyTool())
```

3. Write tests in `tests/unit/test_tools/test_builtin/test_my_tool.py`.

### Adding a New LLM Provider

1. Create a new adapter in `src/deskflow/llm/providers/`:

```python
from deskflow.llm.adapter import BaseLLMAdapter

class MyProviderAdapter(BaseLLMAdapter):
    @property
    def provider_name(self) -> str:
        return "MyProvider"

    async def chat(self, messages, tools=None, ...) -> Message:
        # Implement chat
        ...

    async def stream(self, messages, tools=None, ...) -> AsyncGenerator:
        # Implement streaming
        ...

    async def count_tokens(self, messages) -> int:
        # Estimate token count
        ...
```

2. Add the provider to `LLMProvider` enum in `config.py`.
3. Add the factory case in `client.py:create_adapter()`.
4. Write tests.

## Testing Strategy

| Layer | Type | Tool |
|-------|------|------|
| Core logic | Unit tests | pytest, AsyncMock |
| LLM adapters | Unit tests with mocked API clients | pytest, MagicMock |
| Memory | Integration tests with real SQLite | pytest-asyncio, temp dirs |
| Tools | Integration tests with real shell/file | pytest, temp dirs |
| API routes | HTTP tests with FastAPI TestClient | TestClient |
| CLI | Command tests with typer CliRunner | CliRunner |

Coverage target: 80% overall, 90% for core modules.

## Error Handling

The project uses a structured exception hierarchy:

```
DeskFlowError
├── LLMError
│   ├── LLMConnectionError
│   ├── LLMRateLimitError
│   ├── LLMContextOverflowError
│   ├── LLMResponseError
│   └── LLMAllProvidersFailedError
├── ToolError
│   ├── ToolNotFoundError
│   ├── ToolExecutionError
│   ├── ToolTimeoutError
│   └── ToolSecurityError
├── MemoryError_
│   ├── MemoryStorageError
│   └── MemoryRetrievalError
├── SkillError
│   ├── SkillNotFoundError
│   └── SkillSandboxError
└── ConfigError
```

All errors carry a machine-readable `code` field for programmatic handling.
