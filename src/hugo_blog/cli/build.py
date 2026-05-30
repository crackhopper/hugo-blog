from __future__ import annotations

import argparse
from pathlib import Path

from hugo_blog.pipeline.validate import format_report
from hugo_blog.static_site import static_site_manager


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Obsidian content and build Hugo site.")
    parser.add_argument("--destination", default=None, help="Hugo destination directory.")
    parser.add_argument("--drafts", action="store_true", help="Include draft content.")
    parser.add_argument("--no-minify", action="store_true", help="Disable Hugo minify.")
    parser.add_argument("--no-preprocess", action="store_true", help="Use content/ directly.")
    args = parser.parse_args()

    site = static_site_manager()
    content_dir = "content"
    source_report = site.validate_content(content_dir=Path(content_dir))
    if not source_report.ok:
        print(format_report(source_report))
        return 1

    if not args.no_preprocess:
        site.preprocess_build(force=True)
        content_dir = ".hugo_temp_content"
        exported_report = site.validate_content(content_dir=Path(content_dir))
        if not exported_report.ok:
            print(format_report(exported_report))
            return 1

    return site.run_build(
        content_dir=content_dir,
        include_drafts=args.drafts,
        minify=not args.no_minify,
        destination=args.destination,
    )


if __name__ == "__main__":
    raise SystemExit(main())
