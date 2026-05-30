# AGENTS.md — Hugo 博客项目指南

本文档面向 AI Agent 与作者，说明本仓库的内容规范、构建流程与 Python 工具链。

## 项目概览

- **编辑器**：Obsidian（vault 根目录即仓库根）
- **发布器**：Hugo + Stack 主题
- **语言**：中文技术博客
- **工具链**：Python package in `src/hugo_blog/`，运行入口在 `init.py` 与 `scripts/*.py`

源文件使用 **Obsidian wiki 语法**；构建时由 `hugo_blog.pipeline.export` 转换为 Hugo 可识别的 Markdown，**不修改** `content/` 原文。

## 目录结构

```text
hugo-blog/
├── init.py               # 首次初始化入口
├── src/hugo_blog/        # Python 工具链实现
├── scripts/              # 薄运行入口
├── docs/                 # 开发者文档
├── content/              # Obsidian/Hugo 内容源文件
│   └── pending/          # 待整理笔记，工具链跳过
├── static/images/        # 图片附件
├── themes/Stack/         # Hugo 主题 submodule
├── .hugo_temp_content/   # 预处理输出（勿手改、勿提交）
└── public/               # Hugo 构建输出（勿提交）
```

## Front Matter

每篇文章开头使用 YAML front matter：

```yaml
---
title: 文章标题
date: 2026-05-30T13:00:00+08:00
tags:
  - 标签1
draft: true
---
```

- `draft: true` 为草稿；`python scripts/serve.py` 默认展示草稿
- 不维护 front matter `description`
- 摘要写在正文开头，并在摘要后写 `<!-- more -->`

## 图片引用（源文件写法）

统一使用 Obsidian embed 语法，图片存放在 `static/images/`：

```markdown
![[RT-04-材质和BRDF-回顾brdf定义-01.png]]
![[RT-04-材质和BRDF-回顾brdf定义-02.png|464]]
![[RT-04-材质和BRDF-lambertian-漫反射-01.png|546x370]]
```

命名规范：

```text
{文章stem}-{段落slug}-{两位序号}.{ext}
```

不要在源文件写 `![](/images/...)` 或 HTML `<img>`；历史内容用 `python scripts/normalize.py` 迁移。

## 文章间引用（源文件写法）

统一使用 Obsidian wiki 链接，不要在源文件写 `{{< relref ... >}}`：

```markdown
[[深入思考曲面积分]]
[[posts/数学/深入思考曲面积分]]
[[深入思考曲面积分#换元剪切技巧]]
[[RT-02-光传播理论(渲染方程)|渲染方程]]
```

构建时 wiki 链接解析为 Hugo `relref`。索引键包括相对路径、stem、front matter `title` 和大小写不敏感变体。

## 工作流命令

| 场景 | 命令 |
|------|------|
| 初始化本地工具链 | `python3 init.py` |
| 本地预览 | `python scripts/serve.py` |
| 构建站点 | `python scripts/build.py` |
| 规范化内容并交互确认 | `python scripts/normalize.py` |
| 规范化并跳过确认 | `python scripts/normalize.py --apply-all` |
| 逐篇审核并重启预览 | `python scripts/normalize.py --review-each` |
| 规范化 dry-run | `python scripts/normalize.py --dry-run` |
| 修复 broken 链接 | `python scripts/normalize.py --fix-links` |
| 单篇文章 | `python scripts/normalize.py --article "RT-04-材质和BRDF"` |
| 部署 | `python scripts/deploy.py` |

## 构建流水线

```text
content/*.md -> hugo_blog.pipeline.export -> .hugo_temp_content/ -> hugo -> public/
static/images/ -----------------------------------------------> public/images/
```

## 内容规范化

`hugo_blog.pipeline.normalize` 分阶段执行：

1. 扫描图片引用和 wiki 索引
2. 检查未引用图片
3. 按命名规范重命名图片并更新引用
4. 迁移 Markdown 图片和 Hugo `relref`
5. 修复 broken wiki 链接
6. 补齐 front matter、tags、draft 和正文摘要

默认发现 front matter/tags/摘要需要修复时会询问；只有传入 `--apply-all` 才跳过确认。`--review-each` 会逐篇询问，且每篇写入后重启预览后台。需要预览变化时显式加 `--dry-run`。Agent 批量整理内容前应先运行 `python scripts/normalize.py --dry-run` 展示摘要，经用户确认后再运行默认写入命令。

默认归一化在用户确认后要求 `.env` 中配置可用 LLM；缺少 `LLM_MODEL` 或 `LLM_API_KEY` 会 fatal。`--dry-run` 不调用 LLM，也不会启动预览。真实写入结束后自动启动远程预览。LLM 生成摘要或 tags 时必须输出生成内容。只有明确需要离线运行时才使用 `--no-llm`。

预览默认包含草稿，可用 `python scripts/serve.py --no-drafts` 关闭。构建和部署默认不包含草稿，也不包含开发文档。预览时 `docs/` 会被导出到 `/docs/` 供开发者查看。

## Agent 操作约束

1. 编辑 `content/` 时使用 Obsidian wiki 语法
2. 不要直接修改 `.hugo_temp_content/`、`public/`、`.tools/`、`.venv/`
3. 批量整理内容前先 `python scripts/normalize.py --dry-run`
4. broken wiki 链接必须经用户确认后再 `--fix-links` 写入
5. `content/pending/` 中的文档全部跳过，不参与 normalize、预览导出、构建索引或 Admin 列表
6. Python 业务逻辑必须放在 `src/hugo_blog/`，`scripts/*.py` 只做薄入口
7. 需要理解工具链时先读 `docs/`

## 相关文档

| 文件 | 用途 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 整体架构和数据流 |
| [docs/python-tooling.md](docs/python-tooling.md) | Python 包和模块职责 |
| [docs/content-pipeline.md](docs/content-pipeline.md) | 内容处理流水线 |
| [docs/llm-metadata.md](docs/llm-metadata.md) | LLM 摘要和 tags |
| [docs/deployment.md](docs/deployment.md) | 构建与部署 |
