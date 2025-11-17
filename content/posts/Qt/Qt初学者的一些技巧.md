---
title: Qt初学者的一些技巧
date: 2022-01-18T14:29:34+08:00
tags:
draft: true
---

### 1.QtGui头文件
使用 `<QtGui>` 头文件可以避免一个一个的引入头文件

### 2.聚焦、快捷键和buddy
`setFocusPolicy(Qt::StrongFocus)` 可以让窗口部件通过单击或者通过按下 Tab 键而输入焦点。当获得焦点时，它将会接收由按键而产生的事件。

使用 `&` 可以创建用来聚焦的快键。

通过setBuddy方法，可以让聚焦转移到伙伴(buddy)上。

### 3.翻译标记tr
使用 `tr` 来包裹字符串，可以方便未来翻译。

### 4.合理使用伸展器(spacer)
spacer可以帮助用户布局，当resize的时候spacer会占据空间，从而造成了：向上对齐、向左对齐等等效果。

### 5.QWidget::sizeHint()函数
这个函数可以返回一个widget的“理想”尺寸。

### 6.MOC过程以及其他qt相关过程
对于qt自定义的关键字和宏，需要通过MOC来展开。目前cmake也支持对MOC过程自动处理。通过下面设置即可：
```cmake
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
```
其中MOC就是对源代码进行qt自定义展开，也叫做meta-object compiler；UIC则是转化布局文件(.ui)生成对应的布局头文件；RCC则是对qt定义的资源(.qrc)进行展开，转化为语言里的常量。

当然，也可以用相应的qt工具调用代码进行展开的动作；但利用cmake内置能力显然更加方便。

### 7.signal和slot
这里是qt设计的核心。signal其实就声明个函数签名就行了。slot需要有对应的函数定义，也就是动作。通过connect可以绑定signal和slot。这两个之间是多对多的关系，并且没有具体的执行顺序。 **注意：signal可以和signal连接**
- 如果需要顺序怎么办？定义新的signal，在slot里触发。
- 机制是如何的？没深入研究，猜测就是在MOC过程中，基于函数的签名进行注册。每个signal应该有关联的表。每个slot应该会注册到全局的表中。connect则是把slot关联到signal自己的表中，从而实现signal可以动态绑定slot并触发动作。

只要是QObject就可以充分的利用signal和slot的机制。

使用的时候注意不要导致无限循环，比如signalA->slotA(signalB)->slotB(signalA) ，这种可能比较隐蔽，但会导致不断调用。

如果想要深入研究，阅读QMetaObject文档

### 8.setupUi函数

这个函数不仅仅会对widget按照ui文件安置和布局相应的child widget，同时还会自动将符合 `on_objectName_signalName()` 命名惯例的任意槽与相应 objectName 的 signalName信号连接到一起。

### 9.QRegExp和QRegExpValidator

如名字所见，可以对input进行validate。用法是setValidator。

### 10.QObject内存管理
一般我们都用new来创建qt对象。只要创建对象的时候，指定parent，那么就由parent来管理内存。如果没有制定parent，那么需要注意自己手动释放内存。


### 11.(todo)clang code model相关问题
https://forum.qt.io/topic/95523/qt-creator-clang-code-model-doesn-t-find-types-even-though-code-compiles/9

### 12.gridlayout用法
其实可以拖动一个widget使它占用两个格子。体现在xml上就是item上多了个rowspan和colspan属性。

此外，所有的layout内部其实都是一个个的item，这个是布局作用的单位。

### 13.编辑taborder
单击Edit->Edit Tab Order，然后点击各个组合框就可以设定tab的顺序。

### 14.编辑signal和slot
单击Edit->Edit Signals/Slots，就可以通过UI上的拖拽来绑定信号和槽。

### 15.自定义窗体

