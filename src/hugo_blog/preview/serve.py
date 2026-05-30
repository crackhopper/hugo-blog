#!/usr/bin/env python3
"""Start the Hugo preview server with Obsidian preprocessing enabled."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

from hugo_blog.paths import PROJECT_ROOT
from hugo_blog.pipeline.startup_sync import sync_content_manifests
from hugo_blog.pipeline.validate import format_report
from hugo_blog.static_site import static_site_manager
from hugo_blog.tools.hugo import default_hugo_path, install_hugo

PID_FILE = PROJECT_ROOT / ".hugo-preview.pid"


def detect_lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def build_hugo_command(
    *,
    hugo_bin: Path,
    host: str,
    port: int,
    base_url: str,
    include_drafts: bool,
) -> list[str]:
    command = [
        str(hugo_bin),
        "server",
    ]
    if include_drafts:
        command.append("-D")

    command.extend(
        [
            "--bind",
            host,
            "--baseURL",
            base_url,
            "--port",
            str(port),
            "--contentDir",
            ".hugo_temp_content",
            "--cleanDestinationDir",
        ]
    )
    return command


def start_watcher() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "hugo_blog.pipeline.watch"],
        cwd=PROJECT_ROOT,
        text=True,
    )


def start_admin(host: str, port: int) -> subprocess.Popen[str]:
    from hugo_blog.preview.admin import admin_ui_index_path
    from hugo_blog.preview.admin_ui_build import build_admin_ui

    if not admin_ui_index_path(PROJECT_ROOT).exists():
        build_admin_ui()
    return subprocess.Popen(
        [sys.executable, "-m", "hugo_blog.preview.admin", "--host", host, "--port", str(port)],
        cwd=PROJECT_ROOT,
        text=True,
    )


def issues_url(*, host: str, admin_port: int) -> str:
    display_host = detect_lan_ip() if host == "0.0.0.0" else host
    return f"http://{display_host}:{admin_port}/issues/"


def wait_for_admin_after_validation_failure(admin: subprocess.Popen[str] | None) -> int:
    if admin is None:
        return 1
    try:
        admin.wait()
    except KeyboardInterrupt:
        admin.terminate()
        try:
            admin.wait(timeout=5)
        except subprocess.TimeoutExpired:
            admin.kill()
    return 1


class OsProcess:
    def __init__(self, pid: int):
        self.pid = pid

    def poll(self):
        try:
            os.kill(self.pid, 0)
        except ProcessLookupError:
            return 0
        return None

    def terminate(self) -> None:
        try:
            os.kill(self.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def wait(self, timeout: int) -> None:
        import time

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.poll() is not None:
                return
            time.sleep(0.1)
        raise subprocess.TimeoutExpired(str(self.pid), timeout)

    def kill(self) -> None:
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _terminate_child_processes(pid: int) -> None:
    try:
        output = subprocess.check_output(["pgrep", "-P", str(pid)], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    for child in output.split():
        try:
            os.kill(int(child), signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            pass


def stop_previous_preview(
    *,
    pid_file: Path = PID_FILE,
    current_pid: int | None = None,
    process_factory=OsProcess,
) -> bool:
    if not pid_file.exists():
        return False
    try:
        old_pid = int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        pid_file.unlink(missing_ok=True)
        return False

    if current_pid is not None and old_pid == current_pid:
        return False

    process = process_factory(old_pid)
    if process.poll() is not None:
        pid_file.unlink(missing_ok=True)
        return False

    _terminate_child_processes(old_pid)
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if hasattr(process, "kill"):
            process.kill()
    pid_file.unlink(missing_ok=True)
    return True


def write_pid_file(pid_file: Path = PID_FILE) -> None:
    pid_file.write_text(str(os.getpid()), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Start a remote-accessible Hugo preview.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address.")
    parser.add_argument("--port", type=int, default=1313, help="Hugo server port.")
    parser.add_argument("--base-url", default=None, help="Preview base URL.")
    parser.add_argument("--drafts", action=argparse.BooleanOptionalAction, default=False, help="Include draft posts.")
    parser.add_argument("--no-watch", action="store_true", help="Do not watch content changes.")
    parser.add_argument("--admin", action=argparse.BooleanOptionalAction, default=True, help="Run the local admin page/API.")
    parser.add_argument("--admin-port", type=int, default=1314, help="Admin server port.")
    parser.add_argument("--install-tools", action="store_true", help="Install local Hugo if missing.")
    args = parser.parse_args()

    if stop_previous_preview(current_pid=os.getpid()):
        print("Stopped previous preview process.")
    write_pid_file()

    site = static_site_manager()
    hugo_bin = default_hugo_path(PROJECT_ROOT)
    if args.install_tools or not hugo_bin.exists():
        hugo_bin = install_hugo(project_root=PROJECT_ROOT)
    site.hugo_bin = hugo_bin

    base_host = detect_lan_ip() if args.host == "0.0.0.0" else args.host
    base_url = args.base_url
    if base_url is None:
        base_url = f"http://{base_host}:{args.port}/"

    admin = None
    if args.admin:
        admin = start_admin(args.host, args.admin_port)

    if not hugo_bin.exists():
        print("Hugo is missing. Run: python3 init.py", file=sys.stderr)
        return wait_for_admin_after_validation_failure(admin)

    if args.admin:
        print(f"Admin URL: http://{base_host}:{args.admin_port}/admin/")

    sync_content_manifests(PROJECT_ROOT / "content")

    source_report = site.validate_content()
    if not source_report.ok:
        print(format_report(source_report), file=sys.stderr)
        if args.admin:
            print(f"Issues URL: {issues_url(host=args.host, admin_port=args.admin_port)}", file=sys.stderr)
        return wait_for_admin_after_validation_failure(admin)

    site.preprocess_preview(force=True)

    exported_report = site.validate_content(content_dir=PROJECT_ROOT / ".hugo_temp_content")
    if not exported_report.ok:
        print(format_report(exported_report), file=sys.stderr)
        if args.admin:
            print(f"Issues URL: {issues_url(host=args.host, admin_port=args.admin_port)}", file=sys.stderr)
        return wait_for_admin_after_validation_failure(admin)

    command = build_hugo_command(
        hugo_bin=hugo_bin,
        host=args.host,
        port=args.port,
        base_url=base_url,
        include_drafts=args.drafts,
    )

    watcher = None
    if not args.no_watch:
        watcher = start_watcher()

    print(f"Preview URL: {base_url}")
    print("Hugo command:", " ".join(command))

    try:
        return subprocess.call(command, cwd=PROJECT_ROOT)
    finally:
        for process in (watcher, admin):
            if process is None:
                continue
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
