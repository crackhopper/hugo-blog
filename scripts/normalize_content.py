#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Normalize blog content:
- Remove unused images from static/images
- Rename images to {article}-{section}-{NN}.ext
- Migrate Hugo relref links to Obsidian wiki syntax
- Interactively fix broken wiki links
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from lib.obsidian_links import (
    EMBED_IMAGE_PATTERN,
    IMAGE_EXTENSIONS,
    MARKDOWN_IMAGE_PATTERN,
    WikiIndex,
    build_wikilink_index,
    collect_image_references,
    find_broken_wiki_links,
    fix_same_page_index_links,
    fuzzy_candidates,
    migrate_relref_links,
    parse_wiki_link_inner,
    slugify_heading,
    wiki_link_for_path,
)


HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+?)\s*$', re.MULTILINE)


@dataclass
class ImageRenamePlan:
    old_name: str
    new_name: str
    article: str
    section: str


@dataclass
class NormalizeReport:
    unused_images: List[str] = field(default_factory=list)
    image_renames: List[ImageRenamePlan] = field(default_factory=list)
    relref_migrations: int = 0
    broken_links: List[Tuple[str, str, str]] = field(default_factory=list)


def iter_markdown_files(content_dir: Path, article_filter: Optional[str] = None) -> Iterable[Path]:
    for md_file in sorted(content_dir.rglob('*.md')):
        if article_filter and md_file.stem != article_filter:
            continue
        yield md_file


def scan_all_image_references(content_dir: Path, article_filter: Optional[str] = None) -> Set[str]:
    refs: Set[str] = set()
    for md_file in iter_markdown_files(content_dir, article_filter):
        refs.update(collect_image_references(md_file.read_text(encoding='utf-8')))
    return refs


def scan_unused_images(
    images_dir: Path,
    referenced: Set[str],
    article_filter: Optional[str] = None,
) -> List[str]:
    unused: List[str] = []
    if not images_dir.exists():
        return unused

    for image_file in sorted(images_dir.rglob('*')):
        if not image_file.is_file():
            continue
        if image_file.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        rel_name = image_file.relative_to(images_dir).as_posix()
        if article_filter and not rel_name.startswith(article_filter):
            continue
        if rel_name not in referenced:
            unused.append(rel_name)
    return unused


def parse_headings(content: str) -> List[Tuple[int, str, int]]:
    headings: List[Tuple[int, str, int]] = []
    for match in HEADING_PATTERN.finditer(content):
        level = len(match.group(1))
        title = match.group(2).strip()
        headings.append((match.start(), level, title))
    return headings


def section_for_position(headings: List[Tuple[int, str, int]], pos: int) -> str:
    current = 'intro'
    for start, _, title in headings:
        if start <= pos:
            current = slugify_heading(title) or 'intro'
        else:
            break
    return current or 'intro'


def build_image_rename_plans(
    md_file: Path,
    images_dir: Path,
) -> Tuple[str, List[ImageRenamePlan], Dict[str, str]]:
    content = md_file.read_text(encoding='utf-8')
    article_stem = md_file.stem
    headings = parse_headings(content)
    section_counters: Dict[str, int] = {}
    rename_map: Dict[str, str] = {}
    plans: List[ImageRenamePlan] = []

    def next_name(section: str, ext: str) -> str:
        section_counters[section] = section_counters.get(section, 0) + 1
        index = section_counters[section]
        return f'{article_stem}-{section}-{index:02d}{ext}'

    for match in EMBED_IMAGE_PATTERN.finditer(content):
        inner = match.group(1)
        target, width_meta, alias = parse_wiki_link_inner(inner)
        if not target:
            continue

        ext = Path(target).suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            continue

        if target in rename_map:
            continue

        section = section_for_position(headings, match.start())
        new_name = next_name(section, ext)

        while (images_dir / new_name).exists() and (images_dir / new_name).name != Path(target).name:
            new_name = next_name(section, ext)

        if new_name == target:
            continue

        rename_map[target] = new_name
        plans.append(ImageRenamePlan(target, new_name, article_stem, section))

    new_content = content
    for old_name, new_name in sorted(rename_map.items(), key=lambda item: len(item[0]), reverse=True):
        new_content = new_content.replace(f'![[{old_name}]]', f'![[{new_name}]]')
        new_content = re.sub(
            rf'!\[\[{re.escape(old_name)}\|([^\]]+)\]\]',
            rf'![[{new_name}|\1]]',
            new_content,
        )

    return new_content, plans, rename_map


