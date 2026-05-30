# Python 工具链架构

这个仓库把 `content/` 当成 Obsidian 原文，把 Hugo 当成最终渲染器。中间所有处理都由 Python 负责：规范化源文档、导出 Hugo 能理解的 Markdown、启动预览、管理文章元数据，以及发布站点。

## 数据流

```text
content/**/*.md
  -> hugo_blog.pipeline.normalize     # 可选：整理 posts 下的源文章
  -> hugo_blog.pipeline.export        # Obsidian 语法转 Hugo Markdown
  -> .hugo_temp_content/
  -> Hugo
  -> public/ 或部署目录
```

`content/` 是可编辑源文件。`.hugo_temp_content/`、`public/`、`.tools/`、`.venv/` 都是本地生成状态，不应该提交。

## 源码布局

可复用代码放在 `src/hugo_blog/`。可执行入口放在 `scripts/`，脚本只做薄封装，具体逻辑放回 Python 包里。

```text
init.py                 # 首次初始化入口
scripts/                # 薄 CLI 包装
src/hugo_blog/          # 可 import 的 Python 包
tests/                  # 单元测试
docs/                   # 开发文档，1314 React Docs 页面读取这里
```

## 模块边界

- `init.py` 放在仓库根目录，方便新环境直接运行 `python3 init.py`。
- `scripts/*.py` 只调用包内入口，不承载业务逻辑。
- `pipeline/` 负责 Markdown、front matter、图片、链接、导出和规范化。
- `preview/` 负责本地 Hugo 预览、React Admin、Docs 阅读页和后台启动。
- `tools/` 负责外部工具安装，目前主要是 Hugo。
- `llm/` 负责 DeepSeek/OpenAI 兼容的元数据生成。

## 处理范围

`normalize` 和 Admin 文章管理只处理 `content/posts/` 下的文章。`content/page/`、`content/projects/`、`content/pending/` 不进入文章规范化和 Admin 表格。这样可以避免把独立页面、项目页和暂存笔记误改成博客文章。
