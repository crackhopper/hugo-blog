from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from hugo_blog.pipeline.content_filters import is_skipped_content_path
from hugo_blog.pipeline.metadata import metadata_for_listing

CONTENT_SCOPES = {"normal", "pending"}


def iter_managed_markdown_files(content_dir: Path, *, scope: str = "normal") -> Iterator[Path]:
    if scope not in CONTENT_SCOPES:
        raise ValueError(f"unknown content scope: {scope}")

    for path in sorted(content_dir.rglob("*.md")):
        is_pending = is_skipped_content_path(path, content_dir)
        if scope == "normal" and is_pending:
            continue
        if scope == "pending" and not is_pending:
            continue
        yield path


def list_content_pages(content_dir: Path, *, scope: str = "normal") -> list[dict]:
    pages = []
    for path in iter_managed_markdown_files(content_dir, scope=scope):
        item = metadata_for_listing(path, content_dir)
        item["scope"] = "pending" if item["path"].startswith("pending/") else "normal"
        pages.append(item)
    return pages
