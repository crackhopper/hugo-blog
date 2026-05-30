---
id: art_a49055d65eccdd8ff84a0cf87e487d2c
title: Vulkan入门09-Compute Shader
date: 2025-12-09T22:46:41+08:00
tags:
  - vulkan
  - compute-shader
  - particle-system
draft: false
---
![[Vulkan入门09_Compute_Shader-intro-01.png|342x270]]


整体来说，执行compute pipeline，类似图形管线，但是更加简单：
```
vkCmdBindPipeline (COMPUTE)
vkCmdBindDescriptorSets
vkCmdDispatch
```

注意本章节：仅从概念和一部分细节上介绍粒子，但并不会提供对应可以运行的代码。

我计划构建好基于vulkan的渲染器后，整体基于这个章节的内容再来实现 GPU 粒子系统。


<!--more-->

# Vulkan Pipeline
![[Vulkan入门09_Compute_Shader-vulkan_pipeline-01.png]]

上面的图，左侧是传统的图形管线。右侧是一些特殊的管线（比如基于mesh shader的rendering，以及用GPU来实现计算的Compute Shader）。

## 看图简介Compute Shader

Compute Shader的使用流程：
```
Dispatch
   ↓
Compute Shader
   ↓
（写回资源）
   ↓
后续 Graphics / Compute / Mesh 再继续使用

```

执行触发方式：Dispatch 而不是 Draw

| 图形管线               | Compute                |
| ------------------ | ---------------------- |
| draw / drawIndexed | dispatch(x, y, z)      |
| 以“顶点/图元”为驱动        | 以“线程组”为驱动              |
| 与 framebuffer 强耦合  | **完全无 framebuffer 概念** |

从资源访问来看：Compute Shader  **可以读 + 写** 几乎所有“非 attachment”资源。

# 目标案例
我们将用 Compute Shader来实现一个粒子系统 (Particle System)效果如下

![[Vulkan入门09_Compute_Shader-intro-01.png|342x270]]

# 数据操作(Data manipulation)
## Shader storage buffer objects (SSBO)
SSBO（Shader Storage Buffer Object）相比其他缓冲类型（尤其是 Uniform Buffer Object, UBO），最大的两个不同点是：
1. **SSBO 可以与其他缓冲类型“别名（alias）使用”**
2. **SSBO 的大小几乎不受限制（可以非常大）**

**什么是alias（别名）？** 
- **同一块 GPU 内存（同一个 VkBuffer）可以被当作多种缓冲类型来使用**

例如：
```cpp
VkBufferCreateInfo bufferInfo{};
...
bufferInfo.usage = VK_BUFFER_USAGE_VERTEX_BUFFER_BIT | VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
...

if (vkCreateBuffer(device, &bufferInfo, nullptr, &shaderStorageBuffers[i]) != VK_SUCCESS) {
    throw std::runtime_error("failed to create vertex buffer!");
}
```

- **在 compute shader 中**：  通过 descriptor，把这个 buffer 当作 SSBO 来读 / 写
- **在 graphics pipeline 中**：  把同一个 buffer 绑定为 vertex buffer 来绘制
- 此外 `VK_BUFFER_USAGE_TRANSFER_DST_BIT` 支持我们从host上复制数据到GPU


我们用下面代码创建 storageBuffer
```cpp
createBuffer(
	bufferSize, 
	VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_VERTEX_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT, 
	VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, 
	shaderStorageBuffers[i], shaderStorageBuffersMemory[i]);
```

访问这个buffer的shader代码：
```glsl
struct Particle {
  vec2 position;
  vec2 velocity;
  vec4 color;
};

// std140 是 memory layout 参数，表明 shader storage memory 中元素如何对齐
layout(std140, binding = 1) readonly buffer ParticleSSBOIn {
   Particle particlesIn[ ]; // 代表数量未知
};

layout(std140, binding = 2) buffer ParticleSSBOOut {
   Particle particlesOut[ ];
};
```

向这个 SSBO 写入很容易：
```glsl
particlesOut[index].position = particlesIn[index].position + particlesIn[index].velocity.xy * ubo.deltaTime;
```

## Storage images
这里我们只是解说，Compute Shader也可以对图像操作。本章节我们不使用这个技术。

