---
title: Qt之图形
date: 2022-01-19T15:00:00+08:00
tags:
draft: true
---

## 二维图形部分

### QPainter
QPainter可以在widget上绘图。一般在paintEvent里进行绘制工作。有三个主要的设置：
- 画笔 QPen ： 用来画线和边缘。包含 颜色、宽度、线型、拐点风格(capStyle)和连接风格(joinStyle)。
- 画刷 QBrush ： 用来填充几何形状的图案。包含 颜色、风格、纹理、渐变。
- 字体 QFont ： 绘制文字，包含很多属性：字体族、磅值等等。
  - 字体大小的评估可以参见 `QFontMetricsF::boundingRect` 当需要计算布局的时候很有用。

QPainter具备一些图形功能：
- `setRenderHint` ： 可以开启一些图形功能，比如反走样。
- 几何形体绘制： `drawPoint` , `drawLine`, `drawPolyline`, `drawPoints`, `drawLines`, `drawPolygon`, `drawRect`, `drawRoundRect`, `drawEllipse` , `drawArc`, `drawChord`， `drawPie`, `drawPath`
  - `drawPath` : 对QPainterPath进行绘制。这个对象可以通过移动生成路径。移动方式还支持样条移动。
- 字体绘制： `drawText`
- 图像绘制： `drawPixmap`

此外QPainter还有一些方便的设置：
- 背景模式可以设置如何填充：透明、文字、纹理都支持
- 剪切区域：限定设备绘图区域。
- 视图、窗口和世界矩阵： 默认设定好跟物理坐标一致。
- 融合模式：可以启动alpha融合绘制。
- save/restore: 对状态进行压栈出栈。

不开启反走样，默认坐标+0.5作为像素坐标位置进行绘制。如果开启反走样则会在附近像素做渐变。

### QPainter坐标变换
`QTransform` 封装了二维空间的变换矩阵。支持常见的 `scale`, `rotate`, `translate`, `shear` 。这个类主要结合QPainter使用。做一些简单的变换。复杂的二维图形建议使用后面的 `QGraphicsView` （包含了场景坐标、视图坐标、和项坐标，可以更灵活的做变换以及局部显示）

### 使用QImage
直接在widget上绘图，取决与窗口系统后台的实现。更好的方法是用QImage，基于Qt的绘图引擎直接绘图。

先简要介绍alpha通道，这个一般表示颜色透明，假设一个透明颜色(a,r,g,b)，绘制在不透明区域上(1,ro,go,bo),那么最终的颜色为 (ar+(1-a)ro, ag+(1-a)go, ab+(1-a)bo)。a这里就是alpha通道，也称为透明度。

其次介绍 `预乘ARGB32` 。和 `普通ARGB32` (上面的颜色表达) 相比，提前把a乘进去，这样简化了合成时的计算量，加快了渲染速度。所以上面的颜色用预乘格式表达，即为 (a,ar,ag,ab) 。

### `QGraphicsView`的用法（场景和视图）
由 `QGraphicsScene` 充当场景（其实就是游戏里的world），场景内的物体用 `QGraphicsItem` 来表示（其实就是world里的待渲染对象）。视图可以基于场景，对场景进行变换，渲染。

`QGraphicsItem` 有几个预定义的子类： `QGraphicsLineItem` (以及各种几何图形的子类), `QGraphicsPixmapItem`, `QGraphicsSimpleTextItem` ，也可以创建自己的子类。还有一些方法：
- `setFlags` ： 可以设定是否能被选中，以及是否忽略变换（ItemIgnoreTransformations，通常一些文本会用这个标记）
- `setZValue` : 设定深度。越大越靠近用户。
- `QPainterPath QGraphicsItem::shape() const` ： 可重载，返回项的形状。用来做一些碰撞检测、点击检测等等。默认会使用 `QRectF QGraphicsItem::boundingRect() const` 作为形状，后者也可以重载。
- `void QGraphicsItem::paint(QPainter *painter, const QStyleOptionGraphicsItem *option, QWidget *widget = 0)` 纯虚函数，在局部坐标下进行绘制。这个函数主要是各个子类进行重载。
  - QStyleOptionGraphicsItem* 这个里面给除了绘制可以考虑的一些参数，比如levelOfDetails(可以加速渲染)
- `QVariant QGraphicsItem::itemChange(QGraphicsItem::GraphicsItemChange change, const QVariant &value)` 当自定义的item发生变化的时候，这个会发生改变。具体细节参看 [here](https://doc.qt.io/qt-5/qgraphicsitem.html#GraphicsItemChange-enum)

`QGraphicsScene` 是一个图形项的集合，有三层：背景层(background layer)，项层(item layer)和前景层(foreground layer)。背景层和前景层通常有QBrush指定，但也可以重新实现drawBackground()和drawForeground()。

场景可以告诉我们哪些项是重叠的，哪些是被选取的，以及哪些在特定的点/区域处。场景中的项自动形成一个树，所有对parent item的变换也会作用到item本身上。此外还提供 `QGraphicsItemGroup` ，把项聚合成一个组，可以方便的处理大量项，就像他们是一个单独项一样。

`QGraphicsView` 是一个窗口部件，这个窗口部件可以显示场景，以及影响场景绘制的方式。有利于支持缩放和旋转，帮助浏览场景。
- 默认情况下， `QGraphicsView` 使用Qt内置的二维图形引擎绘图，但这个也可以改变，调用 `setViewport` 改为使用OpenGL部件。
- `setScene` : 设定场景
- `setDragMode` : 可以设定是否框选、是否可以拖动滚动
- `selectedItems` ：获取被选中的项列表
- `scale` : 设定缩放因子

这套widget体系使用三个不同的坐标系
- 场景坐标 ： 逻辑坐标。
- 项坐标 ： 针对某一项，以(0,0)为中心。每个项都有(x,y)坐标和z值；pos会返回针对parent的相对位置。
- 视口坐标 ： 控制最终的渲染成像

### 打印
有专门的QPrinter类，步骤为：
1. 创建对象、弹出 `QPrintDialog` 用户选择打印机和设置
2. 在 `QPrinter` 上操作 `QPainter`
3. 使用 `QPainter` 绘制一页
4. 调用 `QPainter::newPage` 切换下一页
5. 重复上面的

打印不超过一页的项是非常简单的，但是很多应用程序通常都需要打印多页。对于这些情况，需要一次绘制一页并且调用 newPage() 来前进到下一页。这将会导致一个问题，也就是如何决定可以在一页上打印多少信息。在 Qt 中，有两种方式处理多页文档:
- 可以把数据转换为HTML，并且使用Qt的富文本引擎 QTextDocument 进行显示。（调用 `QTextDocument::print`）
- 可以执行绘制并且手动分页。自己计算消耗了多少空间，以及打印页面多大，手动控制。


## 三维图形部分