from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEEPSEEK_BASE_URL = "https://api.deepseek.com"


@dataclass(frozen=True)
class LLMMetadata:
    abstract: str = ""
    tags: list[str] | None = None

    def normalized_tags(self) -> list[str]:
        return [tag.strip() for tag in (self.tags or []) if tag and tag.strip()]


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        values[key] = value
    return values


def config_from_env(project_root: Path) -> LLMConfig:
    dotenv = load_dotenv(project_root / ".env")
    merged = {**dotenv, **os.environ}
    provider = merged.get("LLM_PROVIDER", "deepseek")
    base_url = merged.get("LLM_BASE_URL") or (DEEPSEEK_BASE_URL if provider == "deepseek" else "")
    return LLMConfig(
        provider=provider,
        api_key=merged.get("LLM_API_KEY", ""),
        base_url=base_url.rstrip("/"),
        model=merged.get("LLM_MODEL", ""),
    )


def parse_llm_metadata(raw: str) -> LLMMetadata:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    data = json.loads(text)
    abstract = str(data.get("abstract", "")).strip()
    tags_value = data.get("tags", [])
    if not isinstance(tags_value, list):
        tags_value = []
    tags = [str(tag).strip() for tag in tags_value if str(tag).strip()]
    return LLMMetadata(abstract=abstract, tags=tags)


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    def generate_metadata(self, *, title: str, body: str, need_abstract: bool, need_tags: bool) -> LLMMetadata:
        if not self.config.available:
            return LLMMetadata()

        prompt = (
            "你是中文技术博客编辑。请根据文章内容生成缺失的元数据。"
            "只输出 JSON，不要解释。格式："
            '{"abstract": "80到140字中文摘要", "tags": ["标签1", "标签2"]}。'
            f"需要摘要: {need_abstract}; 需要标签: {need_tags}。\n"
            f"标题: {title}\n\n正文:\n{body[:8000]}"
        )
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "只输出严格 JSON。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return LLMMetadata()

        content = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        try:
            metadata = parse_llm_metadata(content)
        except (json.JSONDecodeError, TypeError, ValueError):
            return LLMMetadata()

        return LLMMetadata(
            abstract=metadata.abstract if need_abstract else "",
            tags=metadata.normalized_tags() if need_tags else [],
        )

    def complete_json(self, *, prompt: str, system: str = "只输出严格 JSON。", temperature: float = 0.2) -> Any:
        if not self.config.available:
            raise RuntimeError("LLM config is required")
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        content = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return parse_json_content(content)


def parse_json_content(raw: str) -> Any:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)
