---
title: WinDbg的初级用法
date: 2025-11-17T22:05:20+08:00
tags:
  - windbg
  - 二进制
  - 调试
draft: false
---
起因开始于 [[posts/Vulkan/记录调试Vulkan程序打印奇怪日志的问题|记录调试Vulkan程序打印奇怪日志的问题]]

这篇文章详细展开了 WinDbg 的基础用法。


<!--more-->
# 正文开始
## 简要介绍
**WinDbg**（Windows Debugger）是 Microsoft 提供的强大调试工具，广泛应用于 Windows 系统的内核调试、用户模式调试、崩溃转储分析等场景。它适用于调试应用程序、驱动程序、操作系统内核等各种不同类型的程序。WinDbg 支持命令行界面，并且具有图形用户界面（WinDbg Preview），它能够帮助开发人员和系统管理员诊断并修复系统崩溃或程序错误。

## 安装与启动 WinDbg
参考文档： https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/

简单来说：
```ps
winget install Microsoft.WinDbg
```

用windows的包管理器下载即可。（类似苹果的HomeBrew，windows下我一般除了 winget，还会用到 chocolate 和 scoop）

## 启动调试

点击文件：

![[WinDbg的初级用法-启动调试-01.png]]

选项介绍：
- Launch executable : 直接启动一个exe，并且中断到最开始的地方。
- Launch executable (advanced) : 这个模式支持更多设置，包括运行参数(arguments)和运行目录(start directory) 。还支持 时间旅行调试 (Time Travel Debugging, TTD)
- Attach to process: 附加到已经在运行的进程上进行调试。
- Open dump file: 加载一个先前捕获的内存转储文件（crash dump）进行事后分析。
- Open trace file: 加载一个先前记录的 时间旅行调试 (TTD) 跟踪文件进行回放和分析。

我们这里选择 Launch executable ，选择要调试的vulkan程序即可。

## 时间旅行调试 (TTD, Time Travel Debugging)
启动调试的时候，选择 `Launch executable(advanced)` 。并勾选开启 Time Travel Debugging

微软开发的一种革命性的调试技术。它允许开发者和逆向工程师**记录**一个进程的执行过程，然后像观看视频一样，对这个记录进行**回放**和**反向调试**。

|**特点**|**描述**|**优势**|
|---|---|---|
|**反向执行 (Reverse Execution)**|可以在程序的执行时间轴上**向后移动**。|能够轻松地回溯到程序状态发生损坏、或导致崩溃的那个瞬间之前，准确找出问题的根源。|
|**完整记录 (Full Recording)**|捕获了程序执行过程中的所有状态变化，包括 CPU 寄存器、内存读写等。|无需重现 Bug。一旦记录了 Bug 发生的过程，您可以无限次地回放和分析，而 Bug 不会再“跑掉”。|
|**可重复性 (Reproducibility)**|调试会话基于记录文件，而不是实时运行的程序。|调试过程是完全确定的，在不同的机器上、不同的时间点上分析结果始终一致，非常利于协作。|
|**高级查询 (Advanced Query)**|允许使用查询语言（如 Linq）来搜索整个执行历史记录。|可以快速找到“是谁最后写入了这个内存地址？”或“这个函数在哪里被调用过？”等复杂问题。|

非常好用，建议调试复杂问题的时候，先开启TTD录制一次。随后加载对应的trace文件。就可以用TTD调试了。在这个调试模式可以使用：
- `g-` : 跳到上一个断点（所以把所有断点 disable 或者清空后，可以直接跳到开头）
- `p-` : 往回跳1个指令。



## 常用寄存器

| **变量**                        | **含义 (x64)**        | **备注**                                                       |
| ----------------------------- | ------------------- | ------------------------------------------------------------ |
| `@rcx`, `@rdx`, `@r8`,  `@r9` | 通用寄存器 （易失性）         | 在windows x64下，函数调用前，这四个寄存器会保存函数调用的前4个参数。（使用的时候，可以不带 `@` 符号)  |
| `@ip`                         | instruction pointer | 指向下一个要执行的指令。通常配合查看汇编代码的时候。                                   |
| `@rsp`                        | 栈指针寄存器              | 总是指向栈顶的地址。（地址越低，越靠近栈顶；函数开始调用前，会移动栈顶指针向低地址，以准备足够的栈空间用来存储局部变量） |
| `@r14, r15`                   | 通用寄存器（非易失性）         | 常用于标识当前函数的栈帧起始位置。                                            |
| `ymm0, ymm1`                  | 256位矢量寄存器           | avx指令集中的寄存器。AVX（Advanced Vector Extensions）                  |

## 内存的引用
一般采用 `[ expression ]` 的方式引用一个内存地址。随后配合指令，决定读写的大小。

`expression` 可以是：
- 寄存器
- 寄存器 + 偏移
- 基址 + 索引 * 缩放 + 偏移
- 标号
- 常量
- 任意合法的组合

注意，有些指令需要内存对齐。否则产生GP异常（General Protection Fault，通用保护异常）。比如SSE，AVX指令。

```
movaps xmm0, [rax]   ; 需要 16 字节对齐，否则 #GP 异常
movdqa xmm1, [rax]   ; 需要 16 字节对齐
vmovaps ymm0, [rax]  ; rax 必须 32 字节对齐
```

## 指令集（SSE/AVX）简介
上一节中，提到的一些用比较特别寄存器的，都是扩展指令集的指令。这节简要介绍一些。

