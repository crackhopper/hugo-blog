---
id: art_93a5daf99e65963632022a15ffa75eb1
title: SDL入门
date: 2025-12-22T19:42:32+08:00
tags:
  - sdl
  - vulkan
draft: false
---

![[SDL入门-intro-01.png]]

SDL (Simple DirectMedia Layer) 是一个非常经典且强大的跨平台开发库，主要用于通过 C/C++ 提供对音频、键盘、鼠标、摇杆以及图形硬件（通过 OpenGL 或 Direct3D）的低级访问。

我们的AI Native渲染器项目（LXEngine），背后使用的窗口系统和输入输出系统，会直接使用SDL库。

<!--more-->

# 入门
## SDL2 v.s. SDL3

|**特性**|**SDL2 (2013年)**|**SDL3 (2024年)**|
|---|---|---|
|**头文件包含**|`#include <SDL.h>`|`#include <SDL3/SDL.h>`|
|**构建系统**|支持 Autotools, CMake 等多种|**仅限 CMake** (更加现代和统一)|
|**C 语言标准**|C89|**C99** (代码风格更现代化)|
|**二进制兼容**|SDL2 各版本间保持兼容|**不兼容 SDL2** (这意味着你需要重新编译代码)|
|**API 命名**|存在部分历史遗留的不规范命名|**重新整理**，命名更加统一、规范|

SDL3 不仅仅是修复 Bug，它引入了许多开发者期待已久的功能：

- **GPU API (核心升级)：** SDL3 引入了跨平台的 GPU 抽象层，允许直接访问 3D 渲染和 **GPU 计算 (Compute)**，而不仅仅是 2D 绘图。
- **全新的主循环回调 (Main Callbacks)：** 以前必须自己写 `while(running)` 循环，现在 SDL3 提供了一套可选的回调模式，这在移植到 Web (Emscripten) 或移动端时更加友好。
- **64位计时器：** `SDL_GetTicks()` 现在返回 64 位值，彻底解决了 SDL2 中运行 49 天后计时器溢出重置的问题。
- **Dialog API：** 终于内置了**原生对话框**支持（如：打开文件、保存文件、弹出消息框），不再需要通过第三方库或平台特定代码来实现。
- **存储与文件系统：** 增加了更强大的文件操作 API，支持异步 I/O、目录遍历和更简单的用户文件夹访问。


输入与显示增强
- **多设备支持：** SDL3 现在可以独立处理**多个鼠标和多个键盘**。
- **手写笔 API：** 原生支持数位板（Pen/Stylus）。
- **HiDPI 支持：** 极大改进了高分辨率屏幕（如 4K 屏、Retina 屏）的适配，窗口缩放更加平滑。
- **系统托盘：** 支持创建系统托盘图标、菜单和通知。
- **暗黑模式检测：** 可以直接查询系统当前是浅色还是深色主题。

音频系统重构
- **逻辑设备：** 引入了“逻辑音频设备”概念，允许一个程序为不同的组件（如背景音乐和音效）创建独立的流。
- **自动迁移：** 当你在玩游戏时拔掉耳机，SDL3 能更平滑地处理音频输出设备的切换。
- **增强型音频流：** 内置了更强的重采样、混音和音调控制功能。


## 引入SDL3
下载安装包： https://github.com/libsdl-org/SDL/releases ，选择带有devel标志的release
解压后（windows版本）：
![[SDL入门-引入sdl3-01.png]]



配置CMake（CMake会利用 `SDL3_DIR` 的逻辑来找模块Config，随后，CMake找到了 SDL 团队提供的 `SDL3Config.cmake` ）
```cmake
# `SDL3_DIR` 定位到具体的cmake路径 `xxxx/cmake` 。
set(SDL3_DIR <SDL3_Extract_Path>)
# Required the SDL3 library
find_package(SDL3 REQUIRED)

add_executable(${PROJECT_NAME} main.cpp)

target_link_libraries(${PROJECT_NAME} PRIVATE SDL3::SDL3)
```


## 第一个SDL程序
这段代码是一个使用 **SDL3** 库编写的极简 C++ 程序，它的功能是：创建一个窗口，并在黑色的背景上绘制一个绿色的正方形。

```cpp
#include <SDL3/SDL.h>
#include <iostream>

int main(int argc, char *argv[]) {
  // 初始化 SDL 的视频子系统（控制窗口显示和图形硬件）
  SDL_Init(SDL_INIT_VIDEO);

  // 创建一个窗口
  // 参数：标题, 宽度 (640), 高度 (480), 标志位 (0 表示默认设置)
  SDL_Window *win = SDL_CreateWindow("SDL3 Project", 640, 480, 0);
  if (win == nullptr) {
    std::cerr << "SDL_CreateWindow Error: " << SDL_GetError() << std::endl;
    SDL_Quit();
    return 1;
  }

  // 创建渲染器（负责在窗口内绘图的“画笔”）
  // 参数：关联的窗口, 渲染驱动名称 (NULL 表示让 SDL 自动选择最合适的)
  SDL_Renderer *ren = SDL_CreateRenderer(win, NULL);
  if (ren == nullptr) {
    std::cerr << "SDL_CreateRenderer Error: " << SDL_GetError() << std::endl;
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 1;
  }

  SDL_Event e;            // 定义一个事件结构体，用于存储用户输入（如键盘、鼠标点击）
  bool quit = false;      // 循环控制变量，决定程序何时退出

  // 定义一个矩形区域 (浮点数版本 SDL_FRect)
  SDL_FRect greenSquare{270, 190, 100, 100};

  // --- 游戏/程序主循环 ---
  while (!quit) {
    // 事件处理：轮询当前队列中的所有事件
    while (SDL_PollEvent(&e)) {
      // 如果用户点击了窗口的关闭按钮
      if (e.type == SDL_EVENT_QUIT) {
        quit = true;
      }
    }
    // 清空屏幕（用黑色清空）
    SDL_SetRenderDrawColor(ren, 0, 0, 0, 255); // Set render draw color to black
    SDL_RenderClear(ren);                      // Clear the renderer

    // 画绿色矩形
    SDL_SetRenderDrawColor(ren, 0, 255, 0,
                           255);           // Set render draw color to green
    SDL_RenderFillRect(ren, &greenSquare); // Render the rectangle

    // 将后台缓冲区绘制好的画面显示到屏幕上
    SDL_RenderPresent(ren); // Render the screen
  }

  // 销毁资源
  SDL_DestroyRenderer(ren);
  SDL_DestroyWindow(win);
  SDL_Quit();

  return 0;
}

```

# 基础功能
## 事件系统
### `SDL_PollEvent`
这个是非阻塞函数。当然也有一个阻塞版本：`SDL_WaitEvent`

如果想**手动控制频率**：使用 **`SDL_Delay`**。 （类似 sleep）

我们主要通过调用这个函数，得到SDL定义的Event结构，从而获取到各种外部数据信息。