类似buffer，创建的时候，指定usage
```cpp
VkImageCreateInfo imageInfo {};
...
imageInfo.usage = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_STORAGE_BIT;
...

if (vkCreateImage(device, &imageInfo, nullptr, &textureImage) != VK_SUCCESS) {
    throw std::runtime_error("failed to create image!");
}
```
- `VK_IMAGE_USAGE_SAMPLED_BIT` : 作为纹理采样
- `VK_IMAGE_USAGE_STORAGE_BIT` : 作为compute shader可以读写的buffer

在glsl中，数据绑定：
```glsl
layout (binding = 0, rgba8) uniform readonly image2D inputImage;
layout (binding = 1, rgba8) uniform writeonly image2D outputImage;
```

在代码中，读写image
```glsl
vec3 pixel = imageLoad(inputImage, ivec2(gl_GlobalInvocationID.xy)).rgb;
imageStore(outputImage, ivec2(gl_GlobalInvocationID.xy), pixel);
```

# 计算队列族(Compute queue family)
Vulkan强制要求，每个驱动实现必须有1个队列，同时支持graphics和compute操作。不过，也不反对驱动实现一个专门的Compute队列，用来执行异步计算。

我们这里使用一个同时支持 graphics 和 compute 操作的队列。

创建队列的相关代码修改：
```cpp
struct QueueFamilyIndices {
  std::optional<uint32_t> graphicsAndComputeFamily; // 图形和计算队列族索引
  std::optional<uint32_t> graphicsFamily; // 图形队列族索引
  std::optional<uint32_t> presentFamily;  // 呈现队列族索引

  bool isComplete() {
    return graphicsFamily.has_value() && presentFamily.has_value() && graphicsAndComputeFamily;
  }
};
...
QueueFamilyIndices findQueueFamilies(VkPhysicalDevice physicalDevice) {
	uint32_t queueFamilyCount = 0;
	vkGetPhysicalDeviceQueueFamilyProperties(device, &queueFamilyCount, nullptr);
	
	std::vector<VkQueueFamilyProperties> queueFamilies(queueFamilyCount);
	vkGetPhysicalDeviceQueueFamilyProperties(
		device, &queueFamilyCount, queueFamilies.data());
	
	int i = 0;
	for (const auto& queueFamily : queueFamilies) {
		...
	    if ((queueFamily.queueFlags & VK_QUEUE_GRAPHICS_BIT) && 
		    (queueFamily.queueFlags & VK_QUEUE_COMPUTE_BIT)) {
	        indices.graphicsAndComputeFamily = i;
	    }
		...
	    i++;
	}	
}
...
// 创建逻辑设备的时候，创建并获取这个队列
VkQueue computeQueue;
...
void createLogicalDevice() {
	...
    vkGetDeviceQueue(device, indices.graphicsAndComputeFamily.value(), 0,
                     &computeQueue);
}
```

# 计算着色器阶段 (Compute Shader Stage)
## 加载 Compute Shader
在我们的应用程序中加载计算着色器与加载任何其他着色器相同。唯一真正的区别是我们需要使用上面提到的 `VK_SHADER_STAGE_COMPUTE_BIT` 。

