# Image Manifest Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Obsidian short image references work by normalizing images inside `static/images/`, maintaining `images.json`, and using that manifest during validation and Hugo export.

**Architecture:** Add a manifest module for `static/images/images.json` and a single-file image normalizer that moves matched images into `YYYY/MM/` buckets with safe filenames. Validation and wiki-link conversion read the manifest first, with legacy root-image fallback marked as a warning. Admin save runs the single-file normalizer before export and returns the updated Markdown.

**Tech Stack:** Python 3.12, unittest, existing Hugo/Obsidian pipeline, React Admin APIs already present.

---

## File Structure

- Create `src/hugo_blog/pipeline/image_manifest.py`: load/save manifest, resolve short names to actual image paths, scan static images by basename.
- Create `src/hugo_blog/pipeline/image_normalizer.py`: normalize one Markdown file’s Obsidian image embeds, safe slug names, date buckets, file moves, manifest updates.
- Modify `src/hugo_blog/pipeline/wikilinks.py`: pass manifest into `transform_obsidian_links()` and output `/images/YYYY/MM/file.png`.
- Modify `src/hugo_blog/pipeline/validate.py`: validate images through manifest first and emit `needs_image_normalization` warnings for root fallback.
- Modify `src/hugo_blog/pipeline/export.py`: load manifest once and pass it to converter.
- Modify `src/hugo_blog/preview/admin.py`: run single-file image normalization during `PUT /api/content/<path>` and return updated content.
- Modify `src/hugo_blog/pipeline/normalize.py`: use the new normalizer for processable posts before other image rename logic.
- Add tests in `tests/test_image_manifest.py`, `tests/test_image_normalizer.py`, extend `tests/test_validation.py`, `tests/test_tooling.py`, `tests/test_admin_server.py`.
- Update docs: `docs/content-pipeline.md`, `docs/python-tooling.md`, `docs/source/pipeline-wikilinks.md`, `docs/source/pipeline-validate.md`, add `docs/source/pipeline-image-manifest.md` and `docs/source/pipeline-image-normalizer.md`.

---

### Task 1: Manifest Core

**Files:**
- Create: `src/hugo_blog/pipeline/image_manifest.py`
- Test: `tests/test_image_manifest.py`

- [ ] **Step 1: Write failing manifest tests**

Create `tests/test_image_manifest.py`:

```python
import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.image_manifest import ImageManifest


class ImageManifestTest(unittest.TestCase):
    def test_load_save_and_resolve_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            images = Path(temp_dir) / "static" / "images"
            images.mkdir(parents=True)
            manifest = ImageManifest.load(images)
            manifest.set("a.png", "2020/06/a.png")
            manifest.save()

            reloaded = ImageManifest.load(images)

            self.assertEqual(reloaded.resolve("a.png"), images / "2020/06/a.png")

    def test_find_by_basename_ignores_manifest_json(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            images = Path(temp_dir) / "static" / "images"
            (images / "nested").mkdir(parents=True)
            (images / "images.json").write_text("{}", encoding="utf-8")
            (images / "nested" / "compile.png").write_bytes(b"png")

            manifest = ImageManifest.load(images)

            self.assertEqual(manifest.find_by_basename("compile.png"), [images / "nested" / "compile.png"])
```

- [ ] **Step 2: Run failing tests**

Run: `uv run python -m unittest tests.test_image_manifest -v`

Expected: import failure for `hugo_blog.pipeline.image_manifest`.

- [ ] **Step 3: Implement manifest**

Create `src/hugo_blog/pipeline/image_manifest.py` with `ImageManifest.load()`, `save()`, `resolve()`, `set()`, `find_by_basename()`, and `is_manifest_path()`.

- [ ] **Step 4: Run manifest tests**

Run: `uv run python -m unittest tests.test_image_manifest -v`

Expected: pass.

---

### Task 2: Single-File Image Normalizer

**Files:**
- Create: `src/hugo_blog/pipeline/image_normalizer.py`
- Test: `tests/test_image_normalizer.py`

- [ ] **Step 1: Write failing normalizer tests**

Create tests for:
- `![[compile.png]]` found at `static/images/nested/compile.png`.
- Article date `2020-06-14T...` creates `static/images/2020/06/`.
- Full-width colon in article title becomes `_`.
- Source Markdown updates to `![[safe-name.png]]`.
- Manifest maps short safe name to `2020/06/safe-name.png`.

