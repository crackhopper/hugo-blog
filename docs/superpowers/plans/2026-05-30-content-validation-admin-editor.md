# Content Validation Admin Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a source-to-preview validation layer for broken image references, expose validation issues in the React Admin UI, and add a Monaco Markdown editor that edits original `content/posts` files only.

**Architecture:** Validation lives in `src/hugo_blog/pipeline/validate.py` and is reused by normalize, preview, build, deploy, and Admin APIs. `serve` starts Admin first, validates source/export output, and blocks Hugo preview when validation fails. The React UI adds `/issues/` and `/editor/<path>` routes backed by small JSON APIs in `preview/admin.py`.

**Tech Stack:** Python 3.12, unittest/pytest, Hugo, React + Vite, `@monaco-editor/react`, `monaco-editor`.

---

## File Structure

- Create `src/hugo_blog/pipeline/validate.py`: parse Markdown image references, validate `static/images`, produce serializable issue reports.
- Modify `src/hugo_blog/pipeline/export.py`: call validation before/after export when requested, preserve pure transformation behavior.
- Modify `src/hugo_blog/static_site.py`: add validation-aware preprocess/build helpers.
- Modify `src/hugo_blog/preview/serve.py`: start Admin first, run validation, block Hugo if report has errors.
- Modify `src/hugo_blog/preview/admin.py`: add validation/content/editor APIs and reuse validation for save operations.
- Modify `src/hugo_blog/preview/admin_ui/package.json`: add Monaco dependencies.
- Modify `src/hugo_blog/preview/admin_ui/src/App.tsx`: add `IssuesView`, `EditorView`, nav routes, API clients.
- Modify `src/hugo_blog/preview/admin_ui/src/styles.css`: layout for Issues and Monaco editor split view.
- Modify `scripts/build.py`, `scripts/deploy.py`, `scripts/normalize.py`: call validation at the correct points.
- Add tests in `tests/test_validation.py`, extend `tests/test_admin_server.py`, add/extend `tests/test_static_site.py` or `tests/test_tooling.py`.
- Update Chinese docs: `README.md`, `docs/content-pipeline.md`, `docs/python-tooling.md`, `docs/source/pipeline-validate.md`, `docs/source/preview-admin.md`, `docs/source/preview-admin-ui-app.md`, `docs/source/preview-serve.md`, `docs/source/static-site.md`.

---

### Task 1: Markdown Image Validation Core

**Files:**
- Create: `src/hugo_blog/pipeline/validate.py`
- Test: `tests/test_validation.py`

- [ ] **Step 1: Write failing tests for image reference extraction and missing images**

Add `tests/test_validation.py` with tests covering Obsidian embeds, Markdown images, HTML images, URL decoding, external URL skipping, and candidate suggestions:

```python
import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.validate import validate_content_tree


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
            self.assertEqual(
                [(issue.kind, issue.raw_reference, issue.line) for issue in report.issues],
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_validation.py -q`

Expected: import failure for `hugo_blog.pipeline.validate`.

- [ ] **Step 3: Implement validation module**

Create `src/hugo_blog/pipeline/validate.py` with:

```python
from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from hugo_blog.pipeline.content_filters import iter_content_markdown_files, iter_processable_markdown_files
from hugo_blog.pipeline.wikilinks import IMAGE_EXTENSIONS, MARKDOWN_IMAGE_PATTERN, parse_wiki_link_inner

WIKI_IMAGE_RE = re.compile(r"!\[\[([^\]]+)\]\]")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)


@dataclass
class ValidationIssue:
    severity: str
    kind: str
    source_path: str
    line: int
    raw_reference: str
    target: str
    message: str
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "issues": [issue.to_dict() for issue in self.issues]}


def validate_content_tree(
    *,
    content_dir: Path,
    static_images_dir: Path,
    processable_only: bool = False,
) -> ValidationReport:
    files = iter_processable_markdown_files(content_dir) if processable_only else iter_content_markdown_files(content_dir)
    image_names = _image_names(static_images_dir)
    issues: list[ValidationIssue] = []
    for path in files:
        issues.extend(validate_markdown_file(path, content_dir=content_dir, static_images_dir=static_images_dir, image_names=image_names))
    return ValidationReport(issues=issues)


def validate_markdown_file(
    path: Path,
    *,
    content_dir: Path,
    static_images_dir: Path,
    image_names: set[str] | None = None,
) -> list[ValidationIssue]:
    text = path.read_text(encoding="utf-8")
    names = image_names if image_names is not None else _image_names(static_images_dir)
    rel_path = path.relative_to(content_dir).as_posix()
    issues: list[ValidationIssue] = []
    for raw, target, line in iter_image_references(text):
        if not target:
            continue
        normalized = normalize_image_target(target)
        if normalized is None:
            continue
        if normalized not in names:
            issues.append(
                ValidationIssue(
                    severity="error",
                    kind="missing_image",
                    source_path=rel_path,
                    line=line,
                    raw_reference=raw,
                    target=normalized,
                    message=f"图片文件不存在: static/images/{normalized}",
                    candidates=suggest_image_candidates(normalized, names, article_stem=path.stem),
                )
            )
    return issues


def iter_image_references(text: str) -> Iterable[tuple[str, str, int]]:
    for match in WIKI_IMAGE_RE.finditer(text):
        target, _, _ = parse_wiki_link_inner(match.group(1))
        yield target, target, _line_number(text, match.start())
    for match in MARKDOWN_IMAGE_PATTERN.finditer(text):
        raw = match.group("path").strip()
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1].strip()
        yield raw, raw, _line_number(text, match.start())
    for match in HTML_IMAGE_RE.finditer(text):
        raw = html.unescape(match.group(1).strip())
        yield raw, raw, _line_number(text, match.start())


def normalize_image_target(target: str) -> str | None:
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https", "data", "mailto"} or target.startswith("//"):
        return None
    path = unquote(parsed.path or target).lstrip()
    if path.startswith("/images/"):
        path = path[len("/images/") :]
    elif path.startswith("images/"):
        path = path[len("images/") :]
    path = path.lstrip("/")
    if Path(path).suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    return path


def suggest_image_candidates(target: str, names: set[str], *, article_stem: str, limit: int = 5) -> list[str]:
    target_name = Path(target).name
    target_ext = Path(target).suffix.lower()
    scored: list[tuple[float, str]] = []
    for name in names:
        score = SequenceMatcher(None, target_name.lower(), Path(name).name.lower()).ratio()
        if article_stem and Path(name).name.startswith(article_stem):
            score += 0.25
        if target_ext and Path(name).suffix.lower() == target_ext:
            score += 0.05
        if score >= 0.45:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored[:limit]]


def _image_names(static_images_dir: Path) -> set[str]:
    if not static_images_dir.exists():
        return set()
    return {
        path.relative_to(static_images_dir).as_posix()
        for path in static_images_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1
```

