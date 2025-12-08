---
title: 记录调试Vulkan程序打印奇怪日志的问题
date: 2025-11-17T21:52:05+08:00
tags:
  - vulkan
  - cpp
  - 调试
draft: false
---
为什么好好的vulkan程序会突然打印神秘的日志？是代码的扭曲，还是SDK的沦丧？且看我慢慢分解。

<!--more-->
## 起因

最近开始学习 `Vulkan` 图形接口，依照 https://vulkan-tutorial.com/ 的教程配合ChatGpt, Gemni, DeepSeek，学起来速度飞起，不亦乐乎。最后，在用了2-3天的时候，成功画出了第一个三角形。

随后，我发现程序有一个奇怪的地方：

![[记录调试Vulkan程序打印奇怪日志的问题-1763387839953.png|700x416]]

这个文件的全名是： `VulkanGLFWDemo.20251117-xxxxxx-xxxx.log`

我的代码基本上就是照着tutorial复刻的，有改动，但都是在自己理解的情况下做的一些简单改动。绝对没有日志打印的操作。

怀着好奇心，我打开这个文件，想看看到底是啥日志。夸张的事情来了：
![[记录调试Vulkan程序打印奇怪日志的问题-1763387971733.png]]

虽然后缀是 `.log` 但是是个二进制文件！但二进制文件咱就看不了了么？显然不是，用hex editor插件打开。我要看看二进制中是不是有什么字符串，能让我猜出来到底咋回事。

![[记录调试Vulkan程序打印奇怪日志的问题-1763388065279.png]]

WTF？！

## 经过
鉴于自己新学Vulkan，可能不够熟练，也许是某个编译配置的开关，或者vulkan的一些底层机制我没学到，会有一些默认的打印操作。于是我虚心请教了AI的看法……

随后，经历了跟AI的各种狂猜乱试，我发现，完全是“两个臭皮匠”在讨论。

AI可以不停的给我提出各种各样没用的方案。

看来定位不到核心的原因，我是没办法解决这个问题了。

考虑到，程序无非就是二进制在CPU上跑，我直接动态调试二进制程序不就可以了？于是开启了我的WinDbg之路。

## WinDbg
**关于 WinDbg 的使用，更多参见** [WinDbg的初级用法]({{< relref "posts/调试/WinDbg的初级用法.md" >}})

# 问题定位
## 增加断点处的行为(scripting)
首先，我们在创建文件的位置，增加一些脚本，打印一下文件名。
```
bp KERNELBASE!CreateFileA "r rcx; da @rcx; k L3; g"
bp KERNELBASE!CreateFileW "r rcx; du @rcx; k L3; g"
```

- `r rcx` ： 打印 rcx的值
- `du rcx` ：以unicode编码解析rcx指向的地址
- `k L3` : 打印3行堆栈
- `g` ： 不停止，继续执行。

接着让我们运行看下会发生什么，将我们的断点配置如下：
![[WinDbg的初级用法-1763438550768.png]]

输出很长。可以见有很多文件都被打开。（大大出乎预料）

下面一段是摘抄的部分日志：
```
rcx=00000073ac18c200
00000073`ac18c200  "C:\ProgramData\obs-studio-hook\o"
00000073`ac18c240  "bs-vulkan64.json"
 # Child-SP          RetAddr               Call Site
00 00000073`ac18c1b8 00007fff`8b77f6dc     KERNEL32!CreateFileW
01 00000073`ac18c1c0 00007fff`8b77f277     vulkan_1!vkResetEvent+0x4e14c
02 00000073`ac18c2e0 00007fff`8b776595     vulkan_1!vkResetEvent+0x4dce7
rcx=00000073ac18c1d0
00000073`ac18c1d0  "C:\Program Files (x86)\WeGame\ap"
00000073`ac18c210  "ps\Cross\Core\Stable\CrossVulkan"
00000073`ac18c250  "Layer64.json"
 # Child-SP          RetAddr               Call Site
