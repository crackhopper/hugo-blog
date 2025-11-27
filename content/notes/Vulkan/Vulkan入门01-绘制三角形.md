---
title: Vulkan入门01-绘制三角形
date: 2025-11-25T21:29:13+08:00
tags:
  - vulkan
  - cmake
  - glfw
draft: false
---
参考： https://vulkan-tutorial.com/

本笔记仅为概要总结，方便自己梳理和回忆。
<!--more-->


# 构建配置
我们选择用cmake配置。依赖库有两个

## 背景知识-CMake的 `find_package` 
cmake提供了 `find_package` 功能。可以方便自动查找一些外部依赖库。

用法：
```
find_package(<PackageName> [version] [REQUIRED] [QUIET] [COMPONENTS <component1> <component2>...] [NO_MODULE])
```

分为两种模式：module模式和config模式

### Module 模式 （老模式，cmake负责）
通过 `Find<PackageName>.cmake` 文件

- **查找文件：** CMake 会尝试在特定的目录（包括 CMake 自己的安装目录和用户指定的目录）中寻找一个名为 `Find<PackageName>.cmake` 的文件。
- **执行逻辑：** 如果找到，CMake 会执行这个文件中的脚本逻辑。这个脚本通常包含了一系列平台特定的命令（如 `find_path`、`find_library`、`find_program`）来定位库的头文件、库文件和可执行程序。
- **设置变量：** 成功定位后，`Find<PackageName>.cmake` 脚本会设置一组标准的 CMake 变量供项目使用。

| **变量名称**                     | **描述**          |
| ---------------------------- | --------------- |
| `<PackageName>_FOUND`        | 布尔值，表示是否成功找到库。  |
| `<PackageName>_INCLUDE_DIRS` | 包含头文件的目录列表。     |
| `<PackageName>_LIBRARIES`    | 要链接的库文件路径或名称列表。 |
| `<PackageName>_DEFINITIONS`  | 编译所需的预处理器定义。    |
**需要分别用 `target_link_library` ， `target_include_directories` ， `target_compile_definitions` 来引入库文件、头文件和编译选项**
### Config 模式 (新模式，库提供者负责)
通过 `<PackageName>Config.cmake` 或 `<PackageName>-config.cmake` 文件
- **查找文件：** CMake 会尝试在系统路径（如 `/usr/local/lib/cmake/` 或自定义路径）中寻找一个名为 `<PackageName>Config.cmake` 或 `<PackageName>-config.cmake` 的配置文件。
- **执行逻辑：** 这种配置文件是由**库的开发者**在库的安装过程中生成的。它包含了库的绝对路径信息。
- **设置目标：** Config 模式的配置文件通常会使用 `IMPORTED` 目标（如 `add_library(<PackageName>::<component> IMPORTED)`）来封装库的信息。这是 CMake 推荐的现代用法，允许用户直接使用库名称作为链接目标，例如： `target_link_libraries(MyExecutable PRIVATE <PackageName>::<component>)`

**一体化导入，将：库文件、头文件、编译选项，都包装到 `Package::Component` 中了**

## 背景知识-Windows下的动态库链接
windows下，如果程序要链接一个动态库，需要两个文件：
- `.lib` : 通常是一个导出库（如果文件很大，那么它本身则很有可能是包含函数定义的静态库，而不是导出库）。导出库里，包含： `符号名称` 和 `DLL文件名` 。编译过程中，windows使用这个就可以完成程序的编译。
- `.dll` ：运行程序时，如果程序编译中link了导出库，那么会按照路径来搜索对应的dll库（包含函数的实际实现）
	- 程序所在目录
	- 系统目录（通常是system32）
	- 环境变量PATH的目录。
## 配置：选择CXX 20
```cmake
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
```
## 配置：关闭MSVC特殊警告
```cmake
# -------------------------------
# Windows 特殊：定义宏
# 关闭MSVC的安全警告，例如，用 strcpy_s 替代 strcpy，用 scanf_s 替代 scanf
# 提高可移植性
# -------------------------------
if (WIN32)
    target_compile_definitions(${PROJECT_NAME} PRIVATE "_CRT_SECURE_NO_WARNINGS")
endif()

```
## 配置：编译器编码(字符集)问题
### MSVC编译器-源代码编码识别

当 MSVC 编译器读取源代码文件时：
- **有 BOM 的 UTF-8 (UTF-8-BOM)**：编译器会检测到 **BOM（字节顺序标记）**，并正确地将文件识别为 UTF-8 编码。
- **无 BOM 的 UTF-8 (UTF-8)**：如果文件中**没有 BOM**，编译器默认会假设文件是使用**当前用户的系统代码页**进行编码的（例如，在中国区就是 GBK/GB2312）。这会导致 UTF-8 编码的非 ASCII 字符被错误解读，从而出现乱码或编译警告/错误。

实际上对UTF8来说，并不需要BOM。我们只需要告诉编译器，输入的源代码是UTF8格式即可。

### 源代码字符集 和 执行字符集

- 源代码字符集 (Source Character Set)
	- 这是指你的 C++ 源代码文件（`.cpp`, `.h` 文件）本身是以哪种编码格式保存的（例如 UTF-8、GBK、或 ISO-8859-1）。
- 执行字符集 (Execution Character Set)
	- 这是指程序编译完成后，存储在可执行文件内部的字符串字面量（String Literals，如 `"Hello"` 或 `"你好"`）所使用的编码格式。

### cmake编译器选项设置
```cmake
if(MSVC)
    # MSVC: 明确指定使用 UTF-8
    add_compile_options(/utf-8)
else()
    # GCC/Clang: 设置源码字符集
    add_compile_options(-finput-charset=UTF-8)
    add_compile_options(-fexec-charset=UTF-8)
endif()
# 定义一个预编译宏，方便我们自己使用
add_definitions(-D_UTF8_SOURCE)
```


## 配置：Vulkan依赖
开发vulkan程序，需要需要程序连接到 vulkan loader动态库 (vulkan-1.dll) 上。
### Vulkan loader
Khronos Group 通过其 **Vulkan Loader and Validation Layer (Loader)** 仓库开发的。它的作用是实现 Khronos 定义的**加载器接口规范**。

硬件厂商会根据这个仓库（有可能有一些定制化改动），编译成 `vulkan-1.dll` 。在安装驱动程序的时候，将这个动态库安装到系统目录中。

`vulkan-1.dll` **本身不是** Vulkan 的图形实现。它是一个薄薄的层（Layer）。真正的、有巨大差异的实现代码位于厂商的 **私有驱动 DLL** 中（如 `nvoglv64.dll`），这些驱动 DLL 会被 `vulkan-1.dll` 加载和调用。

### 链接方式
在安装好的Vulkan的SDK中，可以找到对应的导出库，`vulkan-1.lib` ：
![[Vulkan入门-绘制三角形-1764083080360.png]]

因此严格来说，程序只要link这个库，并且system32中存在 `vulkan-1.dll` 那么就完成了vulkan的集成。

### cmake中导入Vulkan
代码如下：
```cmake
find_package(Vulkan REQUIRED)
# 检查查找是否成功。 (REQUIRED 关键字已经保证了这一点，但保留这个变量以备用)
if(NOT Vulkan_FOUND)
    # 实际上由于 REQUIRED，程序不会运行到这里，但保留是良好的编程习惯。
    message(FATAL_ERROR "Vulkan SDK not found.") 
endif()
```

