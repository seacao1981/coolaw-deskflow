# Coolaw DeskFlow - 文档索引

**版本**: v0.1.0
**最后更新**: 2026-02-24

---

## 📚 快速导航

| 用途 | 推荐文档 | 位置 |
|------|----------|------|
| **新手入门** | [README.md](#readmemd) | 项目根目录 |
| **安装部署** | [DEPLOYMENT.md](#deploymentmd) | docs/ |
| **API 参考** | [api.md](#apimd) | docs/ |
| **配置说明** | [configuration.md](#configurationmd) | docs/ |
| **开发指南** | [developer-guide.md](#developer-guidemd) | docs/ |
| **技术架构** | [ARCHITECTURE.md](#architecturemd) | 项目根目录 |
| **贡献指南** | [CONTRIBUTING.md](#contributingmd) | 项目根目录 |
| **项目状态** | [PROJECT_STATUS.md](#project-statusmd) | 项目根目录 |

---

## 📁 项目根目录文档

### README.md
**用途**: 项目说明和快速开始
**内容**:
- 产品概述
- 功能特性
- 快速开始 (安装、配置、使用)
- 技术栈
- 架构概览

**适合**: 首次接触项目的用户

[📖 阅读全文](../README.md)

---

### PROJECT_STATUS.md
**用途**: 项目状态报告
**内容**:
- 完成度概览表
- 质量指标
- 文档清单
- 待办事项
- 下一步计划

**适合**: 项目管理者、 contributors

[📖 阅读全文](PROJECT_STATUS.md)

---

### CONTRIBUTING.md
**用途**: 贡献指南
**内容**:
- 开发环境设置
- 代码规范
- Git 提交流程
- 测试指南
- 文档规范
- 问题报告模板

**适合**: 开发者、贡献者

[📖 阅读全文](CONTRIBUTING.md)

---

### ARCHITECTURE.md
**用途**: 技术架构文档
**内容**:
- 分层架构图
- 核心模块详解
- 数据流图
- 技术决策记录 (ADR)
- 部署架构
- 性能优化

**适合**: 架构师、高级开发者

[📖 阅读全文](ARCHITECTURE.md)

---

### CHANGELOG.md
**用途**: 变更日志
**内容**:
- 版本历史
- 每个版本的变更内容
- 即将发布的计划

**适合**: 所有用户

[📖 阅读全文](CHANGELOG.md)

---

### CLAUDE.md
**用途**: 项目开发规范 (Claude Code)
**内容**:
- 12 阶段开发流程
- 确认检查点
- 文档路径规范
- UI/UX Pro Max 设计系统
- 验证循环
- Agent 团队配置

**适合**: 使用 Claude Code 的开发者

[📖 阅读全文](CLAUDE.md)

---

## 📂 docs/ 目录文档

### api.md
**用途**: API 参考文档
**内容**:
- REST API 端点
- WebSocket API
- 请求/响应格式
- 错误处理
- 速率限制

**端点列表**:
| 端点 | 方法 | 说明 |
|------|------|------|
| /api/chat | POST | 发送消息 |
| /api/chat/stream | WebSocket | 流式输出 |
| /api/health | GET | 健康检查 |
| /api/status | GET | 组件状态 |
| /api/config | GET | 配置信息 |

[📖 阅读全文](api.md)

---

### configuration.md
**用途**: 配置参考手册
**内容**:
- 环境变量列表
- LLM 配置 (Anthropic/OpenAI/DashScope)
- 服务器配置
- 记忆系统配置
- 工具配置

**配置示例**:
```bash
# LLM 配置
DESKFLOW_LLM_PROVIDER=anthropic
DESKFLOW_ANTHROPIC_API_KEY=sk-ant-...

# 服务器配置
DESKFLOW_HOST=127.0.0.1
DESKFLOW_PORT=8420

# 记忆配置
DESKFLOW_MEMORY_CACHE_SIZE=1000
```

[📖 阅读全文](configuration.md)

---

### developer-guide.md
**用途**: 开发者指南
**内容**:
- 项目结构
- 架构原则
- 开发工作流
- 测试策略
- 错误处理
- 添加新工具/LLM 提供商

**适合**: 核心开发者

[📖 阅读全文](developer-guide.md)

---

### DEPLOYMENT.md
**用途**: 部署指南
**内容**:
- 系统要求
- 快速安装 (源码/pip/Docker)
- 配置说明
- 运行服务
- 桌面应用安装
- 故障排除

**安装方式**:
1. 源码安装 (推荐)
2. pip 安装
3. Docker 安装

[📖 阅读全文](DEPLOYMENT.md)

---

### prd-compliance-report.md
**用途**: PRD 合规性报告
**内容**:
- PRD 需求覆盖情况
- 功能实现状态
- 非功能需求达标情况
- 验收结果

[📖 阅读全文](prd-compliance-report.md)

---

### identity/AGENT.md
**用途**: Agent 身份定义
**内容**:
- Agent 核心能力
- 行为准则
- 权限边界

[📖 阅读全文](identity/AGENT.md)

---

## 📂 Obsidian Vault 文档

位置：`/Users/seacao/Documents/cjh_vault/Projects/coolaw-deskflow/`

### 01-PRD/PRD-v1.0-需求说明.md
**用途**: 产品需求说明书
**内容**:
- 产品定位
- 目标用户
- 功能需求 (P0/P1/P2)
- 非功能需求
- 技术架构
- 项目排期

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/01-PRD/PRD-v1.0-需求说明.md)

---

### 02-DRD/DRD-v1.0-设计说明.md
**用途**: 设计说明书
**内容**:
- 设计理念
- 信息架构
- 页面设计
- 交互规范
- 原型说明

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/02-DRD/DRD-v1.0-设计说明.md)

---

### 03-原型/prototype/index.html
**用途**: HTML 交互原型
**内容**:
- Chat View
- Skills View
- Monitor View
- Settings View

[📖 打开原型](../../Documents/cjh_vault/Projects/coolaw-deskflow/03-原型/prototype/index.html)

---

### 04-开发任务/tasks.md
**用途**: 开发任务清单
**内容**:
- 24 个开发任务
- 任务依赖图
- 工时估算
- 执行注意事项

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/04-开发任务/tasks.md)

---

### 05-测试用例/test-cases-v1.0.md
**用途**: 测试用例文档
**内容**:
- 测试策略
- 测试场景 by 模块
- 覆盖率报告

**测试统计**:
- 总测试数：287
- 覆盖率：83.21%

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/05-测试用例/test-cases-v1.0.md)

---

### 06-验证报告/verification-report-v1.0.md
**用途**: 6 阶段验证报告
**内容**:
- Phase 1: Build Verification
- Phase 2: Type Check
- Phase 3: Lint Check
- Phase 4: Test Suite
- Phase 5: Security Scan
- Phase 6: Diff Review

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/06-验证报告/verification-report-v1.0.md)

---

### 07-开发日志/
**用途**: 开发日志
**内容**:
- 2026-02-21.md - MVP 开发完成日志
- 2026-02-21-final.md - Tauri 构建完成日志
- 2026-02-24-documentation.md - 文档补档完成日志

[📖 查看开发日志](../../Documents/cjh_vault/Projects/coolaw-deskflow/07-开发日志/)

---

### 08-远程测试指南/
**用途**: 远程测试配置指南
**内容**:
- 远程测试环境设置
- SSH 配置
- 端口转发
- 测试流程

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/08-远程测试指南/)

---

### 09-Tauri-Integration/Tauri-Integration-Complete.md
**用途**: Tauri 集成完成报告
**内容**:
- Tauri 配置
- 集成过程
- 问题与解决方案

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/09-Tauri-Integration/Tauri-Integration-Complete.md)

---

### 10-桌面应用测试/
**用途**: 桌面应用测试文档
**内容**:
- desktop-app-test-guide.md - 手动测试指南 (60+ 测试用例)
- desktop-app-test-report.md - 自动化测试报告 (18 测试)
- SUMMARY.md - 测试总结

[📖 查看测试文档](../../Documents/cjh_vault/Projects/coolaw-deskflow/10-桌面应用测试/)

---

### 11-Settings-UI-改进方案/settings-ui-improvement-plan.md
**用途**: Settings UI 改进方案
**内容**:
- 当前 UI 分析
- 改进建议
- 实现方案

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/11-Settings-UI-改进方案/settings-ui-improvement-plan.md)

