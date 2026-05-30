from __future__ import annotations

import subprocess
from pathlib import Path

from hugo_blog.paths import PROJECT_ROOT
from hugo_blog.preview.serve import detect_lan_ip
from hugo_blog.static_site import static_site_manager


def build_background_serve_command(
    *,
    script: Path = PROJECT_ROOT / "scripts" / "serve.py",
    python_bin: Path | None = None,
    include_drafts: bool = False,
) -> list[str]:
    return static_site_manager().background_serve_command(
        include_drafts=include_drafts,
        script=script,
        python_bin=python_bin,
    )


def preview_url(*, host: str = "0.0.0.0", port: int = 1313) -> str:
    base_host = detect_lan_ip() if host == "0.0.0.0" else host
    return f"http://{base_host}:{port}/"


def start_background_preview(*, include_drafts: bool = False, host: str = "0.0.0.0", port: int = 1313) -> str:
    command = build_background_serve_command(include_drafts=include_drafts)
    if host != "0.0.0.0":
        command.extend(["--host", host])
    if port != 1313:
        command.extend(["--port", str(port)])
    subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    url = preview_url(host=host, port=port)
    print(f"Preview restarted: {url}")
    return url
