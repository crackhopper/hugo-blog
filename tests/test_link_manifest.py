import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.link_manifest import LinkManifest
from hugo_blog.pipeline.wikilinks import simplify_document_wiki_links, transform_obsidian_links


class LinkManifestTest(unittest.TestCase):
    def test_builds_recursive_content_manifest_and_skips_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts" / "数学").mkdir(parents=True)
            (content / "page").mkdir(parents=True)
            (content / "pending").mkdir(parents=True)
            (content / "posts" / "数学" / "深入思考曲面积分.md").write_text(
                "---\ntitle: 深入思考曲面积分\ndraft: false\n---\n",
                encoding="utf-8",
            )
            (content / "page" / "about.md").write_text("---\ntitle: 关于我\n---\n", encoding="utf-8")
            (content / "pending" / "draft.md").write_text("---\ntitle: Pending\n---\n", encoding="utf-8")

            manifest = LinkManifest.build(content)

            self.assertEqual(manifest.resolve("深入思考曲面积分"), "posts/数学/深入思考曲面积分.md")
            self.assertEqual(manifest.resolve("关于我"), "page/about.md")
            self.assertIsNone(manifest.resolve("Pending"))

    def test_transform_uses_manifest_to_emit_hugo_relref(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts" / "数学").mkdir(parents=True)
            (content / "posts" / "数学" / "深入思考曲面积分.md").write_text(
                "---\ntitle: 深入思考曲面积分\ndraft: false\n---\n",
                encoding="utf-8",
            )
            manifest = LinkManifest.build(content)

            transformed = transform_obsidian_links(
                "[[深入思考曲面积分]]",
                link_manifest=manifest,
                verbose=False,
            )

            self.assertIn('{{< relref "posts/数学/深入思考曲面积分.md" >}}', transformed)

    def test_simplifies_explicit_path_to_preferred_obsidian_link(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts" / "数学").mkdir(parents=True)
            (content / "posts" / "数学" / "深入思考曲面积分.md").write_text(
                "---\ntitle: 深入思考曲面积分\n---\n",
                encoding="utf-8",
            )
            manifest = LinkManifest.build(content)

            updated, count = simplify_document_wiki_links(
                "[[posts/数学/深入思考曲面积分|深入思考曲面积分]]",
                manifest,
            )

            self.assertEqual(count, 1)
            self.assertEqual(updated, "[[深入思考曲面积分]]")

    def test_draft_manifest_target_does_not_emit_relref(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            (content / "posts" / "draft.md").write_text("---\ntitle: Draft\ndraft: true\n---\n", encoding="utf-8")
            manifest = LinkManifest.build(content)

            transformed = transform_obsidian_links("[[Draft]]", link_manifest=manifest, verbose=False)

            self.assertEqual(transformed, "Draft")


if __name__ == "__main__":
    unittest.main()