### `SDL_Event`
```cpp
typedef union SDL_Event
{
    Uint32 type;                            /**< Event type, shared with all events, Uint32 to cover user events which are not in the SDL_EventType enumeration */
    SDL_CommonEvent common;                 /**< Common event data */
    SDL_DisplayEvent display;               /**< Display event data */
    SDL_WindowEvent window;                 /**< Window event data */
    SDL_KeyboardDeviceEvent kdevice;        /**< Keyboard device change event data */
    SDL_KeyboardEvent key;                  /**< Keyboard event data */
    SDL_TextEditingEvent edit;              /**< Text editing event data */
    SDL_TextEditingCandidatesEvent edit_candidates; /**< Text editing candidates event data */
    SDL_TextInputEvent text;                /**< Text input event data */
    SDL_MouseDeviceEvent mdevice;           /**< Mouse device change event data */
    SDL_MouseMotionEvent motion;            /**< Mouse motion event data */
    SDL_MouseButtonEvent button;            /**< Mouse button event data */
    SDL_MouseWheelEvent wheel;              /**< Mouse wheel event data */
    SDL_JoyDeviceEvent jdevice;             /**< Joystick device change event data */
    SDL_JoyAxisEvent jaxis;                 /**< Joystick axis event data */
    SDL_JoyBallEvent jball;                 /**< Joystick ball event data */
    SDL_JoyHatEvent jhat;                   /**< Joystick hat event data */
    SDL_JoyButtonEvent jbutton;             /**< Joystick button event data */
    SDL_JoyBatteryEvent jbattery;           /**< Joystick battery event data */
    SDL_GamepadDeviceEvent gdevice;         /**< Gamepad device event data */
    SDL_GamepadAxisEvent gaxis;             /**< Gamepad axis event data */
    SDL_GamepadButtonEvent gbutton;         /**< Gamepad button event data */
    SDL_GamepadTouchpadEvent gtouchpad;     /**< Gamepad touchpad event data */
    SDL_GamepadSensorEvent gsensor;         /**< Gamepad sensor event data */
    SDL_AudioDeviceEvent adevice;           /**< Audio device event data */
    SDL_CameraDeviceEvent cdevice;          /**< Camera device event data */
    SDL_SensorEvent sensor;                 /**< Sensor event data */
    SDL_QuitEvent quit;                     /**< Quit request event data */
    SDL_UserEvent user;                     /**< Custom event data */
    SDL_TouchFingerEvent tfinger;           /**< Touch finger event data */
    SDL_PenProximityEvent pproximity;       /**< Pen proximity event data */
    SDL_PenTouchEvent ptouch;               /**< Pen tip touching event data */
    SDL_PenMotionEvent pmotion;             /**< Pen motion event data */
    SDL_PenButtonEvent pbutton;             /**< Pen button event data */
    SDL_PenAxisEvent paxis;                 /**< Pen axis event data */
    SDL_RenderEvent render;                 /**< Render event data */
    SDL_DropEvent drop;                     /**< Drag and drop event data */
    SDL_ClipboardEvent clipboard;           /**< Clipboard event data */

    /* This is necessary for ABI compatibility between Visual C++ and GCC.
       Visual C++ will respect the push pack pragma and use 52 bytes (size of
       SDL_TextEditingEvent, the largest structure for 32-bit and 64-bit
       architectures) for this union, and GCC will use the alignment of the
       largest datatype within the union, which is 8 bytes on 64-bit
       architectures.

       So... we'll add padding to force the size to be the same for both.

       On architectures where pointers are 16 bytes, this needs rounding up to
       the next multiple of 16, 64, and on architectures where pointers are
       even larger the size of SDL_UserEvent will dominate as being 3 pointers.
    */
    Uint8 padding[128];
} SDL_Event;
```

## 硬件输入类事件
### 键盘(key) `SDL_KeyboardEvent`
```cpp
typedef struct SDL_KeyboardEvent
{
    SDL_EventType type;     /**< SDL_EVENT_KEY_DOWN or SDL_EVENT_KEY_UP */
    Uint32 reserved;
    Uint64 timestamp;       /**< In nanoseconds, populated using SDL_GetTicksNS() */
    SDL_WindowID windowID;  /**< The window with keyboard focus, if any */
    SDL_KeyboardID which;   /**< The keyboard instance id, or 0 if unknown or virtual */
    SDL_Scancode scancode;  /**< SDL physical key code */
    SDL_Keycode key;        /**< SDL virtual key code */
    SDL_Keymod mod;         /**< current key modifiers */
    Uint16 raw;             /**< The platform dependent scancode for this event */
    bool down;              /**< true if the key is pressed */
    bool repeat;            /**< true if this is a key repeat */
} SDL_KeyboardEvent;
```
- type: `SDL_EVENT_KEY_DOWN` (按下) 或 `SDL_EVENT_KEY_UP` (弹起)。
- timestamp: **SDL3 重大变化**：从毫秒升级到了**纳秒**。这对于需要极高精度输入同步的游戏（如音游）非常重要。
- windowID: 如果你开了多个窗口（比如编辑器主窗口和属性面板），它可以告诉你这个按键是在哪个窗口里按下的。
- scancode: **物理扫描码** ， 对应键盘上的**物理位置**。无论键盘是中文、美式还是法式，左下角的键永远是同一个扫描码。**适合做游戏控制（WASD）**。
- key: **虚拟键码** , 对应按键上的**字符**。受操作系统语言布局影响。**适合做快捷键（如 Ctrl+S）**。
- mod: **修饰键状态**  , 告诉你按下此键时，Shift、Ctrl、Alt、Command (Mac) 是否也被按住了。它是位掩码（Bitmask）。
- raw: 原始码，通常在排查特定硬件兼容性 Bug 时才用。
- down: 是否按下
- repeat: 是否是“长按重复” 。如果你按住一个键不放，系统会不断发送 DOWN 事件。如果这是由于长按触发的重复信号，该值为 `true`。通常游戏逻辑（如跳跃）会过滤掉重复信号。


**scancode** 描述的是按键在键盘硬件上的**物理坐标**。
- **特点**：独立于操作系统设置，独立于键盘上印的字母。（即按照标准键盘布局来映射按键）
- 核心用途：**兼容不同国家的键盘布局（如法国 AZERTY、德国 QWERTZ 等）**

**key** 描述的是按键被处理后转换成的**语义符号**。
- **特点**：取决于操作系统的键盘布局设置。
- **快捷键**：当玩家想要“**S**ave”（保存）时，他们期望按下字母 **S**。在不同布局中，S 的位置可能不同，但 `key` 始终能保证玩家按下印有 “S” 的那个键时触发保存。

用途区分：
- **人物移动、技能热键**（固定手型） ： scancode
- 菜单快捷键、UI 输入、打字： key
### 鼠标(motion/button/wheel) 
基本一目了然，我们就展示一下类定义（因为比较常用到），和较少的字段。

此外，SDL对窗口坐标来说都是从左上角作为原点。
#### `SDL_MouseMotionEvent`
```c
typedef struct SDL_MouseMotionEvent
{
    SDL_EventType type; /**< SDL_EVENT_MOUSE_MOTION */
    Uint32 reserved;
    Uint64 timestamp;   /**< In nanoseconds, populated using SDL_GetTicksNS() */
    SDL_WindowID windowID; /**< The window with mouse focus, if any */
    SDL_MouseID which;  /**< The mouse instance id in relative mode, SDL_TOUCH_MOUSEID for touch events, or 0 */
    SDL_MouseButtonFlags state;       /**< The current button state */
    float x;            /**< X coordinate, relative to window */
    float y;            /**< Y coordinate, relative to window */
    float xrel;         /**< The relative motion in the X direction */
    float yrel;         /**< The relative motion in the Y direction */
} SDL_MouseMotionEvent;
```

