#!/bin/bash

# Coolaw DeskFlow - 自动化测试脚本
# 用途：验证桌面应用和后端的基本功能

# set -e  # 不使用 set -e，让所有测试都能运行

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数器
PASSED=0
FAILED=0
TOTAL=0

# 测试函数
test_case() {
    local name="$1"
    local command="$2"

    TOTAL=$((TOTAL + 1))
    echo -e "\n${YELLOW}[TEST $TOTAL]${NC} $name"

    if eval "$command"; then
        echo -e "${GREEN}✅ PASS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# 测试摘要
print_summary() {
    echo -e "\n========================================="
    echo -e "测试摘要"
    echo -e "=========================================\n"
    echo -e "总计: $TOTAL"
    echo -e "${GREEN}通过: $PASSED${NC}"
    echo -e "${RED}失败: $FAILED${NC}"

    if [ $FAILED -eq 0 ]; then
        echo -e "\n${GREEN}所有测试通过！ 🎉${NC}"
        exit 0
    else
        echo -e "\n${RED}有测试失败，请检查。${NC}"
        exit 1
    fi
}

echo "========================================="
echo "Coolaw DeskFlow - 自动化测试"
echo "========================================="
echo "日期: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# 1. 后端健康检查
test_case "后端服务健康检查" \
    "curl -s -f http://127.0.0.1:8420/api/health | grep -q '\"status\":\"ok\"'"

# 2. Agent 组件状态
test_case "Agent 组件状态正常" \
    "curl -s http://127.0.0.1:8420/api/health | grep -q '\"agent\":{\"status\":\"ok\"'"

# 3. Memory 组件状态
test_case "Memory 组件状态正常" \
    "curl -s http://127.0.0.1:8420/api/health | grep -q '\"memory\":{\"status\":\"ok\"'"

# 4. Tools 组件状态
test_case "Tools 组件状态正常 (3 个工具)" \
    "curl -s http://127.0.0.1:8420/api/health | grep -q '\"tools\":{\"status\":\"ok\",\"details\":{\"count\":3'"

# 5. LLM 组件状态
test_case "LLM 组件状态正常" \
    "curl -s http://127.0.0.1:8420/api/health | grep -q '\"llm\":{\"status\":\"ok\"'"

# 6. WebSocket 端点可用性
test_case "WebSocket 端点可访问" \
    "curl -s -I http://127.0.0.1:8420/api/chat/stream | grep -q '101\|426'"

# 7. 配置 API 可用
test_case "配置 API 可用" \
    "curl -s -f http://127.0.0.1:8420/api/config >/dev/null"

# 8. OpenAPI 文档可用
test_case "OpenAPI 文档可用" \
    "curl -s -f http://127.0.0.1:8420/docs >/dev/null"

# 9. .app 文件存在
test_case ".app 应用文件存在" \
    "[ -d './src-tauri/target/release/bundle/macos/Coolaw DeskFlow.app' ]"

# 10. .app 结构完整
test_case ".app 内部结构完整" \
    "[ -f './src-tauri/target/release/bundle/macos/Coolaw DeskFlow.app/Contents/Info.plist' ] && \
     [ -d './src-tauri/target/release/bundle/macos/Coolaw DeskFlow.app/Contents/MacOS' ] && \
     [ -d './src-tauri/target/release/bundle/macos/Coolaw DeskFlow.app/Contents/Resources' ]"

# 11. 二进制文件可执行
test_case "二进制文件可执行" \
    "[ -x './src-tauri/target/release/coolaw-deskflow' ]"

# 12. 前端资源存在
test_case "前端资源已构建" \
    "[ -f './dist/index.html' ] && [ -d './dist/assets' ]"

# 13. Tauri 配置正确
test_case "Tauri 配置文件正确" \
    "grep -q 'com.coolaw.deskflow' ./src-tauri/tauri.conf.json"

# 14. Python 后端进程运行
test_case "Python 后端进程运行中" \
    "ps aux | grep -v grep | grep -q 'deskflow serve'"

# 15. 数据库文件存在
test_case "SQLite 数据库文件存在" \
    "[ -f './data/db/deskflow.db' ]"

# 16. 响应时间测试
test_case "API 响应时间 < 200ms" \
    "time_ms=\$(curl -s -w '%{time_total}' -o /dev/null http://127.0.0.1:8420/api/health); \
     [ \$(echo \"\$time_ms < 0.2\" | bc) -eq 1 ]"

# 17. 并发请求处理
test_case "并发请求处理 (5 个)" \
    "for i in {1..5}; do curl -s http://127.0.0.1:8420/api/health & done; wait; [ \$? -eq 0 ]"

# 18. CORS 头部检查
test_case "CORS 头部正确设置" \
    "curl -s -I http://127.0.0.1:8420/api/health | grep -q 'access-control-allow-origin'"

# 打印测试摘要
print_summary
