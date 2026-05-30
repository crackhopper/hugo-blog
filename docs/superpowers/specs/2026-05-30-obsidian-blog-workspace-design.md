# Obsidian Blog Workspace 插件设计

## 背景

本仓库把 Obsidian vault 作为 Hugo 博客源文件。Python 工具链已经负责 normalize、manifest、图片归一化、链接转换、内容校验、预览和 Admin 管理页。现有 Obsidian 插件 `tools/obsidian-hugo-link-updater` 只处理文件重命名后的 wiki/relref 链接更新。

## 目标

把现有插件扩展为一个 Obsidian 侧边栏工作台，让作者在 Obsidian 内完成草稿管理、normalize、图片清理和预览相关操作。插件不复制 Python 里的博客语义逻辑，只负责 UI、Obsidian 事件监听和调用本项目 Python 后台 API。

## 能力边界

Obsidian 官方插件 API 支持自定义 View、读取 vault 文件、监听文件修改和重命名、打开文件。没有稳定公开能力直接过滤或替换原生 File Explorer 的文件树，因此第一版不修改原生文件列表，而是提供一个独立的 Blog Workspace 侧边栏。

## 架构

### Obsidian 插件

插件继续放在 `tools/obsidian-hugo-link-updater`，第一版保留插件 ID `hugo-link-updater`，避免用户重新安装。插件新增：

- Ribbon 图标：打开 Blog Workspace 侧边栏。
- 自定义 View：展示 Drafts、Needs Normalize、Pending、Image Issues 等列表。
- 筛选与排序：按标题、date、modified、目录、normalized 状态筛选或排序。
- 操作按钮：打开文章、Normalize 当前文章、Normalize 选中文章、清理未引用图片、刷新后台状态。
- 后台连接：优先连接已启动的 Python 管理后台；如果不可用，根据设置自动启动。

### Python 后台

Python 后台继续复用 `hugo_blog.preview.admin` 的 HTTP 服务。需要补齐插件友好的 API：

- `GET /api/health`：返回后台状态、项目根目录、Python/Hugo 可用性。
- `POST /api/bootstrap`：运行或检查初始化流程，返回可执行的下一步状态。
- `POST /api/images/cleanup`：调用现有图片引用检查与清理能力，默认 dry-run，明确确认后才删除。
- 复用已有 `GET /api/content`、`POST /api/content-normalize/<path>`、`POST /api/content-refactor`、`GET /api/issues`。

### 启动策略

插件采用 C 方案：

1. 启动时探测 `http://127.0.0.1:1314/api/health`。
2. 如果已有后台，直接使用。
3. 如果没有后台且设置允许自动启动，插件在桌面端通过 Node 子进程启动 `uv run python scripts/serve.py`。
4. 如果环境未初始化，插件提示并触发 `python init.py` 或展示具体命令。
5. 插件关闭时只停止自己启动的后台，不停止用户外部启动的后台。

## 数据流

1. 插件从 `/api/content?status=all&scope=normal` 获取文章列表。
2. 插件在本地筛选 draft、needs normalize、目录和关键词。
3. 用户点击文章时，插件用 Obsidian `WorkspaceLeaf.openFile()` 打开源 Markdown。
4. 用户点击 normalize 时，插件调用 Python API；Python 更新源文件、manifest、链接、图片引用并重建 preview。
5. 插件监听 Obsidian 文件 rename/modify 事件，刷新列表；重命名仍由 Python refactor API 或现有链接更新逻辑兜底。

## 图片清理

删除未引用图片不再依赖第三方 Obsidian 插件。第一版由 Python 后台提供 dry-run 报告，插件展示未引用图片列表和删除确认。确认后调用后台删除。后台必须继续遵守 manifest 规则，避免误删 `static/images/images.json` 中仍被引用的图片。

## 错误处理

- 后台不可用：侧边栏显示连接状态和启动按钮。
- 环境缺失：提示运行初始化，或在桌面端尝试自动执行。
- Normalize 失败：显示 Python 返回的 validation issues 和日志摘要。
- 图片删除：默认 dry-run，删除前必须二次确认。

## 测试策略

- TypeScript 插件逻辑拆分为纯函数：筛选、排序、API client、front matter draft 判断，使用 Node 测试。
- Python API 使用现有 unittest 风格补充 `health/bootstrap/images cleanup` 测试。
- 插件构建使用 `npm run build`。
- 本机无法完整验证 Obsidian UI，但可以验证构建产物和 HTTP API。
