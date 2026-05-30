#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared Obsidian wiki-link parsing, indexing, and Hugo conversion."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

from hugo_blog.pipeline.content_filters import iter_content_markdown_files

IMAGE_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.avif', '.heic', '.heif'
}

WIKI_LINK_PATTERN = re.compile(r'(!)?\[\[([^\]]+)\]\]')
EMBED_IMAGE_PATTERN = re.compile(r'!\[\[([^\]]+)\]\]')
DOC_WIKI_PATTERN = re.compile(r'(?<!!)\[\[([^\]]+)\]\]')
RELREF_PATTERN = re.compile(
    r'\[([^\]]*)\]\(\{\{<\s*relref\s+"([^"]+)"\s*>\}\}(?:#([^)\s]+))?\)'
)
MARKDOWN_IMAGE_PATTERN = re.compile(
    r'!\[(?P<alt>[^\]]*)\]\((?P<path>[^)\s]+)(?:\s+"[^"]*")?\)'
)
MORE_MARKER_PATTERN = re.compile(r'<!--\s+more\s+-->', re.IGNORECASE)

FRONT_MATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
TITLE_PATTERN = re.compile(r'^title:\s*(.+)$', re.MULTILINE)


def url_encode_path(path: str) -> str:
    return quote(path, safe='/-_.~')


