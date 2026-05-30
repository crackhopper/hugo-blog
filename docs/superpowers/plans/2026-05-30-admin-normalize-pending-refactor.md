# Admin Normalize Pending Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Admin-driven normalize, pending, rename/move, and LLM suggestion workflows backed by stable article IDs and manifests.

**Architecture:** Add focused pipeline modules for article inventory, article manifest reconciliation, safe refactor/move operations, single-file normalize, and LLM suggestions. Admin HTTP handlers call these modules; the React UI becomes a thin client for listing, sorting, selecting, confirming, and applying operations. All path-changing operations go through `content_refactor.py`.

**Tech Stack:** Python standard library, existing `hugo_blog` pipeline modules, existing LLM client, React + TypeScript admin UI, `unittest`, Vite.

---

## File Structure

- Create `src/hugo_blog/pipeline/article_manifest.py`: stable article IDs, content fingerprints, manifest load/save, filesystem reconciliation.
- Create `src/hugo_blog/pipeline/content_inventory.py`: content and pending scanning for Admin list views.
- Create `src/hugo_blog/pipeline/content_refactor.py`: safe move/rename service, reference rewriting, manifest updates, preview preprocess.
- Create `src/hugo_blog/pipeline/content_normalize_one.py`: single-file and batch normalize API surface with no image deletion.
- Create `src/hugo_blog/pipeline/content_suggestions.py`: LLM-backed restore/move/rename suggestions and path validation.
- Modify `src/hugo_blog/pipeline/link_manifest.py`: consume article manifest where useful, keep `content/links.json` as link-name resolver.
- Modify `src/hugo_blog/pipeline/export.py`: run article manifest reconcile before link manifest build.
- Modify `src/hugo_blog/preview/admin.py`: add content scope APIs, normalize APIs, refactor APIs, pending APIs, suggestions APIs.
- Modify `src/hugo_blog/preview/admin_ui/src/App.tsx`: add sort controls, selection, row normalize, batch normalize, pending view, refactor/restore/suggestions UI.
- Modify `src/hugo_blog/preview/admin_ui/src/styles.css`: layout for bulk toolbar, candidate cards, suggestions page.
- Add tests:
  - `tests/test_article_manifest.py`
  - `tests/test_content_refactor.py`
  - `tests/test_content_normalize_one.py`
  - `tests/test_content_suggestions.py`
  - extend `tests/test_admin_server.py`
  - extend `tests/test_tooling.py`

## Task 1: Article Manifest

**Files:**
- Create: `src/hugo_blog/pipeline/article_manifest.py`
- Test: `tests/test_article_manifest.py`

- [ ] **Step 1: Write failing tests for article ID creation and pending inclusion**

Create `tests/test_article_manifest.py`:

```python
import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.article_manifest import ArticleManifest, reconcile_article_manifest


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
            self.assertEqual(manifest.by_path("pending/posts/b.md").status, "pending")

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
            self.assertIn("id:", moved.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run python -m unittest tests.test_article_manifest -v
```

Expected: import failure because `hugo_blog.pipeline.article_manifest` does not exist.

- [ ] **Step 3: Implement article manifest module**

Create `src/hugo_blog/pipeline/article_manifest.py`:

