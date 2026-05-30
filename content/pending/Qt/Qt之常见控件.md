---
id: art_d0f938feef634a6cae339d0778cfaec8
title: Qt之常见控件
tags:
draft: true
---

## 项视图类 （QListView、 QTableView 和 QTreeView）

类似MVC，Qt提供了Model（模型）,View（视图）,Delegate（委托）的模型。委托对如何显示和如何编辑提供精细控制。Qt会对多个视图会自动同步。

项视图类（View）提供对应的项（属于Model）。此外模型还可以进一步的连接数据库。

**QListWidget**
- 通过 `listWidget->currentItem()` 可以获取当前选中的项

数据层显示用 QListWidgetItem 。QListWidgetItem 有几个角色(role) ，每一个角色都有一个关联的 QVariant 。最常用的角色有 `Qt::DisplayRole` , `Qt::EditRole` , `Qt::IconRole` ，可以通过 `setData(Qt::UserRole, var)` 存储信息。

**QTableWidget**
- 顶部有个水平的 `QHeaderView` ,通过 `horizontalHeader()` 访问
- 左侧有个垂直的 `QHeaderView` ，通过 `verticalHeader()` 访问
- 右侧有个垂直的 `QScrollBar` ，通过 `verticalScrollBar()` 访问
- 下侧有个水平的 `QScrollBar` ，通过 `horizontalScrollBar()` 访问
- 中间可以通过 `viewport()` 访问，QTableWidget在上面绘制单元格
- 通过 `table->setSelectionMode(ContiguousSelection)` 可以开启矩形框选择
- 通过 `table->setItemPrototype(new Cell)` 可以设定Item创建原型，相当与自定义Item。
- 通过 `table->setEditTriggers( QAstråctItemView: NoEditTriggers` 可以禁止编辑。

数据操作
- 通过 `table->insertRow(row)` 可以插入一行。
- 通过 `table->item(row, column)` 可以返回QTableWidgetItem指针。
- 通过 `table->setItem(row, column, item)` 可以设置QTableWidgetItem对象。
- 通过 `table->setCurrentItem(item)` 可以设置QTableWidgetItem被选中。
- 通过 `table->item->setDirty()` 可以通知QTableWidget重新获取text进行渲染。