- SSE: Streaming SIMD Extensions 。Intel 在 **1999 年** 发布的 SIMD（Single Instruction Multiple Data）扩展。使用 **128 位的 XMM 寄存器（xmm0–xmm15）** ，提供浮点加速。通常需要对齐。
- AVX: Advanced Vector Extensions 。Intel 在 **2011 年** 推出的 SSE 进化版。 使用 **256 位 YMM 寄存器（ymm0–ymm15 / ymm31）**。具备无需对齐的指令。

更多高阶指令：
- AVX2（2013）： 整数 SIMD，Gather 指令，更强的向量整数操作（如 vpblendd、vpmulld）。
- AVX-512（2016）：寄存器扩大到 **512 位的 ZMM0–31**。掩码寄存器（k0–k7），更丰富的数学指令（如 exp/log），分段化（Foundation / BW / VL / VNNI / IFMA 等）。应用：HPC（科学计算），AI 推理（VNNI），数据中心服务器（Xeon 里普遍支持）
- VNNI（Vector Neural Network Instructions）： 属于 AVX-512 家族（也有 AVX2 版本）。专为 AI 推理优化：提供更快的 dot-product（点积）运算，用于 INT8/INT16 加速。
- AMX（Advanced Matrix Extensions）(2021)：**矩阵加速器**，不是传统 SIMD 了。Tile 寄存器（矩阵寄存器）、Tile 配置指令、Tile DP（矩阵乘加）。

这些跟处理器相关。通常消费级处理器，没有AMX。

## 常用指令

### First of All
用 `.hh <x>` 指令可以查看 `<x>` 指令的文档。
### 执行控制和断点

| **命令**   | **完整形式/别名**             | **功能描述**                                                | **示例**                                   |
| -------- | ----------------------- | ------------------------------------------------------- | ---------------------------------------- |
| **`g`**  | `go`                    | **继续执行**。程序将从当前位置继续运行直到遇到断点或退出。                         | `g`                                      |
| **`p`**  | `step`                  | **步过 (Step Over)**。执行下一条指令。如果下一条是函数调用，则执行完整个函数再停下。      | `p`                                      |
| **`t`**  | `trace`                 | **步入 (Step Into)**。执行下一条指令。如果下一条是函数调用，则进入该函数内部并停在第一条指令。 | `t`                                      |
| **`bp`** | `Set Breakpoint`        | **设置软件断点**。                                             | `bp MyModule!MyFunction`                 |
| **`ba`** | `Set Access Breakpoint` | **设置访问断点（硬件断点）**。用于监视内存地址的读、写或执行。                       | `ba w8 @rcx` (在 `@rcx` 地址上设置 8 字节的写访问断点) |
| **`bl`** | `List Breakpoints`      | **列出** 当前设置的所有断点。                                       | `bl`                                     |
| **`bc`** | `Clear Breakpoints`     | **清除** 指定编号的断点。                                         | `bc 0` (清除编号为 0 的断点)                     |
| **`be`** | `Enable Breakpoints`    | **启用** 指定编号的断点。                                         | `be 0`                                   |
| **`bd`** | `Disable Breakpoints`   | **禁用** 指定编号的断点。                                         | `bd 0`                                   |
重中之重：
- `bp, ba` : 调试必备

注意， `bl,bc,be,bd` 在UI上操作更方便。
### 内存检查
|**命令**|**数据类型**|**功能描述**|**示例**|
|---|---|---|---|
|**`db`**|Byte (字节)|**显示** 字节数据 (1 字节/8 位)。同时显示十六进制和 ASCII 字符。|`db 0x180000000`|
|**`dw`**|Word (字)|**显示** 字数据 (2 字节/16 位)。|`dw @rcx`|
|**`dd`**|Double-Word (双字)|**显示** 双字数据 (4 字节/32 位)。|`dd @rsp`|
|**`dq`**|Quad-Word (四字)|**显示** 四字数据 (8 字节/64 位)。**x64 环境下最常用**。|`dq @rcx`|
|**`da`**|ASCII String|**显示** 内存中的 **ASCII** 字符串。|`da @rdx`|
|**`du`**|UNICODE String|**显示** 内存中的 **UNICODE** (UTF-16) 字符串。|`du @rcx`|
### 上下文与符号信息 (Context & Symbol)
| **命令**   | **别名**            | **功能描述**                                  | **示例**                                |
| -------- | ----------------- | ----------------------------------------- | ------------------------------------- |
| **`r`**  | `registers`       | **查看/修改** 寄存器的值。                          | `r` (查看所有) 或 `r rcx=0x123` (修改 `rcx`) |
| **`k`**  | `kb`              | **显示栈回溯 (Stack Backtrace)**。这是最常用的调试命令之一。 | `k` 或 `kb` (后者会显示栈上前4个QWORD)          |
| **`lm`** | `list modules`    | **列出** 当前加载的所有模块（DLL/EXE）。                | `lm` 或 `lm v` (显示详细信息)                |
| **`x`**  | `examine symbols` | **检查** 指定模块内的符号（函数名、变量名）。                 | `x MyModule!*` (列出 MyModule 的所有符号)    |
| **`?`**  | `evaluate`        | **计算** 表达式的值。                             | `? 0x10 + @r8`                        |
| `lmv m`  |                   | 查看具体模块的详细信息                               | `lmv m vulkan_1`                      |
- 用 `x` 指令，支持通配符。可以先用来查询模块中可以使用的符号。（有些带有pdb信息的，有些无pdb信息的仍然有导出库的符号）
- `r` 指令看寄存器的时候，可以指定格式。例如 `r ymm1:uq` 。具体参照文档。

