from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from hugo_blog.paths import PROJECT_ROOT
from hugo_blog.pipeline.export import preprocess_content_dir
from hugo_blog.pipeline.validate import ValidationReport, validate_content_tree
from hugo_blog.tools.hugo import default_hugo_path, install_hugo


@dataclass
class StaticSiteManager:
    project_root: Path = PROJECT_ROOT
    hugo_bin: Path | None = None

    def ensure_hugo(self) -> Path:
        if self.hugo_bin is None:
            self.hugo_bin = default_hugo_path(self.project_root)
        if not self.hugo_bin.exists():
            self.hugo_bin = install_hugo(project_root=self.project_root)
        return self.hugo_bin

    def preprocess_build(self, *, force: bool = True) -> str | None:
        return preprocess_content_dir(force=force)

    def preprocess_preview(self, *, force: bool = True) -> str | None:
        return preprocess_content_dir(force=force, include_docs=True)

    def validate_content(
        self,
        *,
        content_dir: Path | None = None,
        processable_only: bool = False,
    ) -> ValidationReport:
        root = self.project_root
        target_content_dir = content_dir or root / "content"
        if not target_content_dir.is_absolute():
            target_content_dir = root / target_content_dir
        return validate_content_tree(
            content_dir=target_content_dir,
            static_images_dir=root / "static" / "images",
            processable_only=processable_only,
        )

    def build_command(
        self,
        *,
        content_dir: str,
        include_drafts: bool = False,
        minify: bool = True,
        destination: str | None = None,
    ) -> list[str]:
        hugo_bin = str(self.hugo_bin or default_hugo_path(self.project_root))
        command = [hugo_bin, "--contentDir", content_dir]
        if minify:
            command.append("--minify")
        command.append("--cleanDestinationDir")
        if include_drafts:
            command.append("-D")
        if destination:
            command.extend(["--destination", destination])
        return command

    def run_build(
        self,
        *,
        content_dir: str,
        include_drafts: bool = False,
        minify: bool = True,
        destination: str | None = None,
    ) -> int:
        self.ensure_hugo()
        command = self.build_command(
            content_dir=content_dir,
            include_drafts=include_drafts,
            minify=minify,
            destination=destination,
        )
        return subprocess.call(command, cwd=self.project_root)

    def background_serve_command(
        self,
        *,
        include_drafts: bool = False,
        script: Path | None = None,
        python_bin: Path | None = None,
    ) -> list[str]:
        command = [
            str(python_bin or Path(sys.executable)),
            str(script or self.project_root / "scripts" / "serve.py"),
        ]
        if not include_drafts:
            command.append("--no-drafts")
        return command


_STATIC_SITE_MANAGER: StaticSiteManager | None = None


def static_site_manager() -> StaticSiteManager:
    global _STATIC_SITE_MANAGER
    if _STATIC_SITE_MANAGER is None:
        _STATIC_SITE_MANAGER = StaticSiteManager()
    return _STATIC_SITE_MANAGER
