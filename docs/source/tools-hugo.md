# `src/hugo_blog/tools/hugo.py`

这个文件负责安装和定位本地 Hugo。

## 主要职责

- 根据平台和架构生成 Hugo release asset 名称。
- 下载 Hugo extended 版本。
- 解压到 `.tools/hugo/`。
- 返回项目本地 Hugo 可执行文件路径。

## 修改注意

Hugo 是 Go 写的外部工具，不进入 Python venv。这个模块把它放到 `.tools/`，再由 `init.py` 写入 `.env` 的 PATH。
