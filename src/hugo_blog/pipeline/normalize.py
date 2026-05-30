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
from dataclasses import dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from hugo_blog.pipeline.wikilinks import (
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
    simplify_document_wiki_links,
    slugify_heading,
    wiki_link_for_path,
)
from hugo_blog.pipeline.content_filters import iter_processable_markdown_files
from hugo_blog.pipeline.image_manifest import ImageManifest
from hugo_blog.pipeline.image_normalizer import normalize_markdown_images
from hugo_blog.pipeline.link_manifest import LinkManifest
from hugo_blog.pipeline.metadata import ensure_metadata, needs_summary, normalize_title, parse_front_matter
from hugo_blog.pipeline.validate import ValidationIssue, format_report, validate_markdown_text, ValidationReport
from hugo_blog.llm.client import LLMClient, LLMMetadata, config_from_env


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
    metadata_updates: int = 0
    summary_updates: int = 0
    llm_requests: int = 0
    llm_skips: int = 0
    validation_issues: List[ValidationIssue] = field(default_factory=list)


def require_llm_config(llm_client: Optional[LLMClient]) -> None:
    if llm_client is None or not llm_client.config.available:
        raise RuntimeError(
            "LLM config is required. Run python3 init.py to configure LLM_API_KEY and LLM_MODEL, "
            "or pass --no-llm for explicit offline mode."
        )


def resolve_apply_and_llm(*, dry_run: bool, no_llm: bool) -> tuple[bool, bool]:
    apply = not dry_run
    use_llm = False if dry_run else not no_llm
    return apply, use_llm


def format_llm_change_summary(*, file_name: str, metadata: LLMMetadata) -> str:
    lines = [f'{file_name}: LLM 生成内容']
    if metadata.abstract:
        lines.append(f'  摘要: {metadata.abstract}')
    tags = metadata.normalized_tags()
    if tags:
        lines.append(f'  tags: {", ".join(tags)}')
    return '\n'.join(lines)


def metadata_needs_update(md_file: Path) -> bool:
    text = md_file.read_text(encoding='utf-8')
    metadata, body, has_front_matter = parse_front_matter(text)
    if not has_front_matter:
        return True
    if not metadata.get('title'):
        return True
    if not metadata.get('date'):
        return True
    if 'draft' not in metadata:
        return True
    if 'description' in metadata:
        return True
    if not metadata.get('tags'):
        return True
    return needs_summary(body)


def confirm_file_metadata_update(
    *,
    md_file: Path,
    apply: bool,
    apply_all: bool,
    prompt=input,
) -> bool:
    if not apply:
        return True
    if apply_all:
        return True
    try:
        answer = prompt(f'处理 {md_file}: 修复 front matter/tags/摘要？[y/N] ')
    except EOFError:
        return False
    return answer.strip().lower() in {'y', 'yes'}


def confirm_file_write(
    *,
    md_file: Path,
    apply: bool,
    apply_all: bool,
    prompt=input,
) -> bool:
    if not apply:
        return True
    if apply_all:
        return True
    try:
        answer = prompt(f'写入 {md_file} 的归一化修改？[y/N] ')
    except EOFError:
        return False
    return answer.strip().lower() in {'y', 'yes'}


def confirm_metadata_updates(
    *,
    count: int,
    apply: bool,
    apply_all: bool,
    prompt=input,
) -> bool:
    if count <= 0 or not apply:
        return True
    if apply_all:
        return True

    try:
        answer = prompt(
            f'检测到 {count} 篇文章需要修复 front matter/tags/摘要，是否继续写入？[y/N] '
        )
    except EOFError:
        return False
    return answer.strip().lower() in {'y', 'yes'}


def iter_markdown_files(content_dir: Path, article_filter: Optional[str] = None) -> Iterable[Path]:
    for md_file in iter_processable_markdown_files(content_dir):
        if article_filter and not _matches_article_filter(md_file, content_dir, article_filter):
            continue
        yield md_file


def _matches_article_filter(md_file: Path, content_dir: Path, article_filter: str) -> bool:
    normalized = article_filter.strip().replace("\\", "/").removeprefix("/")
    rel_path = md_file.relative_to(content_dir).as_posix()
    if normalized.endswith(".md") or "/" in normalized:
        return rel_path == normalized
    return md_file.stem == normalized


def _date_timestamp(value) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, date):
        return datetime.combine(value, time.min).timestamp()
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            return float("-inf")
    return float("-inf")


def _markdown_order_key(md_file: Path) -> tuple[int, float, str]:
    metadata, _, has_front_matter = parse_front_matter(md_file.read_text(encoding="utf-8"))
    if not has_front_matter:
        return (0, -md_file.stat().st_mtime, md_file.as_posix())
    return (1, -_date_timestamp(metadata.get("date")), md_file.as_posix())


