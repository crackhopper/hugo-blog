# Normalize Preview Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make normalization reviewable in date order, restart preview when requested, keep drafts/docs preview-only, and keep build/deploy clean.

**Architecture:** Add focused helpers for Markdown ordering and preview background startup. Keep normalize as the coordinator and export as the only writer of `.hugo_temp_content/`.

**Tech Stack:** Python 3.12, `markdown-it-py`, Hugo CLI, `unittest`.

---

### Task 1: Ordered Markdown Processing

**Files:**
- Modify: `src/hugo_blog/pipeline/normalize.py`
- Test: `tests/test_metadata_normalizer.py`

- [x] Add tests showing files without front matter sort first by mtime descending, then files with front matter sort by `date` descending.
- [x] Implement `ordered_markdown_files(content_dir, article_filter=None)`.
- [x] Use ordered files for normalize processing and metadata candidate prompts.

### Task 2: Review Each Mode

**Files:**
- Modify: `src/hugo_blog/pipeline/normalize.py`
- Test: `tests/test_metadata_normalizer.py`

- [x] Add `--review-each`.
- [x] In review mode, ask before each metadata candidate.
- [x] After each written file, call an injected preview restart callback.
- [x] Keep `--dry-run` write-free and preview-free.

### Task 3: Background Preview Launcher

**Files:**
- Create: `src/hugo_blog/preview/launcher.py`
- Modify: `src/hugo_blog/preview/serve.py`
- Test: `tests/test_tooling.py`

- [x] Add a helper that starts `scripts/serve.py` in the background and prints the LAN preview URL.
- [x] Reuse existing PID behavior so each start stops the previous preview.
- [x] Keep `serve.py --drafts` default true and `--no-drafts` available.

### Task 4: Preview-only Docs

**Files:**
- Modify: `src/hugo_blog/pipeline/export.py`
- Modify: `src/hugo_blog/preview/serve.py`
- Test: `tests/test_tooling.py`

- [x] Add `include_docs=False` to `preprocess_content_dir`.
- [x] When `include_docs=True`, copy `docs/*.md` into `.hugo_temp_content/docs/` with generated front matter and an index page.
- [x] Call preview export with `include_docs=True`; keep build/deploy default false.

### Task 5: Docs and Verification

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/content-pipeline.md`

- [x] Document `--review-each`, `--apply-all`, draft preview toggle, and preview-only docs.
- [x] Run `uv run python -m unittest discover -s tests`.
- [x] Run `uv run python scripts/normalize.py --dry-run`.
- [x] Run `uv run python scripts/build.py`.
