from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Any

from hugo_blog.pipeline.content_filters import is_skipped_content_path
from hugo_blog.pipeline.metadata import parse_front_matter
from hugo_blog.pipeline.wikilinks import (
    collect_document_wiki_links,
    collect_image_references,
    parse_wiki_link_inner,
)

MANIFEST_NAME = "articles.json"
ARTICLE_ID_PREFIX = "art_"


@dataclass
class ArticleRecord:
    id: str
    path: str
    title: str
    draft: bool
    status: str
    fingerprint: str
    modified: str = ""
    normalized_fingerprint: str = ""
    normalized_at: str = ""
    normalized_modified: str = ""
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
        manifest_path = content_dir / MANIFEST_NAME
        if not manifest_path.exists():
            return cls(content_dir=content_dir)
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(content_dir=content_dir)
        if not isinstance(payload, dict):
            return cls(content_dir=content_dir)
        raw_articles = payload.get("articles", {})
        if not isinstance(raw_articles, dict):
            raw_articles = {}
        articles = {}
        for article_id, record in raw_articles.items():
            if not isinstance(record, dict):
                continue
            articles[str(article_id)] = _record_from_payload(str(article_id), record)
        return cls(
            content_dir=content_dir,
            version=_safe_version(payload.get("version", 1)),
            articles=articles,
            path_index=_string_dict(payload.get("path_index", {})),
            title_index=_string_dict(payload.get("title_index", {})),
        )

    def save(self) -> None:
        payload = {
            "version": self.version,
            "articles": {
                article_id: asdict(record)
                for article_id, record in sorted(self.articles.items())
            },
            "path_index": dict(sorted(self.path_index.items())),
            "title_index": dict(sorted(self.title_index.items())),
        }
        self.content_dir.mkdir(parents=True, exist_ok=True)
        (self.content_dir / MANIFEST_NAME).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def by_path(self, rel_path: str) -> ArticleRecord:
        return self.articles[self.path_index[rel_path]]


def iter_article_files(content_dir: Path, *, include_pending: bool = True) -> Iterable[Path]:
    for md_file in sorted(content_dir.rglob("*.md")):
        rel_path = md_file.relative_to(content_dir)
        if rel_path.name == MANIFEST_NAME:
            continue
        if not include_pending and is_skipped_content_path(md_file, content_dir):
            continue
        yield md_file


