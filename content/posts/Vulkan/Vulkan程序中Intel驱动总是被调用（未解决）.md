---
title: Vulkan程序中Intel驱动总是被调用（未解决）
date: 2025-11-21T12:53:06+08:00
tags:
  - vulkan
  - intel
  - debug
  - windbg
draft: false
---

这篇文章是闲暇时候的探索，并没有真正解决问题。
<!--more-->
## 正文开始
之前调试神秘日志的时候，打印堆栈和文件操作，发现有大量intel驱动程序的调用，并且打开了特别多的文件。不知道为什么。

我们这次也深入研究一下。先手动在程序中设定环境变量： （环境变量设定笔记：TODO ）

这里罗列一下代码：
```cpp
#include "utils.h"
#ifdef _WIN32
#include <windows.h>
#else
#include <stdlib.h>
#endif

void expSetEnvVK() {
#ifdef _WIN32
  SetEnvironmentVariableW(L"VK_LOADER_LAYERS_DISABLE", L"~implicit~");
#else
  setenv("VK_LOADER_LAYERS_DISABLE", "~implicit~", 1);
#endif
}
```


检查环境变量是否设定成功，等程序完成该函数的调用后，执行下面命令查看进程环境变量：
```
!peb
```

不过，即使设定了环境变量，我们断点 
```
bp KERNELBASE!CreateFileW "r rcx; du @rcx; k L3; g"
```

日志目前不产生了。但是，仍然会有大量的打开文件操作。

从堆栈可以看出：
```
[0x0]   igvk64!ctlTemperatureGetState+0x73ea6a   0xcb4b753750   0x7ff9329718a0   
[0x1]   igvk64!ctlTemperatureGetState+0x73c020   0xcb4b753b40   0x7ff93296ecfb   
[0x2]   igvk64!ctlTemperatureGetState+0x73947b   0xcb4b753ce0   0x7ff93296e00b   
[0x3]   igvk64!ctlTemperatureGetState+0x73878b   0xcb4b753d20   0x7ff932964276   
[0x4]   igvk64!ctlTemperatureGetState+0x72e9f6   0xcb4b753d70   0x7ff93211040f   
[0x5]   igvk64!DumpRegistryKeyDefinitions+0x1c605f   0xcb4b753ee0   0x7ff9321007fb   
[0x6]   igvk64!DumpRegistryKeyDefinitions+0x1b644b   0xcb4b7544e0   0x7ff9320e76a4   
[0x7]   igvk64!DumpRegistryKeyDefinitions+0x19d2f4   0xcb4b754650   0x7ff9320d1bd5   
[0x8]   igvk64!DumpRegistryKeyDefinitions+0x187825   0xcb4b754700   0x7ff9320431e6   
[0x9]   igvk64!DumpRegistryKeyDefinitions+0xf8e36   0xcb4b754750   0x7ff932027534   
[0xa]   igvk64!DumpRegistryKeyDefinitions+0xdd184   0xcb4b76b960   0x7ff931ffec7d   
[0xb]   igvk64!DumpRegistryKeyDefinitions+0xb48cd   0xcb4b76b9d0   0x7ff931f80ca5   
[0xc]   igvk64!DumpRegistryKeyDefinitions+0x368f5   0xcb4b76ba20   0x7ff9378dc6dc   
[0xd]   vulkan_1!vkResetEvent+0x4b14c   0xcb4b76baf0   0x7ff9378c3652   
[0xe]   vulkan_1!vkResetEvent+0x320c2   0xcb4b76bc50   0x7ff9378e751e   
[0xf]   vulkan_1!vkResetEvent+0x55f8e   0xcb4b76be40   0x7ff630566b2f   
[0x10]   VulkanGLFWDemo+0x6b2f   0xcb4b76f250   0x7ff630567e80   

```

因为是release外加关闭了implicit layers。所以没有任何validation layers干扰。但是，vulkan还是会产生大量 igvk64模块的调用。
## AI解释
`igvk64` 很可能是 Intel 的 Vulkan ICD / 驱动相关模块（或 Intel GPU 的 Vulkan 支持库/监控库）。Vulkan loader 在进程初始化 / 创建实例时会把系统里注册的所有 ICD（以及某些层）都载入并初始化——因此即便你最后用的是 NVIDIA 的物理设备，Intel 的 ICD 也可能会被加载并执行初始化代码（查询注册表、查询温度/设备信息、打开设备/日志文件等），这就会看到大量 `CreateFileW` / 注册表读取 等操作，堆栈里就会出现 `igvk64` 的函数。

