from __future__ import annotations

from pathlib import Path


SKIPPED_CONTENT_DIRS = {"pending"}
PROCESSABLE_CONTENT_SECTIONS = {"posts"}


def is_skipped_content_path(path: Path, content_dir: Path) -> bool:
    try:
        rel_path = path.relative_to(content_dir)
    except ValueError:
        return False
    return bool(rel_path.parts and rel_path.parts[0] in SKIPPED_CONTENT_DIRS)


def iter_content_markdown_files(content_dir: Path):
    for md_file in sorted(content_dir.rglob("*.md")):
        if is_skipped_content_path(md_file, content_dir):
            continue
        yield md_file


def is_processable_content_path(path: Path, content_dir: Path) -> bool:
    try:
        rel_path = path.relative_to(content_dir)
    except ValueError:
        return False
    return bool(rel_path.parts and rel_path.parts[0] in PROCESSABLE_CONTENT_SECTIONS)


def iter_processable_markdown_files(content_dir: Path):
    for md_file in iter_content_markdown_files(content_dir):
        if is_processable_content_path(md_file, content_dir):
            yield md_file
