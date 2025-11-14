#!/bin/bash
# Hugo 构建脚本（Linux/macOS）
# 自动预处理 Obsidian 图片链接并构建 Hugo 站点
# 使用预处理方式，不修改原始文件，保持 Obsidian 兼容

set -e

SERVER=false
DRAFT=false
NO_PREPROCESS=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --server|-s)
            SERVER=true
            shift
            ;;
        --draft|-D)
            DRAFT=true
            shift
            ;;
        --no-preprocess)
            NO_PREPROCESS=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

echo "=== Hugo 博客构建脚本 ==="

# 1. 预处理 Obsidian 图片链接（创建临时副本，不修改原始文件）
CONTENT_DIR="content"
if [ "$NO_PREPROCESS" = false ]; then
    echo ""
    echo "[1/2] 预处理 Obsidian 图片链接..."
    # 开发服务器模式：每次启动时强制更新，确保最新内容
    if [ "$SERVER" = true ]; then
        python3 scripts/preprocess_obsidian.py --force
    else
        python3 scripts/preprocess_obsidian.py
    fi
    if [ $? -eq 0 ]; then
        CONTENT_DIR=".hugo_temp_content"
        echo "✓ 预处理完成（使用临时内容目录）"
    else
        echo "警告: 预处理失败，使用原始内容目录..."
        CONTENT_DIR="content"
    fi
else
    echo ""
    echo "[1/2] 跳过预处理，使用原始内容目录"
fi

# 2. 构建或启动 Hugo
if [ "$SERVER" = true ]; then
    echo ""
    echo "[2/2] 启动 Hugo 开发服务器..."
    if [ "$DRAFT" = true ]; then
        hugo server -D --contentDir "$CONTENT_DIR"
    else
        hugo server --contentDir "$CONTENT_DIR"
    fi
else
    echo ""
    echo "[2/2] 构建 Hugo 站点..."
    hugo --minify --contentDir "$CONTENT_DIR"
    
    if [ $? -eq 0 ]; then
        echo "✓ 构建完成！输出目录: public/"
    else
        echo "✗ 构建失败"
        exit 1
    fi
fi

