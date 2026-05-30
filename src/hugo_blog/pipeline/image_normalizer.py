from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from hugo_blog.pipeline.image_manifest import ImageManifest
from hugo_blog.pipeline.metadata import normalize_title, parse_front_matter
from hugo_blog.pipeline.wikilinks import EMBED_IMAGE_PATTERN, IMAGE_EXTENSIONS, parse_wiki_link_inner, slugify_heading

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
SAFE_CHAR_PATTERN = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")
UNDERSCORE_PATTERN = re.compile(r"_+")


@dataclass
class ImageNormalizeResult:
    changed: bool = False
    warnings: list[str] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)
    content: str | None = None


def safe_slug(value: str) -> str:
    slug = SAFE_CHAR_PATTERN.sub("_", value.strip())
    slug = UNDERSCORE_PATTERN.sub("_", slug)
    return slug.strip("_") or "image"


def normalize_markdown_images(
    md_file: Path,
    *,
    content_dir: Path,
    static_images_dir: Path,
) -> ImageNormalizeResult:
    content = md_file.read_text(encoding="utf-8")
    metadata, _, _ = parse_front_matter(content)
    manifest = ImageManifest.load(static_images_dir)
    article_slug = safe_slug(str(metadata.get("title") or normalize_title(md_file)))
    bucket = bucket_for_markdown(md_file, metadata)
    headings = parse_headings(content)
    section_counters: dict[str, int] = {}
    replacements: dict[str, str] = {}
    result = ImageNormalizeResult()

    for match in EMBED_IMAGE_PATTERN.finditer(content):
        inner = match.group(1)
        target, width_meta, _ = parse_wiki_link_inner(inner)
        ext = Path(target).suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            continue

        link_name = Path(target).name
        resolved = manifest.resolve(link_name)
        if resolved and resolved.exists():
            continue

        candidates = manifest.find_by_basename(link_name)
        if not candidates:
            continue
        source = candidates[0]
        if len(candidates) > 1:
            result.warnings.append(f"{link_name}: 多个候选，使用 {source.relative_to(static_images_dir).as_posix()}")

        section = section_for_position(headings, match.start())
        section_slug = safe_slug(section)
        section_counters[section_slug] = section_counters.get(section_slug, 0) + 1
        new_name = unique_image_name(
            images_dir=static_images_dir,
            bucket=bucket,
            article_slug=article_slug,
            section_slug=section_slug,
            index=section_counters[section_slug],
            ext=ext,
        )
        rel_target = f"{bucket}/{new_name}"
        target_path = static_images_dir / rel_target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target_path.resolve():
            source.rename(target_path)
        manifest.set(new_name, rel_target)
        replacements[inner] = f"{new_name}|{width_meta}" if width_meta else new_name
        result.renamed.append((link_name, rel_target))

    if replacements:
        updated = content
        for old_inner, new_inner in replacements.items():
            updated = updated.replace(f"![[{old_inner}]]", f"![[{new_inner}]]")
        md_file.write_text(updated, encoding="utf-8")
        manifest.save()
        result.changed = True
        result.content = updated
    return result


def bucket_for_markdown(md_file: Path, metadata: dict) -> str:
    value = metadata.get("date")
    when: datetime
    if isinstance(value, datetime):
        when = value
    elif isinstance(value, date):
        when = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            when = datetime.fromisoformat(text)
        except ValueError:
            when = datetime.fromtimestamp(md_file.stat().st_mtime)
    else:
        when = datetime.fromtimestamp(md_file.stat().st_mtime)
    return f"{when.year:04d}/{when.month:02d}"


def parse_headings(content: str) -> list[tuple[int, str]]:
    return [(match.start(), match.group(2).strip()) for match in HEADING_PATTERN.finditer(content)]


def section_for_position(headings: list[tuple[int, str]], pos: int) -> str:
    current = "intro"
    for start, title in headings:
        if start <= pos:
            current = slugify_heading(title) or title or "intro"
        else:
            break
    return current


def unique_image_name(
    *,
    images_dir: Path,
    bucket: str,
    article_slug: str,
    section_slug: str,
    index: int,
    ext: str,
) -> str:
    current = index
    while True:
        name = f"{article_slug}-{section_slug}-{current:02d}{ext.lower()}"
        if not (images_dir / bucket / name).exists():
            return name
        current += 1