#### `SDL_MouseButtonEvent`
```c
typedef struct SDL_MouseButtonEvent
{
    SDL_EventType type; /**< SDL_EVENT_MOUSE_BUTTON_DOWN or SDL_EVENT_MOUSE_BUTTON_UP */
    Uint32 reserved;
    Uint64 timestamp;   /**< In nanoseconds, populated using SDL_GetTicksNS() */
    SDL_WindowID windowID; /**< The window with mouse focus, if any */
    SDL_MouseID which;  /**< The mouse instance id in relative mode, SDL_TOUCH_MOUSEID for touch events, or 0 */
    Uint8 button;       /**< The mouse button index */
    bool down;          /**< true if the button is pressed */
    Uint8 clicks;       /**< 1 for single-click, 2 for double-click, etc. */
    Uint8 padding;
    float x;            /**< X coordinate, relative to window */
    float y;            /**< Y coordinate, relative to window */
} SDL_MouseButtonEvent;
```

#### `SDL_MouseWheelEvent`
```c
typedef struct SDL_MouseWheelEvent
{
    SDL_EventType type; /**< SDL_EVENT_MOUSE_WHEEL */
    Uint32 reserved;
    Uint64 timestamp;   /**< In nanoseconds, populated using SDL_GetTicksNS() */
    SDL_WindowID windowID; /**< The window with mouse focus, if any */
    SDL_MouseID which;  /**< The mouse instance id in relative mode or 0 */
    float x;            /**< The amount scrolled horizontally, positive to the right and negative to the left */
    float y;            /**< The amount scrolled vertically, positive away from the user and negative toward the user */
    SDL_MouseWheelDirection direction; /**< Set to one of the SDL_MOUSEWHEEL_* defines. When FLIPPED the values in X and Y will be opposite. Multiply by -1 to change them back */
    float mouse_x;      /**< X coordinate, relative to window */
    float mouse_y;      /**< Y coordinate, relative to window */
    Sint32 integer_x;   /**< The amount scrolled horizontally, accumulated to whole scroll "ticks" (added in 3.2.12) */
    Sint32 integer_y;   /**< The amount scrolled vertically, accumulated to whole scroll "ticks" (added in 3.2.12) */
} SDL_MouseWheelEvent;
```
- 通常用y坐标就可以了。
### 触摸操作(tfinger) `SDL_TouchFingerEvent`
为了方便，SDL 默认会将单指触摸模拟成鼠标事件（如 `SDL_EVENT_MOUSE_BUTTON_DOWN`）。
- **优点**：如果你的游戏已经写好了鼠标逻辑，不需要改代码就能在手机上运行。
- **缺点**：无法处理复杂的多指手势（如缩放、双指旋转）。

如果你想通过 `which` 字段区分这个鼠标事件是真鼠标还是触摸模拟的，可以检查： `event.button.which == SDL_TOUCH_MOUSEID`。

```c
/**
 * Touch finger event structure (event.tfinger.*)
 *
 * Coordinates in this event are normalized. `x` and `y` are normalized to a
 * range between 0.0f and 1.0f, relative to the window, so (0,0) is the top
 * left and (1,1) is the bottom right. Delta coordinates `dx` and `dy` are
 * normalized in the ranges of -1.0f (traversed all the way from the bottom or
 * right to all the way up or left) to 1.0f (traversed all the way from the
 * top or left to all the way down or right).
 *
 * Note that while the coordinates are _normalized_, they are not _clamped_,
 * which means in some circumstances you can get a value outside of this
 * range. For example, a renderer using logical presentation might give a
 * negative value when the touch is in the letterboxing. Some platforms might
 * report a touch outside of the window, which will also be outside of the
 * range.
 *
 * \since This struct is available since SDL 3.2.0.
 */
typedef struct SDL_TouchFingerEvent
{
    SDL_EventType type; /**< SDL_EVENT_FINGER_DOWN, SDL_EVENT_FINGER_UP, SDL_EVENT_FINGER_MOTION, or SDL_EVENT_FINGER_CANCELED */
    Uint32 reserved;
    Uint64 timestamp;   /**< In nanoseconds, populated using SDL_GetTicksNS() */
    SDL_TouchID touchID; /**< The touch device id */
    SDL_FingerID fingerID;
    float x;            /**< Normalized in the range 0...1 */
    float y;            /**< Normalized in the range 0...1 */
    float dx;           /**< Normalized in the range -1...1 */
    float dy;           /**< Normalized in the range -1...1 */
    float pressure;     /**< Normalized in the range 0...1 */
    SDL_WindowID windowID; /**< The window underneath the finger, if any */
} SDL_TouchFingerEvent;
```
- 可以利用fingerID结合一些逻辑来做多点触控
- SDL 会自动把单指触摸模拟成鼠标事件（`which` 为 `SDL_TOUCH_MOUSEID`）
### 摇杆(jaxis/jball/jhat/jbutton)
```c
    SDL_JoyAxisEvent jaxis;                 /**< Joystick axis event data */
    SDL_JoyBallEvent jball;                 /**< Joystick ball event data */
    SDL_JoyHatEvent jhat;                   /**< Joystick hat event data */
    SDL_JoyButtonEvent jbutton;             /**< Joystick button event data */
```
这是 SDL 能够识别的所有游戏控制器（包括古老的飞行摇杆、赛车方向盘、甚至是跳舞毯）的最原始形式。
- **没有固定布局**：它只知道这个设备有 12 个按钮、4 个轴。它不知道哪个是“确认键”，哪个是“摇杆”。
- **索引识别**：按钮通常通过数字识别（Button 0, Button 1...）。
- **通用性广**：无论什么奇奇怪怪的控制器，只要系统能识别，它就是一个 Joystick。

**痛点**：如果你只用 Joystick 接口，玩家在用 Xbox 手柄时，A 键可能是 Button 0；但在用 PS5 手柄时，X 键可能是 Button 1。你必须为每种手柄写映射表。

#### `SDL_JoyAxisEvent` (轴变动)
- **对应硬件**：摇杆的 X/Y 轴、赛车游戏的油门/刹车踏板、飞行模拟器的节流阀。
- **数据特点**：`value` 是一个从 **-32768 到 32767** 的整数。
	- `0` 通常代表居中。
	- 在 SDL3 中，如果你开启了 Gamepad 模式，这些值会被归一化，但在底层的 `JoyAxis` 中，它依然是原始的 16 位整数。
#### SDL_JoyBallEvent (轨迹球)
- **对应硬件**：早期的街机摇杆或某些特殊的轨迹球（Trackball）控制器。
- **数据特点**：它不返回绝对位置，而是返回 **相对位移 (`xrel`, `yrel`)**。它就像一个没有按键、专门用来滚动的鼠标。
- **现状**：现代主流手柄（Xbox/PS5）完全不触发这个事件。

