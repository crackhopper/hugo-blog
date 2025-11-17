# crackhopper的技术博客

基于 Hugo + Stack 主题的静态博客

## 快速开始

### 安装 Hugo
访问 https://gohugo.io/installation/ 安装 Hugo

### 安装 Stack 主题
Stack 主题通过 Git Submodule 引入，首次克隆仓库后按顺序执行：

1. 初始化并同步子模块（常用场景）：

   ```powershell
   git submodule update --init --recursive
   ```

2. 如需重新添加或切换到 Stack 主题，可运行：

   ```powershell
   git submodule add https://github.com/CaiJimmy/hugo-theme-stack.git themes/Stack
   ```

3. 在 `config.toml` 中确认 `theme = 'Stack'`，然后执行 `hugo server` 验证本地预览。

> 主题仓库位于 `themes/Stack`，更新主题时只需进入该目录执行 `git pull`。


### 写作全流程脚本
在项目根目录执行 `.\scripts\start-writing.ps1` 可以一键启动完整的写作环境：

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
├── .obsidian/         # obsidian的设置，以及一些安装的插件。
├── content/           # 内容目录
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

1. 复制环境变量示例：`cp .env.example .env`（Windows 可使用 `Copy-Item`）
2. 填写 `.env` 中的：
   - `DEPLOY_REPO`：GitHub Pages 仓库地址
   - `DEPLOY_BRANCH`：用于部署的分支
   - `DEPLOY_DIR`：部署子模块目录（默认 `repo_to_deploy`）
3. 运行 `.\scripts\deploy.ps1`（`-Force` 跳过未提交更改提示，`-ForcePush` 即使没有新文件也会执行 `git push -f`）

部署脚本流程：

- 自动调用 `scripts/init-deploy-submodule.ps1` 将 `DEPLOY_DIR` 初始化为 git submodule（若尚未存在）
- 在部署目录中删除除 `.git` 以外的所有文件，确保不会携带旧产物
- 使用 `hugo --destination <DEPLOY_DIR>` 构建站点
- 在子模块中提交并推送到 `.env` 配置的仓库/分支

如果你更偏好手动流程，也可以直接执行 `hugo --destination repo_to_deploy`，然后在该目录内提交并推送；但推荐使用脚本以覆盖清理、构建与推送的全流程。

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

### 配置新主题
当需要尝试新的 Hugo 主题时，可以沿用以下流程：

1. **引入主题代码**  
   - 使用 Submodule：`git submodule add <theme_repo_url> themes/<ThemeName>`  
   - 或者直接将主题下载/复制到 `themes/<ThemeName>`。

2. **切换主题配置**  
   - 更新 `config.toml` 中的 `theme` 字段为新主题名。  
   - 按新主题文档补充必需的 `[params]`、菜单、自定义 CSS 等配置。

3. **迁移/合并配置**  
   - 参照 `themes/<ThemeName>/exampleSite/config.*` 调整本站配置。  
   - 若主题提供额外的短代码或布局，确认内容文件是否需要相应 Front Matter。

4. **验证与回滚**  
   - 运行 `hugo server -D` 检查本地显示是否正常（包含草稿）。  
   - 如需回滚，恢复 `config.toml` 中的 `theme` 字段并移除对应子模块：`git submodule deinit -f themes/<ThemeName>`、`git rm -f themes/<ThemeName>`。

## 参考资源

- [Hugo 官方文档](https://gohugo.io/documentation/)
- [Stack 主题文档](https://stack.jimmycai.com/)
- [Hugo 数学公式支持](https://gohugo.io/content-management/mathematics/)