## 断点设定示例
考虑在文件创建的时候打断点。
### CreateFileA 和 CreateFileW 函数
这两个是windows的api函数，用来创建文件。

|**特性**|**CreateFileA (ANSI 版本)**|**CreateFileW (Unicode 版本)**|
|---|---|---|
|**字符串类型**|接受 **ANSI/多字节** 字符串。|接受 **Unicode** (UTF-16) 字符串。|
|**应用场景**|主要用于**较老**或非 Unicode 环境的程序。|**现代 Windows 应用程序的主流**，支持全球语言字符集。|
|**内部机制**|需要在内部将 ANSI 转换为 Unicode 才能交给系统内核处理，有轻微性能开销。|直接使用 Unicode，无需转换，**效率更高，更可靠**。|
### CreateFile函数参数
两个函数调用的参数是类似的：

```c
HANDLE CreateFileW(
  LPCWSTR               lpFileName,           // 1. 文件名 (W版本使用 LPCWSTR)
  DWORD                 dwDesiredAccess,      // 2. 期望的访问权限
  DWORD                 dwShareMode,          // 3. 文件共享模式
  LPSECURITY_ATTRIBUTES lpSecurityAttributes, // 4. 安全属性
  DWORD                 dwCreationDisposition,// 5. 创建/打开的方式
  DWORD                 dwFlagsAndAttributes, // 6. 文件属性和标志
  HANDLE                hTemplateFile         // 7. 模板文件句柄
);
```
- 期望的访问权限：主要传入 `GENERIC_READ|GENERIC_WRITE|GENERIC_EXECUTE|0`
- 文件共享模式: 决定其他程序是否可以打开同一个文件。 `0|FILE_SHARED_READ|FILE_SHARED_WRITE|FILE_SHARED_DELETE`
- 安全属性: 主要是权限控制
- 创建/打开的方式 : 当文件存在或者不存在的时候如何处理。**非常关键**
	- `CREATE_NEW` ：创建新文件。如果文件已存在，则失败。
	- `CREATE_ALWAYS` ：创建新文件。如果文件已存在，则覆盖并清空。
	- `OPEN_EXISTING` ：打开现有文件。如果文件不存在则失败。
	- `OPEN_ALWAYS` ：打开现有文件。如果文件不存在则创建。
- 文件属性和标志：设置隐藏文件、只读文件等等。
- 模板文件句柄：按照模板文件来创建文件，继承其属性。

### Windows x64调用约定

在 Windows x64 架构下，微软规定使用 **Fastcall** 调用约定，它要求函数的前四个非浮点数参数通过特定的通用寄存器传递，而不是通过栈传递。

|**参数序号**|**寄存器**|**作用**|**WinDbg 伪寄存器**|
|---|---|---|---|
|**第一个参数 (Param 1)**|**`RCX`**|**通用寄存器 C**|`@rcx`|
|**第二个参数 (Param 2)**|**`RDX`**|**通用寄存器 D**|`@rdx`|
|**第三个参数 (Param 3)**|**`R8`**|**通用寄存器 R8**|`@r8`|
|**第四个参数 (Param 4)**|**`R9`**|**通用寄存器 R9**|`@r9`|
|**第五个及后续参数**|**栈 (Stack)**|从栈上获取参数|`dq @rsp + 0x28` / `dq @rsp + 0x30` 等|
回顾 `CreateFileW` 的前四个参数：
1. `lpFileName` $\rightarrow$ **`@rcx`** (文件名指针)
2. `dwDesiredAccess` $\rightarrow$ **`@rdx`** (访问权限 DWORD)
3. `dwShareMode` $\rightarrow$ **`@r8`** (共享模式 DWORD)
4. `lpSecurityAttributes` $\rightarrow$ **`@r9`** (安全属性指针)

因此，您在 WinDbg 中查看参数时，总是使用 `du @rcx` 或 `? @rdx` 等命令。

# 实操演练
我们的目标是找到异常写日志的代码。选择一个合适的方式，加载exe启动后，看到如下页面。

启动对应exe：
![[WinDbg的初级用法-实操演练-01.png]]

