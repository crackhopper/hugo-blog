---
name: normalize-blog-content
description: >-
  Normalizes Hugo blog content: removes unused images, renames images to
  article-section-index format, migrates relref to Obsidian wiki links, and
  interactively fixes broken links. Use when the user asks to normalize content,
  clean images, rename images, fix links, or run normalize_content.py.
---

# Normalize Blog Content

Follow [AGENTS.md](../../AGENTS.md) conventions. Default to **dry-run** before writing.

## Quick Start

```bash
# 1. Preview all changes
python scripts/normalize_content.py

# 2. Apply image cleanup, rename, relref migration
python scripts/normalize_content.py --apply --yes

# 3. Fix broken wiki links (interactive)
python scripts/normalize_content.py --apply --fix-links

# 4. Single article only
python scripts/normalize_content.py --apply --article "RT-04-材质和BRDF"
```

## Workflow Checklist

```
Task Progress:
- [ ] Run dry-run and summarize report
- [ ] Confirm with user before --apply
- [ ] Apply changes (--apply)
- [ ] Fix broken links if any (--fix-links)
- [ ] Verify: python scripts/preprocess_obsidian.py --force && hugo --contentDir .hugo_temp_content
```

## Phase Guide

| Phase | Flag | Action |
|-------|------|--------|
| Scan | (default) | Report unused images, planned renames, relref count |
| Delete unused | `--apply` | Remove unreferenced files in static/images/ |
| Rename images | `--apply` | `{stem}-{section}-{NN}.ext` |
| Migrate relref | `--apply` | `{{< relref "..." >}}` → `[[...]]` |
| Fix broken | `--apply --fix-links` | Interactive candidate selection |

## Skip Options

- `--skip-delete` — do not remove unused images
- `--skip-rename` — do not rename images
- `--skip-relref` — do not migrate relref links
- `-y` / `--yes` — auto-confirm deletion prompts

## Rules for Agents

1. **Never** `--apply` without showing dry-run summary first
2. Broken links: present candidates; let user choose in `--fix-links` mode
3. Source files use Obsidian syntax only; do not write relref or `/images/` paths
4. Do not use deprecated `scripts/fix_obsidian_images.py`

## Image Naming

```
{article-stem}-{heading-slug}-{01}.{ext}
```

- No heading above image → section slug is `intro`
- Preserve `|width` / `|WxH` suffix when renaming embeds

## Verification

After normalize:

```bash
python scripts/preprocess_obsidian.py --force
hugo --contentDir .hugo_temp_content
```

Check stderr for unresolved wiki links or missing images.
