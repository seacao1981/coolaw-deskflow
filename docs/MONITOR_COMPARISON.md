# OpenAkita vs Coolaw DeskFlow - 状态/监控模块功能对比分析报告

**日期**: 2026-02-24
**分析对象**:
- OpenAkita (`/Users/seacao/Devlop/openakita`)
- Coolaw DeskFlow (`/Users/seacao/Projects/personal/coolaw-deskflow`)

---

## 📋 执行摘要

### 核心差异概览

| 维度 | OpenAkita | Coolaw DeskFlow | 差异说明 |
|------|-----------|-----------------|----------|
| **监控定位** | 企业级多 Agent 协同监控 | 单用户桌面应用监控 | 架构目标不同 |
| **TaskMonitor** | 基础任务跟踪 | 高级任务复盘 + 模型切换 | DeskFlow 更复杂 |
| **健康检查** | 基础健康检查 + LLM 端点检测 | 组件级详细健康检查 | DeskFlow 更详细 |
| **Token 统计** | 多维度统计分析 (按端点/会话/时间线) | 基础 Token 追踪 | OpenAkita 更完善 |
| **系统监控** | 无独立系统监控 | 完整系统资源监控 (CPU/内存/磁盘) | DeskFlow 独有 |
| **实时推送** | 无 WebSocket 推送 | WebSocket 活动实时推送 | DeskFlow 独有 |
| **Prometheus** | 无 | 完整 Prometheus 指标导出 | DeskFlow 独有 |
| **活动日志** | 基础日志 | 结构化活动日志 + 查询 API | DeskFlow 更完善 |
| **多 Agent 监控** | Master/Worker 协同监控 | 不支持 | OpenAkita 独有 |
| **IM 通道监控** | 7 大 IM 平台状态 | 不支持 | OpenAkita 独有 |

---

## 1️⃣ TaskMonitor 模块对比

### OpenAkita TaskMonitor

**文件**: `src/openakita/core/task_monitor.py`

**核心功能**:
```python
class TaskMonitor:
    """任务执行监控器"""

    # 监控内容
    - 任务执行时间跟踪
    - 迭代次数记录
    - 工具调用记录
    - 超时检测
    - 模型切换决策
```

**关键特性**:
| 特性 | 说明 |
|------|------|
| 超时检测 | 无进展超时判断 (`progress_idle_seconds > timeout_seconds`) |
| 模型切换 | 超时后自动切换到备用模型 |
| 重试机制 | LLM 错误重试计数 + 超时重试计数 (双计数器独立) |
| 上下文重置 | 模型切换时可选择重置上下文 |
| 复盘功能 | 任务完成后生成复盘报告 (`get_retrospect_context()`) |

**数据结构**:
```python
@dataclass
class TaskMetrics:
    task_id: str
    description: str
    start_time: float
    end_time: float
    total_iterations: int
    iterations: list[IterationRecord]  # 迭代详情
    initial_model: str
    final_model: str
    model_switched: bool
    success: bool
    error: str | None
```

**局限性**:
- ❌ 无 Token 统计
- ❌ 无系统资源监控
- ❌ 无实时推送能力
- ❌ 无 Prometheus 集成

---

### Coolaw DeskFlow TaskMonitor

**文件**: `src/deskflow/core/task_monitor.py`

**核心功能**:
```python
class TaskMonitor:
    """任务监控器 - 跟踪 Agent 活动、性能和状态"""

    # 监控内容
    - 对话计数统计
    - 工具调用执行记录
    - Token 使用统计
    - Agent 忙/闲状态
    - 活动日志 (最多 1000 条)
```

**关键特性**:
| 特性 | 说明 |
|------|------|
| 状态聚合 | `get_status()` 返回完整 AgentStatus |
| 活动日志 | 环形缓冲区存储最近活动 |
| 工具调用追踪 | 记录工具名称、耗时、成功率 |
| Token 追踪 | 记录输入/输出 Token 数 |

**数据结构**:
```python
@dataclass
class AgentStatus:
    is_online: bool
    is_busy: bool
    current_task: str | None
    uptime_seconds: float
    total_conversations: int
    total_tool_calls: int
    total_tokens_used: int
    memory_count: int
    active_tools: int
    available_tools: int
    llm_provider: str
    llm_model: str
```

