---
title: Vulkan入门03-UniformBuffers
date: 2025-12-03T21:54:56+08:00
tags:
  - vulkan
  - uniformbuffer
  - ubo
draft: false
---

![[Vulkan入门03-UniformBuffers-intro-01.png|603x452]]


通过 `VertexBuffer` ，我们可以给每个顶点赋值数据，并传递给 vertex shader 让其可以使用。（通过drawcall启动pipeline）

那么，对于全局的变量（想传递给每个shader），应该怎么做呢？举例来说：
- MVP矩阵 (model-view-project matrix)

<!--more-->

# 描述符集布局(Descriptor Set Layout)
## 描述符 (Descriptor)

定义 着色器访问 GPU 资源（Buffer / Image）的方式。它是 **CPU ↔ GPU资源 ↔ Shader** 的桥梁。

使用描述符(Descriptor) 主要分为3个步骤：
1. 指定 Descriptor Set Layout (布局) （当pipeline创建时）。
	- 布局：binding = 0 是一个 uniform buffer； binding = 1 是一个 sampler
	- 类比：RenderPass定义附件格式，但不是具体的附件
2. 从 Descriptor Pool 分配 Descriptor Set。真正创建一个描述符集合
	- Descriptor Set，指向某个 `VkBuffer` 或者 `VkImageView`
	- 类比：FrameBuffer绑定一个具体的ImageView
3. 在绘制时绑定 Descriptor Set。（类似绘制绑定VB，IB，FB）
	- `vkCmdBindDescriptorSets(...)`

有各种各样的 Descriptor。我们这里只关注 UBO (Uniform Buffer Object)

## 我们要做什么
我们有一个C数据
```cpp
struct UniformBufferObject {
    glm::mat4 model;
    glm::mat4 view;
    glm::mat4 proj;
};
```
- 注意，基于 `glm:mat4` 定义的类型，和glsl中的 `mat4` 类型在数据层面时完全匹配的。（这方便了我们直接memcpy）

希望把这个数据，复制到一个 `VkBuffer` 中，并且可以再VS中以下面的方式访问：

```glsl
#version 450

layout(binding = 0) uniform UniformBufferObject {
    mat4 model;
    mat4 view;
    mat4 proj;
} ubo;

layout(location = 0) in vec2 inPosition;
layout(location = 1) in vec3 inColor;

layout(location = 0) out vec3 fragColor;

void main() {
    gl_Position = ubo.proj * ubo.view * ubo.model * vec4(inPosition, 0.0, 1.0);
    fragColor = inColor;
}
```
- 这里几个变量定义的顺序不重要。`binding` 指令和 `location` 指令类似。（回忆：`location` ，实际创建pipeline的InputVertex时，指定顶点属性配置中，指定的）（所以，可以容易才想到，UBO的binding，应该也是创建pipeline的Descriptor Set配置的时候，具体指定某一个Descriptor的 `binding` ）
- 注意：`binding` 并不是全局唯一。`layout(set = 0, binding = 0) uniform UniformBufferObject { ... } ubo;` 上面代码省略了默认的set。用类比解释：
	- `set` : 柜子
	- `binding` ： 柜子里的抽屉

先暂时放一个整体的连线图：
```
C++ struct
   ↓ memcpy
VkBuffer (size = sizeof(UBO)) 【这里还涉及到 VkDeviceMemory, vkMapMemory】
   ↓
VkDescriptorBufferInfo 【后续操作前，需要在管线中先定义好布局】
   ↓
VkWriteDescriptorSet (binding = 0)
   ↓
VkDescriptorSet 【渲染前，创建buffer后；完成Descriptor的创建】
   ↓
vkCmdBindDescriptorSets【渲染时，绑定具体的DescriptorSet】
   ↓
Shader: layout(set=0, binding=0) uniform ...【shader可以访问Descriptor资源】
```