**关于ICD机制，更多参见：** [[posts/Vulkan/Vulkan的ICD机制|Vulkan的ICD机制]]


## 手动加载ICD后
新增环境变量设定：
```
VK_DRIVER_FILES=C:\WINDOWS\System32\DriverStore\FileRepository\nvmi.inf_amd64_c6ae241e95feb82d\nv-vk64.json
```

代码的方式：
```cpp
#include "utils.h"
#ifdef _WIN32
#include <windows.h>
#else
#include <stdlib.h>
#endif

void expSetEnvVK() {
#ifdef _WIN32
  SetEnvironmentVariableW(
      L"VK_DRIVER_FILES",
      LR"(C:\WINDOWS\System32\DriverStore\FileRepository\nvmi.inf_amd64_c6ae241e95feb82d\nv-vk64.json)");

  SetEnvironmentVariableW(L"VK_LOADER_LAYERS_DISABLE", L"~implicit~");
#else
  setenv(
      "VK_DRIVER_FILES",
      R"(C:\WINDOWS\System32\DriverStore\FileRepository\nvmi.inf_amd64_c6ae241e95feb82d\nv-vk64.json)",
      1);
  setenv("VK_LOADER_LAYERS_DISABLE", "~implicit~", 1);
#endif
}

```


测试结果：设定成功后

1. 产生大量 nvogl的调用（这个可能符合预期）

```
[0x0]   KERNEL32!CreateFileW   0xc5662fabc8   0x7ff908effb25   
[0x1]   nvoglv64!vk_icdNegotiateLoaderICDInterfaceVersion+0xcc8a5   0xc5662fabd0   0x7ff908f00511   
[0x2]   nvoglv64!vk_icdNegotiateLoaderICDInterfaceVersion+0xcd291   0xc5662fac30   0x7ff90843a853   
[0x3]   nvoglv64+0xdaa853   0xc5662facb0   0x7ff90843a8b6   
[0x4]   nvoglv64+0xdaa8b6   0xc5662fafc0   0x7ff90843a8b6   
[0x5]   nvoglv64+0xdaa8b6   0xc5662fb2d0   0x7ff908439f6a   
[0x6]   nvoglv64+0xda9f6a   0xc5662fb5e0   0x7ff90843ae26   
[0x7]   nvoglv64+0xdaae26   0xc5662fb630   0x7ff90843acb9   
[0x8]   nvoglv64+0xdaacb9   0xc5662fb680   0x7ff90843a6fe   
[0x9]   nvoglv64+0xdaa6fe   0xc5662fb6d0   0x7ff9084385cb   
[0xa]   nvoglv64+0xda85cb   0xc5662fb700   0x7ff908dcca46   
[0xb]   nvoglv64!vkGetInstanceProcAddr+0x94276   0xc5662fb760   0x7ff908dcaf50   
[0xc]   nvoglv64!vkGetInstanceProcAddr+0x92780   0xc5662fb9e0   0x7ff908dc7e46   
[0xd]   nvoglv64!vkGetInstanceProcAddr+0x8f676   0xc5662fba30   0x7ff908dc8e4a   
[0xe]   nvoglv64!vkGetInstanceProcAddr+0x9067a   0xc5662fc1c0   0x7ff908dc7b6c   
[0xf]   nvoglv64!vkGetInstanceProcAddr+0x8f39c   0xc5662fc200   0x7ff93b99c6dc   
[0x10]   vulkan_1!vkResetEvent+0x4b14c   0xc5662fc230   0x7ff93b983652   
[0x11]   vulkan_1!vkResetEvent+0x320c2   0xc5662fc380   0x7ff93b9a751e   
[0x12]   vulkan_1!vkResetEvent+0x55f8e   0xc5662fc570   0x7ff6972b6b33   
[0x13]   VulkanGLFWDemo+0x6b33   0xc5662ff980   0x7ff6972b7e80   
[0x14]   VulkanGLFWDemo+0x7e80   0xc5662ffac0   0x7ff6972b95d4   
[0x15]   VulkanGLFWDemo+0x95d4   0xc5662ffc30   0x7ff6972ba2bf   
[0x16]   VulkanGLFWDemo+0xa2bf   0xc5662ffc80   0x7ff6972cb54c   
[0x17]   VulkanGLFWDemo+0x1b54c   0xc5662ffe70   0x7ffa4389e8d7   
[0x18]   KERNEL32!BaseThreadInitThunk+0x17   0xc5662ffeb0   0x7ffa4520c53c   
[0x19]   ntdll!RtlUserThreadStart+0x2c   0xc5662ffee0   0x0   

```

