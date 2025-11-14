#!/bin/bash
# 刷新预处理内容（Linux/macOS）
# 在开发时，如果修改了原始文件，运行此脚本更新临时目录

echo "刷新预处理内容..."
python3 scripts/preprocess_obsidian.py
if [ $? -eq 0 ]; then
    echo "✓ 内容已更新"
else
    echo "✗ 更新失败"
    exit 1
fi