**局限性**:
- ❌ 无任务复盘功能
- ❌ 无模型切换决策
- ❌ 无迭代详情记录

---

### TaskMonitor 差异总结

| 功能 | OpenAkita | DeskFlow | 优势方 |
|------|-----------|----------|--------|
| 任务复盘 | ✅ | ❌ | OpenAkita |
| 模型切换 | ✅ | ❌ | OpenAkita |
| 双重试计数器 | ✅ | ❌ | OpenAkita |
| 迭代详情记录 | ✅ | ❌ | OpenAkita |
| 活动日志 | ❌ | ✅ | DeskFlow |
| Token 统计 | ❌ | ✅ | DeskFlow |
| Agent 状态聚合 | ❌ | ✅ | DeskFlow |

**结论**: OpenAkita 的 TaskMonitor 更专注于**任务执行过程的深度监控**，DeskFlow 的 TaskMonitor 更专注于**Agent 运行时状态的广度监控**。

---

## 2️⃣ 健康检查 API 对比

### OpenAkita Health API

**文件**: `src/openakita/api/routes/health.py`

**端点**:
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 基础健康检查 |
| `/api/health/check` | POST | LLM 端点健康检测 (dry_run 模式) |

**响应示例**:
```json
{
  "status": "ok",
  "service": "openakita",
  "version": "0.2.0",
  "git_hash": "abc123",
  "agent_initialized": true
}
```

**LLM 端点检测特性**:
- ✅ dry_run 模式 (不修改 Provider 状态)
- ✅ 并发检测所有端点
- ✅ 超时控制 (30 秒)
- ✅ 冷静期状态展示

---

### Coolaw DeskFlow Health API

**文件**: `src/deskflow/api/routes/health.py`

**端点**:
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 组件级健康检查 |
| `/api/health/detailed` | GET | 综合健康报告 + 建议 |
| `/api/status` | GET | Agent 详细状态 |

