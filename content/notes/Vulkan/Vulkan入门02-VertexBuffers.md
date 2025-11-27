---
title: Vulkan入门02-VertexBuffers
date: 2025-11-27T22:17:18+08:00
tags:
  - cpp
  - vulkan
  - vertexbuffer
draft: false
---

<!--more-->
## 正文开始


# 顶点输入描述(Vertex Input Desciption)
## Vertex Shader的修改
```glsl
#version 450

layout(location = 0) in vec2 inPosition;
layout(location = 1) in vec3 inColor;

layout(location = 0) out vec3 fragColor;

void main() {
    gl_Position = vec4(inPosition, 0.0, 1.0);
    fragColor = inColor;
}
```

## 布局限定符
### `location` 限定符详解
在 GLSL 中，`location` 是一个 **布局限定符 (layout qualifier)**，用于显式地指定一个变量在内存或管道中的位置索引。它的主要作用是建立 **CPU 端应用程序** 与 **GPU 端着色器** 之间的数据连接。


```glsl
layout(location = 0) in vec2 inPosition; // 位置属性，索引为 0
layout(location = 1) in vec3 inColor;    // 颜色属性，索引为 1
```


- **用途:**
    - `in` (input) 变量是着色器从 **顶点缓冲对象 (VBO)** 中读取的数据。
    - **CPU 端** (例如，使用 OpenGL 或 Vulkan API) 必须使用相同的索引来配置数据源。例如，当你在 CPU 端调用 `glVertexAttribPointer` 或 `vkCmdBindVertexBuffers` 时，你需要指定与 `location` 匹配的索引，告诉 GPU 哪个数据流对应着色器中的哪个输入变量。
    - **在您的代码中:**
        - `inPosition` 对应 **索引 0** 的顶点属性数据（通常是顶点坐标）。
        - `inColor` 对应 **索引 1** 的顶点属性数据（通常是颜色值）。
            
- **重要性:** 确保 CPU/GPU 之间的数据对齐。如果不使用 `location`，编译器会自行分配，但显式指定可以提高 **可移植性** 和 **调试效率**。

```glsl
layout(location = 0) out vec3 fragColor; // 传递给片段着色器的颜色，索引为 0
```
这用于指定 **顶点着色器** 向 **片段着色器 (Fragment Shader)** 传递的变量的位置索引。这些变量在光栅化阶段会被 **插值 (Interpolated)**。

**用途:**
- `out` (output) 变量是顶点着色器计算的结果，并将这些值传递给下一个阶段（通常是片段着色器）。
- **连接机制:** **顶点着色器** 中的 `out` 变量的 `location` 必须与 **片段着色器** 中相应 `in` 变量的 `location` **匹配**，才能正确连接数据流。

### location FAQ
- **如果 顶点着色器有多个 out。都会被光栅化阶段插值么？**
	- 是的，通常情况下，顶点着色器中所有带 out 限定符的变量都会在光栅化阶段被插值 (Interpolated)。
- **有的变量会占用两个location，比如dvec3。为什么？**
	- 答案的核心在于 **数据类型的大小** 和 **硬件的对齐规则**，特别是针对 **双精度浮点数 (Double-Precision Floating-Point, `double`)**。
	- 一个 `location` 通常被设计用来存储一个 **4 字节** 的基本单位，例如一个 `float`、一个 `int` 或一个 `vec4` 的一个分量。因此，一个标准的 `location` 槽位通常是 **16 字节** (即 4 个 4 字节的组件，如 `vec4`)。
	- 而 `dvec3` ，由于双精度浮点数占用8字节，那么这个向量需要占用24字节，因此一个location就无法存下，它必须溢出到并占用下一个连续的 `location` 索引。

### cocos引擎中对应布局限定符
参看 `cocos-engine/editor/assets/chunks/shading-entries/data-structures/vs-input.chunk`


