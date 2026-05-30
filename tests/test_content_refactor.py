import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.article_manifest import ArticleManifest, reconcile_article_manifest
from hugo_blog.pipeline.content_refactor import refactor_article


class ContentRefactorTest(unittest.TestCase):
    def test_move_article_updates_wiki_links_and_manifests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts" / "old").mkdir(parents=True)
            (content / "posts" / "new").mkdir(parents=True)
            images.mkdir(parents=True)
            source = content / "posts" / "old" / "target.md"
            referrer = content / "posts" / "referrer.md"
            source.write_text(
                "---\ntitle: Target\ndate: 2026-01-01T00:00:00+08:00\ntags:\n- t\ndraft: false\n---\n摘要\n\n<!--more-->\n\n# Body\n",
                encoding="utf-8",
            )
            referrer.write_text("---\ntitle: Ref\n---\n[[Target#Body|read it]]\n", encoding="utf-8")
            first_manifest = reconcile_article_manifest(content)
            article_id = first_manifest.by_path("posts/old/target.md").id

            result = refactor_article(
                content_dir=content,
                static_images_dir=images,
                source_rel_path="posts/old/target.md",
                target_rel_path="posts/new/renamed.md",
                title="Renamed",
                use_llm=False,
            )

            self.assertEqual(result.old_path, "posts/old/target.md")
            self.assertEqual(result.new_path, "posts/new/renamed.md")
            self.assertEqual(result.updated_links, 1)
            self.assertFalse(source.exists())
            self.assertIn("[[Renamed#Body|read it]]", referrer.read_text(encoding="utf-8"))
            self.assertIn("title: Renamed", (content / "posts" / "new" / "renamed.md").read_text(encoding="utf-8"))
            manifest = ArticleManifest.load(content)
            self.assertEqual(manifest.by_path("posts/new/renamed.md").id, article_id)
            self.assertIn("posts/old/target.md", manifest.articles[article_id].previous_paths)
            self.assertTrue((content / "links.json").exists())

    def test_move_to_pending_updates_links_without_normalizing_pending_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            (content / "pending" / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (content / "posts" / "target.md").write_text("---\ntitle: Target\n---\n# Body\n", encoding="utf-8")
            referrer = content / "posts" / "referrer.md"
            referrer.write_text("[[Target]]\n", encoding="utf-8")

            result = refactor_article(
                content_dir=content,
                static_images_dir=images,
                source_rel_path="posts/target.md",
                target_rel_path="pending/posts/target.md",
                use_llm=False,
            )

            self.assertEqual(result.new_path, "pending/posts/target.md")
            self.assertIn("[[pending/posts/target]]", referrer.read_text(encoding="utf-8"))
            self.assertNotIn("draft:", (content / "pending" / "posts" / "target.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