常规步骤如下：
1. 使用Widget模板创建一个新窗体。
2. 利用编辑器，进行UI布局。
3. 连接信号和槽
4. 创建对应的文件：使用多重继承来实现一些功能（或者也可以用组合的方式：创建指针成员；在构造函数，创建ui的窗体，并调用ui的setupUi。）
   1. 通过 `Q_PROPERTY` 宏可以暴露一些属性给用户。
   2. 重载 `sizeHint` 提供一个更好的大小提示。
   3. QSizePolicy:minimum 告诉布局器， sizeHint已经是最小的尺寸了。
   4. `setAttribute(Qt::WA_StaticContents)` 这个告诉Qt内容是不变的，Qt只会对曾经未显示的区域进行repaint。

### 16.动态创建窗体

动态对话框 (dyn皿甘c dialog) 就是在程序运行时使用的从 Qt 设计师的.四文件创建而来的那些对话框。动态对话框不需要通过uic把.ui文件转换成 C++ 代码，相反，它是在程序运行的时候使用 QUiLoader 类载入该文件的，就像下面这种方式:
```cpp
QUiLoader uiLoader;
QFile file("xxx.ui");
QWidget* dialog = uiLoader.load(&file);
```
如果使用uiLoader，需要qt链接的时候加入uitools库。（BSD 3-Clause "New" or "Revised" License）

想要获取child widget，方式是用 `findChild<T*>("objectName")` 。

### 17.slot的返回值
当槽作为一个信号的响应函数而被执行时，就会忽略这个返回值;但是当把槽作为函数来调用时，其返回值对我们的作用就和调用任何一个普通的 C++ 函数时的作用是相同的。

### 18.菜单栏、QAction、ContextMenu、工具栏、状态栏
- 菜单栏：用designer可以轻易的创建菜单和关联的Action。此外可以用 `menuBar()->addMenu` 来创建和添加菜单。
- Action：可以直接 `new Action` ,designer也支持创建Action。此外可以通过 `setStatusTip` 来给Action添加状态栏提示。
- ContextMenu： 通过 `setContextMenuPolicy(Qt::ActionsContextMenu)` 可以实现通过Action创建上下文菜单。此外还有一个办法，通过实现 `QWidget::contextMenuEvent` 函数，在内创建QMenu对象，添加一些期望的动作，并对窗口调用exec函数。
- 工具栏：可以通过designer轻松创建，也可以手动 `addToolBar` 创建。
- 状态栏：通过 `statusBar()` 可以访问。

此外， `setWindowModified` 可以在窗口的标题上增加 `*` 表示文件被修改。同时也需要通过 `setWindowTitle(tr(%1[*]-%2))` 里面提供 `[*]` 标记来标志窗口内容是否发生了修改。

### 19.打开文件和保存文件
打开文件用 `QFileDialog::getOpenFileName` ， 如果显示失败也可以尝试切换成非native的模式，用 `QFileDialog::DontUseNativeDialog` 这个选项。

此外，打开文件前应该做判断，是否保存修改文件。这块别忘了。

读取也会有成功和失败，一般通过状态来做提示： `statusBar()->showMessage(tr("message"), 2000)`

保存文件用 `QFileDialog::getSaveFileName` ，这个函数本身会确认是否覆盖文件，以及是否取消保存。

此外，配合打开和保存，一般需要重载 `void closeEvent(QCloseEvent* event)` 防止没有保存就推出了程序。通过调用 `event->accept()` 接受关闭 或 `event->ignore()` 忽略关闭。

### 20.处理文件信息
`QFileInfo` 这个类型，可以提取文件信息；包括对路径处理。

### 21.模态(modal)和非模态
- 模态(modal)：用 `exec` 显示。对其他窗口block，也会阻塞函数执行。一般也在栈里直接创建变量使用。
- 非模态：用 `show` 显示（一般后续还跟 `raise` 和 `activateWindow` 调用），不会阻碍其他窗口工作

### 22.QSetting
这个会根据系统不同注册到不同的位置上。对于二进制的配置，比如一些widget的saveState和restoreState更加是和用QSetting。如果是文本，我觉得不妨用json库作为配置项（或者yaml）。

### 23.多文档

