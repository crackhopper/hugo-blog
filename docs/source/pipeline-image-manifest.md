# `src/hugo_blog/pipeline/image_manifest.py`

这个文件负责 `static/images/images.json`。

## 主要职责

- 读取和保存图片 manifest。
- 将 Obsidian 短 link 名解析到 `static/images/` 下的真实路径。
- 在 `static/images/` 内按 basename 查找候选图片。
- 忽略 `images.json` 本身。

## Manifest 格式

```json
{
  "post-intro-01.png": "2026/05/post-intro-01.png"
}
```

键是 Markdown 原文中的短文件名，值是相对 `static/images/` 的实际路径。

## 修改注意

这个模块不解析 Markdown，也不移动文件。它只提供图片索引和路径解析能力，供 normalizer、validator 和 converter 复用。
