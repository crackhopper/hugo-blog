---
title: Task - go项目构建工具
date: 2025-12-01T10:54:37+08:00
tags:
  - build
  - go
  - go-task
  - makefile
draft: true
---
很多go项目都用 Makefile来组织项目构建。更现代化一些的，使用 `Taskfile.yaml` 。两者都有各自的优势。本文主要讲解基于 `Taskfile.yaml` 的项目组织。也会在开头简要讲一些 `makefile` 的用法(相对来说，语法晦涩、windows下需要额外配置、调试困难；但对简单项目来说，更容易匹配置；我们只介绍最简单基础的用法)。
<!--more-->
## 正文开始
## `Makefile` 和 `GNUMake` 工具
