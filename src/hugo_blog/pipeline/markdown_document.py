from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml
from markdown_it import MarkdownIt


FRONT_MATTER_RE = re.compile(r"\A\ufeff?---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
MORE_RE = re.compile(r"<!--\s*more\s*-->", re.IGNORECASE)


@dataclass(frozen=True)
class MarkdownDocument:
    text: str
    body: str
    front_matter: dict[str, Any]
    has_front_matter: bool
    summary: str
    first_heading_line: int | None


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str, bool, int]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text, False, 0

    raw = match.group(1).strip()
    metadata = yaml.safe_load(raw) if raw else {}
    if not isinstance(metadata, dict):
        metadata = {}
    line_offset = text[: match.end()].count("\n")
    return metadata, text[match.end() :], True, line_offset


def _first_heading_line(body: str) -> int | None:
    parser = MarkdownIt("commonmark")
    for token in parser.parse(body):
        if token.type == "heading_open" and token.map:
            return token.map[0] + 1
    return None


def _extract_summary(body: str) -> str:
    match = MORE_RE.search(body)
    if not match:
        return ""
    return body[: match.start()].strip()


def parse_markdown_document(text: str) -> MarkdownDocument:
    front_matter, body, has_front_matter, line_offset = _parse_front_matter(text)
    first_heading_line = _first_heading_line(body)
    if first_heading_line is not None:
        first_heading_line += line_offset
    return MarkdownDocument(
        text=text,
        body=body,
        front_matter=front_matter,
        has_front_matter=has_front_matter,
        summary=_extract_summary(body),
        first_heading_line=first_heading_line,
    )