```cpp
auto computeShaderCode = readFile("shaders/compute.spv");

VkShaderModule computeShaderModule = createShaderModule(computeShaderCode);

VkPipelineShaderStageCreateInfo computeShaderStageInfo{};
computeShaderStageInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
computeShaderStageInfo.stage = VK_SHADER_STAGE_COMPUTE_BIT;
computeShaderStageInfo.module = computeShaderModule;
computeShaderStageInfo.pName = "main";
...
```
## 准备 SSBO (Shader Storage Buffer)
我们把粒子数组，写入到SSBO中，方便CS读取和修改。
```cpp
std::vector<VkBuffer> shaderStorageBuffers;
std::vector<VkDeviceMemory> shaderStorageBuffersMemory;
...
void createShaderStorageBuffers(){
	shaderStorageBuffers.resize(MAX_FRAMES_IN_FLIGHT);
	shaderStorageBuffersMemory.resize(MAX_FRAMES_IN_FLIGHT);

    // Initialize particles
    std::default_random_engine rndEngine((unsigned)time(nullptr));
    std::uniform_real_distribution<float> rndDist(0.0f, 1.0f);
    
    // Initial particle positions on a circle
    std::vector<Particle> particles(PARTICLE_COUNT);
    for (auto& particle : particles) {
	    // 用极坐标随机位置
        float r = 0.25f * sqrt(rndDist(rndEngine));
        float theta = rndDist(rndEngine) * 2 * 3.14159265358979323846;
        float x = r * cos(theta) * HEIGHT / WIDTH;
        float y = r * sin(theta);
        particle.position = glm::vec2(x, y);
        // 速度根据位置来计算，向外发射
        particle.velocity = glm::normalize(
	        glm::vec2(x,y)) * 0.00025f;
        particle.color = glm::vec4(
	        rndDist(rndEngine), rndDist(rndEngine), rndDist(rndEngine), 1.0f);
    }
    
    // 创建 staging buffer 来保存初始的粒子属性
    VkDeviceSize bufferSize = sizeof(Particle) * PARTICLE_COUNT;

    VkBuffer stagingBuffer;
    VkDeviceMemory stagingBufferMemory;
    createBuffer(bufferSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, stagingBuffer, stagingBufferMemory);

    void* data;
    vkMapMemory(device, stagingBufferMemory, 0, bufferSize, 0, &data);
    memcpy(data, particles.data(), (size_t)bufferSize);
    vkUnmapMemory(device, stagingBufferMemory);    
    
    // 创建SSBO，并把数据上传到SSBO
    for (size_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
        createBuffer(
	        bufferSize, 
	        VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_VERTEX_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT, 
	        VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, 
	        shaderStorageBuffers[i], shaderStorageBuffersMemory[i]);
        // Copy data from the staging buffer (host) to the shader storage buffer (GPU)
        copyBuffer(stagingBuffer, shaderStorageBuffers[i], bufferSize);
    }    
}
```
## Descriptor
和图形管线一样，我们需要给buffer绑定Descriptor，并且在管线中定义Descriptor Layout，并在运行时，指定Descriptor。从而让Compute Shader可以访问数据。

```cpp
std::array<VkDescriptorSetLayoutBinding, 3> layoutBindings{};
layoutBindings[0].binding = 0;
layoutBindings[0].descriptorCount = 1;
layoutBindings[0].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
layoutBindings[0].pImmutableSamplers = nullptr;
layoutBindings[0].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
...
```

注意，如果希望descriptor从 vertex 和 compute stage都能访问 （比如 UBO），上面可以设置both stage
```cpp
layoutBindings[0].stageFlags = VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_COMPUTE_BIT;
```

我们整体的布局设定为：
```cpp
std::array<VkDescriptorSetLayoutBinding, 3> layoutBindings{};
layoutBindings[0].binding = 0;
layoutBindings[0].descriptorCount = 1;
layoutBindings[0].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
layoutBindings[0].pImmutableSamplers = nullptr;
layoutBindings[0].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;

layoutBindings[1].binding = 1;
layoutBindings[1].descriptorCount = 1;
layoutBindings[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
layoutBindings[1].pImmutableSamplers = nullptr;
layoutBindings[1].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;

layoutBindings[2].binding = 2;
layoutBindings[2].descriptorCount = 1;
layoutBindings[2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
layoutBindings[2].pImmutableSamplers = nullptr;
layoutBindings[2].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;

VkDescriptorSetLayoutCreateInfo layoutInfo{};
layoutInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
layoutInfo.bindingCount = 3;
layoutInfo.pBindings = layoutBindings.data();

if (vkCreateDescriptorSetLayout(device, &layoutInfo, nullptr, &computeDescriptorSetLayout) != VK_SUCCESS) {
    throw std::runtime_error("failed to create compute descriptor set layout!");
}
```

这里面，我们用了两个layout来绑定两个SSBO，为什么呢？
- 粒子系统逐帧更新，基于一个增量时间。
- 每帧需要知道上一帧粒子的位置。以便更新它们。
具体流程如下图：

![[Vulkan入门09_Compute_Shader-descriptor-01.png]]

而UBO显然是用来计算delta time，以及管理哪个buffer是source，哪个buffer是dst的。

