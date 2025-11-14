---
title: Qt之layout
date: 2022-01-18T13:13:21+08:00
tags:
draft: false
---

### 1.布局初步
Qt的layout含义是布局，主要功能是：定义了当有更多空间时，widget应该怎么适应。所有的QWidget的子类都可以用layout来管理child widget。调用 QWidget::setLayout 函数就可以设置layout，同时也会进行下面的任务：
- 对child widget进行定位
- 合理的默认size
- 合理的最小size
- 对resize消息进行处理
- 当内容发生改变时，自动更新。比如：
  - 字体、文本、或者child widget的其他内容变更
  - 对child widget的显示或隐藏
  - 对child widget的删除

主要的Layout类
- QHBoxLayout ： 水平布局
- QVBoxLayout ： 垂直布局
- QFormLayout ： 用来管理表单布局
- QGridLayout ： 网格布局

布局会根据QSizePolicy来调整大小
- Fixed ： 该窗口部件不能被拉伸或者压缩。窗口部件的大小尺寸总是保持为其QSizeHint的尺寸。
- Minimum ： 该窗口部件不能被压缩。窗口部件的大小尺寸最小为其QSizeHint的尺寸。
- Minimum ： 该窗口部件不能被拉伸。窗口部件的大小尺寸最大为其QSizeHint的尺寸。
- Preferred ： 该窗口部件的大小提示就是它比较合适的大小。但是如果需要，还是可以对该窗口部件进行拉伸或者压缩。
- Expanding ： 以拉伸或者压缩该窗口部件，并且它特别希望能够变长变高。

Preferred和Expanding的区别：当两个都有的时候，多余的空间会被Expanding占据，即Expanding会抢夺Preferred的空间。

此外还有：MinimumExpanding，这个deprecated。以及 Ignored，与Expanding类似，但是会忽略窗口部件的大小提示和大小限制。

此外，SizePolicy还可以设定两个方向上的拉伸因子（即当有多余空间时，如何分配）

### 2.QStackedLayout

QStackedLayout类可以对一组子窗口部件进行摆放，或者对它们进行"分页"，而且一次只显示其中一个，而把其他的子窗口部件或者分页都隐藏起来。 QStackedLayout 本身并不可见，并且对于用户改变分页也没有提供其他特有的方法。

为方便起见，Qt还提供了QStackedWidget类，这个类提供了一个带内置QStackedLayout的QWidget。

分页从0开始，通过 `setCurrentIndex` 以及 `indexOf` 可以设置和获取child widget的页号。

常见的用法：左侧QListWidget，右侧QStackedLayout；同时关联列表选中信号到切换页面信号： `connect(listWidget, SIGNAL(currentRowChanged(int)), stackedLayout, SLOT(setCurrentIndex(int)))`

对于页数更少的情况，更简单的方式是用QTabWidget

### 3.QSplitter

在designer中，通过多选widget就可以在工具栏选择QSplitter对widget进行布局管理。

QSplitter是个widget并不是layout，但这个对象支持拖拽来resize，非常方便。

- `setStretchFactor` 可以设定每个child widget的伸展因子。
- `setSizes` 可以移动切分条
- `saveState/restoreState` 可以对切分条等等状态进行序列化和反序列化。

### 4.QScrollArea

QScrollArea 类提供了一个可以滚动的视口和两个滚动条。如果想给一个窗口部件添加一个被动条，则可以使用一个QScrollArea 类来实现，这可能要比我们自己通过初始化 QScrollBar，然后再实现它的滚动等功能简单得多。

- `setWidget` 设定需要scroll的widget
- `viewport` 访问被scroll的widget

原理上， QScrollArea 会以Widget的当前大小来显示它。通过调用 `setWidgetResizable(true)` 可以告诉 QScrollArea 要自动重新改变widget大小，利用任何多余空间。

- `setVertical/HorizontalScrollBarPolicy` : 可以控制垂直或水平滚动条的显示策略

### 5.QDockWidget

可以浮动或者停靠的窗口。工具栏如果需要这个能力，可以创建QDockWidget，把工具栏放入其中。（但是designer不支持这个动作，修改xml再reload是可以的）

- `setAllowedAreas` : 控制停靠窗口的行为
- `setCorner` : 更具体的，停靠在一边的时候是更靠近哪个角
- `setWidget` : 设定内部的widget
- `saveState/restoreState` 可以对dock状态进行序列化和反序列化。

### 6.QMdiArea

这个组件主要提供多文档页面的功能。在 Qt 中，通过把 QMdiArea 类作为中央窗口部件，并且通过让每一个文挡窗口都成为这个 QMdiArea 的子窗口部件，就可以创建一个多文档界面应用程序了。（在designer中，通过选中后右键来增加subwindow，显示是QWidget，实际是 QMdiSubWindow 里包含了QWidget作为子widget。）

- `addSubWindow` : 创建子窗口，返回 `QMdiSubWindow*`
- signal:`subWindowActivated(QMdiSubWindow*)` ： 当子窗口激活时触发。
- property:`viewMode` : 可以设置为窗口模式或者tab页模式。

closeEvent注意事项：
- 需要调用 `closeAllSubWindows` 来关闭QMdiArea里面的窗口。
- 如果有没有关闭的窗口（比如用户取消保存，通过 `subWindowList().isEmpty()` 判断），那么取消关闭。注意：subwindow也应该实现对应的closeEvent。此外subwindow最好设定 `setAttribute(Qt::WA_DeleteOnClose)`

### 7.QGraphicsAnchorLayout

QGraphicsAnchorLayout 类提供了Graphics View中 widget 互相 anchor 的布局能力，我们称呼其为锚定布局。（注意，能被管理的widget必须是 `QGraphicsLayoutItem` 的子类，比如 `QGraphicsView` ；或者使用 `QGraphicsProxyWidget` 通过 `QGraphicsScene` 对 widget 进行代理； `QGraphicsView` 需要显示的时候一般也会addScene）

锚定布局允许开发者制定一个 widget 相对于另一个 widget 如何布局。主要提供下面函数的能力：
- addAnchor() ： 添加一个锚定关系
- addAnchors() ： 垂直、水平锚定，或大小锚定
- addCornerAnchors() ： 添加角的锚定关系。
- anchor() ： 返回布局中的anchor

被 anchor 的 `项` 会自动添加到 layout 中，如果一个 `项` 是 anchor 且被删除，那么所有 anchor 在该 `项` 上的widget都会被自动删除。

考虑下面这个例子：
```cpp
layout->addAnchor(b, Qt::AnchorLeft, a, Qt::AnchorRight);
layout->addAnchor(b, Qt::AnchorTop, a, Qt::AnchorBottom);
```

这里， `a` 的右侧边被锚定到 `b` 的左侧边上， 且 `a` 的下侧边被锚定到 `b` 的上侧边上。于是 `a` 和 `b` 将在对角线上排列。使用 `addCornerAnchors` 则会提供更加便捷的方式，简化两步调用为一步：
```cpp
layout->addCornerAnchors(a, Qt::TopLeftCorner, layout, Qt::TopLeftCorner);
```

如果布局时想要大小一致，或者左右测对对齐，考虑使用 `addAnchors`

例子： http://man.hubwiz.com/docset/Qt_5.docset/Contents/Resources/Documents/doc.qt.io/qt-5/qtwidgets-graphicsview-simpleanchorlayout-example.html


相对位置的设定

利用 QGraphicsAnchor 调用setSpacing来达到