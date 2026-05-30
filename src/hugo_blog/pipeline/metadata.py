from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from hugo_blog.llm.client import LLMMetadata
from hugo_blog.pipeline.markdown_document import MORE_RE, parse_markdown_document


MORE_MARKER = "<!-- more -->"
HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
MULTISPACE_RE = re.compile(r"\s+")
UNSAFE_SLUG_RE = re.compile(r"[^\w\u4e00-\u9fff.+-]+")


@dataclass
class FrontMatterUpdate:
    text: str
    changed: bool
    metadata_changed: bool = False
    summary_changed: bool = False
    llm_needed: bool = False
    llm_used: bool = False


def parse_front_matter(text: str) -> tuple[dict[str, Any], str, bool]:
    document = parse_markdown_document(text)
    return document.front_matter, document.body, document.has_front_matter


def dump_front_matter(metadata: dict[str, Any], body: str) -> str:
    cleaned = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, datetime):
            cleaned[key] = value.isoformat()
        elif isinstance(value, date):
            cleaned[key] = value.isoformat()
        else:
            cleaned[key] = value
    raw = yaml.safe_dump(
        cleaned,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    return f"---\n{raw}\n---\n{body.lstrip()}"


def extract_summary(body: str) -> str:
    match = MORE_RE.search(body)
    if not match:
        return ""
    before = body[: match.start()]
    return before.strip()


def needs_summary(body: str) -> bool:
    return not extract_summary(body)


def normalize_reasons(text: str) -> list[str]:
    metadata, body, has_front_matter = parse_front_matter(text)
    reasons: list[str] = []
    if not has_front_matter:
        reasons.append("front matter")
        return reasons
    if not metadata.get("title"):
        reasons.append("title")
    if not metadata.get("date"):
        reasons.append("date")
    if "draft" not in metadata:
        reasons.append("draft")
    if "description" in metadata:
        reasons.append("description")
    if not metadata.get("tags"):
        reasons.append("tags")
    if needs_summary(body):
        reasons.append("summary")
    return reasons


def insert_summary(body: str, abstract: str) -> str:
    abstract = abstract.strip()
    if not abstract or not needs_summary(body):
        return body

    heading = HEADING_RE.search(body)
    insert_at = heading.start() if heading else 0
    before = body[:insert_at].strip()
    after = body[insert_at:].lstrip()
    prefix = f"{abstract}\n\n{MORE_MARKER}\n\n"
    if before:
        prefix = f"{before}\n\n{prefix}"
    return f"{prefix}{after}"


def _file_mtime_iso(md_file: Path) -> str:
    from datetime import datetime

    if md_file.exists():
        return datetime.fromtimestamp(md_file.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_title(md_file: Path) -> str:
    if md_file.name == "index.md":
        return md_file.parent.name
    if md_file.name == "_index.md":
        return md_file.parent.name if md_file.parent.name != "content" else "首页"
    return md_file.stem


def _source_preview_path(rel_path: str) -> str:
    preview_path = "/" + rel_path
    if preview_path.endswith("/index.md"):
        preview_path = preview_path[: -len("index.md")]
    elif preview_path.endswith("/_index.md"):
        preview_path = preview_path[: -len("_index.md")]
    elif preview_path.endswith(".md"):
        preview_path = preview_path[: -len(".md")] + "/"
    return preview_path


def _parse_date_parts(raw_date: Any) -> tuple[str, str, str] | None:
    if isinstance(raw_date, datetime):
        value = raw_date
    elif isinstance(raw_date, date):
        value = datetime(raw_date.year, raw_date.month, raw_date.day)
    elif isinstance(raw_date, str) and raw_date.strip():
        text = raw_date.strip()
        try:
            value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
            if not match:
                return None
            return match.group(1), match.group(2), match.group(3)
    else:
        return None
    return f"{value.year:04d}", f"{value.month:02d}", f"{value.day:02d}"


def _urlize(value: Any) -> str:
    slug = str(value or "").strip().lower()
    slug = MULTISPACE_RE.sub("-", slug)
    slug = UNSAFE_SLUG_RE.sub("-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def _content_slug(metadata: dict[str, Any], md_file: Path) -> str:
    return _urlize(metadata.get("slug") or metadata.get("title") or normalize_title(md_file))


def preview_url_for_listing(md_file: Path, content_dir: Path, metadata: dict[str, Any], rel_path: str) -> str:
    explicit_url = str(metadata.get("url") or "").strip()
    if explicit_url:
        return explicit_url if explicit_url.startswith("/") else f"/{explicit_url}"

    parts = Path(rel_path).parts
    if not parts:
        return _source_preview_path(rel_path)

    section = parts[0]
    slug = _content_slug(metadata, md_file)
    if section == "posts":
        date_parts = _parse_date_parts(metadata.get("date"))
        if date_parts and slug:
            year, month, day = date_parts
            return f"/{year}/{month}/{day}/{slug}/"
    if section == "page" and slug:
        return f"/{slug}/"
    if section == "projects" and md_file.name != "_index.md" and slug:
        return f"/projects/{slug}/"
    return _source_preview_path(rel_path)


def ensure_metadata(
    *,
    md_file: Path,
    text: str,
    now: str | None = None,
    llm_metadata: LLMMetadata | None = None,
) -> FrontMatterUpdate:
    metadata, body, has_front_matter = parse_front_matter(text)
    original_metadata = dict(metadata)
    original_body = body

    metadata.setdefault("title", normalize_title(md_file))
    metadata.setdefault("date", now or _file_mtime_iso(md_file))
    if "draft" not in metadata:
        metadata["draft"] = True

    tags = metadata.get("tags")
    need_tags = not tags
    need_abstract = needs_summary(body)
    llm_needed = need_tags or need_abstract
    llm_used = llm_metadata is not None and (
        bool(llm_metadata.abstract.strip()) or bool(llm_metadata.normalized_tags())
    )

    if need_tags and llm_metadata:
        generated_tags = llm_metadata.normalized_tags()
        if generated_tags:
            metadata["tags"] = generated_tags

    if "description" in metadata:
        metadata.pop("description")

    if need_abstract and llm_metadata and llm_metadata.abstract.strip():
        body = insert_summary(body, llm_metadata.abstract)

    metadata_changed = metadata != original_metadata
    summary_changed = body != original_body
    if not metadata_changed and not summary_changed and has_front_matter:
        new_text = text
    else:
        new_text = dump_front_matter(metadata, body)
    return FrontMatterUpdate(
        text=new_text,
        changed=new_text != text,
        metadata_changed=metadata_changed,
        summary_changed=summary_changed,
        llm_needed=llm_needed,
        llm_used=llm_used,
    )


def metadata_for_listing(md_file: Path, content_dir: Path) -> dict[str, Any]:
    text = md_file.read_text(encoding="utf-8")
    metadata, _, _ = parse_front_matter(text)
    rel_path = md_file.relative_to(content_dir).as_posix()
    rel_parts = Path(rel_path).parts
    directory = rel_parts[1] if len(rel_parts) >= 3 and rel_parts[0] == "posts" else (rel_parts[0] if len(rel_parts) > 1 else "")
    preview_path = preview_url_for_listing(md_file, content_dir, metadata, rel_path)
    raw_date = metadata.get("date") or ""
    if isinstance(raw_date, datetime):
        date_value = raw_date.isoformat(sep=" ")
    elif isinstance(raw_date, date):
        date_value = raw_date.isoformat()
    else:
        date_value = str(raw_date)

    reasons = normalize_reasons(text)
    return {
        "path": rel_path,
        "title": metadata.get("title") or normalize_title(md_file),
        "date": date_value,
        "tags": metadata.get("tags") or [],
        "draft": bool(metadata.get("draft", True)),
        "modified": datetime.fromtimestamp(md_file.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        "directory": directory,
        "preview_url": preview_path,
        "normalize_reasons": reasons,
        "normalized": not reasons,
    }


def update_core_front_matter(md_file: Path, updates: dict[str, Any]) -> None:
    text = md_file.read_text(encoding="utf-8")
    metadata, body, _ = parse_front_matter(text)
    for key in ("title", "date", "tags", "draft"):
        if key in updates:
            metadata[key] = updates[key]
    md_file.write_text(dump_front_matter(metadata, body), encoding="utf-8")