00 00000073`ac18c188 00007fff`8b77f6dc     KERNEL32!CreateFileW
01 00000073`ac18c190 00007fff`8b77f277     vulkan_1!vkResetEvent+0x4e14c
02 00000073`ac18c2e0 00007fff`8b776595     vulkan_1!vkResetEvent+0x4dce7
rcx=00000073ac18c1f0
00000073`ac18c1f0  "C:\Program Files (x86)\Steam\Ste"
00000073`ac18c230  "amOverlayVulkanLayer64.json"
 # Child-SP          RetAddr               Call Site
00 00000073`ac18c1a8 00007fff`8b77f6dc     KERNEL32!CreateFileW
01 00000073`ac18c1b0 00007fff`8b77f277     vulkan_1!vkResetEvent+0x4e14c
02 00000073`ac18c2e0 00007fff`8b776595     vulkan_1!vkResetEvent+0x4dce7
```

## 日志分析
由于文件很长，因此我用AI编写了脚本专门处理上面的日志文件，提取对应的调用函数，以及打开的文件。（特意跳过stack中，系统相关的函数）

```python
'''
在 windbg 调试程序的时候。用如下方法设置断点：

bp KERNELBASE!CreateFileA "r rcx; da @rcx; k L3; g"
bp KERNELBASE!CreateFileW "r rcx; du @rcx; k L3; g"

会在中断的地方打印第一个参数。（这里是文件名字）。本脚本则是为了处理输出的日志，提取对应有效信息。
'''
import re
import argparse
import sys
import os

# 定义系统调用函数的前缀（使用更标准的常量命名）
SYSTEM_CALLS_PREFIX = ['KERNEL32!', 'ntdll!',
                       'ntoskrnl!', 'win32u!', 'WOW64!', 'WOW64T!', 'WOW64CPU!']


def split_blocks(log_text):
  """
  根据 'rcx=' 分隔符将日志文本拆分成独立的块。
  """
  # 使用 re.split，并保留分隔符
  blocks = re.split(r'(rcx=.*)', log_text)
  # 清理和组合：将分隔符与其后的内容组合成一个块
  processed_blocks = []

  for i in range(1, len(blocks), 2):
    if i + 1 < len(blocks):
      processed_blocks.append(blocks[i] + blocks[i + 1])

  return [block.strip() for block in processed_blocks if block.strip()]


def extract_string_from_block(block):
  """
  从一个日志块中提取并拼接双引号内的字符串，形成完整的路径。
  """
  # 正则表达式匹配行首的地址 (例如 0000022a`1b31a090) 后面的双引号内容
  path_pattern = re.compile(
      r'^\s*[\da-fA-F]+`[\da-fA-F]+\s+"(.*?)"$', re.MULTILINE)
  # 查找所有匹配项
  path_segments = path_pattern.findall(block)
  # 拼接所有段落
  string_value = "".join(path_segments)

  return string_value


def extract_rcx_id(block):
  """
  从一个日志块的开头提取 rcx=... 的值作为块的标识。
  """
  # 正则表达式匹配 'rcx=' 后跟至少一个或多个十六进制字符
  rcx_pattern = re.compile(r'(rcx=[\da-fA-F]+)', re.IGNORECASE)
  rcx_match = rcx_pattern.search(block)

  if rcx_match:
    return rcx_match.group(1)
  else:
    return "N/A"


