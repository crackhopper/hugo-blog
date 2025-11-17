#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预处理脚本：将 Obsidian 图片语法 ![[filename.png]] 转换为标准 Markdown 图片语法
在 Hugo 处理之前运行，不修改原始文件，而是创建临时副本
支持增量更新：只更新修改过的文件
"""
import os
import re
import shutil
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime

def get_file_hash(file_path):
    """计算文件的 MD5 哈希值"""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def transform_obsidian_images(content, static_images_dir=None):
    """将 Obsidian 图片语法转换为标准 Markdown 图片语法或 HTML img 标签"""
    # 匹配 Obsidian 图片语法: ![[filename.png]] 或 ![[filename.png|296]]
    pattern = r'!\[\[([^\]]+)\]\]'
    
    # 如果提供了 static_images_dir，用于验证图片是否存在
    project_root = Path.cwd()
    if static_images_dir is None:
        static_images_dir = project_root / 'static' / 'images'
    else:
        static_images_dir = Path(static_images_dir)
    
    missing_images = []
    
    def replace_func(match):
        full_match = match.group(1).strip()
        
        # 检查是否包含宽度参数（用 | 分隔）
        if '|' in full_match:
            parts = full_match.split('|', 1)
            filename = parts[0].strip()
            width = parts[1].strip()
        else:
            filename = full_match
        
        # 验证图片文件是否存在
        image_path = static_images_dir / filename
        if not image_path.exists():
            missing_images.append(filename)
        
        # 使用文件名（不含扩展名）作为 alt text
        alt_text = Path(filename).stem
        
        # 检查是否包含宽度参数（用 | 分隔）
        if '|' in full_match:
            # 转换为 HTML img 标签，包含 width 属性（Hugo 需要启用 unsafe = true）
            return f'<img src="/images/{filename}" alt="{alt_text}" width="{width}" loading="lazy" />'
        else:
            # 转换为标准 Markdown 图片语法，路径指向 /images/ 目录
            return f"![{alt_text}](/images/{filename})"
    
    result = re.sub(pattern, replace_func, content)
    
    # 如果有缺失的图片，输出警告
    if missing_images:
        print(f"警告: 以下图片文件不存在于 {static_images_dir}:")
        for img in missing_images:
            print(f"  - {img}")
        print("提示: 请确保图片文件已复制到 static/images/ 目录")
    
    return result

def preprocess_content_dir(content_dir='content', temp_dir='.hugo_temp_content', force=False):
    """
    预处理 content 目录，将 Obsidian 图片语法转换为标准 Markdown
    创建临时目录，不修改原始文件
    支持增量更新：只更新修改过的文件
    """
    content_path = Path(content_dir)
    temp_path = Path(temp_dir)
    state_file = temp_path / '.preprocess_state.json'
    
    if not content_path.exists():
        print(f"内容目录不存在: {content_path}")
        return None
    
    # 加载状态文件（记录已处理的文件及其哈希）
    state = {}
    if state_file.exists() and not force:
        try:
            import json
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except:
            state = {}
    
    # 如果强制更新或临时目录不存在，清理并重建
    if force or not temp_path.exists():
        if temp_path.exists():
            shutil.rmtree(temp_path)
        temp_path.mkdir(parents=True, exist_ok=True)
        state = {}
    
    # 确保临时目录存在
    temp_path.mkdir(parents=True, exist_ok=True)
    
    # 获取所有 Markdown 文件
    md_files = list(content_path.rglob('*.md'))
    updated_count = 0
    skipped_count = 0
    
    for md_file in md_files:
        # 计算相对路径
        rel_path = md_file.relative_to(content_path)
        temp_file = temp_path / rel_path
        
        # 创建目录
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 检查文件是否需要更新（增量处理）
        file_str = str(rel_path)
        current_hash = get_file_hash(md_file)
        saved_hash = state.get(file_str)
        
        # 如果文件未修改且已存在临时文件，跳过
        if saved_hash == current_hash and temp_file.exists() and not force:
            skipped_count += 1
            continue
        
        # 读取并转换内容
        content = md_file.read_text(encoding='utf-8')
        # 传递 static/images 目录路径用于验证图片是否存在
        static_images_dir = Path.cwd() / 'static' / 'images'
        transformed = transform_obsidian_images(content, static_images_dir=static_images_dir)
        
        # 写入临时文件
        temp_file.write_text(transformed, encoding='utf-8')
        
        # 更新状态
        state[file_str] = current_hash
        updated_count += 1
    
    # 清理已删除的文件（从状态中移除不存在的文件）
    existing_files = {str(f.relative_to(content_path)) for f in md_files}
    state = {k: v for k, v in state.items() if k in existing_files}
    
    # 保存状态
    if state_file.parent.exists():
        import json
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    print(f"预处理完成: {len(md_files)} 个文件（更新: {updated_count}, 跳过: {skipped_count}）")
    return str(temp_path)

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='预处理 Obsidian 图片语法')
    parser.add_argument('--force', '-f', action='store_true',
                       help='强制重新处理所有文件（忽略增量更新）')
    
    args = parser.parse_args()
    
    temp_dir = preprocess_content_dir(force=args.force)
    if temp_dir:
        print(f"临时目录: {temp_dir}")
        print("提示: 使用 'hugo --contentDir {temp_dir}' 来使用预处理后的内容")

