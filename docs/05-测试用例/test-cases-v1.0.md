# Test Cases v1.0 - Coolaw DeskFlow

**Version**: 1.0
**Date**: 2026-02-21
**Total Tests**: 287
**Coverage**: 83.21%

---

## Test Strategy

### Coverage Targets

| Module | Target | Actual | Status |
|--------|--------|--------|--------|
| Overall | >= 80% | 83.21% | PASS |
| Core (agent, identity, ralph, models) | >= 90% | 92% | PASS |
| Memory (storage, cache, retriever, manager) | >= 90% | 95% | PASS |
| Tools (registry, shell, file, web) | >= 80% | 88% | PASS |
| API (routes, middleware, schemas) | >= 70% | 82% | PASS |
| CLI (init, chat, serve, status, config) | >= 60% | 68% | PASS |
| LLM (adapters, client, providers) | >= 50% | 62% | PASS |

### Test Types

| Type | Count | Purpose |
|------|-------|---------|
| Unit Tests | 248 | Individual function/class behavior |
| Integration Tests | 39 | Cross-component interaction |

---

## Test Scenarios by Module

### 1. Core Models (test_models.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| M-001 | Message creation with all roles | P0 | PASS |
| M-002 | ToolCall serialization | P0 | PASS |
| M-003 | ToolResult success/error | P0 | PASS |
| M-004 | Conversation model with messages | P0 | PASS |
| M-005 | MemoryEntry with metadata | P1 | PASS |
| M-006 | StreamChunk types (text, tool, done, error) | P0 | PASS |
| M-007 | AgentStatus default values | P1 | PASS |
| M-008 | ToolDefinition to_dict | P1 | PASS |

### 2. Agent (test_agent.py)

| ID    | Scenario                                          | Priority | Status |
| ----- | ------------------------------------------------- | -------- | ------ |
| A-001 | Simple chat returns assistant message             | P0       | PASS   |
| A-002 | Chat stores interaction to memory                 | P0       | PASS   |
| A-003 | Chat with tool calls executes tools               | P0       | PASS   |
| A-004 | Cancellation during tool loop                     | P1       | PASS   |
| A-005 | Conversation persistence across turns             | P0       | PASS   |
| A-006 | Stream chat basic flow                            | P0       | PASS   |
| A-007 | Tool call failure handled gracefully              | P0       | PASS   |
| A-008 | Monitor tracking (conversations, tokens)          | P1       | PASS   |
| A-009 | Memory store failure does not crash               | P1       | PASS   |
| A-010 | New conversation created per chat                 | P1       | PASS   |
| A-011 | Max tool rounds limit (10) prevents infinite loop | P0       | PASS   |

### 3. Prompt Assembler (test_prompt_assembler.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| PA-001 | Basic assembly (system + user) | P0 | PASS |
| PA-002 | System prompt contains identity | P0 | PASS |
| PA-003 | Memory context injected into prompt | P0 | PASS |
| PA-004 | Tools listed in system prompt | P1 | PASS |
| PA-005 | Conversation history included | P0 | PASS |
| PA-006 | Token budget trimming | P1 | PASS |
| PA-007 | Memory retrieval failure graceful | P1 | PASS |
| PA-008 | Token estimation (~4 chars/token) | P2 | PASS |

### 4. Memory System

#### Storage (test_storage.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| MS-001 | Initialize creates schema + FTS5 | P0 | PASS |
| MS-002 | Store and retrieve by ID | P0 | PASS |
| MS-003 | FTS5 full-text search | P0 | PASS |
| MS-004 | Delete entry | P1 | PASS |
| MS-005 | Count entries | P1 | PASS |
| MS-006 | Update access count on retrieval | P1 | PASS |
| MS-007 | Empty query returns recent entries | P2 | PASS |

#### Cache (test_cache.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| MC-001 | Get/set operations | P0 | PASS |
| MC-002 | LRU eviction when capacity exceeded | P0 | PASS |
| MC-003 | Cache hit/miss tracking | P1 | PASS |
| MC-004 | Invalidate specific key | P1 | PASS |
| MC-005 | Clear all entries | P1 | PASS |
| MC-006 | Hit rate calculation | P2 | PASS |