#### SDL_JoyHatEvent (帽键 / 十字键)
“Hat” 指的是摇杆顶部的那个小拨杆，通常就是我们说的 **D-Pad（十字键）**。
- **对应硬件**：手柄左侧的上下左右方向键。
- **数据特点**：它返回的是**离散的状态位**（Bitmask）：
    - `SDL_HAT_CENTERED` (居中)
    - `SDL_HAT_UP`, `SDL_HAT_DOWN`, `SDL_HAT_LEFT`, `SDL_HAT_RIGHT`
    - 甚至支持对角线，如 `SDL_HAT_UPRIGHT`。
#### SDL_JoyButtonEvent (按钮)
最基础的点击事件。
- **对应硬件**：手柄上的 A/B/X/Y、L1/R1、菜单键等。
- **数据特点**：只有两个状态：按下 (`SDL_PRESSED`) 或 弹起 (`SDL_RELEASED`)。

### 手柄(gaxis/gbutton/gtouchpad/gsensor)
```c
    SDL_GamepadAxisEvent gaxis;             /**< Gamepad axis event data */
    SDL_GamepadButtonEvent gbutton;         /**< Gamepad button event data */
    SDL_GamepadTouchpadEvent gtouchpad;     /**< Gamepad touchpad event data */
    SDL_GamepadSensorEvent gsensor;         /**< Gamepad sensor event data */
```
**Joystick 是底层的硬件驱动，而 Gamepad 是上层经过标准化的抽象层。**

为了解决不同手柄布局不一的问题，SDL 引入了 Gamepad 接口（在 SDL2 中叫 `GameController`）。它基于一个巨大的开源映射数据库（社区维护）。

- **标准化布局**：它假设所有手柄都长得像 Xbox 手柄。无论你插什么手柄，你都可以通过 `SDL_GAMEPAD_BUTTON_SOUTH`（底部的确认键）来获取输入。
- **自动映射**：SDL 会自动识别设备，并把 PS5 的“十字键”和 Xbox 的“十字键”映射到同一个常量上。
- **易用性**：非常适合主流游戏开发。

这里面的几个类型，基本上面的其他事件里也简要介绍了。我们就介绍一下gsensor

#### `SDL_GamepadSensorEvent`
现在的现代手柄（如 PS5 DualSense、Switch Pro、甚至某些高端国产手柄）都内置了运动检测功能。通过这个事件，你可以实现类似“体感瞄准”、“赛车方向盘转向”或者“摇一摇”的功能。

```c
/**
 * Gamepad sensor event structure (event.gsensor.*)
 *
 * \since This struct is available since SDL 3.2.0.
 */
typedef struct SDL_GamepadSensorEvent
{
    SDL_EventType type; /**< SDL_EVENT_GAMEPAD_SENSOR_UPDATE */
    Uint32 reserved;
    Uint64 timestamp;   /**< In nanoseconds, populated using SDL_GetTicksNS() */
    SDL_JoystickID which; /**< The joystick instance id */
    Sint32 sensor;      /**< The type of the sensor, one of the values of SDL_SensorType */
    float data[3];      /**< Up to 3 values from the sensor, as defined in SDL_sensor.h */
    Uint64 sensor_timestamp; /**< The timestamp of the sensor reading in nanoseconds, not necessarily synchronized with the system clock */
} SDL_GamepadSensorEvent;
```
- **`type`**: 始终为 `SDL_EVENT_GAMEPAD_SENSOR_UPDATE`。只要你开启了传感器的报告功能，这个事件就会以很高的频率（通常是 100Hz 或更高）持续触发。
- **`which`**: 手柄的实例 ID。用来区分是 1 号玩家还是 2 号玩家在晃动手柄。
- **`sensor`**: 传感器的类型。最常见的有两个：
	- `SDL_SENSOR_ACCEL`: **加速度计**。测量物体在三个轴上的加速度（包括重力）。
	- `SDL_SENSOR_GYRO`: **陀螺仪**。测量物体绕三个轴旋转的角速度。
- **`data[3]`**: 这是最重要的原始数据数组，存放 $x, y, z$ 三个轴的值。
- **`sensor_timestamp`**: 硬件层面的原始时间戳。它可能和系统的 `timestamp` 不同步，但对于计算两次采样之间的微小时间差（用于积分计算位移或角度）非常精确。


## 系统输入类事件
### 渲染通知(render) `SDL_RenderEvent`
简单来说，当系统（Windows, Android, iOS 等）对渲染上下文（Rendering Context）进行了一些底层的、会影响你画图的操作时，SDL 会通过这个事件通知你。

**它用来处理什么？**:  `SDL_RenderEvent` 主要包含以下两种核心情景：
1. 设备丢失与重置 (Device Lost/Reset): 在某些图形 API（如 Direct3D 或 Vulkan）中，如果驱动程序崩溃、显卡切换、或者电脑从睡眠中唤醒，渲染器可能会“丢失”它的设备。
	- **事件类型**：`SDL_EVENT_RENDER_DEVICE_RESET`
	- **作用**：当发生这个事件时，你之前创建的所有 **纹理（Textures）** 可能会失效。你需要捕获这个事件并重新上传你的图片数据到 GPU。
2. 目标丢失 (Target Lost)
	- **事件类型**：`SDL_EVENT_RENDER_TARGETS_RESET`
	- **作用**：如果你正在使用 `SDL_SetRenderTarget` 将内容画到一个纹理上，而系统由于某种原因重置了渲染目标，你需要重新准备这些目标。

在手机上，这个事件非常关键。当用户接电话或者切换到后台时，系统可能会收回显存资源。
- **Android**：当你从后台切回游戏时，SDL 可能会发出重置事件。如果你不处理，可能会发现屏幕变黑，因为显存里的纹理已经被系统清空了。
- **逻辑流程**：
    1. 收到 `SDL_EVENT_RENDER_DEVICE_RESET`。
    2. 你的程序执行逻辑：重新加载所有图片（PNG/JPG）到 `SDL_Texture` 中。

对于初学者：**大部分时间你可以忽略它**，因为现代驱动程序和 SDL3 已经处理得很好了。 但如果你发现你的程序在**电脑休眠唤醒后黑屏**，或者在**手机切回应用后贴图丢失**，那么 `SDL_RenderEvent` 就是解决问题的唯一钥匙。

### 输入法相关(text/edit/edit_candidates)
#### `SDL_TextInputEvent` (最终输入)
这是最常用的事件。
- **触发时机**：当用户在输入法中选择了候选词并**确认（按空格或回车）**后，或者直接输入英文时。
- **用途**：获取最终确定的字符串。
- **教程关联**：你之前看的 Glusoft 教程中，`text = text + event.text.text;` 就是用的这个。

#### `SDL_TextEditingEvent` (正在编辑/组合)
- **触发时机**：当用户正在打字，但**尚未确认**时。例如：你在输入法里打了 `zhongwen`，但还没选字。
- **核心数据**：
    - `text`: 当前正在编辑的拼音或笔画。
    - `start`: 光标在编辑文本中的位置。
    - `length`: 选中的长度。