## 初始页面讲解
### 模块加载信息
#### 主程序
```
ModLoad: 00007ff7`f70b0000 00007ff7`f70fa000   image00007ff7`f70b0000
```
加载主程序。名称image后面跟着的是虚拟内存地址，意味着程序被加载到这个内存位置上。主程序永远是第一个被加载的。

查看主程序模块：
```
0:000> lm a 00007ff7`f70b0000
Browse full module list
start             end                 module name
00007ff7`f70b0000 00007ff7`f70fa000   VulkanGLFWDemo C (no symbols)   
```
- **`lm` (List Modules):** 基本命令，用于显示模块信息。
- **`a` (Address):** 这是一个子命令或限定符，意思是**"按地址过滤"**。它告诉 WinDbg **只显示包含这个特定地址的模块**。
- 地址用 $`$ 分隔 : 分隔内存地址的高位和低位部分是为了**提高可读性和清晰度**，尤其是在处理 **64 位 (8 字节)** 地址时 。

#### 其他模块简要介绍
- `ntdll.dll` :  **Windows NT 层的核心库**。它提供用户模式程序到内核模式驱动程序和函数的接口，是所有 Windows 进程的基石。
- `KERNEL32.DLL` : 提供基本的 **操作系统服务**，如内存管理、进程和线程管理、文件 I/O 等。它是 Windows 编程中最重要的 DLL 之一。
- `KERNELBASE.dll` : 包含 `KERNEL32.DLL` 的许多底层函数实现。在现代 Windows 中，许多核心 API 调用被路由到这里。
- `USER32.dll` : 负责管理用户界面元素，如**窗口、菜单、对话框**等。
- `win32u.dll` : 包含底层用户模式的图形和窗口管理函数，是 `USER32.dll` 和 `GDI32.dll` 的**更底层实现**。
- `vulkan-1.dll` : 这是一个**图形 API 库**。它表明你的程序正在使用 **Vulkan** 图形 API，这通常用于高性能的 3D 游戏或渲染应用。

#### 为什么是这个加载顺序？
任何 Windows 进程启动，都需要两个最基本的 DLL 来与内核交互和管理自身。因此，它们总是最先被加载，并且顺序非常固定：

| **顺序** | **模块**                                    | **职责和原因**                                                                                                                      |
| ------ | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **1.** | **主程序 (`VulkanGLFWDemo C` / `image...`)** | **原因：** 它是被执行的文件。加载器首先将 EXE 文件映射到进程的虚拟地址空间，并开始解析它的导入表（Import Table）。                                                           |
| **2.** | **`ntdll.dll`**                           | **原因：** 这是所有用户模式代码访问内核服务（`ntoskrnl.exe`）的**唯一网关**。任何更高层的 DLL，包括 `KERNEL32.DLL`，都必须通过 `ntdll.dll` 来工作。它必须在其他所有依赖内核的模块之前加载。      |
| **3.** | **`KERNEL32.DLL`**                        | **原因：** 它是提供进程、内存、文件等基本 API 的高级层。它自身依赖于 `ntdll.dll`。                                                                           |
| **4.** | **`KERNELBASE.dll`**                      | **原因：** 它是 `KERNEL32.DLL` 的底层实现库。现代 Windows 将 `KERNEL32` 的许多实际功能移到了 `KERNELBASE` 中，以提高效率和隔离性。它紧随其后的加载，是为了满足 `KERNEL32` 启动时的依赖。 |
在基础的系统服务加载完成后，加载器会继续加载主程序**导入表**中列出的下一组核心依赖项，通常是与用户界面 (UI) 相关的库：

|**顺序**|**模块**|**职责和原因**|
|---|---|---|
|**5.**|**`USER32.dll`**|**原因：** 主程序是一个图形应用（基于 `Vulkan`），所以它需要窗口管理 API。`USER32.dll` 是管理窗口、消息和对话框的关键。|
|**6.**|**`win32u.dll`**|**原因：** 类似 `KERNELBASE` 和 `KERNEL32` 的关系，`win32u.dll` 是 `USER32.dll` 的底层实现，用于处理用户模式和内核模式之间的用户界面切换。它在 `USER32` 之后加载，因为它被 `USER32` 所依赖。|
|**7.**|**`GDI32.dll`**|**原因：** 图形设备接口库，负责绘图、字体等。它通常是与 `USER32` 捆绑在一起加载的，用于提供图形界面所需的基本绘制能力。|

### UI配置
页面中的View选项可以调出很多好用的窗口。根据自己的需求配置即可。

![[WinDbg的初级用法-ui配置-01.png]]

随后可以拖拽窗口，dock到自己喜欢的位置上。

### 第一个中断
```
(4d30.26a4): Break instruction exception - code 80000003 (first chance)
ntdll!LdrpDoDebuggerBreak+0x35:
00007ff8`9503f5fd cc              int     3
```
- 进程线程信息：
	- **`4d30`**: 进程 ID (PID)，十六进制表示。
	- **`26a4`**: 线程 ID (TID)，十六进制表示。
- 异常类型和状态：
	- **`Break instruction exception`**: **异常类型：** **中断指令异常**。这意味着 CPU 遇到了一个专门用于触发调试中断的指令。
	- code 80000003： **异常代码：** 这是 Windows 中 **硬编码断点**（Hardcoded Breakpoint）的异常代码。这个代码通常是由 `int 3`（汇编指令）触发的。在 Windows 进程启动或调试器接管时，系统会故意执行这个指令，以确保调试器能在程序真正开始运行前获得控制权。
- 暂停位置：
	- **`ntdll!LdrpDoDebuggerBreak+0x35`**: **模块与函数：** 程序当前暂停在 `ntdll.dll` 模块中的 `LdrpDoDebuggerBreak` 函数内，偏移量为 `+0x35`。
	- ```00007ff8`9503f5fd``` : **内存地址：** 异常发生的具体指令地址。
	- `cc` 机器码。对应的汇编为 `int 3`

### 命令窗口 `0:000>`
命令提示符格式: `P:T>`
- P: 代表正在调试的处理器编号（CPU编号）。
- T: 代表正在调试的线程编号

命令窗口后面可以输出上面我们介绍过的调试指令。

## 添加断点
命令行里输入如下命令
```
bp kernel32!CreateFileA;
bp kernel32!CreateFileW;
```



右下角面板可以打开 Breakpoint 选项卡：
![[WinDbg的初级用法-添加断点-01.png]]

随后可以输入命令：
```
g
```

启动程序运行。


注意，断点另一个常见的用法是，后面接中断触发后执行的指令，比如：
```
bp kernel32!CreateFileW "du rcx;"
```
这个断点中断后，会以 unicode字符串的方式打印 rcx指针指向的地址。这是非常常用的技巧。

## 中断到CreateFile
下面进入我们第一次中断的情况：
![[WinDbg的初级用法-中断到createfile-01.png]]
### 寄存器观察
```
0:000> r
rax=000000000000005c rbx=0000000000000000 rcx=00000073ac18c1b0
rdx=0000000080000000 rsi=0000022a13050f00 rdi=000000000000005c
rip=00007ff893b970f0 rsp=00000073ac18c168 rbp=00000073ac18c270
 r8=0000000000000001  r9=0000000000000000 r10=0000022a13050f5c
