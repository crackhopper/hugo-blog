# crackhopper的技术博客

基于 Hugo + Stack 主题的静态博客

## 快速开始

### 安装 Hugo

1. 访问 https://gohugo.io/installation/ 安装 Hugo
2. 确保安装的是 **Hugo Extended** 版本（Stack 主题需要）

### 本地开发

```bash
# 启动开发服务器（包含草稿）
hugo server -D

# 启动开发服务器（不包含草稿）
hugo server

# 生成静态文件
hugo

# 生成静态文件（包含草稿）
hugo -D
```

访问 http://localhost:1313/ 查看博客

## 编写文章

### 创建新文章

在 `content/posts/` 目录下创建 Markdown 文件，文件名将作为 URL slug。

### Front Matter 模板

每篇文章需要在开头包含 Front Matter（元数据）：

```yaml
---
title: 文章标题
date: 2024-01-01T10:00:00+08:00
tags:
  - 标签1
  - 标签2
draft: false  # true 表示草稿，false 表示已发布
---
```

### 编写草稿

**方法 1：在 Front Matter 中设置**

```yaml
---
title: 我的草稿文章
date: 2024-01-01T10:00:00+08:00
draft: true  # 设置为 true
---
```

**方法 2：使用 Hugo 命令创建**

```bash
hugo new posts/我的新文章.md
```

默认创建的模板中 `draft: true`，编辑完成后改为 `false` 即可发布。

**预览草稿：**

```bash
# 启动服务器时包含草稿
hugo server -D
```

草稿文章不会出现在首页，但可以通过直接访问 URL 查看。

### 数学公式支持

本博客已启用数学公式支持，使用 LaTeX 语法：

- 行内公式：`$E = mc^2$` → $E = mc^2$
- 块级公式：
  ```
  $$
  \int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
  $$
  ```

在文章的 Front Matter 中，可以单独为某篇文章启用数学公式：

```yaml
---
title: 数学文章
math: true  # 启用数学公式
---
```

## Content 目录配置

`content/` 目录是 Hugo 的内容根目录，不同子目录有不同的用途和配置方式。

### posts/ - 博客文章

**用途：** 存放博客文章，是网站的主要内容。

**配置：**
- **Permalink：** `/:year/:month/:day/:title/`（在 `config.toml` 中配置）
- **URL 示例：** `/2024/01/01/文章标题/`
- **Front Matter 示例：**

```yaml
---
title: 文章标题
date: 2024-01-01T10:00:00+08:00
tags:
  - 标签1
  - 标签2
draft: false
---
```

**目录结构：** 可以在 `posts/` 下创建子目录分类，如 `posts/C++/`、`posts/Python/` 等，不影响 URL 结构。

### notes/ - 笔记

**用途：** 存放学习笔记和理论知识整理。

**配置：**
- **Permalink：** `/notes/:slug/`（在 `config.toml` 中配置）
- **URL 示例：** `/notes/笔记标题/`
- **需要创建 `_index.md` 作为列表页：**

```yaml
---
title: 笔记
date: 2024-01-01T10:00:00+08:00
draft: false
menu:
    main:
        name: 笔记
        weight: -80
        params:
            icon: hash
---
```

**说明：** `menu` 配置用于在导航菜单中显示，`weight` 控制菜单顺序（数值越小越靠前），`icon` 设置菜单图标。

### projects/ - 项目

**用途：** 展示个人项目。

**配置：**
- **Permalink：** `/projects/:slug/`（在 `config.toml` 中配置）
- **URL 示例：** `/projects/项目名称/`
- **需要创建 `_index.md` 作为列表页：**

```yaml
---
title: 项目
date: 2024-01-01T10:00:00+08:00
draft: false
menu:
    main:
        name: 项目
        weight: -70
        params:
            icon: link
---
```

**项目页面 Front Matter 示例：**

```yaml
---
title: 项目名称
date: 2024-01-01T10:00:00+08:00
draft: false
image: /images/project-cover.jpg  # 项目封面图
---
```

### page/ - 独立页面

**用途：** 存放独立页面，如"关于"、"归档"等。

**配置：**
- **Permalink：** `/:slug/`（在 `config.toml` 中配置）
- **URL 示例：** `/about/`、`/archives/`
- **需要创建子目录和 `index.md`：**

```
page/
├── about/
│   └── index.md
└── archives/
    └── index.md
```

**页面 Front Matter 示例：**

