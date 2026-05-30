---
title: Vulkan的ICD机制
date: 2025-11-18T12:57:45+08:00
tags:
  - vulkan
  - icd
draft: false
---

不甘心解决不了 igvk 的频繁调用问题的我，深入研究了一下ICD机制。尝试手动指定ICD来启动Vulkan，看能否解决问题。

<!--more-->
# 什么是 Vulkan ICD？

**ICD** 是 **Installable Client Driver**（可安装客户端驱动程序）的缩写。

在 Vulkan 架构中，ICD 指的是 **图形硬件供应商（如 NVIDIA、AMD、Intel）提供的、针对特定硬件实现的 Vulkan 驱动程序部分**。

简单来说，ICD 就是你的 **显卡驱动程序中负责执行 Vulkan 命令的那部分代码**。


Vulkan API 的设计采用了一种分层的（layered）架构，使其比其前身 OpenGL 或 DirectX 更加模块化和灵活。在这个架构中，ICD 扮演了核心角色。

## 详细解释 Vulkan 架构中的 ICD
### 1. Vulkan Loader（加载器）

在应用程序 (App) 和 ICD 之间，有一个关键的中间件：**Vulkan Loader**（加载器）。

- **作用：** 它是应用程序首先链接的库（通常是 `vulkan-1.dll` 或 `libvulkan.so`）。
    
- **功能：**
    
    - **发现与管理：** Loader 负责发现系统上安装的所有 Vulkan ICDs（即所有支持 Vulkan 的显卡驱动）。ICD 通常通过特定的 **JSON 清单文件**（例如 `nvidia_icd.json`、`amd_icd.json` 等，位于系统特定目录如 `/usr/share/vulkan/icd.d/`）向 Loader 注册自己。
        
    - **调度 (Dispatch)：** 当应用程序调用一个 Vulkan API 函数时（例如 `vkCreateInstance`、`vkCmdDraw`），Loader 负责将这个调用正确地导向（调度）到 **正确的 ICD** 或 **Vulkan Layer**（验证层、工具层等）。
        

### 2. Installable Client Driver (ICD)

ICD 是真正的“幕后英雄”，负责与物理 GPU 硬件通信。

- **作用：** 实现 Vulkan API 的核心功能，将抽象的 Vulkan 命令（如绘制三角形、进行计算）转换为 GPU 可以理解的实际硬件指令。
    
- **注册：** 每个 ICD 都会在系统上放置一个 JSON 文件，告诉 Loader 它的动态链接库（DLL 或 SO 文件）在哪里，以及它支持哪些 Vulkan 扩展和特性。
    
- **多 ICDs：** 由于一台计算机上可能有多个 GPU（例如一个 Intel 集成显卡和一个 NVIDIA 独立显卡），因此系统上可以同时安装和运行 **多个 ICDs**。Loader 会将它们全部识别出来，并在应用程序请求创建 Vulkan 实例或设备时，让应用程序选择使用哪一个 ICD。
    

### 3. Vulkan Layers（层）

虽然不是 ICD 本身，但 Layers 是理解 Vulkan 架构的另一个重要部分。

- **位置：** Layers 位于 Loader 和 ICD 之间。
    
- **作用：** 它们可以拦截 API 调用，并在调用传递给 ICD 之前或之后执行额外的操作。最常见的 Layers 是 **验证层 (Validation Layers)**，用于在开发过程中检查应用程序是否正确使用了 Vulkan API。

## 总结

|**角色**|**作用**|**谁提供？**|
|---|---|---|
|**应用程序 (App)**|调用 Vulkan API 函数。|开发者|
|**Loader**|发现所有 ICDs，管理 Layers，并将 API 调用调度给正确的 ICD。|Khronos Group（或驱动程序/发行版）|
|**ICD**|**真正的驱动程序实现，将 Vulkan 命令翻译成 GPU 硬件指令。**|硬件供应商 (NVIDIA, AMD, Intel 等)|

# Loader如何找到ICD？
参考 vulkan 文档 : https://vulkan.lunarg.com/doc/view/latest/mac/LoaderDriverInterface.html 中的 Driver Discovery on Windows 部分，可以知道，通过查询如下注册表项：

