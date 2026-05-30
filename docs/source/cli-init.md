# `src/hugo_blog/cli/init.py`

这个文件是 `blog-init` 的包内入口。

## 主要职责

它只转发到仓库根目录的 `init.py`。保留这个薄入口是为了让 `pyproject.toml` 的 console script 可以调用初始化逻辑。

## 修改注意

初始化主逻辑仍然在根目录 `init.py`，因为新环境最容易执行的是：

```bash
python3 init.py
```
