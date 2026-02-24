#!/bin/bash
# Coolaw DeskFlow - 远程测试桌面应用构建脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
DESKTOP_DIR="$HOME/Projects/personal/coolaw-deskflow/apps/desktop"
BACKEND_URL="http://10.8.0.22:8420"

echo -e "${BLUE}=== Coolaw DeskFlow 桌面应用构建 ===${NC}\n"

# 1. 检查目录
if [ ! -d "$DESKTOP_DIR" ]; then
    echo -e "${RED}❌ 目录不存在: $DESKTOP_DIR${NC}"
    exit 1
fi

cd "$DESKTOP_DIR"
echo -e "${GREEN}✓${NC} 工作目录: $DESKTOP_DIR"

# 2. 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js 未安装${NC}"
    exit 1
fi

NODE_VERSION=$(node --version)
echo -e "${GREEN}✓${NC} Node.js 版本: $NODE_VERSION"

# 3. 检查 Rust
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}❌ Rust 未安装${NC}"
    echo -e "   请访问: https://rustup.rs/"
    exit 1
fi

RUST_VERSION=$(rustc --version)
echo -e "${GREEN}✓${NC} Rust 版本: $RUST_VERSION"

# 4. 配置环境变量
echo -e "\n${BLUE}>>> 配置环境变量...${NC}"
cat > .env.production << EOF
VITE_BACKEND_URL=$BACKEND_URL
EOF

echo -e "${GREEN}✓${NC} 后端地址: $BACKEND_URL"

# 5. 安装依赖
if [ ! -d "node_modules" ]; then
    echo -e "\n${BLUE}>>> 安装 Node 依赖...${NC}"
    npm install
    echo -e "${GREEN}✓${NC} Node 依赖安装完成"
else
    echo -e "${GREEN}✓${NC} Node 依赖已安装"
fi

# 6. 清理旧构建
echo -e "\n${BLUE}>>> 清理旧构建...${NC}"
rm -rf dist src-tauri/target/release/bundle
echo -e "${GREEN}✓${NC} 清理完成"

# 7. 构建应用
echo -e "\n${BLUE}>>> 开始构建桌面应用...${NC}"
echo -e "   这可能需要几分钟时间...\n"

if npm run build; then
    echo -e "\n${GREEN}✓${NC} 构建成功"
else
    echo -e "\n${RED}❌ 构建失败${NC}"
    exit 1
fi

# 8. 查找构建产物
echo -e "\n${BLUE}>>> 构建产物:${NC}\n"

BUNDLE_DIR="src-tauri/target/release/bundle"

# macOS
if [ -d "$BUNDLE_DIR/macos" ]; then
    APP_PATH=$(find "$BUNDLE_DIR/macos" -name "*.app" -type d | head -n 1)
    if [ -n "$APP_PATH" ]; then
        APP_SIZE=$(du -sh "$APP_PATH" | cut -f1)
        echo -e "   macOS App: ${GREEN}$APP_PATH${NC}"
        echo -e "   大小: $APP_SIZE"
    fi
fi

if [ -d "$BUNDLE_DIR/dmg" ]; then
    DMG_PATH=$(find "$BUNDLE_DIR/dmg" -name "*.dmg" | head -n 1)
    if [ -n "$DMG_PATH" ]; then
        DMG_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
        echo -e "   DMG: ${GREEN}$DMG_PATH${NC}"
        echo -e "   大小: $DMG_SIZE"
    fi
fi

# Windows
if [ -d "$BUNDLE_DIR/msi" ]; then
    MSI_PATH=$(find "$BUNDLE_DIR/msi" -name "*.msi" | head -n 1)
    if [ -n "$MSI_PATH" ]; then
        MSI_SIZE=$(du -sh "$MSI_PATH" | cut -f1)
        echo -e "   Windows MSI: ${GREEN}$MSI_PATH${NC}"
        echo -e "   大小: $MSI_SIZE"
    fi
fi

# Linux
if [ -d "$BUNDLE_DIR/deb" ]; then
    DEB_PATH=$(find "$BUNDLE_DIR/deb" -name "*.deb" | head -n 1)
    if [ -n "$DEB_PATH" ]; then
        DEB_SIZE=$(du -sh "$DEB_PATH" | cut -f1)
        echo -e "   Linux DEB: ${GREEN}$DEB_PATH${NC}"
        echo -e "   大小: $DEB_SIZE"
    fi
fi

