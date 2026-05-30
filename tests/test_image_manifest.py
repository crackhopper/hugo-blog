import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.image_manifest import ImageManifest
from hugo_blog.pipeline.normalize import scan_unused_images


class ImageManifestTest(unittest.TestCase):
    def test_load_save_and_resolve_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            images = Path(temp_dir) / "static" / "images"
            (images / "2020" / "06").mkdir(parents=True)
            (images / "2020" / "06" / "a.png").write_bytes(b"png")
            manifest = ImageManifest.load(images)
            manifest.set("a.png", "2020/06/a.png")
            manifest.save()

            reloaded = ImageManifest.load(images)

            self.assertEqual(reloaded.resolve("a.png"), images / "2020" / "06" / "a.png")

    def test_find_by_basename_ignores_manifest_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            images = Path(temp_dir) / "static" / "images"
            (images / "nested").mkdir(parents=True)
            (images / "images.json").write_text("{}", encoding="utf-8")
            (images / "nested" / "compile.png").write_bytes(b"png")

            manifest = ImageManifest.load(images)

            self.assertEqual(manifest.find_by_basename("compile.png"), [images / "nested" / "compile.png"])

    def test_manifest_referenced_bucket_image_is_not_unused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            images = Path(temp_dir) / "static" / "images"
            (images / "2025" / "12").mkdir(parents=True)
            (images / "2025" / "12" / "C_内存管理-intro-01.png").write_bytes(b"png")
            (images / "2025" / "12" / "unused.png").write_bytes(b"png")
            manifest = ImageManifest.load(images)
            manifest.set("C_内存管理-intro-01.png", "2025/12/C_内存管理-intro-01.png")
            manifest.save()

            unused = scan_unused_images(images, {"C_内存管理-intro-01.png"})

            self.assertEqual(unused, ["2025/12/unused.png"])


if __name__ == "__main__":
    unittest.main()