- **用途**：用于在你的程序界面上实时显示“预览效果”（比如在输入位置下方显示一串带下划线的拼音）。
#### `SDL_TextEditingCandidatesEvent` (候选词列表)
这是 **SDL3 新增强化**的功能，以前在 SDL2 中很难直接获取候选词列表。
- **触发时机**：当输入法弹出候选词窗口，且候选词列表发生变化时。
- **核心数据**：包含一组候选词字符串。
- **用途**：如果你在开发一个**高度自定义 UI 的游戏**（比如全屏游戏，不想显示系统自带的输入法窗口），你可以隐藏系统窗口，然后用这个事件获取候选词，并用你游戏内的 UI 把它们画出来。
### 系统功能(drop/clipboard)
```c
    SDL_DropEvent drop;                     /**< Drag and drop event data */
    SDL_ClipboardEvent clipboard;
```
#### `SDL_DropEvent`
拖拽文本或者文件到窗口
```c
/**
 * An event used to drop text or request a file open by the system
 * (event.drop.*)
 *
 * \since This struct is available since SDL 3.2.0.
 */
typedef struct SDL_DropEvent
{
    SDL_EventType type; /**< SDL_EVENT_DROP_BEGIN or SDL_EVENT_DROP_FILE or SDL_EVENT_DROP_TEXT or SDL_EVENT_DROP_COMPLETE or SDL_EVENT_DROP_POSITION */
    Uint32 reserved;
    Uint64 timestamp;   /**< In nanoseconds, populated using SDL_GetTicksNS() */
    SDL_WindowID windowID;    /**< The window that was dropped on, if any */
    float x;            /**< X coordinate, relative to window (not on begin) */
    float y;            /**< Y coordinate, relative to window (not on begin) */
    const char *source; /**< The source app that sent this drop event, or NULL if that isn't available */
    const char *data;   /**< The text for SDL_EVENT_DROP_TEXT and the file name for SDL_EVENT_DROP_FILE, NULL for other events */
} SDL_DropEvent;
```
#### `SDL_ClipboardEvent`
剪切板
```c
/**
 * An event triggered when the clipboard contents have changed
 * (event.clipboard.*)
 *
 * \since This struct is available since SDL 3.2.0.
 */
typedef struct SDL_ClipboardEvent
{
    SDL_EventType type; /**< SDL_EVENT_CLIPBOARD_UPDATE */
    Uint32 reserved;
    Uint64 timestamp;   /**< In nanoseconds, populated using SDL_GetTicksNS() */
    bool owner;         /**< are we owning the clipboard (internal update) */
    Sint32 num_mime_types;   /**< number of mime types */
    const char **mime_types; /**< current mime types */
} SDL_ClipboardEvent;
```
- **`owner`**:
	- 如果为 `true`，说明是你自己的程序刚刚调用了 `SDL_SetClipboardText` 等函数修改了剪切板。
	- 如果为 `false`，说明是用户在别的程序（如 Chrome 或 Word）里复制了东西，现在你的程序感知到了。
- **`num_mime_types` 和 `mime_types`**:
	- 它会告诉你当前剪切板里数据的格式。例如：`text/plain`（纯文本）、`text/html`（富文本）、`image/png`（图片）。
	- 这让你能决定是否要处理这些数据（比如你的程序只接受图片粘贴）。
- 设置数据调用： `SDL_SetClipboardText` 和 `SDL_SetClipboardData`
- 获取数据则调用： `SDL_GetClipboardText` 和 `SDL_GetClipboardData`

剪切板的内容：
- 文本格式: 文本字符串
- 二进制格式: 二进制数据流
程序需要自己对内容编码解码（内容格式层面上，而不是字符串编码；通常系统会选择更好的编码保存字符串）。

## 音频媒体
SDL 提供了跨平台的音频流处理，能够处理混音、重采样和多声道。

这块我们跳过。我们目前仅关注渲染器，不涉及到音频问题。但游戏中使用SDL_Audio也是比较常见的。

## SDL_GPU (参考)
**注意：这部分内容靠和AIChat对话来猜测，并没有深入SDL源码，可能有很多错误**

我们自己手动封装vulkan。但SDL也提供了一些集成，我们这块看下SDL怎么做的。主要看一下一个三角形的渲染流程。这样也方便我们自己抽象vulkan封装的时候参考
### example：画三角形
https://hamdy-elzanqali.medium.com/let-there-be-triangles-sdl-gpu-edition-bd82cf2ef615
步骤：
1. 创建一个 **Device（设备）**
2. 创建 **Buffers（缓冲区）**，它们是在 GPU 上存储数据的容器。
3. 创建一个 **Graphics Pipeline（图形管线）**，用于告诉 GPU 如何使用这些缓冲区。
4. 获取一个 **Command Buffer（命令缓冲区）**，以开始向 GPU 发出任务指令。
5. 使用 **Transfer Buffer（传输缓冲区）** 在 **Copy Pass（拷贝阶段）** 中将数据填充到缓冲区。
6. 获取 **Swapchain（交换链）** 纹理，简单来说就是获取用于绘制的窗口表面。
7. 最后，在 **Render Pass（渲染阶段）** 中发出 **Draw Call（绘制调用）**。

### 创建设备 `SDL_CreateGPUDevice`
```cpp
// signature
SDL_GPUDevice* SDL_CreateGPUDevice(
  SDL_GPUShaderFormat format_flags,
  bool debug_mode,
  const char *name
);

// example:
// create a device for either VULKAN or METAL with debugging enabled and choose the best driver
SDL_GPUDevice* device = SDL_CreateGPUDevice(SDL_GPU_SHADERFORMAT_SPIRV | SDL_GPU_SHADERFORMAT_MSL, true, NULL);
```

这个函数内部：约等于
-  vkCreateInstance
+ 枚举物理设备
+ 选择物理设备
+ 查询并开启 device features
+ 选择并创建 queue families
+ vkCreateDevice
+ 各种 debug / validation / 命名配置

更具体的逻辑分解：
1. 后端选择（Backend Selection） Vulkan/D3D12/Metal/OpenGL
2. 实例 / 设备上下文创建（Instance / Context） 
3. Debug / Validation 配置
4. 物理设备枚举与选择（Physical Device Selection）
5. 设备能力探测与 feature 筛选（Device Features）
6. 队列模型建立（Queue Model）
7. Logical Device 创建
8. 内存模型与分配器初始化（GPU 内存分配策略、buffer / texture 的内存类型映射、staging / transfer 资源池）
	1. 选择 memory heaps
	2. 建立 allocator（类似 VMA）
9. Shader / Pipeline 子系统初始化
	1. `VkRenderPass` 定义的是 **attachment 格式、load/store 操作、subpass依赖、descriptor layout** 。也在这里创建，不绑定具体 framebuffer / swapchain image 。渲染的时候再绑定。
	2. **注意**：创建 window / ClaimWindow 时，会根据 RenderPass 模板创建可绑定对象（framebuffer、per-frame descriptor），但实际绑定发生在 BeginRenderPass / Draw 时
10. 命令系统初始化（但不创建buffer）


整体SDL封装逻辑：
- 对用户来说：
    - 你只接触 `SDL_GPUDevice*`
    - 一切 GPU 资源都必须“从 device 创建”
    - 所有能力查询都通过 device

- 对 SDL 内部来说：
    - `SDL_GPUDevice` 是**入口与聚合点**
    - 真正的功能分散在多个子系统中

