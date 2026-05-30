# `src/hugo_blog/pipeline/images.py`

这个文件是图片相关函数的兼容导出层。

## 主要职责

它从 `pipeline.normalize` 重新导出图片清理、图片重命名和旧 Markdown 图片迁移相关函数。

## 为什么存在

早期图片逻辑集中在 normalizer 中。现在新的图片索引和单篇归一化逻辑已经拆到：

- `pipeline.image_manifest`
- `pipeline.image_normalizer`

这个模块继续给旧调用方一个更稳定的 import 位置。

## 修改注意

新增图片处理逻辑时，优先考虑把实现从 `normalize.py` 迁移到专门模块，再让这里继续提供兼容导出。
