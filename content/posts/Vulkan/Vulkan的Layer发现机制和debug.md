---
title: Vulkan的Layer发现机制
date: 2025-11-19T15:35:53+08:00
tags:
  - vulkan
  - layer
  - debug
draft: false
---
这篇文章是我解决Vulkan神秘日志问题的副产品，主要基于文档 [LoaderAndLayerInterface.md](https://chromium.googlesource.com/external/github.com/KhronosGroup/Vulkan-Loader/%2B/HEAD/loader/LoaderAndLayerInterface.md#layer-discovery)
，讲解了Vulkan的Layer发现机制。

快速总结(指定layer的加载做法)
- 利用 `VK_LAYER_PATH` 环境变量，强制只加载指定的layer。
- 利用 `VK_LOADER_LAYERS_DISABLE=~implicit~` 禁用所有 implicit layer。
- 利用 `VK_LOADER_LAYERS_DISABLE=*wegame*` 禁用wegame layer。

p.s. 用quote块和一些插图是我添加的评论和注释。

<!--more-->
# **Layer Discovery（Layer 发现）**
Layer 可以分为两类：
- **Implicit Layers（隐式层）**
- **Explicit Layers（显式层）**
    
两者的主要区别在于：
- **隐式层会被自动启用，除非被覆盖禁用。**
- **显式层必须由应用程序主动启用。**
    

请注意，隐式层并非存在于所有操作系统（例如 Android 上没有隐式层）。

在任意系统上，loader（加载器）会在特定的位置查找它可加载的层的信息。  
这个查找系统中可用 layer 的过程被称为 **Layer Discovery（layer 发现）**。在发现阶段，loader 会确定哪些 layer 是可用的、layer 名称、layer 版本以及该 layer 支持的扩展。  
这些信息会通过 `vkEnumerateInstanceLayerProperties` 返回给应用。

Loader 可用的所有 layer 的集合称为 **layer library（layer 库）**。

vulkan规范规定了 layer 必须遵循的最小约定和规则，尤其是关于 layer 如何与 loader 和其他 layer 交互。

## **Layer Manifest File Usage（Layer 清单文件的使用方式）**

在 Windows、Linux 和 macOS 系统中，使用 JSON 格式的 **manifest 文件** 来存储 layer 信息。  
为了找到系统中安装的 layer，Vulkan loader 会读取这些 JSON 文件，以确定 layer 的名称、属性、以及其扩展。

使用 manifest 文件使得 loader 可以在应用未查询或启用任何扩展时 **避免加载任何共享库文件**（DLL / SO）。

Layer Manifest File 的格式将在后文详细说明。

Android 的 loader **不会使用 manifest 文件**。相反，它会使用称为 **"introspection"（自省）函数** 的一组特殊函数来查询 layer 属性。  
这些函数的目的与读取 manifest 文件相同：获取 layer 所需的全部信息。  
Desktop loader 不会使用这些 introspection 函数，但 layer 仍应包含它们以保持一致性。


## **Android Layer Discovery（Android 上的 Layer 发现）**

在 Android 上，loader 会在：

`/data/local/debug/vulkan`

中查找可枚举的 layer。  
启用了调试的应用可以枚举并启用该目录中的所有 layer。


## **Windows Layer Discovery（Windows 上的 Layer 发现）**

为了找到系统中安装的 layer，Vulkan loader 会扫描以下 Windows 注册表键下的值：

`HKEY_LOCAL_MACHINE\SOFTWARE\Khronos\Vulkan\ExplicitLayers HKEY_CURRENT_USER\SOFTWARE\Khronos\Vulkan\ExplicitLayers HKEY_LOCAL_MACHINE\SOFTWARE\Khronos\Vulkan\ImplicitLayers HKEY_CURRENT_USER\SOFTWARE\Khronos\Vulkan\ImplicitLayers`

对于上述键中 **DWORD 值为 0** 的项，loader 会打开该项名称所对应的 JSON manifest 文件。  
**每个项必须是 manifest 文件的绝对路径名。**

示例图：
![[Vulkan的Layer发现机制和debug-windows-layer-discoverywindows-上的-layer-发现-01.png]]


另外，只有在应用 **没有管理员权限** 时才会查找 `HKEY_CURRENT_USER` 路径。  
这样做是为了确保具有管理员权限的应用不会运行无需管理员权限就能安装的 layer。

此外，loader 还会扫描与 Display Adapter（显示适配器）和其软件组件相关的注册表键，以查找 manifest 文件的位置。  

这些键位于驱动安装期间创建的 device key 中，并包含 Vulkan、OpenGL、Direct3D ICD 等基础设置。

这些 Device Adapter 和 Software Component 键路径应通过 **PnP Configuration Manager API** 获取。  

其中 `000X` 是一个编号键，每个设备一个编号。


`HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Adapter GUID}\000X\VulkanExplicitLayers HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Adapter GUID}\000X\VulkanImplicitLayers HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Software Component GUID}\000X\VulkanExplicitLayers HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Software Component GUID}\000X\VulkanImplicitLayers`

	具体来说，显卡驱动器编号为： `4D36E968-E325-11CE-BFC1-08002BE10318` 
	软件组织编号为： `5C4C3332-344D-483C-8739-259E934C9CC8`
	上面两个key的截图为：

![[Vulkan的Layer发现机制和debug-windows-layer-discoverywindows-上的-layer-发现-02.png]]
![[Vulkan的Layer发现机制和debug-windows-layer-discoverywindows-上的-layer-发现-03.png]]


在 64 位系统上，可能存在另一组注册表值，用于记录 32 位 layer：

`HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Adapter GUID}\000X\VulkanExplicitLayersWow HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Adapter GUID}\000X\VulkanImplicitLayersWow HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Software Component GUID}\000X\VulkanExplicitLayersWow HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Class\{Software Component GUID}\000X\VulkanImplicitLayersWow`

如果上述任意键中存在 **REG_SZ** 类型的值，loader 会打开该键值所指定的 JSON manifest 文件。


每个键值也必须是 manifest 文件的绝对路径。  
若键值为 **REG_MULTI_SZ**，则该值会被解释为 **多个 JSON manifest 文件的路径列表**。

通常情况下，应用程序应将 layer 安装到：`SOFTWARE\Khronos\Vulkan` 路径下。
- PnP 注册表位置仅适用于 **驱动安装包包含的 layer**。  
- 应用安装程序不应修改 device-specific 注册表，而驱动程序不应修改系统注册表。
- Vulkan loader 将打开提供的每个 manifest 文件，以获取 layer 的信息，包括其共享库（DLL）的名称或路径。
- 如果定义了环境变量 `VK_LAYER_PATH`，loader 将忽略注册表中的路径，而是仅查找此变量指定的目录。  

（详见“强制 layer 源目录”一节。）

	所以我们禁用其他Layer的一个办法是使用 `VK_LAYER_PATH` 环境变量


## **Linux Layer Discovery（Linux 上的 Layer 发现）**

在 Linux 上，Vulkan loader 会扫描以下目录中的文件：

`/usr/local/etc/vulkan/explicit_layer.d /usr/local/etc/vulkan/implicit_layer.d /usr/local/share/vulkan/explicit_layer.d /usr/local/share/vulkan/implicit_layer.d /etc/vulkan/explicit_layer.d /etc/vulkan/implicit_layer.d /usr/share/vulkan/explicit_layer.d /usr/share/vulkan/implicit_layer.d $HOME/.local/share/vulkan/explicit_layer.d $HOME/.local/share/vulkan/implicit_layer.d`

一些注意事项：

- `/usr/local/*` 目录可在构建时配置成其他目录。
    
- `$HOME` 是应用用户的 home 目录；对于 suid 程序会忽略 `$HOME` 路径。
    
- `/usr/local/etc` 和 `/usr/local/share` 目录用于本地构建的 layer。
    
- `/usr/share` 目录用于 Linux 发行版安装的 layer。
    
- `$HOME` 下的目录仅在应用没有 root 权限时搜索，以避免 root 权限的应用执行无需 root 权限就能安装的 layer。
    

与 Windows 类似，如果设置了 `VK_LAYER_PATH`，loader 将忽略上述路径，仅使用该变量指定的路径。但该环境变量对 suid 程序无效。


## **macOS Layer Discovery（macOS 上的 Layer 发现）**

在 macOS 上，Vulkan loader 会扫描：

`<bundle>/Contents/Resources/vulkan/explicit_layer.d <bundle>/Contents/Resources/vulkan/implicit_layer.d /etc/vulkan/explicit_layer.d /etc/vulkan/implicit_layer.d /usr/local/share/vulkan/explicit_layer.d /usr/local/share/vulkan/implicit_layer.d /usr/share/vulkan/explicit_layer.d /usr/share/vulkan/implicit_layer.d $HOME/.local/share/vulkan/explicit_layer.d $HOME/.local/share/vulkan/implicit_layer.d`

说明：
- `<bundle>` 是应用程序的 bundle 目录，该目录会被优先扫描。
- `/usr/local/*` 目录可在构建时配置。
- `$HOME` 是当前用户的 home 目录；对 suid 程序会忽略。
- `$HOME` 下的路径只有在应用没有 root 权限时才会被搜索。
- 和 Windows 一样，如果定义了 `VK_LAYER_PATH`，loader 将仅搜索该变量指定路径（suid 程序除外）。
    
# debug layer相关的能力
参考文档： http://vulkan.lunarg.com/doc/view/latest/mac/LoaderDebugging.html
## Layer的禁用
**注意：此功能仅在使用 Vulkan 头文件版本 1.3.234 或之后构建的 Loader 中可用。**

有时，**隐式层（implicit layers）** 会对应用程序造成问题。因此，下一步可以尝试禁用一个或多个已列出的隐式层。 

你可以使用 **过滤环境变量**（`VK_LOADER_LAYERS_ENABLE` 和 `VK_LOADER_LAYERS_DISABLE`）来选择性启用或禁用不同的 layer。  

如果你不确定该怎么做，可以尝试通过设置 `VK_LOADER_LAYERS_DISABLE` 为 `~implicit~` 来 **手动禁用所有隐式层**：

`set VK_LOADER_LAYERS_DISABLE=~implicit~`

这将禁用所有隐式层，并且当启用了 layer 日志时，loader 会以下列方式在日志输出中报告被禁用的层：

```
[Vulkan Loader] WARNING | LAYER:  Implicit layer "VK_LAYER_MESA_device_select" forced disabled because name matches filter of env var 'VK_LOADER_LAYERS_DISABLE'. [Vulkan Loader] WARNING | LAYER:  Implicit layer "VK_LAYER_AMD_switchable_graphics_64" forced disabled because name matches filter of env var 'VK_LOADER_LAYERS_DISABLE'. [Vulkan Loader] WARNING | LAYER:  Implicit layer "VK_LAYER_Twitch_Overlay" forced disabled because name matches filter of env var 'VK_LOADER_LAYERS_DISABLE'.
```

	对于我们程序的问题来说，可以使用 `VK_LOADER_LAYERS_DISABLE=VK_LAYER_TENCENT_wegame_cross_overlay` 禁用wegame的layer


## **选择性重新启用层（Selectively Re-enable Layers）**

**注意：此功能仅在使用 Vulkan 头文件版本 1.3.234 或之后构建的 Loader 中可用。**

在调试由 layer 引起的问题时，一个有效的策略是：  
**先禁用所有 layer，再逐个重新启用。**  
如果问题重新出现，则能立刻确定是哪个 layer 导致了问题。

例如，在上面的被禁用 layer 列表中，我们选择性地重新启用某一个：

`set VK_LOADER_LAYERS_DISABLE=~implicit~ set VK_LOADER_LAYERS_ENABLE=*AMD*`

这样将保持 `"VK_LAYER_MESA_device_select"` 和 `"VK_LAYER_Twitch_Overlay"` 继续被禁用，  
而 `"VK_LAYER_AMD_switchable_graphics_64"` 会被启用。

### **示例：禁用所有隐式层，但允许名称中包含 steam 或 mesa 的 layer**

```
set VK_LOADER_LAYERS_DISABLE=~implicit~
set VK_LOADER_LAYERS_ALLOW=*steam*,*Mesa*
```

# 更多
[[posts/Vulkan/Vulkan的ICD机制|Vulkan的ICD机制]]