---

### design-system/MASTER.md
**用途**: 全局设计系统
**内容**:
- Color Palette (16 色)
- Typography (Fira Code + Fira Sans)
- Spacing Variables
- Border Radius
- Shadow Depths
- Layout System
- Component Specs
- Animation & Transitions

**适合**: 前端开发者

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/design-system/coolaw-deskflow/MASTER.md)

---

### source/architecture-analysis.md
**用途**: 架构分析报告 (OpenAkita 参考)
**内容**:
- 项目概述
- 整体架构
- 技术栈清单
- 核心逻辑关系
- 功能模块清单
- 潜在风险与优化点

[📖 阅读全文](../../Documents/cjh_vault/Projects/coolaw-deskflow/source/architecture-analysis.md)

---

## 🔗 技能文档

位置：`skills/system/*/SKILL.md`

### 系统技能 (60+)

| 技能类别 | 技能数量 |
|----------|----------|
| 浏览器自动化 | 15+ |
| 桌面控制 | 10+ |
| 文件操作 | 5+ |
| Shell 命令 | 5+ |
| 记忆管理 | 5+ |
| 任务计划 | 5+ |
| MCP 集成 | 5+ |
| 用户配置 | 5+ |
| 其他 | 10+ |

**示例**:
- `browser-screenshot/SKILL.md` - 浏览器截图技能
- `desktop-click/SKILL.md` - 桌面点击技能
- `run-shell/SKILL.md` - Shell 命令执行技能
- `add-memory/SKILL.md` - 添加记忆技能

