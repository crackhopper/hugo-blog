---
id: art_026abf2b4cfa3d4e8c0facc94a56951e
title: cpp中设置环境变量
date: 2025-11-21T12:56:25+08:00
tags:
  - system
  - process
  - boost
  - cpp
  - env
draft: true
---
这篇笔记还未整理
<!--more-->
## 正文开始

C++ 中，可以用 `cstdlib` 中的 `getenv` 设置环境变量。但是标准里没有 `putenv` 和 `setenv` 。而如果访问msdn的话
- https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/putenv-s-wputenv-s?view=msvc-170 （这里说明了c库中，putenv的代替实现；但还说明了，在UWP中，函数不可用。）
- boost里怎么做的呢？参见： 
	- https://github.com/boostorg/process/blob/2a41d0a0dcef77ff362c1e3a7cc88b47191ff9d2/src/detail/environment_win.cpp
	- https://github.com/boostorg/process/blob/2a41d0a0dcef77ff362c1e3a7cc88b47191ff9d2/include/boost/process/v2/detail/environment_win.hpp
- 关于阅读boost源码，需要掌握一定的泛型编程。（后续单独开一个帖子来展开）
	- SFINAE 技术
	- trait技术

那么boost的方式是否支持UWP呢？

AI回答：

**不允许。**

UWP（Universal Windows Platform）运行在沙盒环境中，对 Win32 API 有严格限制。**UWP 不允许修改当前进程或系统的环境变量**，无论是：

- `SetEnvironmentVariableW`
    
- `putenv_s / _wputenv_s`
    
- Win32 CRT 的 `_putenv`
    
- 甚至修改 `Environment` block
    

都无法在 UWP 中运行，因为：

### ✔️ 这些 API 在 UWP 中被归类为 **不允许的 Win32 API**

UWP 可用 API 列表中明确排除了该类功能。  
（你可以在 _Windows API contracts_ 里找到，只允许非常有限的 C runtime。）


# **可行替代方式**

## **1. AppData / LocalSettings 储存配置代替环境变量**

`auto localSettings = Windows::Storage::ApplicationData::Current->LocalSettings; localSettings->Values->Insert("Key", "Value");`

## **2. 把“环境变量”写入文件**

比如写入：

`%localappdata%\Packages\<PackageId>\LocalState\config.json`


总结：

在cpp中设置环境变量，最好的做法，还是stdlib.h + `_WIN32` 宏

```cpp
#include <cstdlib>

#ifdef _WIN32
    _putenv_s("MYVAR", "myvalue");   // 或者 _wputenv_s(L"MYVAR", L"myvalue")
#else
    setenv("MYVAR", "myvalue", 1);
#endif

```