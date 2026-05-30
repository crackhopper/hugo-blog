# `src/hugo_blog/preview/serve.py`

这个文件是本地预览的主入口。

## 主要职责

- 检测局域网 IP。
- 停止旧的 preview 进程。
- 启动 Admin/Docs/Issues 服务。
- 校验源内容和导出内容。
- 预处理内容。
- 校验通过后启动 Hugo server。
- 启动 content watcher。
- 默认不包含 draft；需要草稿时使用 `--drafts` 或 Admin 的 draft 开关重启。

## 端口

- Hugo preview：默认 `1313`。
- React Admin/Docs：默认 `1314`。

## 修改注意

启动逻辑涉及多个进程。改动时要确认旧进程会被关闭，端口占用能被处理，且默认不显示草稿。

如果校验失败，`serve` 会保持 1314 Admin 可访问，但不会启动 1313 Hugo。用户应进入 `/issues/` 查看错误，再从 `/editor/<path>` 修改原始 Markdown。
