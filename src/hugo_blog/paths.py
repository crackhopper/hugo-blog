from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = PROJECT_ROOT / "content"
TEMP_CONTENT_DIR = PROJECT_ROOT / ".hugo_temp_content"
STATIC_IMAGES_DIR = PROJECT_ROOT / "static" / "images"
