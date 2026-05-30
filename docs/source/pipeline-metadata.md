# `src/hugo_blog/pipeline/metadata.py`

这个文件负责文章元数据处理，是 normalize 和 Admin 共用的核心模块。

## 主要职责

- 解析和输出 front matter。
- 判断文章是否需要 normalize。
- 插入摘要和 `<!-- more -->`。
- 合并 LLM 生成的摘要和 tags。
- 为 Admin 列表生成文章数据和 preview URL。
- 更新文章核心 front matter 字段。

## 重要规则

- 不使用 `description` 字段。
- 摘要写在正文 `<!-- more -->` 前面。
- preview URL 按 Hugo permalink 生成。

## 修改注意

Admin 的保存并预览跳转依赖这里生成的 `preview_url`。改 permalink 规则时要同步测试。
