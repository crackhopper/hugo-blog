from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from hugo_blog.llm.client import load_dotenv
from hugo_blog.paths import PROJECT_ROOT
from hugo_blog.cli.build import main as build_main


def run(command: list[str], cwd: Path) -> int:
    print("+", " ".join(command))
    return subprocess.call(command, cwd=cwd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish the Hugo site.")
    parser.add_argument("--force", action="store_true", help="Skip dirty-worktree warning.")
    parser.add_argument("--force-push", action="store_true", help="Push with --force.")
    args = parser.parse_args()

    env = {**load_dotenv(PROJECT_ROOT / ".env"), **os.environ}
    repo = env.get("DEPLOY_REPO", "")
    branch = env.get("DEPLOY_BRANCH", "master")
    deploy_dir = PROJECT_ROOT / env.get("DEPLOY_DIR", "repo_to_deploy")
    if not repo:
        raise SystemExit("DEPLOY_REPO is missing in .env")

    if not deploy_dir.exists():
        if run(["git", "clone", "--branch", branch, repo, str(deploy_dir)], PROJECT_ROOT) != 0:
            return 1

    for child in deploy_dir.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    build_code = subprocess.call(
        ["uv", "run", "blog-build", "--destination", str(deploy_dir)],
        cwd=PROJECT_ROOT,
    )
    if build_code != 0:
        return build_code

    if run(["git", "add", "-A"], deploy_dir) != 0:
        return 1
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=deploy_dir, text=True)
    if status.strip():
        if run(["git", "commit", "-m", "Deploy Hugo site"], deploy_dir) != 0:
            return 1
    push_command = ["git", "push", "origin", branch]
    if args.force_push:
        push_command.insert(2, "--force")
    return run(push_command, deploy_dir)


if __name__ == "__main__":
    raise SystemExit(main())
