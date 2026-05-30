#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预处理脚本：将 Obsidian Wiki 语法 ![[...]] 转换为 Hugo 可识别的 Markdown。
在 Hugo 处理之前运行，不修改原始文件，而是创建临时副本。
"""
import hashlib
import json
import shutil
from pathlib import Path
from filelock import FileLock

from hugo_blog.paths import STATIC_IMAGES_DIR
from hugo_blog.pipeline.content_filters import iter_content_markdown_files
from hugo_blog.pipeline.image_manifest import ImageManifest
from hugo_blog.pipeline.link_manifest import LinkManifest
from hugo_blog.pipeline.metadata import normalize_reasons
from hugo_blog.pipeline.wikilinks import build_wikilink_index, transform_obsidian_links


def get_file_hash(file_path: Path) -> str:
    with open(file_path, 'rb') as file:
        return hashlib.md5(file.read()).hexdigest()


def _docs_front_matter(title: str, extra: str = "") -> str:
    suffix = f"{extra.rstrip()}\n" if extra else ""
    return f"---\ntitle: {title}\ndraft: false\n{suffix}---\n"


def _copy_preview_docs(docs_dir: Path, temp_path: Path) -> None:
    if not docs_dir.exists():
        return
    target_root = temp_path / "docs"
    target_root.mkdir(parents=True, exist_ok=True)
    index = target_root / "_index.md"
    index.write_text(
        _docs_front_matter(
            "Developer Docs",
            """menu:
  main:
    name: Docs
    weight: -20
    params:
      icon: link
""",
        ) + """
<nav>
  <a href="/docs/">Docs</a> |
  <a href="/admin/">Admin</a> |
  <a href="/">Preview</a>
</nav>

# Developer Docs
""",
        encoding="utf-8",
    )
    for source in sorted(docs_dir.rglob("*.md")):
        if "superpowers" in source.parts:
            continue
        rel_path = source.relative_to(docs_dir)
        target = target_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        title = source.stem.replace("-", " ").replace("_", " ").title()
        text = source.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            target.write_text(text, encoding="utf-8")
        else:
            target.write_text(_docs_front_matter(title) + text, encoding="utf-8")


def _write_admin_redirect(temp_path: Path, admin_port: int = 1314) -> None:
    target = temp_path / "admin" / "index.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"""---
title: Admin
draft: false
url: /admin/
menu:
  main:
    name: Admin
    weight: -10
    params:
      icon: user
---
<nav>
  <a id="docs-link" href="http://localhost:{admin_port}/docs/">Docs</a> |
  <a id="admin-link" href="http://localhost:{admin_port}/admin/">Admin</a> |
  <a href="/">Preview</a>
</nav>

# Admin

<iframe
  id="admin-frame"
  title="Blog Admin"
  src="http://localhost:{admin_port}/admin/"
  style="width: 100%; min-height: 78vh; border: 1px solid var(--card-separator-color); border-radius: 8px;"
></iframe>

<script>
  document.getElementById('admin-frame').src = window.location.protocol + '//' + window.location.hostname + ':{admin_port}/admin/';
  document.getElementById('docs-link').href = window.location.protocol + '//' + window.location.hostname + ':{admin_port}/docs/';
  document.getElementById('admin-link').href = window.location.protocol + '//' + window.location.hostname + ':{admin_port}/admin/';
</script>
""",
        encoding="utf-8",
    )


def _remove_preview_docs(temp_path: Path) -> None:
    docs_path = temp_path / "docs"
    if docs_path.exists():
        shutil.rmtree(docs_path)


def preprocess_content_dir(
    content_dir='content',
    temp_dir='.hugo_temp_content',
    force=False,
    include_docs: bool = False,
    docs_dir='docs',
):
    content_path = Path(content_dir)
    temp_path = Path(temp_dir)
    state_file = temp_path / '.preprocess_state.json'
    lock = FileLock(str(temp_path) + ".lock")

    with lock:
        return _preprocess_content_dir_locked(
            content_path=content_path,
            temp_path=temp_path,
            state_file=state_file,
            force=force,
            include_docs=include_docs,
            docs_dir=docs_dir,
        )


def _preprocess_content_dir_locked(
    *,
    content_path: Path,
    temp_path: Path,
    state_file: Path,
    force: bool,
    include_docs: bool,
    docs_dir,
):

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

    all_md_files = list(iter_content_markdown_files(content_path))
    md_files = [
        md_file
        for md_file in all_md_files
        if _should_export_markdown(md_file, content_path)
    ]
    export_paths = {md_file.relative_to(content_path).as_posix() for md_file in md_files}
    wiki_index = build_wikilink_index(content_path)
    link_manifest = LinkManifest.build(content_path)
    for md_file in all_md_files:
        rel_path = md_file.relative_to(content_path).as_posix()
        if rel_path not in export_paths:
            link_manifest.drafts[rel_path] = True
    link_manifest.save()
    static_images_dir = STATIC_IMAGES_DIR
    image_manifest = ImageManifest.load(static_images_dir)
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
            image_manifest=image_manifest,
            link_manifest=link_manifest,
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

    if include_docs:
        _remove_preview_docs(temp_path)
        _write_admin_redirect(temp_path)

    print(f'预处理完成: {len(md_files)} 个文件（更新: {updated_count}, 跳过: {skipped_count}）')
    return str(temp_path)


def _should_export_markdown(md_file: Path, content_path: Path) -> bool:
    rel_path = md_file.relative_to(content_path)
    if not rel_path.parts or rel_path.parts[0] != "posts":
        return True
    return not normalize_reasons(md_file.read_text(encoding="utf-8"))
