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

### 写作全流程脚本

在项目根目录执行 `.\scripts\start-writing.ps1` 可以一键启动完整的写作环境：

1. **环境检查**：确认 Python 及依赖（特别是 `watchdog`）已安装，并运行一次 `scripts/preprocess_obsidian.py --force` 生成 `.hugo_temp_content` 临时目录。
2. **双目录监听**：脚本会后台运行 `scripts/watch_content.py`，同时监听 `content/` 下的 Markdown 与 `static/images/` 下的图片文件。
   - Markdown 发生变化时，监听服务会调用 `preprocess_obsidian.py`，把 Obsidian 语法的 `![[image.png]]` 转成 `![image](/images/image.png)` 并写入 `.hugo_temp_content`，Hugo 读取的始终是这个临时目录。
   - 图片发生变化时，监听服务除了再次触发预处理，还会把 `static/images/` 中的文件同步到 `public/images/`，保证本地预览可以立即访问到最新图片。
3. **Hugo 开发服务器**：脚本前台运行 `hugo server --contentDir .hugo_temp_content`，按 `Ctrl+C` 可以同时停掉监听与服务器。

> 提示：若不需要监听流程，可直接使用 `scripts/build.ps1 -Server` 启动 Hugo。

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

可以使用 Obsidian 的 插入模板指令 （默认快键 alt+shift+insert） 来插入 `新文章` 模板，从而插入了 Front Matter 模板。

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


## Content 目录配置

`content/` 目录是 Hugo 的内容根目录，不同子目录有不同的用途和配置方式。

### posts/ - 博客文章

**用途：** 存放博客文章，是网站的主要内容。
**目录结构：** 可以在 `posts/` 下创建子目录分类，如 `posts/C++/`、`posts/Python/` 等，不影响 URL 结构。

### notes/ - 笔记

**用途：** 存放学习笔记和理论知识整理。

### projects/ - 项目
**用途：** 展示个人项目。

### page/ - 独立页面
**用途：** 存放独立页面，如"关于"、"归档"等。

```
page/
├── about/
│   └── index.md
└── archives/
    └── index.md
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

obsidian 配置了自动插入截图并且重命名为 `文章标题-时间.png`，例如 `测试-20251115004604697.png`。

随后图片会被监控脚本复制到 `public/images/` ，文章的链接也会被调整更新，保存到 `.hugo_temp_content/` 中。

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


### 5. 自定义样式

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

配置使用主题：TODO:

## 参考资源

- [Hugo 官方文档](https://gohugo.io/documentation/)
- [Stack 主题文档](https://stack.jimmycai.com/)
- [Hugo 数学公式支持](https://gohugo.io/content-management/mathematics/)
