---
id: art_05b1c22ae41f1d9c7fe4bddf0f549e54
title: ImGUI入门
date: 2026-04-01T12:53:40+08:00
draft: true
---

# Get Started
Dear ImGui 是从游戏开发领域发展出来的。游戏应用通常需要以互动帧率（比如 60 FPS）持续刷新界面，并且后面总有一个图形密集型的应用在运行。

虽然它也能在非典型场景下使用，但那需要高级技巧。
## 设计理念
**Immediate Mode GUI（即时模式 GUI）**
- 每一帧都“重新描述”UI
- 不保存控件状态（状态由你管理）
- UI ≈ 函数调用的结果，而不是对象树

特点：
- 尽量减少 **多余的状态复制**（superfluous state duplication）
- 减少 **状态同步**（state synchronization）
- 不要求用户维护复杂的状态或记忆界面元素状态（state retention）

对比：

|维度|ImGui|传统 GUI|
|---|---|---|
|编程模型|即时模式|保留模式|
|控件生命周期|每帧生成|长期存在|
|调试工具|极强|一般|
|适用场景|工具、编辑器、调试面板|商业软件|

## 渲染方式
**核心机制**：
- Dear ImGui **不直接操作 GPU**，它只生成：
    - **顶点缓冲区（vertex buffers）**
    - **绘制命令列表（command lists）**
- 然后你可以把这些数据交给你的渲染管线渲染。

**性能**：
- 所需的绘制调用（draw calls）和状态切换很少
- 因为它不直接操作 GPU，你可以在代码的任何位置调用 Dear ImGui（比如算法中途或自己的渲染流程中），然后在合适的时间渲染输出。

常见误解：IMGUI = 每调用一次函数就直接渲染一次（直接 hammer GPU），会非常低效。
- Dear ImGui **不是直接渲染**。它只是生成顶点数据和少量绘制批次（draw call batches），可以稍后在你的应用中渲染。这些绘制批次已经 **相对优化**，不会频繁切换 GPU 状态。

## 集成构建配置
通过引入源码来集成。首先项目中引入 ImGui 作为submodule
```sh
git submodule add https://github.com/ocornut/imgui.git external/imgui
```

Dear ImGui **不需要单独编译成库**；官方推荐直接把源文件加入你的项目编译。  这是因为它体积小、调用密集，不适合做共享库。 (**用到什么文件就引入对应的cpp即可；不过因此需要自己单独写针对imgui的cmake代码**)

**必须包含的核心文件：** （UI前端代码）
```
imgui/imgui.cpp
imgui/imgui_draw.cpp
imgui/imgui_tables.cpp
imgui/imgui_widgets.cpp
```

**添加你需要的后端实现：** （UI后端，即渲染API/窗口系统等）
- 这里根据自己选择的平台选择。我们的平台选择是 Vulkan+SDL3

```
imgui/backends/imgui_impl_sdl3.cpp
imgui/backends/imgui_impl_vulkan.cpp
```

**头文件目录**： 添加整个imgui目录即可。

示例的cmake配置
```cmake
add_library(imgui STATIC)

set(IMGUI_ROOT
    ${PROJECT_SOURCE_DIR}/external/imgui
)

message(STATUS ${IMGUI_ROOT})

target_sources(imgui PRIVATE
    ${IMGUI_ROOT}/imgui.cpp
    ${IMGUI_ROOT}/imgui_draw.cpp
    ${IMGUI_ROOT}/imgui_tables.cpp
    ${IMGUI_ROOT}/imgui_widgets.cpp
    ${IMGUI_ROOT}/backends/imgui_impl_sdl3.cpp
    ${IMGUI_ROOT}/backends/imgui_impl_vulkan.cpp
)

target_include_directories(imgui
    PUBLIC
        ${IMGUI_ROOT}
        ${IMGUI_ROOT}/backends
)

target_link_libraries(imgui
    PUBLIC
        Vulkan::Vulkan
        SDL3::SDL3
)

target_compile_features(imgui PUBLIC cxx_std_17)
```