具体绑定descriptor的代码： （`createDescriptorSet` 在初始化最后的阶段）
```cpp
for (size_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
    VkDescriptorBufferInfo uniformBufferInfo{};
    uniformBufferInfo.buffer = uniformBuffers[i];
    uniformBufferInfo.offset = 0;
    uniformBufferInfo.range = sizeof(UniformBufferObject);

    std::array<VkWriteDescriptorSet, 3> descriptorWrites{};
    ...

    VkDescriptorBufferInfo storageBufferInfoLastFrame{};
    storageBufferInfoLastFrame.buffer = shaderStorageBuffers[(i - 1) % MAX_FRAMES_IN_FLIGHT];
    storageBufferInfoLastFrame.offset = 0;
    storageBufferInfoLastFrame.range = sizeof(Particle) * PARTICLE_COUNT;

    descriptorWrites[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    descriptorWrites[1].dstSet = computeDescriptorSets[i];
    descriptorWrites[1].dstBinding = 1;
    descriptorWrites[1].dstArrayElement = 0;
    descriptorWrites[1].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    descriptorWrites[1].descriptorCount = 1;
    descriptorWrites[1].pBufferInfo = &storageBufferInfoLastFrame;

    VkDescriptorBufferInfo storageBufferInfoCurrentFrame{};
    storageBufferInfoCurrentFrame.buffer = shaderStorageBuffers[i];
    storageBufferInfoCurrentFrame.offset = 0;
    storageBufferInfoCurrentFrame.range = sizeof(Particle) * PARTICLE_COUNT;

    descriptorWrites[2].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    descriptorWrites[2].dstSet = computeDescriptorSets[i];
    descriptorWrites[2].dstBinding = 2;
    descriptorWrites[2].dstArrayElement = 0;
    descriptorWrites[2].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    descriptorWrites[2].descriptorCount = 1;
    descriptorWrites[2].pBufferInfo = &storageBufferInfoCurrentFrame;

    vkUpdateDescriptorSets(device, 3, descriptorWrites.data(), 0, nullptr);
}
```

当然为了支持创建上面的set，我们还需要在对应的池里，扩大容量：（`createDescriptorPool` 在 `createDescriptorSet` 的前一步）
```cpp
std::array<VkDescriptorPoolSize, 2> poolSizes{};
...

poolSizes[1].type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
poolSizes[1].descriptorCount = static_cast<uint32_t>(MAX_FRAMES_IN_FLIGHT) * 2;
```
## 计算管线(Compute pipelines)
由于计算不是图形管线的一部分，我们不能使用 `vkCreateGraphicsPipelines` 。相反，我们需要使用 `vkCreateComputePipelines` 创建一个专门的计算管线来运行我们的计算命令。由于计算管线不涉及任何光栅化状态，因此它的状态比图形管线少得多：

```cpp
VkPipelineLayoutCreateInfo pipelineLayoutInfo{};
pipelineLayoutInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
pipelineLayoutInfo.setLayoutCount = 1;
pipelineLayoutInfo.pSetLayouts = &computeDescriptorSetLayout;

if (vkCreatePipelineLayout(
	device, &pipelineLayoutInfo, nullptr, &computePipelineLayout) != VK_SUCCESS) {
    throw std::runtime_error("failed to create compute pipeline layout!");
}

VkComputePipelineCreateInfo pipelineInfo{};
pipelineInfo.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
pipelineInfo.layout = computePipelineLayout;
pipelineInfo.stage = computeShaderStageInfo;

if (vkCreateComputePipelines(
	device, VK_NULL_HANDLE, 1, &pipelineInfo, nullptr, 
	&computePipeline) != VK_SUCCESS) {
    throw std::runtime_error("failed to create compute pipeline!");
}
```
## Compute space
在深入了解计算着色器的工作原理以及如何向 GPU 提交计算任务之前，我们需要讨论两个重要的计算概念：工作组（ **work groups** ）和调用（ **invocations** ）。它们定义了一个抽象的执行模型，用于描述计算任务如何在 GPU 的三维计算硬件（x、y 和 z 轴）中处理。
- **Work groups** : 工作组定义了 计算工作负载 如何由 GPU 的计算硬件 组织(form) 和 处理(process)。你可以将它们视为 GPU 需要处理的任务项。work group dimension 由应用，在 command buffer录制时，使用 dispatch 指令来设置。
- **invocations** ： 每个工作组是a collections of invocations （调用集合），每个调用执行相同的 compute shader。invocation 可以并行执行，它们的dimension在compute shader中被设置。每个工作组内的调用，访问共同的内存。

