# `src/hugo_blog/pipeline/export.py`

这个文件负责把 Obsidian 源文档导出为 Hugo 可读的临时内容。

## 主要职责

- 遍历 `content/`。
- 转换 Obsidian wiki link 和图片 embed。
- 把结果写入 `.hugo_temp_content/`。
- 维护增量导出的 hash 状态。
- 预览模式生成 `/admin/` 桥接页。

## 重要边界

导出阶段不修改 `content/` 原文。`docs/` 不再复制到 Hugo 预览站，文档阅读由 `1314/docs/` 的 React 页面提供。

## 修改注意

这里使用文件锁避免 watcher、Admin 保存、手动 serve 同时触发导出造成冲突。