def slugify_title(title: str) -> str:
    """Convert heading/title text to Hugo-style anchor slug."""
    slug = title.lower()
    slug = re.sub(r'[^\w\s\u4e00-\u9fa5-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug.strip('-')


slugify_heading = slugify_title


def parse_front_matter_title(content: str) -> Optional[str]:
    match = FRONT_MATTER_PATTERN.match(content)
    if not match:
        return None
    title_match = TITLE_PATTERN.search(match.group(1))
    if not title_match:
        return None
    title = title_match.group(1).strip()
    if (title.startswith('"') and title.endswith('"')) or (
        title.startswith("'") and title.endswith("'")
    ):
        title = title[1:-1]
    return title


def parse_front_matter_draft(content: str) -> bool:
    match = FRONT_MATTER_PATTERN.match(content)
    if not match:
        return False
    draft_match = re.search(r'^draft:\s*(.+)$', match.group(1), re.MULTILINE)
    if not draft_match:
        return False
    return draft_match.group(1).strip().strip('"\'').lower() == "true"


@dataclass
class WikiIndex:
    """Index of markdown files for wiki-link resolution."""

    by_key: Dict[str, List[str]] = field(default_factory=dict)
    titles: Dict[str, str] = field(default_factory=dict)
    drafts: Dict[str, bool] = field(default_factory=dict)

    def all_paths(self) -> List[str]:
        paths = set()
        for values in self.by_key.values():
            paths.update(values)
        return sorted(paths)


def _add_index_key(index: Dict[str, List[str]], key: str, rel_path: str) -> None:
    if not key:
        return
    index.setdefault(key, [])
    if rel_path not in index[key]:
        index[key].append(rel_path)


def build_wikilink_index(content_dir: Path) -> WikiIndex:
    """
    Build wiki-link index with keys:
    - relative path (with/without .md)
    - file stem
    - front matter title
    - case-insensitive variants
    """
    index: Dict[str, List[str]] = {}
    titles: Dict[str, str] = {}
    drafts: Dict[str, bool] = {}

    for md_file in iter_content_markdown_files(content_dir):
        rel_path = md_file.relative_to(content_dir).as_posix()
        stem = md_file.stem
        without_ext = rel_path[: -len(md_file.suffix)] if md_file.suffix else rel_path

        keys = {rel_path, without_ext, stem, Path(without_ext).name}
        content = md_file.read_text(encoding='utf-8')
        title = parse_front_matter_title(content)
        drafts[rel_path] = parse_front_matter_draft(content)
        if title:
            titles[rel_path] = title
            keys.add(title)
            keys.add(title.lower())

        for key in keys:
            _add_index_key(index, key, rel_path)
            _add_index_key(index, key.lower(), rel_path)

    return WikiIndex(by_key=index, titles=titles, drafts=drafts)


def looks_like_width(value: str) -> bool:
    return bool(re.match(r'^\d+(?:px)?(?:[xX]\d+)?$', value.strip()))


def parse_wiki_link_inner(inner: str) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Parse wiki link inner text.
    Supports: target, target|alias, target|width, target#anchor, target#anchor|alias,
    and same-page heading links: #heading, #heading|alias
    """
    raw = inner.strip()
    if raw.startswith('#'):
        heading_part = raw[1:]
        alias = None
        anchor = heading_part
        if '|' in heading_part:
            anchor, alias = heading_part.split('|', 1)
            anchor = anchor.strip()
            alias = alias.strip() or None
        return '', alias, anchor or None

    anchor = None
    target = raw
    alias = None

    if '|' in target:
        left, right = target.split('|', 1)
        left = left.strip()
        right = right.strip()
        if looks_like_width(right):
            return left, right, None
        target, alias = left, right
    else:
        target = target.strip()

    if '#' in target:
        target, anchor = target.split('#', 1)
        target = target.strip()
        anchor = anchor.strip() or None

    return target, alias, anchor


def _candidate_keys(normalized: str) -> List[str]:
    candidates = [normalized]
    if normalized.endswith('.md'):
        candidates.append(normalized[:-3])
    else:
        candidates.append(f'{normalized}.md')
    name = Path(normalized).name
    candidates.append(name)
    stem = Path(name).stem
    if stem != name:
        candidates.append(stem)
    return candidates


def resolve_document_target(
    target: str,
    wiki_index: WikiIndex | Dict[str, List[str]],
    fuzzy: bool = False,
    link_manifest=None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Resolve wiki target to (relative_path, anchor, ambiguity_reason).
    ambiguity_reason is set when multiple matches exist.
    """
    by_key = wiki_index.by_key if isinstance(wiki_index, WikiIndex) else wiki_index

    parsed_target, alias, anchor = parse_wiki_link_inner(target)
    normalized = parsed_target.strip().replace('\\', '/')

    if link_manifest is not None:
        manifest_path = link_manifest.resolve(normalized)
        if manifest_path:
            return manifest_path, anchor, None

    for key in _candidate_keys(normalized):
        key = key.strip()
        if not key:
            continue
        for lookup in (key, key.lower()):
            if lookup in by_key:
                paths = by_key[lookup]
                if len(paths) == 1:
                    return paths[0], anchor, None
                return None, anchor, f"multiple matches: {paths}"

    if fuzzy:
        fuzzy_match = fuzzy_resolve_document(parsed_target, wiki_index)
        if fuzzy_match:
            return fuzzy_match[0], anchor, fuzzy_match[1]

    return None, anchor, None


def fuzzy_resolve_document(
    target: str,
    wiki_index: WikiIndex | Dict[str, List[str]],
    limit: int = 5,
    cutoff: float = 0.55,
) -> Optional[Tuple[str, Optional[str]]]:
    """Return best fuzzy match as (path, reason) or None."""
    by_key = wiki_index.by_key if isinstance(wiki_index, WikiIndex) else wiki_index
    titles = wiki_index.titles if isinstance(wiki_index, WikiIndex) else {}

    target_lower = target.lower().strip()
    scored: List[Tuple[float, str]] = []

    for rel_path in by_key.get(Path(target).stem.lower(), []):
        scored.append((1.0, rel_path))

    all_paths = set()
    for paths in by_key.values():
        all_paths.update(paths)

    for rel_path in all_paths:
        stem = Path(rel_path).stem
        title = titles.get(rel_path, stem)
        for candidate in {stem, title, rel_path, Path(rel_path).name}:
            ratio = SequenceMatcher(None, target_lower, candidate.lower()).ratio()
            if ratio >= cutoff:
                scored.append((ratio, rel_path))

    if not scored:
        return None

    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_path = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else 0.0
    if best_score >= 0.95 or best_score - second_score >= 0.08:
        return best_path, f"fuzzy match ({best_score:.2f})"
    return None


def fuzzy_candidates(
    target: str,
    wiki_index: WikiIndex,
    limit: int = 8,
) -> List[Tuple[str, str, float]]:
    """Return [(path, label, score), ...] for interactive relink."""
    target_lower = target.lower().strip()
    results: Dict[str, Tuple[str, float]] = {}

    for rel_path in wiki_index.all_paths():
        stem = Path(rel_path).stem
        title = wiki_index.titles.get(rel_path, stem)
        for label in {stem, title}:
            score = SequenceMatcher(None, target_lower, label.lower()).ratio()
            if rel_path not in results or score > results[rel_path][1]:
                results[rel_path] = (label, score)

        score = SequenceMatcher(None, target_lower, rel_path.lower()).ratio()
        if rel_path not in results or score > results[rel_path][1]:
            results[rel_path] = (rel_path, score)

    ranked = sorted(
        ((path, label, score) for path, (label, score) in results.items()),
        key=lambda item: (-item[2], item[0]),
    )
    return ranked[:limit]


def wiki_link_for_path(rel_path: str, anchor: Optional[str] = None, alias: Optional[str] = None) -> str:
    without_ext = rel_path[:-3] if rel_path.endswith('.md') else rel_path
    target = without_ext
    if anchor:
        target = f'{target}#{anchor}'
    if alias:
        return f'[[{target}|{alias}]]'
    return f'[[{target}]]'


def simplify_document_wiki_links(content: str, link_manifest) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        is_embed = match.group(1) is not None
        if is_embed:
            return match.group(0)
        inner = match.group(2).strip()
        target, alias, anchor = parse_wiki_link_inner(inner)
        if not target or target.startswith("#") or Path(target).suffix.lower() in IMAGE_EXTENSIONS:
            return match.group(0)
        rel_path = link_manifest.resolve(target)
        if not rel_path:
            return match.group(0)
        preferred = link_manifest.preferred_name(rel_path)
        new_target = f"{preferred}#{anchor}" if anchor else preferred
        if alias and alias != preferred:
            new_inner = f"{new_target}|{alias}"
        else:
            new_inner = new_target
        if new_inner == inner:
            return match.group(0)
        count += 1
        return f"[[{new_inner}]]"

    return WIKI_LINK_PATTERN.sub(replace, content), count


def relref_to_wiki(match: re.Match[str]) -> str:
    alias = match.group(1)
    rel_path = match.group(2)
    anchor = match.group(3)
    without_ext = rel_path[:-3] if rel_path.endswith('.md') else rel_path
    target = without_ext
    if anchor:
        target = f'{target}#{anchor}'
    if alias:
        return f'[[{target}|{alias}]]'
    return f'[[{target}]]'


def fix_same_page_index_links(content: str) -> Tuple[str, int]:
    """
    Fix mistaken Obsidian links like [[_index#Heading|alias]] that target
    headings in the current document. Converts to [[#Heading|alias]].
    """
    pattern = re.compile(r'\[\[_index#([^\]|]+)(?:\|([^\]]+))?\]\]')
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        heading = match.group(1)
        alias = match.group(2)
        if alias:
            return f'[[#{heading}|{alias}]]'
        return f'[[#{heading}]]'

    return pattern.sub(replace, content), count


def migrate_relref_links(content: str) -> Tuple[str, int]:
    new_content, count = RELREF_PATTERN.subn(relref_to_wiki, content)
    return new_content, count


def collect_image_references(content: str) -> List[str]:
    refs: List[str] = []
    for match in EMBED_IMAGE_PATTERN.finditer(content):
        target, _, _ = parse_wiki_link_inner(match.group(1))
        refs.append(target)
    for match in MARKDOWN_IMAGE_PATTERN.finditer(content):
        path = match.group('path').strip()
        if path.startswith('<') and path.endswith('>'):
            path = path[1:-1].strip()
        if path.startswith('/images/'):
            refs.append(path[len('/images/') :])
        else:
            refs.append(path)
    return refs


def collect_document_wiki_links(content: str) -> List[str]:
    links: List[str] = []
    for match in DOC_WIKI_PATTERN.finditer(content):
        target, _, _ = parse_wiki_link_inner(match.group(1))
        if target.startswith('#'):
            continue
        suffix = Path(target).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            continue
        links.append(match.group(1))
    return links


def find_broken_wiki_links(content: str, wiki_index: WikiIndex) -> List[Tuple[str, str]]:
    """Return list of (full_match, target) for unresolved document links."""
    broken: List[Tuple[str, str]] = []
    for match in DOC_WIKI_PATTERN.finditer(content):
        inner = match.group(1)
        target, alias, anchor = parse_wiki_link_inner(inner)
        if not target and anchor:
            continue
        if target.startswith('#'):
            continue
        suffix = Path(target).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            continue
        doc_path, _, _ = resolve_document_target(target, wiki_index, fuzzy=False)
        if not doc_path:
            broken.append((match.group(0), target))
    return broken


def transform_obsidian_links(
    content: str,
    static_images_dir: Optional[Path] = None,
    wiki_index: Optional[WikiIndex | Dict[str, List[str]]] = None,
    image_manifest=None,
    link_manifest=None,
    verbose: bool = True,
) -> str:
    """Convert Obsidian wiki syntax to Hugo-compatible markdown."""
    project_root = Path.cwd()
    static_images_dir = static_images_dir or (project_root / 'static' / 'images')
    wiki_index = wiki_index or WikiIndex()

    missing_images: List[str] = []
    unresolved_documents: List[str] = []

    def replace_func(match: re.Match[str]) -> str:
        is_embed = match.group(1) is not None
        inner = match.group(2).strip()
        target, meta, anchor_from_hash = parse_wiki_link_inner(inner)

        if not is_embed and anchor_from_hash and not target:
            title_text = anchor_from_hash
            link_text = meta or title_text
            anchor_id = slugify_title(title_text)
            if anchor_id:
                return f'[{link_text}](#{anchor_id})'
            return match.group(0)

        if not is_embed and target.startswith('#'):
            title_text = target[1:].strip()
            link_text = meta or title_text
            anchor_id = slugify_title(title_text)
            if anchor_id:
                return f'[{link_text}](#{anchor_id})'
            return match.group(0)

        width = meta if meta and looks_like_width(meta) else None
        alias = None if width else meta

        suffix = Path(target).suffix.lower()
        manifest_target = image_manifest.get(target) if image_manifest is not None else None
        image_output_target = manifest_target or target
        image_path = static_images_dir / image_output_target

        is_image = suffix in IMAGE_EXTENSIONS or image_path.exists()
        if not is_image:
            doc_path, anchor, ambiguity = resolve_document_target(
                inner if anchor_from_hash else target,
                wiki_index,
                fuzzy=True,
                link_manifest=link_manifest,
            )
            anchor = anchor or anchor_from_hash
            if doc_path:
                title = None
                if link_manifest is not None:
                    title = getattr(link_manifest, "titles", {}).get(doc_path)
                if title is None and isinstance(wiki_index, WikiIndex):
                    title = wiki_index.titles.get(doc_path)
                link_text = alias or title or Path(doc_path).stem
                is_draft = False
                if link_manifest is not None:
                    is_draft = bool(link_manifest.is_draft(doc_path))
                elif isinstance(wiki_index, WikiIndex):
                    is_draft = bool(wiki_index.drafts.get(doc_path))
                if is_draft:
                    return link_text
                relref = f'{{{{< relref "{doc_path}" >}}}}'
                if anchor:
                    relref = f'{relref}#{anchor}'
                return f'[{link_text}]({relref})'
            if ambiguity:
                unresolved_documents.append(f'{target} ({ambiguity})')
            else:
                unresolved_documents.append(target)
            return match.group(0)

        alt_text = alias or Path(target).stem
        if not image_path.exists():
            missing_images.append(image_output_target)
        encoded_target = url_encode_path(image_output_target)
        if width:
            return (
                f'<img src="/images/{encoded_target}" '
                f'alt="{alt_text}" width="{width}" loading="lazy" />'
            )
        return f'![{alt_text}](/images/{encoded_target})'

    def log_replace(match: re.Match[str]) -> str:
        if verbose:
            print(f'处理 Obsidian 链接: {match.group(0)}')
        result = replace_func(match)
        if verbose:
            print(f'  替换为: {result}')
        return result

    result = WIKI_LINK_PATTERN.sub(log_replace if verbose else replace_func, content)
    result = MORE_MARKER_PATTERN.sub('<!--more-->', result)

    if verbose:
        if missing_images:
            print(f'警告: 以下图片文件不存在于 {static_images_dir}:')
            for img in sorted(set(missing_images)):
                print(f'  - {img}')
        if unresolved_documents:
            print('警告: 以下 wiki 链接无法解析为文档，将保留原样：')
            for item in sorted(set(unresolved_documents)):
                print(f'  - {item}')

    return result
