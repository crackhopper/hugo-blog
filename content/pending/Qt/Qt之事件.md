---
id: art_e868820828e2cac4cffab0af3cacd45f
title: Qt之事件
date: 2022-01-20T21:45:42+08:00
tags:
draft: true
---

## 1.基本概念

当我们自定义窗口部件，需要改变窗口行为的时候，就需要了解事件并重定义一些事件。

在Qt中，事件就是QEvent子类的一个实例。Qt处理的事件类型有一百多种，其中的每一种都可以通过一个枚举值来进行识别。例如， `QEvent::type()` 可以返回用于处理鼠标按键事件的 `QEvent::MouseButtonPress` 。

事件通过它们的 `event()` 函数来通知对象。在 `QWidget` 中的 `event()` 把绝大多数常用类型的事件提前传递给特定的事件处理器，比如 `mousePressEvent()`, `keyPressEvent()` 以及 `paintEvent()`。通过重载 `event()` 函数，可以自定义消息的处理，比如对tab键特殊处理，只要返回true那么就通知了Qt事件处理完毕，如果返回false则事件将会传递给父窗口处理（类似bubble up）

实现键绑定的一种更为高级的办法是使用 `QAction` ，利用 `setShortcut` 来绑定快键。同时可以把 `activated()` 信号和相应的槽绑定。如果只是快键，没有界面，还可以用 `QShortcut` 对象，`QAction` 对象内部也存在这个对象。一般情况下，一旦包含 `QAction` 窗口（包括递归包含）激活就可以启用绑定键，可以用 `QAction::setShortcutContext` 或 `QShortcut::setContext` 改变这个行为。

## 2.常见事件处理
### 2.0 消息处理流程细节
从源码来看：
- 消息分发首先从 `QtWndProc` 这种注册到系统的窗口回调开始。在回调内会获取到qt的widget，然后对消息进行一定的处理，比如 `QETWidget::translateMouseEvent`
- `QETWidget::translateMouseEvent` 主要是翻译事件到Qt的格式，然后调用 `QApplicationPrivate::sendMouseEvent`
- `QApplicationPrivate::sendMouseEvent` 根据消息的来源做个区分 `spontaneous` 或 `non-spontaneous` ，进行转发，调用 `QApplication::sendSpontaneousEvent` 或 `QApplication::sendEvent` 。
- `QApplication::sendSpontaneousEvent` 内部调用 `QCoreApplication::notifyInternal`
- `QCoreApplication::notifyInternal` 内部做script处理和线程处理，然后调用 `QCoreApplication::nofity`

`QCoreApplication::nofity` 是核心分发逻辑的函数，它会根据消息类型做一系列处理，并分发到对应的widget，通过 `QApplicationPrivate::notify_helper` 再里面再通过 `receiver->event` 进行转发。
- 注意： `QApplicationPrivate::notify_helper` 内部会把消息先传递给widget关联的layout处理，因此layout处理更加优先。

最后，消息被分发到每个widget的 `bool event(QEvent *event)` 函数中。这个函数在QWidget中做了详细实现，将消息转发到 paintEvent, resizeEvent, mouseMoveEvent 等等虚函数中。这个函数也是用户可以重载的函数，通过 `event->type()` 来判定消息类型，做自定义处理；如果不是要处理的类型，就调基类的函数来做默认处理。

具体细节可以参见： （windows平台下）
- https://www.51cto.com/article/272812.html
- https://www.51cto.com/article/272816.html

### 2.1 paintEvent
`void QWidget::paintEvent(QPaintEvent *event)` ， 请求对局部或全部区域进行repaint，这个消息会由下面调用触发：
- `repaint` ： 立即重绘
- `update` ： 下一个tick重绘，同时可以多个调用合并（ `QRegion::united()` ），应尽可能使用这个函数
- 被遮挡之后重新显示。

很多widget可以重绘整个表面，但也可以通过 `QPaintEvent::region()` 来进行部分重绘。

当这个事件触发时，区域已经被背景色清空过了。此外，DoubleBuffer默认是启动的，因此不用手动创建双缓冲来避免闪烁了。