2. 还会产生intel的驱动调用：

```
000001b2`2e445620  "C:\Users\develop\AppData\LocalLo"
000001b2`2e445660  "w\Intel\ShaderCache\42c265904c15"
000001b2`2e4456a0  "3bce841ce64ab3cda0f27c76e6b1e7c0"
000001b2`2e4456e0  "efcc9de2f1082fe2a43e"
 # Child-SP          RetAddr               Call Site
00 00000005`274fdb08 00007ffa`0324e16a     KERNEL32!CreateFileW
01 00000005`274fdb10 00007ffa`0324b720     igxelpicd64!DumpRegistryKeyDefinitions+0xb43aa
02 00000005`274fdf00 00007ffa`03248cfb     igxelpicd64!DumpRegistryKeyDefinitions+0xb1960
03 00000005`274fe0a0 00007ffa`0324800b     igxelpicd64!DumpRegistryKeyDefinitions+0xaef3b
04 00000005`274fe0e0 00007ffa`0323be16     igxelpicd64!DumpRegistryKeyDefinitions+0xae24b
05 00000005`274fe130 00007ffa`030fce7c     igxelpicd64!DumpRegistryKeyDefinitions+0xa2056
06 00000005`274fe2a0 00007ffa`030fb59e     igxelpicd64!DrvValidateVersion+0x13c57c
07 00000005`274fe870 00007ffa`030ee572     igxelpicd64!DrvValidateVersion+0x13ac9e
08 00000005`274fe8b0 00007ffa`02fbf6aa     igxelpicd64!DrvValidateVersion+0x12dc72
09 00000005`274fe8f0 00007ffa`2a8aacfe     igxelpicd64!DrvDescribePixelFormat+0x3a
0a 00000005`274fe940 00007ffa`2a8ed7e9     opengl32!_DescribeDriverPixelFormat+0x5a
0b 00000005`274fe980 00007ffa`2a886e9f     opengl32!LoadAvailableDrivers+0x3d9
0c 00000005`274fefe0 00007ff9`08d2005c     opengl32!wglDescribePixelFormat+0xdf
0d 00000005`274ff120 00007ff9`08d23622     nvoglv64!vk_optimusGetInstanceProcAddr+0x230ec
0e 00000005`274ff150 00007ff9`08d1cfd7     nvoglv64!vk_optimusGetInstanceProcAddr+0x266b2
0f 00000005`274ff1a0 00007ff9`3b9ad9cc     nvoglv64!vk_optimusGetInstanceProcAddr+0x20067
10 00000005`274ff1d0 00007ff9`3b9af465     vulkan_1!vkResetEvent+0x5c43c
11 00000005`274ff2c0 00007ff6`972b72e2     vulkan_1!vkResetEvent+0x5ded5
12 00000005`274ff300 00007ff6`972b7f29     VulkanGLFWDemo+0x72e2
13 00000005`274ff470 00007ff6`972b95d4     VulkanGLFWDemo+0x7f29
14 00000005`274ff5e0 00007ff6`972ba2bf     VulkanGLFWDemo+0x95d4
15 00000005`274ff630 00007ff6`972cb54c     VulkanGLFWDemo+0xa2bf
16 00000005`274ff820 00007ffa`4389e8d7     VulkanGLFWDemo+0x1b54c
17 00000005`274ff860 00007ffa`4520c53c     KERNEL32!BaseThreadInitThunk+0x17
18 00000005`274ff890 00000000`00000000     ntdll!RtlUserThreadStart+0x2c
```


## AI的解释

### 1. NVIDIA Optimus/AMD Switchable Graphics

您运行的系统几乎肯定是一个拥有**集成显卡 (Intel)** 和 **独立显卡 (NVIDIA)** 的笔记本电脑。

- **集成显卡 (Intel iGPU):** 通常直接连接到显示器，负责低功耗下的桌面显示和简单图形渲染。
    
- **独立显卡 (NVIDIA dGPU):** 负责高性能渲染。
    

**Optimus 的工作机制：** NVIDIA 的 Optimus 技术允许应用程序启动时默认使用低功耗的 **Intel iGPU**。如果应用程序需要高性能（例如，一个 3D 游戏或 Vulkan/OpenGL 程序），NVIDIA 的驱动程序会**拦截**图形 API 调用，并将渲染工作交给 **NVIDIA dGPU** 完成。**渲染完成后，dGPU 将结果帧通过 PCIe/内部总线复制回 iGPU 的帧缓冲区，再由 iGPU 将画面输出到显示器。**