def _safe_version(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


def _string_dict(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _record_from_payload(article_id: str, payload: dict) -> ArticleRecord:
    return ArticleRecord(
        id=str(payload.get("id") or article_id),
        path=str(payload.get("path") or ""),
        title=str(payload.get("title") or ""),
        draft=bool(payload.get("draft", False)),
        status=str(payload.get("status") or "missing"),
        fingerprint=str(payload.get("fingerprint") or ""),
        modified=str(payload.get("modified") or ""),
        normalized_fingerprint=str(payload.get("normalized_fingerprint") or ""),
        normalized_at=str(payload.get("normalized_at") or ""),
        normalized_modified=str(payload.get("normalized_modified") or ""),
        previous_paths=_string_list(payload.get("previous_paths")),
        aliases=_string_list(payload.get("aliases")),
        outgoing_links=_string_list(payload.get("outgoing_links")),
        incoming_links=_string_list(payload.get("incoming_links")),
        image_keys=_string_list(payload.get("image_keys")),
        last_seen=str(payload.get("last_seen") or ""),
    )


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def reconcile_article_manifest(content_dir: Path) -> ArticleManifest:
    content_dir = Path(content_dir)
    previous = ArticleManifest.load(content_dir)
    current = ArticleManifest(content_dir=content_dir, version=previous.version)
    previous_by_fingerprint = _unique_records_by_fingerprint(previous.articles.values())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for md_file in iter_article_files(content_dir, include_pending=True):
        rel_path = md_file.relative_to(content_dir).as_posix()
        text = md_file.read_text(encoding="utf-8")
        article_id = read_article_id(text)
        current_fingerprint = fingerprint(text)
        previous_record = previous.articles.get(article_id or "")

        if previous_record is None and article_id is None:
            previous_record = previous_by_fingerprint.get(current_fingerprint)
            if previous_record is not None:
                article_id = previous_record.id

        if article_id is None:
            article_id = new_article_id()
        if article_id in current.articles:
            article_id = new_article_id()
            previous_record = None

        updated_text = ensure_front_matter_id(md_file, article_id)
        metadata, _, _ = parse_front_matter(updated_text)
        title = _metadata_title(metadata, md_file)
        record = ArticleRecord(
            id=article_id,
            path=rel_path,
            title=title,
            draft=bool(metadata.get("draft", False)),
            status="pending" if rel_path.startswith("pending/") else "active",
            fingerprint=fingerprint(updated_text),
            modified=_file_modified_iso(md_file),
            normalized_fingerprint=previous_record.normalized_fingerprint if previous_record else "",
            normalized_at=previous_record.normalized_at if previous_record else "",
            normalized_modified=previous_record.normalized_modified if previous_record else "",
            previous_paths=_previous_paths(previous_record, rel_path),
            aliases=_aliases(metadata, title, md_file, previous_record),
            outgoing_links=_outgoing_links(updated_text),
            image_keys=list(dict.fromkeys(collect_image_references(updated_text))),
            last_seen=now,
        )
        current.articles[article_id] = record
        current.path_index[rel_path] = article_id
        for key in [title, title.lower()]:
            current.title_index.setdefault(key, article_id)

    _mark_missing_previous_articles(previous, current)
    _fill_incoming_links(current)
    current.save()
    return current


def mark_article_normalized(content_dir: Path, rel_path: str) -> ArticleRecord:
    records = mark_articles_normalized(content_dir, [rel_path])
    return records[0]


def mark_articles_normalized(content_dir: Path, rel_paths: Iterable[str]) -> list[ArticleRecord]:
    manifest = reconcile_article_manifest(content_dir)
    updated_records: list[ArticleRecord] = []
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    seen: set[str] = set()
    for rel_path in rel_paths:
        normalized_rel_path = rel_path.strip().replace("\\", "/")
        if not normalized_rel_path or normalized_rel_path in seen:
            continue
        seen.add(normalized_rel_path)
        record = manifest.by_path(normalized_rel_path)
        article = content_dir / normalized_rel_path
        text = article.read_text(encoding="utf-8")
        record.modified = _file_modified_iso(article)
        record.normalized_fingerprint = state_fingerprint(text)
        record.normalized_at = now
        record.normalized_modified = record.modified
        updated_records.append(record)
    manifest.save()
    return updated_records


def read_article_id(text: str) -> str | None:
    metadata, _, _ = parse_front_matter(text)
    value = metadata.get("id")
    if value is None:
        return None
    article_id = str(value).strip()
    return article_id or None


def new_article_id() -> str:
    return ARTICLE_ID_PREFIX + secrets.token_hex(16)


def ensure_front_matter_id(md_file: Path, article_id: str) -> str:
    text = md_file.read_text(encoding="utf-8")
    if read_article_id(text) == article_id:
        return text
    updated = _set_front_matter_id(text, article_id)
    md_file.write_text(updated, encoding="utf-8")
    return updated


def _set_front_matter_id(text: str, article_id: str) -> str:
    if not text.startswith("---\n"):
        return f"---\nid: {article_id}\n---\n{text}"
    end = text.find("\n---\n", 4)
    if end == -1:
        return f"---\nid: {article_id}\n---\n{text}"
    block = text[4:end]
    if re.search(r"^id:\s*.*$", block, flags=re.MULTILINE):
        block = re.sub(r"^id:\s*.*$", f"id: {article_id}", block, count=1, flags=re.MULTILINE)
    else:
        block = f"id: {article_id}\n{block}"
    return f"---\n{block}{text[end:]}"


def fingerprint(text: str) -> str:
    normalized = _normalize_for_fingerprint(text)
    digest = hashlib.blake2b(normalized.encode("utf-8"), digest_size=16).hexdigest()
    return f"b2:{digest}"


def state_fingerprint(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.blake2b(normalized.encode("utf-8"), digest_size=16).hexdigest()
    return f"b2:{digest}"


def _file_modified_iso(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    except OSError:
        return ""


def _normalize_for_fingerprint(text: str) -> str:
    _, body, _ = parse_front_matter(text)
    body = re.sub(r"\s+", " ", body.replace("\r\n", "\n")).strip()
    return body


def _unique_records_by_fingerprint(records: Iterable[ArticleRecord]) -> dict[str, ArticleRecord]:
    unique: dict[str, ArticleRecord] = {}
    duplicates: set[str] = set()
    for record in records:
        if not record.fingerprint:
            continue
        if record.fingerprint in unique:
            duplicates.add(record.fingerprint)
        unique[record.fingerprint] = record
    for duplicate in duplicates:
        unique.pop(duplicate, None)
    return unique


def _metadata_title(metadata: dict[str, Any], md_file: Path) -> str:
    title = str(metadata.get("title") or "").strip()
    if title:
        return title
    if md_file.name in {"index.md", "_index.md"}:
        return md_file.parent.name
    return md_file.stem


def _previous_paths(previous_record: ArticleRecord | None, rel_path: str) -> list[str]:
    paths: list[str] = []
    if previous_record is None:
        return paths
    paths.extend(previous_record.previous_paths)
    if previous_record.path != rel_path:
        paths.append(previous_record.path)
    return list(dict.fromkeys(paths))


def _aliases(
    metadata: dict[str, Any],
    title: str,
    md_file: Path,
    previous_record: ArticleRecord | None,
) -> list[str]:
    aliases: list[str] = [title, md_file.stem]
    raw_aliases = metadata.get("aliases")
    if isinstance(raw_aliases, list):
        aliases.extend(str(alias) for alias in raw_aliases if str(alias).strip())
    elif raw_aliases:
        aliases.append(str(raw_aliases))
    if previous_record is not None:
        aliases.extend(previous_record.aliases)
    return list(dict.fromkeys(alias.strip() for alias in aliases if alias.strip()))


def _outgoing_links(text: str) -> list[str]:
    links: list[str] = []
    for raw_link in collect_document_wiki_links(text):
        target, _, anchor = parse_wiki_link_inner(raw_link)
        if anchor and target:
            target = f"{target}#{anchor}"
        if target:
            links.append(target)
    return list(dict.fromkeys(links))


def _mark_missing_previous_articles(previous: ArticleManifest, current: ArticleManifest) -> None:
    for article_id, previous_record in previous.articles.items():
        if article_id in current.articles:
            continue
        record = ArticleRecord(**asdict(previous_record))
        record.status = "missing"
        current.articles[article_id] = record


def _fill_incoming_links(manifest: ArticleManifest) -> None:
    target_candidates: dict[str, set[str]] = {}
    for article_id, record in manifest.articles.items():
        if record.status == "missing":
            continue
        _add_target_key(target_candidates, record.path, article_id)
        _add_target_key(target_candidates, record.path.removesuffix(".md"), article_id)
        _add_target_key(target_candidates, Path(record.path).stem, article_id)
        for alias in record.aliases:
            _add_target_key(target_candidates, alias, article_id)
    target_index = {
        key: next(iter(article_ids))
        for key, article_ids in target_candidates.items()
        if len(article_ids) == 1
    }

    for record in manifest.articles.values():
        record.incoming_links = []

    for source_id, record in manifest.articles.items():
        if record.status == "missing":
            continue
        for link in record.outgoing_links:
            target = link.split("#", 1)[0].removesuffix(".md")
            target_id = target_index.get(target) or target_index.get(target.lower())
            if target_id and target_id != source_id:
                manifest.articles[target_id].incoming_links.append(source_id)

    for record in manifest.articles.values():
        record.incoming_links = sorted(dict.fromkeys(record.incoming_links))


def _add_target_key(index: dict[str, set[str]], key: str, article_id: str) -> None:
    normalized = key.strip().replace("\\", "/")
    if not normalized:
        return
    index.setdefault(normalized, set()).add(article_id)
    index.setdefault(normalized.lower(), set()).add(article_id)
