# `src/hugo_blog/paths.py`

这个文件集中定义项目内常用路径，是工具链的路径常量层。

## 主要职责

- `PROJECT_ROOT`：仓库根目录。
- `CONTENT_DIR`：源内容目录 `content/`。
- `TEMP_CONTENT_DIR`：Hugo 临时内容目录 `.hugo_temp_content/`。
- `STATIC_IMAGES_DIR`：静态图片目录 `static/images/`。

## 修改注意

这里的路径被构建、预览、规范化、watcher 和 Hugo 安装逻辑共享。修改前要确认所有调用方是否仍然能从任意工作目录运行。