def ordered_markdown_files(content_dir: Path, article_filter: Optional[str] = None) -> List[Path]:
    return sorted(iter_markdown_files(content_dir, article_filter), key=_markdown_order_key)


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

    manifest = ImageManifest.load(images_dir)
    referenced_paths = set(referenced)
    for ref in referenced:
        manifest_target = manifest.get(ref)
        if manifest_target:
            referenced_paths.add(manifest_target)

    for image_file in sorted(images_dir.rglob('*')):
        if not image_file.is_file():
            continue
        if image_file.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        rel_name = image_file.relative_to(images_dir).as_posix()
        if article_filter and not rel_name.startswith(article_filter):
            continue
        if rel_name not in referenced_paths:
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
        if not (images_dir / target).exists():
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
    normalize_metadata: bool = True,
    use_llm: bool = True,
    apply_all: bool = False,
    review_each: bool = False,
    restart_preview: Optional[Callable[[], None]] = None,
    review_prompt=input,
) -> NormalizeReport:
    report = NormalizeReport()
    wiki_index = build_wikilink_index(content_dir)
    link_manifest = LinkManifest.build(content_dir)
    if apply:
        link_manifest.save()
    llm_client: Optional[LLMClient] = None
    metadata_confirmed = True
    ordered_files = ordered_markdown_files(content_dir, article_filter)
    if normalize_metadata:
        metadata_candidates = [
            md_file for md_file in ordered_files
            if metadata_needs_update(md_file)
        ]
        if review_each:
            metadata_confirmed = True
        else:
            metadata_confirmed = confirm_metadata_updates(
                count=len(metadata_candidates),
                apply=apply,
                apply_all=apply_all,
            )
        if not metadata_confirmed:
            print('已跳过 front matter/tags/摘要修复')

    if normalize_metadata and metadata_confirmed and use_llm and metadata_candidates:
        llm_client = LLMClient(config_from_env(Path.cwd()))
        if not review_each:
            require_llm_config(llm_client)

    referenced = scan_all_image_references(content_dir, article_filter)
    report.unused_images = scan_unused_images(images_dir, referenced, article_filter)

    if not skip_delete:
        to_delete = confirm_unused_deletions(report.unused_images, apply, auto_yes)
        if apply:
            for name in to_delete:
                path = images_dir / name
                if path.exists():
                    path.unlink()

    for md_file in ordered_files:
        if apply:
            image_result = normalize_markdown_images(
                md_file,
                content_dir=content_dir,
                static_images_dir=images_dir,
            )
            if image_result.changed:
                print(f'{md_file.name}: 归一化 {len(image_result.renamed)} 张图片到日期目录')
                for old_name, rel_target in image_result.renamed:
                    print(f'  图片: {old_name} -> {rel_target}')
            for warning in image_result.warnings:
                print(f'  warning: {warning}')

        original = md_file.read_text(encoding='utf-8')
        content = original
        changed = False
        file_confirmed: Optional[bool] = None
        rel_file = md_file.relative_to(content_dir).as_posix()
        original_issues = validate_markdown_text(
            original,
            source_path=rel_file,
            static_images_dir=images_dir,
        )
        if original_issues:
            report.validation_issues.extend(original_issues)
            print(format_report(ValidationReport(original_issues)))
            if apply:
                print(f'{md_file.name}: 存在 broken image，跳过写入')
                continue

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

        simplified_content, simplified_count = simplify_document_wiki_links(content, link_manifest)
        if simplified_count:
            content = simplified_content
            changed = True
            print(f'{md_file.name}: 简化 {simplified_count} 处文章链接')

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

        process_metadata = normalize_metadata and metadata_confirmed
        if process_metadata and review_each and metadata_needs_update(md_file):
            file_confirmed = confirm_file_metadata_update(
                md_file=md_file.relative_to(content_dir),
                apply=apply,
                apply_all=apply_all,
                prompt=review_prompt,
            )
            process_metadata = file_confirmed
            if not process_metadata:
                print(f'{md_file.name}: 跳过 front matter/摘要')

        if process_metadata:
            metadata, body, _ = parse_front_matter(content)
            need_tags = not metadata.get('tags')
            need_abstract = needs_summary(body)
            llm_metadata: Optional[LLMMetadata] = None
            if llm_client and (need_tags or need_abstract):
                require_llm_config(llm_client)
                title = str(metadata.get('title') or normalize_title(md_file))
                llm_metadata = llm_client.generate_metadata(
                    title=title,
                    body=body,
                    need_abstract=need_abstract,
                    need_tags=need_tags,
                )
                if llm_metadata.abstract or llm_metadata.normalized_tags():
                    report.llm_requests += 1
                    print(format_llm_change_summary(file_name=md_file.name, metadata=llm_metadata))
                else:
                    report.llm_skips += 1

            metadata_update = ensure_metadata(
                md_file=md_file,
                text=content,
                llm_metadata=llm_metadata,
            )
            if metadata_update.changed:
                content = metadata_update.text
                changed = True
                if metadata_update.metadata_changed:
                    report.metadata_updates += 1
                if metadata_update.summary_changed:
                    report.summary_updates += 1
                print(f'{md_file.name}: 更新 front matter/摘要')

        if apply and changed:
            updated_issues = validate_markdown_text(
                content,
                source_path=rel_file,
                static_images_dir=images_dir,
            )
            if updated_issues:
                report.validation_issues.extend(updated_issues)
                print(format_report(ValidationReport(updated_issues)))
                print(f'{md_file.name}: 归一化结果仍存在 broken image，跳过写入')
                continue
            if review_each and file_confirmed is None:
                file_confirmed = confirm_file_write(
                    md_file=md_file.relative_to(content_dir),
                    apply=apply,
                    apply_all=apply_all,
                    prompt=review_prompt,
                )
            if review_each and not file_confirmed:
                print(f'{md_file.name}: 跳过写入')
                continue
            md_file.write_text(content, encoding='utf-8')
            if review_each and restart_preview:
                restart_preview()

    report.broken_links = scan_broken_links(content_dir, wiki_index)
    return report