**响应示例**:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "components": {
    "agent": {"status": "ok"},
    "memory": {
      "status": "ok",
      "details": {"count": 42, "database_size_mb": 1.2}
    },
    "tools": {
      "status": "ok",
      "details": {"total_count": 3, "responsive": 3}
    },
    "llm": {
      "status": "ok",
      "details": {"provider": "Anthropic", "model": "claude-3-5-sonnet"}
    }
  }
}
```

**组件检测特性**:
| 组件 | 检测内容 |
|------|----------|
| Memory | 记忆数量、数据库大小、缓存命中率 |
| Tools | 工具总数、响应性测试 (ping test) |
| LLM | Provider、Model、API Key 配置、连通性测试 |
| System | CPU、内存、磁盘使用率 |
| Process | 进程 CPU、内存、文件句柄、线程数、运行时间 |

---

### 健康检查差异总结

| 功能 | OpenAkita | DeskFlow | 优势方 |
|------|-----------|----------|--------|
| 基础健康检查 | ✅ | ✅ | 平手 |
| LLM 端点检测 | ✅ | ❌ | OpenAkita |
| 组件级检测 | ❌ | ✅ | DeskFlow |
| 系统资源监控 | ❌ | ✅ | DeskFlow |
| 进程健康检查 | ❌ | ✅ | DeskFlow |
| 健康建议生成 | ❌ | ✅ | DeskFlow |
| dry_run 模式 | ✅ | ❌ | OpenAkita |

**结论**: DeskFlow 的健康检查更加**全面和详细**，适合单用户桌面应用的运维需求。OpenAkita 的健康检查更专注于**LLM 端点管理**，适合多租户 SaaS 场景。

---

## 3️⃣ Token 统计模块对比

### OpenAkita Token Stats API

**文件**: `src/openakita/api/routes/token_stats.py`

**端点**:
| 端点 | 说明 |
|------|------|
| `GET /api/stats/tokens/summary` | 按维度聚合统计 |
| `GET /api/stats/tokens/timeline` | 时间序列图表数据 |
| `GET /api/stats/tokens/sessions` | 会话级别统计 |
| `GET /api/stats/tokens/total` | 总计 |
| `GET /api/stats/tokens/context` | 当前上下文大小 |

**查询参数**:
- `group_by`: 按 endpoint_name / operation_type 分组
- `period`: 1d / 3d / 1w / 1m / 6m / 1y
- `start/end`: 自定义时间范围
- `endpoint_name`: 按端点过滤
- `interval`: hour / day / week / month

**数据库支持**:
- SQLite FTS5
- PostgreSQL (可选)

---

### Coolaw DeskFlow Token Stats API

**文件**: `src/deskflow/api/routes/monitor.py`, `src/deskflow/core/token_tracking.py`

**端点**:
| 端点 | 说明 |
|------|------|
| `GET /api/monitor/llm-stats` | LLM 使用统计 |
| `GET /api/monitor/token-stats` | Token 统计详情 |
| `GET /api/metrics` | Prometheus 指标 |

**统计内容**:
```json
{
  "provider": "Anthropic",
  "model": "claude-3-5-sonnet",
  "memory_count": 42,
  "active_tools": 3,
  "total_tokens": 150000,
  "today_tokens": 5000,
  "total_cost_usd": 1.25,
  "today_cost_usd": 0.15,
  "request_count": 120,
  "today_request_count": 15
}
```

---

### Token 统计差异总结

| 功能 | OpenAkita | DeskFlow | 优势方 |
|------|-----------|----------|--------|
| 多维度统计 | ✅ | ❌ | OpenAkita |
| 时间序列分析 | ✅ | ❌ | OpenAkita |
| 会话级统计 | ✅ | ❌ | OpenAkita |
| 成本估算 | ✅ | ✅ | 平手 |
| 当日统计 | ✅ | ✅ | 平手 |
| Prometheus 导出 | ❌ | ✅ | DeskFlow |
| 上下文监控 | ✅ | ❌ | OpenAkita |

**结论**: OpenAkita 的 Token 统计功能**明显更强**，支持多维度分析和时间序列查询，适合企业级计费和成本分析场景。DeskFlow 的 Token 统计相对简单，但集成了 Prometheus 监控。

---

## 4️⃣ 系统监控模块对比

### OpenAkita 系统监控

**状态**: ❌ **无独立系统监控模块**

系统资源监控分散在：
- `api/routes/health.py` - 基础健康检查
- `core/task_monitor.py` - 任务级别指标

**缺失功能**:
- ❌ CPU/内存/磁盘实时监控
- ❌ 进程级资源追踪
- ❌ 网络 I/O 监控
- ❌ 系统告警机制

---

### Coolaw DeskFlow 系统监控

**文件**: `src/deskflow/api/routes/monitor.py`

**端点**:
| 端点 | 说明 |
|------|------|
| `GET /api/monitor/status` | 实时系统状态 |
| `GET /api/monitor/activity` | 活动日志查询 |
| `GET /api/monitor/token-stats` | Token 统计 |
| `WebSocket /api/monitor/ws/activity` | 活动实时推送 |

**监控内容**:
```json
{
  "cpu": {"percent": 12.5, "cores": 8},
  "memory": {"used_mb": 340, "total_mb": 8192, "percent": 4.2},
  "disk": {"used_gb": 120, "total_gb": 512, "percent": 23.4},
  "data_disk": {"used_gb": 1.2, "total_gb": 512, "percent": 0.2},
  "uptime_seconds": 3600,
  "platform": "Darwin"
}
```

**活动日志功能**:
- ✅ 按类型过滤 (llm_call, tool_execution, memory_operation, system_event, user_action)
- ✅ 按状态过滤 (success, failed, pending)
- ✅ 限制返回数量
- ✅ WebSocket 实时推送

---

### 系统监控差异总结

| 功能 | OpenAkita | DeskFlow | 优势方 |
|------|-----------|----------|--------|
| CPU 监控 | ❌ | ✅ | DeskFlow |
| 内存监控 | ❌ | ✅ | DeskFlow |
| 磁盘监控 | ❌ | ✅ | DeskFlow |
| 进程监控 | ❌ | ✅ | DeskFlow |
| 活动日志 | ❌ | ✅ | DeskFlow |
| WebSocket 推送 | ❌ | ✅ | DeskFlow |

**结论**: DeskFlow 在系统监控方面**全面领先**，提供了完整的系统资源监控和实时活动推送能力。OpenAkita 在此方面基本空白。

---

## 5️⃣ Prometheus 集成对比

### OpenAkita Prometheus 集成

**状态**: ❌ **无 Prometheus 集成**

---

### Coolaw DeskFlow Prometheus 集成

**文件**: `src/deskflow/api/routes/metrics.py`

**端点**:
| 端点 | 说明 |
|------|------|
| `GET /api/metrics` | Prometheus 格式指标 |
| `GET /api/metrics/summary` | 人类可读摘要 |

**指标类型**:
```
# Process Metrics
deskflow_process_cpu_percent
deskflow_process_memory_rss_bytes
deskflow_process_memory_vms_bytes
deskflow_uptime_seconds