实际上Vulkan的SDK（windows下）并没有提供 `VulkunConfig.cmake` 。因此是按照cmake的 Module 方式，调用cmake提供的 `FindVulkan.cmake` 文件来查找的（各种尝试，包括使用环境变量）。但目前的cmake提供的 `FindVulkan.cmake` 也会导出 Config风格的目标。因此，在使用的时候：
```cmake
if(NOT TARGET Vulkan::Vulkan)
    message(FATAL_ERROR "Vulkan SDK found, but does not provide the required modern target Vulkan::Vulkan. Please update your SDK or FindVulkan.cmake.")
endif()
target_link_libraries(${PROJECT_NAME} PRIVATE Vulkan::Vulkan)
```
这样即可。

当然，更稳妥的方式，还是当Config模式找不到的时候，使用Module模式：
```cmake
if(NOT TARGET Vulkan::Vulkan)
    # 如果找到了 SDK，但没找到目标，说明是老旧的 Module 模式。
    # 此时，我们必须回退到使用传统变量。
    message(WARNING "Vulkan SDK found, but target Vulkan::Vulkan is missing. Falling back to using legacy variables.")
    
    # 回退到 Module 模式的链接方式
    target_include_directories(${PROJECT_NAME} PRIVATE ${Vulkan_INCLUDE_DIRS})
    target_link_libraries(${PROJECT_NAME} PRIVATE ${Vulkan_LIBRARIES})
else()
    # 3. 使用推荐的 Config 链接方式。
    target_link_libraries(${PROJECT_NAME} PRIVATE Vulkan::Vulkan)
endif()
```

## 配置：GLFW依赖
直接将源码引入到依赖中。这样有更好的跨平台兼容性。也方便调试。

源码方式（Source Code）的优势

|**优势**|**描述**|
|---|---|
|**1. 调试友好性 (Debuggability)**|如果在应用程序中遇到与窗口、输入或渲染上下文相关的罕见错误，您可以直接进入 GLFW 源码进行调试和单步跟踪。这对于底层的 Vulkan 开发非常有价值。|
|**2. 一致性与控制 (Consistency & Control)**|您可以确保 GLFW 是使用与您的 Vulkan 项目**相同的编译器、相同的编译标志、相同的 C++ 标准**（例如 C++20）和相同的运行时库（如 MSVC 的 `/MT` 或 `/MD`）编译的。这可以避免许多由于ABI不匹配或库冲突导致的链接错误。|
|**3. 易于集成到构建系统 (Easy CMake Integration)**|如果您的项目使用 CMake，您可以使用 `FetchContent` 或 `add_subdirectory()` 将 GLFW 源码直接拉取并集成到您的主构建脚本中。这样，**所有依赖都会在您配置项目时自动构建**，无需手动管理二进制文件。|
|**4. 跨平台支持 (Cross-Platform)**|预编译的二进制文件通常只针对特定的操作系统、编译器和架构（例如 Windows x64 MSVC）。使用源码，您可以轻松地在 Windows、Linux 和 macOS 等平台**用本地编译器进行构建**。|
|**5. 针对性优化 (Targeted Optimization)**|您可以自由修改 GLFW 的 CMake 选项，根据您的特定需求（例如，禁用不必要的特性或开启特定的优化）来编译库。|
### cmake导入方式
很简单，引入对应的源码文件夹即可。因为源码也是用cmake组织的：
```cmake
add_subdirectory(external/glfw-3.4)
```

这样会加载对应目录的 `CMakeLists.txt` 文件，从而其内部定义的target都可以直接使用。

我们使用的方式只需要：
```cmake
target_link_libraries(${PROJECT_NAME} PRIVATE glfw)
```
这其实是由于glfw的cmakelist编写的时候，正确使用的各种cmake的target属性设定的方式，所以我直接一个link_libraries就可以把头文件、库文件和编译选项都引入进来？

## 配置：shader编译
### 找到编译工具 `glslc.exe`
根据 `Vulkan_SDK` 环境变量来查找。（一般安装SDK后会自动配置）

```cmake
find_program(GLSLC_EXECUTABLE
    NAMES glslc
    HINTS $ENV{VULKAN_SDK}/Bin $ENV{VULKAN_SDK}/x86_64/bin
    REQUIRED
)
```

CMake 会按照以下顺序进行查找：
1. **系统默认路径 (PATH 环境变量):** 首先，它会在系统 `PATH` 环境变量中定义的标准可执行文件路径中查找名为 `glslc`（在 Windows 上通常是 `glslc.exe`）的文件。
2. **`HINTS` 指定的路径:** 接下来，它会检查您在 `HINTS` 中提供的自定义目录：
    - `${VULKAN_SDK}/Bin`
    - `${VULKAN_SDK}/x86_64/bin`
3. **CMake 缓存和标准查找路径:** 它还会检查 CMake 自己的缓存和其他标准查找位置（例如用户定义的前缀路径等）。

找不到则直接报错。

### 定义输入输出目录
```cmake
# 定义 shader 目录和输出目录
set(SHADER_DIR ${CMAKE_CURRENT_SOURCE_DIR})
set(SHADER_OUTPUT_DIR ${CMAKE_CURRENT_BINARY_DIR}/shaders)
file(MAKE_DIRECTORY ${SHADER_OUTPUT_DIR})
```

### 查找和自动编译shader
```cmake
# 自动查找所有着色器文件
file(GLOB SHADER_FILES
    "${SHADER_DIR}/*.vert"
    "${SHADER_DIR}/*.frag"
    # ...可以添加更多类型，如.comp, .geom等
)

set(SPV_FILES "") # 用于存储所有生成的.spv文件路径

foreach(SHADER_FILE ${SHADER_FILES})
    # 获取着色器文件的完整文件名（例如: shader.vert）
    get_filename_component(BASE_NAME ${SHADER_FILE} NAME) 
    
    # 构造输出 .spv 文件的完整路径
    # 示例: .../shaders/shader.vert.spv
    set(OUTPUT_SPV "${SHADER_OUTPUT_DIR}/${BASE_NAME}.spv") 

    # 将生成的 .spv 文件添加到列表中
    list(APPEND SPV_FILES "${OUTPUT_SPV}")

    # 定义自定义编译命令
    add_custom_command(
        OUTPUT "${OUTPUT_SPV}"
        COMMAND "${GLSLC_EXECUTABLE}"
            -o "${OUTPUT_SPV}"
            "${SHADER_FILE}"
        DEPENDS "${SHADER_FILE}"
        COMMENT "Compiling shader: ${BASE_NAME}"
        VERBATIM
    )
endforeach()

# 创建目标依赖所有生成的 .spv 文件
add_custom_target(CompileShaders
    DEPENDS ${SPV_FILES}
)
```

