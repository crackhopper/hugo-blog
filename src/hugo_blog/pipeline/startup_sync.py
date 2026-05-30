from __future__ import annotations

from pathlib import Path

from hugo_blog.pipeline.article_manifest import reconcile_article_manifest
from hugo_blog.pipeline.link_manifest import LinkManifest


def sync_content_manifests(content_dir: Path) -> None:
    reconcile_article_manifest(content_dir)
    LinkManifest.build(content_dir).save()
