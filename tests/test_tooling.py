import unittest
import importlib.util
import tempfile
from pathlib import Path

from hugo_blog.preview import serve
from hugo_blog.preview.launcher import build_background_serve_command
from hugo_blog.preview.admin import BlogAdminApp
from hugo_blog.pipeline.export import preprocess_content_dir
from hugo_blog.pipeline.wikilinks import build_wikilink_index
from hugo_blog.pipeline.wikilinks import transform_obsidian_links
from hugo_blog.static_site import StaticSiteManager, static_site_manager
from hugo_blog.tools import hugo as bootstrap_tools

INIT_SPEC = importlib.util.spec_from_file_location("blog_init", Path("init.py"))


class ToolingTest(unittest.TestCase):
    def test_hugo_asset_name_for_linux_amd64(self):
        self.assertEqual(
            bootstrap_tools.hugo_asset_name(
                system="Linux",
                machine="x86_64",
                version="0.148.2",
            ),
            "hugo_extended_0.148.2_linux-amd64.tar.gz",
        )

    def test_hugo_asset_name_rejects_unsupported_platform(self):
        with self.assertRaisesRegex(RuntimeError, "Unsupported Hugo platform"):
            bootstrap_tools.hugo_asset_name(
                system="Plan9",
                machine="x86_64",
                version="0.148.2",
            )

    def test_default_hugo_path_is_project_local(self):
        self.assertEqual(
            bootstrap_tools.default_hugo_path(Path("/repo")),
            Path("/repo/.tools/hugo/hugo"),
        )

    def test_serve_command_binds_to_external_host(self):
        command = serve.build_hugo_command(
            hugo_bin=Path("/repo/.tools/hugo/hugo"),
            host="0.0.0.0",
            port=1313,
            base_url="http://192.168.88.12:1313/",
            include_drafts=True,
        )

        self.assertEqual(
            command,
            [
                "/repo/.tools/hugo/hugo",
                "server",
                "-D",
                "--bind",
                "0.0.0.0",
                "--baseURL",
                "http://192.168.88.12:1313/",
                "--port",
                "1313",
                "--contentDir",
                ".hugo_temp_content",
                "--cleanDestinationDir",
            ],
        )

    def test_background_serve_command_defaults_to_published_only(self):
        command = build_background_serve_command(
            script=Path("/repo/scripts/serve.py"),
            python_bin=Path("/repo/.venv/bin/python"),
        )

        self.assertEqual(command, [str(Path("/repo/.venv/bin/python")), "/repo/scripts/serve.py", "--no-drafts"])

    def test_static_site_manager_is_singleton_and_builds_hugo_command(self):
        self.assertIs(static_site_manager(), static_site_manager())
        manager = StaticSiteManager(project_root=Path("/repo"), hugo_bin=Path("/repo/.tools/hugo/hugo"))

        command = manager.build_command(content_dir=".hugo_temp_content", include_drafts=False, minify=True)

        self.assertEqual(command, ["/repo/.tools/hugo/hugo", "--contentDir", ".hugo_temp_content", "--minify", "--cleanDestinationDir"])

    def test_static_site_manager_validates_content_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "posts").mkdir(parents=True)
            (root / "static" / "images").mkdir(parents=True)
            (content / "posts" / "post.md").write_text("![[missing.png]]", encoding="utf-8")

            report = StaticSiteManager(project_root=root).validate_content()

            self.assertFalse(report.ok)
            self.assertEqual(report.issues[0].source_path, "posts/post.md")

    def test_serve_issues_url_uses_lan_host_for_external_bind(self):
        original = serve.detect_lan_ip
        serve.detect_lan_ip = lambda: "192.168.88.12"
        try:
            self.assertEqual(
                serve.issues_url(host="0.0.0.0", admin_port=1314),
                "http://192.168.88.12:1314/issues/",
            )
        finally:
            serve.detect_lan_ip = original

    def test_background_serve_command_can_enable_drafts(self):
        command = build_background_serve_command(
            script=Path("/repo/scripts/serve.py"),
            python_bin=Path("/repo/.venv/bin/python"),
            include_drafts=True,
        )

        self.assertNotIn("--no-drafts", command)

    def test_preview_export_includes_admin_without_copying_docs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            docs = root / "docs"
            temp = root / ".hugo_temp_content"
            content.mkdir()
            docs.mkdir()
            (temp / "docs").mkdir(parents=True)
            (temp / "docs" / "old.md").write_text("# Old\n", encoding="utf-8")
            (content / "post.md").write_text("# Post\n", encoding="utf-8")
            (docs / "architecture.md").write_text("# Architecture\n\nDetails\n", encoding="utf-8")

            preprocess_content_dir(
                content_dir=content,
                temp_dir=temp,
                force=False,
                include_docs=True,
                docs_dir=docs,
            )

            self.assertTrue((temp / "admin" / "index.md").exists())
            self.assertFalse((temp / "docs").exists())

    def test_export_normalizes_spaced_more_marker_for_hugo(self):
        transformed = transform_obsidian_links("摘要\n\n<!-- more -->\n\n# 标题", verbose=False)

        self.assertIn("<!--more-->", transformed)
        self.assertNotIn("<!-- more -->", transformed)

    def test_export_skips_pending_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            temp = root / ".hugo_temp_content"
            (content / "pending").mkdir(parents=True)
            (content / "pending" / "note.md").write_text("# Pending\n", encoding="utf-8")
            (content / "post.md").write_text("# Post\n", encoding="utf-8")

            preprocess_content_dir(content_dir=content, temp_dir=temp, force=True)

            self.assertTrue((temp / "post.md").exists())
            self.assertFalse((temp / "pending" / "note.md").exists())

    def test_export_skips_unnormalized_posts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            temp = root / ".hugo_temp_content"
            (content / "posts").mkdir(parents=True)
            (content / "page").mkdir(parents=True)
            (content / "posts" / "bad.md").write_text("# Bad\n\n## Looks Like Card\n", encoding="utf-8")
            (content / "posts" / "good.md").write_text(
                "---\ntitle: Good\ndate: 2026-01-01T00:00:00+08:00\ntags:\n- ok\ndraft: false\n---\n摘要\n\n<!--more-->\n\n# Good\n",
                encoding="utf-8",
            )
            (content / "page" / "about.md").write_text("# About\n", encoding="utf-8")

            preprocess_content_dir(content_dir=content, temp_dir=temp, force=True)

            self.assertFalse((temp / "posts" / "bad.md").exists())
            self.assertTrue((temp / "posts" / "good.md").exists())
            self.assertTrue((temp / "page" / "about.md").exists())

    def test_wikilink_index_skips_pending_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pending").mkdir()
            (root / "pending" / "Draft.md").write_text("---\ntitle: Draft\n---\n", encoding="utf-8")
            (root / "Published.md").write_text("---\ntitle: Published\n---\n", encoding="utf-8")

            index = build_wikilink_index(root)

            self.assertNotIn("Draft", index.by_key)
            self.assertIn("Published", index.by_key)

    def test_export_does_not_emit_relref_to_draft_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "posts").mkdir()
            (root / "posts" / "published.md").write_text("---\ntitle: Published\n---\n", encoding="utf-8")
            (root / "posts" / "draft.md").write_text("---\ntitle: Draft\ndraft: true\n---\n", encoding="utf-8")
            index = build_wikilink_index(root)

            transformed = transform_obsidian_links("[[Draft]]", wiki_index=index, verbose=False)

            self.assertEqual(transformed, "Draft")
            self.assertNotIn("relref", transformed)

    def test_export_does_not_emit_relref_to_unnormalized_post(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            temp = root / ".hugo_temp_content"
            (content / "posts").mkdir(parents=True)
            (content / "projects" / "demo").mkdir(parents=True)
            (content / "posts" / "bad.md").write_text("# Bad\n", encoding="utf-8")
            (content / "projects" / "demo" / "index.md").write_text(
                "---\ntitle: Demo\n---\n[[bad|Bad Post]]\n",
                encoding="utf-8",
            )

            preprocess_content_dir(content_dir=content, temp_dir=temp, force=True)

            text = (temp / "projects" / "demo" / "index.md").read_text(encoding="utf-8")
            self.assertIn("Bad Post", text)
            self.assertNotIn("relref", text)

    def test_admin_skips_pending_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            (content / "pending").mkdir(parents=True)
            (content / "posts").mkdir(parents=True)
            (content / "pending" / "note.md").write_text("# Pending\n", encoding="utf-8")
            (content / "posts" / "post.md").write_text("# Post\n", encoding="utf-8")

            pages = BlogAdminApp(project_root=root, content_dir=content).list_pages()

            self.assertEqual([page["path"] for page in pages], ["posts/post.md"])

    def test_previous_preview_pid_file_is_stopped_before_start(self):
        calls = []

        class FakeProcess:
            def __init__(self, poll_result=None):
                self.poll_result = poll_result

            def poll(self):
                return self.poll_result

            def terminate(self):
                calls.append("terminate")

            def wait(self, timeout):
                calls.append(("wait", timeout))

        with tempfile.TemporaryDirectory() as temp_dir:
            pid_file = Path(temp_dir) / ".hugo-preview.pid"
            pid_file.write_text("12345", encoding="utf-8")

            stopped = serve.stop_previous_preview(
                pid_file=pid_file,
                current_pid=999,
                process_factory=lambda pid: FakeProcess(),
            )

        self.assertTrue(stopped)
        self.assertEqual(calls, ["terminate", ("wait", 5)])

    def test_hugo_version_parser(self):
        blog_init = importlib.util.module_from_spec(INIT_SPEC)
        INIT_SPEC.loader.exec_module(blog_init)

        self.assertEqual(
            blog_init.parse_hugo_version(
                "hugo v0.148.2-40c3d8233d4b123eff74725e5766fc6272f0a84d+extended linux/amd64"
            ),
            "0.148.2",
        )

    def test_env_content_exports_local_paths(self):
        blog_init = importlib.util.module_from_spec(INIT_SPEC)
        INIT_SPEC.loader.exec_module(blog_init)

        env = blog_init.build_shell_env(
            base_env={"PATH": "/usr/bin"},
            project_root=Path("/repo"),
            python_bin=Path("/repo/.venv/bin/python"),
            hugo_bin=Path("/repo/.tools/hugo/hugo"),
        )
        content = blog_init.build_env_content(
            project_root=Path("/repo"),
            python_bin=Path("/repo/.venv/bin/python"),
            hugo_bin=Path("/repo/.tools/hugo/hugo"),
            env=env,
        )

        self.assertIn("export VIRTUAL_ENV=/repo/.venv", content)
        self.assertIn("export PYTHON=/repo/.venv/bin/python", content)
        self.assertIn("export HUGO_BIN=/repo/.tools/hugo/hugo", content)
        self.assertIn("export PATH=/repo/.venv/bin:/repo/.tools/hugo:/usr/bin", content)

    def test_shell_env_puts_local_tools_first(self):
        blog_init = importlib.util.module_from_spec(INIT_SPEC)
        INIT_SPEC.loader.exec_module(blog_init)

        env = blog_init.build_shell_env(
            base_env={"PATH": "/usr/bin"},
            project_root=Path("/repo"),
            python_bin=Path("/repo/.venv/bin/python"),
            hugo_bin=Path("/repo/.tools/hugo/hugo"),
        )

        self.assertEqual(env["BLOG_PROJECT_ROOT"], "/repo")
        self.assertEqual(env["VIRTUAL_ENV"], "/repo/.venv")
        self.assertEqual(env["PYTHON"], "/repo/.venv/bin/python")
        self.assertEqual(env["HUGO_BIN"], "/repo/.tools/hugo/hugo")
        self.assertEqual(env["PATH"], "/repo/.venv/bin:/repo/.tools/hugo:/usr/bin")

    def test_merge_env_content_preserves_llm_settings(self):
        blog_init = importlib.util.module_from_spec(INIT_SPEC)
        INIT_SPEC.loader.exec_module(blog_init)

        merged = blog_init.merge_env_content(
            existing="LLM_API_KEY=secret\nDEPLOY_REPO=repo\n",
            generated="export PYTHON=/repo/.venv/bin/python\n",
        )

        self.assertIn("LLM_API_KEY=secret", merged)
        self.assertIn("DEPLOY_REPO=repo", merged)
        self.assertIn(blog_init.GENERATED_ENV_START, merged)
        self.assertIn("export PYTHON=/repo/.venv/bin/python", merged)

    def test_missing_llm_config_is_detected(self):
        blog_init = importlib.util.module_from_spec(INIT_SPEC)
        INIT_SPEC.loader.exec_module(blog_init)

        missing = blog_init.missing_llm_config({"LLM_API_KEY": "", "LLM_MODEL": ""})

        self.assertEqual(missing, ["LLM_MODEL", "LLM_API_KEY"])

    def test_llm_env_block_is_created_from_answers(self):
        blog_init = importlib.util.module_from_spec(INIT_SPEC)
        INIT_SPEC.loader.exec_module(blog_init)

        block = blog_init.build_llm_env_content(
            {
                "LLM_PROVIDER": "deepseek",
                "LLM_BASE_URL": "https://api.deepseek.com",
                "LLM_MODEL": "deepseek-chat",
                "LLM_API_KEY": "secret",
            }
        )

        self.assertIn('LLM_PROVIDER="deepseek"', block)
        self.assertIn('LLM_MODEL="deepseek-chat"', block)
        self.assertIn('LLM_API_KEY="secret"', block)


if __name__ == "__main__":
    unittest.main()
