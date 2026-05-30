# Image Manifest Normalization Design

## 背景

Obsidian 支持在 `![[...]]` 中只写文件名，并在 vault 内自动匹配附件。当前 Python 工具链把 `![[compile.png]]` 直接映射为 `static/images/compile.png`，因此当图片真实位置不是根目录文件时会校验失败。

目标是把 Obsidian 的短文件名引用、Hugo 的路径化图片资源、以及仓库内不断增长的图片集合统一到一套可维护机制里。

## 设计目标

- 原始 Markdown 继续使用 Obsidian embed 风格。
- 图片只在 `static/images/` 内解析，不扫描整个仓库。
- 图片按文章日期移动到 `static/images/YYYY/MM/`。
- 文件名使用安全 slug，特殊符号转 `_`。
- `static/images/images.json` 作为短文件名到实际路径的 manifest。
- converter 和 validator 优先使用 manifest。
- Admin 保存单篇文章时可触发该文章的图片归一化。

## 非目标

- 不从 `repo_to_deploy/images/`、`public/`、`.hugo_temp_content/` 或主题目录查找图片。
- 不在 Admin 保存单篇文章时自动删除未引用图片。
- 不把 Markdown 原文改成 `/images/YYYY/MM/...`。

## Manifest

文件位置：

```text
static/images/images.json
```

格式：

```json
{
  "小白学写编译器_1_编译基础概念-一个例子-01.png": "2020/06/小白学写编译器_1_编译基础概念-一个例子-01.png"
}
```

键是 Obsidian 原文中的短 link 名，值是相对 `static/images/` 的实际文件路径。

## 标准图片路径

根据文章 front matter 的 `date` 生成目录：

```text
static/images/YYYY/MM/{article_slug}-{heading_slug}-{NN}.{ext}
```

如果文章没有 `date`，使用 Markdown 文件修改时间兜底。

示例：

```text
static/images/2020/06/小白学写编译器_1_编译基础概念-一个例子-01.png
```

原文引用更新为：

```markdown
![[小白学写编译器_1_编译基础概念-一个例子-01.png]]
```

## Slug 规则

- 中文、英文字母、数字保留。
- 空白、冒号、全角冒号、斜杠、括号、标点等特殊字符转 `_`。
- 连续 `_` 合并。
- 首尾 `_` 去掉。
- 扩展名转小写。

## 图片归一化流程

对单篇 Markdown：

1. 解析 `![[...]]` 图片引用。
2. 先查 `images.json`。
3. manifest 命中且目标文件存在：引用有效，可按需要继续标准命名检查。
4. manifest 未命中：只在 `static/images/` 下按文件名查找。
5. 找到多个匹配时，按路径排序后取第一个，并记录 warning。
6. 计算该图片所在 heading，生成 `{article_slug}-{heading_slug}-{NN}.{ext}`。
7. 将图片移动到 `static/images/YYYY/MM/标准名.ext`。
8. 更新 manifest：`标准名.ext -> YYYY/MM/标准名.ext`。
9. 更新原始 Markdown 引用为 `![[标准名.ext]]`。
10. 保存后再调用 converter 导出 Hugo Markdown。

## Converter 规则

`hugo_blog.pipeline.wikilinks.transform_obsidian_links()` 必须优先使用 manifest。

输入：

```markdown
![[小白学写编译器_1_编译基础概念-一个例子-01.png]]
```

manifest：

```json
{
  "小白学写编译器_1_编译基础概念-一个例子-01.png": "2020/06/小白学写编译器_1_编译基础概念-一个例子-01.png"
}
```

输出：

```markdown
![小白学写编译器_1_编译基础概念-一个例子-01](/images/2020/06/小白学写编译器_1_编译基础概念-一个例子-01.png)
```

如果 manifest 缺失：

- fallback 检查 `static/images/<filename>`。
- 如果存在，仍可导出旧路径。
- 同时 validator 标记为 `needs_image_normalization` warning。
- 如果不存在，报告 `missing_image` error。

## Validator 规则

校验器优先查 manifest：

- manifest 有 key 且实际文件存在：通过。
- manifest 有 key 但实际文件不存在：`missing_image` error。
- manifest 无 key 但 `static/images/<filename>` 存在：`needs_image_normalization` warning。
- manifest 无 key 且文件不存在：`missing_image` error。

warning 不阻断 preview/build；error 阻断。

## Admin 保存流程

`PUT /api/content/<path>` 保存 Markdown 时：

1. 写入用户编辑的原文。
2. 对该文件运行图片归一化。
3. 如果图片归一化修改了原文，返回最新原文内容。
4. 重新导出 `.hugo_temp_content`。
5. 重新校验并返回 report。

这样用户可以在 Monaco 中只写 Obsidian 风格短引用，例如 `![[compile.png]]`，保存后由 Python 自动移动图片、更新 manifest 和更新原文引用。

## 删除策略

未被 manifest 引用的文件不在 Admin 保存时自动删除。

删除逻辑放到 normalize 的专门流程中：

- 默认 dry-run。
- 列出 manifest 未引用且 posts 当前引用也找不到的文件。
- 用户确认后删除。

## 测试要求

- `![[compile.png]]` 可从 `static/images/nested/compile.png` 解析并移动到日期目录。
- 文件名中的全角冒号等特殊字符会转 `_`。
- manifest 命中时 converter 输出 `/images/YYYY/MM/name.png`。
- manifest 无 key 但根目录图片存在时 validator 返回 warning，不阻断。
- manifest key 指向缺失文件时 validator 返回 error。
- Admin 保存后返回更新后的 Markdown 内容和校验报告。