```python
from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from hugo_blog.pipeline.content_filters import is_skipped_content_path
from hugo_blog.pipeline.metadata import parse_front_matter
from hugo_blog.pipeline.wikilinks import collect_document_wiki_links, collect_image_references

MANIFEST_NAME = "articles.json"
ID_RE = re.compile(r"^id:\s*(.+)$", re.MULTILINE)


@dataclass
class ArticleRecord:
    id: str
    path: str
    status: str
    title: str
    draft: bool
    fingerprint: str
    previous_paths: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    outgoing_links: list[str] = field(default_factory=list)
    incoming_links: list[str] = field(default_factory=list)
    image_keys: list[str] = field(default_factory=list)
    last_seen: str = ""


@dataclass
class ArticleManifest:
    content_dir: Path
    version: int = 1
    articles: dict[str, ArticleRecord] = field(default_factory=dict)
    path_index: dict[str, str] = field(default_factory=dict)
    title_index: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, content_dir: Path) -> "ArticleManifest":
        path = content_dir / MANIFEST_NAME
        if not path.exists():
            return cls(content_dir=content_dir)
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = {
            article_id: ArticleRecord(**record)
            for article_id, record in payload.get("articles", {}).items()
        }
        return cls(
            content_dir=content_dir,
            version=int(payload.get("version", 1)),
            articles=records,
            path_index={str(k): str(v) for k, v in payload.get("path_index", {}).items()},
            title_index={str(k): str(v) for k, v in payload.get("title_index", {}).items()},
        )

    def save(self) -> None:
        payload = {
            "version": self.version,
            "articles": {key: asdict(value) for key, value in sorted(self.articles.items())},
            "path_index": dict(sorted(self.path_index.items())),
            "title_index": dict(sorted(self.title_index.items())),
        }
        (self.content_dir / MANIFEST_NAME).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def by_path(self, rel_path: str) -> ArticleRecord:
        return self.articles[self.path_index[rel_path]]


def iter_article_files(content_dir: Path, *, include_pending: bool = True) -> Iterable[Path]:
    for path in sorted(content_dir.rglob("*.md")):
        rel = path.relative_to(content_dir)
        if rel.name == MANIFEST_NAME:
            continue
        if not include_pending and is_skipped_content_path(path, content_dir):
            continue
        yield path


def normalized_body(text: str) -> str:
    _, body, _ = parse_front_matter(text)
    return re.sub(r"\s+", " ", body.replace("\r\n", "\n")).strip()


def fingerprint(text: str) -> str:
    digest = hashlib.blake2b(normalized_body(text).encode("utf-8"), digest_size=16).hexdigest()
    return f"b2:{digest}"


def new_article_id() -> str:
    return "art_" + secrets.token_hex(16)


def read_article_id(text: str) -> str | None:
    metadata, _, _ = parse_front_matter(text)
    value = metadata.get("id")
    return str(value).strip() if value else None


def ensure_front_matter_id(path: Path, article_id: str) -> None:
    text = path.read_text(encoding="utf-8")
    if read_article_id(text) == article_id:
        return
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            block = text[4:end]
            if ID_RE.search(block):
                block = ID_RE.sub(f"id: {article_id}", block)
            else:
                block = f"id: {article_id}\n" + block
            path.write_text("---\n" + block + text[end:], encoding="utf-8")
            return
    path.write_text(f"---\nid: {article_id}\n---\n{text}", encoding="utf-8")


def reconcile_article_manifest(content_dir: Path) -> ArticleManifest:
    previous = ArticleManifest.load(content_dir)
    by_fingerprint = {record.fingerprint: record for record in previous.articles.values()}
    by_id = previous.articles
    current = ArticleManifest(content_dir=content_dir)
    now = datetime.now(timezone.utc).isoformat()

    for path in iter_article_files(content_dir, include_pending=True):
        rel_path = path.relative_to(content_dir).as_posix()
        text = path.read_text(encoding="utf-8")
        article_id = read_article_id(text)
        fp = fingerprint(text)
        old_record = by_id.get(article_id or "") or by_fingerprint.get(fp)
        if old_record:
            article_id = old_record.id
        if not article_id:
            article_id = new_article_id()
        ensure_front_matter_id(path, article_id)
        updated_text = path.read_text(encoding="utf-8")
        metadata, _, _ = parse_front_matter(updated_text)
        title = str(metadata.get("title") or path.stem)
        status = "pending" if rel_path.startswith("pending/") else "active"
        previous_paths = []
        if old_record:
            previous_paths = list(dict.fromkeys(old_record.previous_paths + ([old_record.path] if old_record.path != rel_path else [])))
        record = ArticleRecord(
            id=article_id,
            path=rel_path,
            status=status,
            title=title,
            draft=bool(metadata.get("draft", False)),
            fingerprint=fingerprint(updated_text),
            previous_paths=previous_paths,
            aliases=list(dict.fromkeys(([title, path.stem] + (old_record.aliases if old_record else [])))),
            outgoing_links=collect_document_wiki_links(updated_text),
            image_keys=collect_image_references(updated_text),
            last_seen=now,
        )
        current.articles[article_id] = record
        current.path_index[rel_path] = article_id
        if title not in current.title_index:
            current.title_index[title] = article_id

    for article_id, record in previous.articles.items():
        if article_id not in current.articles:
            missing = ArticleRecord(**asdict(record))
            missing.status = "missing"
            current.articles[article_id] = missing

    _fill_incoming_links(current)
    current.save()
    return current


def _fill_incoming_links(manifest: ArticleManifest) -> None:
    title_to_id = {record.title: article_id for article_id, record in manifest.articles.items()}
    path_to_id = {record.path.removesuffix(".md"): article_id for article_id, record in manifest.articles.items()}
    for record in manifest.articles.values():
        record.incoming_links = []
    for source_id, record in manifest.articles.items():
        for link in record.outgoing_links:
            target = link.split("#", 1)[0].removesuffix(".md")
            target_id = title_to_id.get(target) or path_to_id.get(target)
            if target_id and target_id in manifest.articles:
                manifest.articles[target_id].incoming_links.append(source_id)
```

- [ ] **Step 4: Run article manifest tests**

Run:

```bash
uv run python -m unittest tests.test_article_manifest -v
```

Expected: all tests pass.

## Task 2: Content Inventory

**Files:**
- Create: `src/hugo_blog/pipeline/content_inventory.py`
- Test: extend `tests/test_admin_server.py`

- [ ] **Step 1: Write failing inventory test**

Add to `tests/test_admin_server.py`:

```python
def test_list_pages_can_show_normal_and_pending_content(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        content = root / "content"
        (content / "posts").mkdir(parents=True)
        (content / "projects").mkdir(parents=True)
        (content / "pending" / "posts").mkdir(parents=True)
        (root / "static" / "images").mkdir(parents=True)
        (content / "posts" / "post.md").write_text("---\ntitle: Post\n---\n", encoding="utf-8")
        (content / "projects" / "project.md").write_text("---\ntitle: Project\n---\n", encoding="utf-8")
        (content / "pending" / "posts" / "old.md").write_text("---\ntitle: Old\n---\n", encoding="utf-8")

        app = BlogAdminApp(project_root=root, content_dir=content)

        self.assertEqual([p["path"] for p in app.list_pages(scope="normal")], ["posts/post.md", "projects/project.md"])
        self.assertEqual([p["path"] for p in app.list_pages(scope="pending")], ["pending/posts/old.md"])
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
uv run python -m unittest tests.test_admin_server.AdminServerTest.test_list_pages_can_show_normal_and_pending_content -v
```

Expected: failure because `list_pages` does not accept `scope`.

- [ ] **Step 3: Implement inventory module**

Create `src/hugo_blog/pipeline/content_inventory.py`:

```python
from __future__ import annotations

from pathlib import Path

from hugo_blog.pipeline.content_filters import is_skipped_content_path
from hugo_blog.pipeline.metadata import metadata_for_listing


def iter_managed_markdown_files(content_dir: Path, *, scope: str = "normal"):
    for path in sorted(content_dir.rglob("*.md")):
        rel = path.relative_to(content_dir)
        if rel.name in {"links.json", "articles.json"}:
            continue
        is_pending = is_skipped_content_path(path, content_dir)
        if scope == "normal" and is_pending:
            continue
        if scope == "pending" and not is_pending:
            continue
        yield path


def list_content_pages(content_dir: Path, *, scope: str = "normal") -> list[dict]:
    pages = []
    for path in iter_managed_markdown_files(content_dir, scope=scope):
        item = metadata_for_listing(path, content_dir)
        item["scope"] = "pending" if item["path"].startswith("pending/") else "normal"
        pages.append(item)
    return pages
```