```glsl
//IA Input
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_texCoord;
#if CC_SURFACES_USE_TANGENT_SPACE
  layout(location = 3) in vec4 a_tangent;
#endif

#if CC_SURFACES_USE_VERTEX_COLOR
  in vec4 a_color;
#endif

// Attribute define should depend on system macro, not surface macro
#if CC_SURFACES_USE_SECOND_UV || CC_USE_LIGHTMAP
  in vec2 a_texCoord1;
#endif

#if CC_USE_SKINNING
  #if __VERSION__ > 310
    // strictly speaking this should be u16vec4, but due to poor driver support
    // somehow it seems we can get better results on many platforms using u32vec4
    layout(location = 4) in u32vec4 a_joints;
  #else
    #pragma format(RGBA16UI)
    layout(location = 4) in vec4 a_joints;
  #endif

  layout(location = 5) in vec4 a_weights;
#endif

#if USE_INSTANCING
  #if CC_USE_BAKED_ANIMATION
    in highp vec4 a_jointAnimInfo; // frameID, totalJoints, offset
  #endif
  in vec4 a_matWorld0;
  in vec4 a_matWorld1;
  in vec4 a_matWorld2;
  #if CC_USE_LIGHTMAP
    in vec4 a_lightingMapUVParam;
  #endif
  #if CC_RECEIVE_SHADOW || CC_USE_REFLECTION_PROBE
    in vec4 a_localShadowBiasAndProbeId; // x:shadow bias, y:shadow normal bias, z: reflection probe id, w: blend reflection probe id
  #endif
  #if CC_USE_REFLECTION_PROBE
    in vec4 a_reflectionProbeData; // x:reflection probe blend weight
  #endif
  #if CC_USE_LIGHT_PROBE
    in vec4 a_sh_linear_const_r;
    in vec4 a_sh_linear_const_g;
    in vec4 a_sh_linear_const_b;
  #endif
#endif

#if CC_USE_MORPH
  #if __VERSION__ < 450
    in float a_vertexId;
  #endif
#endif
```

注意有很多没有显示指定location。此时会被动态绑定。做法：
- **搜集已指定的位置**：编译器首先收集所有通过 `layout(location = L)` 显式指定的变量及其占用的位置范围。
- **顺序分配未指定变量：** 对于所有未显式指定 `location` 的变量，编译器会按照它们在 GLSL 源代码中**声明的顺序**，从 **第一个未被占用的、可用的 `location` 索引** 开始，顺序地为它们分配位置。
- 所以，按照这个规则 `a_color` 这个变量如果启动（对应的宏打开），那么可能绑定的位置是3、4或者6。


## 顶点数据定义
根据我们在VS中的布局限定：
```glsl
layout(location = 0) in vec2 inPosition; // 位置属性，索引为 0
layout(location = 1) in vec3 inColor;    // 颜色属性，索引为 1
```

我们顶点数据也要有这两个分量
```cpp
#include <glm/glm.hpp>
struct Vertex {
    glm::vec2 pos;
    glm::vec3 color;
};

const std::vector<Vertex> vertices = {
    {{0.0f, -0.5f}, {1.0f, 0.0f, 0.0f}},
    {{0.5f, 0.5f}, {0.0f, 1.0f, 0.0f}},
    {{-0.5f, 0.5f}, {0.0f, 0.0f, 1.0f}}
};
```

## 绑定描述 (一组数据的读取方式)
描述顶点数据：绑定的索引、大小、移动速率（每个顶点移动，或 每个instance移动）
```cpp
// 描述如何加载顶点数据
VkVertexInputBindingDescription getBindingDescription() {
    VkVertexInputBindingDescription bindingDescription{};
    
    // binding：顶点缓冲区的索引（如果只有一个 VBO，通常为 0）
    bindingDescription.binding = 0;
    
    // stride：两个连续顶点之间的字节数，即 Vertex 结构体的大小
    bindingDescription.stride = sizeof(Vertex);
    
    // inputRate：数据速率。VK_VERTEX_INPUT_RATE_VERTEX 表示每读取一个顶点就移动一次
    bindingDescription.inputRate = VK_VERTEX_INPUT_RATE_VERTEX;

    return bindingDescription;
}
```

## 属性描述 (单个数据内部的读取方式)
因为有两个属性，因此要分别描述两个属性。最终得到属性描述的数组

第一个属性（location=0）， `vec2`
```cpp
attributeDescriptions[0].binding = 0;
attributeDescriptions[0].location = 0;
attributeDescriptions[0].format = VK_FORMAT_R32G32_SFLOAT;
attributeDescriptions[0].offset = offsetof(Vertex, pos);
```

第二个属性（location=1)，vec3
```cpp
attributeDescriptions[1].binding = 0;
attributeDescriptions[1].location = 1;
attributeDescriptions[1].format = VK_FORMAT_R32G32B32_SFLOAT;
attributeDescriptions[1].offset = offsetof(Vertex, color);
```

如果数据不是float：
- `ivec2` : `VK_FORMAT_R32G32_SINT`
- `uvec4` :  `VK_FORMAT_R32G32B32A32_UINT`


