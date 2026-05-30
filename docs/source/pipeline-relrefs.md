# `src/hugo_blog/pipeline/relrefs.py`

这个文件是 Hugo `relref` 迁移函数的兼容导出层。

## 主要职责

从 `pipeline.wikilinks` 导出 `migrate_relref_links()`，让旧调用方可以继续从 `pipeline.relrefs` import。

## 修改注意

真正的 relref 解析和迁移逻辑在 `wikilinks.py`。如果迁移规则变化，优先修改那里。
