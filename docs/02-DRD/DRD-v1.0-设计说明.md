# DRD v1.0 - Coolaw DeskFlow 设计说明书

> **版本**: v1.0
> **日期**: 2026-02-21
> **状态**: 待确认
> **作者**: Prototype Agent
> **设计系统**: design-system/MASTER.md

---

## 1. 设计理念

### 1.1 核心风格

**Dark Mode Dashboard + Minimal IDE Aesthetic**

Coolaw DeskFlow 是一款面向开发者和技术用户的 AI Agent 桌面应用。设计语言以深色模式为基底，融合 IDE 和现代 Dashboard 的视觉元素，传达"智能、精准、可信赖"的产品气质。

### 1.2 设计原则

| 原则 | 描述 | 体现 |
|------|------|------|
| **专注 (Focus)** | 对话是核心，界面元素不喧宾夺主 | 大面积留白，信息层级清晰 |
| **信任 (Trust)** | 用户需要相信 AI Agent 的判断 | 状态透明，操作可追溯，错误明示 |
| **效率 (Efficiency)** | 开发者追求效率 | 键盘优先，侧边栏收缩，快捷操作 |
| **可控 (Control)** | 用户始终掌控 Agent 行为 | 停止按钮醒目，权限可配置，日志可查 |

### 1.3 配色方案

**主题: "Code Dark + Run Green"**

深色 Slate 色系作为背景底色，#22C55E 绿色作为核心动作色（代表"执行/运行"），语义色用于状态反馈。

详见 `design-system/MASTER.md > Color Palette`。

### 1.4 字体方案

**Fira Code + Fira Sans**

- Fira Code (monospace): 标题、代码块、技术标签 -- 传达技术感
- Fira Sans (sans-serif): 正文、按钮、描述 -- 保证可读性

---

## 2. 信息架构

### 2.1 导航结构

```
Sidebar (左侧导航)
  |-- Chat (默认视图)         对话交互
  |-- Skills                  技能管理
  |-- Monitor                 状态监控
  |-- Settings                系统设置
  |
  |-- [底部]
  |   |-- User Profile        用户头像 + 状态
  |   |-- Collapse Toggle     收起/展开侧边栏
```

### 2.2 视图层级

```
App Shell
  |-- Title Bar (Tauri 拖拽区域 + 窗口控制)
  |-- Sidebar (导航 + 用户)
  |-- Main Content
  |   |-- Chat View
  |   |   |-- Conversation List (左面板, 可选)
  |   |   |-- Chat Area (消息 + 输入)
  |   |-- Skills View
  |   |   |-- Skill Browser (网格/列表)
  |   |   |-- Skill Detail (侧面板)
  |   |-- Monitor View
  |   |   |-- Status Cards (Agent/Memory/LLM/Tools)
  |   |   |-- Activity Timeline
  |   |   |-- Resource Charts
  |   |-- Settings View
  |   |   |-- LLM Configuration
  |   |   |-- Channel Configuration
  |   |   |-- Identity Configuration
  |   |   |-- System Preferences
  |-- Status Bar (底部状态栏)
```

---

## 3. 页面设计

### 3.1 Chat View (核心视图)

**布局**: 单列全高布局，消息区自动滚动

```
+--------+--------------------------------------------------+
| Sidebar |  [Agent Name]  [Status: Online]     [...]        |
|         |--------------------------------------------------|
|  Chat   |                                                  |
|  Skills |  [AI] Welcome! I'm DeskFlow...                   |
|  Monitor|       How can I help you today?                   |
|  Setup  |                                                  |
|         |  [User] Help me refactor this code:              |
|         |         ```python                                 |
|         |         def foo():...                              |
|         |         ```                                       |
|         |                                                  |
|         |  [AI] I'll analyze the code. Let me:              |
|         |       1. Check structure  [Running...]             |
|         |       2. Find issues                              |
|         |       3. Suggest improvements                     |
|         |                                                  |
|         |       [Tool: analyze_code] [Running...]           |
|         |                                                  |
|         |--------------------------------------------------|
|  [User] |  [Input area]                    [Send] [Stop]   |
| Profile |  [Attach] [Tool Picker]                           |
+--------+--------------------------------------------------+
| Status: Connected | Model: Claude 3.5 | Memory: 1,234     |
+-----------------------------------------------------------+
```

**关键交互**:
- 消息流式输出，逐字显示
- 工具调用显示折叠卡片（可展开查看详情）
- 输入区支持 Shift+Enter 换行，Enter 发送
- Stop 按钮在 AI 回复时显示（红色醒目）
- 代码块有语法高亮和复制按钮

### 3.2 Skills View

**布局**: 顶部筛选栏 + 网格卡片

```
+--------+--------------------------------------------------+
| Sidebar |  Skills            [Search...]  [+ Install]      |
|         |  [All] [System] [User] [Auto-generated]          |
|         |--------------------------------------------------|
|         |  +---------------+  +---------------+            |
|         |  | web_search    |  | file_manager  |            |
|         |  | System Skill  |  | System Skill  |            |
|         |  | [Active]      |  | [Active]      |            |
|         |  +---------------+  +---------------+            |
|         |  +---------------+  +---------------+            |
|         |  | code_review   |  | daily_report  |            |
|         |  | User Skill    |  | Auto-gen      |            |
|         |  | [Inactive]    |  | [Active]      |            |
|         |  +---------------+  +---------------+            |
+--------+--------------------------------------------------+
```