通常，Shader中的数据，长度小于4的数组比较常用，效率较高；而是的枚举可以参考上面的用法。


## Pipeline创建时
需要在pipeline创建时候，附带这些配置信息
```cpp
auto bindingDescription = Vertex::getBindingDescription();
auto attributeDescriptions = Vertex::getAttributeDescriptions();

vertexInputInfo.vertexBindingDescriptionCount = 1;
vertexInputInfo.vertexAttributeDescriptionCount = static_cast<uint32_t>(attributeDescriptions.size());
vertexInputInfo.pVertexBindingDescriptions = &bindingDescription;
vertexInputInfo.pVertexAttributeDescriptions = attributeDescriptions.data();
```

# 顶点缓冲区创建 (Vertex Buffer Creation)
## 创建Buffer对象
相对来说比较简单
```cpp
  VkBuffer vertexBuffer;
  void createVertexBuffer() {
    VkBufferCreateInfo bufferInfo{};
    bufferInfo.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bufferInfo.size = sizeof(vertices[0]) * vertices.size();
    bufferInfo.usage = VK_BUFFER_USAGE_VERTEX_BUFFER_BIT;
    bufferInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    if (vkCreateBuffer(device, &bufferInfo, nullptr, &vertexBuffer) !=
        VK_SUCCESS) {
      throw std::runtime_error("failed to create vertex buffer!");
    }
  }
```
当然要记得，有创建就有销毁 `vkDestroyBuffer(device, vertexBuffer, nullptr);`

一些字段解释：
- `VK_BUFFER_USAGE_VERTEX_BUFFER_BIT`：明确告诉 Vulkan，这个缓冲区将用作 **顶点数据** 的来源。
- `VK_SHARING_MODE_EXCLUSIVE`：表示缓冲区将 **只被一个队列族**（例如，只被图形队列）使用。这是最简单和最常见的设置。如果需要在多个队列族（如图形和计算队列）之间共享，则需要使用 `VK_SHARING_MODE_CONCURRENT`

值得注意的是，`vkCreateBuffer` **只创建了缓冲区对象本身**，它代表了 GPU 内存中的一个 **区域定义**。它 **并没有** 实际分配 GPU 内存并将顶点数据复制进去。后续步骤通常包括：
1. 查询内存需求（`vkGetBufferMemoryRequirements`）。
2. 分配合适的设备内存（`vkAllocateMemory`）。
3. 将缓冲区绑定到分配的内存（`vkBindBufferMemory`）。
4. 将实际的顶点数据从 CPU 传输到 GPU 内存中（通常通过 **映射内存** 或 **暂存缓冲区**）。

## 内存需求(Memory Requirements)
Buffer对象还需要绑定内存。获取内存需求：（注意，这步得到的是 `memRequirements` ）
```cpp
VkMemoryRequirements memRequirements;
vkGetBufferMemoryRequirements(device, vertexBuffer, &memRequirements);
```
这个步骤实际会返回 `memRequirements.memoryTypeBits` ，这个flag标记了设备上可以支持这个vertexBuffe使用的类型编号。

在物理设备中，查找合适的内存（符合需求的；不同的内存类型，允许的操作和性能也不一样）。（注意，这步开始查询的则是 `memProperties`）
```cpp
  uint32_t findMemoryType(uint32_t typeFilter,
                          VkMemoryPropertyFlags properties) {
    VkPhysicalDeviceMemoryProperties memProperties;
    vkGetPhysicalDeviceMemoryProperties(physicalDevice, &memProperties);
    for (uint32_t i = 0; i < memProperties.memoryTypeCount; i++) {
      if ((typeFilter & (1 << i)) &&
          (memProperties.memoryTypes[i].propertyFlags & properties) ==
              properties) {
        return i;
      }
    }

    throw std::runtime_error("failed to find suitable memory type!");
  }
```

代码解释：
- 函数参数：
	- typeFilter： 位掩码。指定了哪些内存类型 **可以** 用于特定的资源（例如，你之前创建的 `VkBuffer`）。如果第 $i$ 位被设置，则第 $i$ 种内存类型是可用的。
		- 这个本身的掩码是由物理设备提供的，由第一步得到。
	- properties：位掩码。指定你对内存的 **必需属性**，例如内存是否可由 CPU 访问 (可映射)、是否为快速的设备本地内存等。
		- 这个我们根据需求来传入，比如 
			- `VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT` ：**主机（CPU）可见。** 允许 CPU 通过 `vkMapMemory` 直接读写这块内存。
			- `VK_MEMORY_PROPERTY_HOST_COHERENT_BIT` ：**主机一致性。** 保证 CPU 写入的数据能立即被 GPU 读取，避免手动调用 `vkFlushMappedMemoryRanges`。通常和上面的标签一起使用。
