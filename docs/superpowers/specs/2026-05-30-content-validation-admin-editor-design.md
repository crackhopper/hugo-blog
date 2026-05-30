# 内容验证与 Admin 编辑器设计

## 背景

当前博客源文档使用 Obsidian 写法，Hugo 预览使用导出后的 `.hugo_temp_content/`。`normalize` 会修改原始 Markdown，`export` 会把 Obsidian 图片和 wiki link 转成 Hugo 可识别的 Markdown。现在的问题是：如果源文档里的图片引用已经被改写，但 `static/images/` 中没有对应文件，Hugo 仍然可以启动，直到浏览器里才发现图片 404。

`C++内存管理` 的图片丢失就是这种情况：源文档引用 `![[C++内存管理-intro-01.png]]`，导出后指向 `/images/C%2B%2B...intro-01.png`，但 `static/images/C++内存管理-intro-01.png` 不存在。

## 目标

- 在 `normalize`、`serve`、`build`、`deploy` 前统一检查 broken image。
- 支持 Obsidian 图片引用、Markdown 图片引用和 HTML `<img>` 引用。
- `serve` 遇到 validation error 时仍启动 `1314` Admin/Issues/Editor，但不启动 `1313` Hugo preview。
- `build` 和 `deploy` 遇到 validation error 时直接失败。
- Admin 增加 Issues 页面，按文档展示错误。
- Admin 增加 Monaco Markdown 编辑器，只编辑 `content/posts/` 原文。
- 保存后重新导出并验证，确保程序转换后的 preview 内容正确。
- 同步更新中文 docs 和源码说明文档。

## 非目标

- 第一版不做自动从 git 历史或 `repo_to_deploy` 恢复图片。
- 第一版不做完整 Hugo HTML iframe 预览。
- 第一版不允许编辑 `content/page/`、`content/projects/`、`content/pending/`。
- 第一版不把验证错误写入 front matter。

## 架构

新增统一验证模块：

```text
src/hugo_blog/pipeline/validate.py
```

该模块只读取文件并生成报告，不直接修改内容。调用方根据报告决定是否阻断、显示或继续。

数据流：

```text
content/posts/**/*.md
  -> validate source references
  -> export to .hugo_temp_content/
  -> validate exported /images/... references
  -> Hugo preview/build
```

Admin 数据流：

```text
/api/validation/run
  -> run validator
  -> return grouped issues

/api/content/<path>
  -> read/write content/posts/<path>

/api/content-preview/<path>
  -> transform one source document
  -> return converted markdown + validation report
```

## 验证模型

新增数据结构：

```python
@dataclass(frozen=True)
class ValidationIssue:
    severity: str          # "error" | "warning"
    kind: str              # "missing_image" | "broken_wiki_link"
    source_path: str       # posts/C++/C++内存管理.md
    line: int
    raw_reference: str
    target: str
    message: str
    candidates: list[str]

@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue]
```

第一版必须支持的图片引用：

```markdown
![[image.png]]
![[image.png|640]]
![](/images/image.png)
![](image.png)
<img src="/images/image.png">
```

验证规则：

- 图片目标必须存在于 `static/images/`。
- `/images/foo.png` 映射到 `static/images/foo.png`。
- URL encoded 路径需要 decode 后检查。
- 非图片 wiki link 不进入图片检查，继续由现有 wiki link 逻辑处理。
- 候选图片使用文件名相似度、相同文章 stem、相同扩展名生成，供 Issues 页面提示。

## normalize 行为

`normalize` 调用 validator：

- 处理前先验证目标文章集合。
- 如果某篇文章有 broken image，默认不继续写入该文件，避免进一步破坏引用。
- `--dry-run` 只报告。
- 暂不实现 `--fix-images`，但 validation issue 中保留 candidates，为下一步交互修复做准备。
- `--review-each` 每次写入后对该文章重新验证；验证失败时仍报告，并不自动启动 preview。

## serve 行为

`serve.py` 启动流程改为：

