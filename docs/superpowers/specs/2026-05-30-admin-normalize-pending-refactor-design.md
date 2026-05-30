# Admin Normalize、Pending 与文章重构设计

## 背景

当前 Admin 已能编辑 `content/posts` 下文章的 front matter 和正文，也能查看内容校验问题。后续管理工作需要从命令行迁移到 Admin：单篇/批量 normalize、pending 管理、LLM 目录建议、以及涉及文章改名和移动的安全重构。

核心原则：任何会改变 Markdown 文件路径、目录或文件名的操作，都必须走统一的 Python 重构模块，避免 UI、脚本和 LLM 建议各自直接移动文件导致引用、manifest 或 preview 状态不一致。

## 内容范围

Admin 的文章管理范围为：

- 包含：`content/**/*.md`
- 排除：`content/pending/**/*.md`

Pending 管理范围为：

- 仅包含：`content/pending/**/*.md`

链接索引与 manifest 范围为：

- 扫描 `content/**/*.md`
- 排除 `content/pending/**/*.md`
- 支持递归路径、front matter `title`、文件 stem 和相对路径作为索引键

文章实体 manifest 范围为：

- 扫描 `content/**/*.md`
- 包含 pending，用于识别文章被移动到 pending 或从 pending 恢复
- 记录稳定文章 ID、当前路径、历史路径、标题、内容指纹、引用关系和状态

## Admin 列表

默认列表展示常规内容，即 `content/**/*.md` 且排除 pending。列表能力：

- 行级 `Normalize` 按钮
- 行级 `Move to pending` 按钮
- 行级 `Rename / Move` 操作入口
- 多选复选框
- `Normalize selected`
- `Move selected to pending`
- 筛选：
  - 常规内容
  - Pending 内容
  - Draft / Published
  - normalized / not normalized
- 排序：
  - Title
  - Date
  - Modified
  - 正序 / 倒序

默认排序保持 `Modified desc`。

## Normalize 行为

Admin normalize 只执行安全操作：

- 图片归一化到 manifest 管理路径
- Markdown 链接 manifest 更新
- Obsidian 链接简化
- relref 迁移
- front matter / tags / 摘要修复

Admin normalize 不删除未引用图片。需要 LLM 但配置不可用时，API 返回 fatal error，前端直接显示错误。

Normalize API：

- `POST /api/content/normalize`
  - 入参：`{ "path": "posts/xxx.md" }`
- `POST /api/content/normalize-batch`
  - 入参：`{ "paths": ["posts/a.md", "projects/b.md"] }`

返回内容包含每篇文章的 normalize 结果、validation、warnings 和 errors。

## Pending 工作流

常规文章移动到 pending 时保留原始相对路径：

```text
content/posts/数学/foo.md
-> content/pending/posts/数学/foo.md
```

Pending 恢复时不自动决定目标。用户点击 `Restore...` 后，后端调用 LLM 分析文章，返回 3-5 个候选目标路径。UI 显示候选卡片，用户点击确认后才执行移动。

候选格式：

```json
{
  "target_path": "posts/数学/几何/四元数原理.md",
  "reason": "文章主题属于数学/几何，标题明确",
  "confidence": 0.86
}
```

UI 同时提供手动输入目标路径作为兜底。目标路径允许使用 `content` 下已有结构，并允许多一个层级的子目录。

## 建议操作页面

新增 Admin 页面：`Suggestions`。

用途：

- 扫描常规内容和 pending 内容
- 调用 LLM 分析文章结构和主题
- 生成可确认的操作建议

建议类型：

- `Normalize`
- `Move`
- `Rename`
- `Move to pending`
- `Restore from pending`
- `Skip`

每条建议都需要用户确认。LLM 不直接移动文件。

## 统一文章重构模块

新增模块：`src/hugo_blog/pipeline/content_refactor.py`。

所有涉及 Markdown 文件路径变化的操作都必须调用该模块，包括：

- `Move to pending`
- `Restore from pending`
- LLM 建议移动
- 手动移动目录
- 手动重命名文件
- Admin 里修改文章标题后触发的文件名重命名

UI 和其他脚本不得直接调用 `Path.rename()` 移动文章。

## 文章实体 Manifest 与 ID

新增模块：`src/hugo_blog/pipeline/article_manifest.py`。

Manifest 文件：`content/articles.json`。

目的：

- 记录所有 Markdown 文章的稳定身份
- 识别 Obsidian 或外部工具造成的移动、重命名、删除、新增
- 将文章 ID 与文章链接 manifest、图片 manifest、引用关系关联起来
- 启动 `python scripts/serve.py` 时自动 reconcile 当前文件系统和 manifest