简而言之： **这个API体现了SDL_GPU高度封装了图形API为多个子系统，并在初始化过程中调用这些系统，完成了对外统一提供了SDL_GPUDevice设备指针; 在内部子系统围绕它被初始化并注册**

注意：
- Vulkan 的 instance、logical device、队列、内存、缓冲区等可以在完全离屏的环境下创建。
- WSI（Window System Integration）相关内容，例如 Swapchain、Surface、呈现队列，只在你要渲染到屏幕时才需要。
。

### 添加窗口`SDL_ClaimWindowForGPUDevice`
```c
SDL_ClaimWindowForGPUDevice(device, window);
```
内部逻辑分解：
1. 校验窗口与设备状态（检查内部状态，防止被其他GPU复用）
2. 创建 WSI surface / 后端窗口对象 （即创建 vulkanSurface）
3. 查询可用的显示格式和能力，并选出**最优默认设置**。
4. 创建 Swapchain / backbuffer；配置 image usage / memory / layout（Vulkan）
5. 创建呈现队列 / command queue 绑定
	1. 确定哪个 queue family 支持 `VK_QUEUE_GRAPHICS_BIT | VK_QUEUE_PRESENT_BIT`
	2. 分配逻辑呈现 queue（可能复用 graphics queue）
6. 初始化同步与帧管理
	1. 为每个 swapchain image 创建 fence / semaphore / timeline
	2. 设置多帧 in-flight（通常 2~3 帧）
	3. 初始化 frame index / 当前 backbuffer 指针
	4. 这里具体创建framebuffer，Per-frame descriptor binding / buffer update：ClaimWindow。运行时，这些信息在和具体的renderpass绑定（按照layout描述）。
7. 更新 SDL_GPUDevice 内部状态



### 渲染帧准备
```cpp
SDL_AppResult SDL_AppIterate(void *appstate)
{
    // acquire the command buffer
    SDL_GPUCommandBuffer* commandBuffer = SDL_AcquireGPUCommandBuffer(device);

    // get the swapchain texture
    SDL_GPUTexture* swapchainTexture;
    Uint32 width, height;
    SDL_WaitAndAcquireGPUSwapchainTexture(commandBuffer, window, &swapchainTexture, &width, &height);

    // end the frame early if a swapchain texture is not available
    if (swapchainTexture == NULL)
    {
        // you must always submit the command buffer
        SDL_SubmitGPUCommandBuffer(commandBuffer);
        return SDL_APP_CONTINUE;
    }

    // create the color target
    SDL_GPUColorTargetInfo colorTargetInfo{};
    colorTargetInfo.clear_color = {240/255.0f, 240/255.0f, 240/255.0f, 255/255.0f};
    colorTargetInfo.load_op = SDL_GPU_LOADOP_CLEAR;
    colorTargetInfo.store_op = SDL_GPU_STOREOP_STORE;
    colorTargetInfo.texture = swapchainTexture;

    // begin a render pass
    SDL_GPURenderPass* renderPass = SDL_BeginGPURenderPass(commandBuffer, &colorTargetInfo, 1, NULL);

    // draw something

    // end the render pass
    SDL_EndGPURenderPass(renderPass);

    // submit the command buffer
    SDL_SubmitGPUCommandBuffer(commandBuffer);

    return SDL_APP_CONTINUE;
}
```
其实比较之直观接单。我们把这里面对应vulkan api调用猜测预估一下：
- SDL_AcquireGPUCommandBuffer: 内部对应 vkResetCommandBuffer、vkBeginCommandBuffer
	- **备注**：CreateDevice 时只是创建了 CommandPool / 模板；ClaimWindow 分配了每帧独立 CommandBuffer
- SDL_WaitAndAcquireGPUSwapchainTexture：内部对应 vkAcquireNextImageKHR ，获取对应的VkImage、layout转化操作、以及fence/semaphore同步，frame-in-flight 管理。
- SDL_GPUColorTargetInfo ： 创建启动renderpass需要绑定的参数，实际绑定对应renderTarget。
- SDL_SubmitGPUCommandBuffer: 内部对应 vkQueueSubmit、vkQueuePresentKHR 以及fence/semaphore同步管理。

### 数据上传
需要提前创建好buffer之类的
```cpp
// the vertex input layout
struct Vertex
{
    float x, y, z;      //vec3 position
    float r, g, b, a;   //vec4 color
};

// a list of vertices
static Vertex vertices[]
{
    {0.0f, 0.5f, 0.0f, 1.0f, 0.0f, 0.0f, 1.0f},     // top vertex
    {-0.5f, -0.5f, 0.0f, 1.0f, 1.0f, 0.0f, 1.0f},   // bottom left vertex
    {0.5f, -0.5f, 0.0f, 1.0f, 0.0f, 1.0f, 1.0f}     // bottom right vertex
};

// create the vertex buffer
SDL_GPUBufferCreateInfo bufferInfo{};
bufferInfo.size = sizeof(vertices); 
bufferInfo.usage = SDL_GPU_BUFFERUSAGE_VERTEX;
SDL_GPUBuffer* vertexBuffer = SDL_CreateGPUBuffer(device, &bufferInfo);
```
- vulkan在创建device的时候中，创建 renderpass中的subpass的pipeline时，定义了默认的 **vertex input layout** 和 **input assembly**。
	- 如果用户想自定义，那么用户就需要调用一些api手动创建对应的renderpipeline。（但可以复用 renderpass）


```cpp
// create a transfer buffer to upload to the vertex buffer
SDL_GPUTransferBufferCreateInfo transferInfo{};
transferInfo.size = sizeof(vertices);
transferInfo.usage = SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD;
SDL_GPUTransferBuffer* transferBuffer = SDL_CreateGPUTransferBuffer(device, &transferInfo);
// map the transfer buffer to a pointer  
Vertex* data = (Vertex*)SDL_MapGPUTransferBuffer(device, transferBuffer, false);  
  
data[0] = vertices[0];  
data[1] = vertices[1];  
data[2] = vertices[2];  
  
// or you can copy them all in one operation  
// SDL_memcpy(data, vertices, sizeof(vertices));  
  
// unmap the pointer when you are done updating the transfer buffer  
SDL_UnmapGPUTransferBuffer(device, transferBuffer);

// start a copy pass  
SDL_GPUCommandBuffer* commandBuffer = SDL_AcquireGPUCommandBuffer(device);  
SDL_GPUCopyPass* copyPass = SDL_BeginGPUCopyPass(commandBuffer);  
  
// where is the data  
SDL_GPUTransferBufferLocation location{};  
location.transfer_buffer = transferBuffer;  
location.offset = 0; // start from the beginning  
  
// where to upload the data  
SDL_GPUBufferRegion region{};  
region.buffer = vertexBuffer;  
region.size = sizeof(vertices); // size of the data in bytes  
region.offset = 0; // begin writing from the first vertex  
  
// upload the data  
SDL_UploadToGPUBuffer(copyPass, &location, &region, true);  
  
// end the copy pass  
SDL_EndGPUCopyPass(copyPass);  
SDL_SubmitGPUCommandBuffer(commandBuffer);
```
- 这个流程则是把上传数据的接口封装了一下。但封装得不多。有不少基本就是vulkan函数的调用。只不过fence/semaphore的管理不需要了（估计内部管理了）。

