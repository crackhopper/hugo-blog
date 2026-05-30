#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from hugo_blog.paths import PROJECT_ROOT
from hugo_blog.pipeline.content_inventory import iter_managed_markdown_files, list_content_pages
from hugo_blog.pipeline.content_refactor import refactor_article
from hugo_blog.pipeline.content_suggestions import suggest_article_moves
from hugo_blog.pipeline.image_normalizer import normalize_markdown_images
from hugo_blog.pipeline.metadata import metadata_for_listing, update_core_front_matter
from hugo_blog.pipeline.normalize_service import normalize_article
from hugo_blog.pipeline.validate import ValidationReport, validate_content_tree, validate_markdown_text
from hugo_blog.pipeline.wikilinks import build_wikilink_index, transform_obsidian_links
from hugo_blog.static_site import StaticSiteManager, static_site_manager

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
DOC_SLUG_RE = re.compile(r"[^\w\u4e00-\u9fff-]+")
DOC_ORDER = {
    "architecture.md": 10,
    "python-tooling.md": 20,
    "content-pipeline.md": 30,
    "llm-metadata.md": 40,
    "deployment.md": 50,
}
DOC_SECTION_ORDER = {
    "": 0,
    "source": 100,
}


def admin_ui_dist_dir(project_root: Path = PROJECT_ROOT) -> Path:
    return project_root / "src" / "hugo_blog" / "preview" / "admin_ui" / "dist"


def admin_ui_index_path(project_root: Path = PROJECT_ROOT) -> Path:
    return admin_ui_dist_dir(project_root) / "index.html"


