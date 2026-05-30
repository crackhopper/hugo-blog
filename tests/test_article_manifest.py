import json
import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.article_manifest import ArticleManifest, mark_article_normalized, reconcile_article_manifest


class ArticleManifestTest(unittest.TestCase):
    def test_assigns_id_to_article_and_includes_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            (content / "pending" / "posts").mkdir(parents=True)
            active = content / "posts" / "a.md"
            pending = content / "pending" / "posts" / "b.md"
            active.write_text("---\ntitle: A\n---\n正文 A\n", encoding="utf-8")
            pending.write_text("---\ntitle: B\n---\n正文 B\n", encoding="utf-8")

            manifest = reconcile_article_manifest(content)

            self.assertEqual(len(manifest.articles), 2)
            self.assertIn("id:", active.read_text(encoding="utf-8"))
            self.assertIn("id:", pending.read_text(encoding="utf-8"))
            self.assertEqual(manifest.by_path("posts/a.md").title, "A")
            self.assertEqual(manifest.by_path("posts/a.md").status, "active")
            self.assertEqual(manifest.by_path("pending/posts/b.md").status, "pending")
            self.assertTrue((content / "articles.json").exists())

    def test_detects_obsidian_move_by_front_matter_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts" / "old").mkdir(parents=True)
            article = content / "posts" / "old" / "a.md"
            article.write_text("---\ntitle: A\n---\n正文 A\n", encoding="utf-8")
            first = reconcile_article_manifest(content)
            article_id = first.by_path("posts/old/a.md").id

            (content / "posts" / "new").mkdir(parents=True)
            moved = content / "posts" / "new" / "renamed.md"
            article.rename(moved)

            second = reconcile_article_manifest(content)

            self.assertEqual(second.by_path("posts/new/renamed.md").id, article_id)
            self.assertIn("posts/old/a.md", second.articles[article_id].previous_paths)

    def test_detects_move_by_fingerprint_when_id_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            article = content / "posts" / "a.md"
            article.write_text("---\ntitle: A\n---\n正文 A\n", encoding="utf-8")
            first = reconcile_article_manifest(content)
            article_id = first.by_path("posts/a.md").id

            moved = content / "posts" / "b.md"
            text_without_id = article.read_text(encoding="utf-8")
            text_without_id = "\n".join(line for line in text_without_id.splitlines() if not line.startswith("id: "))
            article.unlink()
            moved.write_text(text_without_id.replace("title: A", "title: B"), encoding="utf-8")

            second = reconcile_article_manifest(content)

            self.assertEqual(second.by_path("posts/b.md").id, article_id)
            self.assertIn("posts/a.md", second.articles[article_id].previous_paths)
            self.assertIn("id:", moved.read_text(encoding="utf-8"))

    def test_marks_previous_manifest_records_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            article = content / "posts" / "a.md"
            article.write_text("---\ntitle: A\n---\n正文 A\n", encoding="utf-8")
            first = reconcile_article_manifest(content)
            article_id = first.by_path("posts/a.md").id

            article.unlink()
            second = reconcile_article_manifest(content)

            self.assertEqual(second.articles[article_id].status, "missing")
            self.assertEqual(second.articles[article_id].path, "posts/a.md")

    def test_records_links_images_aliases_and_indexes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            source = content / "posts" / "source.md"
            target = content / "posts" / "target.md"
            source.write_text(
                "---\ntitle: Source\ndraft: true\naliases:\n  - Src\n---\n[[Target]]\n![[img.png|400]]\n",
                encoding="utf-8",
            )
            target.write_text("---\ntitle: Target\n---\n正文\n", encoding="utf-8")

            manifest = reconcile_article_manifest(content)
            reloaded = ArticleManifest.load(content)
            source_record = reloaded.by_path("posts/source.md")
            target_record = reloaded.by_path("posts/target.md")
            raw_manifest = json.loads((content / "articles.json").read_text(encoding="utf-8"))

            self.assertTrue(source_record.draft)
            self.assertIn("Src", source_record.aliases)
            self.assertIn("Source", source_record.aliases)
            self.assertEqual(source_record.outgoing_links, ["Target"])
            self.assertEqual(source_record.image_keys, ["img.png"])
            self.assertIn(source_record.id, target_record.incoming_links)
            self.assertEqual(raw_manifest["path_index"]["posts/source.md"], source_record.id)
            self.assertEqual(manifest.title_index["Target"], target_record.id)
            self.assertRegex(source_record.modified, r"^\d{4}-\d{2}-\d{2}T")

    def test_marks_article_normalized_with_current_fingerprint_and_time(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            article = content / "posts" / "a.md"
            article.write_text("---\ntitle: A\n---\n正文 A\n", encoding="utf-8")
            manifest = reconcile_article_manifest(content)
            record = manifest.by_path("posts/a.md")

            updated = mark_article_normalized(content, "posts/a.md")

            self.assertTrue(updated.normalized_fingerprint.startswith("b2:"))
            self.assertNotEqual(updated.normalized_fingerprint, "")
            self.assertRegex(updated.normalized_at, r"^\d{4}-\d{2}-\d{2}T")
            reloaded = ArticleManifest.load(content).by_path("posts/a.md")
            self.assertEqual(reloaded.normalized_fingerprint, updated.normalized_fingerprint)
            self.assertEqual(reloaded.normalized_at, updated.normalized_at)

    def test_duplicate_front_matter_ids_are_split_without_manifest_corruption(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            (content / "posts" / "a.md").write_text("---\nid: art_same\ntitle: A\n---\nA\n", encoding="utf-8")
            (content / "posts" / "b.md").write_text("---\nid: art_same\ntitle: B\n---\nB\n", encoding="utf-8")

            manifest = reconcile_article_manifest(content)

            a = manifest.by_path("posts/a.md")
            b = manifest.by_path("posts/b.md")
            self.assertNotEqual(a.id, b.id)
            self.assertEqual(len(manifest.articles), 2)

    def test_malformed_manifest_does_not_block_reconcile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            content.mkdir()
            (content / "articles.json").write_text("{broken", encoding="utf-8")
            (content / "post.md").write_text("---\ntitle: Post\n---\nBody\n", encoding="utf-8")

            manifest = reconcile_article_manifest(content)

            self.assertEqual(len(manifest.articles), 1)
            self.assertIn("id:", (content / "post.md").read_text(encoding="utf-8"))

    def test_malformed_manifest_shapes_do_not_block_reconcile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            content.mkdir()
            (content / "articles.json").write_text(
                json.dumps({"version": "bad", "articles": [], "path_index": [], "title_index": []}),
                encoding="utf-8",
            )
            (content / "post.md").write_text("---\ntitle: Post\n---\nBody\n", encoding="utf-8")

            manifest = reconcile_article_manifest(content)

            self.assertEqual(len(manifest.articles), 1)

    def test_malformed_record_fields_do_not_block_reconcile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            content.mkdir()
            (content / "articles.json").write_text(
                json.dumps(
                    {
                        "articles": {
                            "art_bad": {
                                "id": "art_bad",
                                "path": "old.md",
                                "title": "Old",
                                "draft": False,
                                "status": "active",
                                "fingerprint": "b2:old",
                                "previous_paths": 123,
                                "aliases": "Alias",
                                "outgoing_links": None,
                                "incoming_links": {},
                                "image_keys": 456,
                                "last_seen": "then",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (content / "post.md").write_text("---\ntitle: Post\n---\nBody\n", encoding="utf-8")

            manifest = reconcile_article_manifest(content)

            self.assertEqual(manifest.articles["art_bad"].status, "missing")
            self.assertEqual(manifest.articles["art_bad"].previous_paths, [])

    def test_adding_id_preserves_front_matter_comments_and_quoting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            content.mkdir()
            article = content / "post.md"
            article.write_text("---\n# keep me\ntitle: 'Post'\n---\nBody\n", encoding="utf-8")

            reconcile_article_manifest(content)

            text = article.read_text(encoding="utf-8")
            self.assertIn("# keep me", text)
            self.assertIn("title: 'Post'", text)

    def test_ambiguous_targets_do_not_create_incoming_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            (content / "posts" / "source.md").write_text("---\ntitle: Source\n---\n[[Same]]\n", encoding="utf-8")
            (content / "posts" / "a.md").write_text("---\ntitle: Same\n---\nA\n", encoding="utf-8")
            (content / "posts" / "b.md").write_text("---\ntitle: Same\n---\nB\n", encoding="utf-8")

            manifest = reconcile_article_manifest(content)

            self.assertEqual(manifest.by_path("posts/a.md").incoming_links, [])
            self.assertEqual(manifest.by_path("posts/b.md").incoming_links, [])


if __name__ == "__main__":
    unittest.main()
