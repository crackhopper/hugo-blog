import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from hugo_blog.preview.admin import BlogAdminApp, admin_ui_dist_dir, admin_ui_index_path, make_handler


class AdminServerTest(unittest.TestCase):
    def test_list_pages_filters_drafts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            posts = content / "posts"
            posts.mkdir(parents=True)
            (posts / "draft.md").write_text("---\ntitle: Draft\ndraft: true\n---\nbody", encoding="utf-8")
            (posts / "published.md").write_text("---\ntitle: Published\ndraft: false\n---\nbody", encoding="utf-8")

            class FakeSite:
                def preprocess_preview(self, *, force: bool):
                    return None

            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())

            drafts = app.list_pages(status="draft")
            self.assertEqual([page["title"] for page in drafts], ["Draft"])

    def test_list_pages_defaults_to_modified_desc_and_adds_admin_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            math_dir = content / "posts" / "数学"
            render_dir = content / "posts" / "renderer"
            math_dir.mkdir(parents=True)
            render_dir.mkdir(parents=True)
            old = math_dir / "old.md"
            new = render_dir / "new.md"
            old.write_text("---\ntitle: Old\ndate: 2024-01-01T00:00:00+08:00\ndraft: false\n---\n", encoding="utf-8")
            new.write_text("---\ntitle: New\ndate: 2025-01-01T00:00:00+08:00\ndraft: true\n---\n", encoding="utf-8")
            import os

            os.utime(old, (100, 100))
            os.utime(new, (200, 200))

            pages = BlogAdminApp(project_root=root, content_dir=content).list_pages(status="all")

            self.assertEqual([page["title"] for page in pages], ["New", "Old"])
            self.assertEqual(pages[0]["directory"], "renderer")
            self.assertIn("modified", pages[0])
            self.assertEqual(pages[0]["preview_url"], "/2025/01/01/new/")
            self.assertIn("normalized", pages[0])
            self.assertIn("normalize_reasons", pages[0])

    def test_list_pages_uses_hugo_permalinks_for_preview_urls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts" / "数学").mkdir(parents=True)
            (content / "posts" / "数学" / "四元数原理.md").write_text(
                "---\ntitle: 四元数原理\ndate: 2026-05-30T14:36:13+08:00\ndraft: true\n---\nbody",
                encoding="utf-8",
            )

            pages = {page["path"]: page for page in BlogAdminApp(project_root=root, content_dir=content).list_pages(status="all")}

            self.assertEqual(pages["posts/数学/四元数原理.md"]["preview_url"], "/2026/05/30/四元数原理/")

    def test_list_pages_marks_normalized_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            posts = content / "posts"
            posts.mkdir(parents=True)
            normalized = posts / "normalized.md"
            needs_work = posts / "needs-work.md"
            normalized.write_text(
                "---\ntitle: Normalized\ndate: 2026-01-01T00:00:00+08:00\ntags:\n- ok\ndraft: false\n---\n摘要\n\n<!--more-->\n\n# Body\n",
                encoding="utf-8",
            )
            needs_work.write_text("# Body\n", encoding="utf-8")

            pages = {page["path"]: page for page in BlogAdminApp(project_root=root, content_dir=content).list_pages()}

            self.assertTrue(pages["posts/normalized.md"]["normalized"])
            self.assertFalse(pages["posts/needs-work.md"]["normalized"])
            self.assertIn("front matter", pages["posts/needs-work.md"]["normalize_reasons"])

    def test_missing_draft_field_is_not_treated_as_published(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            posts = content / "posts"
            posts.mkdir(parents=True)
            (posts / "missing-draft.md").write_text("---\ntitle: Missing Draft\n---\nbody", encoding="utf-8")
            (posts / "published.md").write_text("---\ntitle: Published\ndraft: false\n---\nbody", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content)

            published = app.list_pages(status="published")
            drafts = app.list_pages(status="draft")

            self.assertEqual([page["path"] for page in published], ["posts/published.md"])
            self.assertEqual([page["path"] for page in drafts], ["posts/missing-draft.md"])

    def test_list_pages_serializes_yaml_dates_as_strings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts").mkdir(parents=True)
            (content / "posts" / "post.md").write_text(
                "---\ntitle: Post\ndate: 2026-05-30T13:00:00+08:00\ndraft: true\n---\nbody",
                encoding="utf-8",
            )

            class FakeSite:
                def preprocess_preview(self, *, force: bool):
                    return None

            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())

            pages = app.list_pages(status="all")
            self.assertEqual(pages[0]["date"], "2026-05-30 13:00:00+08:00")

    def test_update_front_matter_changes_core_fields_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            content.mkdir()
            (content / "posts").mkdir(parents=True)
            page = content / "posts" / "post.md"
            page.write_text(
                "---\ntitle: Old\ndraft: true\nmenu:\n  main:\n    weight: 1\n---\n# Body\n",
                encoding="utf-8",
            )

            app = BlogAdminApp(project_root=root, content_dir=content)
            app.update_front_matter(
                "posts/post.md",
                {
                    "title": "New",
                    "date": "2026-05-30T13:00:00+08:00",
                    "tags": ["cpp", "vulkan"],
                    "draft": False,
                },
            )

            text = page.read_text(encoding="utf-8")
            self.assertIn("title: New", text)
            self.assertIn("draft: false", text)
            self.assertIn("menu:", text)
            self.assertTrue(text.rstrip().endswith("# Body"))

    def test_update_front_matter_triggers_preview_preprocess(self):
        calls = []

        class FakeSite:
            def preprocess_preview(self, *, force: bool):
                calls.append(force)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts").mkdir(parents=True)
            page = content / "posts" / "post.md"
            page.write_text("---\ntitle: Old\ndraft: true\n---\n# Body\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())
            app.update_front_matter("posts/post.md", {"title": "New", "draft": True, "tags": [], "date": ""})

        self.assertEqual(calls, [True])

    def test_list_pages_includes_all_normal_content_except_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts").mkdir(parents=True)
            (content / "page" / "about").mkdir(parents=True)
            (content / "projects" / "demo").mkdir(parents=True)
            (content / "pending" / "posts").mkdir(parents=True)
            (content / "posts" / "post.md").write_text("---\ntitle: Post\n---\nbody", encoding="utf-8")
            (content / "page" / "about" / "index.md").write_text("---\ntitle: About\n---\nbody", encoding="utf-8")
            (content / "projects" / "demo" / "index.md").write_text("---\ntitle: Demo\n---\nbody", encoding="utf-8")
            (content / "pending" / "posts" / "old.md").write_text("---\ntitle: Old\n---\nbody", encoding="utf-8")

            pages = BlogAdminApp(project_root=root, content_dir=content).list_pages(status="all")

            self.assertEqual(
                [page["path"] for page in pages],
                ["page/about/index.md", "posts/post.md", "projects/demo/index.md"],
            )

    def test_list_pages_can_show_normal_and_pending_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts").mkdir(parents=True)
            (content / "projects").mkdir(parents=True)
            (content / "pending" / "posts").mkdir(parents=True)
            (root / "static" / "images").mkdir(parents=True)
            (content / "posts" / "post.md").write_text("---\ntitle: Post\n---\n", encoding="utf-8")
            (content / "projects" / "project.md").write_text("---\ntitle: Project\n---\n", encoding="utf-8")
            (content / "pending" / "posts" / "old.md").write_text("---\ntitle: Old\n---\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content)

            self.assertEqual(
                sorted(p["path"] for p in app.list_pages(scope="normal")),
                ["posts/post.md", "projects/project.md"],
            )
            self.assertEqual(
                sorted(p["path"] for p in app.list_pages(scope="pending")),
                ["pending/posts/old.md"],
            )

    def test_update_front_matter_allows_normal_content_under_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "page" / "about").mkdir(parents=True)
            page = content / "page" / "about" / "index.md"
            page.write_text("---\ntitle: About\n---\nbody", encoding="utf-8")

            class FakeSite:
                def preprocess_preview(self, *, force: bool):
                    return None

            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())

            result = app.update_front_matter("page/about/index.md", {"title": "New", "draft": True, "tags": [], "date": ""})

            self.assertEqual(result["title"], "New")
            self.assertIn("title: New", page.read_text(encoding="utf-8"))

    def test_validation_report_exposes_missing_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts").mkdir(parents=True)
            (root / "static" / "images").mkdir(parents=True)
            (content / "posts" / "post.md").write_text("![[missing.png]]", encoding="utf-8")

            report = BlogAdminApp(project_root=root, content_dir=content).validation_report()

            self.assertFalse(report["ok"])
            self.assertEqual(report["issues"][0]["source_path"], "posts/post.md")
            self.assertEqual(report["issues"][0]["target"], "missing.png")

    def test_content_api_rejects_path_escape_and_pending_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts").mkdir(parents=True)
            (content / "pending").mkdir(parents=True)
            (content / "posts" / "post.md").write_text("# Post\n", encoding="utf-8")
            (content / "pending" / "old.md").write_text("# Old\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content)

            with self.assertRaises(ValueError):
                app.get_content("../README.md")
            with self.assertRaises(ValueError):
                app.get_content("pending/old.md")

    def test_content_api_lists_requested_scope_and_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts").mkdir(parents=True)
            (content / "pending").mkdir(parents=True)
            (content / "posts" / "draft.md").write_text("---\ntitle: Draft\ndraft: true\n---\n", encoding="utf-8")
            (content / "pending" / "draft.md").write_text("---\ntitle: Pending Draft\ndraft: true\n---\n", encoding="utf-8")
            (content / "pending" / "published.md").write_text("---\ntitle: Pending Published\ndraft: false\n---\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/api/content?scope=pending&status=draft", timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual([page["path"] for page in payload], ["pending/draft.md"])

    def test_content_api_returns_400_for_invalid_scope(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            content.mkdir()
            app = BlogAdminApp(project_root=root, content_dir=content)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                from urllib.error import HTTPError

                with self.assertRaises(HTTPError) as context:
                    urlopen(f"http://127.0.0.1:{server.server_port}/api/content?scope=bad", timeout=5)
                self.assertEqual(context.exception.code, 400)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_normalize_page_processes_exact_post_and_rebuilds_preview(self):
        calls = []

        class FakeSite:
            def preprocess_preview(self, *, force: bool):
                calls.append(force)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts" / "a").mkdir(parents=True)
            (content / "posts" / "b").mkdir(parents=True)
            images.mkdir(parents=True)
            first = content / "posts" / "a" / "same.md"
            second = content / "posts" / "b" / "same.md"
            first.write_text("# A\n", encoding="utf-8")
            second.write_text("---\ntitle: B\ndate: 2026-01-01T00:00:00+08:00\ntags:\n- b\ndraft: false\n---\n摘要\n\n<!--more-->\n\n# B\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())
            result = app.normalize_page("posts/a/same.md", use_llm=False)

            self.assertEqual(result["path"], "posts/a/same.md")
            self.assertIn("title: same", first.read_text(encoding="utf-8"))
            self.assertEqual(second.read_text(encoding="utf-8").count("title: B"), 1)
            self.assertEqual(calls, [True])

    def test_normalize_page_rejects_non_post_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "page" / "about").mkdir(parents=True)
            (root / "static" / "images").mkdir(parents=True)
            (content / "page" / "about" / "index.md").write_text("# About\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content)

            with self.assertRaisesRegex(ValueError, "posts"):
                app.normalize_page("page/about/index.md", use_llm=False)

    def test_content_normalize_http_endpoint_decodes_paths(self):
        calls = []

        class FakeSite:
            def preprocess_preview(self, *, force: bool):
                calls.append(force)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts" / "数学").mkdir(parents=True)
            (root / "static" / "images").mkdir(parents=True)
            (content / "posts" / "数学" / "same.md").write_text("# Same\n", encoding="utf-8")
            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                encoded = quote("posts/数学/same.md", safe="")
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/content-normalize/{encoded}",
                    data=json.dumps({"use_llm": False}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

            self.assertEqual(payload["path"], "posts/数学/same.md")
            self.assertIn("title: same", (content / "posts" / "数学" / "same.md").read_text(encoding="utf-8"))
            self.assertEqual(calls, [True])

    def test_refactor_page_moves_article_and_rebuilds_preview(self):
        calls = []

        class FakeSite:
            def preprocess_preview(self, *, force: bool):
                calls.append(force)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts" / "old").mkdir(parents=True)
            (content / "posts" / "new").mkdir(parents=True)
            (root / "static" / "images").mkdir(parents=True)
            (content / "posts" / "old" / "post.md").write_text(
                "---\ntitle: Old\ndate: 2026-01-01T00:00:00+08:00\ntags:\n- old\ndraft: false\n---\n摘要\n\n<!--more-->\n\n# Body\n",
                encoding="utf-8",
            )

            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())
            result = app.refactor_page(
                {
                    "source_path": "posts/old/post.md",
                    "target_path": "posts/new/post.md",
                    "title": "New",
                    "use_llm": False,
                }
            )

            self.assertEqual(result["new_path"], "posts/new/post.md")
            self.assertEqual(result["page"]["title"], "New")
            self.assertTrue((content / "posts" / "new" / "post.md").exists())
            self.assertEqual(calls, [True])

    def test_update_content_writes_source_markdown_and_revalidates(self):
        calls = []

        class FakeSite:
            def preprocess_preview(self, *, force: bool):
                calls.append(force)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (images / "exists.png").write_bytes(b"png")
            page = content / "posts" / "post.md"
            page.write_text("![[missing.png]]", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())
            result = app.update_content("posts/post.md", "# New\n\n![[exists.png]]")

            self.assertEqual(page.read_text(encoding="utf-8"), "# New\n\n![[post-new-01.png]]")
            self.assertEqual(calls, [True])
            self.assertTrue(result["validation"]["ok"])

    def test_update_content_normalizes_short_image_reference(self):
        calls = []

        class FakeSite:
            def preprocess_preview(self, *, force: bool):
                calls.append(force)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            page = content / "posts" / "编译器" / "post.md"
            page.parent.mkdir(parents=True)
            (images / "nested").mkdir(parents=True)
            (images / "nested" / "compile.png").write_bytes(b"png")
            page.write_text("---\ntitle: Old\ndate: 2020-06-14T00:00:00+08:00\n---\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=content, site=FakeSite())
            result = app.update_content(
                "posts/编译器/post.md",
                "---\ntitle: 小白学写编译器：1.编译基础概念\ndate: 2020-06-14T00:00:00+08:00\n---\n# 一个例子\n\n![[compile.png]]\n",
            )

            expected_name = "小白学写编译器_1_编译基础概念-一个例子-01.png"
            self.assertIn(f"![[{expected_name}]]", result["content"])
            self.assertTrue((images / "2020" / "06" / expected_name).exists())
            self.assertFalse((images / "nested" / "compile.png").exists())
            self.assertEqual(calls, [True])

    def test_content_preview_returns_hugo_markdown_without_writing_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (images / "exists.png").write_bytes(b"png")
            page = content / "posts" / "post.md"
            page.write_text("![[exists.png|640]]", encoding="utf-8")

            result = BlogAdminApp(project_root=root, content_dir=content).content_preview("posts/post.md")

            self.assertIn('/images/exists.png', result["content"])
            self.assertTrue(result["validation"]["ok"])
            self.assertEqual(page.read_text(encoding="utf-8"), "![[exists.png|640]]")

    def test_list_docs_returns_navigation_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            (docs / "superpowers").mkdir(parents=True)
            (docs / "guides").mkdir(parents=True)
            (docs / "architecture.md").write_text("# Architecture\n\nDetails\n", encoding="utf-8")
            (docs / "guides" / "python-tooling.md").write_text("# Python Tooling\n\nDetails\n", encoding="utf-8")
            (docs / "superpowers" / "internal.md").write_text("# Internal\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=root / "content")

            docs_list = app.list_docs()

            self.assertEqual([item["path"] for item in docs_list], ["architecture.md", "guides/python-tooling.md"])
            self.assertEqual(docs_list[0]["title"], "Architecture")
            self.assertEqual(docs_list[1]["section"], "guides")
            self.assertEqual(docs_list[1]["parts"], ["guides", "python-tooling.md"])

    def test_list_docs_uses_reading_order_before_source_reference(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            (docs / "source").mkdir(parents=True)
            (docs / "source" / "pipeline-normalize.md").write_text("# Normalize\n", encoding="utf-8")
            (docs / "python-tooling.md").write_text("# Tooling\n", encoding="utf-8")
            (docs / "architecture.md").write_text("# Architecture\n", encoding="utf-8")
            (docs / "deployment.md").write_text("# Deployment\n", encoding="utf-8")

            docs_list = BlogAdminApp(project_root=root, content_dir=root / "content").list_docs()

            self.assertEqual(
                [item["path"] for item in docs_list],
                ["architecture.md", "python-tooling.md", "deployment.md", "source/pipeline-normalize.md"],
            )
            self.assertLess(docs_list[0]["order"], docs_list[-1]["order"])

    def test_get_doc_returns_markdown_and_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "architecture.md").write_text("# Architecture\n\n## Components\n\nDetails\n", encoding="utf-8")

            app = BlogAdminApp(project_root=root, content_dir=root / "content")

            document = app.get_doc("architecture.md")

            self.assertEqual(document["path"], "architecture.md")
            self.assertEqual(document["title"], "Architecture")
            self.assertIn("## Components", document["content"])
            self.assertEqual(
                document["headings"],
                [
                    {"level": 1, "title": "Architecture", "id": "architecture"},
                    {"level": 2, "title": "Components", "id": "components"},
                ],
            )

    def test_get_doc_rejects_paths_outside_docs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs").mkdir()
            app = BlogAdminApp(project_root=root, content_dir=root / "content")

            with self.assertRaises(ValueError):
                app.get_doc("../README.md")

    def test_admin_html_exposes_preview_draft_toggle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist = Path(temp_dir) / "src" / "hugo_blog" / "preview" / "admin_ui" / "dist"
            dist.mkdir(parents=True)
            (dist / "index.html").write_text("<div id=\"root\"></div>", encoding="utf-8")

            self.assertEqual(admin_ui_dist_dir(Path(temp_dir)), dist)
            self.assertEqual(admin_ui_index_path(Path(temp_dir)), dist / "index.html")


if __name__ == "__main__":
    unittest.main()