if [ -d "$BUNDLE_DIR/appimage" ]; then
    APPIMAGE_PATH=$(find "$BUNDLE_DIR/appimage" -name "*.AppImage" | head -n 1)
    if [ -n "$APPIMAGE_PATH" ]; then
        APPIMAGE_SIZE=$(du -sh "$APPIMAGE_PATH" | cut -f1)
        echo -e "   Linux AppImage: ${GREEN}$APPIMAGE_PATH${NC}"
        echo -e "   大小: $APPIMAGE_SIZE"
    fi
fi

# 9. 创建打包脚本
echo -e "\n${BLUE}>>> 创建传输包...${NC}"

OUTPUT_DIR="$HOME/coolaw-deskflow-dist"
mkdir -p "$OUTPUT_DIR"

# macOS
if [ -n "$APP_PATH" ]; then
    echo -e "   正在打包 macOS 应用..."
    cd "$BUNDLE_DIR/macos"
    ZIP_FILE="$OUTPUT_DIR/coolaw-deskflow-macos-$(date +%Y%m%d).zip"
    zip -rq "$ZIP_FILE" "$(basename "$APP_PATH")"
    ZIP_SIZE=$(du -sh "$ZIP_FILE" | cut -f1)
    echo -e "   ${GREEN}✓${NC} macOS ZIP: $ZIP_FILE ($ZIP_SIZE)"
    cd "$DESKTOP_DIR"
fi

# DMG
if [ -n "$DMG_PATH" ]; then
    cp "$DMG_PATH" "$OUTPUT_DIR/"
    DMG_FILE="$OUTPUT_DIR/$(basename "$DMG_PATH")"
    DMG_SIZE=$(du -sh "$DMG_FILE" | cut -f1)
    echo -e "   ${GREEN}✓${NC} macOS DMG: $DMG_FILE ($DMG_SIZE)"
fi

# Windows
if [ -n "$MSI_PATH" ]; then
    cp "$MSI_PATH" "$OUTPUT_DIR/"
    MSI_FILE="$OUTPUT_DIR/$(basename "$MSI_PATH")"
    MSI_SIZE=$(du -sh "$MSI_FILE" | cut -f1)
    echo -e "   ${GREEN}✓${NC} Windows MSI: $MSI_FILE ($MSI_SIZE)"
fi

# Linux
if [ -n "$DEB_PATH" ]; then
    cp "$DEB_PATH" "$OUTPUT_DIR/"
    DEB_FILE="$OUTPUT_DIR/$(basename "$DEB_PATH")"
    DEB_SIZE=$(du -sh "$DEB_FILE" | cut -f1)
    echo -e "   ${GREEN}✓${NC} Linux DEB: $DEB_FILE ($DEB_SIZE)"
fi

if [ -n "$APPIMAGE_PATH" ]; then
    cp "$APPIMAGE_PATH" "$OUTPUT_DIR/"
    APPIMAGE_FILE="$OUTPUT_DIR/$(basename "$APPIMAGE_PATH")"
    APPIMAGE_SIZE=$(du -sh "$APPIMAGE_FILE" | cut -f1)
    echo -e "   ${GREEN}✓${NC} Linux AppImage: $APPIMAGE_FILE ($APPIMAGE_SIZE)"
fi

# 10. 生成传输指令
echo -e "\n${GREEN}=== 构建完成 ===${NC}\n"
echo -e "📦 传输包位置: ${BLUE}$OUTPUT_DIR${NC}\n"

echo -e "📝 传输到测试电脑的方法:\n"

if [ -n "$ZIP_FILE" ]; then
    echo -e "   方法 1 (SCP):"
    echo -e "   ${BLUE}scp $ZIP_FILE user@testpc:~/Downloads/${NC}\n"
fi

if [ -n "$DMG_FILE" ]; then
    echo -e "   方法 2 (DMG):"
    echo -e "   ${BLUE}scp $DMG_FILE user@testpc:~/Downloads/${NC}\n"
fi

echo -e "   方法 3 (HTTP 服务器):"
echo -e "   ${BLUE}cd $OUTPUT_DIR && python3 -m http.server 8000${NC}"
echo -e "   然后在测试电脑浏览器访问: ${BLUE}http://10.8.0.22:8000${NC}\n"

echo -e "🧪 在测试电脑上安装后:"
echo -e "   1. 验证后端连接: ${BLUE}curl http://10.8.0.22:8420/health${NC}"
echo -e "   2. 启动应用测试功能"
echo -e "   3. 参考测试指南: ${BLUE}vault/Projects/coolaw-deskflow/08-远程测试指南/${NC}\n"

echo -e "${GREEN}====================${NC}\n"
