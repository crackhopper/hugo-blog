# `src/hugo_blog/pipeline/watch.py`

这个文件负责监听内容变化并触发重新导出。

## 主要职责

- 使用 watchdog 监听 `content/`。
- 对 Markdown 创建、修改、删除、移动做 debounce。
- 调用 `preprocess_content_dir(force=False)` 增量导出。

## 关键类型

- `MarkdownChangeHandler`：watchdog 事件处理器。

## 修改注意

watcher 只负责导出，不负责重启 Hugo。Hugo server 自己会监听 `.hugo_temp_content/` 的变化并刷新页面。
