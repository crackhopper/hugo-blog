#!/usr/bin/env python3
"""Install non-Python local tools used by this blog project."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from hugo_blog.paths import PROJECT_ROOT

DEFAULT_HUGO_VERSION = "0.148.2"


def default_hugo_path(project_root: Path = PROJECT_ROOT) -> Path:
    suffix = ".exe" if platform.system() == "Windows" else ""
    return project_root / ".tools" / "hugo" / f"hugo{suffix}"


def _normalize_system(system: str) -> str:
    mapping = {
        "Darwin": "darwin",
        "Linux": "linux",
        "Windows": "windows",
    }
    if system not in mapping:
        raise RuntimeError(f"Unsupported Hugo platform: {system}")
    return mapping[system]


def _normalize_arch(machine: str) -> str:
    normalized = machine.lower()
    mapping = {
        "amd64": "amd64",
        "x86_64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    if normalized not in mapping:
        raise RuntimeError(f"Unsupported Hugo architecture: {machine}")
    return mapping[normalized]


def hugo_asset_name(
    *,
    system: str | None = None,
    machine: str | None = None,
    version: str = DEFAULT_HUGO_VERSION,
) -> str:
    os_name = _normalize_system(system or platform.system())
    arch = _normalize_arch(machine or platform.machine())
    extension = "zip" if os_name == "windows" else "tar.gz"
    return f"hugo_extended_{version}_{os_name}-{arch}.{extension}"


def hugo_download_url(version: str, asset_name: str) -> str:
    return (
        "https://github.com/gohugoio/hugo/releases/download/"
        f"v{version}/{asset_name}"
    )


def install_hugo(
    *,
    version: str = DEFAULT_HUGO_VERSION,
    project_root: Path = PROJECT_ROOT,
    force: bool = False,
) -> Path:
    target = default_hugo_path(project_root)
    if target.exists() and not force:
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    asset_name = hugo_asset_name(version=version)
    url = hugo_download_url(version, asset_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / asset_name
        print(f"Downloading Hugo {version}: {url}")
        urllib.request.urlretrieve(url, archive_path)

        extract_dir = Path(temp_dir) / "extract"
        extract_dir.mkdir()
        if asset_name.endswith(".zip"):
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(extract_dir)
        else:
            with tarfile.open(archive_path) as archive:
                archive.extractall(extract_dir)

        source_name = "hugo.exe" if platform.system() == "Windows" else "hugo"
        source = extract_dir / source_name
        if not source.exists():
            raise RuntimeError(f"Hugo executable not found in archive: {asset_name}")

        shutil.copy2(source, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Install project-local tooling.")
    parser.add_argument(
        "--hugo-version",
        default=os.environ.get("HUGO_VERSION", DEFAULT_HUGO_VERSION),
        help=f"Hugo version to install. Default: {DEFAULT_HUGO_VERSION}",
    )
    parser.add_argument("--force", action="store_true", help="Reinstall tools.")
    args = parser.parse_args()

    hugo_bin = install_hugo(version=args.hugo_version, force=args.force)
    print(f"Hugo installed at: {hugo_bin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
