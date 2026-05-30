# `src/hugo_blog/static_site.py`

这个文件封装静态站点生成器操作，是当前 Hugo 调用的统一入口。未来如果要切换到其他静态博客生成器，应优先从这个类开始抽象。

## 主要职责

- 确保本地 Hugo 可用。
- 调用预处理导出。
- 调用内容校验。
- 生成 Hugo build 命令。
- 启动后台 preview 的命令。

## 关键对象

- `StaticSiteManager`：站点管理类。
- `static_site_manager()`：进程内单例，避免各处重复创建 manager。

## 修改注意

`build_command()` 默认加入 `--cleanDestinationDir`，用于清理历史构建残留。不要随意移除，否则 build/deploy 可能保留已经移除的页面。

`validate_content()` 是 preview/build/deploy 共享的校验入口。新增静态站点生成器时，应保留这个抽象层，让上层 CLI 不直接依赖 Hugo 的实现细节。