- [ ] **Step 2: Run failing tests**

Run: `uv run python -m unittest tests.test_image_normalizer -v`

Expected: import failure for `image_normalizer`.

- [ ] **Step 3: Implement normalizer**

Implement:
- `safe_slug(value: str) -> str`
- `bucket_for_markdown(md_file: Path, metadata: dict) -> str`
- `normalize_markdown_images(md_file, content_dir, static_images_dir) -> ImageNormalizeResult`
- heading detection using existing normalize-style logic
- manifest update and file move

- [ ] **Step 4: Run normalizer tests**

Run: `uv run python -m unittest tests.test_image_normalizer -v`

Expected: pass.

---

### Task 3: Converter And Validator Manifest Support

**Files:**
- Modify: `src/hugo_blog/pipeline/wikilinks.py`
- Modify: `src/hugo_blog/pipeline/validate.py`
- Modify: `src/hugo_blog/pipeline/export.py`
- Test: `tests/test_validation.py`, `tests/test_tooling.py`

- [ ] **Step 1: Add failing converter/validator tests**

Add tests:
- manifest hit converts `![[a.png]]` to `/images/2020/06/a.png`.
- manifest hit validates if target exists.
- manifest missing but root `static/images/a.png` exists returns warning `needs_image_normalization` and does not block.
- manifest points to missing target returns `missing_image` error.

- [ ] **Step 2: Run failing tests**

Run: `uv run python -m unittest tests.test_validation tests.test_tooling -v`

Expected: new assertions fail because manifest is not used.

- [ ] **Step 3: Update converter and export**

Load `ImageManifest` in `export.py` and pass it into `transform_obsidian_links()`. In `wikilinks.py`, resolve image target through manifest before legacy root lookup.

- [ ] **Step 4: Update validator**

Add warning severity support for `needs_image_normalization`. `ValidationReport.ok` remains true when only warnings exist.

- [ ] **Step 5: Run tests**

Run: `uv run python -m unittest tests.test_validation tests.test_tooling -v`

Expected: pass.

---

### Task 4: Admin Save Integration

**Files:**
- Modify: `src/hugo_blog/preview/admin.py`
- Test: `tests/test_admin_server.py`

- [ ] **Step 1: Add failing Admin test**

Add a test where saving content with `![[compile.png]]` moves `static/images/nested/compile.png`, updates Markdown, writes manifest, and returns updated content.

- [ ] **Step 2: Run failing test**

Run: `uv run python -m unittest tests.test_admin_server -v`

Expected: new assertion fails because Admin does not run image normalizer.

- [ ] **Step 3: Update Admin save**

After writing the user content, call `normalize_markdown_images()`. If it changes the file, re-read source and include `content` in the PUT response.

- [ ] **Step 4: Run Admin tests**

Run: `uv run python -m unittest tests.test_admin_server -v`

Expected: pass.

---

### Task 5: Normalize CLI Integration And Docs

**Files:**
- Modify: `src/hugo_blog/pipeline/normalize.py`
- Modify docs listed above.
- Test: `tests/test_validation.py`, `tests/test_image_normalizer.py`

- [ ] **Step 1: Integrate normalizer into normalize flow**

Run single-file image normalization before old image rename logic. Keep deletion cleanup separate and not automatic in Admin save.

- [ ] **Step 2: Update docs**

Document `images.json`, date buckets, converter manifest priority, and Admin save behavior.

- [ ] **Step 3: Run focused tests**

Run: `uv run python -m unittest tests.test_image_manifest tests.test_image_normalizer tests.test_validation -v`

Expected: pass.

---

### Task 6: Full Verification

**Files:**
- No new source files unless fixing verification failures.

- [ ] **Step 1: Run all Python tests**

Run: `uv run python -m unittest discover -s tests -v`

Expected: pass.

- [ ] **Step 2: Run React build**

Run: `npm run build` in `src/hugo_blog/preview/admin_ui`

Expected: pass.

- [ ] **Step 3: Run target sample check**

Run a focused normalization/Admin-equivalent path for `content/posts/编译器/小白学写编译器：1.编译基础概念.md` after ensuring `compile.png` exists somewhere under `static/images`.

Expected: source reference becomes safe Obsidian embed, manifest points to date bucket, converter outputs `/images/2020/06/...`.