# GLFW窗口初始化
```cpp
// 它初始化了 GLFW 内部的所有必需组件，包括系统计时器、线程、以及输入系统（键盘、鼠标等）。
glfwInit();
// 禁用 OpenGL API 。 默认情况下，GLFW 旨在创建与 **OpenGL** 上下文兼容的窗口。
glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API);
// 创建主应用程序窗口
window = glfwCreateWindow(WIDTH, HEIGHT, "Vulkan", nullptr, nullptr);
// 设置用户自定义数据： 将一个**用户指针**与 GLFW 窗口关联起来。
//     主要目的就是为了在回调函数中访问到设定的这个指针。
glfwSetWindowUserPointer(window, this);
// 注册帧缓冲大小变化回调：处理窗口变化，通常这里用到上面设定的指针
glfwSetFramebufferSizeCallback(window, framebufferResizeCallback);
```
因为使用了GLFW库。窗口创建相对来说比较简单。
# Vulkan初始化-基础初始化
## 创建 Vulkan 实例
设定：
- App信息： `VkApplicationInfo`
- 开启的扩展（字符串数组）：通常是 `VK_xxxx` 。比如， `VK_KHR_surface` ，`VK_EXT_debug_utils` (变量: `VK_EXT_DEBUG_UTILS_EXTENSION_NAME`)
- 开启的验证层（validation layers）（字符串数组)：通常类似 `VK_LAYER_xxx` 。比如，`VK_LAYER_KHRONOS_validation`
- 对创建Instance的过程调试（optional）：利用 `pNext` 这个指针和 `VkDebugUtilsMessengerCreateInfoEXT` 结构。
### Extensions
Vulkan 的设计是模块化的，核心 API 提供了一些基本的功能，而 **extensions**（扩展）则允许添加额外的功能。扩展是由硬件厂商（如 NVIDIA、AMD）或 Vulkan 的开发团队提供的，可以是官方支持的，也可以是实验性的。
- **功能扩展**：扩展允许 Vulkan 添加一些不在核心 API 中的功能。例如，增加对新的硬件特性、图形效果、或计算功能的支持。
- **平台扩展**：某些扩展是针对特定平台的。例如，支持 Windows、Linux 或 Android 上 Vulkan 的特性扩展。

举个例子，一些常见的 Vulkan 扩展包括：
- **VK_EXT_debug_utils** : 为 Vulkan 提供统一、可扩展的调试信息输出和对象标注机制
- **VK_KHR_surface**：提供了一组 **API 来创建和管理“表面（Surface）**

**加载原理**
- 不拦截原 API
- 只是“是否有这组新功能”
- 功能直接由 Driver 或 Loader 实现

### Validation layers

**Validation layers**（验证层）是 Vulkan 的一个重要特性，它主要用于在开发过程中帮助你调试和验证 Vulkan 程序的正确性。它们并不直接影响程序的性能，而是用来捕捉潜在的错误和不符合规范的使用。

从某种角度来看，**验证层（Validation Layers）** 可以被视为 **一种特殊的扩展**，因为它们本质上是在 Vulkan 上层提供额外的功能，但它们并不直接扩展 Vulkan 的核心图形渲染功能，而是为开发者提供错误检查、调试和运行时验证的能力。

- **功能**：验证层会在运行时检查你的 Vulkan 调用是否符合规范，并报告潜在的错误和警告。例如，检查你是否正确地管理了资源，是否按照 Vulkan 的要求调用了正确的函数，或者是否发生了未定义的行为。
- **开发过程中的帮助**：验证层是 Vulkan 开发的一个非常重要的工具，可以帮助开发者快速发现问题，尤其是在学习和调试阶段。

Vulkan 提供了几个验证层：

- **VK_LAYER_KHRONOS_validation**：这是最常用的验证层，它会检查你是否正确地使用 Vulkan API，并提供详细的错误信息和警告。
- **VK_LAYER_LUNARG_standard_validation**：这是一个由第三方（LunarG）提供的标准验证层，也是最常见的一个。

在 Vulkan 中，**验证层（Validation Layers）** 的功能是通过特定的调试工具来呈现的（但并不是必必要的；不过为了更好的使用，通常要配合调试信使相关的扩展来一起使用）。

**加载原理**
- 拦截 Vulkan API 调用
- 可观察、修改、拒绝调用
- 不实现 GPU 功能，只做检查

## 配置调试工具(EXT)
### 创建扩展对象
```cpp
auto func = (PFN_vkCreateDebugUtilsMessengerEXT)vkGetInstanceProcAddr(
	instance, "vkCreateDebugUtilsMessengerEXT");
```
这是调用一个扩展函数，之所以这么做: **Vulkan 的扩展函数根本就不是普通意义上的 API 符号，它们是运行时由 Loader 返回的函数指针**。

### 关于扩展 `VK_EXT_debug_utils`
- 允许你注册一个回调函数
- 接收来自：
    - Validation Layers
    - Loader
    - Driver（少量）
- 的调试消息

使用方式就是使用这个扩展提供的函数指针： `vkCreateDebugUtilsMessengerEXT`

更多功能：
- 提供给对象的命名
- 给 Command Buffer / Queue 插入“标签”
- 被 RenderDoc / Nsight 等 GPU 工具识别

**因此这个扩展的行为更像是一个钩子，可以钩在各个位置上。而调用则是由具体的 validation layers， loader 和 driver来调用。但主要是配合validation layers一起使用**
## 创建 Surface
由GLFW和底层交互，完成创建。

`surface` 是：**Vulkan 用来“往某个窗口显示内容”的平台抽象接口**

作用（surface主要符合和vulkan交互）：
1. 查询设备是否支持展示到这个窗口
2. 查询窗口相关参数（尺寸 / 格式 / 刷新）
3. 创建 Swapchain（**最重要**）

总结：
- `window`：OS 窗口（GLFW 管）
- `surface`：Vulkan 的显示目标抽象
- GLFW 只是帮你把 **OS window → Vulkan surface** 连起来
- surface 为 **swapchain** 服务
- Vulkan **永远不直接操作 window**
## 选择物理设备
主要通过 `vkEnumeratePhysicalDevices` 查询，然后选择一个物理设备对象。留待后续使用。
## 创建逻辑设备
### 配置队列族+创建队列
在 Vulkan 中，**queue（队列）是提交命令到 GPU 的执行通道**。你把已经记录好的 command buffer 提交（`vkQueueSubmit`）到某个 queue，GPU 就按顺序在那个队列上执行这些命令。每个 queue 属于某个 **队列族（queue family）**，同一队列族里的队列通常能执行相同类别的工作（比如支持图形、计算或拷贝）。

更直观的队列族例子：
- 比如：一个 GPU 可能有：
    - Family 0: Graphics + Compute + Transfer，队列数 16
    - Family 1: Compute-only，队列数 8
    - Family 2: Transfer-only，队列数 4

**需要使用的队列组，保存到 `VkDeviceQueueCreateInfo` 的数组，逻辑设备创建的时候提供**

**注意：名字叫 QueueCreateInfo，描述从已有队列族申请队列实例的方式。队列族本身不会被创建或改变，创建逻辑设备时才生成队列实例句柄。**

**这个步骤的做法**
1. 寻找需要的队列族特性：
	1. 利用 `queueFamily.queueFlags & VK_QUEUE_GRAPHICS_BIT` 来查找
	2. 利用 `vkGetPhysicalDeviceSurfaceSupportKHR` 来寻找（这种需要结合外部对象来判断队列能力）
2. 填充 `VkDeviceQueueCreateInfo`
3. 创建逻辑设备的时候，队列就被创建好了。
4. 后续获取方法： `vkGetDeviceQueue`

### 启用的设备特征 (features)
主要填充 `VkPhysicalDeviceFeatures`

### 启用的设备扩展 (extensions)
主要填充字符串数组。类似： `VK_KHR_swapchain` 这种

对比VkInstance的扩展：
![[Vulkan入门-绘制三角形-1764135429992.png]]

### 实例扩展v.s.设备扩展
相似点
- **枚举扩展**
    - 实例扩展：`vkEnumerateInstanceExtensionProperties`
    - 设备扩展：`vkEnumerateDeviceExtensionProperties`
- **启用扩展**
    - 实例扩展：在 `VkInstanceCreateInfo` 中通过 `enabledExtensionCount` 和 `ppEnabledExtensionNames` 指定
    - 设备扩展：在 `VkDeviceCreateInfo` 中通过 `enabledExtensionCount` 和 `ppEnabledExtensionNames` 指定
