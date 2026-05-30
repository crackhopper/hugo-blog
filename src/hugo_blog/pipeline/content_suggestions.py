from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from hugo_blog.llm.client import LLMClient, config_from_env
from hugo_blog.pipeline.metadata import parse_front_matter


MAX_DIRECTORY_DEPTH = 2
SAFE_SEGMENT_RE = re.compile(r"[^\w\u4e00-\u9fff.+-]+")


class JsonCompleter(Protocol):
    def complete_json(self, *, prompt: str, system: str = "只输出严格 JSON。", temperature: float = 0.2):
        ...


@dataclass(frozen=True)
class MoveSuggestion:
    target_path: str
    title: str
    reason: str


def suggest_article_moves(
    *,
    content_dir: Path,
    rel_path: str,
    llm_client: JsonCompleter | None = None,
    limit: int = 3,
) -> list[MoveSuggestion]:
    target = (content_dir / rel_path).resolve()
    content_root = content_dir.resolve()
    if content_root not in target.parents and target != content_root:
        raise ValueError("path escapes content dir")
    if not target.exists() or target.suffix != ".md":
        raise FileNotFoundError(rel_path)

    client = llm_client or LLMClient(config_from_env(Path.cwd()))
    text = target.read_text(encoding="utf-8")
    metadata, body, _ = parse_front_matter(text)
    title = str(metadata.get("title") or target.stem).strip()
    existing_dirs = _existing_post_dirs(content_dir)
    prompt = (
        "你是中文技术博客内容管理员。请根据文章标题、标签、正文片段，给出文章应该移动到 posts 下的目录和文件名建议。"
        "目录最多两级，例如 posts/图形学/Vulkan/标题.md。文件名使用中文标题，保留技术词，但不要包含路径分隔符。"
        "只输出 JSON：{\"suggestions\":[{\"target_path\":\"posts/分类/文件名.md\",\"title\":\"新标题\",\"reason\":\"简短原因\"}]}。"
        f"\n已有目录: {', '.join(existing_dirs) or '无'}"
        f"\n当前路径: {rel_path}"
        f"\n标题: {title}"
        f"\n标签: {metadata.get('tags') or []}"
        f"\n正文片段:\n{body[:5000]}"
    )
    payload = client.complete_json(prompt=prompt)
    raw_items = payload.get("suggestions", []) if isinstance(payload, dict) else []
    suggestions: list[MoveSuggestion] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        target_path = _sanitize_target_path(str(item.get("target_path") or ""), fallback_title=title)
        suggestions.append(
            MoveSuggestion(
                target_path=target_path,
                title=str(item.get("title") or Path(target_path).stem).strip(),
                reason=str(item.get("reason") or "").strip(),
            )
        )
        if len(suggestions) >= limit:
            break
    if not suggestions:
        suggestions.append(
            MoveSuggestion(
                target_path=_sanitize_target_path(f"posts/{target.name}", fallback_title=title),
                title=title,
                reason="LLM 未返回可用建议，保留在 posts 根目录。",
            )
        )
    return suggestions


def _existing_post_dirs(content_dir: Path) -> list[str]:
    posts = content_dir / "posts"
    if not posts.exists():
        return []
    dirs = []
    for path in posts.rglob("*"):
        if path.is_dir():
            rel = path.relative_to(content_dir).as_posix()
            if len(Path(rel).parts) <= MAX_DIRECTORY_DEPTH + 1:
                dirs.append(rel)
    return sorted(dirs)


def _sanitize_target_path(value: str, *, fallback_title: str) -> str:
    raw_parts = [part for part in value.replace("\\", "/").split("/") if part and part not in {".", ".."}]
    if raw_parts and raw_parts[0] == "content":
        raw_parts = raw_parts[1:]
    if raw_parts and raw_parts[0] == "pending":
        raw_parts = raw_parts[1:]
    if not raw_parts or raw_parts[0] != "posts":
        raw_parts.insert(0, "posts")
    file_name = raw_parts[-1]
    if not file_name.endswith(".md"):
        file_name = f"{file_name}.md"
    stem = Path(file_name).stem or fallback_title or "untitled"
    suffix = Path(file_name).suffix or ".md"
    file_name = f"{_safe_segment(stem)}{suffix}"
    dirs = [_safe_segment(part) for part in raw_parts[1:-1]][:MAX_DIRECTORY_DEPTH]
    return "/".join(["posts", *dirs, file_name])


def _safe_segment(value: str) -> str:
    segment = SAFE_SEGMENT_RE.sub("_", value.strip()).strip("._ ")
    segment = re.sub(r"_+", "_", segment)
    return segment or "untitled"
