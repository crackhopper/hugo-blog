from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hugo_blog.pipeline.article_manifest import reconcile_article_manifest
from hugo_blog.pipeline.content_filters import iter_content_markdown_files
from hugo_blog.pipeline.link_manifest import LinkManifest
from hugo_blog.pipeline.metadata import metadata_for_listing, update_core_front_matter
from hugo_blog.pipeline.normalize_service import normalize_article
from hugo_blog.pipeline.wikilinks import (
    IMAGE_EXTENSIONS,
    WIKI_LINK_PATTERN,
    parse_wiki_link_inner,
)


@dataclass
class RefactorResult:
    old_path: str
    new_path: str
    updated_links: int
    page: dict


def refactor_article(
    *,
    content_dir: Path,
    static_images_dir: Path,
    source_rel_path: str,
    target_rel_path: str,
    title: str | None = None,
    use_llm: bool = True,
) -> RefactorResult:
    source = _content_markdown_path(content_dir, source_rel_path, must_exist=True)
    target = _content_markdown_path(content_dir, target_rel_path, must_exist=False)
    old_rel = source.relative_to(content_dir).as_posix()
    new_rel = target.relative_to(content_dir).as_posix()
    if old_rel == new_rel and title is None:
        return RefactorResult(
            old_path=old_rel,
            new_path=new_rel,
            updated_links=0,
            page=metadata_for_listing(source, content_dir),
        )
    if not old_rel.startswith("posts/") and not old_rel.startswith("pending/"):
        raise ValueError("refactor only supports posts or pending content")
    if target.exists() and source.resolve() != target.resolve():
        raise FileExistsError(new_rel)

    before_manifest = LinkManifest.build(content_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        source.rename(target)

    if title is not None:
        update_core_front_matter(target, {"title": title})

    after_manifest = LinkManifest.build(content_dir)
    replacement = after_manifest.preferred.get(new_rel, new_rel.removesuffix(".md"))
    updated_links = update_article_references(
        content_dir=content_dir,
        old_manifest=before_manifest,
        old_rel_path=old_rel,
        new_target=replacement,
    )
    after_manifest = LinkManifest.build(content_dir)
    after_manifest.save()
    reconcile_article_manifest(content_dir)
    if new_rel.startswith("posts/"):
        normalize_article(
            content_dir=content_dir,
            static_images_dir=static_images_dir,
            rel_path=new_rel,
            use_llm=use_llm,
        )
    return RefactorResult(
        old_path=old_rel,
        new_path=new_rel,
        updated_links=updated_links,
        page=metadata_for_listing(target, content_dir),
    )


def update_article_references(
    *,
    content_dir: Path,
    old_manifest: LinkManifest,
    old_rel_path: str,
    new_target: str,
) -> int:
    total = 0
    for md_file in iter_content_markdown_files(content_dir):
        original = md_file.read_text(encoding="utf-8")
        updated, count = _replace_references(original, old_manifest, old_rel_path, new_target)
        if count:
            md_file.write_text(updated, encoding="utf-8")
            total += count
    return total


def _replace_references(
    text: str,
    manifest: LinkManifest,
    old_rel_path: str,
    new_target: str,
) -> tuple[str, int]:
    count = 0

    def replace(match):
        nonlocal count
        is_embed = match.group(1) is not None
        if is_embed:
            return match.group(0)
        inner = match.group(2).strip()
        target, alias, anchor = parse_wiki_link_inner(inner)
        if not target or target.startswith("#") or Path(target).suffix.lower() in IMAGE_EXTENSIONS:
            return match.group(0)
        resolved = manifest.resolve(target)
        if resolved != old_rel_path:
            return match.group(0)
        next_target = f"{new_target}#{anchor}" if anchor else new_target
        next_inner = f"{next_target}|{alias}" if alias else next_target
        if next_inner == inner:
            return match.group(0)
        count += 1
        return f"[[{next_inner}]]"

    return WIKI_LINK_PATTERN.sub(replace, text), count


def _content_markdown_path(content_dir: Path, rel_path: str, *, must_exist: bool) -> Path:
    target = (content_dir / rel_path).resolve()
    content_root = content_dir.resolve()
    if content_root not in target.parents and target != content_root:
        raise ValueError("path escapes content dir")
    if target.suffix != ".md":
        raise ValueError("target must be markdown")
    if must_exist and not target.exists():
        raise FileNotFoundError(rel_path)
    return target