r11=00000073ac18c1b0 r12=0000000000000000 r13=00000073ac18c310
r14=0000000000000000 r15=00000073ac18c1b0
iopl=0         nv up ei pl zr na po nc
cs=0033  ss=002b  ds=002b  es=002b  fs=0053  gs=002b             efl=00000246
KERNEL32!CreateFileW:
00007ff8`93b970f0 ff25ea270300    jmp     qword ptr [KERNEL32!_imp_CreateFileW (00007ff8`93bc98e0)] ds:00007ff8`93bc98e0={KERNELBASE!CreateFileW (00007ff8`922f3ac0)}
```

回忆API接口：
```c
HANDLE CreateFileW(
  LPCWSTR               lpFileName,           // 1. 文件名 (W版本使用 LPCWSTR)
  DWORD                 dwDesiredAccess,      // 2. 期望的访问权限
  DWORD                 dwShareMode,          // 3. 文件共享模式
  LPSECURITY_ATTRIBUTES lpSecurityAttributes, // 4. 安全属性
  DWORD                 dwCreationDisposition,// 5. 创建/打开的方式
  DWORD                 dwFlagsAndAttributes, // 6. 文件属性和标志
  HANDLE                hTemplateFile         // 7. 模板文件句柄
);
```

函数入参：

- `rcx` : 第一个参数。`lpFileName` (文件名地址)
- `rdx` : 第二个参数。`dwDesiredAccess` (期望访问权限) 。$0x80000000$ 对应 `GENERIC_READ`。这表示程序**只请求读取权限**。
- `r8`: 第三个参数： `dwShareMode` (共享模式)。 `0x1` 对应 `FILE_SHARE_READ`。这意味着其他进程在文件打开时**可以同时拥有读取权限**。
- `r9`: 第四个参数： `lpSecurityAttributes` (安全属性) 。0代表不使用安全属性。

函数返回：
- `rax` : **返回值寄存器** 。 在调用前，`RAX` 的值不确定。

控制/指针寄存器:
- `rip` : **Instruction Pointer (指令指针)**。指向当前 CPU 正在执行的下一条指令的地址，即 `KERNEL32!CreateFileW` 的入口点。
- `rsp` : **Stack Pointer (栈指针)**。指向当前线程栈的顶部。
- `rbp` : **Base Pointer (基址指针)**。通常用于标记当前函数栈帧的底部。

#### 易失性和非易失性寄存器
- `rbx` :  **非易失性（Non-Volatile）寄存器**，也称为**被调用者保存（Callee-Saved）** 寄存器。程序员和编译器通常用 $RBX$ 来存储在整个函数执行过程中需要保持不变的 **重要本地变量**或 **指针** 。 
- `rsi/rdi` : 同上。在旧的 x86 架构中，它们传统上用作源索引（Source Index）和目标索引（Destination Index），常用于字符串和内存块操作。x64架构中，则类似 `rbx` 。
- 同样非易失性寄存器有： `rbx, rbp, rsi, rdi, r12, r13, r14, r15`
- 而易失性寄存器有： `rcx, rdx,r8,r9 r10, r11` 

#### 状态和段寄存器（不太常用）
状态和段寄存器解读：
```
iopl=0         nv up ei pl zr na po nc
cs=0033  ss=002b  ds=002b  es=002b  fs=0053  gs=002b             efl=00000246
```

**`iopl=0`**
- **含义：** **I/O Privilege Level (I/O 特权级别)**。这是一个 2 位的字段，用于控制当前代码是否可以直接执行 I/O 指令。
- **值：** $0$ 是最高的特权级别（通常是内核模式，Ring 0）。

**nv ....**
- 含义  **RFLAGS** (Registers Flags)，它包含了控制 CPU 操作和指示上次运算结果的各种标志位。

|**缩写**|**含义**|**状态**|**解释**|
|---|---|---|---|
|**nv**|**Overflow Flag**|**nv** (No Overflow)|上一次运算没有发生溢出。|
|**up**|**Direction Flag**|**up** (Up)|字符串操作（如移动数据）的方向是从低地址到高地址（递增）。|
|**ei**|**Interrupt Enable Flag**|**ei** (Enable Interrupts)|CPU **允许**接收外部可屏蔽中断信号。|
|**pl**|**Sign Flag**|**pl** (Positive)|上一次算术运算的结果是非负数（或零）。|
|**zr**|**Zero Flag**|**zr** (Zero)|上一次算术或逻辑运算的结果是**零**。|
|**na**|**Auxiliary Carry Flag**|**na** (Not Applicable)|辅助进位标志，主要用于 BCD (Binary-Coded Decimal) 运算，通常不显示具体状态。|
|**po**|**Parity Flag**|**po** (Parity Odd)|上一次运算结果的低 8 位中，置位（1）的个数是奇数。|
|**nc**|**Carry Flag**|**nc** (No Carry)|上一次算术运算没有产生进位或借位。|
**cs=0033 ...**
- 段寄存器（Segment Registers）。x64架构中，主要用于定义**特权级别**和访问一些特殊结构（如线程本地存储）。在x86架构中，段寄存器主要是辅助地址选择。

|**寄存器**|**值**|**含义**|**解释 (x64 Windows)**|
|---|---|---|---|
|**cs**|`0033`|**Code Segment**|代码段。段选择子 $0x33$ 对应于**用户模式（User Mode, Ring 3）**代码。|
|**ss**|`002b`|**Stack Segment**|栈段。段选择子 $0x2B$ 对应于**用户模式（User Mode, Ring 3）**数据。|
|**ds**|`002b`|**Data Segment**|数据段。与 SS 相同，对应于用户模式数据。|
|**es**|`002b`|**Extra Segment**|附加段。与 SS/DS 相同，对应于用户模式数据。|
|**fs**|`0053`|**FS Segment**|**特殊用途**。在 64 位 Windows 中，$FS$ 寄存器指向**线程信息块 (TEB)**，用于访问线程特定的数据（如异常处理、栈限制等）。|
|**gs**|`002b`|**GS Segment**|**特殊用途**。在 64 位 Windows 中，$GS$ 寄存器通常指向 **KPCR (内核处理器控制区)**，但用户模式下它的使用较少或被重定义。这里的值 $0x2B$ 可能只是一个占位符。|
### 更多函数参数的观察

```c
HANDLE CreateFileW(
  LPCWSTR               lpFileName,           // 1. 文件名 (W版本使用 LPCWSTR)
  DWORD                 dwDesiredAccess,      // 2. 期望的访问权限
  DWORD                 dwShareMode,          // 3. 文件共享模式
  LPSECURITY_ATTRIBUTES lpSecurityAttributes, // 4. 安全属性
  DWORD                 dwCreationDisposition,// 5. 创建/打开的方式
  DWORD                 dwFlagsAndAttributes, // 6. 文件属性和标志
  HANDLE                hTemplateFile         // 7. 模板文件句柄
);
```

- 1. `lpFileName` 下面的值显示为一个字符串。
```
du @rcx
00000073`ac18c1b0  "C:\WINDOWS\System32\DriverStore\"
00000073`ac18c1f0  "FileRepository\nvmi.inf_amd64_c6"
00000073`ac18c230  "ae241e95feb82d\nv-vk64.json"
```

