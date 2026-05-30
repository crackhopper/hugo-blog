# React Admin UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inline admin HTML with a locally built React admin UI that supports directory filtering, search, sorting, save/preview flow, and unified preview-site navigation.

**Architecture:** Keep Python as the API server on port 1314 and Hugo as the user-facing preview site on port 1313. React assets are built locally under `src/hugo_blog/preview/admin_ui/dist` and served by the Python admin server, while `/admin/` in Hugo embeds that app.

**Tech Stack:** Python 3.12 `http.server`, React, Vite, TypeScript, `unittest`.

---

### Task 1: Admin API Shape

**Files:**
- Modify: `src/hugo_blog/pipeline/metadata.py`
- Modify: `src/hugo_blog/preview/admin.py`
- Test: `tests/test_admin_server.py`

- [x] Add `modified`, `directory`, and `preview_url` fields to page listings.
- [x] Sort default page listings by modified time descending.
- [x] Keep `content/pending/` skipped.

### Task 2: Static Admin UI Serving

**Files:**
- Create: `src/hugo_blog/preview/admin_ui_build.py`
- Modify: `src/hugo_blog/preview/admin.py`
- Test: `tests/test_admin_server.py`

- [x] Serve built React files from `src/hugo_blog/preview/admin_ui/dist`.
- [x] Keep API paths under `/api/*`.
- [x] Fall back to a clear build-missing HTML message when dist is absent.

### Task 3: React App

**Files:**
- Create: `src/hugo_blog/preview/admin_ui/package.json`
- Create: `src/hugo_blog/preview/admin_ui/index.html`
- Create: `src/hugo_blog/preview/admin_ui/src/App.tsx`
- Create: `src/hugo_blog/preview/admin_ui/src/main.tsx`
- Create: `src/hugo_blog/preview/admin_ui/src/styles.css`

- [x] Implement filters for status, directory, and keyword search.
- [x] Implement sorting by modified/date/title/directory.
- [x] Implement row editing and dirty-state detection.
- [x] Implement Preview vs Save & Preview button behavior.
- [x] Implement draft preview restart control.

### Task 4: Unified Preview Navigation

**Files:**
- Modify: `src/hugo_blog/pipeline/export.py`

- [x] Keep `/docs/` and `/admin/` in the Hugo preview navigation.
- [x] Embed admin app at `/admin/` using the Python admin service on the same host and port 1314.

### Task 5: Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/python-tooling.md`

- [x] Document the React admin build behavior.
- [x] Run `uv run python -m unittest discover -s tests`.
- [x] Run admin UI build if Node/npm are available.
- [x] Run `uv run python scripts/build.py`.
