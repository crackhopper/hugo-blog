import json
import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.article_manifest import ArticleManifest
from hugo_blog.pipeline.metadata import (
    FrontMatterUpdate,
    ensure_metadata,
    extract_summary,
    parse_front_matter,
)
from hugo_blog.llm.client import LLMMetadata, parse_llm_metadata
from hugo_blog.pipeline.normalize import confirm_metadata_updates, require_llm_config
from hugo_blog.pipeline.normalize import normalize_content
from hugo_blog.pipeline.normalize import resolve_apply_and_llm
from hugo_blog.pipeline.normalize import format_llm_change_summary
from hugo_blog.pipeline.normalize import ordered_markdown_files


class MetadataNormalizerTest(unittest.TestCase):
    def test_adds_front_matter_without_description_and_summary_before_first_header(self):
        text = "# Vulkan\n正文内容\n"

        updated = ensure_metadata(
            md_file=Path("content/posts/Vulkan.md"),
            text=text,
            now="2026-05-30T13:00:00+08:00",
            llm_metadata=LLMMetadata(abstract="这是一篇 Vulkan 入门摘要。", tags=["vulkan", "graphics"]),
        )

        metadata, body, _ = parse_front_matter(updated.text)
        self.assertEqual(metadata["title"], "Vulkan")
        self.assertEqual(metadata["date"], "2026-05-30T13:00:00+08:00")
        self.assertEqual(metadata["tags"], ["vulkan", "graphics"])
        self.assertIs(metadata["draft"], True)
        self.assertNotIn("description", metadata)
        self.assertTrue(body.startswith("这是一篇 Vulkan 入门摘要。\n\n<!-- more -->\n\n# Vulkan"))

    def test_does_not_override_existing_draft_false_or_non_empty_tags(self):
        text = """---
title: 已发布
date: 2025-11-11T21:29:13+08:00
tags:
  - c++
draft: false
---
# Header
正文
"""

        updated = ensure_metadata(
            md_file=Path("content/posts/cpp.md"),
            text=text,
            now="2026-05-30T13:00:00+08:00",
            llm_metadata=LLMMetadata(abstract="摘要。", tags=["ignored"]),
        )

        metadata, _, _ = parse_front_matter(updated.text)
        self.assertIs(metadata["draft"], False)
        self.assertEqual(metadata["tags"], ["c++"])
        self.assertIn("date: '2025-11-11T21:29:13+08:00'", updated.text)

    def test_existing_more_marker_counts_as_summary(self):
        body = "已有摘要。\n\n<!--more-->\n\n# Header\n正文"
        self.assertEqual(extract_summary(body), "已有摘要。")

        updated = ensure_metadata(
            md_file=Path("content/posts/has-summary.md"),
            text=f"---\ntitle: Has Summary\n---\n{body}",
            now="2026-05-30T13:00:00+08:00",
            llm_metadata=LLMMetadata(abstract="新摘要。", tags=["tag"]),
        )

        self.assertEqual(updated.text.count("<!--more-->"), 1)
        self.assertIn("已有摘要。", updated.text)
        self.assertNotIn("新摘要。", updated.text)

    def test_complete_front_matter_and_summary_are_skipped(self):
        text = """---
title: 完整文章
date: '2025-11-11T21:29:13+08:00'
tags:
  - vulkan
draft: false
---
已有摘要。

<!--more-->

# Header
正文
"""

        updated = ensure_metadata(
            md_file=Path("content/posts/full.md"),
            text=text,
            now="2026-05-30T13:00:00+08:00",
            llm_metadata=None,
        )

        self.assertFalse(updated.changed)
        self.assertFalse(updated.metadata_changed)
        self.assertFalse(updated.summary_changed)

    def test_normalize_records_successful_manifest_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            images = Path(temp_dir) / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (content / "posts" / "post.md").write_text(
                "---\ntitle: Post\ndate: 2026-01-01T00:00:00+08:00\ntags:\n- ok\ndraft: true\n---\n摘要\n\n<!-- more -->\n\n# Body\n",
                encoding="utf-8",
            )

            normalize_content(
                content_dir=content,
                images_dir=images,
                apply=True,
                skip_delete=True,
                normalize_metadata=True,
                use_llm=False,
            )

            record = ArticleManifest.load(content).by_path("posts/post.md")
            self.assertTrue(record.normalized_fingerprint.startswith("b2:"))
            self.assertRegex(record.normalized_at, r"^\d{4}-\d{2}-\d{2}T")

    def test_existing_front_matter_summary_without_llm_does_not_add_empty_tags(self):
        text = """---
title: 已有文章
date: '2025-11-11T21:29:13+08:00'
draft: true
---
已有摘要。

<!--more-->

# Header
正文
"""

        updated = ensure_metadata(
            md_file=Path("content/posts/existing.md"),
            text=text,
            now="2026-05-30T13:00:00+08:00",
            llm_metadata=None,
        )

        self.assertFalse(updated.changed)
        self.assertNotIn("tags:", updated.text)

    def test_parse_llm_metadata_json(self):
        parsed = parse_llm_metadata('{"abstract": "摘要", "tags": ["C++", "图形学"]}')
        self.assertEqual(parsed, LLMMetadata(abstract="摘要", tags=["C++", "图形学"]))

    def test_normalizer_requires_llm_when_enabled(self):
        with self.assertRaisesRegex(RuntimeError, "LLM"):
            require_llm_config(None)

    def test_normalize_defaults_to_apply_and_llm(self):
        apply, use_llm = resolve_apply_and_llm(dry_run=False, no_llm=False)
        self.assertTrue(apply)
        self.assertTrue(use_llm)

    def test_dry_run_disables_llm(self):
        apply, use_llm = resolve_apply_and_llm(dry_run=True, no_llm=False)
        self.assertFalse(apply)
        self.assertFalse(use_llm)

    def test_default_apply_requires_confirmation_for_metadata_updates(self):
        self.assertFalse(confirm_metadata_updates(count=1, apply=True, apply_all=False, prompt=lambda _: "n"))
        self.assertTrue(confirm_metadata_updates(count=1, apply=True, apply_all=False, prompt=lambda _: "y"))

    def test_apply_all_skips_metadata_confirmation(self):
        self.assertTrue(confirm_metadata_updates(count=1, apply=True, apply_all=True, prompt=lambda _: "n"))

    def test_non_interactive_metadata_confirmation_defaults_to_no(self):
        def raise_eof(_: str) -> str:
            raise EOFError

        self.assertFalse(confirm_metadata_updates(count=1, apply=True, apply_all=False, prompt=raise_eof))

    def test_llm_change_summary_prints_generated_fields(self):
        summary = format_llm_change_summary(
            file_name="post.md",
            metadata=LLMMetadata(abstract="摘要内容", tags=["cpp", "vulkan"]),
        )

        self.assertIn("post.md", summary)
        self.assertIn("摘要内容", summary)
        self.assertIn("cpp, vulkan", summary)

    def test_ordered_markdown_files_prioritizes_missing_front_matter_then_dates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            posts = root / "posts"
            posts.mkdir()
            no_front_old = posts / "no-front-old.md"
            no_front_new = posts / "no-front-new.md"
            dated_old = posts / "dated-old.md"
            dated_new = posts / "dated-new.md"

            no_front_old.write_text("# Old\n", encoding="utf-8")
            no_front_new.write_text("# New\n", encoding="utf-8")
            dated_old.write_text("---\ntitle: Old\ndate: 2024-01-01T00:00:00+08:00\n---\n正文\n", encoding="utf-8")
            dated_new.write_text("---\ntitle: New\ndate: 2025-01-01T00:00:00+08:00\n---\n正文\n", encoding="utf-8")

            import os

            os.utime(no_front_old, (100, 100))
            os.utime(no_front_new, (200, 200))

            ordered = [path.name for path in ordered_markdown_files(root)]

        self.assertEqual(ordered, ["no-front-new.md", "no-front-old.md", "dated-new.md", "dated-old.md"])

    def test_ordered_markdown_files_skips_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pending = root / "pending"
            pending.mkdir()
            posts = root / "posts"
            posts.mkdir()
            (pending / "note.md").write_text("# Pending\n", encoding="utf-8")
            (posts / "post.md").write_text("# Post\n", encoding="utf-8")

            ordered = [path.relative_to(root).as_posix() for path in ordered_markdown_files(root)]

        self.assertEqual(ordered, ["posts/post.md"])

    def test_ordered_markdown_files_only_includes_posts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "posts").mkdir()
            (root / "page" / "about").mkdir(parents=True)
            (root / "projects" / "demo").mkdir(parents=True)
            (root / "posts" / "post.md").write_text("# Post\n", encoding="utf-8")
            (root / "page" / "about" / "index.md").write_text("# About\n", encoding="utf-8")
            (root / "projects" / "demo" / "index.md").write_text("# Project\n", encoding="utf-8")

            ordered = [path.relative_to(root).as_posix() for path in ordered_markdown_files(root)]

        self.assertEqual(ordered, ["posts/post.md"])

    def test_ordered_markdown_files_can_filter_by_relative_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "posts" / "a").mkdir(parents=True)
            (root / "posts" / "b").mkdir(parents=True)
            (root / "posts" / "a" / "same.md").write_text("# A\n", encoding="utf-8")
            (root / "posts" / "b" / "same.md").write_text("# B\n", encoding="utf-8")

            ordered = [
                path.relative_to(root).as_posix()
                for path in ordered_markdown_files(root, "posts/b/same.md")
            ]

        self.assertEqual(ordered, ["posts/b/same.md"])

    def test_review_each_restarts_preview_after_confirmed_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (content / "posts" / "skip.md").write_text("# Skip\n", encoding="utf-8")
            (content / "posts" / "apply.md").write_text("# Apply\n", encoding="utf-8")
            restarts = []
            answers = iter(["n", "y"])

            report = normalize_content(
                content_dir=content,
                images_dir=images,
                apply=True,
                skip_delete=True,
                skip_rename=True,
                skip_relref=True,
                use_llm=False,
                review_each=True,
                restart_preview=lambda: restarts.append("restart"),
                review_prompt=lambda _: next(answers),
            )

            self.assertEqual(report.metadata_updates, 1)
            self.assertEqual(restarts, ["restart"])


if __name__ == "__main__":
    unittest.main()
