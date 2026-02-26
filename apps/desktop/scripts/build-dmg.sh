#!/bin/bash

# Coolaw DeskFlow DMG Build Script
# 用于构建 macOS DMG 安装包

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_TAURI_DIR="$PROJECT_DIR/src-tauri"

echo "=========================================="
echo "  Coolaw DeskFlow DMG Build Script"
echo "=========================================="
echo ""

# 检查是否安装了 Tauri CLI
if ! command -v cargo &> /dev/null; then
    echo "错误：未找到 cargo，请先安装 Rust"
    exit 1
fi

# 检查是否安装了 Node.js
if ! command -v node &> /dev/null; then
    echo "错误：未找到 node，请先安装 Node.js"
    exit 1
fi

# 进入项目目录
cd "$PROJECT_DIR"

# 安装前端依赖
echo "[1/4] 安装前端依赖..."
npm install

# 构建前端
echo "[2/4] 构建前端..."
npm run build:web

# 构建 Tauri 应用
echo "[3/4] 构建 Tauri 应用..."
cd "$SRC_TAURI_DIR"
cargo build --release

# 构建 DMG
echo "[4/4] 创建 DMG 文件..."

# 定义路径
APP_NAME="Coolaw DeskFlow"
BUILD_DIR="$SRC_TAURI_DIR/target/release"
APP_BUNDLE="$BUILD_DIR/${APP_NAME}.app"
DMG_DIR="$BUILD_DIR/dmg"
DMG_TEMPLATE="$DMG_DIR/dmg_template"
DMG_FINAL="$BUILD_DIR/${APP_NAME}-v$(cat "$PROJECT_DIR/package.json" | grep version | head -1 | awk -F: '{ print $2 }' | sed 's/[",]//g' | tr -d ' ').dmg"

# 清理旧的 DMG 文件
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR"
mkdir -p "$DMG_TEMPLATE"

# 复制应用到模板目录
cp -r "$APP_BUNDLE" "$DMG_TEMPLATE/"

# 创建 Applications 快捷方式
ln -s /Applications "$DMG_TEMPLATE/Applications"

# 创建 DMG
hdiutil create -volname "Coolaw DeskFlow" -srcfolder "$DMG_TEMPLATE" -ov -format UDZO "$DMG_FINAL"

echo ""
echo "=========================================="
echo "  构建完成!"
echo "=========================================="
echo ""
echo "DMG 文件位置：$DMG_FINAL"
echo ""

# 清理临时文件
rm -rf "$DMG_TEMPLATE"

echo "提示：可以使用以下命令测试 DMG:"
echo "  hdiutil attach \"$DMG_FINAL\""
echo ""