- [ ] **Step 4: Run validation tests**

Run: `pytest tests/test_validation.py -q`

Expected: all tests pass.

---

### Task 2: Block Preview/Build On Validation Errors

**Files:**
- Modify: `src/hugo_blog/static_site.py`
- Modify: `src/hugo_blog/preview/serve.py`
- Modify: `scripts/build.py`
- Modify: `scripts/deploy.py`
- Test: `tests/test_static_site.py`, `tests/test_tooling.py`

- [ ] **Step 1: Add tests for validation-aware build helpers**

Add tests that create a temp content tree with a missing image and assert the validation helper returns an error report before Hugo is called.

- [ ] **Step 2: Add `StaticSiteManager.validate_content` and fatal helper**

Implement:

```python
from hugo_blog.pipeline.validate import ValidationReport, validate_content_tree

def validate_content(self, *, content_dir: Path | None = None, processable_only: bool = False) -> ValidationReport:
    root = self.project_root
    return validate_content_tree(
        content_dir=content_dir or root / "content",
        static_images_dir=root / "static" / "images",
        processable_only=processable_only,
    )
```

- [ ] **Step 3: Update `serve.main` startup order**

Order must be:
1. stop previous preview and write pid
2. ensure Hugo
3. start Admin if enabled
4. validate source `content`
5. if validation fails, print Issues URL and return `1` without starting watcher or Hugo
6. preprocess preview
7. validate `.hugo_temp_content`
8. if validation fails, print Issues URL and return `1`
9. start watcher and Hugo

- [ ] **Step 4: Update build/deploy CLIs**

Before running Hugo, validate source and exported content. Any error prints issue summary and exits nonzero. Build/deploy do not include Admin docs and do not include drafts by default.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_validation.py tests/test_tooling.py -q`

Expected: all relevant tests pass.

---

### Task 3: Admin Validation And Content APIs

**Files:**
- Modify: `src/hugo_blog/preview/admin.py`
- Test: `tests/test_admin_server.py`

- [ ] **Step 1: Add tests for Admin validation and content APIs**

Extend `tests/test_admin_server.py` with direct `BlogAdminApp` tests:

```python
def test_validation_report_groups_missing_images(self):
    report = app.validation_report()
    self.assertFalse(report["ok"])
    self.assertEqual(report["issues"][0]["source_path"], "posts/post.md")

def test_get_and_update_content_reject_non_posts_and_path_escape(self):
    with self.assertRaises(ValueError):
        app.get_content("../README.md")
    with self.assertRaises(ValueError):
        app.get_content("page/about/index.md")

def test_update_content_writes_original_markdown_and_revalidates(self):
    result = app.update_content("posts/post.md", "# New\n\n![[exists.png]]")
    self.assertTrue(result["validation"]["ok"])
