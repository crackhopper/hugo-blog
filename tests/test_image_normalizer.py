import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.image_manifest import ImageManifest
from hugo_blog.pipeline.image_normalizer import normalize_markdown_images, safe_slug


class ImageNormalizerTest(unittest.TestCase):
    def test_safe_slug_replaces_special_characters_with_underscore(self):
        self.assertEqual(safe_slug("小白学写编译器：1.编译基础概念"), "小白学写编译器_1_编译基础概念")
        self.assertEqual(safe_slug("Texture mapping (C++)"), "Texture_mapping_C")

    def test_normalizes_short_obsidian_image_to_date_bucket(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            article = content / "posts" / "编译器" / "小白学写编译器：1.编译基础概念.md"
            article.parent.mkdir(parents=True)
            (images / "nested").mkdir(parents=True)
            (images / "nested" / "compile.png").write_bytes(b"png")
            article.write_text(
                "---\n"
                "title: 小白学写编译器：1.编译基础概念\n"
                "date: 2020-06-14T21:49:51+08:00\n"
                "---\n"
                "# 一个例子\n\n"
                "![[compile.png]]\n",
                encoding="utf-8",
            )

            result = normalize_markdown_images(
                article,
                content_dir=content,
                static_images_dir=images,
            )

            expected_name = "小白学写编译器_1_编译基础概念-一个例子-01.png"
            expected_path = images / "2020" / "06" / expected_name
            self.assertTrue(result.changed)
            self.assertEqual(result.renamed, [("compile.png", f"2020/06/{expected_name}")])
            self.assertTrue(expected_path.exists())
            self.assertFalse((images / "nested" / "compile.png").exists())
            self.assertIn(f"![[{expected_name}]]", article.read_text(encoding="utf-8"))

            manifest = ImageManifest.load(images)
            self.assertEqual(manifest.get(expected_name), f"2020/06/{expected_name}")

    def test_existing_manifest_hit_does_not_move_again(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            article = content / "posts" / "post.md"
            article.parent.mkdir(parents=True)
            (images / "2020" / "06").mkdir(parents=True)
            (images / "2020" / "06" / "post-intro-01.png").write_bytes(b"png")
            manifest = ImageManifest.load(images)
            manifest.set("post-intro-01.png", "2020/06/post-intro-01.png")
            manifest.save()
            article.write_text(
                "---\ntitle: Post\ndate: 2020-06-14T00:00:00+08:00\n---\n![[post-intro-01.png]]\n",
                encoding="utf-8",
            )

            result = normalize_markdown_images(article, content_dir=content, static_images_dir=images)

            self.assertFalse(result.changed)
            self.assertEqual(result.renamed, [])


if __name__ == "__main__":
    unittest.main()