#### Retriever (test_manager.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| MR-001 | Store and retrieve round-trip | P0 | PASS |
| MR-002 | Ranking by importance | P1 | PASS |
| MR-003 | Time decay reduces old entry scores | P1 | PASS |

### 5. Tool System

#### Registry (test_registry.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| TR-001 | Register and retrieve tool | P0 | PASS |
| TR-002 | Duplicate registration raises | P1 | PASS |
| TR-003 | Get nonexistent tool raises | P0 | PASS |
| TR-004 | Execute tool with arguments | P0 | PASS |
| TR-005 | Execute with timeout | P1 | PASS |
| TR-006 | Execute failure handled | P0 | PASS |
| TR-007 | List all tools | P1 | PASS |
| TR-008 | Unregister tool | P1 | PASS |

#### Shell Tool (test_shell_file.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| TS-001 | Execute safe command (echo) | P0 | PASS |
| TS-002 | Block dangerous commands (rm -rf /) | P0 | PASS |
| TS-003 | Output size limits | P1 | PASS |

#### File Tool (test_shell_file.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| TF-001 | Read file within allowed paths | P0 | PASS |
| TF-002 | Write file within allowed paths | P0 | PASS |
| TF-003 | Block path traversal (/etc/passwd) | P0 | PASS |
| TF-004 | List directory contents | P1 | PASS |

### 6. LLM System

#### Client (test_client.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| LC-001 | Basic chat through primary adapter | P0 | PASS |
| LC-002 | Failover to fallback adapter | P0 | PASS |
| LC-003 | All providers fail raises error | P0 | PASS |
| LC-004 | Count tokens | P1 | PASS |
| LC-005 | Health check all providers | P1 | PASS |

#### Providers (test_providers.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| LP-001 | Anthropic message conversion | P0 | PASS |
| LP-002 | Anthropic tool call parsing | P0 | PASS |
| LP-003 | Anthropic rate limit error | P0 | PASS |
| LP-004 | Anthropic connection error | P0 | PASS |
| LP-005 | OpenAI message conversion | P0 | PASS |
| LP-006 | OpenAI tool call parsing | P0 | PASS |
| LP-007 | OpenAI rate limit error | P0 | PASS |
| LP-008 | OpenAI connection error | P0 | PASS |

### 7. API (test_api_endpoints.py)

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| API-001 | GET /api/health returns 200 | P0 | PASS |
| API-002 | Health with memory error shows degraded | P1 | PASS |
| API-003 | GET /api/status returns metrics | P0 | PASS |
| API-004 | GET /api/config returns redacted config | P1 | PASS |
| API-005 | POST /api/chat returns response | P0 | PASS |
| API-006 | Empty message returns 422 | P1 | PASS |

### 8. Integration Tests

| ID | Scenario | Priority | Status |
|----|----------|----------|--------|
| INT-001 | Agent with real memory + tools (mocked LLM) | P0 | PASS |
| INT-002 | Multi-turn conversation persistence | P0 | PASS |
| INT-003 | Tool use flow end-to-end | P0 | PASS |
| INT-004 | Memory round-trip (store, retrieve, FTS) | P0 | PASS |
| INT-005 | Shell dangerous commands blocked | P0 | PASS |
| INT-006 | File path traversal blocked | P0 | PASS |
| INT-007 | Safe shell commands execute | P1 | PASS |
| INT-008 | File operations within allowed paths | P1 | PASS |

---

## Coverage Report Summary

```
TOTAL                                          2001    336    83%
Required test coverage of 80.0% reached. Total coverage: 83.21%
287 passed, 0 failed
```

### Modules at 100% Coverage

- core/models.py
- core/prompt_assembler.py
- core/ralph.py
- core/task_monitor.py
- errors/exceptions.py
- memory/cache.py
- memory/manager.py
- api/schemas/models.py
- observability/logging.py
- cli/init.py
- cli/serve.py

### Known Gaps

| Module | Coverage | Reason |
|--------|----------|--------|
| cli/chat.py | 15% | Interactive REPL requires real LLM; tested via _run_chat mock |
| llm/providers/anthropic.py | 59% | Streaming requires real API; chat/convert fully tested |
| llm/providers/openai_compat.py | 55% | Streaming requires real API; chat/convert fully tested |
| api/routes/chat.py | 38% | WebSocket streaming requires real connection |

---

## Tags

#testing #coverage #deskflow #v1.0