```

- [ ] **Step 2: Implement `BlogAdminApp.validation_report`**

Return `validate_content_tree(..., processable_only=True).to_dict()`.

- [ ] **Step 3: Implement `get_content`, `update_content`, `content_preview`**

Rules:
- Only `content/posts/**/*.md` is accepted.
- Path escapes are rejected.
- `update_content` writes source Markdown, preprocesses preview, returns page metadata and validation report.
- `content_preview` returns transformed Hugo Markdown for display without writing source.

- [ ] **Step 4: Add HTTP routes**

Add:
- `GET /issues/` and `/editor/...` -> React index.
- `GET /api/validation`
- `POST /api/validation/run`
- `GET /api/content/<path>`
- `PUT /api/content/<path>`
- `GET /api/content-preview/<path>`

- [ ] **Step 5: Run Admin tests**

Run: `pytest tests/test_admin_server.py -q`

Expected: all tests pass.

---

### Task 4: React Issues Page And Monaco Editor

**Files:**
- Modify: `src/hugo_blog/preview/admin_ui/package.json`
- Modify: `src/hugo_blog/preview/admin_ui/src/App.tsx`
- Modify: `src/hugo_blog/preview/admin_ui/src/styles.css`

- [ ] **Step 1: Install Monaco packages**

Run: `cd src/hugo_blog/preview/admin_ui && npm install @monaco-editor/react monaco-editor`

- [ ] **Step 2: Add TypeScript types and nav routes**

Add `ValidationIssue`, `ValidationReport`, `ContentPayload`, and route detection for `/admin/`, `/issues/`, `/docs/`, `/editor/`.

- [ ] **Step 3: Implement `IssuesView`**

Behavior:
- Fetch `/api/validation`.
- Group issues by `source_path`.
- Show line, raw reference, target, message, candidates.
- `Edit Markdown` opens `/editor/<encoded path>`.
- `Revalidate` posts `/api/validation/run`.

- [ ] **Step 4: Implement `EditorView` with Monaco**

Behavior:
- Load `/api/content/<path>`.
- Render Monaco editor for Markdown.
- Right panel shows validation issues for that file and converted Markdown preview from `/api/content-preview/<path>`.
- Save calls `PUT /api/content/<path>`.
- Preview button opens `http://<host>:1313<preview_url>` only if validation is ok.

- [ ] **Step 5: Update CSS**

Add readable split-pane layout, issue badges, editor toolbar, and docs/admin nav active states.

- [ ] **Step 6: Build UI**

Run: `cd src/hugo_blog/preview/admin_ui && npm run build`

Expected: Vite build succeeds and `dist/` is refreshed.

---

### Task 5: Normalize Integration

**Files:**
- Modify: `src/hugo_blog/pipeline/normalize.py`
- Modify: `scripts/normalize.py`
- Test: `tests/test_validation.py` or `tests/test_tooling.py`

- [ ] **Step 1: Add tests for normalize image validation guard**

Test that a post with `![[missing.png]]` is reported before image rename plans can silently create a broken preview reference.

- [ ] **Step 2: Validate before and after normalize**

Behavior:
- Dry-run reports validation errors and never calls LLM.
- Apply mode refuses to write a file that already has unresolved image references.
- After each write, revalidate that file and show changed summary.

- [ ] **Step 3: Ensure restart-after-file uses new validation gate**

The existing per-file preview restart option must restart Admin/Preview only when validation passes. If not, print Issues URL instead.

- [ ] **Step 4: Run normalize tests**

Run: `pytest tests/test_validation.py tests/test_metadata_normalizer.py -q`

Expected: pass.

---

### Task 6: Chinese Developer Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/content-pipeline.md`
- Modify: `docs/python-tooling.md`
- Create: `docs/source/pipeline-validate.md`
- Modify: `docs/source/preview-admin.md`
- Modify: `docs/source/preview-admin-ui-app.md`
- Modify: `docs/source/preview-serve.md`
- Modify: `docs/source/static-site.md`

- [ ] **Step 1: Document validation pipeline in Chinese**

Add these points:
- 原始 Markdown 保持 Obsidian 写法。
- preview/build 前统一导出到 `.hugo_temp_content`。
- 验证器检查 Obsidian/Markdown/HTML 图片引用。
- `serve` 有错误时只开放 Admin/Issues，不启动 Hugo preview。
- `build/deploy` 有错误时直接失败。

- [ ] **Step 2: Document Admin Issues and Monaco editor**

Explain:
- `/issues/` 查看错误报告。
- `/editor/<path>` 编辑 `content/posts` 原文。
- 保存后程序重新导出并校验。
- Preview 按钮只在校验通过后可用。

- [ ] **Step 3: Ensure Docs navigation order includes pipeline-validate**

Update `DOC_ORDER` or source index if needed so validation docs appear near content pipeline docs.

---

### Task 7: Full Verification

**Files:**
- No new source files unless fixing verification failures.

- [ ] **Step 1: Run Python tests**

Run: `pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run React build**

Run: `cd src/hugo_blog/preview/admin_ui && npm run build`

Expected: Vite build succeeds.

- [ ] **Step 3: Run Hugo build**

Run: `python scripts/build.py`

Expected: either succeeds, or fails only because the existing content now correctly reports broken images. If it fails, record the specific issue list and verify Admin can show the same report.

- [ ] **Step 4: Run preview startup check**

Run: `python scripts/serve.py --no-watch`

Expected:
- If validation errors exist: Admin URL is printed, Issues URL is printed, Hugo command is not started.
- If validation is clean: Admin URL and Preview URL are printed, Hugo starts on `0.0.0.0:1313`.