动态创建mainwindow，利用 `show` 来显示就能做到。为了防止主窗口被关闭导致退出，一般也会在堆上创建mainwindow。为了防止内存泄漏，在构造函数中调用 `setAttribute(Qt::WA_DeleteOnClose)` 来保证关闭的时候会自动释放资源。当所有窗口都关闭的时候，程序会自动退出。

此外，可以通过 `QApplication::topLevelWidgets()` 来访问所有创建的顶级窗口。一般用来同步一些全局变量的时候用到。

此外，如果要支持MDI风格，可以利用 `QMdiArea` 组件来实现。

### 24.启动画面

如果需要加载比较多的模块，那么可以在main中用 `QSplashScreen` 来创建过渡的启动画面。

### 25.触发信号
- 直接调用
- emit Signal()

### 26.序列化
- QDataStream : 由它们共同提供与平台元关的二进制数输人/输出接口。

### 27.在designer中引用自定义Widget
改进法（promotion）：简单，但不灵活
- 选择相似的UI，然后创建一下即可。会提示我们对应的类和文件。

插件法（plugin）：需要创建一个插件库
- 首先，必须对 `QDesignerCustomWidgetInterface` 进行子类化，并且需要实现一些虚函数。类定义如下：
  ```cpp
    #include <QDesìgnerCustomWidgetlnterface>
    class IconEditorPlugin : public QObject ,public QDesignerCustomWidgetlnterface{
        Q OBJECT
        Q_INTERFACES(QDesignerCustomWidgetlnterface)
    public:
        IconEditorPlugin(QObject *parent= 0);
        QString name() const;
        QString includeFile() const;
        QString group() const;
        QIcon icon() const;
        QString toolTip() const;
        QString whatsThis() const;
        bool isContainer() const;
        QWidget *createWidget(QWidget *parent);
    }
  ```  
  - 这个子类是一个工厂类，生产自定义的Widget
  - name：返回插件名字。
  - includeFile: 返回插件头文件名字。
  - group : 返回插件注册到哪个组下。
  - icon ： 返回插件的图标文件。
  - toolTip : 返回工具提示信息。
  - whatsThis : 返回whatsThis中需要的文本
  - isContainer ： 返回是否是container。
  - createWidget ： 工厂函数
  - 源文件的末尾需要增加 `Q_EXPORT_PLUGIN2(xxx,xxx)` 注册插件名字和类名字

此外，对于cmake组织的项目来说，参见：https://bugreports.qt.io/browse/QTBUG-51900

### 28.调色板
两个基本概念：ColorGroup和ColorRole

ColorGroup有一下三组，Widget会根据自己的状态选择对应的ColorGroup
- 激活组（Active）：可用于当前激活窗口中的部件 
- 非激活组（Inactive）：可用于其他窗口中的部件 
- 不可用组（Disabled）：可用于任意窗口中不可用部件

确定ColorGroup后，Widget会根据要绘制的区域选择ColorRole。ColorRole比较细节：

主要的有：（以下枚举均在 `QPalette::` 下）
- Window/Background : 背景色
- WindowText/Foreground : 前景色
- BrighterText : 更加有区分的前景色
- Base : 类似背景色，在特殊控件上表现不一样
- Text : 和Base一对，类似前景色
- AlternateBase : 需要交替颜色的背景的时候用到
- ToolTipBase : 提示窗口的背景色
- ToolTipText : 提示窗口的前景色
- Button ： 按钮的背景色
- ButtonText ： 按钮的前景色

此外还有一些颜色是用于3D和阴影的（以下枚举均在 `QPalette::` 下）
- Light ： 比Button更亮的颜色
- MidLight ： 介于Button和Light的颜色
- Dark ： 比Button更暗的颜色
- Mid ： 介于Button和Dark之间的颜色
- Shadow ： 非常暗的颜色

选中的文本有两个ColorRole（以下枚举均在 `QPalette::` 下）
- Highlight ： 选中区域的背景色
- HighlightedText : 选中区域的前景色

超链接也有两个ColorRole（以下枚举均在 `QPalette::` 下）
- Link ： 未访问的链接
- LinkVisited ： 访问过的链接