### Front Matter ID

每篇文章增加稳定 `id` 字段：

```yaml
---
id: art_01hx7w8p9k3v2m6n4q5r
title: 文章标题
date: 2026-05-30T10:00:00+08:00
draft: false
tags:
  - 标签
---
```

`id` 不是 description，不参与摘要展示。它是内部稳定标识。因为 Obsidian 移动或重命名文件时会保留 front matter，所以 `id` 是识别移动/重命名最可靠的信号。

### ID 生成算法

新文章或旧文章没有 `id` 时：

1. 读取正文，移除 front matter。
2. 规范化内容：
   - 统一换行
   - 去除首尾空白
   - 连续空白折叠
   - 不把文件路径纳入指纹
3. 生成 `body_fingerprint = blake2b(normalized_body, digest_size=16)`。
4. 如果旧 `articles.json` 中存在相同或高度相似的 fingerprint，则沿用旧 ID。
5. 如果无法匹配，生成新 ID：`art_` + 128 bit 随机 token 的 base32/hex 表示。
6. 将 ID 写回 front matter，并写入 `content/articles.json`。

ID 一旦写入，不因标题、路径或正文变更而变化。

### Manifest 结构

```json
{
  "version": 1,
  "articles": {
    "art_01hx7w8p9k3v2m6n4q5r": {
      "path": "posts/数学/四元数原理.md",
      "status": "active",
      "title": "四元数原理",
      "draft": true,
      "fingerprint": "b2:...",
      "previous_paths": [
        "posts/old/四元数.md"
      ],
      "aliases": [
        "四元数原理",
        "四元数"
      ],
      "outgoing_links": [
        "art_xxx"
      ],
      "incoming_links": [
        "art_yyy"
      ],
      "image_keys": [
        "四元数原理-intro-01.png"
      ],
      "last_seen": "2026-05-30T19:00:00+08:00"
    }
  },
  "path_index": {
    "posts/数学/四元数原理.md": "art_01hx7w8p9k3v2m6n4q5r"
  },
  "title_index": {
    "四元数原理": "art_01hx7w8p9k3v2m6n4q5r"
  }
}
```

### 启动 Reconcile

`python scripts/serve.py` 启动前执行：

1. 扫描 `content/**/*.md`。
2. 读取每篇文章 front matter `id`。
3. 对无 ID 文章计算 fingerprint。
4. 与旧 `content/articles.json` 对比：
   - 同 ID 不同路径：识别为移动或重命名。
   - 无 ID 但 fingerprint 匹配：识别为旧文章移动或 front matter ID 丢失。
   - 旧 manifest 有记录但当前不存在：标记为 `missing` 或 `deleted`。
   - 当前存在但 manifest 无记录：标记为 `new` 并分配 ID。
5. 对移动/重命名文章更新引用。
6. 重建 `content/links.json`。
7. 更新图片 manifest 中与文章 ID 相关的信息。
8. 运行必要的 normalize。
9. 预处理 preview。

### 外部删除

如果外部删除了一篇文章：

- manifest 将该 ID 标记为 `missing`。
- 其他文章指向它的链接不会被静默删除。
- Admin Issues / Suggestions 显示 broken article reference。
- 用户可选择：
  - 移除引用
  - 改为纯文本
  - 指向其他候选文章
  - 如果文件恢复，则重新 reconcile

### 外部新增

如果外部新增文章：

- 无 ID 时自动分配 ID 并写回 front matter。
- 更新 `content/articles.json` 和 `content/links.json`。
- 可进入 Admin suggestions，建议目录、标题、tags、summary 和 normalize 操作。

### 外部移动或重命名

如果文章在 Obsidian 中被移动或重命名：

- 若 front matter `id` 保留，直接识别为同一文章。
- 若 `id` 丢失，但正文内容基本不变，则通过 fingerprint 识别。
- 如果标题也变化，但内容高度相似，仍优先识别为同一文章。
- 识别成功后，更新：
  - `content/articles.json`
  - `content/links.json`
  - 其他文章对该文章的 wiki 链接
  - preview 预处理输出

### 输入与约束

主要入口：

```python
refactor_article(
    source_rel_path: str,
    target_rel_path: str,
    *,
    content_dir: Path,
    static_images_dir: Path,
    preprocess: bool = True,
) -> RefactorReport
```

约束：

- 源和目标必须在 `content/` 内
- 目标必须是 `.md`
- 不能覆盖已有文件
- 不能把文件移动到 `public/`、`.hugo_temp_content/`、`docs/` 等非内容目录
- pending 与常规内容之间的移动也通过同一入口

### 引用更新