- **获取扩展函数指针**（如果扩展定义了新函数）
    - 实例扩展函数：使用 `vkGetInstanceProcAddr(instance, "函数名")`
    - 设备扩展函数：使用 `vkGetDeviceProcAddr(device, "函数名")`
- **依赖检查**
    - 在启用之前必须先 **枚举支持的扩展**，否则创建实例/设备会失败。

差异点：
- 实例扩展是全局的，设备扩展仅为单个逻辑设备。后者依赖前者。
## 物理设备v.s.逻辑设备
### 物理设备（`VkPhysicalDevice`）
> **“有什么硬件能力”**
- 一块 GPU（或虚拟 GPU）
- 包含：
    - 支持的特性（geometry shader、ray tracing…）
    - 队列家族（graphics / compute / transfer）
    - 内存类型
    - 支持的格式
- **只读、不能创建资源**
你只能“查”。
### 逻辑设备（`VkDevice`）
> **“我决定怎么用这块硬件”**
- 基于某个 `VkPhysicalDevice` 创建
- 指定：
    - 用哪些 queue family
    - 需要几个 queue
    - 打开哪些 feature
    - 启用哪些扩展
- 之后**所有 Vulkan 操作都用它**

你真正“干活”都靠它。
### 区分两者的好处
1. **性能确定性**:  Vulkan driver不用动态判断，不用兼容你没开却想用的东西。更低CPU开销，驱动路径更短。
2. **多逻辑设备（理论上）** : 更好配合多进程，多上下文，GPU虚拟化。
3. **线程友好设计** ： 逻辑设备提供：明确的 queue ownership、明确的同步边界。


直接用 PhysicalDevice 的问题：
![[Vulkan入门-绘制三角形-1764134227084.png]]

对比OpenGL：
![[Vulkan入门-绘制三角形-1764134269682.png]]
## Vulkan窗口渲染核心模型
关键的元素：
- Surface： Vulkan 用来表示“操作系统窗口表面”的对象。
- SwapChain：Vulkan 中专门用于 **窗口渲染的图像队列**。它维护一组 **可以显示到 surface 的图像（images）**。
- ImageView：`VkImageView` 是对 `VkImage` 的一种“视图”或“接口”。Swapchain 中的每一张图像都是 `VkImage`，但是 Vulkan 的渲染操作（Framebuffer、Pipeline）不能直接操作 `VkImage`，需要通过 `VkImageView`。

![[Vulkan入门-绘制三角形-1764135952685.png]]
## 创建 SwapChain(建立渲染的条件)
从**原理**角度来看，交换链 (Swap Chain) 是连接你的 Vulkan 渲染世界和操作系统的显示窗口的关键。它本质上是一个**生产-消费**缓冲区队列，因此，创建它需要定义生产者（Vulkan 渲染）和消费者（显示器/操作系统）之间的所有关键契约。

创建 $\text{Swap Chain}$ 必须回答的基本问题：
- **在哪里显示？**
- **显示什么？如何显示？**
- **其他显示配置**

### 在哪里显示？(目标)

| **核心设定**                | **对应的代码字段**           | **设定的原理/为什么需要？**                                                                      |
| ----------------------- | --------------------- | ------------------------------------------------------------------------------------- |
| **目标表面 (Surface)**      | $\text{surface}$      | 明确指出交换链创建的图像将要**呈现**到的抽象窗口表面。**这是连接 Vulkan 驱动和操作系统窗口管理器的句柄。**                         |

- **目标表面** ：`createInfo.surface = surface`

### 显示什么？如何显示？(数据)
#### 图像方面 （FrameBuffer相关）
这是关于交换链中每个图像（帧）的**物理属性**和**数据格式**。

| **核心设定**                            | **对应的代码字段**                                     | **设定的原理/为什么需要？**                                                                                                       |
| ----------------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **图像数量 (Minimum Image Count)**      | $\text{minImageCount}$                          | 决定了缓冲区队列的**深度**。$\text{minImageCount}=2$ 是双缓冲。数量越多，可以容忍更大的渲染延迟（例如三缓冲可以提高吞吐量），但会占用更多显存。**这是调度渲染和显示的契约。**                |
| **图像分辨率 (Extent)**                  | $\text{imageExtent}$                            | 图像的像素宽度和高度。它必须与渲染管线中的**视口**和**帧缓冲**配置相匹配。**这是显存分配的基础。**                                                                |
| **图像格式和颜色空间 (Format & Colorspace)** | $\text{imageFormat}$ / $\text{imageColorSpace}$ | 决定了每个像素占用多少**字节**（如 $\text{B8G8R8A8}$），以及像素值应如何**解码**成最终的颜色（如 $\text{SRGB}$）。**这是渲染结果的解释规范。**                          |
| **图像用途 (Usage)**                    | $\text{imageUsage}$                             | 告诉 Vulkan 驱动程序，这些图像在管线中将扮演什么角色，例如：作为**颜色附件** ( $\text{COLOR\_ATTACHMENT\_BIT}$)，还是作为**纹理**来读取。**这是驱动程序内部优化图像资源布局的依据。** |

对应的代码：
- **图像数量**：`createInfo.minImageCount = imageCount;` （通过 `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 来查询得到这个数据）
- **图像分辨率 (Extent)**：`createInfo.imageExtent = extent; ` （同样通过上面的capability，但结合glfw的窗口大小设定）
-  **图像格式 (Format)**：`createInfo.imageFormat = surfaceFormat.format; createInfo.imageColorSpace = surfaceFormat.colorSpace; ` （通过 `vkGetPhysicalDeviceSurfaceFormatsKHR` 来查询） 
- **图像用途 (Usage)**：`createInfo.imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT; ` （常规渲染的用户设定就是颜色附件）
#### 指令方面 （CommandBuffer相关）

| **核心设定**                  | **对应的代码字段**                                              | **设定的原理/为什么需要？**                                                                                     |
| ------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **图像共享模式 (Sharing Mode)** | $\text{imageSharingMode}$ / $\text{pQueueFamilyIndices}$ | 决定了图形队列（生产者）和呈现队列（消费者）对图像的**访问权限**。如果两个队列不同，选择**并发**模式可以消除显式的**所有权转移**步骤，简化同步，提高效率。**这是多队列同步机制的基础。** |
|                           |                                                          |                                                                                                      |
swapchain逻辑上有两个队列：图形队列（生产者）、呈现队列（消费者）

如果物理上也是两个队列，可以并发：
```cpp
createInfo.imageSharingMode = VK_SHARING_MODE_CONCURRENT;
createInfo.queueFamilyIndexCount = 2;
createInfo.pQueueFamilyIndices = queueFamilyIndices;
```
如果物理上是一个队列，需要共享，因此要有锁机制：
```cpp
createInfo.imageSharingMode = VK_SHARING_MODE_EXCLUSIVE;
// 队列可以忽略不用配置，实际上使用的时候需要自己加锁，硬件不保证。
```

注意：队列实际上是用来上传 `commandBuffer` 的队列。swapchain则配置了不同种类 `commandBuffer` 队列如何协同。


### 其他显示配置（呈现模式、Alpha合成、动态变化设置）
这是关于渲染完成的帧如何以及何时被显示器接收和呈现给用户的策略。

| **核心设定**                         | **对应的代码字段**             | **设定的原理/为什么需要？**                                                                                                                                        |
| -------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **呈现模式 (Present Mode)**          | $\text{presentMode}$    | 决定了渲染完成的图像如何被提交给显示器。例如：是等待**垂直消隐**（$\text{V-Sync}$ 模式，消除画面撕裂），还是**立即呈现**（$\text{Immediate}$ 模式，可能撕裂但延迟最低）。**这是控制应用程序帧率和视觉流畅性的关键。**                      |
| **Alpha 合成模式 (Composite Alpha)** | $\text{compositeAlpha}$ | 决定了 $\text{Swap Chain}$ 图像的 $\text{alpha}$ 通道如何与底层的**桌面背景**进行混合。$\text{OPAQUE\_BIT}$（不透明）是常见选择，因为它更简单高效。**这是与窗口管理器（$\text{Window Manager}$）合成最终画面的契约。** |
| **旧交换链引用 (Old Swapchain)**       | $\text{oldSwapchain}$   | 在窗口大小改变时，用于引用旧的、即将被销毁的 $\text{Swap Chain}$。这允许驱动程序在重建过程中**重用资源或图像数据**（如果可能），实现**平滑无缝**的 $\text{Swap Chain}$ 替换。**这是处理窗口动态变化的健壮性要求。**                    |
| **预变换 (Pre-Transform)**          | $\text{preTransform}$   | 告知驱动程序在呈现图像之前，是否需要进行**旋转**、**镜像**等操作，以适应窗口的当前状态（例如手机横屏）。**这允许 GPU 在硬件层面进行高效的最终图像调整。**                                                                   |
| **裁剪 ($\text{clipped}$)**        | clipped                 | 指示驱动程序是否可以放弃渲染被其他窗口遮挡的像素。                                                                                                                               |
- **呈现模式 (Present Mode)** ：`createInfo.presentMode = presentMode;` （默认查询并选择了 `VK_PRESENT_MODE_MAILBOX_KHR` ，取最新渲染好的帧）
- **alpha合成**： 暂时没有设定
- **旧交换链**： 暂时没有设定
- **Pre-Transform** : `createInfo.preTransform = swapChainSupport.capabilities.currentTransform;`
- **裁剪**: `createInfo.clipped = VK_TRUE;`

## 创建 ImageView(创建FrameBuffer接口)
主要代码：
```cpp
vkCreateImageView(device, &createInfo, nullptr,
                            &swapChainImageViews[i]) 