- [ ] **Step 4: Wire inventory into Admin**

Modify `src/hugo_blog/preview/admin.py`:

```python
from hugo_blog.pipeline.content_inventory import iter_managed_markdown_files, list_content_pages
```

Replace:

```python
def iter_pages(self):
    return list(iter_processable_markdown_files(self.content_dir))
```

with:

```python
def iter_pages(self, *, scope: str = "normal"):
    return list(iter_managed_markdown_files(self.content_dir, scope=scope))
```

Replace `list_pages` body with:

```python
def list_pages(self, *, status: str = "all", scope: str = "normal") -> list[dict]:
    pages = list_content_pages(self.content_dir, scope=scope)
    if status == "draft":
        pages = [page for page in pages if page["draft"]]
    elif status == "published":
        pages = [page for page in pages if not page["draft"]]
    return sorted(pages, key=lambda page: page["modified"], reverse=True)
```

Update `_content_path` to allow pending only where intended by callers:

```python
def _content_path(self, rel_path: str, *, allow_pending: bool = False) -> Path:
    target = (self.content_dir / rel_path).resolve()
    content_root = self.content_dir.resolve()
    if content_root not in target.parents and target != content_root:
        raise ValueError("path escapes content dir")
    if not target.exists() or target.suffix != ".md":
        raise FileNotFoundError(rel_path)
    if target.relative_to(self.content_dir).parts[0] == "pending" and not allow_pending:
        raise ValueError("pending content requires explicit pending operation")
    return target
```

- [ ] **Step 5: Update GET `/api/content` parser**

In `make_handler().do_GET`, parse `scope`:

```python
if parsed.path == "/api/content":
    query = parse_qs(parsed.query)
    status = query.get("status", ["all"])[0]
    scope = query.get("scope", ["normal"])[0]
    body = json.dumps(app.list_pages(status=status, scope=scope), ensure_ascii=False).encode("utf-8")
    self._send_json(body)
    return
```

- [ ] **Step 6: Run Admin inventory tests**

Run:

```bash
uv run python -m unittest tests.test_admin_server -v
```

Expected: tests pass.

## Task 3: Single-File Normalize API

**Files:**
- Create: `src/hugo_blog/pipeline/content_normalize_one.py`
- Modify: `src/hugo_blog/preview/admin.py`
- Test: `tests/test_content_normalize_one.py`, extend `tests/test_admin_server.py`

- [ ] **Step 1: Write failing single normalize test**

Create `tests/test_content_normalize_one.py`:

```python
import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.content_normalize_one import normalize_one


class ContentNormalizeOneTest(unittest.TestCase):
    def test_normalize_one_updates_links_without_deleting_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (images / "unused.png").write_bytes(b"png")
            (content / "posts" / "target.md").write_text("---\ntitle: Target\n---\n", encoding="utf-8")
            source = content / "posts" / "source.md"
            source.write_text("---\ntitle: Source\n---\n[[posts/target|Target]]\n", encoding="utf-8")

            result = normalize_one(
                source.relative_to(content).as_posix(),
                content_dir=content,
                static_images_dir=images,
                project_root=root,
                use_llm=False,
                preprocess=False,
            )

            self.assertTrue(result["ok"])
            self.assertIn("[[Target]]", source.read_text(encoding="utf-8"))
            self.assertTrue((images / "unused.png").exists())
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run python -m unittest tests.test_content_normalize_one -v
```

Expected: import failure.

- [ ] **Step 3: Implement `normalize_one`**

Create `src/hugo_blog/pipeline/content_normalize_one.py`:

```python
from __future__ import annotations

from pathlib import Path

from hugo_blog.llm.client import LLMClient, config_from_env
from hugo_blog.pipeline.image_normalizer import normalize_markdown_images
from hugo_blog.pipeline.link_manifest import LinkManifest
from hugo_blog.pipeline.metadata import ensure_metadata, needs_summary, normalize_title, parse_front_matter
from hugo_blog.pipeline.validate import ValidationReport, validate_markdown_text
from hugo_blog.pipeline.wikilinks import fix_same_page_index_links, migrate_relref_links, simplify_document_wiki_links
from hugo_blog.static_site import StaticSiteManager


def normalize_one(
    rel_path: str,
    *,
    content_dir: Path,
    static_images_dir: Path,
    project_root: Path,
    use_llm: bool = True,
    preprocess: bool = True,
) -> dict:
    target = (content_dir / rel_path).resolve()
    content_root = content_dir.resolve()
    if content_root not in target.parents and target != content_root:
        raise ValueError("path escapes content dir")
    if not target.exists() or target.suffix != ".md":
        raise FileNotFoundError(rel_path)

    changes: list[str] = []
    image_result = normalize_markdown_images(target, content_dir=content_dir, static_images_dir=static_images_dir)
    if image_result.changed:
        changes.append(f"images:{len(image_result.renamed)}")

    text = target.read_text(encoding="utf-8")
    link_manifest = LinkManifest.build(content_dir)
    link_manifest.save()

    migrated, relref_count = migrate_relref_links(text)
    if relref_count:
        text = migrated
        changes.append(f"relref:{relref_count}")

    fixed, index_count = fix_same_page_index_links(text)
    if index_count:
        text = fixed
        changes.append(f"same_page:{index_count}")

    simplified, simplified_count = simplify_document_wiki_links(text, link_manifest)
    if simplified_count:
        text = simplified
        changes.append(f"links:{simplified_count}")

    metadata, body, _ = parse_front_matter(text)
    llm_metadata = None
    if use_llm and (not metadata.get("tags") or needs_summary(body)):
        client = LLMClient(config_from_env(project_root))
        if not client.config.available:
            raise RuntimeError("LLM config is required for Admin normalize")
        llm_metadata = client.generate_metadata(
            title=str(metadata.get("title") or normalize_title(target)),
            body=body,
            need_abstract=needs_summary(body),
            need_tags=not metadata.get("tags"),
        )

    update = ensure_metadata(md_file=target, text=text, llm_metadata=llm_metadata)
    if update.changed:
        text = update.text
        changes.append("metadata")

    issues = validate_markdown_text(
        text,
        source_path=rel_path,
        static_images_dir=static_images_dir,
    )
    report = ValidationReport(issues=issues).to_dict()
    if report["ok"]:
        target.write_text(text, encoding="utf-8")
        LinkManifest.build(content_dir).save()
        if preprocess:
            StaticSiteManager(project_root=project_root).preprocess_preview(force=True)

    return {"path": rel_path, "ok": report["ok"], "changes": changes, "validation": report}
```