def missing_admin_ui_html() -> str:
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>Blog Admin</title></head>
<body style="font-family: system-ui, sans-serif; padding: 24px">
<h1>Blog Admin UI is not built</h1>
<p>Run <code>python -m hugo_blog.preview.admin_ui_build</code>, then refresh this page.</p>
</body></html>"""


class BlogAdminApp:
    def __init__(
        self,
        *,
        project_root: Path = PROJECT_ROOT,
        content_dir: Path | None = None,
        site: StaticSiteManager | None = None,
    ):
        self.project_root = project_root
        self.content_dir = content_dir or project_root / "content"
        self.docs_dir = project_root / "docs"
        self.site = site or static_site_manager()

    def iter_pages(self, *, scope: str = "normal"):
        return list(iter_managed_markdown_files(self.content_dir, scope=scope))

    def list_pages(self, *, status: str = "all", scope: str = "normal") -> list[dict]:
        pages = list_content_pages(self.content_dir, scope=scope)
        if status == "draft":
            pages = [page for page in pages if page["draft"]]
        elif status == "published":
            pages = [page for page in pages if not page["draft"]]
        return sorted(pages, key=lambda page: page["modified"], reverse=True)

    def update_front_matter(self, rel_path: str, updates: dict) -> dict:
        target = self._content_path(rel_path)

        clean_updates = {
            "title": str(updates.get("title", "")).strip(),
            "date": str(updates.get("date", "")).strip(),
            "tags": [str(tag).strip() for tag in updates.get("tags", []) if str(tag).strip()],
            "draft": bool(updates.get("draft", False)),
        }
        update_core_front_matter(target, clean_updates)
        self.site.preprocess_preview(force=True)
        return metadata_for_listing(target, self.content_dir)

    def _content_path(self, rel_path: str, *, allow_pending: bool = False) -> Path:
        target = (self.content_dir / rel_path).resolve()
        content_root = self.content_dir.resolve()
        if content_root not in target.parents and target != content_root:
            raise ValueError("path escapes content dir")
        if not target.exists() or target.suffix != ".md":
            raise FileNotFoundError(rel_path)
        rel_parts = target.relative_to(self.content_dir).parts
        if rel_parts and rel_parts[0] == "pending" and not allow_pending:
            raise ValueError("pending content requires explicit pending operation")
        return target

    def validation_report(self) -> dict:
        return self._validation_report().to_dict()

    def _validation_report(self) -> ValidationReport:
        return validate_content_tree(
            content_dir=self.content_dir,
            static_images_dir=self.project_root / "static" / "images",
            processable_only=True,
        )

    def _validation_for_text(self, rel_path: str, text: str) -> dict:
        return ValidationReport(
            issues=validate_markdown_text(
                text,
                source_path=rel_path,
                static_images_dir=self.project_root / "static" / "images",
            )
        ).to_dict()

    def _issues_for_path(self, rel_path: str) -> list[dict]:
        return [
            issue
            for issue in self.validation_report()["issues"]
            if issue["source_path"] == rel_path
        ]

    def get_content(self, rel_path: str) -> dict:
        target = self._content_path(rel_path)
        rel = target.relative_to(self.content_dir).as_posix()
        text = target.read_text(encoding="utf-8")
        return {
            "path": rel,
            "content": text,
            "page": metadata_for_listing(target, self.content_dir),
            "validation": self._validation_for_text(rel, text),
            "issues": self._issues_for_path(rel),
        }

    def update_content(self, rel_path: str, content: str) -> dict:
        target = self._content_path(rel_path)
        rel = target.relative_to(self.content_dir).as_posix()
        target.write_text(content, encoding="utf-8")
        normalize_markdown_images(
            target,
            content_dir=self.content_dir,
            static_images_dir=self.project_root / "static" / "images",
        )
        updated_content = target.read_text(encoding="utf-8")
        self.site.preprocess_preview(force=True)
        return {
            "path": rel,
            "content": updated_content,
            "page": metadata_for_listing(target, self.content_dir),
            "validation": self._validation_report().to_dict(),
            "issues": self._issues_for_path(rel),
        }

    def normalize_page(self, rel_path: str, *, use_llm: bool = True) -> dict:
        result = normalize_article(
            content_dir=self.content_dir,
            static_images_dir=self.project_root / "static" / "images",
            rel_path=rel_path,
            use_llm=use_llm,
        )
        self.site.preprocess_preview(force=True)
        return result

    def refactor_page(self, payload: dict) -> dict:
        result = refactor_article(
            content_dir=self.content_dir,
            static_images_dir=self.project_root / "static" / "images",
            source_rel_path=str(payload.get("source_path", "")),
            target_rel_path=str(payload.get("target_path", "")),
            title=str(payload["title"]).strip() if "title" in payload else None,
            use_llm=bool(payload.get("use_llm", True)),
        )
        self.site.preprocess_preview(force=True)
        return {
            "old_path": result.old_path,
            "new_path": result.new_path,
            "updated_links": result.updated_links,
            "page": result.page,
        }

    def suggest_moves(self, rel_path: str) -> dict:
        suggestions = suggest_article_moves(content_dir=self.content_dir, rel_path=rel_path)
        return {
            "path": rel_path,
            "suggestions": [
                {
                    "target_path": item.target_path,
                    "title": item.title,
                    "reason": item.reason,
                }
                for item in suggestions
            ],
        }

    def content_preview(self, rel_path: str, content: str | None = None) -> dict:
        target = self._content_path(rel_path)
        rel = target.relative_to(self.content_dir).as_posix()
        text = target.read_text(encoding="utf-8") if content is None else content
        transformed = transform_obsidian_links(
            text,
            static_images_dir=self.project_root / "static" / "images",
            wiki_index=build_wikilink_index(self.content_dir),
            verbose=False,
        )
        return {
            "path": rel,
            "content": transformed,
            "validation": self._validation_for_text(rel, text),
        }

    def iter_docs(self) -> list[Path]:
        if not self.docs_dir.exists():
            return []
        return [
            path
            for path in sorted(self.docs_dir.rglob("*.md"))
            if "superpowers" not in path.relative_to(self.docs_dir).parts
        ]

    def _doc_path(self, rel_path: str) -> Path:
        target = (self.docs_dir / rel_path).resolve()
        docs_root = self.docs_dir.resolve()
        if docs_root not in target.parents and target != docs_root:
            raise ValueError("path escapes docs dir")
        if not target.exists() or target.suffix != ".md":
            raise FileNotFoundError(rel_path)
        return target

    def list_docs(self) -> list[dict]:
        docs: list[dict] = []
        for path in self.iter_docs():
            rel_path = path.relative_to(self.docs_dir).as_posix()
            content = _strip_front_matter(path.read_text(encoding="utf-8"))
            title = _doc_title(content, path)
            section = rel_path.split("/", 1)[0] if "/" in rel_path else ""
            docs.append(
                {
                    "path": rel_path,
                    "title": title,
                    "section": section,
                    "parts": list(Path(rel_path).parts),
                    "order": _doc_order(rel_path),
                    "modified": path.stat().st_mtime,
                }
            )
        return sorted(docs, key=lambda item: (item["order"], item["path"]))

    def get_doc(self, rel_path: str) -> dict:
        path = self._doc_path(rel_path)
        content = _strip_front_matter(path.read_text(encoding="utf-8"))
        return {
            "path": path.relative_to(self.docs_dir).as_posix(),
            "title": _doc_title(content, path),
            "content": content,
            "headings": _doc_headings(content),
        }


def _strip_front_matter(text: str) -> str:
    return FRONT_MATTER_RE.sub("", text, count=1).lstrip()


def _doc_title(content: str, path: Path) -> str:
    match = HEADING_RE.search(content)
    if match and len(match.group(1)) == 1:
        return match.group(2).strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def _doc_slug(title: str) -> str:
    slug = title.strip().lower().replace(" ", "-")
    slug = DOC_SLUG_RE.sub("-", slug)
    return re.sub(r"-{2,}", "-", slug).strip("-")


def _doc_headings(content: str) -> list[dict]:
    headings = []
    seen: dict[str, int] = {}
    for match in HEADING_RE.finditer(content):
        title = match.group(2).strip()
        base = _doc_slug(title)
        count = seen.get(base, 0)
        seen[base] = count + 1
        heading_id = base if count == 0 else f"{base}-{count}"
        headings.append({"level": len(match.group(1)), "title": title, "id": heading_id})
    return headings


def _doc_order(rel_path: str) -> int:
    if rel_path in DOC_ORDER:
        return DOC_ORDER[rel_path]
    section = rel_path.split("/", 1)[0] if "/" in rel_path else ""
    return DOC_SECTION_ORDER.get(section, 90) * 1000


def make_handler(app: BlogAdminApp):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if (
                parsed.path in {"/", "/admin", "/admin/", "/docs", "/docs/", "/issues", "/issues/"}
                or parsed.path.startswith("/editor")
            ):
                index = admin_ui_index_path(app.project_root)
                if index.exists():
                    self._send(200, index.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._send(200, missing_admin_ui_html().encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path.startswith("/assets/"):
                target = (admin_ui_dist_dir(app.project_root) / parsed.path.removeprefix("/")).resolve()
                dist = admin_ui_dist_dir(app.project_root).resolve()
                if dist in target.parents and target.exists() and target.is_file():
                    content_type = guess_type(target.name)[0] or "application/octet-stream"
                    self._send(200, target.read_bytes(), content_type)
                    return
            if parsed.path == "/api/pages":
                status = parse_qs(parsed.query).get("status", ["all"])[0]
                body = json.dumps(app.list_pages(status=status), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/api/content":
                query = parse_qs(parsed.query)
                status = query.get("status", ["all"])[0]
                scope = query.get("scope", ["normal"])[0]
                try:
                    body = json.dumps(app.list_pages(status=status, scope=scope), ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            if parsed.path == "/api/docs":
                body = json.dumps(app.list_docs(), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/api/validation":
                body = json.dumps(app.validation_report(), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            content_preview_prefix = "/api/content-preview/"
            if parsed.path.startswith(content_preview_prefix):
                rel_path = unquote(parsed.path[len(content_preview_prefix) :])
                try:
                    body = json.dumps(app.content_preview(rel_path), ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            content_prefix = "/api/content/"
            if parsed.path.startswith(content_prefix):
                rel_path = unquote(parsed.path[len(content_prefix) :])
                try:
                    body = json.dumps(app.get_content(rel_path), ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            prefix = "/api/docs/"
            if parsed.path.startswith(prefix):
                rel_path = unquote(parsed.path[len(prefix) :])
                try:
                    body = json.dumps(app.get_doc(rel_path), ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(404, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/validation/run":
                body = json.dumps(app.validation_report(), ensure_ascii=False).encode("utf-8")
                self._send(200, body, "application/json; charset=utf-8")
                return
            if parsed.path == "/api/content-refactor":
                length = int(self.headers.get("Content-Length", "0"))
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    body = json.dumps(app.refactor_page(payload), ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            normalize_prefix = "/api/content-normalize/"
            if parsed.path.startswith(normalize_prefix):
                rel_path = unquote(parsed.path[len(normalize_prefix) :])
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                    body = json.dumps(
                        app.normalize_page(rel_path, use_llm=bool(payload.get("use_llm", True))),
                        ensure_ascii=False,
                    ).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            suggest_prefix = "/api/content-suggestions/"
            if parsed.path.startswith(suggest_prefix):
                rel_path = unquote(parsed.path[len(suggest_prefix) :])
                try:
                    body = json.dumps(app.suggest_moves(rel_path), ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            self._send(404, b"not found", "text/plain; charset=utf-8")

        def do_PUT(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/preview/drafts":
                length = int(self.headers.get("Content-Length", "0"))
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    include_drafts = bool(payload.get("drafts", True))
                    from hugo_blog.preview.launcher import preview_url, start_background_preview

                    url = preview_url()
                    threading.Timer(
                        0.2,
                        lambda: start_background_preview(include_drafts=include_drafts),
                    ).start()
                    body = json.dumps({"drafts": include_drafts, "url": url}, ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return

            content_preview_prefix = "/api/content-preview/"
            if parsed.path.startswith(content_preview_prefix):
                rel_path = unquote(parsed.path[len(content_preview_prefix) :])
                length = int(self.headers.get("Content-Length", "0"))
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    body = json.dumps(
                        app.content_preview(rel_path, str(payload.get("content", ""))),
                        ensure_ascii=False,
                    ).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return

            content_prefix = "/api/content/"
            if parsed.path.startswith(content_prefix):
                rel_path = unquote(parsed.path[len(content_prefix) :])
                length = int(self.headers.get("Content-Length", "0"))
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    body = json.dumps(
                        app.update_content(rel_path, str(payload.get("content", ""))),
                        ensure_ascii=False,
                    ).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except Exception as exc:
                    self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return

            prefix = "/api/pages/"
            if not parsed.path.startswith(prefix):
                self._send(404, b"not found", "text/plain; charset=utf-8")
                return
            rel_path = unquote(parsed.path[len(prefix) :])
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                page = app.update_front_matter(rel_path, payload)
            except Exception as exc:
                self._send(400, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            body = json.dumps(page, ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")

        def log_message(self, fmt: str, *args) -> None:
            print(f"[admin] {self.address_string()} - {fmt % args}")

    return Handler


def run_server(*, host: str, port: int, project_root: Path = PROJECT_ROOT) -> None:
    app = BlogAdminApp(project_root=project_root)
    server = ThreadingHTTPServer((host, port), make_handler(app))
    print(f"Admin URL: http://{host}:{port}/admin/")
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local blog admin API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1314)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