## 描述符集布局的创建
在创建 pipeline之前，要先创建 **描述符集布局**
```cpp
void initVulkan() {
    ...
    createDescriptorSetLayout();
    createGraphicsPipeline();
    ...
}

...

VkDescriptorSetLayout descriptorSetLayout;
void createDescriptorSetLayout() { // 整个函数仅创建了1个descriptorSetLayout (set=0)
	// 这里仅仅是定义 1 个DescriptorSetLayout下的1个binding。
    VkDescriptorSetLayoutBinding uboLayoutBinding{};
    // 在 descriptor set 中的索引（编号）。这与 shader 中 
    // layout(set=0, binding = 0) 对应。
    uboLayoutBinding.binding = 0;
    // 该 binding 的类型，这里是 VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER，
    // 说明这个 binding 期待一个 Uniform Buffer（或一组 uniform buffers，
    // 如果 descriptorCount > 1）。
    uboLayoutBinding.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
    // 这个binding可以绑定相同单个描述符还是描述符数组
	// =1 时是单个 descriptor；>1 时该 binding 是一个 descriptor 数组。
	// shader 端需要声明成 uniform 块数组才能访问多个元素。
    // 比如 N个同类型 uniform buffers。
    uboLayoutBinding.descriptorCount = 1;
    // 哪些着色器阶段可以访问这个binding。这里定义 Vertex Shader 阶段
    uboLayoutBinding.stageFlags = VK_SHADER_STAGE_VERTEX_BIT;
    // 仅对 sampler 类型有意义 （暂时不讲）
    uboLayoutBinding.pImmutableSamplers = nullptr; // Optional

	// 1个 DescriptorSetLayout 可以做多个 Binding （下面只做了1个binding）
	VkDescriptorSetLayoutCreateInfo layoutInfo{};
	layoutInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
	layoutInfo.bindingCount = 1;
	layoutInfo.pBindings = &uboLayoutBinding;
	
	if (vkCreateDescriptorSetLayout(device, &layoutInfo, nullptr, &descriptorSetLayout) != VK_SUCCESS) {
	    throw std::runtime_error("failed to create descriptor set layout!");
	}
}

void createGraphicsPipeline() {
	...
	VkPipelineLayoutCreateInfo pipelineLayoutInfo{};
	pipelineLayoutInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
	// 创建 pipeline layout的时候，可以创建多个 DescriptorSetLayout
	// 我们这里仅绑定了1个
	pipelineLayoutInfo.setLayoutCount = 1;
	pipelineLayoutInfo.pSetLayouts = &descriptorSetLayout;	
	...
}

void cleanup() {
    cleanupSwapChain();
    vkDestroyDescriptorSetLayout(device, descriptorSetLayout, nullptr);
    ...
}
```

## Uniform buffer创建
上一节，做到了shader能用。但GPU上数据并没有做。

**UniformBuffer的数量：每一帧使用一个独立的 uniform buffer**

回顾StagingBuffer的作用：**大数据、偶尔更新、希望数据在 DEVICE_LOCAL 中** ，而UniformBuffer特点则是小数据，常更新。因此更适合 `HOST_VISIBLE` 内存。

相关代码如下
```cpp
// 确保每帧都有1个UBO

// Buffer对象句柄。描述 buffer 资源 （更类似于meta信息）
// 用途（vertex/uniform/storage）、大小、可以被绑定到 descriptor
std::vector<VkBuffer> uniformBuffers; 
// GPU显存句柄。代表实际的显存块。
// 需要用 vkAllocateMemory 来创建。
// 可用 vkBindBufferMemory 绑定到 VkBuffer (这样可以用VkBuffer对象来配合函数，操作GPU显存；被shader和descriptor访问使用；类似 vkImageView 和 vkImage 的关系)
// 可用 vkMapMemory 获取到 uniformBuffersMapped 这里的指针。
std::vector<VkDeviceMemory> uniformBuffersMemory; 
// GPU显存映射后的进程空间的虚拟地址 (实际要复制的dst；复制后会被驱动自动/手动同步到显存)
std::vector<void*> uniformBuffersMapped; 

void initVulkan() {
    ...
    createVertexBuffer();
    createIndexBuffer();
    createUniformBuffers();
    ...
}

void createUniformBuffers() {
    VkDeviceSize bufferSize = sizeof(UniformBufferObject);

    uniformBuffers.resize(MAX_FRAMES_IN_FLIGHT);
    uniformBuffersMemory.resize(MAX_FRAMES_IN_FLIGHT);
    uniformBuffersMapped.resize(MAX_FRAMES_IN_FLIGHT);

    for (size_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
        createBuffer( // 之前写过的便利函数，方便创建和绑定VkBuffer、VkDeviceMemory
            bufferSize,
            VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,   // 用途为UBO
            VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | // CPU可见
            VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, // 写入后 GPU 自动可见，无需手动 flush
            uniformBuffers[i],
            uniformBuffersMemory[i]
        ); 

// 使用持久映射（persistent mapping）技术：vkMapMemory 返回的指针在整个应用生命周期内有效
// CPU 可以直接写入 UBO 数据，GPU 可以访问，无需每帧重复映射
        vkMapMemory(
            device,
            uniformBuffersMemory[i],
            0,
            bufferSize,
            0,
            &uniformBuffersMapped[i]
        );
    }
}

void cleanup() {
	...
    for (size_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
        vkDestroyBuffer(device, uniformBuffers[i], nullptr);
        vkFreeMemory(device, uniformBuffersMemory[i], nullptr);
    }
	// Descriptor 实际持有 Uniform Buffer，因此要后释放。
    vkDestroyDescriptorSetLayout(device, descriptorSetLayout, nullptr);
    ...
}
```

