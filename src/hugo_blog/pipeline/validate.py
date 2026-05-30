from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from hugo_blog.pipeline.content_filters import iter_content_markdown_files, iter_processable_markdown_files
from hugo_blog.pipeline.image_manifest import ImageManifest
from hugo_blog.pipeline.wikilinks import IMAGE_EXTENSIONS, MARKDOWN_IMAGE_PATTERN, parse_wiki_link_inner

WIKI_IMAGE_RE = re.compile(r"!\[\[([^\]]+)\]\]")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)


@dataclass
class ValidationIssue:
    severity: str
    kind: str
    source_path: str
    line: int
    raw_reference: str
    target: str
    message: str
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "issues": [issue.to_dict() for issue in self.issues]}


def validate_content_tree(
    *,
    content_dir: Path,
    static_images_dir: Path,
    processable_only: bool = False,
) -> ValidationReport:
    files = iter_processable_markdown_files(content_dir) if processable_only else iter_content_markdown_files(content_dir)
    image_names = _image_names(static_images_dir)
    image_manifest = ImageManifest.load(static_images_dir)
    issues: list[ValidationIssue] = []
    for path in files:
        issues.extend(
            validate_markdown_file(
                path,
                content_dir=content_dir,
                static_images_dir=static_images_dir,
                image_names=image_names,
                image_manifest=image_manifest,
            )
        )
    return ValidationReport(issues=issues)


def validate_markdown_file(
    path: Path,
    *,
    content_dir: Path,
    static_images_dir: Path,
    image_names: set[str] | None = None,
    image_manifest: ImageManifest | None = None,
) -> list[ValidationIssue]:
    text = path.read_text(encoding="utf-8")
    names = image_names if image_names is not None else _image_names(static_images_dir)
    rel_path = path.relative_to(content_dir).as_posix()
    return validate_markdown_text(
        text,
        source_path=rel_path,
        static_images_dir=static_images_dir,
        image_names=names,
        image_manifest=image_manifest,
        article_stem=path.stem,
    )


def validate_markdown_text(
    text: str,
    *,
    source_path: str,
    static_images_dir: Path,
    image_names: set[str] | None = None,
    image_manifest: ImageManifest | None = None,
    article_stem: str | None = None,
) -> list[ValidationIssue]:
    names = image_names if image_names is not None else _image_names(static_images_dir)
    manifest = image_manifest if image_manifest is not None else ImageManifest.load(static_images_dir)
    stem = article_stem or Path(source_path).stem
    issues: list[ValidationIssue] = []
    for raw, target, line in iter_image_references(text):
        normalized = normalize_image_target(target)
        if normalized is None:
            continue
        manifest_target = manifest.get(normalized)
        if manifest_target:
            if manifest_target in names:
                continue
            issues.append(
                ValidationIssue(
                    severity="error",
                    kind="missing_image",
                    source_path=source_path,
                    line=line,
                    raw_reference=raw,
                    target=manifest_target,
                    message=f"图片文件不存在: static/images/{manifest_target}",
                    candidates=suggest_image_candidates(manifest_target, names, article_stem=stem),
                )
            )
            continue

        if normalized in names:
            if "/" not in normalized:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        kind="needs_image_normalization",
                        source_path=source_path,
                        line=line,
                        raw_reference=raw,
                        target=normalized,
                        message=f"图片未登记到 manifest，需要归一化: static/images/{normalized}",
                        candidates=[normalized],
                    )
                )
            continue

        if normalized not in names:
            issues.append(
                ValidationIssue(
                    severity="error",
                    kind="missing_image",
                    source_path=source_path,
                    line=line,
                    raw_reference=raw,
                    target=normalized,
                    message=f"图片文件不存在: static/images/{normalized}",
                    candidates=suggest_image_candidates(normalized, names, article_stem=stem),
                )
            )
    return issues


def iter_image_references(text: str) -> Iterable[tuple[str, str, int]]:
    for match in WIKI_IMAGE_RE.finditer(text):
        target, _, _ = parse_wiki_link_inner(match.group(1))
        yield target, target, _line_number(text, match.start())
    for match in MARKDOWN_IMAGE_PATTERN.finditer(text):
        raw = match.group("path").strip()
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1].strip()
        yield raw, raw, _line_number(text, match.start())
    for match in HTML_IMAGE_RE.finditer(text):
        raw = html.unescape(match.group(1).strip())
        yield raw, raw, _line_number(text, match.start())


def normalize_image_target(target: str) -> str | None:
    parsed = urlparse(target)
    if parsed.scheme in {"http", "https", "data", "mailto"} or target.startswith("//"):
        return None

    path = unquote(parsed.path or target).lstrip()
    if path.startswith("/images/"):
        path = path[len("/images/") :]
    elif path.startswith("images/"):
        path = path[len("images/") :]
    path = path.lstrip("/")

    if Path(path).suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    return path


def suggest_image_candidates(target: str, names: set[str], *, article_stem: str, limit: int = 5) -> list[str]:
    target_name = Path(target).name
    target_ext = Path(target).suffix.lower()
    scored: list[tuple[float, str]] = []
    for name in names:
        score = SequenceMatcher(None, target_name.lower(), Path(name).name.lower()).ratio()
        if article_stem and Path(name).name.startswith(article_stem):
            score += 0.25
        if target_ext and Path(name).suffix.lower() == target_ext:
            score += 0.05
        if score >= 0.45:
            scored.append((score, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _, name in scored[:limit]]


def format_report(report: ValidationReport, *, limit: int = 20) -> str:
    if report.ok:
        return "内容校验通过"
    errors = [issue for issue in report.issues if issue.severity == "error"]
    warnings = [issue for issue in report.issues if issue.severity != "error"]
    lines = [f"内容校验失败: {len(errors)} 个错误，{len(warnings)} 个 warning"]
    ordered = errors + warnings
    for issue in ordered[:limit]:
        lines.append(f"- {issue.source_path}:{issue.line} {issue.message} ({issue.raw_reference})")
        if issue.candidates:
            lines.append(f"  候选: {', '.join(issue.candidates[:3])}")
    if len(ordered) > limit:
        lines.append(f"... 以及另外 {len(ordered) - limit} 个问题")
    return "\n".join(lines)


def _image_names(static_images_dir: Path) -> set[str]:
    if not static_images_dir.exists():
        return set()
    return {
        path.relative_to(static_images_dir).as_posix()
        for path in static_images_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1