```
最后得到的是 `VkImageView` 数组。即函数最后一个参数。这步也是为了渲染准备。
# Vulkan初始化-渲染相关
## 创建 RenderPass
可以理解为生产1帧图像的，多个工厂的集合（产业集）。每个图像、Attachment，都可以理解为一个原材料仓库。这个层级定义的仓库主要是图像/模板的产出。（此外，还有各种VertexBuffer其实也是原材料，但没有在这个层级定义。）

|**Render Pass 概念**|**工厂比喻**|**对应作用**|
|---|---|---|
|**Render Pass (整体)**|**产业集 / 工厂群**|定义整个帧的生产计划，包含多个工厂（Subpass），规划各工厂如何使用仓库（Attachment）和产出最终产品（Framebuffer）。|
|**Attachment (附件)**|**原材料仓库 / 半成品仓库**|存储渲染所需的原料或半成品（颜色、深度、模板数据）。定义物料的格式和生产前后的状态。|
|**Subpass (子通道)**|**单个工厂 / 车间**|产业集中的具体工厂，每个工厂负责一条或多条生产线（Pipeline）来完成特定生产任务（例如先渲染不透明物体，再渲染透明物体）。|
|**Attachment Reference**|**工厂与仓库的连接**|指示工厂从哪些仓库获取原料，以及将生产结果输出到哪个仓库（颜色输出、深度输入等）。|
|**Subpass Dependency**|**工厂间的物流/依赖关系**|确保工厂之间严格按顺序作业，例如工厂 A 必须完成某些半成品，工厂 B 才能开始生产。|
|**Load Op / Store Op**|**工厂的物料装卸规则**|决定工厂开始生产前是否清空仓库（LOAD_OP_CLEAR），以及生产结束后是否将新产品存回仓库（STORE_OP_STORE）。这是工厂层面的操作，而不是生产线（Pipeline）的操作。|

创建 Render Pass 需要围绕 **“什么数据”、“如何处理”** 和 **“何时处理”** 这三个问题进行定义：
1. **定义附件 (Attachments)：** 描述 Render Pass 将使用的所有图像资源（格式、采样、Load/Store 操作和初始/最终布局）。
2. **定义子通道 (Subpasses)：** 描述渲染管线的实际阶段，并指定每个子通道使用哪些附件作为输入、输出、深度/模板。
3. **定义依赖 (Dependencies)：** 描述子通道之间或子通道与外部操作之间的执行和内存同步。

### 附件(Attachments)
```cpp
VkAttachmentDescription colorAttachment{};
colorAttachment.format = swapChainImageFormat;

colorAttachment.samples = VK_SAMPLE_COUNT_1_BIT;

colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
colorAttachment.storeOp = VK_ATTACHMENT_STORE_OP_STORE;

colorAttachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
colorAttachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;

colorAttachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
colorAttachment.finalLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
```
#### LoadOp 和 StoreOp
注意到有普通的，还有带模板前缀（stencil）的。这是因为，颜色附件的设计是通用的，可以描述：**颜色附件** (Color Attachment)、**深度附件** (Depth Attachment)、**深度/模板附件** (Depth-Stencil Attachment)

这里进一步深入说一下：

|**概念**|**形象化比喻**|**实际作用的精确解释**|
|---|---|---|
|**`loadOp`/`storeOp`** (用于颜色)|**直接写入/读出颜料**|控制渲染管线中 **颜色输出阶段** 对 **颜色附件（Color Attachment）** 的操作。渲染结束后，结果直接覆盖或写入到颜色数据区域。|
|**`loadOp`/`storeOp`** (用于深度)|**写入/读出 Z 坐标卡**|控制渲染管线中 **深度测试阶段** 对 **深度附件** 的操作。它存储每个像素的 $Z$ 深度值，用于比较遮挡关系。|
|**`stencilLoadOp`/`stencilStoreOp`** (用于模板)|**写入/读出“遮罩板”的编号/标记**|控制渲染管线中 **模板测试阶段** 对 **模板附件** 的操作。模板值是一个整数标记，用于 **控制** 哪些像素可以进行颜色写入或深度写入，但 **它本身不是颜色**。|
模板v.s.普通操作：
- 相同点：都写入FrameBuffer。
- 不同点：**模板的作用是控制：** 模板的独特之处在于，它的 **主要功能** 不是存储最终画面数据（像颜色），也不是存储几何深度数据（像深度），而是作为一个 **可编程的掩码或控制机制**。它决定了当前的 Fragment 是否应该通过测试并继续影响颜色或深度缓冲区。

#### finalLayout
当前代码：
```cpp
colorAttachment.finalLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
```
- `finalLayout` 决定了图像在 Render Pass 结束后应处于的 **布局状态**，以便 GPU 知道如何处理后续的操作。不同的配置决定了图像的“下一站”是什么。可能的下一站：
	- 显示到屏幕 (Present)
	- **作为纹理输入**
	- **作为传输源**
	- **作为传输目标
	- 作为下一帧/Render Pass 的颜色附件 : `VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL`
### 子通道(Subpasses)
这个是更加具体的生产线。因此我们在创建具体 Pipeline 的时候要绑定到subpass。

```cppp
VkAttachmentReference colorAttachmentRef{};
colorAttachmentRef.attachment = 0; // 这个代表索引0，和renderPassInfo.pAttachments[0]对应
colorAttachmentRef.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;