# Uniform Buffer
## 更新UniformBuffer
比较简单直观：
```cpp
#define GLM_FORCE_RADIANS
#include "glm/glm.hpp"
#include <glm/gtc/matrix_transform.hpp>

...
void drawFrame() {
    ...

    updateUniformBuffer(currentFrame);

    ...

    VkSubmitInfo submitInfo{};
    submitInfo.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;

    ...
}

...

void updateUniformBuffer(uint32_t currentImage) {
    static auto startTime = std::chrono::high_resolution_clock::now();

    auto currentTime = std::chrono::high_resolution_clock::now();
    float time = std::chrono::duration<float, std::chrono::seconds::period>(currentTime - startTime).count();
	
	UniformBufferObject ubo{}; 
	// 按照经过的时间进行旋转（恒定角速度）
	// 模型变换：围绕 Z 轴旋转（恒定角速度）
	ubo.model = glm::rotate(glm::mat4(1.0f), time * glm::radians(90.0f), glm::vec3(0.0f, 0.0f, 1.0f));
	// 视图变换：摄像机从 (2,2,2) 看向原点
	ubo.view = glm::lookAt(glm::vec3(2.0f, 2.0f, 2.0f), glm::vec3(0.0f, 0.0f, 0.0f), glm::vec3(0.0f, 0.0f, 1.0f));
	// 投影变换：45° 视角，近平面0.1，远平面10
	ubo.proj = glm::perspective(glm::radians(45.0f), swapChainExtent.width / (float) swapChainExtent.height, 0.1f, 10.0f);
	// 由于GLM库默认给OpenGL设计的，Vulkan里需要flip Y坐标。
	ubo.proj[1][1] *= -1;
	
    // 对于 HOST_COHERENT 内存，写入后 GPU 可直接访问，无需 flush
	memcpy(uniformBuffersMapped[currentImage], &ubo, sizeof(ubo));
}
```
# 描述符集(Descriptor Set)
我们还没有具体创建这个对象来关联 UBO 和对应的pipeline的 Layout。
## 描述符池 (Descriptor Pool) 创建
描述符集(Descriptor Set) 无法直接创建。需要类似command buffer一样，从pool中创建。

```cpp
void initVulkan() {
    ...
    createUniformBuffers();
    createDescriptorPool();
    ...
}

...

VkDescriptorPool descriptorPool;
void createDescriptorPool() {
	VkDescriptorPoolSize poolSize{};
	// 描述符类型：统一缓冲区（Uniform Buffer）
	poolSize.type = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
	// 描述符数量：每个帧一个，这里通常和同时渲染的帧数相同
	poolSize.descriptorCount = static_cast<uint32_t>(MAX_FRAMES_IN_FLIGHT);
	
	VkDescriptorPoolCreateInfo poolInfo{};
	poolInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
	poolInfo.poolSizeCount = 1;
	poolInfo.pPoolSizes = &poolSize;	
	// 描述符集最大数量，决定可以从池中分配多少个 descriptor set
	poolInfo.maxSets = static_cast<uint32_t>(MAX_FRAMES_IN_FLIGHT);
	
	if (vkCreateDescriptorPool(device, &poolInfo, nullptr, &descriptorPool) != VK_SUCCESS) {
	    throw std::runtime_error("failed to create descriptor pool!");
	}
}
```
- 一个描述符池，可以管理多个类型的描述符的创建最大数量。（每个类型对应一个 descriptorCount) **set里descriptor的个数限制**
- 一个描述符池，提供了可以创建的描述符的总最大数量（maxSets） **set的个数限制**