```
HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Adapter GUID}\000X\VulkanDriverName
HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{SoftwareComponent GUID}\000X\VulkanDriverName
```

## 显卡设备
对于显卡驱动开说，这里的 Adapter GUID是固定的，为 `4D36E968-E325-11CE-BFC1-08002BE10318` 。

![[Vulkan的ICD机制-显卡设备-01.png]]

对应设备管理器：
	
![[Vulkan的ICD机制-显卡设备-02.png]]

在我们的case下，这里的两个真实显卡会配置： `VulkanDriverName` 和 `VulkanDriverNameWow` 这两个key，分别指定64位和32位的 ICD的json配置文件。

## 软件组织设备

SoftwareComponent GUID也是固定的(“软件组件设备”，用于管理软件模块或驱动包中的附加功能。 **为了让操作系统可以像管理硬件设备一样管理驱动包中的软件模块**)，为 `5C4C3332-344D-483C-8739-259E934C9CC8`  （**SoftwareComponent 可以作为非标准设备或附加模块的“容器”，让操作系统统一管理**。）
![[Vulkan的ICD机制-软件组织设备-01.png]]
对应设备管理器：
![[Vulkan的ICD机制-软件组织设备-02.png]]



# 使用WinDbg定位到Loader获取ICD的位置
上面是我阅读文档得到的信息。不过，既然咱都学会了 windbg，是不是可以从二进制中看到vulkan如何加载这个json的呢？

## 思路1：注册表访问函数上打断点（失败）

![[Vulkan的ICD机制-思路1注册表访问函数上打断点失败-01.png]]


### `1F68E:2FD` 中断示例
这个中断点是最接近我们要访问的注册表项了。可惜读取的值并不是我们期待的。

```
[0x0]   ADVAPI32!RegGetValueWStub   0x55168e3898   0x7ff886f69e7d   
[0x1]   ControlLib!ctlWaitForPropertyChange+0x1bcd   0x55168e38a0   0x7ff886f6c493   
[0x2]   ControlLib!ctlWaitForPropertyChange+0x41e3   0x55168e3910   0x7fff7ef9348f   
[0x3]   igvk64!ctlInit+0xff   0x55168e3a80   0x7fff7ee61a59   
[0x4]   igvk64!DumpRegistryKeyDefinitions+0x1b76a9   0x55168e3ec0   0x7fff7ee60835   
[0x5]   igvk64!DumpRegistryKeyDefinitions+0x1b6485   0x55168e41a0   0x7fff7ee476a4   
[0x6]   igvk64!DumpRegistryKeyDefinitions+0x19d2f4   0x55168e4310   0x7fff7ee31bd5   
[0x7]   igvk64!DumpRegistryKeyDefinitions+0x187825   0x55168e43c0   0x7fff7eda31e6   
[0x8]   igvk64!DumpRegistryKeyDefinitions+0xf8e36   0x55168e4410   0x7fff7ed87534   
[0x9]   igvk64!DumpRegistryKeyDefinitions+0xdd184   0x55168fb620   0x7fff7ed5ec7d   
[0xa]   igvk64!DumpRegistryKeyDefinitions+0xb48cd   0x55168fb690   0x7fff7ece0ca5   
[0xb]   igvk64!DumpRegistryKeyDefinitions+0x368f5   0x55168fb6e0   0x7fffbd89c6dc   
[0xc]   vulkan_1!vkResetEvent+0x4b14c   0x55168fb7b0   0x7fff810205e7   
[0xd]   VkLayer_khronos_validation!vulkan_layer_chassis::CreateInstance+0x217   0x55168fb910   0x7fff8bb1b27c   
[0xe]   CrossVulkanLayer64!vkCreateInstance+0x180   0x55168fbad0   0x7ff8498fcacb   
[0xf]   graphics_hook64!dummy_debug_proc+0x294b   0x55168fbbe0   0x7fff741fc952   
[0x10]   nvoglv64!DrvPresentBuffers+0x3698d2   0x55168fbca0   0x7fffbd883652   
[0x11]   vulkan_1!vkResetEvent+0x320c2   0x55168fbcd0   0x7fffbd8a751e   
[0x12]   vulkan_1!vkResetEvent+0x55f8e   0x55168fc000   0x7ff717220f44   
[0x13]   VulkanGLFWDemo!HelloTriangleApplication::createInstance+0x244   0x55168ff410   0x7ff717224b64   

```