说明示例图：

![[Vulkan入门09_Compute_Shader-compute_space-01.png]]

work groups 和 invocations 的维度数 (number of dimensions) 取决于输入数据的结构 （由compute shader的 local size 定义）。

在我们的例子里，处理一个一维数组，那么你需要给这两个都指定x的维度。

举例来说：如果我们dispatch work group数量为 `[64,1,1]` ，computer shader的 local size 为 `[32,32,1]` (local size也即每个workgroup内invocation的数量) ，那么我们的compute shader整体被调用 `64x32x32=65536` 次。

注意：最大work group数量，以及 local sizes的限制，根据驱动不同而不同。最好通过  `VkPhysicalDeviceLimits` 计算相关 `maxComputeWorkGroupCount` 、 `maxComputeWorkGroupInvocations` 和 `maxComputeWorkGroupSize` 限制。

## Compute shader
```glsl
#version 450

layout (binding = 0) uniform ParameterUBO {
    float deltaTime;
} ubo;

struct Particle {
    vec2 position;
    vec2 velocity;
    vec4 color;
};

layout(std140, binding = 1) readonly buffer ParticleSSBOIn {
   Particle particlesIn[ ];
};

layout(std140, binding = 2) buffer ParticleSSBOOut {
   Particle particlesOut[ ];
};

layout (local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

void main() 
{
    uint index = gl_GlobalInvocationID.x;  

    Particle particleIn = particlesIn[index];

    particlesOut[index].position = particleIn.position + particleIn.velocity.xy * ubo.deltaTime;
    particlesOut[index].velocity = particleIn.velocity;
    ...
}
```

一些解释和说明：
1. **为什么 `particlesIn[]` 可以不写大小**
	1. 它是 **运行期大小（runtime-sized array）**
	2. array 的长度 **在 shader 编译时未知**
	3. 真正长度由 CPU 端 `vkCmdBindDescriptorSets / glBindBufferRange` 决定
	4. 被所有 invocations 共享。
2. **gl_GlobalInvocationID是什么？**
	1. WorkGroupID × LocalSize + LocalInvocationID。它是通过 **workgroup 的 ID** 和 **workgroup 内的 invocation ID** 组合出来的一个 **全局唯一 invocation 索引**。
	2. 在 compute shader 中同时存在 **三套 ID**：
		1. uvec3 gl_WorkGroupID： 这是第几个 workgroup
		2. uvec3 gl_LocalInvocationID： 当前 invocation 在 workgroup 内的编号
		3. `gl_GlobalInvocationID`： 组合上面两个和 `local_size` 得到的全局id
3. shared变量，才是每个workgroup中独立的，workgroup内共享的
4. 这里的 Particle 的每个字段按照 std140对齐：
	1. 基础标量 `float`, `int`, `uint`： 4 bytes
	2. 向量 `vec2` : 8 bytes
	3. 向量 `vec3, vec4` : 16bytes
	4. 我们在copy数据进去的时候，一定要注意对齐。使用C++11的 `alignas(16)` 进行妥善对齐。


注意索引计算逻辑：
```
gl_GlobalInvocationID.x = gl_WorkGroupID.x * local_size_x + gl_LocalInvocationID.x;
gl_GlobalInvocationID.y = gl_WorkGroupID.y * local_size_y + gl_LocalInvocationID.y;
gl_GlobalInvocationID.z = gl_WorkGroupID.z * local_size_z + gl_LocalInvocationID.z;
```

假设数据维度为 64 x 64 x 64 。那么在 work group 可以展开 16 x 16 x 16，这样每个 local size 可以继续展开 4 x 4 x 4 。效果类似于 每个workgroup 负责数据上一个 4x4x4的小块，一共有 16x16x16个小块。而workgroup具体执行，则会展开成 4x4x4个 invocations，分别调用 compute shader。

