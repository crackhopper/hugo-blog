# `src/hugo_blog/preview/admin_ui_build.py`

这个文件负责构建 React Admin/Docs 前端。

## 主要职责

- 检查本地是否有 `npm`。
- 如果没有 `node_modules`，先执行 `npm install`。
- 执行 `npm run build`。

## 修改注意

这是本地工具链的一部分，不参与 Hugo 构建。`scripts/serve.py` 会在 dist 缺失时自动调用它。