### Shader/Pipeline创建
基本还是要手动绑定的。
```c
// load the vertex shader code  
size_t vertexCodeSize;  
void* vertexCode = SDL_LoadFile("shaders/vertex.spv", &vertexCodeSize);  
  
// create the vertex shader  
SDL_GPUShaderCreateInfo vertexInfo{};  
vertexInfo.code = (Uint8*)vertexCode;  
vertexInfo.code_size = vertexCodeSize;  
vertexInfo.entrypoint = "main";  
vertexInfo.format = SDL_GPU_SHADERFORMAT_SPIRV;  
vertexInfo.stage = SDL_GPU_SHADERSTAGE_VERTEX;  
vertexInfo.num_samplers = 0;  
vertexInfo.num_storage_buffers = 0;  
vertexInfo.num_storage_textures = 0;  
vertexInfo.num_uniform_buffers = 0;  
  
SDL_GPUShader* vertexShader = SDL_CreateGPUShader(device, &vertexInfo);  
  
// free the file  
SDL_free(vertexCode);  
  
// load the fragment shader code  
size_t fragmentCodeSize;  
void* fragmentCode = SDL_LoadFile("shaders/fragment.spv", &fragmentCodeSize);  
  
// create the fragment shader  
SDL_GPUShaderCreateInfo fragmentInfo{};  
fragmentInfo.code = (Uint8*)fragmentCode;  
fragmentInfo.code_size = fragmentCodeSize;  
fragmentInfo.entrypoint = "main";  
fragmentInfo.format = SDL_GPU_SHADERFORMAT_SPIRV;  
fragmentInfo.stage = SDL_GPU_SHADERSTAGE_FRAGMENT;  
fragmentInfo.num_samplers = 0;  
fragmentInfo.num_storage_buffers = 0;  
fragmentInfo.num_storage_textures = 0;  
fragmentInfo.num_uniform_buffers = 0;  
  
SDL_GPUShader* fragmentShader = SDL_CreateGPUShader(device, &fragmentInfo);  
  
// free the file  
SDL_free(fragmentCode);  
  
// create the graphics pipeline  
SDL_GPUGraphicsPipelineCreateInfo pipelineInfo{};  
pipelineInfo.vertex_shader = vertexShader;  
pipelineInfo.fragment_shader = fragmentShader;  
pipelineInfo.primitive_type = SDL_GPU_PRIMITIVETYPE_TRIANGLELIST;  
  
// describe the vertex buffers  
SDL_GPUVertexBufferDescription vertexBufferDesctiptions[1];  
vertexBufferDesctiptions[0].slot = 0;  
vertexBufferDesctiptions[0].input_rate = SDL_GPU_VERTEXINPUTRATE_VERTEX;  
vertexBufferDesctiptions[0].instance_step_rate = 0;  
vertexBufferDesctiptions[0].pitch = sizeof(Vertex);  
  
pipelineInfo.vertex_input_state.num_vertex_buffers = 1;  
pipelineInfo.vertex_input_state.vertex_buffer_descriptions = vertexBufferDesctiptions;  
  
// describe the vertex attribute  
SDL_GPUVertexAttribute vertexAttributes[2];  
  
// a_position  
vertexAttributes[0].buffer_slot = 0;  
vertexAttributes[0].location = 0;  
vertexAttributes[0].format = SDL_GPU_VERTEXELEMENTFORMAT_FLOAT3;  
vertexAttributes[0].offset = 0;  
  
// a_color  
vertexAttributes[1].buffer_slot = 0;  
vertexAttributes[1].location = 1;  
vertexAttributes[1].format = SDL_GPU_VERTEXELEMENTFORMAT_FLOAT4;  
vertexAttributes[1].offset = sizeof(float) * 3;  
  
pipelineInfo.vertex_input_state.num_vertex_attributes = 2;  
pipelineInfo.vertex_input_state.vertex_attributes = vertexAttributes;  
  
// describe the color target  
SDL_GPUColorTargetDescription colorTargetDescriptions[1];  
colorTargetDescriptions[0] = {};  
colorTargetDescriptions[0].blend_state.enable_blend = true;  
colorTargetDescriptions[0].blend_state.color_blend_op = SDL_GPU_BLENDOP_ADD;  
colorTargetDescriptions[0].blend_state.alpha_blend_op = SDL_GPU_BLENDOP_ADD;  
colorTargetDescriptions[0].blend_state.src_color_blendfactor = SDL_GPU_BLENDFACTOR_SRC_ALPHA;  
colorTargetDescriptions[0].blend_state.dst_color_blendfactor = SDL_GPU_BLENDFACTOR_ONE_MINUS_SRC_ALPHA;  
colorTargetDescriptions[0].blend_state.src_alpha_blendfactor = SDL_GPU_BLENDFACTOR_SRC_ALPHA;  
colorTargetDescriptions[0].blend_state.dst_alpha_blendfactor = SDL_GPU_BLENDFACTOR_ONE_MINUS_SRC_ALPHA;  
colorTargetDescriptions[0].format = SDL_GetGPUSwapchainTextureFormat(device, window);  
  
pipelineInfo.target_info.num_color_targets = 1;  
pipelineInfo.target_info.color_target_descriptions = colorTargetDescriptions;  
  
// create the pipeline  
graphicsPipeline = SDL_CreateGPUGraphicsPipeline(device, &pipelineInfo);  
  
// we don't need to store the shaders after creating the pipeline  
SDL_ReleaseGPUShader(device, vertexShader);  
SDL_ReleaseGPUShader(device, fragmentShader);  
  
// create the vertex buffer  
SDL_GPUBufferCreateInfo bufferInfo{};  
bufferInfo.size = sizeof(vertices);  
bufferInfo.usage = SDL_GPU_BUFFERUSAGE_VERTEX;  
vertexBuffer = SDL_CreateGPUBuffer(device, &bufferInfo);  
  
// create a transfer buffer to upload to the vertex buffer  
SDL_GPUTransferBufferCreateInfo transferInfo{};  
transferInfo.size = sizeof(vertices);  
transferInfo.usage = SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD;  
transferBuffer = SDL_CreateGPUTransferBuffer(device, &transferInfo);
```

### 渲染DrawCall
```c
SDL_GPURenderPass* renderPass = SDL_BeginGPURenderPass(commandBuffer, &colorTargetInfo, 1, NULL);

// bind the graphics pipeline
SDL_BindGPUGraphicsPipeline(renderPass, graphicsPipeline);

...

SDL_EndGPURenderPass(renderPass);
```
可以渲染的时候，具体绑定 graphicsPipeline


AI坚持SDL可以自行创建：

| 用法        | pipeline 创建方式                      | 生命周期管理                | 灵活性         |
| --------- | ---------------------------------- | --------------------- | ----------- |
| 手动创建（你代码） | 显式 `SDL_CreateGPUGraphicsPipeline` | 你管理 pipeline + shader | 高，可以自定义所有状态 |
| 默认/懒创建    | SDL 内部检查 + 自动创建                    | SDL 内部管理              | 低，只能用默认状态   |
### 总结
- **SDL GPU 封装的内容**：
    - 设备创建、上下文管理 (`SDL_CreateGPUDevice`)
    - buffer/transfer buffer 的创建和映射
    - shader module 的加载
    - pipeline 创建接口（你需要手动填 info）
    - 命令缓冲区提交 (`SDL_AcquireGPUCommandBuffer`, `SDL_SubmitGPUCommandBuffer`)
    - 内部可能管理 fence/semaphore、pipeline 缓存和默认状态

