# `src/hugo_blog/preview/launcher.py`

这个文件提供后台启动 preview 的便捷函数，主要给 normalize review 流程使用。

## 主要职责

- 生成后台 `scripts/serve.py` 命令。
- 推断局域网访问 URL。
- 用 `subprocess.Popen` 后台启动预览。

## 修改注意

这里不会等待服务完全启动。调用方如果要立刻访问页面，需要自己加短暂等待或重试。
