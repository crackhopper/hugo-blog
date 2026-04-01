---
title: Cook-Torrance BRDF
date: 2026-04-01T12:53:19+08:00
draft: true
---

# 核心思想
## 微表面理论（Microfacet Theory）

现实中的表面并不是光滑的，而是由大量微小的镜面片（microfacets）组成：
- 每个微表面都是理想镜面（perfect mirror）
- 表面粗糙度 = 微表面法线分布的离散程度
- 只有**法线刚好满足反射条件的微表面**会贡献反射

![[Cook-Torrance BRDF-1774585998381.png]]


常用变量


![[Cook-Torrance BRDF-1774585986437.png]]


![[Cook-Torrance BRDF-1774585964203.png]]