def extract_callsite_info(block):
  """
  从一个日志块中提取 Call Site 信息，并找到第一个非系统调用函数。
  """

  # Call Site 区域通常以 '# Child-SP' 开始
  callstack_start_marker = '# Child-SP'

  if callstack_start_marker not in block:
    return "Call Site region not found."

  # 找到 Call Site 区域的起始位置
  start_index = block.find(callstack_start_marker)
  callstack_section = block[start_index:]

  # 按行分割
  lines = callstack_section.split('\n')

  # 提取 Call Site
  call_sites = []
  # 跳过标题行和可能为空的行
  for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
      continue

    # 假设 Call Site 是每行最后一个非空的字段（通常是模块!函数名+偏移量）
    parts = line.split()
    if len(parts) >= 4:
      call_site = parts[-1]
      call_sites.append(call_site)

  # 查找第一个非系统调用函数
  for site in call_sites:
    is_system_call = False
    # 排除地址/偏移量部分，只保留函数名（如 igxelpicd64!DumpRegistryKeyDefinitions）
    if '!' not in site:
      continue

    for sys_call in SYSTEM_CALLS_PREFIX:
      if site.startswith(sys_call):
        is_system_call = True
        break

    if not is_system_call:
      return site

  return "Only system calls or no calls found."


def parse_log(log_text):
  """
  主解析函数，协调所有子函数。
  """

  blocks = split_blocks(log_text)
  results = []

  for block in blocks:
    rcx_value = extract_rcx_id(block)
    string_value = extract_string_from_block(block)
    first_non_sys_call = extract_callsite_info(block)

    # 检查是否提取到有效的字符串和 Call Site
    if string_value and first_non_sys_call != "Only system calls or no calls found.":
      results.append({
          "rcx_value": rcx_value,
          "string_value": string_value,
          "first_non_system_call": first_non_sys_call
      })

  return results

# --- 新增命令行参数和主函数 ---


def main():
  """
  程序入口点，处理命令行参数和文件读取。
  """
  parser = argparse.ArgumentParser(
      description="解析 WinDbg 日志文件，提取文件路径和第一个非系统调用 Call Site。"
  )
  # 定义必须传入的日志文件参数
  parser.add_argument(
      "log_file",
      type=str,
      help="要解析的 WinDbg 日志文件路径。"
  )

  # 定义可选的输出文件参数
  parser.add_argument(
      "-o", "--output",
      type=str,
      help="将解析结果写入指定文件（例如 result.txt）。如果未指定，则打印到控制台。"
  )

  args = parser.parse_args()

  log_file_path = args.log_file
  output_file_path = args.output

  if not os.path.exists(log_file_path):
    print(f"错误：文件未找到 -> {log_file_path}", file=sys.stderr)
    sys.exit(1)

  try:
    # 读取日志文件内容，使用 'utf-8' 或 'latin-1' 应对可能的编码问题
    with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
      log_content = f.read()
  except Exception as e:
    print(f"读取文件时发生错误: {e}", file=sys.stderr)
    sys.exit(1)

  # 执行解析
  parsed_results = parse_log(log_content)

  # 格式化输出结果
  output_lines = []
  for i, result in enumerate(parsed_results):
    output_lines.append("-" * 50)
    output_lines.append(f"记录 {i + 1} ({result['rcx_value']})")
    output_lines.append(f"  文件路径/字符串: {result['string_value']}")
    output_lines.append(f"  调用点: {result['first_non_system_call']}")
  output_lines.append("-" * 50)
  output_text = "\n".join(output_lines)

  # 处理输出
  if output_file_path:
    try:
      with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(output_text)
      print(f"解析结果已成功写入文件: {output_file_path}")
    except Exception as e:
      print(f"写入文件时发生错误: {e}", file=sys.stderr)
      sys.exit(1)
  else:
    # 打印到控制台
    print(output_text)


if __name__ == "__main__":
  main()

```

处理结果（部分摘要）：
```
--------------------------------------------------
记录 1 (rcx=00000073ac18c200)
  文件路径/字符串: C:\ProgramData\obs-studio-hook\obs-vulkan64.json
  调用点: vulkan_1!vkResetEvent+0x4e14c
--------------------------------------------------
记录 2 (rcx=00000073ac18c1d0)
  文件路径/字符串: C:\Program Files (x86)\WeGame\apps\Cross\Core\Stable\CrossVulkanLayer64.json
  调用点: vulkan_1!vkResetEvent+0x4e14c