RegGetValueWStub，其实它是一个 “Stub（代理/跳转）” 函数，而真正的 API 是 RegGetValueW。
```cpp
LONG WINAPI RegGetValueW(
    HKEY    hkey,          // [in]      已打开的注册表键句柄
    LPCWSTR lpSubKey,      // [in, optional] 子键路径（相对 hkey），如果为 NULL 或 "" 则直接在 hkey 上查
    LPCWSTR lpValue,       // [in, optional] 注册表值名称，如果为 NULL 或 "" 则查默认值
    DWORD   dwFlags,       // [in]      检索类型的标志
    LPDWORD pdwType,       // [out, optional] 返回数据类型（如 REG_SZ 等）
    PVOID   pvData,        // [out, optional] 缓冲区 接收数据
    LPDWORD pcbData        // [in,out]  指定数据缓冲区大小，返回时写入实际用字节数
);
```
因此可以看一下第二第三个参数：
```
0:000> du rdx;
000001ea`8a246d60  "SYSTEM\CurrentControlSet\Control"
000001ea`8a246da0  "\Class\{4d36e968-e325-11ce-bfc1-"
000001ea`8a246de0  "08002be10318}\0001"
0:000> du r8;
00007ff8`86f86370  "ControlApiPath"
```

为什么注意这个注册表的读取？因为按照vulkan文档的解释，ICD的信息其实就是从这个key里得到的。

为了方便定位到类似的读取，我们改造一下断点：
```
bp advapi32!RegGetValueWStub "du rdx; du r8;"
```

继续执行，把这个调用的重要参数打印出来。除了这个并没有太多有效信息。所以，应该是使用别的API读取值。（ **当然也可能是内核态读取的，这样无法断点；这个是后来才知道的，参见思路2** ）

### 总结
打了尽可能多的读取注册表的断点，没有一处中断到 读取 值 `VulkanDriverName` 上。



## 思路2：找到打开配置文件的代码，追踪文件路径的获取过程
既然注册表思路不行，还有一个办法，我们其实已经知道对应的ICD配置文件。同时代码一定会读取这个文件，从 `kernel32!CreateFileW` 入手，我们可以中断到ICD配置文件（字符串：一个json文件）。随后我们溯源这个字符串怎么来的。

这里细节不表。详细过程大概为：
- 定位到文件的字符串，然后再代码中找到传参的变量/寄存器/内存。
- 如果是内存，打内存断点，随后追查内存写入位置的传参。
循环上面两个步骤。。。（有效的利用TTD调试，可以不断的阅读汇编代码，中断，随后 `g-` 跳转回去；当然还可以用 `tt br-` 和 `tt ba-` ，只不过我一开始不会用，就用了笨办法）

最终定位到，在内存位置： ```000001ea`87f61530``` 这里，被填充了字符串： `C:\WINDOWS\System32\DriverStore\FileRepository\iigd_dch.inf_amd64_aaa3915de44b535a\igvk64.json` 

而填充这个内存的代码无法中断到。通过不断的单步，最后定位到代码：

```asm
    win32u!NtGdiDdDDIQueryAdapterInfo: CFG
00007ff8`926b57d0 4c8bd1           mov     r10, rcx
00007ff8`926b57d3 b82a120000       mov     eax, 122Ah
00007ff8`926b57d8 f604250803fe7f01 test    byte ptr [7FFE0308h], 1
00007ff8`926b57e0 7503             jne     win32u!NtGdiDdDDIQueryAdapterInfo+0x15 (7ff8926b57e5)
00007ff8`926b57e2 0f05             syscall 
00007ff8`926b57e4 c3               ret     
00007ff8`926b57e5 cd2e             int     2Eh
00007ff8`926b57e7 c3               ret     
00007ff8`926b57e8 0f1f840000000000 nop     dword ptr [rax+rax]
```

在syscall之后，得到了数据。

通过询问AI，知道切换到了内核态。是由驱动本身来填充的。内核态的代码，用户态调试无法中断。这也是为什么，之前注册表访问函数中断不了的原因。

