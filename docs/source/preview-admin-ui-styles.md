# `src/hugo_blog/preview/admin_ui/src/styles.css`

这个文件定义 React Admin/Docs 的样式。

## 主要职责

- Admin 表格、筛选栏、按钮和状态 badge。
- Docs 的三栏布局：左侧目录、中间正文、右侧页内目录。
- 响应式布局，窄屏时折叠成单栏。

## 设计取向

Docs 参考 mkdocs-material 的阅读体验：固定侧栏、正文居中、页内目录辅助扫描。Admin 则保持工具型界面，信息密度更高。

## 修改注意

不要让按钮、表格单元格和文档标题在窄屏重叠。新增样式时优先检查 `900px` 以下布局。
