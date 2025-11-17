#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量将 Markdown 图片语法 ![alt](path) 转换为 Obsidian/百科式语法 ![[path]]

默认遍历项目根目录下的 content 目录，可通过传参覆盖。脚本提供
dry-run、统计信息等辅助选项，方便先预览再写入。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

# 匹配标准 Markdown 图片语法：
#   ![alt text](/path/to/image.png "optional title")
IMAGE_PATTERN = re.compile(
    r"""
    !\[
        (?P<alt>[^\]]*)
    \]
    \(
        (?P<path>[^)\s]+)            # 图片路径
        (?:\s+"(?P<title>[^"]*)")?   # 可选标题
    \)
    """,
    re.VERBOSE,
)


def find_markdown_files(content_dir: Path) -> Iterable[Path]:
    """递归列出 content_dir 下的所有 Markdown 文件。"""
    return content_dir.rglob("*.md")


def convert_image_syntax(markdown: str) -> tuple[str, int]:
    """将字符串中的 Markdown 图片语法转换为 wiki 链接，返回新内容和替换次数。"""

    def _replace(match: re.Match[str]) -> str:
        path = match.group("path").strip()
        # 统一去除包裹在 <> 中的路径（Markdown 允许这种写法）
        if path.startswith("<") and path.endswith(">"):
            path = path[1:-1].strip()
        # 去掉 /images/ 前缀，转换为相对 static/images 的路径
        if path.startswith("/images/"):
            path = path[len("/images/") :]
        return f"![[{path}]]"

    return IMAGE_PATTERN.subn(_replace, markdown)


def process_file(
    file_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """处理单个 Markdown 文件，返回替换次数。"""
    content = file_path.read_text(encoding="utf-8")
    new_content, replacements = convert_image_syntax(content)

    if replacements and not dry_run:
        file_path.write_text(new_content, encoding="utf-8")

    if verbose and replacements:
        action = "模拟" if dry_run else "修改"
        print(f"{action}: {file_path} ({replacements} 处替换)")

    return replacements


def main() -> None:
    parser = argparse.ArgumentParser(
        description="将 Markdown 图片语法转换为 wiki 链接（![[path]]）"
    )
    parser.add_argument(
        "--content-dir",
        default="content",
        help="Markdown 内容目录（默认：content）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计替换次数，不写回文件",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="静默模式，仅输出最终统计",
    )
    args = parser.parse_args()

    content_dir = Path(args.content_dir)
    if not content_dir.exists():
        raise SystemExit(f"目录不存在: {content_dir}")

    total_files = 0
    total_replacements = 0

    for md_file in find_markdown_files(content_dir):
        total_files += 1
        total_replacements += process_file(
            md_file, dry_run=args.dry_run, verbose=not args.quiet
        )

    summary = (
        "（dry-run）" if args.dry_run else ""
    )
    print(
        f"完成{summary}：扫描 {total_files} 个文件，替换 {total_replacements} 处图片语法。"
    )


if __name__ == "__main__":
    main()

