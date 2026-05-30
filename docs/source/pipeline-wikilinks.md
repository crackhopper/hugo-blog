# `src/hugo_blog/pipeline/wikilinks.py`

这个文件处理 Obsidian wiki link、图片 embed 和 Hugo link 转换。

## 主要职责

- 建立 Markdown 文件索引。
- 解析 `[[文章]]`、`[[文章#标题]]`、`[[文章|别名]]`。
- 转换 wiki link 为 Hugo `relref`。
- 转换 Obsidian 图片 embed 为 Hugo 图片语法，并优先使用 `images.json` manifest 输出日期目录路径。
- 发现 broken wiki link。
- 迁移历史 `relref` 链接回 Obsidian wiki link。

## 修改注意

这是导出和 normalize 都会调用的共享模块。改链接解析时，要同时验证预览导出和 normalize 的行为。

图片转换不要直接假设 `![[a.png]]` 对应 `static/images/a.png`。应先查 manifest；只有 manifest 缺失时才走旧的根目录 fallback。
