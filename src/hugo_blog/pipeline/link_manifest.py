from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from hugo_blog.pipeline.content_filters import iter_content_markdown_files
from hugo_blog.pipeline.wikilinks import parse_front_matter_draft, parse_front_matter_title

MANIFEST_NAME = "links.json"


def normalize_link_key(value: str) -> str:
    return value.strip().replace("\\", "/").removesuffix(".md")


@dataclass
class LinkManifest:
    content_dir: Path
    entries: dict[str, str] = field(default_factory=dict)
    preferred: dict[str, str] = field(default_factory=dict)
    titles: dict[str, str] = field(default_factory=dict)
    drafts: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, content_dir: Path) -> "LinkManifest":
        path = content_dir / MANIFEST_NAME
        if not path.exists():
            return cls(content_dir=content_dir)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        return cls(
            content_dir=content_dir,
            entries={str(k): str(v).replace("\\", "/") for k, v in payload.get("entries", {}).items()},
            preferred={str(k).replace("\\", "/"): str(v) for k, v in payload.get("preferred", {}).items()},
            titles={str(k).replace("\\", "/"): str(v) for k, v in payload.get("titles", {}).items()},
            drafts={str(k).replace("\\", "/"): bool(v) for k, v in payload.get("drafts", {}).items()},
        )

    @classmethod
    def build(cls, content_dir: Path) -> "LinkManifest":
        candidates: dict[str, list[str]] = {}
        titles: dict[str, str] = {}
        drafts: dict[str, bool] = {}

        for md_file in iter_content_markdown_files(content_dir):
            rel_path = md_file.relative_to(content_dir).as_posix()
            without_ext = rel_path.removesuffix(".md")
            stem = Path(without_ext).name
            text = md_file.read_text(encoding="utf-8")
            title = parse_front_matter_title(text)
            drafts[rel_path] = parse_front_matter_draft(text)
            if title:
                titles[rel_path] = title
            for key in {rel_path, without_ext, stem, title or ""}:
                normalized = normalize_link_key(key)
                if normalized:
                    candidates.setdefault(normalized, []).append(rel_path)

        entries = {
            key: paths[0]
            for key, paths in candidates.items()
            if len(set(paths)) == 1
        }
        manifest = cls(content_dir=content_dir, entries=entries, titles=titles, drafts=drafts)
        manifest.preferred = {
            rel_path: manifest._choose_preferred_name(rel_path)
            for rel_path in sorted({path for paths in candidates.values() for path in paths})
        }
        return manifest

    @property
    def path(self) -> Path:
        return self.content_dir / MANIFEST_NAME

    def save(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "entries": dict(sorted(self.entries.items())),
                    "preferred": dict(sorted(self.preferred.items())),
                    "titles": dict(sorted(self.titles.items())),
                    "drafts": dict(sorted(self.drafts.items())),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def resolve(self, target: str) -> str | None:
        key = normalize_link_key(strip_anchor(target)[0])
        if not key:
            return None
        direct = self.entries.get(key)
        if direct:
            return direct
        lower_matches = {path for entry_key, path in self.entries.items() if entry_key.lower() == key.lower()}
        if len(lower_matches) == 1:
            return next(iter(lower_matches))
        return None

    def preferred_name(self, rel_path: str) -> str:
        return self.preferred.get(rel_path, Path(rel_path).stem)

    def is_draft(self, rel_path: str) -> bool:
        return bool(self.drafts.get(rel_path))

    def _choose_preferred_name(self, rel_path: str) -> str:
        title = self.titles.get(rel_path)
        if title and self.resolve(title) == rel_path:
            return title
        stem = Path(rel_path).stem
        if self.resolve(stem) == rel_path:
            return stem
        return rel_path.removesuffix(".md")


def strip_anchor(target: str) -> tuple[str, str | None]:
    if "#" not in target:
        return target, None
    base, anchor = target.split("#", 1)
    return base, anchor or None


def slugify_alias(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())