# 执行计算指令
下面的指令都是需要每帧调用的
## 分发(Dispatch)
```cpp
VkCommandBufferBeginInfo beginInfo{};
beginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;

if (vkBeginCommandBuffer(commandBuffer, &beginInfo) != VK_SUCCESS) {
    throw std::runtime_error("failed to begin recording command buffer!");
}

...

vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, computePipeline);
vkCmdBindDescriptorSets(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, computePipelineLayout, 0, 1, &computeDescriptorSets[i], 0, 0);

vkCmdDispatch(computeCommandBuffer, PARTICLE_COUNT / 256, 1, 1);

...

if (vkEndCommandBuffer(commandBuffer) != VK_SUCCESS) {
    throw std::runtime_error("failed to record command buffer!");
}
```
这里我们注意到：  `PARTICLE_COUNT / 256` ，因为我们每个local size是256。

所以常见做法是：
- local size 是固定的（设备本身也有一定限制）
- work group size 则是根据数据和local size动态计算出来的。
## 提交work(Submitting work)
很简单，一目了然
```cpp
...
if (vkQueueSubmit(computeQueue, 1, &submitInfo, nullptr) != VK_SUCCESS) {
    throw std::runtime_error("failed to submit compute command buffer!");
};
...
if (vkQueueSubmit(graphicsQueue, 1, &submitInfo, inFlightFences[currentFrame]) != VK_SUCCESS) {
    throw std::runtime_error("failed to submit draw command buffer!");
}
```
## 同步图形和计算(Synchronizing graphics and compute)
不难，只要有大致逻辑，就知道如何用 semaphore 和 fence 进行同步

```cpp
std::vector<VkFence> computeInFlightFences;
std::vector<VkSemaphore> computeFinishedSemaphores;
...
computeInFlightFences.resize(MAX_FRAMES_IN_FLIGHT);
computeFinishedSemaphores.resize(MAX_FRAMES_IN_FLIGHT);

VkSemaphoreCreateInfo semaphoreInfo{};
semaphoreInfo.sType = VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO;

VkFenceCreateInfo fenceInfo{};
fenceInfo.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
fenceInfo.flags = VK_FENCE_CREATE_SIGNALED_BIT;

for (size_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
    ...
    if (vkCreateSemaphore(
		    device, &semaphoreInfo, nullptr, 
		    &computeFinishedSemaphores[i]) != VK_SUCCESS ||
		vkCreateFence(
			device, &fenceInfo, nullptr, &computeInFlightFences[i]) != VK_SUCCESS
	) {
        throw std::runtime_error("failed to create compute synchronization objects for a frame!");
    }
    
	// Compute submission
	vkWaitForFences(
		device, 1, &computeInFlightFences[currentFrame], VK_TRUE, UINT64_MAX);
	
	updateUniformBuffer(currentFrame);
	
	vkResetFences(device, 1, &computeInFlightFences[currentFrame]);
	
	vkResetCommandBuffer(
		computeCommandBuffers[currentFrame], /*VkCommandBufferResetFlagBits*/ 0);
	recordComputeCommandBuffer(computeCommandBuffers[currentFrame]);
	
	submitInfo.commandBufferCount = 1;
	submitInfo.pCommandBuffers = &computeCommandBuffers[currentFrame];
	submitInfo.signalSemaphoreCount = 1;
	submitInfo.pSignalSemaphores = &computeFinishedSemaphores[currentFrame];
	
	if (vkQueueSubmit(
			computeQueue, 1, &submitInfo, computeInFlightFences[currentFrame]
		) != VK_SUCCESS) {
	    throw std::runtime_error("failed to submit compute command buffer!");
	};
	
	// Graphics submission
	vkWaitForFences(device, 1, &inFlightFences[currentFrame], VK_TRUE, UINT64_MAX);
	
	vkResetCommandBuffer(
		commandBuffers[currentFrame], /*VkCommandBufferResetFlagBits*/ 0);
	recordCommandBuffer(commandBuffers[currentFrame], imageIndex);
	
	VkSemaphore waitSemaphores[] = { computeFinishedSemaphores[currentFrame], imageAvailableSemaphores[currentFrame] };	
		...    
}
```
# 绘制粒子系统