## 描述符集(Descriptor Set)和描述符(Descriptor)创建
```cpp
void initVulkan() {
    ...
    createDescriptorPool();
    createDescriptorSets();
    ...
}

...

std::vector<VkDescriptorSet> descriptorSets;
void createDescriptorSets() {
	std::vector<VkDescriptorSetLayout> layouts(MAX_FRAMES_IN_FLIGHT, descriptorSetLayout);
	
	// 分配描述符集的信息
	VkDescriptorSetAllocateInfo allocInfo{};
	allocInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
	// 指定从哪个池分配
	allocInfo.descriptorPool = descriptorPool;
	// 分配数量
	allocInfo.descriptorSetCount = static_cast<uint32_t>(MAX_FRAMES_IN_FLIGHT);
	// // 指向每个 Descriptor Set 的布局
	allocInfo.pSetLayouts = layouts.data();
	
	descriptorSets.resize(MAX_FRAMES_IN_FLIGHT);
	if (vkAllocateDescriptorSets(device, &allocInfo, descriptorSets.data()) != VK_SUCCESS) {
	    throw std::runtime_error("failed to allocate descriptor sets!");
	}
	// 到这里，descriptorSets数组已经都被分配好了

    // 绑定每个 descriptor set 对应的 uniform buffer	
	for (size_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
	    VkDescriptorBufferInfo bufferInfo{};
	    // 指向对应帧的 uniform buffer
	    bufferInfo.buffer = uniformBuffers[i];
	    // buffer 偏移
	    bufferInfo.offset = 0;
	    // buffer 大小
	    bufferInfo.range = sizeof(UniformBufferObject);
	    
	    // 更新描述符集 （其实就是更新上面的 绑定uniform的信息）
	    VkWriteDescriptorSet descriptorWrite{};
		descriptorWrite.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
		// 指定要更新的 descriptor set
		descriptorWrite.dstSet = descriptorSets[i];
		 // 对应 layout 中 binding = 0
		descriptorWrite.dstBinding = 0;
		// 如果是数组描述符，这里是数组起始索引
		descriptorWrite.dstArrayElement = 0;
		// 描述符类型
		descriptorWrite.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
		// 更新一个描述符
		descriptorWrite.descriptorCount = 1;
		// 更新的内容：
		// 指向 buffer info
		descriptorWrite.pBufferInfo = &bufferInfo;
		descriptorWrite.pImageInfo = nullptr; // Optional
		descriptorWrite.pTexelBufferView = nullptr; // Optional

		// 调用 Vulkan API 更新 descriptor set，将 bufferInfo 绑定到 descriptor
		vkUpdateDescriptorSets(device, 1, &descriptorWrite, 0, nullptr);
	}
}

void cleanup() {
    ...
    vkDestroyDescriptorPool(device, descriptorPool, nullptr);

    vkDestroyDescriptorSetLayout(device, descriptorSetLayout, nullptr);
    ...
}
```

## 渲染时使用描述符集
在drawcall前，绑定描述符集
```cpp
vkCmdBindDescriptorSets(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS, pipelineLayout, 0, 1, &descriptorSets[currentFrame], 0, nullptr);
vkCmdDrawIndexed(commandBuffer, static_cast<uint32_t>(indices.size()), 1, 0, 0, 0);
```

一些bug修复。由于我们flip Y，导致三角形面的方向也相反，从而被 `BACK_CULL` 掉了。因此回到 pipeline创建的部分，修改
```cpp
rasterizer.cullMode = VK_CULL_MODE_BACK_BIT;
rasterizer.frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE;
```

到这里，可以看到渲染的画面了

![[Vulkan入门03-UniformBuffers-渲染时使用描述符集-01.png]]


## 对齐问题
考虑下面两个：

内存中v.s. glsl中
```cpp
struct UniformBufferObject {
    glm::vec2 foo;
    glm::mat4 model;
    glm::mat4 view;
    glm::mat4 proj;
};

layout(binding = 0) uniform UniformBufferObject {
    vec2 foo;
    mat4 model;
    mat4 view;
    mat4 proj;
} ubo;
```
其实回顾我们之前的学习，我们知道 shader中对内存布局有额外要求：
- Scalars have to be aligned by N (= 4 bytes given 32 bit floats).
- A `vec2` must be aligned by 2N (= 8 bytes)
- A `vec3` or `vec4` must be aligned by 4N (= 16 bytes)
- A nested structure must be aligned by the base alignment of its members rounded up to a multiple of 16.
- A `mat4` matrix must have the same alignment as a `vec4`.

显然我们上面CPU布局和GPU内存布局不一致。（因为vec2，会占有8字节，而后面我们需要16字节对齐。所以我们必须手动对齐CPU的内存）
```cpp
struct UniformBufferObject {
    glm::vec2 foo;
    alignas(16) glm::mat4 model;
    glm::mat4 view;
    glm::mat4 proj;
};
```

此外，GLM库提供了自动对齐的宏配置
```cpp
#define GLM_FORCE_RADIANS
#define GLM_FORCE_DEFAULT_ALIGNED_GENTYPES
#include <glm/glm.hpp>
```
这样GLM定义的对象，会按照GPU的规范进行自动对齐。但如果你嵌套使用自定义struct，那么对齐也会失效。（GLM仅能负责自己对象内部的对齐）。教程里举了个奇怪的例子，我们这里不举例子，知道有内存对齐问题以及手动对齐为主即可。

## 多个 Descriptor Set
这个其实我们之前也提到过了。
```glsl
layout(set = 0, binding = 0) uniform UniformBufferObject { ... }
```

- 1个pipiline 可以绑定 多个 Descriptor Set （每个set，可以根据UBO使用频率来规划）
- 1个Descriptor Set可以绑定多个Descriptor Set Binding （每个binding可以对应一种单个/数组类型的UBO/其他资源）
- 每个binding实际运行时，绑定1个Descriptor / 1个Descriptor数组 。