- 函数返回值：可以使用的内存类型索引。
- `vkGetPhysicalDeviceMemoryProperties` : 获取设备内存属性
- 循环：遍历和筛选内存类型。
	- `(typeFilter & (1 << i)` 检查内存类型索引为i的，是否是vertexBuffer可以用的。
	- `(memProperties.memoryTypes[i].propertyFlags & properties) == properties` 检查我们传入的必须属性的掩码是否满足。
## 内存分配(Memory Allocation)
```cpp
    VkMemoryAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    allocInfo.allocationSize = memRequirements.size;
    allocInfo.memoryTypeIndex =
        findMemoryType(memRequirements.memoryTypeBits,
                       VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                           VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);

    if (vkAllocateMemory(device, &allocInfo, nullptr, &vertexBufferMemory) !=
        VK_SUCCESS) {
      throw std::runtime_error("failed to allocate vertex buffer memory!");
    }
    vkBindBufferMemory(device, vertexBuffer, vertexBufferMemory, 0);
```
这个代码比较直观。相当于把之前创建的Buffer对象，分配一个Memory给它。(最后一个代码将allocate的内存绑定给buffer对象)

## 填充顶点缓冲区 (Filling the Vertex Buffer)
```cpp
void* data;
vkMapMemory(device, vertexBufferMemory, 0, bufferInfo.size, 0, &data);
    memcpy(data, vertices.data(), (size_t) bufferInfo.size);
vkUnmapMemory(device, vertexBufferMemory);
```

这段代码的目的是将 CPU 内存中存储的顶点数据（在 vertices 容器中）映射到 GPU 可访问的内存区域，然后将数据 复制 过去，最后 解除映射。
- `vkMapMemory` : 这是一个 Vulkan 函数，用于将 **设备内存** (device memory) 映射到应用程序（CPU）的地址空间。（实际：让操作系统将GPU地址映射到进程的虚拟地址空间；操作系统会创建页表、并调用CPU硬件指令告诉CPU这个地址的特殊性：它是I/O设备地址，采用 WC , Write-Combining的方式处理写入，随后到达这个地址的写入指令会被CPU发送到PCIe总线）
- `memcpy` ： 复制，将我们准备好的数据复制到GPU中。（由于复制数据的指令，CPU提前知道了这个地址的特殊性，于是触发了PCIe的总线上数据的发送）
- `vkUnmapMemory` : 这是一个 Vulkan 函数，用于解除对设备内存的映射。

注意，上面的过程是由于创建显存空间的时候设置了 `HOST_COHERENT_BIT` 。否则则需要单独的动作来进行上传。
## 绑定+绘制 (Binding the Vertex Buffer)
实际是是一个录制的指令，会绑定到上下文的图形管线上。（图形管线定义了VertexInput)

```cpp
vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, graphicsPipeline);

VkBuffer vertexBuffers[] = {vertexBuffer};
VkDeviceSize offsets[] = {0};
vkCmdBindVertexBuffers(commandBuffer, 0, 1, vertexBuffers, offsets);

vkCmdDraw(commandBuffer, static_cast<uint32_t>(vertices.size()), 1, 0, 0);
```

`vkCmdBindVertexBuffers(commandBuffer, 0, 1, vertexBuffers, offsets);`
- `commandBuffer` : 指令写入的buffer
- `firstBinding` (0): **起始绑定点索引。** 它指定了从管线输入的哪个槽位开始绑定缓冲区。通常从 `0` 开始。这对应于你在管线创建时，`VkPipelineVertexInputStateCreateInfo` 中定义的 `VkVertexInputBindingDescription` 数组的索引。 (**这需要对应到正确VertexInputDescription**)
- `bindingCount` (1):**要绑定的缓冲区数量。** 示例中只绑定了一个顶点缓冲区，所以是 `1`。
- `pBuffers` : **缓冲区数组指针。**
- `pOffsets` : **缓冲区偏移量数组指针。** 这是一个与 `pBuffers` 一一对应的数组，指定从每个缓冲区的哪个字节偏移量开始读取顶点数据。
从接口来说，蛮C语言风格的。