- [ ] **Step 4: Wire Admin normalize endpoints**

In `src/hugo_blog/preview/admin.py`, import:

```python
from hugo_blog.pipeline.content_normalize_one import normalize_one
```

Add methods:

```python
def normalize_content(self, rel_path: str) -> dict:
    return normalize_one(
        rel_path,
        content_dir=self.content_dir,
        static_images_dir=self.project_root / "static" / "images",
        project_root=self.project_root,
        use_llm=True,
        preprocess=True,
    )

def normalize_content_batch(self, paths: list[str]) -> dict:
    results = [self.normalize_content(path) for path in paths]
    return {"results": results, "ok": all(item["ok"] for item in results)}
```

In `do_POST`, add:

```python
if parsed.path == "/api/content/normalize":
    payload = self._read_json()
    body = json.dumps(app.normalize_content(str(payload["path"])), ensure_ascii=False).encode("utf-8")
    self._send_json(body)
    return

if parsed.path == "/api/content/normalize-batch":
    payload = self._read_json()
    paths = [str(path) for path in payload.get("paths", [])]
    body = json.dumps(app.normalize_content_batch(paths), ensure_ascii=False).encode("utf-8")
    self._send_json(body)
    return
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run python -m unittest tests.test_content_normalize_one tests.test_admin_server -v
```

Expected: tests pass.

## Task 4: Content Refactor Module

**Files:**
- Create: `src/hugo_blog/pipeline/content_refactor.py`
- Test: `tests/test_content_refactor.py`
- Modify: `src/hugo_blog/preview/admin.py`

- [ ] **Step 1: Write failing refactor tests**

Create `tests/test_content_refactor.py`:

```python
import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.content_refactor import refactor_article


class ContentRefactorTest(unittest.TestCase):
    def test_move_article_updates_references_and_manifests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts" / "old").mkdir(parents=True)
            (content / "posts" / "new").mkdir(parents=True)
            images.mkdir(parents=True)
            source = content / "posts" / "old" / "target.md"
            source.write_text("---\ntitle: Old Target\n---\n正文\n", encoding="utf-8")
            ref = content / "posts" / "ref.md"
            ref.write_text("---\ntitle: Ref\n---\n[[Old Target]]\n", encoding="utf-8")

            report = refactor_article(
                "posts/old/target.md",
                "posts/new/New Target.md",
                content_dir=content,
                static_images_dir=images,
                project_root=root,
                preprocess=False,
            )

            self.assertEqual(report["moved_to"], "posts/new/New Target.md")
            self.assertFalse(source.exists())
            self.assertTrue((content / "posts" / "new" / "New Target.md").exists())
            self.assertIn("[[New Target]]", ref.read_text(encoding="utf-8"))
            self.assertTrue((content / "articles.json").exists())
            self.assertTrue((content / "links.json").exists())

    def test_refactor_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content = root / "content"
            images = root / "static" / "images"
            (content / "posts").mkdir(parents=True)
            images.mkdir(parents=True)
            (content / "posts" / "a.md").write_text("---\ntitle: A\n---\n", encoding="utf-8")
            (content / "posts" / "b.md").write_text("---\ntitle: B\n---\n", encoding="utf-8")

            with self.assertRaisesRegex(FileExistsError, "target exists"):
                refactor_article(
                    "posts/a.md",
                    "posts/b.md",
                    content_dir=content,
                    static_images_dir=images,
                    project_root=root,
                    preprocess=False,
                )
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run python -m unittest tests.test_content_refactor -v
```

Expected: import failure.

- [ ] **Step 3: Implement content refactor**

