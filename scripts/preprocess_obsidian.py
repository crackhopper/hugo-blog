#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预处理脚本：将 Obsidian Wiki 语法 ![[...]] 转换为 Hugo 可识别的 Markdown。
在 Hugo 处理之前运行，不修改原始文件，而是创建临时副本。
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib.obsidian_links import build_wikilink_index, transform_obsidian_links


def get_file_hash(file_path: Path) -> str:
    with open(file_path, 'rb') as file:
        return hashlib.md5(file.read()).hexdigest()


def preprocess_content_dir(content_dir='content', temp_dir='.hugo_temp_content', force=False):
    content_path = Path(content_dir)
    temp_path = Path(temp_dir)
    state_file = temp_path / '.preprocess_state.json'

    if not content_path.exists():
        print(f'内容目录不存在: {content_path}')
        return None

    state = {}
    if state_file.exists() and not force:
        try:
            with open(state_file, 'r', encoding='utf-8') as file:
                state = json.load(file)
        except OSError:
            state = {}

    if force or not temp_path.exists():
        if temp_path.exists():
            shutil.rmtree(temp_path)
        temp_path.mkdir(parents=True, exist_ok=True)
        state = {}

    temp_path.mkdir(parents=True, exist_ok=True)

    md_files = list(content_path.rglob('*.md'))
    wiki_index = build_wikilink_index(content_path)
    static_images_dir = Path.cwd() / 'static' / 'images'
    updated_count = 0
    skipped_count = 0

    for md_file in md_files:
        rel_path = md_file.relative_to(content_path)
        temp_file = temp_path / rel_path
        temp_file.parent.mkdir(parents=True, exist_ok=True)

        file_str = str(rel_path)
        current_hash = get_file_hash(md_file)
        saved_hash = state.get(file_str)

        if saved_hash == current_hash and temp_file.exists() and not force:
            skipped_count += 1
            continue

        content = md_file.read_text(encoding='utf-8')
        transformed = transform_obsidian_links(
            content,
            static_images_dir=static_images_dir,
            wiki_index=wiki_index,
            verbose=False,
        )
        temp_file.write_text(transformed, encoding='utf-8')
        state[file_str] = current_hash
        updated_count += 1

    existing_files = {str(file.relative_to(content_path)) for file in md_files}
    state = {key: value for key, value in state.items() if key in existing_files}

    if state_file.parent.exists():
        with open(state_file, 'w', encoding='utf-8') as file:
            json.dump(state, file, indent=2, ensure_ascii=False)

    print(f'预处理完成: {len(md_files)} 个文件（更新: {updated_count}, 跳过: {skipped_count}）')
    return str(temp_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='预处理 Obsidian wiki 语法')
    parser.add_argument('--force', '-f', action='store_true', help='强制重新处理所有文件')
    args = parser.parse_args()

    result = preprocess_content_dir(force=args.force)
    if result:
        print(f'临时目录: {result}')
        print("提示: 使用 'hugo --contentDir .hugo_temp_content' 来使用预处理后的内容")
