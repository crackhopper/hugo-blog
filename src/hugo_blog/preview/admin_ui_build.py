from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hugo_blog.paths import PROJECT_ROOT


ADMIN_UI_DIR = PROJECT_ROOT / "src" / "hugo_blog" / "preview" / "admin_ui"


def build_admin_ui(*, admin_ui_dir: Path = ADMIN_UI_DIR) -> int:
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm is required to build the React admin UI.")
    if not (admin_ui_dir / "node_modules").exists():
        install_code = subprocess.call([npm, "install"], cwd=admin_ui_dir)
        if install_code != 0:
            return install_code
    return subprocess.call([npm, "run", "build"], cwd=admin_ui_dir)


def main() -> int:
    return build_admin_ui()


if __name__ == "__main__":
    raise SystemExit(main())