--------------------------------------------------
记录 3 (rcx=00000073ac18c1f0)
  文件路径/字符串: C:\Program Files (x86)\Steam\SteamOverlayVulkanLayer64.json
  调用点: vulkan_1!vkResetEvent+0x4e14c
--------------------------------------------------
记录 4 (rcx=00000073ac18c1f0)
  文件路径/字符串: C:\Program Files (x86)\Steam\SteamFossilizeVulkanLayer64.json
  调用点: vulkan_1!vkResetEvent+0x4e14c
--------------------------------------------------
记录 5 (rcx=00000073ac18c1b0)
  文件路径/字符串: C:\Program Files (x86)\Epic Games\Launcher\Portal\Extras\Overlay\EOSOverlayVkLayer-Win32.json
  调用点: vulkan_1!vkResetEvent+0x4e14c
--------------------------------------------------
记录 6 (rcx=00000073ac18c1b0)
  文件路径/字符串: C:\Program Files (x86)\Epic Games\Launcher\Portal\Extras\Overlay\EOSOverlayVkLayer-Win64.json
  调用点: vulkan_1!vkResetEvent+0x4e14c
--------------------------------------------------
...
--------------------------------------------------
记录 1025 (rcx=0000022a1b31a090)
  文件路径/字符串: C:\Users\develop\AppData\LocalLow\Intel\ShaderCache\fef977ca3300ec0bc2c0cffc3b7876ee20569af48fb97cdc1b368bbc0e5a57f6   
  调用点: igxelpicd64!DumpRegistryKeyDefinitions+0xb43aa
--------------------------------------------------
记录 1026 (rcx=0000022a1b31a090)
  文件路径/字符串: C:\Users\develop\AppData\LocalLow\Intel\ShaderCache\ff99df07dcd0c6178ee47752e83177aee8f50f71c5e1bf8eaf748c39909b3bb1   
  调用点: igxelpicd64!DumpRegistryKeyDefinitions+0xb43aa
--------------------------------------------------
记录 1027 (rcx=0000022a1b31a090)
  文件路径/字符串: C:\Users\develop\AppData\LocalLow\Intel\ShaderCache\ffbf928ad5120a2f1efed1a992d0e667884951d6f937bdb98f037eae46cde6e1   
  调用点: igxelpicd64!DumpRegistryKeyDefinitions+0xb43aa
--------------------------------------------------
```
## 日志问题
首先，居然打开了1027个文件！！大部分都是由 igxelpicd64 和 igvk64 打开的。这两个是什么？



## 原因定位
### 1. 本地打开日志文件
通过日志，我们可以搜索，找到：
```
rcx=0000022a16429dc0
0000022a`16429dc0  "C:/Program Files (x86)/WeGame/ap"
0000022a`16429e00  "ps/Cross/Core/Stable/../../Log/V"
0000022a`16429e40  "ulkanGLFWDemo.20251118-120259-84"
0000022a`16429e80  "2.log"
 # Child-SP          RetAddr               Call Site
