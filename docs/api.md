# API Reference

DeskFlow exposes a REST + WebSocket API via FastAPI. When the server is running,
interactive documentation is available at `http://127.0.0.1:8420/docs`.

## Base URL

```
http://127.0.0.1:8420
```

---

## Endpoints

### POST /api/chat

Send a message to the agent and receive a complete response.

**Request Body**

```json
{
  "message": "Hello, DeskFlow!",
  "conversation_id": null,
  "stream": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | User message (1-100,000 chars) |
| `conversation_id` | string | No | Resume an existing conversation |
| `stream` | boolean | No | Reserved for future use |

**Response** `200 OK`

```json
{
  "message": "Hello! How can I help you today?",
  "conversation_id": "conv-abc123",
  "tool_calls": [],
  "metadata": {
    "usage": { "input_tokens": 50, "output_tokens": 20 }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Agent response text |
| `conversation_id` | string | Conversation identifier |
| `tool_calls` | array | List of tool calls made during response |
| `metadata` | object | Token usage and provider info |

---

### WebSocket /api/chat/stream

Stream chat responses in real time over WebSocket.

**Client sends:**

```json
{ "message": "List my files", "conversation_id": null }
```

**Server sends (one per line):**

```json
{ "type": "text", "content": "Let me " }
{ "type": "text", "content": "check..." }
{ "type": "tool_start", "tool_call": { "id": "tc-1", "name": "shell" } }
{ "type": "tool_end", "tool_call": { "id": "tc-1", "name": "shell", "arguments": { "command": "ls" } } }
{ "type": "tool_result", "tool_result": { "tool_call_id": "tc-1", "success": true, "output": "file1.py" } }
{ "type": "text", "content": "Here are your files..." }
{ "type": "done" }
```

**Chunk types:**

| Type | Description |
|------|-------------|
| `text` | Partial text content |
| `tool_start` | Tool execution started |
| `tool_end` | Tool execution finished |
| `tool_result` | Tool output |
| `error` | Error occurred |
| `done` | Response complete |

---

### GET /api/health

Health check endpoint returning component status.

**Response** `200 OK`

```json
{
  "status": "ok",
  "version": "0.1.0",
  "components": {
    "agent": { "status": "ok", "details": {} },
    "memory": { "status": "ok", "details": { "count": 42 } },
    "tools": { "status": "ok", "details": { "count": 3 } },
    "llm": { "status": "ok", "details": { "provider": "Anthropic", "model": "claude-3-haiku" } }
  }
}
```

Status values: `ok`, `degraded`, `error`.

---

### GET /api/status

Detailed agent status with runtime metrics.

**Response** `200 OK`

```json
{
  "is_online": true,
  "is_busy": false,
  "current_task": null,
  "uptime_seconds": 3600.0,
  "total_conversations": 15,
  "total_tool_calls": 42,
  "total_tokens_used": 150000,
  "memory_count": 100,
  "active_tools": 3,
  "available_tools": 3,
  "llm_provider": "Anthropic",
  "llm_model": "claude-3-5-sonnet-20241022"
}
```

---

### GET /api/config

Current configuration (sensitive values redacted).

**Response** `200 OK`

```json
{
  "llm_provider": "anthropic",
  "llm_model": "claude-3-5-sonnet-20241022",
  "llm_temperature": 0.7,
  "llm_max_tokens": 4096,
  "has_api_key": true,
  "server_host": "127.0.0.1",
  "server_port": 8420,
  "memory_cache_size": 1000,
  "tool_timeout": 30.0
}
```

---

## Rate Limiting

The API enforces a sliding-window rate limit per client IP address.

- Default: **60 requests per minute**
- Health check (`/api/health`) and docs endpoints are exempt
- When exceeded, returns `429 Too Many Requests`:

```json
{
  "error": "Rate limit exceeded",
  "code": "RATE_LIMITED",
  "details": { "limit": 60, "window": "1 minute" }
}
```

---

## Error Responses

All errors follow a consistent format:

```json
{
  "error": "Description of the error",
  "code": "ERROR_CODE",
  "details": {}
}
```

Common error codes:

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Invalid request body |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