- **不封装的内容**：
    - pipeline 状态必须手动配置（shader stage、vertex layout、blend state 等）
    - 对复杂资源绑定、descriptor set、render pass 等没有高层封装
    - 同步控制、frame-in-flight、细粒度内存管理仍需理解底层逻辑
    - 并没有隐藏 Vulkan 本身的对象创建生命周期问题

# SDL和Vulkan集成
## 引入SDL的原因
- SDL提供了极致的手柄支持 (Game Controller DB)： 内置了一个巨大的数据库，能自动识别数千种手柄并映射为标准的布局（如 `SDL_Gamepad`）。如果你的项目未来要支持主机手柄，SDL 是唯一选择。
- SDL 提供了跨平台的音频流处理，能够处理混音、重采样和多声道。
- SDL 有更好的增强的跨平台能力（移动端/网页）
- SDL 提供了系统原生功能：
	- 剪贴板：跨平台的文字和数据剪贴板操作。
	- 电源管理：检测笔记本电量，调整渲染帧率以省电。
	- 原生对话框：比如弹出一个系统原生的报错窗口或文件选择器。

### SDL 的职责（非常明确）
SDL **只做三件事**：
1. 创建原生窗口（Win32/X11/Cocoa）
2. 获取该窗口的原生句柄
3. 调用正确的 `vkCreateXxxSurfaceKHR` 的Vulkan扩展函数。

SDL **不做**：
- 不管理 Swapchain
- 不管理 Vulkan 生命周期
- 不参与渲染
## SDL 创建 Vulkan Surface 

### SDL-创建支持 Vulkan 的 SDL_Window

```cpp
SDL_Window* window = SDL_CreateWindow(
    "Vulkan + SDL",
    SDL_WINDOWPOS_CENTERED,
    SDL_WINDOWPOS_CENTERED,
    1280,
    720,
    SDL_WINDOW_VULKAN | SDL_WINDOW_SHOWN
);

```
以 Windows 为例：
- SDL 调用 `CreateWindowExW`
- 保存 `HWND`
- **不会创建 OpenGL / DirectX 上下文**
- 只是一个“裸窗口”

### SDL-查询 Vulkan Instance 需要的扩展
```cpp
unsigned int count = 0;
SDL_Vulkan_GetInstanceExtensions(window, &count, nullptr);

std::vector<const char*> extensions(count);
SDL_Vulkan_GetInstanceExtensions(window, &count, extensions.data());
```
做了什么： **“如果你想让 Vulkan 能往这个窗口呈现，Instance 至少要开什么扩展？”**
- 确认当前 SDL_Window 的视频后端（比如类似x11这样的窗口系统）
- 根据该后端列出 Vulkan WSI 所需的 Instance 扩展
	- WSI: Window System Integration 。WSI 是 Vulkan（以及部分现代图形 API）中，  “GPU 图像如何交付给操作系统窗口系统显示”的完整机制集合。 **WSI 是Vulkan 与窗口系统之间的 契约** （包含的能力有：被Vulkan引用、能创建可呈现对象、能调度显示、能处理生命周期变化）
	- 这里主要根据 Vulkan WSI规范，返回窗口系统支持的能力，以及窗口系统的标记。
- 把扩展名（const char）交给你

没做什么：
- 不调用 `vkEnumerateInstanceExtensionProperties`
- 不验证扩展是否真的存在
- 不创建 `VkInstance`
- 不接触 GPU / Driver


### Vulkan-创建 Vulkan Instance
```cpp
VkInstanceCreateInfo createInfo{}; 
createInfo.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO; createInfo.enabledExtensionCount = static_cast<uint32_t>(extensions.size()); 
createInfo.ppEnabledExtensionNames = extensions.data();  
vkCreateInstance(&createInfo, nullptr, &instance);
```
- **没有 Instance，就没有 Surface**
- Instance ≈ Vulkan 与 OS 的“连接点”
### SDL - 创建 VkSurfaceKHR
```cpp
VkSurfaceKHR surface; 
if (!SDL_Vulkan_CreateSurface(window, instance, &surface)) {  
    throw std::runtime_error("Failed to create Vulkan surface"); 
}
```

### `SDL_Vulkan_CreateSurface` 具体做了什么？

层 1：SDL 层 (The Wrapper)
- **职责**：跨平台适配。
- **动作**：提取平台相关的窗口句柄（`HWND`），封装进 Vulkan 要求的 `CreateInfo` 结构体。

层 2：Vulkan Loader (The Dispatcher)
- **实现者**：通常由 **LunarG (Vulkan SDK)** 或 **操作系统分发**（如 Windows 自带的 `vulkan-1.dll`）。**它不是显卡厂商提供的，只是有可能会由它分发**
- **动作**：
    1. 它是 `vkCreateWin32SurfaceKHR` 函数的**入口点**。
    2. 它维护一张“跳板表”（Trampoline Table）。当你调用该函数时，它会检查你的 `VkInstance` 绑定了哪些显卡驱动。
    3. **转发**：它把调用分发给底层所有的 ICD。
        
层 3：Vulkan WSI 扩展实现 (The Bridge)
- **实现者**：**显卡厂商（NVIDIA/AMD/Intel）的驱动程序。**
- **动作**：每个驱动程序内部都有一个专门处理 WSI 的模块。最终转发给 ICD来执行

层 4：驱动 (ICD - Installable Client Driver)
- **实现者**：显卡厂商。
- **动作**：
    1. **OS 握手**：通过 WDDM（Windows 显存驱动模型）接口，告诉 Windows 桌面管理器（DWM）：“我要接管这个窗口的图像渲染了”。
    2. **生成句柄**：创建一个 `VkSurfaceKHR` 对象（这本质上是一个指向驱动内部数据结构的指针/句柄）。

注意： **Surface 本身不分配 GPU 显存**


## Surface的一些注意点

### Surface 依赖 Instance
- Instance 销毁前，必须销毁 Surface
- 否则 **未定义行为**

### Surface 不是 Swapchain

|对象|作用|
|---|---|
|VkSurfaceKHR|OS 显示目标|
|VkSwapchainKHR|图像队列|

Swapchain **依赖** Surface，但不反之。


### 一个 Surface 能否被多个 Device 使用？
- **理论上可以**
- 实际上你只会用一个
- 每个 PhysicalDevice 都要：
    `vkGetPhysicalDeviceSurfaceSupportKHR(...)`

### 为什么 SDL 不直接给你 Swapchain？
1. Swapchain 与：格式、Present Mode、Image Count、同步模型  **强耦合**
2. Vulkan 明确要求：应用完全控制

SDL 的设计哲学是：**“只解决平台差异，不做策略决策”**

# 参考资料
- https://wiki.libsdl.org/SDL3/Tutorials
- https://glusoft.com/sdl3-tutorials/
- https://hamdy-elzanqali.medium.com/let-there-be-triangles-sdl-gpu-edition-bd82cf2ef615