from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from hugo_blog.pipeline.article_manifest import mark_article_normalized
from hugo_blog.pipeline.metadata import metadata_for_listing, normalize_reasons
from hugo_blog.pipeline.normalize import NormalizeReport, normalize_content
from hugo_blog.pipeline.validate import ValidationReport, validate_markdown_text


def normalize_article(
    *,
    content_dir: Path,
    static_images_dir: Path,
    rel_path: str,
    use_llm: bool = True,
) -> dict[str, Any]:
    target = (content_dir / rel_path).resolve()
    content_root = content_dir.resolve()
    if content_root not in target.parents and target != content_root:
        raise ValueError("path escapes content dir")
    if not target.exists() or target.suffix != ".md":
        raise FileNotFoundError(rel_path)

    normalized_rel_path = target.relative_to(content_dir).as_posix()
    if not normalized_rel_path.startswith("posts/"):
        raise ValueError("normalize only supports posts content")

    report = normalize_content(
        content_dir=content_dir,
        images_dir=static_images_dir,
        apply=True,
        article_filter=normalized_rel_path,
        auto_yes=True,
        skip_delete=True,
        normalize_metadata=True,
        use_llm=use_llm,
        apply_all=True,
    )
    text = target.read_text(encoding="utf-8")
    issues = validate_markdown_text(
        text,
        source_path=normalized_rel_path,
        static_images_dir=static_images_dir,
    )
    article_record = None
    if not issues and not normalize_reasons(text):
        article_record = mark_article_normalized(content_dir, normalized_rel_path)
    return {
        "path": normalized_rel_path,
        "page": metadata_for_listing(target, content_dir, article_record=article_record),
        "report": normalize_report_to_dict(report),
        "validation": ValidationReport(issues=issues).to_dict(),
    }


def normalize_report_to_dict(report: NormalizeReport) -> dict[str, Any]:
    return {
        "unused_images": report.unused_images,
        "image_renames": [asdict(plan) for plan in report.image_renames],
        "relref_migrations": report.relref_migrations,
        "broken_links": report.broken_links,
        "metadata_updates": report.metadata_updates,
        "summary_updates": report.summary_updates,
        "llm_requests": report.llm_requests,
        "llm_skips": report.llm_skips,
        "validation_issues": [asdict(issue) for issue in report.validation_issues],
    }
