import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.startup_sync import sync_content_manifests


class StartupSyncTest(unittest.TestCase):
    def test_sync_writes_article_and_link_manifests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            article = content / "posts" / "a.md"
            article.write_text("---\ntitle: A\n---\nBody\n", encoding="utf-8")

            sync_content_manifests(content)

            self.assertTrue((content / "articles.json").exists())
            self.assertTrue((content / "links.json").exists())
            self.assertIn("id:", article.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