- 2. `dwDesiredAccess` : 注意，不能用 dw, db等指令，这些指令会解析参数为地址。如果是直接看寄存器的值，用r指令。下面的值显示为  `GENERIC_READ`
```
0:000> r @rdx
rdx=0000000080000000
```

- 3. `dwShareMode` ： `r @r8` 结果为 `0x1` 即 `FILE_SHARE_READ` 
- 4. `lpSecurityAttributes` ： 先用r来看地址是否为空。 `r @r9` 。结果为0。

#### 关于 `db, dw, dd, dq`
- `BYTE` :  8字节 。因此， `db` 会把内存按照8字节切分。
- `WORD` : 16字节
- `DWORD` : 32字节
- `QWORD` : 64字节
#### 关于寄存器
**WinDbg 默认将寄存器名称视为其**存储的 **值** 。因此比如 `dd rcx` 实际上将rcx的值作为dd的参数。dd的参数需要使用到一个地址，因此实际会解析 rcx 存储值所指向的地址，而不是rcx的值。

所以要注意： **寄存器在 windbg 中被当作值来使用；而指令后面的参数常常作为地址来解析**

#### 栈上参数
接着，对于5，6，7参数，都保存在栈上。对于栈上来说，约定有：

|**相对地址（相对于 RSP）**|**长度 (字节)**|**含义**|**CreateFileW 参数**|
|---|---|---|---|
|$\mathbf{RSP + 0x00}$|8|**返回地址**（Return Address）|N/A|
|**--- 32 字节阴影空间（Shadow Space）开始 ---**||||
|$\mathbf{RSP + 0x08}$|8|阴影空间槽位 1|（用于保存 $\text{RCX}$ 的副本）|
|$\mathbf{RSP + 0x10}$|8|阴影空间槽位 2|（用于保存 $\text{RDX}$ 的副本）|
|$\mathbf{RSP + 0x18}$|8|阴影空间槽位 3|（用于保存 $\text{R8}$ 的副本）|
|$\mathbf{RSP + 0x20}$|8|阴影空间槽位 4|（用于保存 $\text{R9}$ 的副本）|
|**--- 32 字节阴影空间（Shadow Space）结束 ---**||||
|$\mathbf{RSP + 0x28}$|8|**第 5 个参数**|`dwCreationDisposition`|
|$\mathbf{RSP + 0x30}$|8|**第 6 个参数**|`dwFlagsAndAttributes`|
|$\mathbf{RSP + 0x38}$|8|**第 7 个参数**|`hTemplateFile`|
- **阴影空间** : 其实是按照规范，所有参数都应该在栈上。不过windows会放入寄存器，因此这些栈上空间就相当于被留空了。（实际会保存副本）
- **调用参数的存储位置** (正偏移): 一般在 `rsp` 向高地址的方向去找，每次64位（即8byte）
- **局部变量** (负偏移): 一般在 rsp 向低地址的方向去找，每次64位。所以，第一个局部变量位置在 `rsp-0x08`