Create `src/hugo_blog/pipeline/content_refactor.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

from hugo_blog.pipeline.article_manifest import reconcile_article_manifest
from hugo_blog.pipeline.content_normalize_one import normalize_one
from hugo_blog.pipeline.link_manifest import LinkManifest
from hugo_blog.pipeline.metadata import update_core_front_matter
from hugo_blog.pipeline.wikilinks import WIKI_LINK_PATTERN, parse_wiki_link_inner
from hugo_blog.static_site import StaticSiteManager


def safe_article_filename(title: str) -> str:
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", title.strip()).strip("_")
    return f"{stem or 'article'}.md"


def validate_target(content_dir: Path, source_rel_path: str, target_rel_path: str) -> tuple[Path, Path]:
    source = (content_dir / source_rel_path).resolve()
    target = (content_dir / target_rel_path).resolve()
    root = content_dir.resolve()
    if root not in source.parents or root not in target.parents:
        raise ValueError("path escapes content dir")
    if source.suffix != ".md" or target.suffix != ".md":
        raise ValueError("source and target must be markdown")
    if not source.exists():
        raise FileNotFoundError(source_rel_path)
    if target.exists():
        raise FileExistsError(f"target exists: {target_rel_path}")
    return source, target


def refactor_article(
    source_rel_path: str,
    target_rel_path: str,
    *,
    content_dir: Path,
    static_images_dir: Path,
    project_root: Path,
    preprocess: bool = True,
) -> dict:
    source, target = validate_target(content_dir, source_rel_path, target_rel_path)
    before = reconcile_article_manifest(content_dir)
    source_record = before.by_path(source_rel_path)
    old_names = set([source_record.title, Path(source_rel_path).stem, source_rel_path.removesuffix(".md")])

    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)

    after = reconcile_article_manifest(content_dir)
    target_record = after.by_path(target_rel_path)
    new_name = target_record.title or Path(target_rel_path).stem
    updated_refs = rewrite_references(content_dir, old_names, new_name)

    normalize_result = normalize_one(
        target_rel_path,
        content_dir=content_dir,
        static_images_dir=static_images_dir,
        project_root=project_root,
        use_llm=False,
        preprocess=False,
    )
    reconcile_article_manifest(content_dir)
    LinkManifest.build(content_dir).save()
    if preprocess:
        StaticSiteManager(project_root=project_root).preprocess_preview(force=True)

    return {
        "moved_from": source_rel_path,
        "moved_to": target_rel_path,
        "updated_references": updated_refs,
        "manifest_updated": True,
        "normalized": bool(normalize_result["changes"]),
        "validation": normalize_result["validation"],
        "warnings": [],
        "errors": [],
    }


def rewrite_references(content_dir: Path, old_names: set[str], new_name: str) -> list[dict]:
    changed = []
    for path in sorted(content_dir.rglob("*.md")):
        if path.relative_to(content_dir).parts[:1] == ("pending",):
            continue
        original = path.read_text(encoding="utf-8")
        count = 0

        def replace(match):
            nonlocal count
            if match.group(1):
                return match.group(0)
            inner = match.group(2).strip()
            target, alias, anchor = parse_wiki_link_inner(inner)
            base = target.removesuffix(".md")
            if target not in old_names and base not in old_names:
                return match.group(0)
            next_target = f"{new_name}#{anchor}" if anchor else new_name
            next_inner = f"{next_target}|{alias}" if alias and alias != new_name else next_target
            count += 1
            return f"[[{next_inner}]]"

        updated = WIKI_LINK_PATTERN.sub(replace, original)
        if count:
            path.write_text(updated, encoding="utf-8")
            changed.append({"path": path.relative_to(content_dir).as_posix(), "count": count})
    return changed
```

- [ ] **Step 4: Add pending helper methods to Admin**

In `src/hugo_blog/preview/admin.py`, import:

```python
from hugo_blog.pipeline.content_refactor import refactor_article, safe_article_filename
```

Add methods:

```python
def move_to_pending(self, rel_path: str) -> dict:
    target = f"pending/{rel_path}"
    return refactor_article(
        rel_path,
        target,
        content_dir=self.content_dir,
        static_images_dir=self.project_root / "static" / "images",
        project_root=self.project_root,
    )

def refactor_content(self, source: str, target: str) -> dict:
    return refactor_article(
        source,
        target,
        content_dir=self.content_dir,
        static_images_dir=self.project_root / "static" / "images",
        project_root=self.project_root,
    )
```

Add POST endpoints:

```python
if parsed.path == "/api/content/move-to-pending":
    payload = self._read_json()
    body = json.dumps(app.move_to_pending(str(payload["path"])), ensure_ascii=False).encode("utf-8")
    self._send_json(body)
    return

if parsed.path == "/api/content/refactor":
    payload = self._read_json()
    body = json.dumps(app.refactor_content(str(payload["source"]), str(payload["target"])), ensure_ascii=False).encode("utf-8")
    self._send_json(body)
    return
```

- [ ] **Step 5: Run refactor tests**

Run:

```bash
uv run python -m unittest tests.test_content_refactor tests.test_admin_server -v
```

Expected: tests pass.

## Task 5: LLM Suggestions

**Files:**
- Create: `src/hugo_blog/pipeline/content_suggestions.py`
- Modify: `src/hugo_blog/llm/client.py`
- Modify: `src/hugo_blog/preview/admin.py`
- Test: `tests/test_content_suggestions.py`

- [ ] **Step 1: Write failing suggestions tests**

Create `tests/test_content_suggestions.py`:

```python
import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.content_suggestions import validate_suggested_target


class ContentSuggestionsTest(unittest.TestCase):
    def test_validate_suggested_target_accepts_safe_markdown_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts" / "数学").mkdir(parents=True)

            target = validate_suggested_target("posts/数学/几何/foo.md", content)

            self.assertEqual(target, "posts/数学/几何/foo.md")

    def test_validate_suggested_target_rejects_escape_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            (content / "posts" / "foo.md").write_text("# Foo\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "relative content path"):
                validate_suggested_target("../foo.md", content)
            with self.assertRaisesRegex(FileExistsError, "target exists"):
                validate_suggested_target("posts/foo.md", content)
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run python -m unittest tests.test_content_suggestions -v
```

Expected: import failure.

- [ ] **Step 3: Extend LLM client with JSON helper**

Modify `src/hugo_blog/llm/client.py`, add:

```python
def parse_json_response(raw: str):
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)
```

Add method to `LLMClient`:

```python
def complete_json(self, *, prompt: str, timeout: int = 60):
    if not self.config.available:
        raise RuntimeError("LLM config is required")
    payload = {
        "model": self.config.model,
        "messages": [
            {"role": "system", "content": "只输出严格 JSON。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        f"{self.config.base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    return parse_json_response(content)
```

- [ ] **Step 4: Implement suggestions module**