### 2.2 show/hideEvent
`void QWidget::showEvent(QShowEvent *event)` ， 显示的时候会触发这个事件。`void QWidget::hideEvent(QHideEvent *event)`，隐藏的时候出发。有两个种类的Event:
- 自发的(spontaneous) : 由底层窗口系统触发的，在动作发生(窗口已经显示)之后。
- 非自发的(non-spontaneous) : 内部的，在动作发生（窗口还没显示）之前。

注意：当底层窗口系统发生变化，widget才接受自发消息。比如，由用户最小化窗口产生的自发的隐藏消息。而在接受到自发消息后，widget其实仍然是"短暂"可见的（在 `isVisible` 的含义下，实际肉眼看不出）

### 2.3 resizeEvent
`void QWidget::resizeEvent(QResizeEvent *event)` ，当窗口大小发生变化的时候会触发这个事件。注意前面分析的流程，消息会首先被layout处理，然后才会被resize处理。因此此时已经拿到了layout调整过的尺寸。但反过来是不成立的，即被layout处理过的消息，变更了size不一定会调用resize进行处理。

因此，如果窗口还被布局管理。那么想要实现正确的效果需要既处理 `resizeEvent` ， 也要在event函数中处理 `QEvent::LayoutRequest` 消息。

### 2.4 moveEvent
`void QWidget::moveEvent(QMoveEvent *event)` 当widget移动的时候触发这个消息。并且此时窗口已经移动过了，可以通过 `QMoveEvent::oldPos()` 来获取旧位置。

### 2.5 closeEvent
`void QWidget::closeEvent(QCloseEvent *event)` 当最外层关闭按钮被点击的时候触发。默认这个event会被accept从而widget被关闭。但很多时候，比如我们要在关闭前确认保存，那么就要重写这个事件。比如：
```cpp
void MainWindow::closeEvent(QCloseEvent *event)
{
    if (maybeSave()) {
        writeSettings();
        event->accept();
    } else {
        event->ignore();
    }
}
```

### 2.6 鼠标Event
doubleclick
- `void QWidget::mouseDoubleClickEvent(QMouseEvent *event)` : 注意，即使响应了这个事件，普通点击和释放的事件也会被触发。

press/release
- `void QWidget::mousePressEvent(QMouseEvent *event)`
- `void QWidget::mouseReleaseEvent(QMouseEvent *event)`

move
- `void QWidget::mouseMoveEvent(QMouseEvent *event)` ： 按键后鼠标移动事件（开启mouse tracking后，可以检测所有移动事件）。注意，如果想要即时响应tooltip，需要打开mouse tracking属性，并且使用 `QToolTip::showText` 来快速显示，而不是使用 `setToolTip` 函数。

leave/enter
- `void QWidget::enterEvent(QEvent *event)`
- `void QWidget::leaveEvent(QEvent *event)`

drag相关 （参见： https://doc.qt.io/qt-5/qdragenterevent.html）
- `void QWidget::dragEnterEvent(QDragEnterEvent *event)` ： 当处于drag-in-rogress时，（比如从外部拖动文件），鼠标进入widget的时候触发这个动作。如果这个被忽略了，那么dragmove也不会继续接收。
- `void QWidget::dropEvent(QDropEvent *event)` : 当处于drag-in-rogress时，抬起鼠标触发drop
- `void QWidget::dragLeaveEvent(QDragLeaveEvent *event)` ： 当处于drag-in-rogress时，鼠标离开widget时触发的动作。
- `void QWidget::dragMoveEvent(QDragMoveEvent *event)` ： 当处于drag-in-rogress时，下面情况都会触发：
  - 鼠标进入widget时
  - 鼠标移动
  - 修饰键(modifiers)被按下且当前widget有focus。

一般头两个函数重载就够用了。如果要使拖放生效，需要调用 `setAcceptDrops(true)`。随后通过 `event->mimeData()->hasFormat("text/uri-list")` 可以判断数据格式，调用 `event->acceptPropsedAction()` 则表明用户可以拖放对象。通过 `event->mimeData()->urls()` 可以获取文件资源位置 （url需要再调用一次toLocalFile转化为路径）