def convert_legacy_markdown_images(content: str) -> Tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        path = match.group('path').strip()
        if path.startswith('<') and path.endswith('>'):
            path = path[1:-1].strip()
        if path.startswith('/images/'):
            path = path[len('/images/') :]
        count += 1
        return f'![[{path}]]'

    return MARKDOWN_IMAGE_PATTERN.sub(replace, content), count


def confirm_unused_deletions(unused: List[str], apply: bool, auto_yes: bool) -> List[str]:
    if not unused:
        return []

    print(f'\n发现 {len(unused)} 个未引用图片:')
    for name in unused[:20]:
        print(f'  - {name}')
    if len(unused) > 20:
        print(f'  ... 以及另外 {len(unused) - 20} 个')

    if not apply:
        print('[dry-run] 跳过删除')
        return []

    if auto_yes:
        return unused

    answer = input('删除这些图片? [y/N/a=全部删除/q=取消]: ').strip().lower()
    if answer == 'q':
        return []
    if answer in {'y', 'a', 'yes'}:
        return unused
    return []


def apply_image_renames(
    plans: List[ImageRenamePlan],
    images_dir: Path,
    apply: bool,
) -> None:
    for plan in plans:
        old_path = images_dir / plan.old_name
        new_path = images_dir / plan.new_name
        print(f'  图片: {plan.old_name} -> {plan.new_name} ({plan.section})')
        if apply and old_path.exists():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            if new_path.exists() and new_path.resolve() != old_path.resolve():
                raise FileExistsError(f'目标已存在: {new_path}')
            old_path.rename(new_path)


def interactive_fix_links(
    md_file: Path,
    content: str,
    wiki_index: WikiIndex,
    apply: bool,
    auto_yes: bool,
) -> str:
    broken = find_broken_wiki_links(content, wiki_index)
    if not broken:
        return content

    print(f'\n修复链接: {md_file}')
    updated = content
    for full_match, target in broken:
        print(f'\nBroken: {full_match}')
        print(f'  target: {target}')
        candidates = fuzzy_candidates(target, wiki_index)
        if not candidates:
            print('  无候选，跳过')
            continue

        for idx, (path, label, score) in enumerate(candidates, start=1):
            print(f'  [{idx}] {label} -> {path} ({score:.2f})')
        print('  [s] 跳过  [q] 停止')

        if not apply:
            print('[dry-run] 跳过写入')
            continue

        if auto_yes and candidates:
            choice = '1'
        else:
            choice = input('选择: ').strip().lower()
            if choice == 'q':
                break
            if choice in {'s', ''}:
                continue

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(candidates):
                chosen_path, chosen_label, _ = candidates[index]
                inner = full_match[2:-2]
                _, alias, anchor = parse_wiki_link_inner(inner)
                replacement = wiki_link_for_path(chosen_path, anchor=anchor, alias=alias or chosen_label)
                updated = updated.replace(full_match, replacement, 1)
                print(f'  -> {replacement}')

    return updated


def scan_broken_links(content_dir: Path, wiki_index: WikiIndex) -> List[Tuple[str, str, str]]:
    broken: List[Tuple[str, str, str]] = []
    for md_file in iter_markdown_files(content_dir):
        content = md_file.read_text(encoding='utf-8')
        for full_match, target in find_broken_wiki_links(content, wiki_index):
            broken.append((str(md_file.relative_to(content_dir)), full_match, target))
    return broken


