# `src/hugo_blog/pipeline/article_manifest.py`

这个文件维护 `content/articles.json`，用于给每篇 Markdown 建立稳定身份。

## 主要职责

- 扫描 `content/**/*.md`，包含 `pending`。
- 为缺少 `id` 的文章写入 front matter `id`。
- 通过已有 `id` 或正文指纹识别移动、重命名后的文章。
- 记录当前路径、历史路径、标题、草稿状态、aliases、出链、入链和图片引用。
- 将删除或暂时找不到的旧记录标记为 `missing`。

## 修改注意

`ensure_front_matter_id()` 用字符串方式写入 `id`，是为了尽量保留原 front matter 的注释和引号风格。不要轻易改成完整 YAML dump。

入链只在目标唯一时建立。如果标题或 stem 有歧义，宁可不建立 incoming link，也不要猜错。