VkSubpassDescription subpass{};
subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
subpass.colorAttachmentCount = 1;
subpass.pColorAttachments = &colorAttachmentRef;
```
- `colorAttachmentRef.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;` : 这个布局告诉 **GPU 驱动程序** 和 **管线**：在 **当前这个 Subpass (子通道) 执行期间**，这个图像将作为 **颜色附件** 被写入。（工作状态）
	- 而颜色附件描述的 `finalLayout` 则是颜色附件最终的走向。（Render Pass结束时，最终状态）
- `VK_PIPELINE_BIND_POINT_GRAPHICS` : 代表这个subpass是用来被 GraphicsPipeline绑定的。即这是个图形生产线。
	- 另一种选择是： `VK_PIPELINE_BIND_POINT_COMPUTE` 。意味着绑定的是计算生产线。
### 依赖(Dependencies)
这里主要设定subpass生产线工作的依赖条件。可以是其他subpass，也可以是颜色附件的状态（`VK_SUBPASS_EXTERNAL`）。
```cpp
VkSubpassDependency dependency{};
dependency.srcSubpass = VK_SUBPASS_EXTERNAL;
dependency.dstSubpass = 0; // 索引为0的subpass
dependency.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
dependency.srcAccessMask = 0;
dependency.dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
dependency.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
```
类比：
- subpass:
	- src: 上一个人。
	- dst: 下一个人。
- stage:（关心的步骤）
	- src: 上一个人执行到步骤 srcStage （等待触发的条件，如果src正处于这个阶段）
	- dst: 下一个人开始执行步骤 dstStage（等待触发的时刻，dst要进入这个阶段）
- access:（关心的具体做了什么）
	- src: 上一个人需完成的动作 srcAccess（等待触发的条件，如果src正在完成某个访问）
	- dst: 下一个人将要完成的动作 dstAccess（等待触发的时刻，dst要执行某个访问）

用一句话简单描述：
**当下一个人（将要进入 dstStage&&dstAccess 所定义的状态时），需要看一下上一个人（src是否在 srcStage &&  srcAccess 所定义的状态；如果在，则等待其离开）**。

代码里的，效果来说：
1. 当subpass执行到要对颜色附件写入阶段，并且要获取AccessMask的动作时：
2. 如果由外部过程正处于对颜色附件写入的状态时（不管它Access是什么样的），此时等待其完成。

注意：这个描述当空条件的时候，dst也会执行的。即，并不是dst依赖src的完成，而仅仅关注是否有src处于描述中的状态，仅等待这个状态而已。
## 创建 GraphicsPipeline
考虑subpass类比为一个工厂/车间，那么Pipeline则是一个具体的生产线。而生产线的各个部分的定义可以类比：

| **Pipeline 配置项**           | **生产线比喻**        | **对应作用**                                    |
| -------------------------- | ---------------- | ------------------------------------------- |
| **Shader Stage（顶点/片段着色器）** | **工人技能**         | 决定生产线上工人如何加工原料（顶点/片段数据）。                    |
| **Vertex Input**           | **原料装配台**        | 定义原料规格和布局（顶点属性、缓冲区绑定）。                      |
| **Input Assembly**         | **工序顺序**         | 定义如何把原料组合成半成品（三角形列表、带、扇等）。                  |
| **Viewport / Scissor**     | **操作区域 / 工作台范围** | 决定工人在哪个区域操作，哪些区域允许加工。                       |
| **Dynamic State**          | **可调节工作台**       | 可在生产过程中灵活调整参数（视口、剪裁等）。                      |
| **Rasterizer**             | **模具 / 加工方式**    | 决定半成品如何变成最终产品（填充模式、剔除模式、线宽）。                |
| **Multisampling**          | **品质控制工序**       | 决定产品的平滑度和抗锯齿质量。                             |
| **Depth / Stencil**        | **质量检测工序**       | 判断半成品覆盖情况或是否允许加工。                           |
| **Color Blend**            | **上色 / 涂装工序**    | 决定最终产品颜色如何叠加。                               |
| **Pipeline Layout**        | **工人手册 / 工具**    | 定义工人可以使用的工具（uniform buffer、push constants）。 |
通过这个表可以看出，我们如果需要具体渲染，主要就是和 GraphicsPipeline 打交道。这里每个生产线最终产出的都是一个framebuffer。
### Shader Stage
这个很容易理解，就是原本图形接口的各个shader，我们需要编译好。把它装配到流水线上。因为它比较灵活，所以理解为流水线上的工人也没有问题。

```cpp
auto vertShaderCode = readFile("./build/shaders/shader.vert.spv");
auto fragShaderCode = readFile("./build/shaders/shader.frag.spv");

auto vertShaderModule = createShaderModule(vertShaderCode);
auto fragShaderModule = createShaderModule(fragShaderCode);

VkPipelineShaderStageCreateInfo vertShaderStageInfo{};
vertShaderStageInfo.sType =
	VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
vertShaderStageInfo.stage = VK_SHADER_STAGE_VERTEX_BIT;
vertShaderStageInfo.module = vertShaderModule;
vertShaderStageInfo.pName = "main";

VkPipelineShaderStageCreateInfo fragShaderStageInfo{};
fragShaderStageInfo.sType =
	VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
fragShaderStageInfo.stage = VK_SHADER_STAGE_FRAGMENT_BIT;
fragShaderStageInfo.module = fragShaderModule;
fragShaderStageInfo.pName = "main";

VkPipelineShaderStageCreateInfo shaderStages[] = {vertShaderStageInfo,
												  fragShaderStageInfo};
												  
// ...忽略中间
// 最后需要释放掉创建的shaderModule
vkDestroyShaderModule(device, fragShaderModule, nullptr);
vkDestroyShaderModule(device, vertShaderModule, nullptr);
```
### **Vertex Input**（VertexBuffer格式）
定义原料规格和布局（顶点属性、缓冲区绑定）。

我们这里没有用外部的顶点数据。所以没设置。
```cpp
VkPipelineVertexInputStateCreateInfo vertexInputInfo{};
vertexInputInfo.sType =
	VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO;
vertexInputInfo.vertexBindingDescriptionCount = 0;
vertexInputInfo.pVertexBindingDescriptions = nullptr; // Optional
vertexInputInfo.vertexAttributeDescriptionCount = 0;
vertexInputInfo.pVertexAttributeDescriptions = nullptr; // Optional
```

如果使用顶点数据，考虑顶点数据结构：
```cpp
struct Vertex {
    glm::vec2 pos;    // 位置
    glm::vec3 color;  // 颜色
};
```
- `pos` 对应 `location = 0`
- `color` 对应 `location = 1`
- (location是在shader中绑定这些变量的描述)

那么：顶点缓冲区绑定描述（Vertex Binding）
```cpp
VkVertexInputBindingDescription bindingDescription{};
bindingDescription.binding = 0;                        // 绑定点 0
bindingDescription.stride = sizeof(Vertex);             // 每个顶点占用字节
bindingDescription.inputRate = VK_VERTEX_INPUT_RATE_VERTEX; // 每个顶点变化一次
```
- 这里是每顶点模式（用顶点渲染的指令），还有每实例模式（需要用实例渲染的一些指令）。
	- 差别在于，vertex shader在每顶点模式处理所有顶点，比较基础的处理方式；在每实例模式，顶点数据虽然只有一份但是按照实例数目来处理多次（不同的实例，顶点数据可以复用；此外，通过额外传入实例的特有信息来辅助处理，比如索引、矩阵等等）

顶点属性描述（Vertex Attributes）
```cpp
std::array<VkVertexInputAttributeDescription, 2> attributeDescriptions{};

