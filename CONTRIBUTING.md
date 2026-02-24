# Coolaw DeskFlow - 贡献指南

**版本**: v0.1.0
**最后更新**: 2026-02-24

---

## 📋 目录

1. [开发环境设置](#开发环境设置)
2. [代码规范](#代码规范)
3. [提交流程](#提交流程)
4. [测试指南](#测试指南)
5. [文档规范](#文档规范)
6. [问题报告](#问题报告)
7. [联系方式](#联系方式)

---

## 开发环境设置

### 前置要求

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 后端开发 |
| Node.js | 20+ | 前端构建 |
| Rust | 1.75+ | Tauri 编译 |
| Git | 2.40+ | 版本控制 |

### 克隆项目

```bash
git clone https://github.com/coolaw/coolaw-deskflow.git
cd coolaw-deskflow
```

### Python 环境

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装开发依赖
pip install -e ".[dev]"

# 验证安装
python -m deskflow --help
```

### Node.js 环境

```bash
cd apps/desktop

# 安装依赖
npm install

# 开发模式
npm run dev

# 构建
npm run build
```

### 配置

```bash
# 复制环境变量示例
cp .env.example .env

# 编辑 .env，填入你的 API 密钥
# 或使用初始化向导
deskflow init
```

---

## 代码规范

### Python 代码

```bash
# 格式化代码
ruff format src/deskflow/

# 检查代码质量
ruff check src/deskflow/

# 类型检查
mypy src/deskflow/
```

**命名约定**:
- 类：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 私有成员：`_prefix`

**代码风格**:
- 函数不超过 50 行
- 文件不超过 500 行
- 使用类型注解
- 添加文档字符串

### TypeScript 代码

```bash
cd apps/desktop

# 格式化
npm run format

# 检查
npm run lint

# 类型检查
npx tsc --noEmit
```

**命名约定**:
- 类/组件：`PascalCase` (如 `ChatView.tsx`)
- 函数/变量：`camelCase`
- 常量：`UPPER_SNAKE_CASE`
- 接口/类型：`PascalCase`

---

## 提交流程

### 分支策略

```
main (生产)
  ↑
develop (开发)
  ↑
feature/xxx (功能分支)
```

### 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Type 类型**:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

**示例**:
```
feat(chat): 添加流式输出功能

- 实现 WebSocket 流式传输
- 添加前端逐字渲染
- 编写单元测试

Closes #123
```

### 提交流程

```bash
# 1. 创建功能分支
git checkout -b feature/chat-stream

# 2. 开发并提交
git add .
git commit -m "feat(chat): 实现流式输出"

# 3. 推送到远程
git push origin feature/chat-stream

# 4. 创建 Pull Request
```

---

## 测试指南

### 运行测试

```bash
# 所有测试
pytest

# 带覆盖率
pytest --cov=src/deskflow --cov-report=term-missing

# 特定模块
pytest tests/unit/test_core/test_agent.py

# 集成测试
pytest tests/integration/
```

### 覆盖率要求

| 模块类型 | 覆盖率要求 |
|----------|-----------|
| 核心模块 (core/) | >= 90% |
| 记忆系统 (memory/) | >= 90% |
| 工具系统 (tools/) | >= 80% |
| API 层 (api/) | >= 70% |
| CLI | >= 60% |
| 整体 | >= 80% |

### 测试命名

```python
# ✅ 好的命名
def test_agent_chat_returns_assistant_message():
    pass

def test_memory_store_failure_does_not_crash():
    pass

# ❌ 不好的命名
def test_chat():
    pass

def test_memory():
    pass
```

---

## 文档规范

### 文档类型

| 类型 | 位置 | 说明 |
|------|------|------|
| PRD | `docs/01-PRD/` | 产品需求文档 |
| DRD | `docs/02-DRD/` | 设计说明文档 |
| 任务 | `docs/04-开发任务/` | 开发任务清单 |
| 测试 | `docs/05-测试用例/` | 测试用例 |
| 日志 | `docs/07-开发日志/` | 开发日志 |

### 文档模板

**PRD 模板**:
```markdown
# PRD v1.0 - {产品名}

## 1. 产品概述
### 1.1 产品定位
### 1.2 目标用户
### 1.3 价值主张

## 2. 功能需求
### 2.1 P0 - 必须实现
### 2.2 P1 - 重要功能
### 2.3 P2 - 扩展功能

## 3. 非功能需求
### 3.1 性能要求
### 3.2 安全要求

## 4. 技术架构
## 5. 项目排期
```

### 文档版本

- 使用 `v1.0`, `v1.1`, `v2.0` 等版本号
- 重大变更升级主版本
- 小修改升级次版本

---

## 问题报告

### Bug 报告模板

```markdown
**问题描述**: 简要描述问题

**复现步骤**:
1. 步骤 1
2. 步骤 2
3. 步骤 3

**期望行为**: 应该发生什么

**实际行为**: 实际发生了什么

**环境信息**:
- OS: macOS 14.0
- Python: 3.11.5
- 版本：v0.1.0

**日志**: 附上相关日志
```

### 功能请求模板

```markdown
**功能描述**: 想要什么功能

**使用场景**: 为什么需要这个功能

**实现建议**: 如何实现 (可选)
```

---

## 联系方式

- GitHub Issues: https://github.com/coolaw/coolaw-deskflow/issues
- 项目讨论：GitHub Discussions

---

## 感谢贡献

感谢所有为 Coolaw DeskFlow 做出贡献的开发者！

[![Contributors](https://contrib.rocks/image?repo=coolaw/coolaw-deskflow)](https://github.com/coolaw/coolaw-deskflow/graphs/contributors)

---

**编制**: Coolaw DeskFlow Team
**许可**: MIT License
