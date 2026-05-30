# `src/hugo_blog/preview/admin.py`

这个文件提供 1314 端口的 Admin/Docs 后端。

## 主要职责

- 提供 React 静态资源。
- 提供文章列表 API。
- 更新 posts 下文章的核心 front matter。
- 提供内容校验报告 API。
- 读取和保存 posts 下的原始 Markdown。
- 为 Monaco 编辑器提供转换后的 Markdown 预览。
- 切换 draft preview 并重启预览。
- 提供 docs 列表和单篇 docs 内容 API。

## 当前接口

- `GET /api/pages`
- `PUT /api/pages/<path>`
- `PUT /api/preview/drafts`
- `GET /api/validation`
- `POST /api/validation/run`
- `GET /api/content/<path>`
- `PUT /api/content/<path>`
- `GET /api/content-preview/<path>`
- `PUT /api/content-preview/<path>`
- `GET /api/docs`
- `GET /api/docs/<path>`

## 修改注意

Admin 只允许修改 `content/posts/` 下的文章。`page`、`projects`、`pending` 不显示也不能通过 API 修改。

`/issues/` 和 `/editor/<path>` 都由 React 前端接管。后端只负责返回同一个 `index.html`，实际路由在 `App.tsx` 内完成。