1. 停止旧 preview。
2. 构建 Admin UI，如有需要。
3. 启动 `1314` Admin 服务。
4. 运行 validation。
5. 如果 validation 有 error：
   - 不启动 `1313` Hugo preview。
   - 命令行打印 Issues URL。
   - 保持 Admin 服务运行，用户可以打开 `/issues/` 和 `/editor/...` 修复。
6. 如果 validation 通过：
   - 导出 `.hugo_temp_content/`。
   - 启动 watcher。
   - 启动 Hugo preview。

Admin 中切换 draft 或保存内容后重启 preview 时，也复用同一套验证流程。

## build/deploy 行为

`build.py` 和 `deploy.py` 在 Hugo build 前运行 validation：

- 有 error：直接退出非 0。
- 无 error：继续 export 和 Hugo build。

这是发布链路，不能允许 broken image 混入输出。

## Admin Issues 页面

React App 新增页面：

```text
/issues/
```

顶部导航包含：

```text
Admin | Issues | Docs | Preview
```

页面内容：

- 汇总：错误数量、warning 数量、影响文档数量。
- 按 `source_path` 分组展示问题。
- 每条 issue 显示：
  - 文件路径
  - 行号
  - 原始引用
  - 缺失目标
  - 候选图片
  - message
- 操作按钮：
  - `Edit Markdown`
  - `Revalidate`

点击 `Edit Markdown` 跳转：

```text
/editor/posts/C++/C++内存管理.md
```

## Monaco 编辑器

第一版直接引入：

```json
"@monaco-editor/react": "...",
"monaco-editor": "..."
```

Editor 页面：

```text
/editor/<content-path>
```

布局：

- 左侧：Monaco Markdown 编辑器，编辑原始 `content/posts/...md`。
- 右侧上方：当前 validation issues。
- 右侧下方：转换后的 Markdown 预览。

行为：

- `GET /api/content/<path>` 读取原始 Markdown。
- `PUT /api/content/<path>` 保存原始 Markdown。
- `GET /api/content-preview/<path>` 返回转换后的 Markdown 和 validation report。
- 保存后自动重新运行单文件 export/validation。
- issue 点击后 Monaco 跳到对应行。
- `Preview` 按钮只在 validation 通过后可用，打开 `1313` 对应文章 URL。

路径安全：

- 只允许 `content/posts/`。
- 禁止 `..` 路径逃逸。
- 禁止编辑 `.hugo_temp_content/` 或 `public/`。

## 后端 API

新增或扩展：

```text
GET  /api/validation
POST /api/validation/run
GET  /api/content/<path>
PUT  /api/content/<path>
GET  /api/content-preview/<path>
```

`/api/validation` 返回最近一次报告。`/api/validation/run` 立即重新扫描。

`/api/content-preview/<path>` 不写盘，只返回：

```json
{
  "path": "posts/C++/C++内存管理.md",
  "converted": "...Hugo-readable Markdown...",
  "report": {
    "ok": false,
    "issues": []
  },
  "preview_url": "/2025/12/16/c++内存管理/"
}
```

## 错误处理

- validator 自身异常返回 Admin 可读错误，不让服务崩溃。
- 缺图是 `error`。
- 候选为空仍然是 `error`，但 message 要说明未找到候选。
- 单文件编辑保存失败时保留 Monaco 内容，不覆盖用户当前输入。

## 测试策略

后端测试：

- Obsidian image 缺失会产生 `missing_image`。
- Markdown image 缺失会产生 `missing_image`。
- HTML img 缺失会产生 `missing_image`。
- URL encoded `/images/...` 可以正确 decode。
- `serve` validation error 时不构造 Hugo server command，但 Admin 可启动。
- `build` validation error 时退出非 0。
- content API 拒绝非 posts 和路径逃逸。

前端验证：

- Vite build 通过。
- Issues 页面能加载 validation report。
- Editor 页面能加载 Monaco，保存后刷新 preview report。

## 文档更新

需要更新：

- `docs/content-pipeline.md`
- `docs/python-tooling.md`
- `docs/source/pipeline-validate.md`
- `docs/source/preview-admin.md`
- `docs/source/preview-admin-ui-app.md`
- `docs/source/preview-serve.md`
- `README.md`

文档全部使用中文。
