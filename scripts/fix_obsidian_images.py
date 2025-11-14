#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 Obsidian 格式的图片链接，转换为 Hugo 可用的格式
将 ![[filename.png]] 转换为 ![alt text](/images/filename.png)

支持增量处理：只处理新文件或修改过的文件，提高效率
"""
import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime

# 状态文件路径
STATE_FILE = Path('.obsidian_images_state.json')

def get_file_hash(file_path):
    """计算文件的 MD5 哈希值"""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def load_state():
    """加载处理状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_state(state):
    """保存处理状态"""
    state['last_processed'] = datetime.now().isoformat()
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def find_image_in_static(filename, static_dir='static/images'):
    """
    在 static 目录中查找图片文件
    返回相对于网站根目录的路径（如 /images/filename.png）
    """
    static_path = Path(static_dir)
    
    if not static_path.exists():
        return None
    
    # 直接查找
    direct_path = static_path / filename
    if direct_path.exists():
        return f"/images/{filename}"
    
    # 递归查找
    for img_file in static_path.rglob(filename):
        # 计算相对路径
        rel_path = img_file.relative_to(static_path)
        return f"/images/{rel_path.as_posix()}"
    
    return None

def convert_obsidian_image_link(match, static_dir='static/images'):
    """
    将 Obsidian 格式的图片链接转换为标准 Markdown 格式
    ![[filename.png]] -> ![filename](/images/filename.png)
    """
    full_match = match.group(0)
    filename = match.group(1)
    
    # 查找图片文件
    image_path = find_image_in_static(filename, static_dir)
    
    if image_path:
        # 使用文件名（不含扩展名）作为 alt text
        alt_text = Path(filename).stem
        return f"![{alt_text}]({image_path})"
    else:
        # 如果找不到文件，保留原格式但添加警告注释
        return f"<!-- 图片未找到: {filename} -->\n{full_match}"

def fix_obsidian_images_in_file(file_path, static_dir='static/images', verbose=True):
    """
    修复单个文件中的 Obsidian 图片链接
    返回: (是否修复成功, 文件哈希值)
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        if verbose:
            print(f"文件不存在: {file_path}")
        return False, None
    
    content = file_path.read_text(encoding='utf-8')
    file_hash = get_file_hash(file_path)
    
    # 匹配 Obsidian 格式的图片链接: ![[filename]]
    pattern = r'!\[\[([^\]]+)\]\]'
    
    # 先检查是否有匹配
    matches = list(re.finditer(pattern, content))
    if not matches:
        return False, file_hash
    
    if verbose:
        print(f"找到 {len(matches)} 个 Obsidian 图片链接，开始转换...")
    
    def replace_func(match):
        result = convert_obsidian_image_link(match, static_dir)
        if verbose:
            print(f"  转换: {match.group(0)} -> {result[:50]}...")
        return result
    
    new_content = re.sub(pattern, replace_func, content)
    
    if content != new_content:
        file_path.write_text(new_content, encoding='utf-8')
        if verbose:
            print(f"已修复: {file_path}")
        # 重新计算哈希（因为文件已修改）
        file_hash = get_file_hash(file_path)
        return True, file_hash
    else:
        if verbose:
            print(f"警告: 内容未改变: {file_path}")
        return False, file_hash

def fix_all_obsidian_images(content_dir='content', static_dir='static/images', 
                           incremental=True, force=False, verbose=True):
    """
    修复指定目录下所有 Markdown 文件中的 Obsidian 图片链接
    
    参数:
        content_dir: 内容目录
        static_dir: 静态资源目录
        incremental: 是否使用增量处理（只处理新文件或修改过的文件）
        force: 强制处理所有文件（忽略状态文件）
        verbose: 是否显示详细信息
    """
    content_path = Path(content_dir)
    
    if not content_path.exists():
        if verbose:
            print(f"目录不存在: {content_path}")
        return
    
    # 加载状态
    state = {} if force else load_state()
    files_state = state.get('files', {})
    
    md_files = list(content_path.rglob('*.md'))
    
    if not md_files:
        if verbose:
            print(f"未找到 Markdown 文件: {content_path}")
        return
    
    if verbose:
        print(f"找到 {len(md_files)} 个 Markdown 文件")
        if incremental and not force:
            print("使用增量处理模式（只处理新文件或修改过的文件）")
        print("开始修复 Obsidian 图片链接...\n")
    
    fixed_count = 0
    processed_count = 0
    skipped_count = 0
    
    for md_file in md_files:
        file_str = str(md_file)
        
        # 增量处理：检查文件是否需要处理
        if incremental and not force:
            current_hash = get_file_hash(md_file)
            saved_hash = files_state.get(file_str)
            
            # 如果文件哈希未改变，且之前已处理过，跳过
            if saved_hash == current_hash:
                skipped_count += 1
                continue
        
        # 处理文件
        processed_count += 1
        fixed, file_hash = fix_obsidian_images_in_file(md_file, static_dir, verbose=verbose)
        
        if fixed:
            fixed_count += 1
        
        # 更新状态
        files_state[file_str] = file_hash
    
    # 清理状态：移除不存在的文件
    existing_files = {str(f) for f in md_files}
    files_state = {k: v for k, v in files_state.items() if k in existing_files}
    state['files'] = files_state
    
    # 保存状态
    save_state(state)
    
    if verbose:
        print(f"\n修复完成！")
        print(f"  - 处理文件数: {processed_count}")
        print(f"  - 修复文件数: {fixed_count}")
        if incremental and not force:
            print(f"  - 跳过文件数: {skipped_count} (未修改)")

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='修复 Obsidian 格式的图片链接')
    parser.add_argument('file', nargs='?', help='要修复的单个文件路径（可选）')
    parser.add_argument('--force', '-f', action='store_true', 
                       help='强制处理所有文件（忽略状态文件）')
    parser.add_argument('--no-incremental', action='store_true',
                       help='禁用增量处理（处理所有文件）')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='静默模式（不显示详细信息）')
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    incremental = not args.no_incremental
    
    # 如果提供了文件路径，只修复该文件
    if args.file:
        fix_obsidian_images_in_file(args.file, verbose=verbose)
    else:
        # 否则修复所有文件
        fix_all_obsidian_images(incremental=incremental, force=args.force, verbose=verbose)