`vkCmdDraw(commandBuffer, static_cast<uint32_t>(vertices.size()), 1, 0, 0);`
- `commandBuffer` : 指令写入的buffer
- `vertexCount` : **要绘制的顶点数量。** 这指示了管线应该处理多少个顶点数据。在你的示例中，它等于 `vertices` 数组中元素的总数。
- `instanceCount`: **实例化数量。** 表示要重复绘制的次数。`1` 表示只绘制一次。如果这个值大于 1，GPU 会将同样的几何体绘制多次，这常用于批量渲染相同的对象（如粒子、草地）。
- `firstVertex` : **起始顶点索引。** 这是在顶点缓冲区中开始读取数据的索引。`0` 表示从数组的第一个顶点开始。
- `firstInstance`: **起始实例化索引。** 通常为 `0`

这是一个**非索引绘制 (Non-Indexed Draw)** 命令。这意味着 Vulkan 会按顺序读取顶点缓冲区中的数据，每 $N$ 个顶点（由图元拓扑决定，如 3 个顶点组成一个三角形）构成一个图元，然后绘制它。

**绘制动作实际的逻辑操作取决于InputAssembly环节的设置**

比如InputAssembly设置了三角形带。实际是定义了一种组合模式，类似 `0,1,2;1,2,3;....` 这样的组合模式，来组成图元。**InputAssembly实际决定的是 `0,1,2;1,2,3;` 这种组合模式，也即拓扑规则** 。更具体来说：（如果InputAssembly中设置了三角形）
- 非索引绘制。 `V_0,V_1,V_2` 组成三角形（按照组合模式，直接取顶点）
- 索引绘制。 `V_I0,V_I1,V_I2` 组成三角形 （按照组合模式，先取索引，再取顶点）

## 效果展示
到这里，前两节如果都按照教程操作成功，那么可以正常绘制三角形。
![[Vulkan入门02-VertexBuffers-1764249822704.png]]
# 暂存缓冲区(Staging Buffer)
我们创建的显存，properties指定的是： 
```
VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT
```
这不是最有效率的显存。最有效率的是 `VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT`  ，但通常CPU无法访问。

本小节优化这个部分。创建两个 Vertex Vuffer。
- `staging buffer` : 让CPU方便访问的。（我们把数据复制到这里）
- `final vertex buffer` : 选择更有效率的显存。（调用指令，将数据从staging buffer传输到 final vertex buffer）
## 传输队列(Transfer queue)
我们描述的传输操作，需要专门的队列来支持（显卡特性）。不过具备 `VK_QUEUE_GRAPHICS_BIT`  或者 `VK_QUEUE_COMPUTE_BIT` 的队列能力的，默认支持 `VK_QUEUE_TRANSFER_BIT` 这个能力。

## 重构
把创建Buffer单独分离出一个函数
```cpp
void createBuffer(VkDeviceSize size, VkBufferUsageFlags usage, VkMemoryPropertyFlags properties, VkBuffer& buffer, VkDeviceMemory& bufferMemory) {
    VkBufferCreateInfo bufferInfo{};
    bufferInfo.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    bufferInfo.size = size;
    bufferInfo.usage = usage;
    bufferInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    if (vkCreateBuffer(device, &bufferInfo, nullptr, &buffer) != VK_SUCCESS) {
        throw std::runtime_error("failed to create buffer!");
    }

    VkMemoryRequirements memRequirements;
    vkGetBufferMemoryRequirements(device, buffer, &memRequirements);

    VkMemoryAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    allocInfo.allocationSize = memRequirements.size;
    allocInfo.memoryTypeIndex = findMemoryType(memRequirements.memoryTypeBits, properties);

    if (vkAllocateMemory(device, &allocInfo, nullptr, &bufferMemory) != VK_SUCCESS) {
        throw std::runtime_error("failed to allocate buffer memory!");
    }

    vkBindBufferMemory(device, buffer, bufferMemory, 0); // 0代表偏移量
}
```
## 使用暂存缓冲区
```cpp
  void createVertexBuffer() {
    VkDeviceSize bufferSize = sizeof(vertices[0]) * vertices.size();

    VkBuffer stagingBuffer;
    VkDeviceMemory stagingBufferMemory;

    createBuffer(bufferSize, VK_BUFFER_USAGE_VERTEX_BUFFER_BIT,
                 VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                     VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                 stagingBuffer, stagingBufferMemory);

    void *data;
    vkMapMemory(device, stagingBufferMemory, 0, bufferSize, 0, &data);
    memcpy(data, vertices.data(), (size_t)bufferSize);
    vkUnmapMemory(device, stagingBufferMemory);

    createBuffer(bufferSize, VK_BUFFER_USAGE_VERTEX_BUFFER_BIT,
                 VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, vertexBuffer,
                 vertexBufferMemory);
    copyBuffer(stagingBuffer, vertexBuffer, bufferSize);

    vkDestroyBuffer(device, stagingBuffer, nullptr);
    vkFreeMemory(device, stagingBufferMemory, nullptr);
  }

```
显然，创建了两块显存。一个是用来作为 StagingBuffer要求CPU可见。另一个用来作为，VertexBuffer，要求性能更好。同时再用途上执行了一个为src，另一个为dst+VertexBuffer

