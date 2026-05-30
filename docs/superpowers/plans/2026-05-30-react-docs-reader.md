# React Docs Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move preview-only developer docs into the React app on port 1314 with a Material-for-MkDocs-style reading experience and quick switching back to Admin.

**Architecture:** Keep Hugo preview on port 1313 for the rendered blog. Extend the Python admin server on port 1314 with docs JSON APIs, then add client-side Admin/Docs views in the existing Vite React app. Docs are read from repository `docs/` only and are not part of build/deploy output.

**Tech Stack:** Python `http.server`, existing Markdown files, Vite, React, TypeScript, CSS.

---

### Task 1: Backend Docs API

**Files:**
- Modify: `src/hugo_blog/preview/admin.py`
- Test: `tests/test_admin_server.py`

- [x] Add a failing test that `BlogAdminApp.list_docs()` returns a directory-style docs navigation tree.
- [x] Add a failing test that `BlogAdminApp.get_doc()` returns markdown content and headings.
- [x] Implement docs path validation, title extraction, heading extraction, list API, and get API.
- [x] Expose `GET /api/docs` and `GET /api/docs/<path>`.
- [x] Run targeted admin server tests.

### Task 2: React Docs View

**Files:**
- Modify: `src/hugo_blog/preview/admin_ui/src/App.tsx`
- Modify: `src/hugo_blog/preview/admin_ui/src/styles.css`

- [x] Add lightweight route selection from `window.location.pathname`.
- [x] Keep Admin view at `/admin/`.
- [x] Add Docs view at `/docs/` with top navigation, left doc tree, markdown body, right heading TOC, and docs search.
- [x] Keep Preview link targeting port 1313.
- [x] Add responsive layout for narrow screens.

### Task 3: Hugo Preview Cleanup

**Files:**
- Modify: `src/hugo_blog/pipeline/export.py`
- Test: `tests/test_tooling.py`

- [x] Stop copying `docs/` into Hugo preview content.
- [x] Keep `/admin/` available in Hugo preview as the bridge to the 1314 React app.
- [x] Update tests so preview export expects admin only, not Hugo docs pages.

### Task 4: Verification

**Files:**
- Generated: `src/hugo_blog/preview/admin_ui/dist/*`

- [x] Run Python unit tests.
- [x] Build the React admin UI.
- [x] Build Hugo output.
- [x] Restart preview/admin services.
- [x] Verify `http://127.0.0.1:1314/docs/` and docs APIs respond.
