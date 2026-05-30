# `src/hugo_blog/pipeline/content_suggestions.py`

这个文件负责让 LLM 给出文章归档位置建议。

## 主要职责

- 读取文章 front matter 和正文片段。
- 收集当前 `posts/` 下已有目录。
- 调用 LLM，要求返回多个候选 `target_path`、`title` 和 `reason`。
- 清洗 LLM 返回的路径，确保结果落在 `posts/` 下。
- 限制建议目录最多两级。

## 修改注意

LLM 输出只能作为建议，不能自动执行移动。真正移动必须交给 `content_refactor.py`，这样引用、manifest、normalize 和 preview rebuild 才能保持一致。