Create `src/hugo_blog/pipeline/content_suggestions.py`:

```python
from __future__ import annotations

from pathlib import Path

from hugo_blog.llm.client import LLMClient
from hugo_blog.pipeline.content_inventory import iter_managed_markdown_files
from hugo_blog.pipeline.metadata import parse_front_matter


def validate_suggested_target(target_path: str, content_dir: Path, *, allow_pending: bool = False) -> str:
    normalized = target_path.strip().replace("\\", "/").lstrip("/")
    if not normalized or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("target must be a relative content path")
    if not normalized.endswith(".md"):
        raise ValueError("target must be a markdown file")
    if normalized.startswith("pending/") and not allow_pending:
        raise ValueError("pending target requires pending operation")
    target = (content_dir / normalized).resolve()
    root = content_dir.resolve()
    if root not in target.parents:
        raise ValueError("target must be inside content")
    if target.exists():
        raise FileExistsError(f"target exists: {normalized}")
    return normalized


def directory_tree(content_dir: Path) -> list[str]:
    dirs = set()
    for path in iter_managed_markdown_files(content_dir, scope="normal"):
        dirs.add(path.parent.relative_to(content_dir).as_posix())
    return sorted(dirs)


def suggest_restore_targets(rel_path: str, *, content_dir: Path, llm_client: LLMClient) -> list[dict]:
    source = content_dir / rel_path
    text = source.read_text(encoding="utf-8")
    metadata, body, _ = parse_front_matter(text)
    prompt = (
        "你是中文技术博客的信息架构助手。根据文章标题、正文和现有目录，给出 3 到 5 个目标 Markdown 路径建议。"
        "只输出 JSON 数组，每项包含 target_path, reason, confidence。"
        "target_path 必须是 content 目录下的相对路径，以 .md 结尾，可以比现有目录多一个子目录层级。"
        f"\n现有目录:\n{directory_tree(content_dir)}"
        f"\n当前路径: {rel_path}"
        f"\n标题: {metadata.get('title') or source.stem}"
        f"\n正文片段:\n{body[:4000]}"
    )
    raw = llm_client.complete_json(prompt=prompt)
    suggestions = []
    for item in raw if isinstance(raw, list) else []:
        target = validate_suggested_target(str(item.get("target_path", "")), content_dir)
        suggestions.append({
            "target_path": target,
            "reason": str(item.get("reason", "")),
            "confidence": float(item.get("confidence", 0)),
        })
    return suggestions[:5]
```

- [ ] **Step 5: Wire suggestion endpoints**

In `src/hugo_blog/preview/admin.py`, import:

```python
from hugo_blog.llm.client import LLMClient, config_from_env
from hugo_blog.pipeline.content_suggestions import suggest_restore_targets
```

Add method:

```python
def restore_suggestions(self, rel_path: str) -> dict:
    client = LLMClient(config_from_env(self.project_root))
    suggestions = suggest_restore_targets(rel_path, content_dir=self.content_dir, llm_client=client)
    return {"path": rel_path, "suggestions": suggestions}
```

Add POST route:

```python
if parsed.path == "/api/content/restore-suggestions":
    payload = self._read_json()
    body = json.dumps(app.restore_suggestions(str(payload["path"])), ensure_ascii=False).encode("utf-8")
    self._send_json(body)
    return
```

- [ ] **Step 6: Run suggestion tests**

Run:

```bash
uv run python -m unittest tests.test_content_suggestions -v
```

Expected: tests pass.

## Task 6: Admin UI Listing, Sorting, Selection, Normalize

**Files:**
- Modify: `src/hugo_blog/preview/admin_ui/src/App.tsx`
- Modify: `src/hugo_blog/preview/admin_ui/src/styles.css`

- [ ] **Step 1: Extend `Page` and view state**

In `App.tsx`, keep `SortKey = 'modified' | 'date' | 'title' | 'directory'`, add:

```ts
type Scope = 'normal' | 'pending';

type NormalizeResult = {
  path: string;
  ok: boolean;
  changes: string[];
  validation: ValidationReport;
};
```

Inside `AdminView`, add state:

```ts
const [scope, setScope] = useState<Scope>('normal');
const [selected, setSelected] = useState<Set<string>>(new Set());
```

- [ ] **Step 2: Fetch pages with scope**

Change `loadPages` to:

```ts
async function loadPages(nextScope = scope) {
  const response = await fetch(`/api/content?scope=${nextScope}`);
  const data = await response.json() as Page[];
  setPages(data);
  setDrafts(Object.fromEntries(data.map((page) => [page.path, draftFromPage(page)])));
}
```

- [ ] **Step 3: Add sortable column helper**

Use existing `compareValues`, ensure sorting maps:

```ts
const visiblePages = useMemo(() => {
  return [...filteredPages].sort((a, b) => {
    if (sortKey === 'title') return compareValues(a.title, b.title, sortDesc);
    if (sortKey === 'date') return compareValues(a.date || '', b.date || '', sortDesc);
    if (sortKey === 'directory') return compareValues(a.directory || '', b.directory || '', sortDesc);
    return compareValues(a.modified || '', b.modified || '', sortDesc);
  });
}, [filteredPages, sortKey, sortDesc]);
```

- [ ] **Step 4: Add normalize actions**

Add functions:

```ts
async function normalizeOne(path: string) {
  setMessage(`正在 normalize ${path}...`);
  const response = await fetch('/api/content/normalize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  const data = await response.json() as NormalizeResult;
  setMessage(data.ok ? `Normalize 完成: ${path}` : `Normalize 失败: ${path}`);
  await loadPages();
}

async function normalizeSelected() {
  const paths = [...selected];
  setMessage(`正在 normalize ${paths.length} 篇文章...`);
  const response = await fetch('/api/content/normalize-batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paths }),
  });
  const data = await response.json() as { ok: boolean; results: NormalizeResult[] };
  setMessage(data.ok ? `Normalize 完成: ${paths.length} 篇` : '部分文章 normalize 失败');
  setSelected(new Set());
  await loadPages();
}
```

