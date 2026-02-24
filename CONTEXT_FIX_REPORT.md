# 上下文连贯性修复报告

**日期**: 2026-02-24
**问题**: coolaw-deskflow 无法识别上下文引用（如"删除刚创建的文件夹"）
**状态**: 已修复

---

## 问题分析

### 根本原因

1. **对话历史未加载** ⭐⭐⭐
   - Agent 每次收到请求时创建新的空 Conversation 对象
   - 没有从持久化存储加载历史消息
   - 导致每次请求都是"新的开始"

2. **短期记忆缺失** ⭐⭐
   - 没有追踪最近操作的对象（文件、文件夹等）
   - 无法理解"刚创建的"、"那个文件"等上下文引用

3. **提示词缺少上下文** ⭐
   - PromptAssembler 没有包含最近操作的上下文信息
   - LLM 无法获知用户所指的对象

---

## 修复方案

### 1. 新增最近实体追踪缓存 (`recent_entities.py`)

**文件**: `src/deskflow/core/recent_entities.py`

```python
class RecentEntitiesCache:
    """追踪最近操作的对象（文件、文件夹等）"""

    def add(entity_type, name, action, location)  # 添加实体
    def get_last(entity_type, action)              # 获取最近的实体
    def get_recent(limit, max_age_seconds)         # 获取最近的实体列表
    def to_prompts()                                # 生成提示词上下文
```

**功能**:
- 追踪最近 20 个操作的对象
- 5 分钟 TTL（可配置）
- 支持按类型、动作筛选
- 生成 LLM 可读的上下文提示

### 2. 增强记忆存储 (`memory/storage.py`)

**新增方法**:
```python
async def save_conversation(conversation_id, messages, title)  # 保存对话
async def load_conversation(conversation_id)                    # 加载对话
async def get_conversation_ids(limit)                           # 获取对话列表
```

**功能**:
- 持久化存储对话历史
- 支持按 conversation_id 加载完整历史
- 自动管理消息顺序

### 3. 增强记忆管理器 (`memory/manager.py`)

**新增方法**:
```python
def add_recent_entity(entity_type, name, action, location)      # 添加实体
def get_recent_entities(limit, max_age_seconds, entity_type)   # 获取实体
def get_recent_entities_context(limit)                          # 获取提示上下文
async def save_conversation(...)                                 # 保存对话
async def load_conversation(...)                                 # 加载对话
```

**功能**:
- 集成 RecentEntitiesCache
- 提供统一的实体追踪接口
- 暴露对话历史方法

### 4. 增强 Agent (`core/agent.py`)

**新增方法**:
```python
async def _load_conversation_history(conversation_id)  # 加载对话历史
def _track_tool_execution(tool_name, args, result)     # 追踪工具执行
def _track_shell_command(command)                       # 追踪 shell 命令
```

**功能**:
- 每次请求前加载对话历史
- 自动追踪文件/文件夹操作
- 识别 mkdir, rm, cp, mv, touch, cd 等命令

**追踪的操作**:
| Shell 命令 | 实体类型 | 动作 |
|-----------|---------|------|
| `mkdir`   | folder  | create |
| `rm` / `rmdir` | file/folder | delete |
| `cp`      | file    | copy |
| `mv`      | file    | move |
| `touch`   | file    | create |
| `cd`      | folder  | open |

### 5. 增强提示词组装 (`core/prompt_assembler.py`)

**新增方法**:
```python
def _format_recent_entities_context()  # 格式化实体上下文
```

**生成的提示词示例**:
```
## Recent Context

The user has recently performed these actions:

- Created folder called "123" (at /Users/seacao/Desktop)
- Created file called "test.txt" (at /Users/seacao/Desktop)

When the user refers to 'the folder I just created' or 'that file',
they are likely referring to one of these recent operations.
```

---

## 测试验证

运行测试脚本:
```bash
python test_context_fix.py
```

**测试结果**:
```
=== Test Recent Entities Cache ===
✓ 添加实体
✓ 获取最近实体
✓ 获取最后一个创建的文件夹
✓ 按名称查找实体
✓ 生成上下文摘要
✓ 生成提示词

=== Test Memory Storage ===
✓ 保存对话
✓ 加载对话
✓ 验证消息内容

ALL TESTS PASSED!
```

---

## 使用示例

### 场景 1: 创建文件夹后删除

```
用户：在桌面创建文件夹 123
Agent: [执行 mkdir ~/Desktop/123] ✓ 已创建

用户：删除刚创建的文件夹
Agent: [理解"刚创建的文件夹"指的是"123"]
       [执行 rmdir ~/Desktop/123] ✓ 已删除
```

### 场景 2: 多轮对话

```
用户：创建一个测试文件 test.txt
Agent: [执行 touch test.txt] ✓ 已创建

用户：打开看看
Agent: [理解"打开看看"指的是"test.txt"]
       [执行 cat test.txt]
```

---

## 配置选项

### RecentEntitiesCache 配置

```python
# 在 MemoryManager 初始化时配置
memory = MemoryManager(
    db_path="data/db/deskflow.db",
    recent_entities_max=20,        # 最多追踪 20 个实体
    recent_entities_ttl=300.0,     # 5 分钟过期
)
```

---

## 注意事项

1. **实体追踪依赖工具执行结果**
   - 只有成功执行的工具调用才会被追踪
   - 失败的命令不会记录

2. **TTL 配置**
   - 默认 5 分钟，根据需求调整
   - 过短会丢失上下文，过长会积累噪音

3. **提示词长度**
   - 最近实体上下文占用约 200-300 tokens
   - 已纳入整体 token 预算管理

---

## 后续改进建议

1. **智能实体链接**
   - 使用 NLP 模型识别用户引用的实体
   - 例如："那个文件夹" → 自动匹配最近创建的文件夹

2. **长期记忆整合**
   - 将频繁访问的实体转入长期记忆
   - 支持跨会话上下文

3. **实体关系图谱**
   - 记录文件/文件夹的父子关系
   - 支持"删除文件夹里的文件"等复杂引用

---

## 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `src/deskflow/core/recent_entities.py` | 新增 | 实体追踪缓存 |
| `src/deskflow/memory/storage.py` | 修改 | 添加对话历史方法 |
| `src/deskflow/memory/manager.py` | 修改 | 集成实体追踪 |
| `src/deskflow/core/agent.py` | 修改 | 加载历史 + 实体追踪 |
| `src/deskflow/core/prompt_assembler.py` | 修改 | 添加实体上下文 |
| `test_context_fix.py` | 新增 | 测试脚本 |

---

**修复完成** ✅

现在 coolaw-deskflow 应该能够正确识别上下文引用，如"删除刚创建的文件夹"。
