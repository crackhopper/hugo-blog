---
id: art_16fbf071b33a44825309fe3f27c1789c
title: Qt之QTableWidget
date: 2022-01-18T21:06:22+08:00
tags:
draft: true
---

### 1.自定义Item类型
通常情况下，当用户在一个空单元格中输人一些文本的时候， QTableWidget将会自动创建一个QTableWidgetItem来保存这些文本。如果我们想要利用自定义的类代替它，那么需要在构造函数中调用 `setItemPrototype` 函数。实际上，QTableWidget会在每次需要新项的时候，用我们传入的对象作为原型进行克隆。
```cpp
setItemPrototype(new Cell)
```

### 2.允许矩形选择

```cpp
setSelectionMode(ContiguousSelection)
```

### 3.QTableWidget组成
- 顶部有个水平的 `QHeaderView` ,通过 `horizontalHeader()` 访问
- 左侧有个垂直的 `QHeaderView` ，通过 `verticalHeader()` 访问
- 右侧有个垂直的 `QScrollBar` ，通过 `verticalScrollBar()` 访问
- 下侧有个水平的 `QScrollBar` ，通过 `horizontalScrollBar()` 访问
- 中间可以通过 `viewport()` 访问，QTableWidget在上面绘制单元格
- 通过 `item(row, column)` 可以返回QTableWidgetItem指针。
- 通过 `item->setDirty()` 可以通知QTableWidget重新获取text进行渲染。

通过从QTableView和QAbstractScrollArea中继承的一些函数，可以访问不同的子窗口部件。