- [ ] **Step 5: Add row controls and bulk toolbar**

In toolbar JSX add:

```tsx
<select value={scope} onChange={(event) => {
  const next = event.target.value as Scope;
  setScope(next);
  setSelected(new Set());
  void loadPages(next);
}}>
  <option value="normal">常规内容</option>
  <option value="pending">Pending</option>
</select>
<button disabled={!selected.size} onClick={() => void normalizeSelected()}>Normalize selected</button>
```

In table header add checkbox:

```tsx
<th><input type="checkbox" checked={selected.size > 0 && selected.size === visiblePages.length} onChange={(event) => {
  setSelected(event.target.checked ? new Set(visiblePages.map((page) => page.path)) : new Set());
}} /></th>
```

In table row add:

```tsx
<td><input type="checkbox" checked={selected.has(page.path)} onChange={(event) => {
  const next = new Set(selected);
  if (event.target.checked) next.add(page.path); else next.delete(page.path);
  setSelected(next);
}} /></td>
<button onClick={() => void normalizeOne(page.path)}>Normalize</button>
```

- [ ] **Step 6: Build Admin UI**

Run:

```bash
npm run build
```

from `src/hugo_blog/preview/admin_ui`.

Expected: Vite build succeeds.

## Task 7: Admin UI Pending and Refactor

**Files:**
- Modify: `src/hugo_blog/preview/admin_ui/src/App.tsx`
- Modify: `src/hugo_blog/preview/admin_ui/src/styles.css`

- [ ] **Step 1: Add pending actions**

Add functions:

```ts
async function moveToPending(path: string) {
  setMessage(`正在移动到 pending: ${path}`);
  const response = await fetch('/api/content/move-to-pending', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  const data = await response.json();
  setMessage(data.errors?.length ? `移动失败: ${data.errors.join(', ')}` : `已移动: ${data.moved_to}`);
  await loadPages();
}

async function refactorPath(source: string, target: string) {
  setMessage(`正在移动: ${source}`);
  const response = await fetch('/api/content/refactor', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, target }),
  });
  const data = await response.json();
  setMessage(data.errors?.length ? `移动失败: ${data.errors.join(', ')}` : `已移动: ${data.moved_to}`);
  await loadPages();
}
```

- [ ] **Step 2: Add row buttons by scope**

In normal rows:

```tsx
{scope === 'normal' && <button onClick={() => void moveToPending(page.path)}>Pending</button>}
```

In pending rows:

```tsx
{scope === 'pending' && <button onClick={() => void openRestoreDialog(page.path)}>Restore...</button>}
```

- [ ] **Step 3: Implement restore suggestion modal state**

Add state:

```ts
const [restorePath, setRestorePath] = useState('');
const [restoreSuggestions, setRestoreSuggestions] = useState<Array<{ target_path: string; reason: string; confidence: number }>>([]);
const [manualTarget, setManualTarget] = useState('');
```

Add function:

```ts
async function openRestoreDialog(path: string) {
  setRestorePath(path);
  setManualTarget('');
  setMessage(`正在分析恢复目录: ${path}`);
  const response = await fetch('/api/content/restore-suggestions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
  const data = await response.json() as { suggestions: Array<{ target_path: string; reason: string; confidence: number }> };
  setRestoreSuggestions(data.suggestions || []);
  setMessage('');
}
```

- [ ] **Step 4: Add modal JSX**

Render after table:

```tsx
{restorePath && (
  <section className="modalPanel">
    <h2>恢复 Pending 文章</h2>
    <p>{restorePath}</p>
    <div className="candidateGrid">
      {restoreSuggestions.map((item) => (
        <button key={item.target_path} className="candidateCard" onClick={() => void refactorPath(restorePath, item.target_path)}>
          <strong>{item.target_path}</strong>
          <span>{item.reason}</span>
          <small>{Math.round(item.confidence * 100)}%</small>
        </button>
      ))}
    </div>
    <input value={manualTarget} onChange={(event) => setManualTarget(event.target.value)} placeholder="手动输入目标路径，例如 posts/数学/foo.md" />
    <button disabled={!manualTarget} onClick={() => void refactorPath(restorePath, manualTarget)}>Move</button>
    <button onClick={() => setRestorePath('')}>Close</button>
  </section>
)}
```

- [ ] **Step 5: Add CSS**

In `styles.css`:

```css
.modalPanel {
  background: #fff;
  border: 1px solid #dde3ea;
  border-radius: 8px;
  margin-top: 16px;
  padding: 16px;
}
.candidateGrid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}
.candidateCard {
  align-items: flex-start;
  display: grid;
  gap: 6px;
  text-align: left;
}
.candidateCard span,
.candidateCard small {
  color: #667085;
}
```

- [ ] **Step 6: Build Admin UI**

Run:

```bash
npm run build
```

Expected: Vite build succeeds.

## Task 8: Suggestions Page

**Files:**
- Modify: `src/hugo_blog/preview/admin.py`
- Modify: `src/hugo_blog/preview/admin_ui/src/App.tsx`
- Test: extend `tests/test_admin_server.py`

- [ ] **Step 1: Add minimal suggestions API test**

Add to `tests/test_admin_server.py`:

```python
def test_suggestions_endpoint_returns_list_shape(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        content = root / "content"
        (content / "posts").mkdir(parents=True)
        (root / "static" / "images").mkdir(parents=True)
        (content / "posts" / "post.md").write_text("---\ntitle: Post\n---\n", encoding="utf-8")

        data = BlogAdminApp(project_root=root, content_dir=content).content_suggestions()

        self.assertIn("suggestions", data)
        self.assertIsInstance(data["suggestions"], list)
```

