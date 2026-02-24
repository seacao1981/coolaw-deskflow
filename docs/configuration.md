# Configuration Reference

DeskFlow is configured via environment variables or a `.env` file. Run
`deskflow init` for guided setup.

## Environment Variables

### LLM Provider

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DESKFLOW_LLM_PROVIDER` | string | `anthropic` | LLM provider: `anthropic`, `openai`, `dashscope` |
| `DESKFLOW_LLM_MAX_TOKENS` | int | `4096` | Maximum response tokens (1-200,000) |
| `DESKFLOW_LLM_TEMPERATURE` | float | `0.7` | Sampling temperature (0.0-2.0) |

### Anthropic

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DESKFLOW_ANTHROPIC_API_KEY` | string | - | Anthropic API key (required when provider=anthropic) |
| `DESKFLOW_ANTHROPIC_MODEL` | string | `claude-3-5-sonnet-20241022` | Model identifier |

### OpenAI Compatible

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DESKFLOW_OPENAI_API_KEY` | string | - | OpenAI API key (required when provider=openai) |
| `DESKFLOW_OPENAI_BASE_URL` | string | `https://api.openai.com/v1` | API base URL |
| `DESKFLOW_OPENAI_MODEL` | string | `gpt-4o` | Model identifier |

### DashScope (Alibaba Qwen)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DESKFLOW_DASHSCOPE_API_KEY` | string | - | DashScope API key (required when provider=dashscope) |
| `DESKFLOW_DASHSCOPE_MODEL` | string | `qwen-max` | Model identifier |

### Server

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DESKFLOW_HOST` | string | `127.0.0.1` | Server bind host |
| `DESKFLOW_PORT` | int | `8420` | Server bind port (1024-65535) |
| `DESKFLOW_LOG_LEVEL` | string | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |

### Memory

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DESKFLOW_DB_PATH` | string | `data/db/deskflow.db` | SQLite database path (relative to project root) |
| `DESKFLOW_MEMORY_CACHE_SIZE` | int | `1000` | L1 LRU cache capacity (10-100,000) |

### Tools

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DESKFLOW_TOOL_TIMEOUT` | float | `30.0` | Tool execution timeout in seconds (1-300) |
| `DESKFLOW_TOOL_MAX_PARALLEL` | int | `3` | Maximum parallel tool executions (1-10) |
| `DESKFLOW_ALLOWED_PATHS` | string | `~/Projects,~/Documents` | Comma-separated allowed file paths |

### Application

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DESKFLOW_ENV` | string | `dev` | Environment: `dev`, `prod`, `test` |

## .env File

Create a `.env` file in the project root (or use `deskflow init`):

```bash
# LLM Configuration
DESKFLOW_LLM_PROVIDER=anthropic
DESKFLOW_LLM_MAX_TOKENS=4096
DESKFLOW_LLM_TEMPERATURE=0.7

# Anthropic
DESKFLOW_ANTHROPIC_API_KEY=sk-ant-api03-...
DESKFLOW_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Server
DESKFLOW_HOST=127.0.0.1
DESKFLOW_PORT=8420
DESKFLOW_LOG_LEVEL=INFO

# Memory
DESKFLOW_DB_PATH=data/db/deskflow.db
DESKFLOW_MEMORY_CACHE_SIZE=1000

# Tools
DESKFLOW_TOOL_TIMEOUT=30
DESKFLOW_TOOL_MAX_PARALLEL=3
DESKFLOW_ALLOWED_PATHS=~/Projects,~/Documents
```

## Configuration Precedence

1. Environment variables (highest priority)
2. `.env` file
3. Default values (lowest priority)

## Security Notes

- API keys are stored only in `.env` (which is in `.gitignore`)
- The `/api/config` endpoint redacts sensitive values
- `deskflow config list` masks API keys in terminal output
- File tool operations are restricted to `DESKFLOW_ALLOWED_PATHS`
- Shell tool blocks dangerous commands (`rm -rf /`, `shutdown`, etc.)
