---
title: WinDbg的初级用法
date: 2025-11-17T22:05:20+08:00
tags:
  - windbg
  - 二进制
  - 调试
draft: false
---
起因开始于 [记录调试Vulkan程序打印奇怪日志的问题]({{< relref "posts/Vulkan/记录调试Vulkan程序打印奇怪日志的问题.md" >}})


<!--more-->
# 正文开始
## 简要介绍
**WinDbg**（Windows Debugger）是 Microsoft 提供的强大调试工具，广泛应用于 Windows 系统的内核调试、用户模式调试、崩溃转储分析等场景。它适用于调试应用程序、驱动程序、操作系统内核等各种不同类型的程序。WinDbg 支持命令行界面，并且具有图形用户界面（WinDbg Preview），它能够帮助开发人员和系统管理员诊断并修复系统崩溃或程序错误。

## 安装与启动 WinDbg
参考文档： https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/

简单来说：
```ps
winget install Microsoft.WinDbg
```

用windows的包管理器下载即可。（类似苹果的HomeBrew，windows下我一般除了 winget，还会用到 chocolate 和 scoop）

