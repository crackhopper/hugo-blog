---
id: art_42975218b57ac95c0eb80df90fe02325
title: Kalfka一些知识的总结01
date: 2025-12-01T11:06:54+08:00
tags:
  - kafka
  - zookeeper
  - proto
  - buf
draft: true
---
- `kafka` 基础原理
- `kafka` 配置多IP访问
- `zookeeper` 
	- 介绍
	- 数据存储
	- leader选举
- kafka写入protobuf:
	- 优缺点
	- 可视化问题
		- schema registry：原理，以及为什么不用它
	- 暂定解决方案：
		- 自己开发一个非侵入式protobuf的schema管理和可视化工具：BufView


<!--more-->
# 多