对于调色板，我们可以设定对应ColorGroup和ColorRold下的笔刷和颜色：
- `void QPalette::setBrush ( ColorRole role, const QBrush & brush )` ：改变所有组下指定角色role的画刷颜色值。
- `void QPalette::setBrush ( ColorGroup group, ColorRole role, const QBrush & brush )` ：改变指定组group下的指定角色role的画刷颜色值。
- `void QPalette::setColor ( ColorRole role, const QColor & color )` ：改变所有组下指定角色role的颜色值。
- `void QPalette::setColor ( ColorGroup group, ColorRole role, const QColor & color )` ：改变指定组group下指定角色role的颜色值。

注意：在以上代码之前，必须先调用函数 `setAutoFillBackground(true)`，设置窗体运行自动填充。


### 29.绘制类
- QStylePainter ： 扩展了QPainter，可以画 QStyle 元素
  - drawPixmap : 绘制pixmap
- QPainter ： 用来画线的类
  - setPen : 设定笔刷

### 30.常见事件
- QWidget::update() 会强制触发重绘，下一个tick。（可以传入QRect来局部绘制）
- QWidget::repaint() 会强制触发重绘，立即。
- QWidget::updateGeometry() 告诉上层layout，这个控件的sizeHint已经修改，需要重新布局。
- paintEvent : 绘制时调用的函数.
  - 调用机会：
    - 第一次显示时
    - 重新调整窗口大小时
    - 被其他窗口遮挡时
- mouseMoveEvent : 鼠标按键后移动触发，如果setMouseTracking了，那么会一直触发
  - 通过 `event->buttons()& Qt::LeftButton` 可以判断鼠标左键是否按下。右键同理。
- mousePressEvent/mouseReleaseEvent : 同上，只不过是鼠标 按键/释放 时触发
- keyPressEvent : 按键事件，需要focus， 通过 `event->key()` 可以按键值
- wheelEvent : 滚轮事件，需要focus， 通过 `event->delta()` 可以获取滚动的大小（一般是滚动角度的8倍，且单位滚动一般是15度）

### 30.布局相关
- `adjustSize()` 调整到content大小，利用了sizeHint的信息（如果可用）

### 31.画笔Pen
这个对象定义了QPainter如何进行绘制。QPainter只是定义了绘制的指令，但不关心绘制的细节（颜色、风格等等），这些由QPen定义。

画笔Pen包含5个主要属性：
- `width()` : 画笔宽度
- `style()` : 指定了轮廓的线的风格
- `brush()` : 指定了轮廓内的填充方式（颜色和风格），包含以下4个部分
  - `QBrush::style()` : 填充风格
  - `QBrush::color()` : 填充颜色
  - `QBrush::gradient()` : 渐变方式，需要配合风格使用
  - `QBrush::texture()` : 如果风格是 `Qt::TexturePattern` 则可以用纹理作为填充
- `capStyle()` : 拐点风格，线终止处的画法
- `joinStyle()` ： 连接风格，线交汇处的画法

关于笔Pen、笔刷Brush、和颜色。笔和笔刷包含了颜色，且包含一种绘制的方式，比如是实心填充、还是网格填充。笔主要负责轮廓的绘制，笔刷负责内容的填充。

### 32.风格QStyle
这个类可以模仿各个平台显示的风格效果。此外Styles也可以最为插件植入到Qt中。

所有Qt内置的Widget都会符合一个QStyle，在不同平台构建的时候会自动适配到平台外观上。也可以在命令行传入参数来指定风格。

如果自定义Widget需要注意平台风格的话，那么可以采用`QStyle draw functions` ，比如 `drawItemText()` , `drawItemPixmap()` , `drawPrimitive()` , `drawControl()` , 和 `drawComplexControl()` 。通常调用这些函数需要4个参数：
- 枚举值：标注需要绘制的图形元素
- QStyleOption： 制定如何以及在哪里进行渲染
- QPainter ： 执行绘制动作的对象
- QWidget ： 在哪个Widget上执行 (optional)

为了方便，Qt也提供了QStylePainter这个类帮忙绘制Widget。