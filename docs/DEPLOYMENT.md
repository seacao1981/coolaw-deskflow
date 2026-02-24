# Coolaw DeskFlow - 部署指南

**版本**: v0.1.0
**最后更新**: 2026-02-24

---

## 📋 目录

1. [系统要求](#系统要求)
2. [快速安装](#快速安装)
3. [配置说明](#配置说明)
4. [运行服务](#运行服务)
5. [桌面应用](#桌面应用)
6. [故障排除](#故障排除)

---

## 系统要求

### 最低要求

| 组件 | 要求 |
|------|------|
| **操作系统** | macOS 12+ / Windows 10+ / Linux (Ubuntu 20.04+) |
| **Python** | 3.11+ |
| **内存** | 4GB RAM |
| **磁盘** | 500MB 可用空间 |

### 推荐配置

| 组件 | 要求 |
|------|------|
| **操作系统** | macOS 14+ / Windows 11+ / Ubuntu 22.04+ |
| **Python** | 3.12+ |
| **内存** | 8GB RAM |
| **磁盘** | 1GB SSD 可用空间 |

---

## 快速安装

### 方式 1: 源码安装 (推荐)

```bash
# 1. 克隆仓库
git clone https://github.com/coolaw/coolaw-deskflow.git
cd coolaw-deskflow

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 初始化配置
deskflow init

# 5. 验证安装
deskflow --help
```

### 方式 2: pip 安装

```bash
# 直接从 PyPI 安装 (如果已发布)
pip install coolaw-deskflow

# 或从 GitHub 安装
pip install git+https://github.com/coolaw/coolaw-deskflow.git

# 初始化配置
deskflow init
```

### 方式 3: Docker 安装 (可选)

```bash
# 构建镜像
docker build -t coolaw-deskflow .

# 运行容器
docker run -d \
  -p 8420:8420 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  coolaw-deskflow
```

---

## 配置说明

### 环境变量

运行 `deskflow init` 会创建 `.env` 文件，或手动创建：

```bash
# 复制示例文件
cp .env.example .env

# 编辑 .env 文件
nano .env
```

### 必需配置

```bash
# LLM 提供商选择 (三选一)

# 选项 1: Anthropic Claude (推荐)
DESKFLOW_LLM_PROVIDER=anthropic
DESKFLOW_ANTHROPIC_API_KEY=sk-ant-xxxxx

# 选项 2: OpenAI 兼容 API
DESKFLOW_LLM_PROVIDER=openai
DESKFLOW_OPENAI_API_KEY=sk-xxxxx
DESKFLOW_OPENAI_BASE_URL=https://api.openai.com/v1

# 选项 3: DashScope (阿里通义千问)
DESKFLOW_LLM_PROVIDER=dashscope
DESKFLOW_DASHSCOPE_API_KEY=sk-xxxxx
DESKFLOW_DASHSCOPE_MODEL=qwen-max
```

### 可选配置

```bash
# 服务器设置
DESKFLOW_HOST=127.0.0.1
DESKFLOW_PORT=8420
DESKFLOW_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# 记忆系统
DESKFLOW_DB_PATH=data/db/deskflow.db
DESKFLOW_MEMORY_CACHE_SIZE=1000  # L1 缓存大小

# 工具设置
DESKFLOW_TOOL_TIMEOUT=30.0  # 工具执行超时 (秒)
DESKFLOW_TOOL_MAX_PARALLEL=3  # 最大并行工具数
DESKFLOW_ALLOWED_PATHS=~/Projects,~/Documents  # 文件访问白名单

# 应用设置
DESKFLOW_ENV=dev  # dev, prod, test
```

---

## 运行服务

### 启动 API 服务器

```bash
# 方式 1: 使用 CLI
deskflow serve

# 方式 2: 直接运行
python -m deskflow serve

# 后台运行
deskflow serve &

# 守护进程模式 (Linux/macOS)
nohup deskflow serve > deskflow.log 2>&1 &
```

### 验证服务

```bash
# 健康检查
curl http://127.0.0.1:8420/api/health

# 查看状态
curl http://127.0.0.1:8420/api/status

# 查看配置
curl http://127.0.0.1:8420/api/config
```

### 停止服务

```bash
# 找到进程 ID
ps aux | grep deskflow

# 停止进程
kill <PID>

# 强制停止
kill -9 <PID>
```

---

## 桌面应用

### macOS

```bash
# 方式 1: 使用预构建应用
# 下载 .dmg 文件并拖拽到 Applications

# 方式 2: 从源码构建
cd apps/desktop
npm install
npm run build

# 应用位置
open src-tauri/target/release/bundle/macos/Coolaw\ DeskFlow.app
```

### Windows

```bash
# 下载 .exe 安装程序
# 运行安装向导
# 从开始菜单启动
```

### Linux

```bash
# Debian/Ubuntu
sudo dpkg -i coolaw-deskflow_0.1.0_amd64.deb

# Arch Linux
yay -S coolaw-deskflow

# AppImage (通用)
chmod +x coolaw-deskflow.AppImage
./coolaw-deskflow.AppImage
```

---

## 故障排除

### 常见问题

#### 1. 无法启动服务

**症状**: `Error: Address already in use`

**解决方案**:
```bash
# 检查端口占用
lsof -i :8420

# 停止占用进程
kill <PID>

# 或更改端口
export DESKFLOW_PORT=8421
deskflow serve
```

#### 2. LLM API 连接失败

**症状**: `LLMConnectionError: Failed to connect to API`

**解决方案**:
```bash
# 检查 API Key 是否正确
cat .env | grep API_KEY

# 测试 API 连接
curl -H "Authorization: Bearer $DESKFLOW_ANTHROPIC_API_KEY" \
     https://api.anthropic.com/v1/models

# 检查网络/代理设置
export HTTPS_PROXY=http://127.0.0.1:7890  # 如果需要代理
```

#### 3. 记忆数据库错误

**症状**: `MemoryStorageError: Database locked`

**解决方案**:
```bash
# 停止所有 deskflow 进程
pkill -f deskflow

# 删除数据库锁文件
rm data/db/deskflow.db-journal

# 重启服务
deskflow serve
```

#### 4. 工具执行超时

**症状**: `ToolTimeoutError: Tool execution timed out`

**解决方案**:
```bash
# 增加超时时间
export DESKFLOW_TOOL_TIMEOUT=60

# 或限制工具输出
# 对于 Shell 工具，使用管道限制输出
ls | head -100
```

#### 5. 桌面应用无法连接后端

**症状**: `Connection refused` 或 `Backend not responding`

**解决方案**:
```bash
# 确保后端服务正在运行
deskflow serve

# 检查后端地址
# 桌面应用默认连接 http://127.0.0.1:8420

# 查看后端日志
tail -f deskflow.log
```

### 日志查看

```bash
# 查看实时日志
tail -f deskflow.log

# 查看错误日志
grep ERROR deskflow.log | tail -20

# 清理日志
> deskflow.log
```

### 获取帮助

```bash
# CLI 帮助
deskflow --help
deskflow <command> --help

# 查看版
deskflow --version

# 查看配置
deskflow config show
```

### 报告问题

如遇无法解决的问题，请收集以下信息并提交 Issue：

```bash
# 系统信息
uname -a
python3 --version
deskflow --version

# 配置信息 (隐藏敏感数据)
deskflow config list

# 错误日志
tail -100 deskflow.log
```

---

## 升级指南

### 升级源码版本

```bash
# 拉取最新代码
git pull origin main

# 更新依赖
pip install -e ".[dev]" --upgrade

# 重启服务
pkill -f deskflow
deskflow serve
```

### 升级桌面应用

```bash
# macOS: 覆盖安装新版本
# Windows: 运行新版本安装程序
# Linux: 重新安装包
```

---

## 卸载指南

### 卸载 Python 包

```bash
pip uninstall coolaw-deskflow
```

### 卸载桌面应用

```bash
# macOS: 拖拽到废纸篓
rm -rf /Applications/Coolaw\ DeskFlow.app

# Windows: 控制面板卸载
# Linux: 包管理器卸载
```

### 清理数据 (可选)

```bash
# 删除所有数据
rm -rf ~/.deskflow
rm -rf coolaw-deskflow/data
```

---

**编制**: DevOps Team
**许可**: MIT License
