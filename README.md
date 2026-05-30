# crackhopper 的技术博客

基于 Obsidian + Hugo + Stack 主题的中文技术博客。源文件保留 Obsidian wiki 语法，构建前由 Python 脚本预处理到 Hugo 可识别的 Markdown。

## 快速开始

首次进入仓库后执行：

```bash
python3 init.py
```

脚本会自动：

- 使用 `uv sync` 创建/更新 `.venv`
- 检查本地 Hugo 版本，不满足时下载 Hugo extended 到 `.tools/hugo/`
- 检查 `.env` 中的 LLM 配置；缺失时交互式提示填写
- 生成或更新 `.env`
- 进入一个已注入本地工具链的交互 shell

进入该 shell 后，`python` 和 `hugo` 会优先指向项目本地版本。自动化环境可用：

```bash
python3 init.py --no-shell
```

`--no-shell` 不会交互补配置；如果缺少 `LLM_MODEL` 或 `LLM_API_KEY` 会直接失败。

## 本地预览

启动远程可访问的预览服务：

```bash
python scripts/serve.py
```

默认行为：

- 绑定 `0.0.0.0`
- 先启动 1314 Admin，再校验 `content/` 和 `.hugo_temp_content/`
- 校验通过后预处理 `content/` 到 `.hugo_temp_content/`
- 默认不包含 draft 文档
- 启动 Hugo 预览端口 `1313`
- 启动本地管理页/API 端口 `1314`

常用参数：

```bash
python scripts/serve.py --port 1313 --admin-port 1314
python scripts/serve.py --drafts
python scripts/serve.py --no-admin
python scripts/serve.py --host 127.0.0.1
```

管理页地址：

```text
http://<你的局域网IP>:1314/admin/
http://<你的局域网IP>:1314/issues/
http://<你的局域网IP>:1314/docs/
```

管理页是本地构建的 React 应用，支持目录过滤、draft/published 过滤、关键字搜索、按 modified/date/title/directory 排序，并编辑 `title`、`date`、`tags`、`draft`。顶部 `Save all & restart preview` 会保存所有改动并重启预览；如需查看草稿，先勾选 `Preview drafts`。它只用于本地预览写作，不参与生产发布。

如果校验发现 broken image，`serve` 会只保留 1314 Admin，不启动 1313 Hugo preview。进入 `/issues/` 可以查看具体文件、行号、缺失图片和候选文件；点击 `Edit Markdown` 会打开 Monaco 编辑器修改 `content/posts/` 原文。保存后工具链会重新导出并校验，校验通过后再跳转 1313 preview。

如果首次启动提示 Admin UI 未构建，可手动执行：

```bash
python -m hugo_blog.preview.admin_ui_build
```

## 内容规范

内容目录：

```text
content/
├── posts/      # 博客文章
├── projects/   # 项目页
├── page/       # about、archives 等独立页面
└── pending/    # 待整理笔记，工具链跳过
```

文章使用 YAML front matter：

```yaml
---
title: 文章标题
date: 2026-05-30T13:00:00+08:00
tags:
  - C++
draft: true
---
```

摘要写在正文开头，并用 Hugo 摘要分界线结束：

```markdown
这里是摘要内容。

<!-- more -->

# 第一个标题
```

不要在 front matter 中维护 `description` 字段；归一化脚本会移除它。

图片和文章引用遵循 [AGENTS.md](AGENTS.md)：源文件使用 Obsidian wiki 语法，构建时自动转换。

## 内容归一化

默认发现 front matter/tags/摘要需要修复时会先询问，确认后才写入：

```bash
python scripts/normalize.py
```

跳过确认并处理所有候选文章：

```bash
python scripts/normalize.py --apply-all
```

逐篇审核：每篇写入前询问，写入后自动重启预览后台：

```bash
python scripts/normalize.py --review-each
```

Dry-run 检查：

```bash
python scripts/normalize.py --dry-run
```

常用参数：

```bash
python scripts/normalize.py --article "RT-04-材质和BRDF"
python scripts/normalize.py --apply-all
python scripts/normalize.py --review-each
python scripts/normalize.py --no-llm
python scripts/normalize.py --fix-links
python scripts/normalize.py --skip-metadata
```

归一化会处理：

- 删除未引用图片的提示与确认
- broken image 检查；存在缺失图片时跳过该文件写入
- 图片命名规范化
- 旧 Markdown 图片链接迁移到 Obsidian `![[...]]`
- Hugo `relref` 迁移到 Obsidian wiki 链接
- broken wiki 链接交互式修复
- 缺失 front matter 自动补齐
- 缺失 `tags` 自动生成
- 缺失正文摘要自动生成并插入到 `<!-- more -->` 前

`draft` 只在缺失时补 `true`；已有 `draft: false` 不会被覆盖。

真实写入完成后，归一化脚本会自动启动远程预览。`--dry-run` 不启动预览。

## LLM 配置

`scripts/normalize.py` 默认会在缺失 tags 或摘要时调用 LLM。配置写入 `.env`：

```bash
LLM_PROVIDER="deepseek"
LLM_BASE_URL="https://api.deepseek.com"
LLM_MODEL="你的模型名"
LLM_API_KEY="你的 API Key"
```

DeepSeek 使用 OpenAI-compatible chat completions API。默认情况下，归一化需要可用的 `LLM_API_KEY` 和 `LLM_MODEL`；缺失会 fatal。`--dry-run` 不调用 LLM。每次 LLM 生成摘要或 tags 时，脚本会打印对应文件名和生成内容。需要完全离线写入时必须显式使用：

```bash
python scripts/normalize.py --no-llm
```

## 构建与发布

本地构建：

```bash
python scripts/build.py
```

构建和发布默认不包含草稿，也不会包含 `docs/` 开发文档。构建前会执行同一套内容校验；如果存在 broken image，会直接失败。预览模式的开发文档由 1314 React Docs 提供。

发布使用 Python 脚本：

```bash
python scripts/deploy.py
```

部署配置位于 `.env`：

```bash
DEPLOY_REPO="git@github.com:crackhopper/crackhopper.github.io.git"
DEPLOY_BRANCH="master"
DEPLOY_DIR="repo_to_deploy"
```

发布流程会构建到 `DEPLOY_DIR` 并推送到目标 GitHub Pages 仓库。生产发布不包含 draft；draft 仅用于本地预览。

## 目录结构

```text
hugo-blog/
├── content/              # Obsidian/Hugo 内容源文件
├── static/images/        # 图片附件
├── scripts/              # 薄运行入口
├── src/hugo_blog/        # Python 工具链实现
├── docs/                 # 开发者文档
├── themes/Stack/         # Hugo Stack 主题 submodule
├── .hugo_temp_content/   # 预处理输出，勿提交
├── .tools/               # 本地 Hugo 等工具，勿提交
├── .venv/                # uv 创建的 Python 环境，勿提交
└── public/               # Hugo 构建输出，勿提交
```

更多 Agent 和内容细节见 [AGENTS.md](AGENTS.md)。