00 00000073`ac189e88 00007ff8`499ba227     KERNEL32!CreateFileW
01 00000073`ac189e90 00007ff8`499b9729     CrossVulkanLayer64!base::BaseTimer::Stop+0xc5297
02 00000073`ac189f80 00007ff8`499ba53d     CrossVulkanLayer64!base::BaseTimer::Stop+0xc4799
```
显然，有个奇怪的模块调用。

可以看到 `CrossVulkanLayer64` 这个模块是罪魁祸首，我们看看到底这个模块啥来头

```
0:000> lmv m CrossVulkanLayer64
Browse full module list
start             end                 module name
00007fff`8bb10000 00007fff`8bcdf000   CrossVulkanLayer64   (export symbols)       CrossVulkanLayer64.dll
    Loaded symbol image file: CrossVulkanLayer64.dll
    Mapped memory image file: C:\Program Files (x86)\WeGame\apps\Cross\Core\Stable\CrossVulkanLayer64.dll
    Image path: C:\Program Files (x86)\WeGame\apps\Cross\Core\Stable\CrossVulkanLayer64.dll
    Image name: CrossVulkanLayer64.dll
    Browse all global symbols  functions  data  Symbol Reload
    Timestamp:        Tue Sep 10 20:00:11 2024 (66E034CB)
    CheckSum:         001D4A34
    ImageSize:        001CF000
    Mapping Form:     Loaded
    File version:     1.0.0.0
    Product version:  1.0.0.0
    File flags:       0 (Mask 17)
    File OS:          4 Unknown Win32
    File type:        2.0 Dll
    File date:        00000000.00000000
    Translations:     0804.04b0
    Information from resource tables:
        CompanyName:      Tencent
        ProductName:      Tencent.WeGame.Cross
        InternalName:     VulkanLayer
        ProductVersion:   1.0.0.0
        FileVersion:      1.0.0.0
        FileDescription:  Tencent.WeGame.Cross.VulkanLayer
        LegalCopyright:   Copyright (C) 2017 Tencent.All Rights Reserved
        LegalTrademarks:  Tencent

```

**原来是你！腾讯，WeGame！**
### 2. igvk64被疯狂调用和操作（未解决）
在我们通过 `CreateFileW` 断点，打印所有打开文件的操作的时候。日志里产生了大量 igvk64 和 igxeplicd 的调用。到底是怎么回事？

在出问题的时候，手动中断，获取到堆栈信息：
```
[0x0]   KERNEL32!CreateFileW   0x55168e3588   0x7fff7f6e783a   
[0x1]   igvk64!ctlTemperatureGetState+0x751fba   0x55168e3590   0x7fff7f6e67e9   
[0x2]   igvk64!ctlTemperatureGetState+0x750f69   0x55168e3760   0x7fff7f6d17f9   
[0x3]   igvk64!ctlTemperatureGetState+0x73bf79   0x55168e3800   0x7fff7f6cecfb   
[0x4]   igvk64!ctlTemperatureGetState+0x73947b   0x55168e39a0   0x7fff7f6ce00b   
[0x5]   igvk64!ctlTemperatureGetState+0x73878b   0x55168e39e0   0x7fff7f6c4276   
[0x6]   igvk64!ctlTemperatureGetState+0x72e9f6   0x55168e3a30   0x7fff7ee7040f   
[0x7]   igvk64!DumpRegistryKeyDefinitions+0x1c605f   0x55168e3ba0   0x7fff7ee607fb 
[0x8]   igvk64!DumpRegistryKeyDefinitions+0x1b644b   0x55168e41a0   0x7fff7ee476a4 
[0x9]   igvk64!DumpRegistryKeyDefinitions+0x19d2f4   0x55168e4310   0x7fff7ee31bd5 
[0xa]   igvk64!DumpRegistryKeyDefinitions+0x187825   0x55168e43c0   0x7fff7eda31e6 
[0xb]   igvk64!DumpRegistryKeyDefinitions+0xf8e36   0x55168e4410   0x7fff7ed87534  
[0xc]   igvk64!DumpRegistryKeyDefinitions+0xdd184   0x55168fb620   0x7fff7ed5ec7d  
[0xd]   igvk64!DumpRegistryKeyDefinitions+0xb48cd   0x55168fb690   0x7fff7ece0ca5  
[0xe]   igvk64!DumpRegistryKeyDefinitions+0x368f5   0x55168fb6e0   0x7fffbd89c6dc  
[0xf]   vulkan_1!vkResetEvent+0x4b14c   0x55168fb7b0   0x7fff810205e7   
[0x10]   VkLayer_khronos_validation!vulkan_layer_chassis::CreateInstance+0x217   
[0x11]   CrossVulkanLayer64!vkCreateInstance+0x180   0x55168fbad0   0x7ff8498fcacb 
[0x12]   graphics_hook64!dummy_debug_proc+0x294b   0x55168fbbe0   0x7fff741fc952   
[0x13]   nvoglv64!DrvPresentBuffers+0x3698d2   0x55168fbca0   0x7fffbd883652   
[0x14]   vulkan_1!vkResetEvent+0x320c2   0x55168fbcd0   0x7fffbd8a751e   
[0x15]   vulkan_1!vkResetEvent+0x55f8e   0x55168fc000   0x7ff717220f44   
[0x16]   VulkanGLFWDemo!HelloTriangleApplication::createInstance+0x244   0x55168ff410   0x7ff717224b64
```


关于 igxeplicd 产生的大量文件创建。

```
 # Child-SP          RetAddr               Call Site