### 2. OpenGL/WGL 路径依赖 ⚠️

您的堆栈跟踪（Stack Trace）清晰地显示了调用链经过了 **OpenGL/WGL** 的函数：

```
09 00000005`274fe8f0 00007ffa`2a8aacfe igxelpicd64!DrvDescribePixelFormat+0x3a
0a 00000005`274fe940 00007ffa`2a8ed7e9 opengl32!_DescribeDriverPixelFormat+0x5a
0b 00000005`274fe980 00007ffa`2a886e9f opengl32!LoadAvailableDrivers+0x3d9
0c 00000005`274fefe0 00007ff9`08d2005c opengl32!wglDescribePixelFormat+0xdf
0d 00000005`274ff120 00007ff9`08d23622 nvoglv64!vk_optimusGetInstanceProcAddr+0x230ec
```

**关键点：**
- 虽然您在使用 Vulkan (`vulkan_1.dll`), 但您的程序可能使用了像 **GLFW** 或类似的跨平台窗口库来创建窗口表面。
- 在 Windows 上，这些库在创建窗口或进行必要的初始化时，往往会调用 **OpenGL/WGL** 相关的函数（例如 `wglDescribePixelFormat`），即使目标是 Vulkan。
- 在 Optimus 系统上，这个 **WGL 调用** 默认被路由到 **Intel iGPU 的驱动程序 (`igxelpicd64.dll`)**，因为它是实际连接到显示器的。
- `igxelpicd64` 正在尝试访问 **Intel 的 Shader Cache** 路径 (`C:\Users\develop\AppData\LocalLow\Intel\ShaderCache\..`)。

### 3. Vulkan 实例和物理设备分离

您手动设置 `VK_DRIVER_FILES` 只影响了 Vulkan **实例 (Instance)** 的创建过程，确保 NVIDIA 的 ICD 驱动程序被加载。

- **`vkCreateInstance` 成功：** NVIDIA 驱动（`nvoglv64.dll`）被成功加载并初始化。
    
- **后续步骤：** 即使 NVIDIA 驱动被加载，当程序调用 `vkEnumeratePhysicalDevices` 时，它会发现 **系统上的所有 Vulkan 兼容设备**，包括 Intel iGPU 和 NVIDIA dGPU。
    
- **Optimus 干预：** 如上所述，在窗口和上下文的初始化过程中，**OpenGL/WGL** 的初始化路径（即使不是最终的 Vulkan 渲染路径）依然可能被 Intel 驱动程序介入，因为它管理着显示输出。


### 解决方案
在您的代码中添加一个全局导出变量，告诉 NVIDIA 驱动程序，您的程序是一个高性能应用，应该使用 dGPU。

在您的任何 .cpp 文件（最好是 main 所在的源文件）的全局作用域内添加以下代码：

```cpp
// 告诉 NVIDIA 驱动程序使用独立显卡 (dGPU)
extern "C" {
  __declspec(dllexport) DWORD NvOptimusEnablement = 0x00000001;
}

// 告诉 AMD 驱动程序使用独立显卡 (dGPU) (可选)
extern "C" {
  __declspec(dllexport) int AmdPowerXpressRequestHighPerformance = 1;
}
```

