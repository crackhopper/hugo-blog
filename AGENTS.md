# AGENTS.md — Hugo 博客项目指南

本文档面向 AI Agent 与作者，说明本仓库的内容规范、构建流程与工具链。

## 项目概览

- **编辑器**：Obsidian（vault 根目录即仓库根）
- **发布器**：Hugo + [Stack](https://stack.jimmycai.com/) 主题
- **语言**：中文技术博客（C++、图形学、游戏、数学等）

源文件使用 **Obsidian wiki 语法**；构建时由 `scripts/preprocess_obsidian.py` 转换为 Hugo 可识别的 Markdown，**不修改** `content/` 原文。

## 目录结构

```
hugo-blog/
├── content/              # Hugo 内容（Obsidian 笔记）
│   ├── posts/            # 博客文章（可分子目录分类）
│   ├── projects/         # 项目页
│   └── page/             # 独立页面（about、archives 等）
├── static/images/        # 图片附件（Obsidian attachmentFolderPath）
├── templates/            # Obsidian 文章模板
├── scripts/              # 预处理、规范化、构建脚本
├── themes/Stack/         # Hugo 主题（git submodule）
├── .hugo_temp_content/   # 预处理输出（勿手改、勿提交）
└── public/               # Hugo 构建输出（勿提交）
```

## Front Matter

每篇文章开头使用 YAML front matter，可参考 [`templates/new.md`](templates/new.md)：

```yaml
---
title: 文章标题
date: 2024-01-01T10:00:00+08:00
tags:
  - 标签1
draft: false
---
```

- `draft: true` 为草稿；本地预览可用 `hugo server -D`
- 数学公式默认启用（见 `config.toml` 中 `[params.article] math = true`）

## 图片引用（源文件写法）

**统一使用 Obsidian embed 语法**，图片存放在 `static/images/`：

```markdown
![[RT-04-材质和BRDF-回顾brdf定义-01.png]]
![[RT-04-材质和BRDF-回顾brdf定义-02.png|464]]
![[RT-04-材质和BRDF-lambertian-漫反射-01.png|546x370]]
```

### 命名规范

```
{文章stem}-{段落slug}-{两位序号}.{ext}
```

| 部分 | 说明 | 示例 |
|------|------|------|
| 文章 stem | markdown 文件名去掉 `.md` | `RT-04-材质和BRDF` |
| 段落 slug | 图片上方最近 heading 的 slug | `回顾brdf定义` |
| 序号 | 同一段落下从 `01` 递增 | `01`, `02` |
| 无 heading | 使用 `intro` | `RT-04-材质和BRDF-intro-01.png` |

**不要在源文件写** `![](/images/...)` 或 HTML `<img>`；历史内容用 `python scripts/normalize_content.py` 迁移。

### 编译时转换

`preprocess_obsidian.py` 在构建前将 wiki 图片转为 Hugo 格式：

- `![[file.png]]` → `![alt](/images/file.png)`
- `![[file.png|width]]` → `<img src="/images/file.png" width="..." />`

## 文章间引用（源文件写法）

**统一使用 Obsidian wiki 链接**，不要在源文件写 `{{< relref ... >}}`：

```markdown
[[深入思考曲面积分]]
[[posts/数学/深入思考曲面积分]]
[[深入思考曲面积分#换元剪切技巧]]
[[RT-02-光传播理论(渲染方程)|渲染方程]]
```

| 形式 | 含义 |
|------|------|
| `[[标题或文件名]]` | 按索引匹配唯一文章 |
| `[[posts/路径/文件名]]` | 显式路径（推荐歧义时使用） |
| `[[文章#heading]]` | 带锚点 |
| `[[文章\|显示文字]]` | 带别名 |
| `[[#heading]]` | 文内标题链接（同页锚点） |

### 编译时转换

构建时 wiki 链接解析为 Hugo `relref`：

```markdown
[[posts/数学/深入思考曲面积分#换元剪切技巧|曲面积分]]
→ [曲面积分]({{< relref "posts/数学/深入思考曲面积分.md" >}}#换元剪切技巧)
```

索引键：相对路径、stem、front matter `title`（含大小写不敏感）；唯一模糊匹配时自动解析，歧义则 warn 并保留原样。

## 工作流命令

| 场景 | 命令 |
|------|------|
| 本地写作（推荐） | `.\scripts\start-writing.ps1` |
| 构建站点 | `.\scripts\build.ps1` |
| 规范化内容 | `python scripts/normalize_content.py` |
| 规范化并写入 | `python scripts/normalize_content.py --apply` |
| 修复 broken 链接 | `python scripts/normalize_content.py --apply --fix-links` |
| 单篇文章 | `python scripts/normalize_content.py --apply --article "RT-04-材质和BRDF"` |
| 部署 | `.\scripts\deploy.ps1` |

### 构建流水线

```
content/*.md  →  preprocess_obsidian.py  →  .hugo_temp_content/  →  hugo  →  public/
static/images/ ────────────────────────────────────────────────────────────────→ public/images/
```

## 内容规范化（normalize）

`scripts/normalize_content.py` 分阶段执行：

1. **扫描**：收集所有图片引用，构建 wiki 索引
2. **清理**：删除 `static/images/` 中未被引用的图片（默认 dry-run，需 `--apply` 并确认）
3. **重命名**：按 `{文章}-{段落}-{序号}` 规范重命名图片并更新引用
4. **迁移**：将遗留 `relref` 链接转为 `[[wiki]]` 语法
5. **修复**：`--fix-links` 交互式修复无法解析的 wiki 链接

默认 **dry-run**，必须加 `--apply` 才会写盘。Agent 应先 dry-run 展示摘要，经用户确认后再 `--apply`。

## Obsidian 配置

- 附件目录：`.obsidian/app.json` → `attachmentFolderPath: static/images`
- 重命名联动：启用社区插件 **hugo-link-updater**（更新 wiki 链接与 relref 短代码）
- 模板：Templater 插入 [`templates/new.md`](templates/new.md)

### 更新 hugo-link-updater 插件

```bash
cd tools/obsidian-hugo-link-updater
npm install && npm run build
copy main.js ..\..\.obsidian\plugins\hugo-link-updater\main.js
```

## Agent 操作约束

1. 编辑 `content/` 时使用 Obsidian wiki 语法，**不要**直接修改 `.hugo_temp_content/` 或 `public/`
2. 新增/移动图片后，确保引用与 `static/images/` 文件名一致
3. 批量整理内容前先 `python scripts/normalize_content.py`（dry-run），确认后再 `--apply`
4. broken wiki 链接必须经用户确认后再 `--fix-links` 写入
5. 不要提交 `public/`、`.hugo_temp_content/`、`.env`
6. 遗留脚本 `scripts/fix_obsidian_images.py` 已 **deprecated**（会原地改源文件）；请用 `normalize_content.py` 替代

## 相关文件

| 文件 | 用途 |
|------|------|
| [`scripts/lib/obsidian_links.py`](scripts/lib/obsidian_links.py) | wiki 索引、链接转换共享库 |
| [`scripts/preprocess_obsidian.py`](scripts/preprocess_obsidian.py) | 构建前预处理 |
| [`scripts/normalize_content.py`](scripts/normalize_content.py) | 内容规范化 CLI |
| [`.cursor/skills/normalize-blog-content/SKILL.md`](.cursor/skills/normalize-blog-content/SKILL.md) | Cursor Agent 规范化 skill |
| [`config.toml`](config.toml) | Hugo 配置 |