- 5. `dwCreateionDisposition` : dw 代表 `DWORD` ，因此用dd指令。容易看到第一个值为 `0x03` ，对应 `OPEN_EXISTING` ，即打开一个文件或设备。如果文件或设备不存在，函数将失败。
```
0:000> dd rsp+0x28
00000073`ac18c190  00000003 00000073 00000080 00000000
```

- 6. `dwCreateionDisposition` 从上一步的结果也容易看到这个参数为 `0x80` (注意，每64bit一个参数，因此 `00000073` 被跳过，随后是 `00000080` ，即 `0x80` ) ，对应值为 `FILE_ATTRIBUTE_NORMAL`

- 7. `hTemplateFile` ，这个参数是HANDLE类型，通常是指针，在 64位程序中，就是8个字节，用dq命令来看。容易看到结果为空。
```
0:000> dq @rsp+0x38
00000073`ac18c1a0  00000000`00000000 00000000`00000000
```

## 函数代码的观察
断点处，我们可以看到 
```
KERNEL32!CreateFileW:
00007ff8`93b970f0 ff25ea270300    jmp     qword ptr [KERNEL32!_imp_CreateFileW (00007ff8`93bc98e0)] ds:00007ff8`93bc98e0={KERNELBASE!CreateFileW (00007ff8`922f3ac0)}
```

这个代表下一步要执行的指令。
- ```00007ff8`93b970f0``` : 当前指令的地址。
- 指令 `ff25ea270300`

#### 指令的解读 `ff25ea270300`
拆分为:
- `ff25` : `jmp qword ptr [RIP+displacement]` 这个操作码（OPCODE）。意思是，以当前 `RIP` （当前指令地址） 作为基地址，叠加 displacement 偏移量后，得到的地址按照QWORD解析，并作为地址进一步跳转到其指向的位置。（因此涉及到一次跳转）
	- 这个跳转通常叫做 IAT （操作系统和指令层都实现的概念：Import Address Table，导入地址表）
	- IAT这个技术用来做动态链接。提供一个间接层，程序在自己的内存空间设置一张指针表。那么通过IAT跳转指令 `jmp qword ptr` （间接跳转指令），就会进一步解码这个表中指向的地址，从而实现RIP的计算、解码加跳转。
- `ea270300` ：4个byte，偏移量。因为是 Little Endian，所以代表的值为 `0x000327ea` 
- 计算间接跳转地址 ```00007ff8`93b970f0``` + `0x000327ea`  = ```00007ff8`93bc98e0``` 。这个地址是IAT表的地址。因此按照里面的值，进一步查找地址，得到 ```00007ff8`922f3ac0```
- 显示区域的 ```ds:00007ff8`93bc98e0={KERNELBASE!CreateFileW (00007ff8`922f3ac0)}``` 显示的是IAT表项的地址。不过并不代表使用了段寄存器，而是反汇编工具的约定，是一个注释，表明它访问的是数据内存（IAT表）

#### 真正的代码位置
经过上面的分析，我们知道，真正的要执行的代码的位置在 ```00007ff8`922f3ac0``` ，其对应的符号表的符号为 `KERNELBASE!CreateFileW`

#### 函数地址和符号
函数地址在调试的时候，经常有与之相关的符号：

```
0:000> ln 00007ff8`922f3ac0
Browse module
Set bu breakpoint

(00007ff8`922f3ac0)   KERNELBASE!CreateFileW   |  (00007ff8`922f3ba0)   KERNELBASE!SleepEx
Exact matches:
```
可以看到地址对应的符号为 `KERNELBASE!CreateFileW`

反之，也可以从符号找到对应的地址：
```
0:000> ln KERNELBASE!CreateFileW
Browse module
Set bu breakpoint

(00007ff8`922f3ac0)   KERNELBASE!CreateFileW   |  (00007ff8`922f3ba0)   KERNELBASE!SleepEx
Exact matches:
```

#### 符号和地址如何关联的呢？
答案：通过调试信息文件。windows自己加载了对应的调试信息。
```
0:000> lm m kernelbase
Browse full module list
start             end                 module name
00007ff8`922b0000 00007ff8`926a8000   KERNELBASE   (pdb symbols)          C:\ProgramData\Dbg\sym\kernelbase.pdb\8314490F996705E2CF4A8DF59DF277DB1\kernelbase.pdb
```

#### **如何知道我们自己程序的调试符号表有没有加载？**
```
0:000> lm m VulkanGLFWDemo
Browse full module list
start             end                 module name
00007ff7`f70b0000 00007ff7`f70fa000   VulkanGLFWDemo C (no symbols)   
```
可以看到没有加载。这是由于我们用的时release无符号版本的程序。（当然，release也可以配置生成pdb调试信息）


#### **如何查看具体汇编代码**（指令方式）
```
0:000> u KERNELBASE!CreateFileW L10
KERNELBASE!CreateFileW:
00007ff8`922f3ac0 488bc4          mov     rax,rsp
00007ff8`922f3ac3 48895808        mov     qword ptr [rax+8],rbx
00007ff8`922f3ac7 48896810        mov     qword ptr [rax+10h],rbp
00007ff8`922f3acb 48897018        mov     qword ptr [rax+18h],rsi
00007ff8`922f3acf 48897820        mov     qword ptr [rax+20h],rdi
00007ff8`922f3ad3 4156            push    r14
00007ff8`922f3ad5 4883ec50        sub     rsp,50h
00007ff8`922f3ad9 448bb42480000000 mov     r14d,dword ptr [rsp+80h]
```
- `u` ： unassemble，反汇编
- `L8` : 8行 。注意 L后面跟的是16进制数。

下面来具体解释这里面的汇编干了什么

|**地址**|**机器码**|**汇编指令**|**解释**|**目的**|
|---|---|---|---|---|
|$\text{922f3ac0}$|$\text{488bc4}$|**`mov rax,rsp`**|将当前的栈指针 $\text{RSP}$ 的值备份到 $\text{RAX}$。|暂时保存栈指针，以便在 $\text{RSP}$ 被后续指令修改后，仍能通过 $\text{RAX}$ 访问原始栈帧（特别是阴影空间）。|
|$\text{922f3ac3}$|$\text{48895808}$|**`mov qword ptr [rax+8],rbx`**|将 $\text{RBX}$ 寄存器的值保存到 $\text{RAX}+0\text{x}08$ 处。|保存 **非易失性** 寄存器 $\text{RBX}$。该地址是 $\text{RSP}+0\text{x}08$，即**阴影空间**的第一个槽位。|
|$\text{922f3ac7}$|$\text{48896810}$|**`mov qword ptr [rax+10h],rbp`**|将 $\text{RBP}$ 的值保存到 $\text{RAX}+0\text{x}10$ 处。|保存 **非易失性** 寄存器 $\text{RBP}$（基址指针）。这是阴影空间的第二个槽位。|
|$\text{922f3acb}$|$\text{48897018}$|**`mov qword ptr [rax+18h],rsi`**|将 $\text{RSI}$ 的值保存到 $\text{RAX}+0\text{x}18$ 处。|保存 **非易失性** 寄存器 $\text{RSI}$。这是阴影空间的第三个槽位。|
|$\text{922f3acf}$|$\text{48897820}$|**`mov qword ptr [rax+20h],rdi`**|将 $\text{RDI}$ 的值保存到 $\text{RAX}+0\text{x}20$ 处。|保存 **非易失性** 寄存器 $\text{RDI}$。这是阴影空间的第四个槽位。|
|$\text{922f3ad3}$|$\text{4156}$|**`push r14`**|将 $\text{R14}$ 寄存器的值压入栈中。|保存 **非易失性** 寄存器 $\text{R14}$。这会使 $\text{RSP}$ 减去 $0\text{x}08$。|
|$\text{922f3ad5}$|$\text{4883ec50}$|**`sub rsp,50h`**|将 $\text{RSP}$ 减去 $0\text{x}50$ ($80$ 字节)。|**分配局部变量和后续函数调用所需的栈帧空间。**|
|$\text{922f3ad9}$|$\text{448bb42480000000}$|**`mov r14d,dword ptr [rsp+80h]`**|将 $\text{RSP} + 0\text{x}80$ 处的 4 字节数据加载到 $\text{R14D}$（$\text{R14}$ 的低 32 位）。|访问栈上参数或调用者栈帧中的局部变量。$0\text{x}80$ 是相对于**调整后的 $\text{RSP}$** 的大偏移量。|

注：
- 类似 `r14d` ，还有 `eax, ebx, ecx` 分别代表 `rax, rbx, rcx` 的低32位
- 更多代码内容，从汇编分析，就比较费时间和偏离主题了。

#### **如何查看具体汇编代码**（UI方式）
可以打开 Disaseembly 面板。（当然如果有源代码+pdb文件，甚至可以直接打开源代码，类似普通在 vscode 中调试一样）

![[WinDbg的初级用法-如何查看具体汇编代码ui方式-01.png]]


# TTD指令
time travel 模式下，有一些便捷指令。尤其常用 `!tt` 和 `!tt <position>`

```
 tt 0                           - Time travel to the beginning of the trace (percentage)
 tt 50                          - Time travel to halfway through the trace (percentage)
 tt 100                         - Time travel to the end of the trace (percentage)
 tt 13.56                       - Time travel to 13.56% through the trace
 tt 1A0:                        - Time travel to position 1A0:0
 tt 1A0:0                       - Time travel to position 1A0:0
 tt 1A0:12F                     - Time travel to position 1A0:12F
 tt 1A0000000000000012F         - Time travel to position 1A0:12F
 tt br rax                      - Time travel to the next write to RAX
 tt br- rax 0x12345678          - Time travel to the previous write to RAX with the value 0x12345678
 tt ba- rw 0x12345678 0x4000    - Find previous position that reads or writes from memory range
                                  [0x12345678 - 0x12345678 + 0x4000).
 tt ba e 0x7fffe0001234 0x30000 - Find next position that executes from specified range. If the
                                  address and range represent the range of ntdll.dll, this command
                                  would find the next position where ntdll.dll is entered.
 tt bm                          - Time travel to the next instruction that is in a different module
                                  than current instruction's module.
 tt bm- ntdll.dll               - Time travel to the previous instruction that is in ntdll.dll

```
此外，在ttd模式下，还可以用 ：
- `p-` ： 回退一步
- `g-` ： 回退到上一个缎带你




# TODO: (未来有空再进一步研究)
1. memory leak调试
2. 脚本：NatVis
3. 脚本：javascript
4. 以及更多学习资料： https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/debugging-resources