def print_report(report: NormalizeReport) -> None:
    print('\n=== Normalize Report ===')
    print(f'未引用图片: {len(report.unused_images)}')
    print(f'图片重命名: {len(report.image_renames)}')
    print(f'relref 迁移: {report.relref_migrations}')
    print(f'front matter 更新: {report.metadata_updates}')
    print(f'摘要更新: {report.summary_updates}')
    print(f'LLM 成功生成: {report.llm_requests}')
    print(f'LLM 跳过/失败: {report.llm_skips}')
    print(f'图片引用错误: {len(report.validation_issues)}')
    print(f'仍 broken 的 wiki 链接: {len(report.broken_links)}')
    for issue in report.validation_issues[:20]:
        print(f'  - {issue.source_path}:{issue.line}: {issue.message}')
    for file_path, full_match, target in report.broken_links[:20]:
        print(f'  - {file_path}: {full_match} ({target})')


def main() -> None:
    parser = argparse.ArgumentParser(description='Normalize blog content (images + links)')
    parser.add_argument('--content-dir', default='content')
    parser.add_argument('--images-dir', default='static/images')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing; also disables LLM calls')
    parser.add_argument('--fix-links', action='store_true', help='Interactively fix broken wiki links')
    parser.add_argument('--article', help='Only process one article stem')
    parser.add_argument('--yes', '-y', action='store_true', help='Auto confirm prompts')
    parser.add_argument('--apply-all', action='store_true', help='Apply metadata fixes without asking for confirmation')
    parser.add_argument('--review-each', action='store_true', help='Ask per file and restart preview after each written file')
    parser.add_argument('--skip-delete', action='store_true')
    parser.add_argument('--skip-rename', action='store_true')
    parser.add_argument('--skip-relref', action='store_true')
    parser.add_argument('--skip-metadata', action='store_true', help='Skip front matter, tags, and abstract normalization')
    parser.add_argument('--no-llm', action='store_true', help='Do not call the configured LLM API')
    args = parser.parse_args()

    content_dir = Path(args.content_dir)
    images_dir = Path(args.images_dir)

    if not content_dir.exists():
        raise SystemExit(f'内容目录不存在: {content_dir}')

    apply, use_llm = resolve_apply_and_llm(dry_run=args.dry_run, no_llm=args.no_llm)
    mode = 'DRY-RUN' if args.dry_run else 'APPLY'
    print(f'=== Normalize ({mode}) ===')

    restart_preview = None
    if apply and args.review_each:
        from hugo_blog.preview.launcher import start_background_preview

        restart_preview = lambda: start_background_preview(include_drafts=False)

    report = normalize_content(
        content_dir=content_dir,
        images_dir=images_dir,
        apply=apply,
        fix_links=args.fix_links,
        article_filter=args.article,
        auto_yes=args.yes,
        skip_delete=args.skip_delete,
        skip_rename=args.skip_rename,
        skip_relref=args.skip_relref,
        normalize_metadata=not args.skip_metadata,
        use_llm=use_llm,
        apply_all=args.apply_all,
        review_each=args.review_each,
        restart_preview=restart_preview,
    )
    print_report(report)
    if apply and not args.dry_run:
        from hugo_blog.preview.launcher import start_background_preview

        if not args.review_each:
            start_background_preview(include_drafts=True)


if __name__ == '__main__':
    main()