00 00000055`168fd778 00007fff`f46ce16a     KERNEL32!CreateFileW
01 00000055`168fd780 00007fff`f46cb720     igxelpicd64!DumpRegistryKeyDefinitions+0xb43aa
02 00000055`168fdb70 00007fff`f46c8cfb     igxelpicd64!DumpRegistryKeyDefinitions+0xb1960
03 00000055`168fdd10 00007fff`f46c800b     igxelpicd64!DumpRegistryKeyDefinitions+0xaef3b
04 00000055`168fdd50 00007fff`f46bbe16     igxelpicd64!DumpRegistryKeyDefinitions+0xae24b
05 00000055`168fdda0 00007fff`f457ce7c     igxelpicd64!DumpRegistryKeyDefinitions+0xa2056
06 00000055`168fdf10 00007fff`f457b59e     igxelpicd64!DrvValidateVersion+0x13c57c
07 00000055`168fe4e0 00007fff`f456e572     igxelpicd64!DrvValidateVersion+0x13ac9e
08 00000055`168fe520 00007fff`f443f6aa     igxelpicd64!DrvValidateVersion+0x12dc72
09 00000055`168fe560 00007fff`f53bacfe     igxelpicd64!DrvDescribePixelFormat+0x3a
0a 00000055`168fe5b0 00007fff`f53fd7e9     OpenGL32!_DescribeDriverPixelFormat+0x5a
0b 00000055`168fe5f0 00007fff`f5396e9f     OpenGL32!LoadAvailableDrivers+0x3d9
0c 00000055`168fec50 00007fff`7422005c     OpenGL32!wglDescribePixelFormat+0xdf
0d 00000055`168fed90 00007fff`74223622     nvoglv64!vk_optimusGetInstanceProcAddr+0x230ec
0e 00000055`168fedc0 00007fff`7421cfd7     nvoglv64!vk_optimusGetInstanceProcAddr+0x266b2
0f 00000055`168fee10 00007fff`bd8ad9cc     nvoglv64!vk_optimusGetInstanceProcAddr+0x20067
10 00000055`168fee40 00007fff`812b4934     vulkan_1!vkResetEvent+0x5c43c
11 (Inline Function) --------`--------     VkLayer_khronos_validation!vvl::dispatch::Device::CreateSwapchainKHR+0xc1 [C:\SDKBuild\build-X64-1.4.328.1\Vulkan-ValidationLayers\layers\vulkan\generated\dispatch_object.cpp @ 3153] 
12 00000055`168fef30 00007fff`8bb1af8a     VkLayer_khronos_validation!vulkan_layer_chassis::CreateSwapchainKHR+0x2c4 [C:\SDKBuild\build-X64-1.4.328.1\Vulkan-ValidationLayers\layers\vulkan\generated\chassis.cpp @ 10385] 
13 00000055`168ff140 00007ff8`498fdda0     CrossVulkanLayer64!vkCreateSwapchainKHR+0x182
14 00000055`168ff270 00007fff`bd8af465     graphics_hook64!dummy_debug_proc+0x3c20
15 00000055`168ff340 00007ff7`17221c0d     vulkan_1!vkResetEvent+0x5ded5
16 00000055`168ff380 00007ff7`17224b96     VulkanGLFWDemo!HelloTriangleApplication::createSwapChain+0x27d [C:\Users\develop\game-dev\renderer\src\main.cpp @ 985] 
17 00000055`168ff5d0 00007ff7`172286de     VulkanGLFWDemo!HelloTriangleApplication::initVulkan+0x46 [C:\Users\develop\game-dev\renderer\src\main.cpp @ 800] 
18 00000055`168ff600 00007ff7`171f878f     VulkanGLFWDemo!HelloTriangleApplication::run+0x1e [C:\Users\develop\game-dev\renderer\src\main.cpp @ 63] 
19 00000055`168ff630 00007ff7`17256919     VulkanGLFWDemo!main+0x2f [C:\Users\develop\game-dev\renderer\src\main.cpp @ 1431] 
1a 00000055`168ff8a0 00007ff7`172567c2     VulkanGLFWDemo!invoke_main+0x39 [D:\a\_work\1\s\src\vctools\crt\vcstartup\src\startup\exe_common.inl @ 79] 
1b 00000055`168ff8f0 00007ff7`1725667e     VulkanGLFWDemo!__scrt_common_main_seh+0x132 [D:\a\_work\1\s\src\vctools\crt\vcstartup\src\startup\exe_common.inl @ 288] 
1c 00000055`168ff960 00007ff7`172569ae     VulkanGLFWDemo!__scrt_common_main+0xe [D:\a\_work\1\s\src\vctools\crt\vcstartup\src\startup\exe_common.inl @ 331] 
1d 00000055`168ff990 00007ff8`93b6e8d7     VulkanGLFWDemo!mainCRTStartup+0xe [D:\a\_work\1\s\src\vctools\crt\vcstartup\src\startup\exe_main.cpp @ 17] 
1e 00000055`168ff9c0 00007ff8`94fac53c     KERNEL32!BaseThreadInitThunk+0x17
1f 00000055`168ff9f0 00000000`00000000     ntdll!RtlUserThreadStart+0x2c
```

