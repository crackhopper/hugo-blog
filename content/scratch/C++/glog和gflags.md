---
title: 那些年踩过的坑--glog with gflags
date: 2022-01-12T18:28:55+08:00
tags:
draft: true
---

注意，如果编译新项目的时候，引用老项目的文件；比如构建原项目的单元测试：
- 文件里间接使用了glog会导致链接之后运行找不到gflags，因为gflags的rpath没有链接进去（因为没有符号依赖，然而glog内部实际需要gflags，这就导致了运行时找不到gflags.so）。

解决办法：在main的时候再次重新初始化glog和gflags。