对于拖动widget对象则需要更多的处理：创建QMimeData对象和QDrag对象，通过drag->exec来启动拖拽。此外，我们也可以自定义拖放，方式是对QMimeData定制化，有3个办法：a.用setData+自定义序列化（有性能缺点）；b.子类化QMimeData并重新实现formats和retrieveData;c. 直接子类化添加我们的数据结构。

其他事件相关函数
- `void QWidget::grabMouse()` ： widget会接收所有的鼠标事件，直到鼠标被释放。（注意这个动作会对terminal锁定，导致log异常）。通常来说Qt会自己适当的处理grab，不用我们操心（通常来说按键按下的时候grab到按键抬起）。
- `QWidget *QWidget::mouseGrabber()` 这个静态函数会返回被grab的widget。
- `event->buttons()` : 反映鼠标按键状态。是一个bit flag。
- `event->globalPos()` : 如果需要resize或move，建议用globalPos
- `event->pos()` : 相对于widget的位置

### 2.7 键盘Event
press/release
- `void QWidget::keyPressEvent(QKeyEvent *event)` : 注意必须要有focus才能接受这个事件。默认的实现会用escape键关闭popup的widget。
- `void QWidget::keyReleaseEvent(QKeyEvent *event)` : 注意必须要有focus才能接受这个事件。
  
其他
- `void QWidget::grabKeyboard()` ： widget会接收所有的键盘事件，直到按键被释放。
- `focusPolicy : Qt::FocusPolicy` ： 这个属性决定了widget是否能接受键盘消息。
### 2.8 actionEvent
`void QWidget::actionEvent(QActionEvent *event)` 当widget管理的action发生变更的时候会触发这个动作。比如 `addAction()` ， `insertAction()` 等等。。

### 2.9 contextMenuEvent
`void QWidget::contextMenuEvent(QContextMenuEvent *event)` 这个主要相应上下文菜单事件。同时需要定义 `contextMenuPolicy` 。默认是忽略这类事件的。

### 2.10 changeEvent
`void QWidget::changeEvent(QEvent *event)` 窗口状态变更的时候触发，包含：
- QEvent::ToolBarChange
- QEvent::ActivationChange
- QEvent::EnabledChange
- QEvent::FontChange
- QEvent::StyleChange
- QEvent::PaletteChange
- QEvent::WindowTitleChange
- QEvent::IconTextChange
- QEvent::ModifiedChange
- QEvent::MouseTrackingChange
- QEvent::ParentChange
- QEvent::WindowStateChange
- QEvent::LanguageChange
- QEvent::LocaleChange
- QEvent::LayoutDirectionChange
- QEvent::ReadOnlyChange.


### 2.11 其他

**timerEvent**
`void QObject::timerEvent(QTimerEvent *event)` 这个是定义在QObject上的消息。

**窗口原生消息**
`bool QWidget::nativeEvent(const QByteArray &eventType, void *message, long *result)`

一般用的也不多，通过 eventType 的标记可以区分底层系统。通过返回true来防止Qt继续消费消息。

## 3.事件过滤器
Qt事件模型一个非常强大的功能是: QObject 实例在看到它自己的事件之前，可以通过设置另外一个 QObject 实例先监视这些事件。
- `installEventFilter` 来注册监视对象。
- 在监视对象的 `bool eventFilter(QObject*, Event*)` 中，处理过滤。如果是返回true代表处理了事件，就不用后续处理了。
 
不要忘记调用基类方法做默认处理，一般这个方法也会实现在parent widget中；也可以在QApplication中安装事件过滤器，这样会影响整个程序的运行，对调试的帮助更大。

此外，还有一个威力更大的办法，就是重载QApplication的 `nofity` 函数。

最后，Qt的UI线程的模型也是EventLoop，因此处理事件的时候要注意时间开销，以免造成页面卡顿。如果想要自定义循环，可以考虑用计时器。

## 4.剪切板处理技术
通过 `QApplication::clipboard()` 可以获取剪切板 `QClipBoard` 对象。内置的很多widget都支持序列化到剪切板以及反序列化回对象。

如果想要更加自由，那么也是通过 QMimeData 来扩展功能，用其来进行序列化和反序列化动作。
