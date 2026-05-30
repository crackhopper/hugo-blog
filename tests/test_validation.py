import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.normalize import normalize_content
from hugo_blog.pipeline.validate import validate_content_tree
from hugo_blog.pipeline.image_manifest import ImageManifest
from hugo_blog.pipeline.wikilinks import transform_obsidian_links


class ValidationTest(unittest.TestCase):
    def test_reports_missing_obsidian_markdown_and_html_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (images / "exists.png").write_bytes(b"png")
            (content / "posts" / "post.md").write_text(
                "\n".join(
                    [
                        "![[exists.png]]",
                        "![[missing-a.png|640]]",
                        "![alt](/images/missing-b.png)",
                        '<img src="/images/missing-c.png" width="640" />',
                        "![remote](https://example.com/remote.png)",
                    ]
                ),
                encoding="utf-8",
            )

            report = validate_content_tree(content_dir=content, static_images_dir=images)

            self.assertFalse(report.ok)
            errors = [issue for issue in report.issues if issue.severity == "error"]
            self.assertEqual(
                [(issue.kind, issue.raw_reference, issue.line) for issue in errors],
                [
                    ("missing_image", "missing-a.png", 2),
                    ("missing_image", "/images/missing-b.png", 3),
                    ("missing_image", "/images/missing-c.png", 4),
                ],
            )

    def test_decodes_url_encoded_image_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (images / "C++内存管理-intro-01.png").write_bytes(b"png")
            (content / "posts" / "post.md").write_text(
                "![img](/images/C%2B%2B%E5%86%85%E5%AD%98%E7%AE%A1%E7%90%86-intro-01.png)",
                encoding="utf-8",
            )

            report = validate_content_tree(content_dir=content, static_images_dir=images)

            self.assertTrue(report.ok)

    def test_suggests_similar_image_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (images / "C++内存管理-1765799530743.png").write_bytes(b"png")
            (content / "posts" / "C++内存管理.md").write_text("![[C++内存管理-intro-01.png]]", encoding="utf-8")

            report = validate_content_tree(content_dir=content, static_images_dir=images)

            self.assertFalse(report.ok)
            self.assertIn("C++内存管理-1765799530743.png", report.issues[0].candidates)

    def test_processable_only_limits_validation_to_posts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            (content / "page" / "about").mkdir(parents=True)
            images.mkdir(parents=True)
            (content / "posts" / "post.md").write_text("# Post\n", encoding="utf-8")
            (content / "page" / "about" / "index.md").write_text("![[missing.png]]", encoding="utf-8")

            report = validate_content_tree(content_dir=content, static_images_dir=images, processable_only=True)

            self.assertTrue(report.ok)

    def test_normalize_skips_writing_file_with_missing_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            page = content / "posts" / "post.md"
            page.write_text("![alt](/images/missing.png)\n\n[[Missing Doc]]", encoding="utf-8")

            report = normalize_content(
                content,
                images,
                apply=True,
                normalize_metadata=False,
                use_llm=False,
            )

            self.assertEqual(page.read_text(encoding="utf-8"), "![alt](/images/missing.png)\n\n[[Missing Doc]]")
            self.assertEqual(len(report.validation_issues), 1)

    def test_manifest_hit_validates_and_converts_to_bucket_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            (images / "2020" / "06").mkdir(parents=True)
            (images / "2020" / "06" / "a.png").write_bytes(b"png")
            manifest = ImageManifest.load(images)
            manifest.set("a.png", "2020/06/a.png")
            manifest.save()
            (content / "posts" / "post.md").write_text("![[a.png]]", encoding="utf-8")

            report = validate_content_tree(content_dir=content, static_images_dir=images)
            converted = transform_obsidian_links(
                "![[a.png]]",
                static_images_dir=images,
                image_manifest=ImageManifest.load(images),
                verbose=False,
            )

            self.assertTrue(report.ok)
            self.assertIn("/images/2020/06/a.png", converted)

    def test_root_image_without_manifest_is_warning_not_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (images / "a.png").write_bytes(b"png")
            (content / "posts" / "post.md").write_text("![[a.png]]", encoding="utf-8")

            report = validate_content_tree(content_dir=content, static_images_dir=images)

            self.assertTrue(report.ok)
            self.assertEqual(report.issues[0].severity, "warning")
            self.assertEqual(report.issues[0].kind, "needs_image_normalization")

    def test_manifest_target_missing_is_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            manifest = ImageManifest.load(images)
            manifest.set("a.png", "2020/06/a.png")
            manifest.save()
            (content / "posts" / "post.md").write_text("![[a.png]]", encoding="utf-8")

            report = validate_content_tree(content_dir=content, static_images_dir=images)

            self.assertFalse(report.ok)
            self.assertEqual(report.issues[0].kind, "missing_image")


if __name__ == "__main__":
    unittest.main()
