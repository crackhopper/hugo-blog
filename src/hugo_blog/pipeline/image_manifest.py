from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from hugo_blog.pipeline.wikilinks import IMAGE_EXTENSIONS

MANIFEST_NAME = "images.json"


@dataclass
class ImageManifest:
    images_dir: Path
    entries: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, images_dir: Path) -> "ImageManifest":
        manifest_path = images_dir / MANIFEST_NAME
        if not manifest_path.exists():
            return cls(images_dir=images_dir, entries={})
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        entries = {str(key): str(value).replace("\\", "/").lstrip("/") for key, value in payload.items()}
        return cls(images_dir=images_dir, entries=entries)

    @property
    def path(self) -> Path:
        return self.images_dir / MANIFEST_NAME

    def save(self) -> None:
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(dict(sorted(self.entries.items())), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def set(self, link_name: str, rel_path: str) -> None:
        self.entries[normalize_link_name(link_name)] = normalize_manifest_path(rel_path)

    def get(self, link_name: str) -> str | None:
        return self.entries.get(normalize_link_name(link_name))

    def resolve(self, link_name: str) -> Path | None:
        rel_path = self.get(link_name)
        if not rel_path:
            return None
        return self.images_dir / rel_path

    def find_by_basename(self, link_name: str) -> list[Path]:
        name = Path(normalize_link_name(link_name)).name
        if not name or Path(name).suffix.lower() not in IMAGE_EXTENSIONS:
            return []
        if not self.images_dir.exists():
            return []
        return sorted(
            path
            for path in self.images_dir.rglob(name)
            if path.is_file() and not is_manifest_path(path) and path.suffix.lower() in IMAGE_EXTENSIONS
        )


def normalize_link_name(link_name: str) -> str:
    return unquote(link_name.strip().replace("\\", "/")).lstrip("/")


def normalize_manifest_path(rel_path: str) -> str:
    return unquote(rel_path.strip().replace("\\", "/")).lstrip("/")


def is_manifest_path(path: Path) -> bool:
    return path.name == MANIFEST_NAME
