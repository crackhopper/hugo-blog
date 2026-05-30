# Obsidian Blog Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Obsidian sidebar plugin that manages Hugo blog drafts through the existing Python backend.

**Architecture:** Keep blog semantics in Python and expose plugin-friendly HTTP APIs. Extend the existing `hugo-link-updater` plugin with a custom `ItemView`, API client, backend launcher, and draft list UI.

**Tech Stack:** Python `unittest` and `http.server`; Obsidian TypeScript plugin API; esbuild; local `uv` environment.

---

### Task 1: Python Backend APIs

**Files:**
- Modify: `src/hugo_blog/preview/admin.py`
- Modify: `tests/test_admin_server.py`

- [ ] Add tests for `GET /api/health` and `POST /api/images/cleanup`.
- [ ] Implement health JSON with backend status, project root, content dir, Hugo availability, and issue counts.
- [ ] Implement image cleanup dry-run and confirmed delete API using existing image reference logic.
- [ ] Run `uv run python -m unittest tests.test_admin_server -v`.

### Task 2: Plugin API Client And State

**Files:**
- Modify: `tools/obsidian-hugo-link-updater/src/main.ts`
- Modify: `tools/obsidian-hugo-link-updater/package.json`

- [ ] Add settings for backend URL, auto-start, Python command, and serve command.
- [ ] Add a small API client for health, content list, normalize, and image cleanup.
- [ ] Add backend auto-start with Node child process for desktop use.
- [ ] Keep existing rename link updater behavior intact.

### Task 3: Obsidian Sidebar View

**Files:**
- Modify: `tools/obsidian-hugo-link-updater/src/main.ts`

- [ ] Register a custom Blog Workspace view.
- [ ] Add ribbon icon and commands to open the view, refresh, normalize current file, and cleanup images.
- [ ] Render tabs/filters for Drafts, Needs Normalize, Pending, and Image Issues.
- [ ] Open selected source markdown through Obsidian workspace APIs.

### Task 4: Build And Install Plugin

**Files:**
- Modify: `.obsidian/plugins/hugo-link-updater/main.js`
- Maybe modify: `.obsidian/plugins/hugo-link-updater/manifest.json`

- [ ] Run `npm --prefix tools/obsidian-hugo-link-updater install` if needed.
- [ ] Run `npm --prefix tools/obsidian-hugo-link-updater run build`.
- [ ] Copy built `main.js` and `manifest.json` into `.obsidian/plugins/hugo-link-updater/`.
- [ ] Run Python tests and inspect git status to ensure generated build outputs outside the plugin install are not accidentally committed.

### Task 5: Final Verification And Push

**Files:**
- All changed source, tests, docs, plugin install files.

- [ ] Run `uv run python -m unittest discover -s tests -v`.
- [ ] Run `npm --prefix tools/obsidian-hugo-link-updater run build`.
- [ ] Confirm ignored generated outputs such as `public/`, `.hugo_temp_content/`, `.venv/`, `.tools/`, and Admin UI dist are not staged.
- [ ] Commit and push to `origin/main`.