def normalize_content(
    content_dir: Path,
    images_dir: Path,
    apply: bool = False,
    fix_links: bool = False,
    article_filter: Optional[str] = None,
    auto_yes: bool = False,
    skip_delete: bool = False,
    skip_rename: bool = False,
    skip_relref: bool = False,
) -> NormalizeReport:
    report = NormalizeReport()
    wiki_index = build_wikilink_index(content_dir)

    referenced = scan_all_image_references(content_dir, article_filter)
    report.unused_images = scan_unused_images(images_dir, referenced, article_filter)

    if not skip_delete:
        to_delete = confirm_unused_deletions(report.unused_images, apply, auto_yes)
        if apply:
            for name in to_delete:
                path = images_dir / name
                if path.exists():
                    path.unlink()

    for md_file in iter_markdown_files(content_dir, article_filter):
        original = md_file.read_text(encoding='utf-8')
        content = original
        changed = False

        legacy_content, legacy_count = convert_legacy_markdown_images(content)
        if legacy_count:
            content = legacy_content
            changed = True
            print(f'{md_file.name}: 转换 {legacy_count} 处 Markdown 图片语法')

        if not skip_relref:
            migrated, relref_count = migrate_relref_links(content)
            if relref_count:
                content = migrated
                report.relref_migrations += relref_count
                changed = True
                print(f'{md_file.name}: 迁移 {relref_count} 处 relref -> wiki')

        fixed_index, index_count = fix_same_page_index_links(content)
        if index_count:
            content = fixed_index
            changed = True
            print(f'{md_file.name}: 修复 {index_count} 处 _index 文内链接')

        if not skip_rename:
            renamed_content, plans, _ = build_image_rename_plans(md_file, images_dir)
            if plans:
                report.image_renames.extend(plans)
                content = renamed_content
                changed = True
                print(f'{md_file.name}: 计划重命名 {len(plans)} 张图片')
                apply_image_renames(plans, images_dir, apply)

        if fix_links:
            content = interactive_fix_links(md_file, content, wiki_index, apply, auto_yes)
            if content != original:
                changed = True

        if apply and changed:
            md_file.write_text(content, encoding='utf-8')

    report.broken_links = scan_broken_links(content_dir, wiki_index)
    return report


def print_report(report: NormalizeReport) -> None:
    print('\n=== Normalize Report ===')
    print(f'未引用图片: {len(report.unused_images)}')
    print(f'图片重命名: {len(report.image_renames)}')
    print(f'relref 迁移: {report.relref_migrations}')
    print(f'仍 broken 的 wiki 链接: {len(report.broken_links)}')
    for file_path, full_match, target in report.broken_links[:20]:
        print(f'  - {file_path}: {full_match} ({target})')


def main() -> None:
    parser = argparse.ArgumentParser(description='Normalize blog content (images + links)')
    parser.add_argument('--content-dir', default='content')
    parser.add_argument('--images-dir', default='static/images')
    parser.add_argument('--apply', action='store_true', help='Write changes to disk')
    parser.add_argument('--fix-links', action='store_true', help='Interactively fix broken wiki links')
    parser.add_argument('--article', help='Only process one article stem')
    parser.add_argument('--yes', '-y', action='store_true', help='Auto confirm prompts')
    parser.add_argument('--skip-delete', action='store_true')
    parser.add_argument('--skip-rename', action='store_true')
    parser.add_argument('--skip-relref', action='store_true')
    args = parser.parse_args()

    content_dir = Path(args.content_dir)
    images_dir = Path(args.images_dir)

    if not content_dir.exists():
        raise SystemExit(f'内容目录不存在: {content_dir}')

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'=== Normalize ({mode}) ===')

    report = normalize_content(
        content_dir=content_dir,
        images_dir=images_dir,
        apply=args.apply,
        fix_links=args.fix_links,
        article_filter=args.article,
        auto_yes=args.yes,
        skip_delete=args.skip_delete,
        skip_rename=args.skip_rename,
        skip_relref=args.skip_relref,
    )
    print_report(report)


if __name__ == '__main__':
    main()