# System Metrics
deskflow_system_memory_percent
deskflow_system_disk_percent

# Memory System Metrics
deskflow_memory_total
deskflow_memory_cache_hits
deskflow_memory_cache_misses
deskflow_memory_cache_hit_rate
deskflow_memory_hnsw_index_size

# Tool System Metrics
deskflow_tools_registered

# LLM Metrics
deskflow_llm_info{provider, model}

# HTTP Metrics
deskflow_http_requests_total{endpoint}
```

**Grafana 仪表板支持**:
- ✅ 可直接对接 Grafana
- ✅ 支持 AlertManager 告警
- ✅ 支持 Prometheus 查询语言 (PromQL)

---

### Prometheus 集成差异总结

| 功能 | OpenAkita | DeskFlow | 优势方 |
|------|-----------|----------|--------|
| Prometheus 导出 | ❌ | ✅ | DeskFlow |
| Grafana 集成 | ❌ | ✅ | DeskFlow |
| 自定义指标 | ❌ | ✅ | DeskFlow |
| 告警规则 | ❌ | ✅ | DeskFlow |

**结论**: DeskFlow 的 Prometheus 集成是**企业级可观测性**的重要特性，OpenAkita 在此方面完全缺失。

---

## 6️⃣ 多 Agent 协同监控对比

### OpenAkita 多 Agent 监控

**文件**: `src/openakita/orchestration/monitor.py`

**功能**:
- ✅ Master/Worker 架构监控
- ✅ Worker 注册发现状态
- ✅ 负载均衡状态
- ✅ ZeroMQ 消息总线健康检查

**监控内容**:
```python
class OrchestrationMonitor:
    """多 Agent 协同监控器"""

    def get_worker_status(self) -> list[WorkerInfo]:
        """获取 Worker 状态列表"""

    def get_task_distribution(self) -> dict:
        """获取任务分发统计"""

    def get_load_balance_stats(self) -> dict:
        """获取负载均衡统计"""