## 添加高性能标记后
还是有大量intel驱动的调用：
```
00000154`764574e0  "C:\Users\develop\AppData\LocalLo"
00000154`76457520  "w\Intel\ShaderCache\5f11c2592227"
00000154`76457560  "90422146768d167662e6e467ee38e871"
00000154`764575a0  "11911336f4e1aec31b96"
 # Child-SP          RetAddr               Call Site
00 0000000c`adafa1e8 00007ffa`35b172ea     KERNEL32!CreateFileW
01 0000000c`adafa1f0 00007ffa`35b148a0     igd10um64xe!OpenAdapter10_2+0x6935a
02 0000000c`adafa5e0 00007ffa`35b11d8b     igd10um64xe!OpenAdapter10_2+0x66910
03 0000000c`adafa780 00007ffa`35b1109b     igd10um64xe!OpenAdapter10_2+0x63dfb
04 0000000c`adafa7c0 00007ffa`35b07f56     igd10um64xe!OpenAdapter10_2+0x6310b
05 0000000c`adafa810 00007ffa`35a5874a     igd10um64xe!OpenAdapter10_2+0x59fc6
06 0000000c`adafa980 00007ffa`35a976d3     igd10um64xe!ctlInit+0x1d8a
07 0000000c`adafb040 00007ffa`35a9747f     igd10um64xe!ctlInit+0x40d13
08 0000000c`adafb0c0 00007ffa`3f94d011     igd10um64xe!ctlInit+0x40abf
09 0000000c`adafb0f0 00007ffa`3f94b512     d3d11!NDXGI::CDevice::CreateDriverInstance+0x271
0a 0000000c`adafb210 00007ffa`3f94af26     d3d11!CDevice::CreateDriverInstance+0xa2
0b 0000000c`adafb280 00007ffa`3f95d01b     d3d11!CContext::LUCCompleteLayerConstruction+0xc2
0c 0000000c`adafb3a0 00007ffa`3f95d602     d3d11!NOutermost::CDeviceChild::LUCCompleteLayerConstruction+0x5b
0d 0000000c`adafb400 00007ffa`3f95d1f6     d3d11!CUseCountedObject<NOutermost::CDeviceChild>::CUseCountedObject<NOutermost::CDeviceChild>+0x2a2
0e 0000000c`adafb490 00007ffa`3f9da7db     d3d11!NOutermost::CDevice::CreateLayeredChild+0x166
0f 0000000c`adafb5b0 00007ffa`3f94c72b     d3d11!CDevice::LLOCompleteLayerConstruction+0xafb
10 0000000c`adafbcb0 00007ffa`3f94fe14     d3d11!NDXGI::CDevice::LLOCompleteLayerConstruction+0xdf
11 0000000c`adafbf80 00007ffa`3f94ff1a     d3d11!NOutermost::CDevice::LLOCompleteLayerConstruction+0x14
12 0000000c`adafbfb0 00007ffa`3f94c561     d3d11!TComObject<NOutermost::CDevice>::TComObject<NOutermost::CDevice>+0xf6
13 0000000c`adafc020 00007ffa`3f94e8bb     d3d11!D3D11CreateLayeredDevice+0x231
14 0000000c`adafc120 00007ffa`3f94f2b7     d3d11!D3D11CoreCreateLayeredDevice+0x11b
15 0000000c`adafc1f0 00007ffa`3f94dabf     d3d11!D3D11RegisterLayersAndCreateDevice+0x57f
16 0000000c`adafc350 00007ffa`3f9bb073     d3d11!D3D11CoreCreateDevice+0x40f
17 0000000c`adafc670 00007ffa`3f9c22fe     d3d11!D3D11CreateDeviceAndSwapChainImpl+0x2a3
18 0000000c`adafc8e0 00007ffa`3f9c224c     d3d11!D3D11CreateDeviceAndSwapChain+0x9e
19 0000000c`adafc960 00007ffa`3f9c3b36     d3d11!D3D11CreateDeviceImpl+0x5c
1a 0000000c`adafc9d0 00007ffa`3f9d764b     d3d11!D3D11CreateDevice+0x86
1b 0000000c`adafca40 00007ffa`3fbf4692     d3d11!NDXGI::CDevice::EnsureChildDevice+0xdb
1c 0000000c`adafcad0 00007ffa`3fbbf76d     dxgi!CDXGISwapChain::EnsureChildDeviceInternal+0x6a
1d 0000000c`adafcda0 00007ffa`3fbc05a2     dxgi!CDXGISwapChain::PrepareWindowedBltPresent+0x72d
1e 0000000c`adafcec0 00007ffa`3fbb3674     dxgi!CDXGISwapChain::PresentImplCore+0x502
1f 0000000c`adafd870 00007ffa`3fbb2e1a     dxgi!CDXGISwapChain::PresentImpl+0x104
20 0000000c`adafd940 00007ff9`089965d3     dxgi!CDXGISwapChain::Present+0x17a
21 0000000c`adafdad0 00007ff9`089ca824     nvoglv64!DrvPresentBuffers+0x3553
22 0000000c`adafdb70 00007ff9`089a83f4     nvoglv64!DrvPresentBuffers+0x377a4
23 0000000c`adafde80 00007ff9`089cbef9     nvoglv64!DrvPresentBuffers+0x15374
24 0000000c`adafe390 00007ff9`08acb4ab     nvoglv64!DrvPresentBuffers+0x38e79
25 0000000c`adafe650 00007ff9`08ad807c     nvoglv64!DrvPresentBuffers+0x13842b
26 0000000c`adafe6f0 00007ff9`08aeeb75     nvoglv64!DrvPresentBuffers+0x144ffc
27 0000000c`adafe8b0 00007ff9`08964906     nvoglv64!DrvPresentBuffers+0x15baf5
28 0000000c`adafe990 00007ff9`08ab3bd1     nvoglv64!DrvValidateVersion+0x6db6
29 0000000c`adafe9e0 00007ff9`08a906cc     nvoglv64!DrvPresentBuffers+0x120b51
2a 0000000c`adaff270 00007ff9`08a8fb12     nvoglv64!DrvPresentBuffers+0xfd64c
2b 0000000c`adaff2a0 00007ff9`08d22259     nvoglv64!DrvPresentBuffers+0xfca92
2c 0000000c`adaff700 00007ff9`08d2456c     nvoglv64!vk_optimusGetInstanceProcAddr+0x252e9
2d 0000000c`adaff740 00007ff9`08d1e4ea     nvoglv64!vk_optimusGetInstanceProcAddr+0x275fc
2e 0000000c`adaffac0 00007ff9`08e2ff05     nvoglv64!vk_optimusGetInstanceProcAddr+0x2157a
2f 0000000c`adaffb10 00007ff6`53b47941     nvoglv64!vkGetInstanceProcAddr+0xf7735
30 0000000c`adaffcb0 00007ff6`53b4952e     VulkanGLFWDemo+0x7941
31 0000000c`adaffe70 00007ff6`53b42522     VulkanGLFWDemo+0x952e
32 0000000c`adaffec0 00007ffa`429e37b0     VulkanGLFWDemo+0x2522
33 0000000c`adaffef0 00007ffa`4389e8d7     ucrtbase!thread_start<unsigned int (__cdecl*)(void *),1>+0x30
34 0000000c`adafff20 00007ffa`4520c53c     KERNEL32!BaseThreadInitThunk+0x17
35 0000000c`adafff50 00000000`00000000     ntdll!RtlUserThreadStart+0x2c
```

