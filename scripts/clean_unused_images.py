#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan static/images for files not referenced by content/, then interactively delete them.

Usage:
  python scripts/clean_unused_images.py           # list only (dry-run)
  python scripts/clean_unused_images.py --apply   # confirm and delete
  python scripts/clean_unused_images.py --apply -y  # delete without prompt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, Set

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib.obsidian_links import IMAGE_EXTENSIONS, collect_image_references

FRONT_MATTER_IMAGE = re.compile(r'^image:\s*/images/(.+)\s*$', re.MULTILINE)
HTML_IMAGE = re.compile(r'<img[^>]+src=["\']/images/([^"\']+)["\']', re.IGNORECASE)


def iter_markdown_files(content_dir: Path) -> Iterable[Path]:
    yield from sorted(content_dir.rglob('*.md'))


def iter_image_files(images_dir: Path) -> Iterable[Path]:
    if not images_dir.exists():
        return
    for path in sorted(images_dir.rglob('*')):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def normalize_ref(path: str) -> str:
    return path.strip().replace('\\', '/')


def collect_referenced_images(content_dir: Path) -> Set[str]:
    refs: Set[str] = set()

    for md_file in iter_markdown_files(content_dir):
        text = md_file.read_text(encoding='utf-8')
        for ref in collect_image_references(text):
            refs.add(normalize_ref(ref))

        for match in FRONT_MATTER_IMAGE.finditer(text):
            refs.add(normalize_ref(match.group(1)))

        for match in HTML_IMAGE.finditer(text):
            refs.add(normalize_ref(match.group(1)))

    return refs


def find_unused_images(images_dir: Path, referenced: Set[str]) -> list[str]:
    unused: list[str] = []
    for image_file in iter_image_files(images_dir):
        rel = image_file.relative_to(images_dir).as_posix()
        if rel not in referenced:
            unused.append(rel)
    return unused


def confirm_delete(unused: list[str], auto_yes: bool) -> list[str]:
    if not unused:
        return []

    print(f'\n共 {len(unused)} 个未引用图片：')
    for name in unused:
        print(f'  - {name}')

    if auto_yes:
        print('\n已启用 --yes，将全部删除。')
        return unused

    print('\n操作: [y] 全部删除  [n] 取消  [i] 逐项确认')
    answer = input('请选择: ').strip().lower()

    if answer == 'n':
        print('已取消。')
        return []

    if answer == 'y':
        return unused

    selected: list[str] = []
    for name in unused:
        choice = input(f'删除 {name}? [y/N/q]: ').strip().lower()
        if choice == 'q':
            break
        if choice == 'y':
            selected.append(name)
    return selected


def delete_images(images_dir: Path, names: list[str]) -> int:
    deleted = 0
    for name in names:
        path = images_dir / name
        if path.exists():
            path.unlink()
            deleted += 1
            print(f'已删除: {name}')
        else:
            print(f'跳过（不存在）: {name}')
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(description='检查并删除 content 未引用的 static/images 图片')
    parser.add_argument('--content-dir', default='content', help='Markdown 内容目录')
    parser.add_argument('--images-dir', default='static/images', help='图片目录')
    parser.add_argument('--apply', action='store_true', help='确认后删除（默认仅列出）')
    parser.add_argument('-y', '--yes', action='store_true', help='跳过确认，直接删除全部未引用图片')
    args = parser.parse_args()

    project_root = Path.cwd()
    content_dir = project_root / args.content_dir
    images_dir = project_root / args.images_dir

    if not content_dir.exists():
        raise SystemExit(f'内容目录不存在: {content_dir}')
    if not images_dir.exists():
        raise SystemExit(f'图片目录不存在: {images_dir}')

    referenced = collect_referenced_images(content_dir)
    all_images = [p.relative_to(images_dir).as_posix() for p in iter_image_files(images_dir)]
    unused = find_unused_images(images_dir, referenced)

    print('=== 未引用图片检查 ===')
    print(f'扫描内容: {content_dir}')
    print(f'图片目录: {images_dir}')
    print(f'图片总数: {len(all_images)}')
    print(f'引用数量: {len(referenced)}')
    print(f'未引用数: {len(unused)}')

    if not unused:
        print('\n没有未引用的图片。')
        return

    if not args.apply:
        print('\n[dry-run] 以上文件不会被删除。执行删除请加 --apply')
        return

    to_delete = confirm_delete(unused, args.yes)
    if not to_delete:
        return

    deleted = delete_images(images_dir, to_delete)
    print(f'\n完成，已删除 {deleted} 个文件。')


if __name__ == '__main__':
    main()