```

---

### Coolaw DeskFlow 多 Agent 监控

**状态**: ❌ **不支持多 Agent 协同**

**未来计划** (Phase 4):
- [ ] Master/Worker 架构
- [ ] ZeroMQ 消息总线
- [ ] Worker 注册发现

---

### 多 Agent 监控差异总结

| 功能 | OpenAkita | DeskFlow | 优势方 |
|------|-----------|----------|--------|
| Master/Worker 监控 | ✅ | ❌ | OpenAkita |
| Worker 注册发现 | ✅ | ❌ | OpenAkita |
| 负载均衡统计 | ✅ | ❌ | OpenAkita |
| 消息总线监控 | ✅ | ❌ | OpenAkita |

**结论**: OpenAkita 的多 Agent 协同监控是**企业级特性**，DeskFlow 目前为单 Agent 架构。

---

## 7️⃣ IM 通道监控对比

### OpenAkita IM 通道监控

**文件**: `src/openakita/api/routes/im.py`

**支持平台**:
- Telegram
- 飞书 (Feishu)
- 企业微信 (WeWork)
- 钉钉 (DingTalk)
- OneBot (NapCat/Lagrange)
- QQ 官方机器人

**监控内容**:
- ✅ 通道连接状态
- ✅ 消息收发统计
- ✅ Webhook 健康检查
- ✅ 会话管理状态

---

### Coolaw DeskFlow IM 通道监控

**状态**: ❌ **不支持 IM 通道**

**未来计划** (Phase 3):
- [ ] 飞书集成
- [ ] 企业微信集成
- [ ] 钉钉集成

---

### IM 通道监控差异总结

| 功能 | OpenAkita | DeskFlow | 优势方 |
|------|-----------|----------|--------|
| Telegram | ✅ | ❌ | OpenAkita |
| 飞书 | ✅ | ❌ | OpenAkita |
| 企业微信 | ✅ | ❌ | OpenAkita |
| 钉钉 | ✅ | ❌ | OpenAkita |
| OneBot | ✅ | ❌ | OpenAkita |
| QQ 官方 | ✅ | ❌ | OpenAkita |

**结论**: OpenAkita 的 IM 通道监控是**全渠道客服场景**的核心能力，DeskFlow 目前专注于桌面应用。

---

## 📊 功能矩阵总览

| 功能模块 | OpenAkita | DeskFlow | 优势方 |
|----------|-----------|----------|--------|
| **TaskMonitor** | ⭐⭐⭐⭐ | ⭐⭐⭐ | OpenAkita |
| **健康检查** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | DeskFlow |
| **Token 统计** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | OpenAkita |
| **系统监控** | ⭐ | ⭐⭐⭐⭐⭐ | DeskFlow |
| **Prometheus** | ❌ | ⭐⭐⭐⭐⭐ | DeskFlow |
| **多 Agent 监控** | ⭐⭐⭐⭐ | ❌ | OpenAkita |
| **IM 通道监控** | ⭐⭐⭐⭐ | ❌ | OpenAkita |
| **活动日志** | ⭐⭐ | ⭐⭐⭐⭐⭐ | DeskFlow |
| **WebSocket 推送** | ❌ | ⭐⭐⭐⭐ | DeskFlow |
| **任务复盘** | ⭐⭐⭐⭐ | ❌ | OpenAkita |

---

## 🎯 架构定位差异

### OpenAkita

**定位**: 企业级多 Agent 协同平台

**监控设计目标**:
1. 支持多租户、多 Agent 协同
2. 全渠道 IM 接入监控
3. Token 成本分析和计费
4. 任务执行复盘和优化

**典型场景**:
- 企业客服中心 (多 IM 平台)
- 多 Agent 任务协同
- Token 成本分摊

---

### Coolaw DeskFlow

**定位**: 单用户桌面 AI 助手

**监控设计目标**:
1. 本地系统资源监控
2. 实时活动推送
3. Prometheus 可观测性
4. 组件健康检查

**典型场景**:
- 个人开发者桌面助手
- 本地运行、本地监控
- Grafana 仪表板展示

---

## 💡 改进建议

### 对 Coolaw DeskFlow 的建议

基于 OpenAkita 的优势功能，建议补充：

#### Phase 1 (短期)
- [ ] **增强 Token 统计**
  - 添加按端点分组统计
  - 添加时间序列查询
  - 添加会话级统计
- [ ] **任务复盘功能**
  - 实现 `get_retrospect_context()`
  - 添加复盘结果存储
  - 与每日自检系统集成

#### Phase 2 (中期)
- [ ] **多 Agent 监控**
  - Master/Worker 架构监控
  - Worker 注册发现
- [ ] **IM 通道监控**
  - 飞书集成
  - 企业微信集成

### 对 OpenAkita 的建议

基于 DeskFlow 的优势功能，建议补充：

- [ ] **系统资源监控**
  - CPU/内存/磁盘监控
  - 进程级资源追踪
- [ ] **Prometheus 集成**
  - `/metrics` 端点
  - Grafana 仪表板模板
- [ ] **组件级健康检查**
  - Memory/Tools/LLM 组件检测

---

## 📝 总结

### OpenAkita 优势
1. **企业级特性**: 多 Agent 协同、IM 通道监控
2. **Token 分析**: 多维度统计、时间序列查询
3. **任务复盘**: 深度任务执行分析和优化

### Coolaw DeskFlow 优势
1. **系统监控**: 完整的 CPU/内存/磁盘监控
2. **可观测性**: Prometheus + Grafana 集成
3. **实时推送**: WebSocket 活动推送
4. **健康检查**: 组件级详细健康诊断

### 适用场景

| 场景 | 推荐项目 |
|------|----------|
| 企业客服中心 | OpenAkita |
| 个人桌面助手 | DeskFlow |
| 多 Agent 协同 | OpenAkita |
| 本地运行 + Grafana 监控 | DeskFlow |
| 全渠道 IM 接入 | OpenAkita |
| 系统资源敏感型应用 | DeskFlow |

---

**报告编制**: Architect Agent + Orchestrator Agent
**审阅状态**: 待技术负责人确认
**许可**: MIT License
