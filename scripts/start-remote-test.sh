#!/bin/bash
# Coolaw DeskFlow - 远程测试快速启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$HOME/Projects/personal/coolaw-deskflow"

echo -e "${BLUE}=== Coolaw DeskFlow 远程测试启动 ===${NC}\n"

# 1. 检查项目目录
if [ ! -d "$PROJECT_ROOT" ]; then
    echo -e "${RED}❌ 项目目录不存在: $PROJECT_ROOT${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"
echo -e "${GREEN}✓${NC} 项目目录: $PROJECT_ROOT"

# 2. 检查并配置 .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠${NC}  .env 文件不存在，从 .env.remote 复制..."
    cp .env.remote .env
    echo -e "${YELLOW}⚠${NC}  请编辑 .env 文件，填入 API Key"
    echo -e "   运行: ${BLUE}nano .env${NC}"
    exit 1
fi

# 检查 API Key
if grep -q "your-key-here" .env; then
    echo -e "${RED}❌ 请先在 .env 文件中配置 API Key${NC}"
    echo -e "   运行: ${BLUE}nano .env${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} .env 配置已存在"

# 3. 检查 DESKFLOW_HOST 配置
HOST=$(grep "^DESKFLOW_HOST=" .env | cut -d'=' -f2)
if [ "$HOST" != "0.0.0.0" ]; then
    echo -e "${RED}❌ DESKFLOW_HOST 必须设置为 0.0.0.0 才能远程访问${NC}"
    echo -e "   当前值: $HOST"
    exit 1
fi

echo -e "${GREEN}✓${NC} DESKFLOW_HOST 配置正确: $HOST"

# 4. 检查 deskflow 是否已安装
if ! command -v deskflow &> /dev/null; then
    echo -e "${YELLOW}⚠${NC}  deskflow 命令不存在，正在安装..."
    pip install -e ".[dev]"
fi

echo -e "${GREEN}✓${NC} deskflow 已安装"

# 5. 检查端口是否被占用
PORT=8420
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠${NC}  端口 $PORT 已被占用"
    PID=$(lsof -Pi :$PORT -sTCP:LISTEN -t)
    echo -e "   进程 PID: $PID"
    read -p "是否停止现有进程并重启? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill $PID
        sleep 2
    else
        echo -e "${RED}❌ 取消启动${NC}"
        exit 1
    fi
fi

# 6. 创建数据目录
mkdir -p data/db
echo -e "${GREEN}✓${NC} 数据目录已创建"

# 7. 启动后端服务
echo -e "\n${BLUE}>>> 启动后端服务...${NC}"
echo -e "    监听地址: 0.0.0.0:$PORT"
echo -e "    访问地址: http://10.8.0.22:$PORT\n"

# 创建日志文件
LOG_FILE="$PROJECT_ROOT/deskflow.log"
touch "$LOG_FILE"

# 启动服务
nohup deskflow serve > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# 等待服务启动
echo -e "等待服务启动..."
sleep 3

# 验证服务状态
if ps -p $SERVER_PID > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} 服务启动成功 (PID: $SERVER_PID)"
else
    echo -e "${RED}❌ 服务启动失败${NC}"
    echo -e "日志内容:"
    tail -20 "$LOG_FILE"
    exit 1
fi

# 8. 测试本地连接
echo -e "\n${BLUE}>>> 测试本地连接...${NC}"
sleep 2
if curl -s http://127.0.0.1:$PORT/health > /dev/null; then
    echo -e "${GREEN}✓${NC} 本地连接测试通过"
else
    echo -e "${RED}❌ 本地连接失败${NC}"
    tail -20 "$LOG_FILE"
    exit 1
fi

# 9. 测试远程连接
echo -e "\n${BLUE}>>> 测试远程连接...${NC}"
if curl -s http://10.8.0.22:$PORT/health > /dev/null; then
    echo -e "${GREEN}✓${NC} 远程连接测试通过"
else
    echo -e "${YELLOW}⚠${NC}  远程连接失败（可能被防火墙阻止）"
    echo -e "   请检查防火墙设置或在测试电脑上执行:"
    echo -e "   ${BLUE}curl http://10.8.0.22:$PORT/health${NC}"
fi

# 10. 显示状态
echo -e "\n${GREEN}=== 启动成功 ===${NC}\n"
echo -e "📊 服务状态:"
echo -e "   PID: $SERVER_PID"
echo -e "   日志: $LOG_FILE"
echo -e "   本地地址: ${BLUE}http://127.0.0.1:$PORT${NC}"
echo -e "   远程地址: ${BLUE}http://10.8.0.22:$PORT${NC}"
echo -e "   健康检查: ${BLUE}http://10.8.0.22:$PORT/health${NC}"
echo -e "   API 文档: ${BLUE}http://10.8.0.22:$PORT/docs${NC}"

echo -e "\n📝 查看日志:"
echo -e "   ${BLUE}tail -f $LOG_FILE${NC}"

echo -e "\n🛑 停止服务:"
echo -e "   ${BLUE}kill $SERVER_PID${NC}"
echo -e "   ${BLUE}或: pkill -f 'deskflow serve'${NC}"

echo -e "\n📱 下一步:"
echo -e "   1. 在测试电脑上验证连接:"
echo -e "      ${BLUE}curl http://10.8.0.22:$PORT/health${NC}"
echo -e "   2. 构建桌面应用:"
echo -e "      ${BLUE}cd $PROJECT_ROOT/apps/desktop && npm run build${NC}"
echo -e "   3. 传输应用到测试电脑并测试"

echo -e "\n${GREEN}====================${NC}\n"