仍然有从nvida驱动最终转发给 intel驱动的调用。

## AI解释

### 核心结论：窗口创建和显示管理

即使您的最终渲染 API 是 Vulkan，您的程序在创建窗口和将 Vulkan 渲染结果**呈现 (Present)** 到屏幕时，仍需要依赖底层的 OS/窗口管理系统。

在 Windows 的双显卡系统上：

1. **D3D11/DXGI 接口被调用：** 许多现代窗口库（如 GLFW, SDL 等）在底层创建窗口表面时，或者为了与 Windows 的桌面合成管理器（DWM）更好地集成，会涉及到 D3D11 和 DXGI 的初始化路径。
    
2. **Intel 驱动拥有显示输出权：** 由于 Intel iGPU 通常是**直接连接**到笔记本电脑显示器的，所以任何与 **显示适配器 (Adapter)** 相关的操作（如 DXGI 创建设备、枚举显示模式等），都会首先或默认涉及到 Intel 驱动程序（`igd10um64xe.dll`），因为它管理着最终的像素输出。
    
3. **着色器缓存访问：** 在 D3D11/DXGI 初始化的过程中，Intel 驱动程序会执行标准操作，例如检查或创建其自身的着色器缓存目录 (`C:\Users\...\Intel\ShaderCache\`)。这表明 **Intel 驱动程序被加载并运行了初始化逻辑**。

### 方案：尝试使用 Vulkan 原生表面创建

如果您使用的是 GLFW 或 SDL，尝试查看是否可以在 Vulkan 初始化阶段**之前**避免任何 WGL/DXGI 的调用。

**对于 GLFW 库：**

在调用 `glfwInit()` 之后、创建窗口之前，确保您明确告诉 GLFW **不创建任何图形 API 上下文**，这将有助于跳过 WGL/OpenGL 或 D3D/DXGI 的早期初始化。

```cpp
// 确保在创建窗口前设置以下提示
glfwWindowHint(GLFW_CLIENT_API, GLFW_NO_API); 

// 创建窗口
GLFWwindow* window = glfwCreateWindow(WIDTH, HEIGHT, "Vulkan App", nullptr, nullptr);
```

**目前AI提供的代码并没有用。因为目前出现问题的时候就是这么设置的。暂时卡在这里，后续可以考虑用windows原生API创建窗口，以及从堆栈看，可能d3d11可以做一些配置，避免其使用intel显卡**