接下来实现buffer传输的功能
```cpp
  void copyBuffer(VkBuffer srcBuffer, VkBuffer dstBuffer, VkDeviceSize size) {
    VkCommandBufferAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    allocInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    allocInfo.commandPool = commandPool;
    allocInfo.commandBufferCount = 1;

    VkCommandBuffer commandBuffer;
    vkAllocateCommandBuffers(device, &allocInfo, &commandBuffer);

    VkCommandBufferBeginInfo beginInfo{};
    beginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    beginInfo.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;

    vkBeginCommandBuffer(commandBuffer, &beginInfo);

    VkBufferCopy copyRegion{};
    copyRegion.srcOffset = 0; // Optional
    copyRegion.dstOffset = 0; // Optional
    copyRegion.size = size;
    vkCmdCopyBuffer(commandBuffer, srcBuffer, dstBuffer, 1, &copyRegion);

    VkSubmitInfo submitInfo{};
    submitInfo.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submitInfo.commandBufferCount = 1;
    submitInfo.pCommandBuffers = &commandBuffer;

    vkQueueSubmit(graphicsQueue, 1, &submitInfo, VK_NULL_HANDLE);
    vkQueueWaitIdle(graphicsQueue);

    vkFreeCommandBuffers(device, commandPool, 1, &commandBuffer);
  }
```
实际上和渲染类似，我们需要把指令提交给传输队列，等待传输队列idle（等待执行完毕）

## 总结
目前代码为每一个Buffer都执行了 `vkAllocateMemory` 。实际我们不会这么做，而是创建一个大的，然后自己管理offset。因为设备通常不允许创建很多的buffer。
# 索引缓冲区(Index Buffer)

## 创建IB数据
```cpp
const std::vector<Vertex> vertices = {
    {{-0.5f, -0.5f}, {1.0f, 0.0f, 0.0f}},
    {{0.5f, -0.5f}, {0.0f, 1.0f, 0.0f}},
    {{0.5f, 0.5f}, {0.0f, 0.0f, 1.0f}},
    {{-0.5f, 0.5f}, {1.0f, 1.0f, 1.0f}}
};

const std::vector<uint16_t> indices = { 0, 1, 2, 2, 3, 0 };
```

## 创建 IndexBuffer
相对容易，类似VertexBuffer。但不需要太多配置。直接创建即可。

```cpp
void createIndexBuffer() {
    VkDeviceSize bufferSize = sizeof(indices[0]) * indices.size();

    VkBuffer stagingBuffer;
    VkDeviceMemory stagingBufferMemory;
    createBuffer(bufferSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, stagingBuffer, stagingBufferMemory);

    void* data;
    vkMapMemory(device, stagingBufferMemory, 0, bufferSize, 0, &data);
    memcpy(data, indices.data(), (size_t) bufferSize);
    vkUnmapMemory(device, stagingBufferMemory);

    createBuffer(bufferSize, VK_BUFFER_USAGE_TRANSFER_DST_BIT | VK_BUFFER_USAGE_INDEX_BUFFER_BIT, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, indexBuffer, indexBufferMemory);

    copyBuffer(stagingBuffer, indexBuffer, bufferSize);

    vkDestroyBuffer(device, stagingBuffer, nullptr);
    vkFreeMemory(device, stagingBufferMemory, nullptr);
}
```

## 使用IndexBuffer
相对容易，绘制前，绑定一下。
```cpp
vkCmdBindVertexBuffers(commandBuffer, 0, 1, vertexBuffers, offsets);

vkCmdBindIndexBuffer(commandBuffer, indexBuffer, 0, VK_INDEX_TYPE_UINT16);
```
- 注意这里的数据类型，要指定对。


绘制使用新的命令。
```cpp
vkCmdDrawIndexed(commandBuffer, static_cast<uint32_t>(indices.size()), 1, 0, 0, 0);
```

## 效果
![[Vulkan入门02-VertexBuffers-1764252524778.png]]