// 位置属性
attributeDescriptions[0].binding = 0;                // 对应绑定点 0
attributeDescriptions[0].location = 0;               // shader 中 location 0
attributeDescriptions[0].format = VK_FORMAT_R32G32_SFLOAT; // vec2
attributeDescriptions[0].offset = offsetof(Vertex, pos);

// 颜色属性
attributeDescriptions[1].binding = 0;                // 同绑定点 0
attributeDescriptions[1].location = 1;               // shader 中 location 1
attributeDescriptions[1].format = VK_FORMAT_R32G32B32_SFLOAT; // vec3
attributeDescriptions[1].offset = offsetof(Vertex, color);
```

最后就是 更新 `VkPipelineVertexInputStateCreateInfo` 。
```cpp
VkPipelineVertexInputStateCreateInfo vertexInputInfo{};
vertexInputInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO;
vertexInputInfo.vertexBindingDescriptionCount = 1;
vertexInputInfo.pVertexBindingDescriptions = &bindingDescription;
vertexInputInfo.vertexAttributeDescriptionCount = static_cast<uint32_t>(attributeDescriptions.size());
vertexInputInfo.pVertexAttributeDescriptions = attributeDescriptions.data();
```

### **Input Assembly**（IndexBuffer格式）
```cpp
VkPipelineInputAssemblyStateCreateInfo inputAssembly{};
inputAssembly.sType =
	VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO;
inputAssembly.topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST;
inputAssembly.primitiveRestartEnable = VK_FALSE;
```
主要描述顶点所组成的图元。但是没有描述顶点的连接关系。但图元关系的确认，会影响到 IndexBuffer的解析。不同的定义方式，会按照不同方法来解析IndexBuffer。

### **Viewport / Scissor**
视口和裁剪的设定。这个相对比较容易。不解释。

### **Dynamic State**
这里把 视口和裁剪的设定。 也设置为了 **Dynamic State** 。所谓 **Dynamic State** ，是Pipeline创建好了之后，每次渲染的时候，可以动态变更的参数。
### Rasterizer
```cpp
// rasterizer配置
VkPipelineRasterizationStateCreateInfo rasterizer{};
rasterizer.sType =
	VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO;
rasterizer.depthClampEnable = VK_FALSE;
rasterizer.rasterizerDiscardEnable = VK_FALSE;
rasterizer.polygonMode = VK_POLYGON_MODE_FILL;
// Using any mode other than fill requires enabling a GPU feature.
// 如果用不是1.0f的值，需要开启 wide lines 功能
rasterizer.lineWidth = 1.0f;
rasterizer.cullMode = VK_CULL_MODE_BACK_BIT;
rasterizer.frontFace = VK_FRONT_FACE_CLOCKWISE;

rasterizer.depthBiasEnable = VK_FALSE;
rasterizer.depthBiasConstantFactor = 0.0f; // Optional
rasterizer.depthBiasClamp = 0.0f;          // Optional
rasterizer.depthBiasSlopeFactor = 0.0f;    // Optional
```
光栅化流程的参数设置。定义顶点（或者说图元）到片元的转化规则。
### Multisampling
多重采样设置。画三角形没开启。
### Depth/Stencil
深度和模板测试。画三角形没开启。
### **Color Blend**
颜色融合。画三角形没开启。
### Pipeline Layout
```cpp
// Pipeline Layout 定义 shader 资源布局
// 说明 shader 能访问哪些资源（Uniform Buffer, Texture, Storage Buffer 等）
// 以及绑定点和 Push Constants 的范围

VkPipelineLayoutCreateInfo pipelineLayoutInfo{};
pipelineLayoutInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
pipelineLayoutInfo.setLayoutCount = 0;            // Optional
pipelineLayoutInfo.pSetLayouts = nullptr;         // Optional
pipelineLayoutInfo.pushConstantRangeCount = 0;    // Optional
pipelineLayoutInfo.pPushConstantRanges = nullptr; // Optional
```
uniform buffer可以理解为把对shader预留一些dynamic state出来，在渲染的时候可以动态改变。这里layout定义，主要定义这些变量如何映射到shader的环境中。


更准确的描述：
- **Pipeline Layout** 并不是具体存储 uniform buffer 的内容，它只是 **定义 shader 的资源接口**：
    - **Descriptor Set Layouts**（`pSetLayouts`）：定义哪些资源（Uniform Buffer, Storage Buffer, Texture 等）会被绑定到 shader，以及它们在 shader 里对应的 binding。
    - **Push Constants**（`pPushConstantRanges`）：定义一小块快速更新的数据范围，也会映射到 shader 里。
        
> 换句话说，它是 **shader 资源布局的“描述表”**，告诉 Vulkan 管线在渲染时 shader 会访问哪些资源以及如何访问。


## 创建 FrameBuffers
做法很显然，根据swapchain中的imageview来创建即可。
```cpp
VkImageView attachments[] = {swapChainImageViews[i]};

VkFramebufferCreateInfo framebufferInfo{};
framebufferInfo.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
framebufferInfo.renderPass = renderPass;
framebufferInfo.attachmentCount = 1;
framebufferInfo.pAttachments = attachments;
framebufferInfo.width = swapChainExtent.width;
framebufferInfo.height = swapChainExtent.height;
framebufferInfo.layers = 1;
```

值得注意的是：framebuffer可以绑定多个 attachment。所以严格来说一个framebuffer可以关联大量图片资源。当然这些如果先渲染中想要用到，必须在renderpass和subpass中绑定。

因此真正渲染工作的时候，可以猜测是需要 framebuffer和renderpass绑定。同时它们的attachments定义要能够配对上。

**Framebuffer 与 RenderPass 的关系**
- `VkFramebuffer` 是对一组 `VkImageView` 的封装，表示某次渲染将会使用的具体图像资源。
- 每个 `Framebuffer` 必须绑定一个 `RenderPass`。
- 绑定的 `RenderPass` 决定了这个 `Framebuffer` 中的 attachments 的 **数量、格式、样式（load/store ops）**。
- **关键**：`Framebuffer` 的 attachments 数量和顺序 **必须和 RenderPass 的 attachment 描述完全匹配**。

## 创建 CommandPool
```cpp
QueueFamilyIndices queueFamilyIndices = findQueueFamilies(physicalDevice);

// 创建图形指令的命令池
VkCommandPoolCreateInfo poolInfo{};
poolInfo.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
poolInfo.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
poolInfo.queueFamilyIndex = queueFamilyIndices.graphicsFamily.value();