这个调用的堆栈：
```
[0x0]   win32u!NtGdiDdDDIQueryAdapterInfo+0x14   0x55168fb7e8   0x7fffbd8b331d   
[0x1]   vulkan_1!vkResetEvent+0x61d8d   0x55168fb7f0   0x7fffbd8b2e1c   
[0x2]   vulkan_1!vkResetEvent+0x6188c   0x55168fbb20   0x7fffbd88489d   
[0x3]   vulkan_1!vkResetEvent+0x3330d   0x55168fbbc0   0x7fffbd896535   
[0x4]   vulkan_1!vkResetEvent+0x44fa5   0x55168fbc10   0x7fffbd89828a   
[0x5]   vulkan_1!vkResetEvent+0x46cfa   0x55168fbca0   0x7fffbd8a8db2   
[0x6]   vulkan_1!vkResetEvent+0x57822   0x55168fbd60   0x7ff71722f720   
[0x7]   VulkanGLFWDemo!_glfwInitVulkan+0x110(int mode = 2) [C:\Users\develop\game-dev\renderer\external\glfw-3.4\src\vulkan.c @ 100]   0x55168ff150   0x7ff71722f5cc   
[0x8]   VulkanGLFWDemo!glfwGetRequiredInstanceExtensions+0x5c(unsigned int * count = 0x55168ff214 : 0x0) [C:\Users\develop\game-dev\renderer\external\glfw-3.4\src\vulkan.c @ 236]   0x55168ff1c0   0x7ff7172249b8   
[0x9]   VulkanGLFWDemo!HelloTriangleApplication::getRequiredExtenstions+0x48() [C:\Users\develop\game-dev\renderer\src\main.cpp @ 531]   0x55168ff1f0   0x7ff71721e6b2   

```

可以看出来，在我的程序获取 `glfw` 所需要的extentions的时候，会触发 `_glfwInitVulkan` ，最终触发了 `win32u!NtGdiDdDDIQueryAdapterInfo` 这个函数的调用。

那么其他位置，比如 `vkCreateInstance` 的时候，应该类似。最终的调用被转发给了系统调用，从而获取到了对应的ICD配置。（如果想定位到对应的指令，必须得内核态调试）

这个就更加进阶了。暂时我不打算继续深入。相关文档在： https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/getting-started-with-windbg--kernel-mode- 。未来有需要再看。

### 关于这个中断相关信息的AI解读
#### AI（节选）
函数第一个参数：

dd @rcx L4 这个命令结果为： 
```
00000055168f6300 40001c00 00000030 87f61310 000001ea
```
#### AI（节选）
您的内存数据如下： `00000055168f6300 40001c00 00000030 87f61310 000001ea`

这是一块连续内存，WinDbg 的 `dd` (Display DWORD) 是按 4 字节显示的。我们来按结构体布局拆解它：
- **地址**: `0x00000055168f6300`
- **Offset 0x00 (hAdapter)**: `40001c00`
    - 这是适配器句柄。
        
- **Offset 0x04 (Type)**: `00000030`
    - 十六进制 `0x30` = 十进制 **48**。
    - 查阅 WDDM 驱动开发文档，`KMTQUERYADAPTERINFOTYPE` 枚举中，值 48 对应的是 **`KMTQAITYPE_PHYSICALADAPTERDEVICEIDS`**。
    - **含义**：Vulkan Loader 正在询问内核：“**请告诉我这个物理适配器的 PCI Device ID、Vendor ID 和 SubSystem ID**”。这正是 Loader 用来匹配 JSON 文件中筛选器的关键步骤。
        
- **Offset 0x08 (pPrivateDriverData)**:
    - 由于这是 x64，指针占 8 字节，由后两个 DWORD 组成。
    - 低 4 字节: `87f61310`
    - 高 4 字节: `000001ea`
    - **指针地址**: `0x000001ea87f61310`。这是接收返回数据（Device IDs）的缓冲区地址。

**结论**：Vulkan 正在遍历 GPU 并获取它们的硬件 ID。

#### 我的讨论

我的调用会在  ```000001ea87f61530```  这个地址，写入 C:\WINDOWS\System32\DriverStore\FileRepository\iigd_dch.inf_amd64_aaa3915de44b535a\igvk64.json 这个字符串。而不是你分析的地址。而在 `000001ea87f61310` 这个位置，信息为：（二进制）：