**关键交互**:
- 卡片展示技能名称、类型标签、状态指示
- 点击卡片展开详情侧面板
- 详情面板包含：描述、参数、使用统计、启用/禁用开关
- Install 按钮打开安装对话框（支持 URL / 本地路径）

### 3.3 Monitor View

**布局**: Dashboard 网格，状态卡片 + 图表

```
+--------+--------------------------------------------------+
| Sidebar |  Monitor                      [Refresh] [Export] |
|         |--------------------------------------------------|
|         |  +----------+ +----------+ +----------+ +------+ |
|         |  | Agent    | | Memory   | | LLM      | | Tools| |
|         |  | [Online] | | 1,234    | | Claude   | | 12   | |
|         |  | Idle     | | entries  | | Sonnet   | | avail| |
|         |  +----------+ +----------+ +----------+ +------+ |
|         |                                                  |
|         |  +---------------------------+ +---------------+ |
|         |  | Activity Timeline         | | Resource      | |
|         |  | 14:32 Tool: web_search    | | CPU: 12%      | |
|         |  | 14:31 Memory: stored      | | MEM: 340MB    | |
|         |  | 14:30 LLM: response ok    | | Disk: 1.2GB   | |
|         |  +---------------------------+ +---------------+ |
+--------+--------------------------------------------------+
```

**关键交互**:
- 状态卡片实时更新（WebSocket 推送）
- Activity Timeline 可滚动，支持按类型筛选
- Resource 图表使用 Recharts 渲染折线图
- Export 导出诊断报告

### 3.4 Settings View

**布局**: 左侧分类导航 + 右侧表单

```
+--------+--------------------------------------------------+
| Sidebar |  Settings                                        |
|         |  +-----------+----------------------------------+|
|         |  | LLM       |  LLM Configuration               ||
|         |  | Channels  |                                  ||
|         |  | Identity  |  Provider: [Claude v]             ||
|         |  | System    |  API Key:  [************] [Show]  ||
|         |  |           |  Model:    [claude-3.5-sonnet v]  ||
|         |  |           |  Fallback: [+ Add Fallback]       ||
|         |  |           |                                  ||
|         |  |           |  [Test Connection]  [Save]        ||
|         |  +-----------+----------------------------------+|
+--------+--------------------------------------------------+
```

**关键交互**:
- API Key 默认遮罩，点击 Show 切换
- Test Connection 按钮验证配置
- 保存后 Toast 通知成功/失败
- 支持多 Provider 配置（列表 + 排序）

---

## 4. 交互规范

### 4.1 状态反馈

| 状态 | 视觉表现 | 示例 |
|------|---------|------|
| **空状态** | 居中图标 + 引导文案 | "No conversations yet. Start chatting!" |
| **加载中** | 骨架屏 / Pulse 动画 | 消息加载时的骨架占位 |
| **流式输出** | 绿色光标闪烁 + 逐字渲染 | AI 回复中 |
| **工具执行** | 折叠卡片 + 旋转图标 | "Running: web_search..." |
| **成功** | 绿色 Toast，2 秒自动消失 | "Settings saved" |
| **警告** | 琥珀色 Toast，需手动关闭 | "Memory usage high" |
| **错误** | 红色 Toast + 内联错误信息 | "LLM connection failed" |

### 4.2 键盘快捷键

| 快捷键 | 动作 |
|--------|------|
| `Cmd/Ctrl + N` | 新建对话 |
| `Cmd/Ctrl + /` | 展开/收起侧边栏 |
| `Cmd/Ctrl + K` | 命令面板 (搜索/快捷操作) |
| `Enter` | 发送消息 |
| `Shift + Enter` | 换行 |
| `Escape` | 取消/关闭 |
| `Cmd/Ctrl + .` | 停止 AI 回复 |

### 4.3 命令面板 (Command Palette)

类似 VS Code 的 `Cmd+K` 面板：
- 搜索对话历史
- 快速切换视图
- 执行技能
- 系统命令

---

## 5. 原型说明

### 5.1 HTML 原型范围

本次原型覆盖 MVP 的 4 个核心视图：

| 页面 | 文件 | 交互程度 |
|------|------|---------|
| Chat View | `index.html` (默认) | 高 - 可切换视图 + 模拟消息 |
| Skills View | 同一 SPA | 中 - 静态卡片展示 |
| Monitor View | 同一 SPA | 中 - 静态数据展示 |
| Settings View | 同一 SPA | 低 - 表单布局展示 |

### 5.2 原型技术

- **HTML/CSS/JS** 纯静态原型
- **Tailwind CSS** (CDN) 快速样式
- **Lucide Icons** (CDN) SVG 图标
- **Google Fonts** Fira Code + Fira Sans

---

## 附录: 设计系统引用

完整设计系统定义位于:
- 代码目录: `/Users/seacao/Projects/personal/coolaw-deskflow/design-system/coolaw-deskflow/MASTER.md`
- 文档目录: `/Users/seacao/Documents/cjh_vault/Projects/coolaw-deskflow/design-system/MASTER.md`

---

**文档编制**: Prototype Agent
**审阅状态**: 待用户确认
**下一步**: 用户确认通过后进入阶段 3（任务规划）