if (vkCreateCommandPool(device, &poolInfo, nullptr, &commandPool) !=
	VK_SUCCESS) {
  throw std::runtime_error("failed to create command pool!");
}
```
**队列（Queue）和 `vkGetQueue`**
- 队列是 GPU 执行命令的“通道”，每个队列属于某个队列族（Queue Family）。
- `vkGetQueue(device, queueFamilyIndex, 0, &queue)` 得到的只是一个 **句柄**，可以用它提交命令执行。
- 队列本身**不存储命令**，它只是执行命令的管道。

**CommandPool 的作用**
- `VkCommandPool` 是 **分配命令缓冲区 (CommandBuffer) 的内存池**。
- 它是 GPU 内存管理的一层封装，用来高效管理命令缓冲区的创建、重置和回收。
- 创建命令缓冲区（CommandBuffer）**必须依附于某个 CommandPool**。
- CommandPool 与 **队列族绑定**，也就是这个 pool 创建出来的命令缓冲区只能提交给这个队列族的队列。

**CommandBuffer 的作用**
- `CommandBuffer` 是实际记录 GPU 命令的容器（画图、复制、计算、内存屏障等）。
- 你 **不能直接往队列里提交绘制操作**，必须先把操作记录到 CommandBuffer。
- CommandBuffer 的生命周期由 CommandPool 管理。

总结：
- 队列（Queue） = 执行命令的管道。
- CommandPool = 管理命令缓冲区的“内存池”，绑定到特定队列族。
- CommandBuffer = 真正记录 GPU 命令的对象，需要从 CommandPool 分配。
## 创建 CommandBuffers
很显然，根据swapchain中image数量创建即可。创建需要使用到 commandPool
```cpp
commandBuffers.resize(swapChainImageViews.size());

VkCommandBufferAllocateInfo allocInfo{};
allocInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
allocInfo.commandPool = commandPool;
allocInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
allocInfo.commandBufferCount = (uint32_t)commandBuffers.size();
```
## 总结
根据渲染相关的描述。我们大概可以猜到，真正渲染的时候：
- renderpass 和 framebuffer绑定，设定为当前上下文。
- commandbuffer记录指令，提交给GPU
- 呈现相关指令，也许要提交到呈现队列。
# Vulkan初始化-同步工具
## 创建 SyncObjects
由于大部分工作都是通过队列提交到GPU的。并且有可能还会使用不同的队列。因此，明显涉及到同步问题。所以我们需要用到GPU上的同步对象。

```cpp
std::vector<VkSemaphore> imageAvailableSemaphores;
std::vector<VkSemaphore> renderFinishedSemaphores;
std::vector<VkFence> inFlightFences;
  
imageAvailableSemaphores.resize(MAX_FRAMES_IN_FLIGHT);
renderFinishedSemaphores.resize(MAX_FRAMES_IN_FLIGHT);
inFlightFences.resize(MAX_FRAMES_IN_FLIGHT);
```
对每个framebuffer使用1套同步工具：
- 信号量：
	- imageAvailableSemaphores： 可以渲染了
	- renderFinishedSemaphores： 渲染结束了
- Fence：
	- inFlightFences：当前framebuffer的上一帧还没有画完，此时等待fence。等待成功了，reset让其再次被启动。
	- `vkQueueSubmit` 这个动作完成后，会释放fence。
# Vulkan主循环
## 每帧渲染函数
### 等上一帧结束
保证 GPU 里用到同一条 CommandBuffer 的上一帧已经跑完，CPU 才继续。
```cpp
vkWaitForFences(inFlightFences[currentFrame])  
```

### 拿一张交换链图像
返回 OUT_OF_DATE / SUBOPTIMAL 就重建 swapChain 并提前 return。
```cpp
vkAcquireNextImageKHR → imageIndex
```
### 重置“帧内”同步对象
把 fence 重新置为“未触发”，把 CB 清零准备重新记录。
```cpp
vkResetFences(inFlightFences[currentFrame])
vkResetCommandBuffer(commandBuffers[currentFrame])
```

### 记录绘制命令
```cpp
recordCommandBuffer(commandBuffers[currentFrame], imageIndex)
```
### 提交给图形队列
```cpp
vkQueueSubmit(graphicsQueue, &submitInfo, inFlightFences[currentFrame])
```
submitInfo 里：
- 等 `imageAvailableSemaphores[currentFrame]  @ COLOR_ATTACHMENT_OUTPUT` 
- 执行完 signal `renderFinishedSemaphores[currentFrame]`
### 呈现
```cpp
vkQueuePresentKHR(presentQueue, &presentInfo)
```
presentInfo 里：
‑ 等 `renderFinishedSemaphores[currentFrame]`

### 轮转“飞行帧”索引
```cpp
currentFrame = (currentFrame + 1) % MAX_FRAMES_IN_FLIGHT
```

## RecordCommandBuffer
### 指令录制开始
```cpp
    VkCommandBufferBeginInfo beginInfo{};
    beginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    beginInfo.flags = 0;                  // Optional
    beginInfo.pInheritanceInfo = nullptr; // Optional
    if (vkBeginCommandBuffer(commandBuffer, &beginInfo) != VK_SUCCESS) {
      throw std::runtime_error("failed to begin recording command buffer!");
    }
```

### RenderPass开始(绑定FrameBuffer)
```cpp
    VkRenderPassBeginInfo renderPassInfo{};
    renderPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO;
    renderPassInfo.renderPass = renderPass;
    // 绑定帧
    renderPassInfo.framebuffer = swapChainFramebuffers[imageIndex];
    // 设定渲染区域
    renderPassInfo.renderArea.offset = {0, 0};
    renderPassInfo.renderArea.extent = swapChainExtent;
    // 设定clear value
    VkClearValue clearColor = {{0.0f, 0.0f, 0.0f, 1.0f}};
    renderPassInfo.clearValueCount = 1;
    renderPassInfo.pClearValues = &clearColor;
    // 启动render pass
    vkCmdBeginRenderPass(commandBuffer, &renderPassInfo,
                         VK_SUBPASS_CONTENTS_INLINE);
```

### 开始绘制(绑定CB, 绑定Pipeline)
```cpp
    // 绑定管线
    vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
                      graphicsPipeline);

    // 设定动态变量
    VkViewport viewport{};
    viewport.x = 0.0f;
    viewport.y = 0.0f;
    viewport.width = static_cast<float>(swapChainExtent.width);
    viewport.height = static_cast<float>(swapChainExtent.height);
    viewport.minDepth = 0.0f;
    viewport.maxDepth = 1.0f;
    vkCmdSetViewport(commandBuffer, 0, 1, &viewport);

    VkRect2D scissor{};
    scissor.offset = {0, 0};
    scissor.extent = swapChainExtent;
    vkCmdSetScissor(commandBuffer, 0, 1, &scissor);

    // !!绘制三角形啦 （包饺子啦；其他代码都是为了这盘饺子准备的工具和馅料 ）
    vkCmdDraw(commandBuffer, 3, 1, 0, 0);
```

如果要上传VertexBuffer或者IndexBuffer。更应该在初始化中做。

而在渲染命令前，如果用VB和IB，那么需要在Draw绑定它们。最后用 `vkCmdDrawIndexed` 。

### RenderPass结束
略
### 指令录制结束
略


# 三角形数据呢？
为了简化这个例子。数据直接写到了 vertex shader中。

## Vertex Shader
```vert
#version 450

layout(location = 0) out vec3 fragColor;

vec2 positions[3] = vec2[](
    vec2(0.0, -0.5),
    vec2(0.5, 0.5),
    vec2(-0.5, 0.5)
);

vec3 colors[3] = vec3[](
    vec3(1.0, 0.0, 0.0),
    vec3(0.0, 1.0, 0.0),
    vec3(0.0, 0.0, 1.0)
);

void main() {
    gl_Position = vec4(positions[gl_VertexIndex], 0.0, 1.0);
    fragColor = colors[gl_VertexIndex];
}
```
这里。 `gl_VertexIndex` 是渲染指令触发，传递给每个shader调用的。

## Fragment Shader
```frag
#version 450

layout(location = 0) in vec3 fragColor;

layout(location = 0) out vec4 outColor;

void main() {
    outColor = vec4(fragColor, 1.0);
}
```
没做任何操作。直接输出颜色。（注意颜色插值是管线的固定流程自动计算的）