```
000001ea87f61310 0001 0000 0001 0000 0056 0075 006c 006b
000001ea87f61320 0061 006e 0044 0072 0069 0076 0065 0072
000001ea87f61330 004e 0061 006d 0065 0000 0000 0000 0000
```

并没有看到内存变化。看起来更像是函数调用输入的信息。000001ea87f61310 是结构体的地址，而 000001ea87f61530 则是用来接收返回值的buffer。

或者说，整个rcx存放的是一个指针，指向某个结构体。而这个结构体前三个dword之后，又跟随一个指针，这个指针指向另一个结构体（顺便用这个结构体接收一些返回值）。

这么一推断，你上面很多说法都不成立（毕竟你的接口体定义都不对）

#### AI（节选）

**修正：现场内存分析 (CSI 现场还原)**


你抓到的内存数据： `000001ea'87f61310 0056 0075 006c 006b ...`

这确实是 **Unicode 字符串**。
- `0056` = 'V'
- `0075` = 'u'
- `006c` = 'l'
- `006b` = 'k'
- 拼起来正是：**`VulkanDriverName`**
    

**这是什么意思？** 这说明 `Type = 0x30` (48) 在这个上下文（Windows 10/11 + DCH 驱动）中，实际上执行的是 **`KMTQAITYPE_ADAPTERREGISTRYINFO`** (查询适配器注册表信息) 的某种变体或特定实现。

**流程重构：**
1. **Input**: Vulkan Loader 将字符串 `VulkanDriverName` 放入 `pPrivateDriverData` 指向的缓冲区。
2. **Call**: 调用 `NtGdiDdDDIQueryAdapterInfo`。
3. **Kernel Action**: 内核拿着显卡句柄，去该显卡在 `HKLM\SYSTEM\CurrentControlSet\Control\Class\{GUID}\00xx` 下的**私有驱动注册表项**中查找名为 `VulkanDriverName` 的值。
4. **Output**: 内核找到了路径（如 `...\igvk64.json`），并将其写回到缓冲区的某个偏移位置（你观察到的 `0x...530`）。
    

**结论**：Vulkan Loader 不再依赖全局的 `Khronos\Vulkan\Drivers` 列表，而是直接询问内核：“当前这个显卡，它的驱动 JSON 藏在哪里？”。这就是为什么你的注册表中没有那个全局 Drivers 键值的原因。

	注意：实际上和Vulkan Loader可能没有关系。因为目前堆栈定位到调用是 vkEnumerateInstanceExtensionProperties 中

#### AI（节选）
	AI坚持认为调用时用 `D3DKMTQueryAdapterInfo` 这个函数。

它并没有直接调用 NtGdiDdDDIQueryAdapterInfo。

它调用的是 D3DKMTQueryAdapterInfo。这是一个由 gdi32.dll 或 d3dkmthk.dll 导出的函数。

在 WinDbg 中，你看到 NtGdi... 是因为 D3DKMT... 只是一个很薄的封装，它立即通过 syscall 进入内核，而 WinDbg 在内核入口处抓住了它。

待排查。

# 补充知识
## DCH

**DCH** 代表 **D**eclarative, **C**omponentized, **H**ardware Support Apps。这是微软在 Windows 10 1809 之后强制推行的新驱动架构。

- **Legacy (旧版) 驱动**：
    - 一个巨大的 `.exe` 安装包。
    - 把 DLL 扔进 `System32`。
    - 注册表乱写。
    - 控制面板和驱动混在一起。
        
- **DCH (新版) 驱动**：
    - **Declarative (声明式)**：通过 INF 文件清晰声明所有文件去向。
    - **Componentized (组件化)**：核心驱动 (Kernel)、服务 (Service)、用户软件 (Control Panel) 必须分开。
    - **Hardware Support Apps**：控制面板（如 NVIDIA Control Panel）必须通过 Microsoft Store 安装，不能捆绑在驱动里。
    - **关键影响**：
        - 驱动文件被严格隔离在 `C:\Windows\System32\DriverStore\FileRepository\...` 这种带哈希值的文件夹里，防止被篡改或覆盖。
        - Vulkan JSON 文件也必须放在那里。
        - 注册表不再使用全局位置，而是绑定在 PnP 设备节点上。