- [ ] **Step 2: Implement non-LLM suggestions shell**

In `src/hugo_blog/preview/admin.py`, add:

```python
def content_suggestions(self) -> dict:
    pages = self.list_pages(scope="normal")
    suggestions = [
        {"type": "Normalize", "path": page["path"], "reason": "文章尚未完全归一化"}
        for page in pages
        if not page.get("normalized", True)
    ]
    return {"suggestions": suggestions}
```

Add POST route:

```python
if parsed.path == "/api/content/suggestions":
    body = json.dumps(app.content_suggestions(), ensure_ascii=False).encode("utf-8")
    self._send_json(body)
    return
```

- [ ] **Step 3: Add Suggestions nav**

Change `TopNav` active type:

```ts
function TopNav({ active }: { active: 'admin' | 'docs' | 'issues' | 'editor' | 'suggestions' })
```

Add nav link:

```tsx
<a className={active === 'suggestions' ? 'active' : ''} href="/suggestions/">Suggestions</a>
```

Ensure router maps `/suggestions/` to `SuggestionsView`.

- [ ] **Step 4: Implement SuggestionsView**

Add:

```tsx
function SuggestionsView() {
  const [items, setItems] = useState<Array<{ type: string; path: string; reason: string }>>([]);
  const [message, setMessage] = useState('');

  async function load() {
    setMessage('正在生成建议...');
    const response = await fetch('/api/content/suggestions', { method: 'POST' });
    const data = await response.json() as { suggestions: Array<{ type: string; path: string; reason: string }> };
    setItems(data.suggestions || []);
    setMessage('');
  }

  useEffect(() => { void load(); }, []);

  return (
    <main>
      <TopNav active="suggestions" />
      {message && <div className="message">{message}</div>}
      <section className="issuesShell">
        {items.map((item) => (
          <article className="issueGroup" key={`${item.type}:${item.path}`}>
            <header>
              <div>
                <h2>{item.type}</h2>
                <p>{item.path}</p>
              </div>
            </header>
            <p>{item.reason}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
```

- [ ] **Step 5: Build UI and run Admin tests**

Run:

```bash
uv run python -m unittest tests.test_admin_server -v
npm run build
```

Expected: tests and build pass.

## Task 9: Serve Startup Reconcile

**Files:**
- Modify: `src/hugo_blog/preview/serve.py`
- Modify: `src/hugo_blog/pipeline/export.py`
- Test: extend `tests/test_tooling.py`

- [ ] **Step 1: Add test for startup reconcile hook**

In `tests/test_tooling.py`, add:

```python
def test_preprocess_creates_article_manifest(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        content = root / "content"
        temp = root / ".hugo_temp_content"
        (content / "posts").mkdir(parents=True)
        (content / "posts" / "post.md").write_text("---\ntitle: Post\n---\nBody\n", encoding="utf-8")

        preprocess_content_dir(content_dir=content, temp_dir=temp, force=True)

        self.assertTrue((content / "articles.json").exists())
        self.assertIn("id:", (content / "posts" / "post.md").read_text(encoding="utf-8"))
```

- [ ] **Step 2: Modify export preprocess**

In `src/hugo_blog/pipeline/export.py`, import:

```python
from hugo_blog.pipeline.article_manifest import reconcile_article_manifest
```

Before `md_files = list(iter_content_markdown_files(content_path))`, add:

```python
reconcile_article_manifest(content_path)
```

- [ ] **Step 3: Run tooling test**

Run:

```bash
uv run python -m unittest tests.test_tooling -v
```

Expected: tests pass.

## Task 10: Full Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run full Python test suite**

Run:

```bash
uv run python -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Build Admin UI**

Run:

```bash
npm run build
```

from `src/hugo_blog/preview/admin_ui`.

Expected: Vite build succeeds.

- [ ] **Step 3: Build Hugo site**

Run:

```bash
uv run python scripts/build.py
```

Expected: Hugo build succeeds. The existing `Search page not found` warning is acceptable.

- [ ] **Step 4: Start preview and Admin**

Run:

```bash
timeout 8s uv run python scripts/serve.py --no-watch --no-admin
```

Expected: Hugo prints a `Web Server is available at http://...:1313/` line before timeout exits with code 124.

- [ ] **Step 5: Start full background preview for manual Admin verification**

Run:

```bash
setsid -f bash -lc 'cd /home/lixiang/blog/hugo-blog && exec .venv/bin/python scripts/serve.py > /tmp/hugo-blog-serve.log 2>&1'
sleep 4
ss -ltnp | rg ':(1313|1314)\b'
curl -s http://127.0.0.1:1314/api/validation
```

Expected: ports 1313 and 1314 are listening; validation JSON has `"ok": true`.

## Self-Review

Spec coverage:

- Admin normalize button and batch normalize: Tasks 3 and 6.
- Sort by Title / Date / Modified: Task 6.
- Pending move and restore: Tasks 4 and 7.
- LLM restore choices: Tasks 5 and 7.
- Suggestions page: Task 8.
- Unified rename/move module: Task 4.
- UI title rename must use refactor module: covered by Task 4 API and Task 7 refactor UI foundation.
- Article manifest with stable IDs: Task 1.
- Startup detection for Obsidian external move/delete/add: Tasks 1 and 9.
- Link/image/article manifest integration: Tasks 1, 3, 4, 9.

Placeholder scan:

- No `TBD` markers.
- No intentionally unspecified function signatures.
- Dangerous deletion is excluded from Admin normalize.

Type consistency:

- `ArticleManifest`, `ArticleRecord`, `normalize_one`, `refactor_article`, and `suggest_restore_targets` signatures are defined before use.
- Admin endpoints use JSON shapes consumed by the React plan.
