# Python 工具使用指南

## 入口命令

新环境先运行初始化：

```bash
python3 init.py
```

初始化后，可以通过脚本运行：

```bash
python scripts/serve.py
python scripts/normalize.py
python scripts/build.py
python scripts/deploy.py
```

也可以通过 uv console scripts 运行：

```bash
uv run blog-serve
uv run blog-normalize
uv run blog-build
uv run blog-deploy
```

逐篇检查文章时使用：

```bash
python scripts/normalize.py --review-each
```

这个模式会在每篇文章写入前询问，并在写入后重启预览，方便马上查看页面效果。

## 模块职责

- `hugo_blog.paths`：共享项目路径。
- `hugo_blog.tools.hugo`：本地 Hugo 版本检测和下载。
- `hugo_blog.pipeline.markdown_document`：Markdown 和 front matter 解析。
- `hugo_blog.pipeline.metadata`：front matter、draft、tags、摘要和预览 URL 处理。
- `hugo_blog.pipeline.content_filters`：定义哪些内容目录可处理、哪些目录跳过。
- `hugo_blog.pipeline.image_manifest`：读写 `static/images/images.json` 图片索引。
- `hugo_blog.pipeline.image_normalizer`：把单篇文章里的短图片引用归一化到日期目录。
- `hugo_blog.pipeline.wikilinks`：Obsidian wiki link 解析和 Hugo 转换。
- `hugo_blog.pipeline.validate`：检查源文档和导出文档中的 broken image。
- `hugo_blog.pipeline.images`：图片清理和命名相关兼容导出。
- `hugo_blog.pipeline.relrefs`：Hugo `relref` 迁移兼容导出。
- `hugo_blog.pipeline.export`：导出 Hugo 可读 Markdown 到 `.hugo_temp_content/`。
- `hugo_blog.pipeline.normalize`：源文章规范化编排。
- `hugo_blog.preview.admin`：本地 Admin/Docs API。
- `hugo_blog.preview.admin_ui_build`：构建本地 Vite/React 管理界面。
- `hugo_blog.preview.launcher`：为 normalize review 流程后台重启预览。
- `hugo_blog.preview.serve`：启动 Hugo、Admin 和 watcher。
- `hugo_blog.llm.client`：DeepSeek/OpenAI 兼容聊天补全客户端。

## 新增处理步骤

新的 Markdown 处理逻辑应该优先放在 `src/hugo_blog/pipeline/` 下，尽量写成可测试的纯函数，再由 `pipeline.normalize` 或 `pipeline.export` 调用。

推荐形状：

```python
def transform_x(content: str, context: XContext) -> TransformResult:
    ...
```

结果对象应该能说明内容是否发生变化。CLI 只负责打印摘要、决定 dry-run 还是写入。

## React Admin 和 Docs

React 源码在 `src/hugo_blog/preview/admin_ui/`。它由 Python Admin 服务在 `1314` 端口提供：

```text
http://<host>:1314/admin/
http://<host>:1314/issues/
http://<host>:1314/docs/
```

`/issues/` 显示 preview/build 前会阻断的问题，主要包括缺失图片。点击 `Edit Markdown` 可以进入 Monaco 编辑器，只编辑 `content/posts/` 下的原始 Markdown。保存后 Admin 会重新导出和校验；校验通过后才建议跳转到 1313 preview。

如果编辑器里写了 `![[compile.png]]` 这样的 Obsidian 短引用，保存时后端会在 `static/images/` 内按文件名查找，移动到 `static/images/YYYY/MM/`，更新 `images.json`，并把原文引用改成标准短文件名。

构建命令：

```bash
python -m hugo_blog.preview.admin_ui_build
```

`python scripts/serve.py` 在 dist 缺失且本地有 npm 时，会自动构建 Admin UI。