模块执行移动后扫描 `content/**/*.md`，默认排除 `content/pending/**/*.md`，更新指向旧文章的链接。

兼容形式：

```markdown
[[旧标题]]
[[posts/旧路径/foo]]
[[posts/旧路径/foo#heading]]
[[posts/旧路径/foo|别名]]
[[posts/旧路径/foo#heading|别名]]
```

更新后优先使用新文章的 Obsidian 简化链接：

```markdown
[[新标题]]
[[新标题#heading|别名]]
```

如果新标题存在歧义，则使用相对路径形式：

```markdown
[[posts/目标目录/new-name#heading|别名]]
```

### Manifest 更新

重构模块在移动后重建或更新：

- `content/articles.json`
- `content/links.json`
- `static/images/images.json` 中与文章标题或文件名相关的 key

图片文件不因文章移动立即强制重命名。若文章 normalize 后图片名应调整，由单文件 normalize 负责。

所有文章引用优先通过文章 ID 建模。`content/links.json` 是面向 Obsidian link name 的解析索引，`content/articles.json` 是面向文章实体的稳定索引。

### Normalize 与 Preview

移动完成后：

- 对目标文章运行单文件 normalize
- 对被更新引用的文章运行 link normalize
- 不执行未引用图片删除
- 调用 `StaticSiteManager.preprocess_preview(force=True)`

Hugo watch 会自动刷新 1313。若未来需要硬重启 preview，可以在模块外层复用已有 preview launcher。

### 返回报告

`RefactorReport` 返回给 Admin：

```json
{
  "moved_from": "posts/old.md",
  "moved_to": "posts/数学/new.md",
  "updated_references": [
    {
      "path": "posts/renderer/a.md",
      "count": 2
    }
  ],
  "manifest_updated": true,
  "normalized": true,
  "validation": {},
  "warnings": [],
  "errors": []
}
```

## Admin 标题修改与重命名

当前 Admin 可修改文章 `title`。后续如果 UI 提供“同步文件名”或“Rename file”能力，必须调用 `content_refactor.py`。

行为：

- 仅修改 front matter title：不改文件名，只保存 front matter
- 用户选择“同步文件名”：根据 title 生成安全文件名，并调用 `refactor_article`
- 用户手动输入新文件名：调用 `refactor_article`

文件名生成规则：

- 去掉路径危险字符
- 特殊符号转 `_`
- 保留中文、英文、数字
- 后缀固定 `.md`
- 如果目标已存在，要求用户重新确认新名称，不自动覆盖

## LLM 目录建议

新增模块：`src/hugo_blog/pipeline/content_suggestions.py`。

职责：

- 读取文章 title、front matter、摘要和正文前若干字符
- 读取当前内容目录树
- 调用 LLM 返回候选目标路径和理由

LLM 只返回建议，不执行文件操作。后端需要校验 LLM 返回路径：

- 必须是相对 `content/` 的 `.md` 路径
- 不能进入 pending，除非建议类型是 `Move to pending`
- 不能包含 `..`
- 不能覆盖已有文件

## API 草案

- `GET /api/content/pages?scope=normal|pending`
- `POST /api/content/normalize`
- `POST /api/content/normalize-batch`
- `POST /api/content/move-to-pending`
- `POST /api/content/restore-suggestions`
- `POST /api/content/refactor`
- `POST /api/content/suggestions`
- `POST /api/content/apply-suggestion`

## 测试策略

后端测试：

- content inventory 扫描递归 content 并排除 pending
- article manifest 扫描递归 content 并包含 pending
- 无 ID 文章自动写入 front matter ID
- Obsidian 外部移动后通过 ID 识别同一文章
- ID 丢失但正文基本不变时通过 fingerprint 识别同一文章
- 外部删除文章后保留 missing 状态并报告 broken reference
- 外部新增文章后分配 ID 并更新 manifest
- 单篇 normalize 不删除图片
- 批量 normalize 返回逐篇结果
- move to pending 保留原相对路径
- pending restore 候选路径校验
- rename 后更新 wiki 链接
- rename 后更新 `content/links.json`
- title 同步文件名必须调用 refactor 模块
- draft 目标链接不生成会阻断 Hugo 的 relref

前端测试或构建验证：

- Admin UI 构建通过
- 排序 Title / Date / Modified 正常
- 多选 normalize 可触发批量 API
- pending 视图可显示和恢复
- suggestions 页面只显示待确认操作，不自动执行

## 非目标

- 不让 LLM 自动移动或重命名文件
- 不在 Admin normalize 中删除未引用图片
- 不直接编辑 `.hugo_temp_content/` 或 `public/`
- 不把 docs 源码说明纳入文章管理
