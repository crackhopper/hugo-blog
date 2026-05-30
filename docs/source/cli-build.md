# `src/hugo_blog/cli/build.py`

这个文件是 `blog-build` 的 CLI 入口。

## 主要职责

- 解析 build 参数。
- 默认先导出 `.hugo_temp_content/`。
- 调用 `StaticSiteManager.run_build()` 执行 Hugo build。

## 常用参数

- `--drafts`：构建草稿。
- `--destination`：指定 Hugo 输出目录。
- `--no-minify`：关闭 minify。
- `--no-preprocess`：直接使用 `content/` 构建，主要用于排查问题。

## 修改注意

CLI 文件保持薄封装。构建行为应该放在 `static_site.py`，不要把 Hugo 细节散落到这里。
