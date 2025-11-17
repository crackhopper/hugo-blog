#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预处理脚本：将 Obsidian Wiki 语法 ![[...]] 转换为 Hugo 可识别的 Markdown：
- 图片：转换为标准 Markdown 图片或带宽度的 HTML img
- 文档：转换为使用 relref 的 Markdown 链接
在 Hugo 处理之前运行，不修改原始文件，而是创建临时副本
支持增量更新：只更新修改过的文件
"""
import re
import shutil
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

IMAGE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.avif', '.heic', '.heif'
}

def get_file_hash(file_path):
    """计算文件的 MD5 哈希值"""
    with open(file_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def build_wikilink_index(content_dir: Path) -> Dict[str, List[str]]:
    """
    构建一个 wiki 链接索引，支持以下匹配方式：
    - 相对路径（含/不含 .md 扩展名）
    - 文件名（stem）
    """
    index: Dict[str, List[str]] = {}
    for md_file in content_dir.rglob('*.md'):
        rel_path = md_file.relative_to(content_dir).as_posix()
        stem = md_file.stem
        without_ext = rel_path[: -len(md_file.suffix)] if md_file.suffix else rel_path
        for key in {rel_path, without_ext, stem}:
            if not key:
                continue
            index.setdefault(key, [])
            if rel_path not in index[key]:
                index[key].append(rel_path)
    return index


def looks_like_width(value: str) -> bool:
    """判断 | 后的参数是否是图片宽度/尺寸描述"""
    return bool(re.match(r'^\d+(?:px)?(?:[xX]\d+)?$', value.strip()))


def resolve_document_target(target: str, wiki_index: Dict[str, List[str]]) -> Tuple[Optional[str], Optional[str]]:
    """根据 wiki 索引解析目标文档，返回 (相对路径, 锚点)"""
    anchor = None
    normalized = target.strip().replace('\\', '/')
    if '#' in normalized:
        normalized, anchor = normalized.split('#', 1)
        anchor = anchor.strip()
    candidates = []
    candidates.append(normalized)
    if normalized.endswith('.md'):
        candidates.append(normalized[:-3])
    else:
        candidates.append(f"{normalized}.md")
    name = Path(normalized).name
    candidates.append(name)
    name_without_ext = Path(name).stem
    if name_without_ext != name:
        candidates.append(name_without_ext)
    for key in candidates:
        key = key.strip()
        if not key:
            continue
        if key in wiki_index:
            paths = wiki_index[key]
            if len(paths) == 1:
                return paths[0], anchor
            print(f"警告: Wiki 链接 '{target}' 存在多个候选项，跳过。候选: {paths}")
            return None, anchor
    return None, anchor


def transform_obsidian_links(content, static_images_dir=None, wiki_index=None):
    """将 Obsidian 的 ![[...]] 语法转换为标准 Markdown 资源"""
    pattern = r'!\[\[([^\]]+)\]\]'
    
    project_root = Path.cwd()
    static_images_dir = Path(static_images_dir or (project_root / 'static' / 'images'))
    wiki_index = wiki_index or {}
    
    missing_images = []
    unresolved_documents = []
    
    def replace_func(match):
        full_match = match.group(1).strip()
        parts = [p.strip() for p in full_match.split('|')]
        target = parts[0]
        meta = parts[1] if len(parts) > 1 else None
        width = meta if meta and looks_like_width(meta) else None
        alias = None if width else meta
        
        suffix = Path(target).suffix.lower()
        image_path = static_images_dir / target
        
        is_image = False
        if suffix in IMAGE_EXTENSIONS:
            is_image = True
        elif image_path.exists():
            is_image = True
        else:
            doc_path, anchor = resolve_document_target(target, wiki_index)
            if doc_path:
                link_text = alias or Path(doc_path).stem
                relref = f'{{{{< relref "{doc_path}" >}}}}'
                if anchor:
                    relref = f"{relref}#{anchor}"
                return f"[{link_text}]({relref})"
            else:
                unresolved_documents.append(target)
        
        alt_text = alias or Path(target).stem
        if is_image:
            if not image_path.exists():
                missing_images.append(target)
            if width:
                return f'<img src="/images/{target}" alt="{alt_text}" width="{width}" loading="lazy" />'
            return f"![{alt_text}](/images/{target})"
        return match.group(0)
    
    result = re.sub(pattern, replace_func, content)
    
    if missing_images:
        print(f"警告: 以下图片文件不存在于 {static_images_dir}:")
        for img in sorted(set(missing_images)):
            print(f"  - {img}")
        print("提示: 请确保图片文件已复制到 static/images/ 目录")
    if unresolved_documents:
        print("警告: 以下 wiki 链接无法解析为文档，将保留原样：")
        for item in sorted(set(unresolved_documents)):
            print(f"  - {item}")
    
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
    wiki_index = build_wikilink_index(content_path)
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
        transformed = transform_obsidian_links(
            content,
            static_images_dir=static_images_dir,
            wiki_index=wiki_index,
        )
        
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