[📖 查看所有技能](../skills/system/)

---

## 📋 身份定义文档

位置：`identity/`

| 文档 | 用途 |
|------|------|
| SOUL.md | Agent 核心价值与本质 |
| AGENT.md | 能力边界与行为准则 |
| USER.md | 用户特定信息与偏好 |
| MEMORY.md | 长期记忆摘要 |
| personas/default.md | 默认人格 |
| personas/butler.md | 管家 |
| personas/tech_expert.md | 技术专家 |
| personas/business.md | 商务 |

[📖 查看身份定义](../identity/)

---

## 🎯 按角色推荐阅读

### 普通用户
1. README.md - 了解产品
2. DEPLOYMENT.md - 安装使用
3. configuration.md - 配置说明

### 开发者
1. CONTRIBUTING.md - 开发规范
2. ARCHITECTURE.md - 技术架构
3. developer-guide.md - 开发指南
4. CLAUDE.md - Claude Code 流程

### 架构师
1. ARCHITECTURE.md - 架构设计
2. source/architecture-analysis.md - 架构分析
3. PRD-v1.0-需求说明.md - 需求文档

### 测试人员
1. test-cases-v1.0.md - 测试用例
2. verification-report-v1.0.md - 验证报告
3. desktop-app-test-guide.md - 手动测试指南

### 产品经理
1. PROJECT_STATUS.md - 项目状态
2. PRD-v1.0-需求说明.md - 需求文档
3. CHANGELOG.md - 版本历史

---

## 📞 需要帮助？

- **GitHub Issues**: https://github.com/coolaw/coolaw-deskflow/issues
- **GitHub Discussions**: https://github.com/coolaw/coolaw-deskflow/discussions
- **文档问题**: 在对应文档目录下提交 Issue

---

**编制**: Documentation Team
**版本**: v0.1.0
**许可**: MIT License