```yaml
---
title: 关于我
date: 2024-01-01T10:00:00+08:00
draft: false
slug: about
menu:
    main:
        weight: -90
        params:
            icon: user
---
```

### _index.md - 首页配置

**用途：** 配置网站首页的菜单项。

**位置：** `content/_index.md`

**配置示例：**

```yaml
---
menu:
    main:
        name: 文章
        weight: -100
        params:
            icon: home
---
```

**说明：** `weight: -100` 确保首页菜单项在最前面。

## Stack 主题使用技巧

### 1. 菜单配置

在 Front Matter 中使用 `menu` 字段配置导航菜单：

```yaml
---
menu:
    main:
        name: 菜单名称
        weight: -80  # 控制顺序，数值越小越靠前
        params:
            icon: hash  # 图标名称
---
```

**常用图标：** `home`、`user`、`hash`、`link`、`archive`、`search` 等。图标文件位于 `themes/Stack/assets/icons/`。

### 2. 图片使用

**静态资源位置：** `static/images/`

**在文章中使用：**

```markdown
![图片描述](/images/文章标题/图片名.png)
```

**在 Front Matter 中使用：**

```yaml
---
image: /images/cover.jpg  # 文章封面图
---
```

### 3. 文章分类和标签

**分类：** 通过目录结构自动分类，如 `posts/C++/` 下的文章属于 C++ 分类。

**标签：** 在 Front Matter 中设置：

```yaml
---
tags:
  - C++
  - CMake
  - 教程
---
```

### 4. 文章摘要

**方法 1：** 在 Front Matter 中设置 `description`

```yaml
---
description: 这是文章的摘要
---
```

**方法 2：** 在文章中使用 `<!--more-->` 分隔符，之前的内容作为摘要。

### 5. 代码高亮

已在 `config.toml` 中配置代码高亮：

```toml
[markup.highlight]
  style = 'github'
  lineNos = true
```

**使用示例：**

````markdown
```python
def hello():
    print("Hello, World!")
```
````

### 6. 数学公式

全局已启用数学公式，使用 LaTeX 语法：

- 行内公式：`$E = mc^2$`
- 块级公式：使用 `$$...$$`

### 7. 草稿管理

**创建草稿：**

```bash
hugo new posts/新文章.md
```

默认创建的模板中 `draft: true`。

**预览草稿：**

```bash
hugo server -D
```

### 8. 自定义样式

可以在 `static/` 目录下创建自定义 CSS 文件，然后在 `config.toml` 中引入。

## 目录结构

```
hugo-blog/
├── content/            # 内容目录
│   ├── _index.md      # 首页配置
│   ├── posts/         # 博客文章目录
│   │   ├── C++/       # 分类子目录
│   │   ├── Python/
│   │   └── ...
│   ├── notes/         # 笔记目录
│   │   ├── _index.md  # 笔记列表页
│   │   └── *.md       # 笔记文件
│   ├── projects/      # 项目目录
│   │   ├── _index.md  # 项目列表页
│   │   └── */         # 项目子目录
│   └── page/          # 独立页面
│       ├── about/     # 关于页面
│       └── archives/  # 归档页面
├── static/            # 静态资源目录
│   └── images/        # 图片资源
├── themes/            # 主题目录
│   └── Stack/         # Stack 主题（Git Submodule）
├── config.toml        # Hugo 配置文件
├── templates/         # 文章模板
└── public/            # 构建输出目录（已忽略）
```

## 部署

### GitHub Pages

1. 生成静态文件：`hugo`
2. 将 `public/` 目录的内容推送到 GitHub Pages 仓库

### 使用 GitHub Actions（推荐）

创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy Hugo

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          submodules: true
      - uses: peaceiris/actions-hugo@v2
        with:
          hugo-version: 'latest'
          extended: true
      - run: hugo
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./public
```

## 主题管理

Stack 主题通过 Git Submodule 管理：

```bash
# 初始化 submodule（首次克隆仓库后）
git submodule update --init --recursive

# 更新主题到最新版本
cd themes/Stack
git pull origin master
cd ../..
git add themes/Stack
git commit -m "Update theme"
```

## 常用命令

```bash
# 创建新文章
hugo new posts/文章标题.md

# 本地预览（包含草稿）
hugo server -D

# 构建生产版本
hugo --minify

# 检查配置
hugo config
```

## 参考资源

- [Hugo 官方文档](https://gohugo.io/documentation/)
- [Stack 主题文档](https://stack.jimmycai.com/)
- [Hugo 数学公式支持](https://gohugo.io/content-management/mathematics/)