实际上，虽然可以看到validation layer的影子。但无法确定是由其导致的。( **因为validation layer有可能仅仅是转发一下调用** )

## 为什么会这样？Vulkan为什么加载其他的dll？
在 **Vulkan 的设计机制中**，`vkCreateInstance` 会根据调用时指定的 **Layer 列表** 去加载对应 Layer（包括第三方 Validation Layer）的动态库（Windows 下为 `.dll`，Linux 下为 `.so`）。  
这是 Vulkan **Layer 机制**的正常行为，而不是驱动“偷偷加载”。

### 原因
vulkan初始化的时候，会检查注册表，加载所有 `Implicit Layer` 的配置（manifest）。这样同样也会加载对应的dll。这就是为什么 WeGame 的Layer被加载了。（vulkan的这个功能似乎很有安全问题啊！）

**关于validation layer发现机制，更多参见**： [Vulkan的Layer发现机制和debug]({{< relref "posts/Vulkan/Vulkan的Layer发现机制和debug.md" >}})

# 神秘日志问题解决！

## 方法一
仅把我使用的layer，对应的json和dll，存放到项目目录中。用 `VK_LAYER_PATH` 指定程序仅加载我指定的layer。

（暂时方法二更容易，采用方法二）

## 方法二
设定环境变量：

```sh
VK_LOADER_LAYERS_DISABLE=~implicit~
```

或

```sh
VK_LOADER_LAYERS_DISABLE=*wegame*
```


# 遗留问题未解决！intel驱动总被调用
由于内容比较多，单独开了一个帖子来记录。这个问题当前没找到解决方案。


[Vulkan程序中Intel驱动总是被调用（未解决）]({{< relref "posts/Vulkan/Vulkan程序中Intel驱动总是被调用（未解决）.md" >}})