```cpp
struct Particle {
    ...

    static std::array<VkVertexInputAttributeDescription, 2> getAttributeDescriptions() {
        std::array<VkVertexInputAttributeDescription, 2> attributeDescriptions{};

        attributeDescriptions[0].binding = 0;
        attributeDescriptions[0].location = 0;
        attributeDescriptions[0].format = VK_FORMAT_R32G32_SFLOAT;
        attributeDescriptions[0].offset = offsetof(Particle, position);

        attributeDescriptions[1].binding = 0;
        attributeDescriptions[1].location = 1;
        attributeDescriptions[1].format = VK_FORMAT_R32G32B32A32_SFLOAT;
        attributeDescriptions[1].offset = offsetof(Particle, color);

        return attributeDescriptions;
    }
};
...
vkCmdBindVertexBuffers(commandBuffer, 0, 1, &shaderStorageBuffer[currentFrame], offsets);

vkCmdDraw(commandBuffer, PARTICLE_COUNT, 1, 0, 0);
```

这里忽略了图元的定义。最简单的方法（教程里的效果）：
```cpp
VkPipelineInputAssemblyStateCreateInfo inputAssembly{};
inputAssembly.sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO;
inputAssembly.topology = VK_PRIMITIVE_TOPOLOGY_POINT_LIST; // <-- 这里决定了图元类型
inputAssembly.primitiveRestartEnable = VK_FALSE;
```

指定大小的方式

方法A:
```cpp
vkCmdSetLineWidth(commandBuffer, pointSize); // 注意 Vulkan 也有 line width 但点可以用动态状态
```

方法B（shader）：
```glsl
#version 450
layout(location = 0) in vec2 inPosition;
layout(location = 1) in vec4 inColor;

layout(location = 0) out vec4 fragColor;

void main() {
    gl_Position = vec4(inPosition, 0.0, 1.0);
    gl_PointSize = 10.0; // 每个点的大小（像素为单位）
    fragColor = inColor;
}

```


# 我们未来绘制的思路

## 方法 A - 基于 instance draw
**一个 SSBO 存储逻辑粒子 (position/velocity)，一个 vertex-/index buffer 存储三角形几何 (模板)，然后实例化 (instancing)**

1. 用 compute shader 更新粒子状态 (position, maybe other per-particle data) 存在 SSBO。
    
2. 在 graphics pass，使用一个固定的三角形 (triangle mesh)，这个 triangle 作为 **实例 (instance)**，然后通过 instancing + shader，把 instance 的 transform/位置设为 particle 的 position (从 SSBO 读取)。
    
    - vertex shader 读取 SSBO (or SSBO → uniform/instance-buffer → vertex shader) 里的 position，把三角形移动到对应位置。
        
    - draw call 用 instanced draw (vkCmdDrawIndexed or vkCmdDraw) + instanceCount = number of particles。
        

优点：简单、每粒子三角形共享几何数据 (triangle 顶点)，数据量小且高效。

缺点：如果你希望每个 particle 的三角形几何不一样 (顶点数、顶点位移、随机形状等等)，就不太适用。


## 方法 B — GPU-generated vertex data
**compute shader 写出每个粒子的三角形顶点 (vertex) 到一个 buffer (SSBO or VBO with both storage + vertex usage)，然后用 graphics pass 渲染这些顶点**

也就是说：让 compute shader _输出_ 顶点 (vertex) 数据，而不是仅输出粒子 position。对于每个粒子，写出 3 (或更多) 顶点 (构成三角形, quad, billboard, mesh …) 到一个大的 vertex buffer。

- 在 Vulkan 中，这个 buffer 要在创建时同时具有 `VK_BUFFER_USAGE_STORAGE_BUFFER_BIT` (给 compute shader 写) 和 `VK_BUFFER_USAGE_VERTEX_BUFFER_BIT` (给 vertex shader 读) 标志。教程里已经提到这种 buffer 可行。 [tutorial.vulkan.net.cn](https://tutorial.vulkan.net.cn/Compute_Shader)
    
- 然后在 graphics pass 的 vertex input stage，将这个 buffer 绑定为 vertex buffer (`vkCmdBindVertexBuffers`)。
    
- vertex shader 只需做最基本的 transform (按 position 输出 `gl_Position`)，primitive topology 设置为三角形 (triangle) — draw 时用 vkCmdDraw with vertexCount = num_particles * 3 (或总顶点数)，不使用 instancing (或 instancing + per-vertex data as needed)。