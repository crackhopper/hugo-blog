---
id: art_7038b16438cb0f7b513ba979876a349d
title: Vulkan入门04-Texture mapping
date: 2025-12-04T09:51:00+08:00
tags:
  - vulkan
  - texture
  - sampler
  - descriptor
draft: false
---
![[Vulkan入门04_Texture_mapping-intro-01.png]]


纹理映射，熟悉OGL和DX的，对这个功能并不陌生。在传统的API中，相对来说使用方式比较简单也比较固定。在vulkan中：
1. 创建Image对象（类似创建Buffer，需要绑定 VkDeviceMemory）
2. 读取图片并上传（使用图片库读取，使用 vkMapMemory/vkUnmapMemory，转化 layout :借助pipeline barrier同步），创建 TextureImage 和 TextureImageView
3. 创建 TextureSampler (指定过滤、address mode等) 
4. 创建 Descriptor (类似UBO的步骤，但类型为 COMBINED_IMAGE_SAMPLER)

其他额外步骤：增加纹理坐标，修改InputVertex配置；修改Vertex数据；修改 Vertex Shader （读取并传递纹理坐标）；修改 FragmentShader (读取 Descriptor绑定的 sampler，进行纹理采样)
<!--more-->

# 图像
## 总体流程概述
1. **创建一个 image 对象（VkImage）**
    - 手动创建，不是 SwapChain 自动生成
	- 分配 `DEVICE_LOCAL` 内存并绑定
	- 指定格式、宽高、tiling（通常 `OPTIMAL`）这次不是 SwapChain 自动创建
2. **从图片文件读取像素并上传**
    - 例如 PNG / JPG
    - 写入 HOST_VISIBLE staging buffer
    - 使用 vkCmdCopyBufferToImage 拷贝到最终 image
    - 通过 pipeline barrier 将 image layout 切换到 VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL
3. **创建 image sampler（VkSampler）**
    - 控制如何采样（过滤、寻址方式、mipmap等）
4. **创建 Combined Image Sampler 描述符**
    - 描述符作用：将 image 和 sampler 绑定到 shader
    - 着色器中就可以 `sampler2D` 读取纹理颜色

**为什么要用Staging Buffer？**
- CPU → staging buffer（HOST_VISIBLE）
- staging buffer → GPU image（DEVICE_LOCAL）
原因：GPU 专用内存（DEVICE_LOCAL）**CPU 无法直接写** 。staging buffer 是 CPU 可见的，用来做中转。（所以想要将数据复制到更高性能的位置，不得不用这个中转）

这里我有个核心疑问，**如果某个纹理是每帧都更新的，那是不是不需要用 staging buffer 转到 DEVICE_LOCAL ？** 。AI帮我做了如下回答：
- 情况一：CPU 每帧更新（最常见）
	- 思路：“既然每帧都要改，那就别再拷来拷去了”。
	- 做法：创建 `VkImage`；内存类型：`HOST_VISIBLE | HOST_COHERENT`；tiling：`VK_IMAGE_TILING_LINEAR`；直接 `vkMapMemory()` → 写像素；- layout：`SHADER_READ_ONLY_OPTIMAL` 或 GENERAL
	- 特点：不用 staging buffer，没有copy命令。
	- 代价：GPU访问慢；可能不能sampler；无mipmap
	- 适合：小且频繁更新的纹理。
- 情况二：CPU 每帧更新，但纹理很大 （比如高清视频、大型动态噪声）
	- 思路：拷贝有 DMA / 专用路径；GPU 采样效率差距巨大；多帧拷贝摊销成本
	- 做法：还是用 staging buffer → DEVICE_LOCAL image
- 情况三：GPU 每帧更新（最优路径）
	- 思路 ：直接在DEVICE_LOCAL的图像上操作
	- 做法：image：`DEVICE_LOCAL`；layout：`GENERAL` / `STORAGE`；compute shader 写；fragment shader 读
	- 特点：不需要staging buffer；不需要CPU干预；性能最好

当然，出了staging buffer，还有一个叫staging image的概念。简单来说，在 Vulkan 中你只有两种 image 可选：

|image 类型|CPU|GPU|
|---|---|---|
|LINEAR tiling|✅ 可写|❌ 访问慢 / 受限|
|OPTIMAL tiling|❌ 不可写|✅ 采样最快|

**不存在一种“CPU 可写 + GPU 高效采样”的 image** 。而支持CPU可写的这种image，也叫staging image（这是一种口语化的描述，指的是`HOST_VISIBLE + LINEAR tiling` 的image）， 主要用来做CPU侧的一些操作和调试工作。

而使用staging buffer足够，很多GPU硬件层会优化从 staging buffer 到 GPU image的复制动作。

对图像来说，有一些额外需要注意的点。就是 `layouts` ，描述像素在memory中的组织方式。不同的操作对于不同的layout来说，性能是不一样的：

|Layout|用途|
|---|---|
|`VK_IMAGE_LAYOUT_PRESENT_SRC_KHR`|用来显示到屏幕（交换链）|
|`VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL`|作为颜色附件，被 fragment shader 写|
|`VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL`|作为拷贝源|
|`VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL`|作为拷贝目标|
|`VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`|**供 shader 采样纹理用（非常关键）**|

一个典型的纹理流程：
```
UNDEFINED
→ TRANSFER_DST_OPTIMAL
→ SHADER_READ_ONLY_OPTIMAL
```

**Layout 是必须“手动切换”的**
- 最常用的，来转化image layout的方式是 `pipeline barrier` 。pipeline barrier 通常主要用来同步对资源的访问操作（比如读之前确保已经写入完成），但它也可以用来做 layout 转化操作。（此外，barrier也可以用来转移 queue family 的 拥有权：比如从 graphics 队列转移到 transfer队列）

## 加载图像 (使用 stb 库)
这里，我们需要加载简单的 BMP或者PPM格式。选择使用 `stb` 库 (https://github.com/nothings/stb) 。好处是，这个库是一个单文件header库。我们仅需要在构建过程中，添加一个 include directory 就可以了。

我们的目录结构：

![[Vulkan入门04_Texture_mapping-加载图像_使用_stb_库-01.png|205x325]]

我们的cmakelist配置
```cmake
set(SOURCES
    src/main.cpp
    src/utils.cpp
)
add_executable(${PROJECT_NAME} ${SOURCES})
target_link_libraries(${PROJECT_NAME} PRIVATE Vulkan::Vulkan glfw)
target_include_directories(${PROJECT_NAME} PRIVATE include)
```

我们在代码里的使用方式
```cpp
#define STB_IMAGE_IMPLEMENTATION
#include <stb/stb_image.h>
```

开始之前，在创建 textures 文件夹，并放入一个 CC0 的image （512 x 512 ） `texture.jpg` 如下：
![[Vulkan入门04_Texture_mapping-intro-01.png|142x142]]

接下来我们来创建TextureImage:
```cpp
void initVulkan() {
    ...
    createCommandPool();
    createTextureImage();
    createVertexBuffer();
    ...
}

...

VkBuffer stagingBuffer;
VkDeviceMemory stagingBufferMemory;
void createTextureImage() {
    int texWidth, texHeight, texChannels;
    // 加载图像像素为一个指针
    stbi_uc* pixels = stbi_load("textures/texture.jpg", &texWidth, &texHeight, &texChannels, STBI_rgb_alpha);
    VkDeviceSize imageSize = texWidth * texHeight * 4;

    if (!pixels) {
        throw std::runtime_error("failed to load texture image!");
    }
    
    // 创建vkBuffer
    createBuffer(imageSize, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT, stagingBuffer, stagingBufferMemory);
    // 复制pixel到我们的buffer
	void* data;
	vkMapMemory(device, stagingBufferMemory, 0, imageSize, 0, &data);
	    memcpy(data, pixels, static_cast<size_t>(imageSize));
	vkUnmapMemory(device, stagingBufferMemory);    
	
	// 释放掉我们用stb加载的image
	stbi_image_free(pixels);
	
}
```

## 创建 Texture Image
```cpp
// 声明纹理图像对象
VkImage textureImage;
// 声明纹理图像对应的显存对象
VkDeviceMemory textureImageMemory;

// 创建图像的通用函数，方便后续多次复用 (类似我们之前用过的createBuffer函数)
void createImage(
	uint32_t width, 
	uint32_t height, 
	VkFormat format,  // 像素格式，如 R8G8B8A8_SRGB
	VkImageTiling tiling,  // 内存布局 （决定硬件访问效率）
	VkImageUsageFlags usage,  // 用途
	VkMemoryPropertyFlags properties, // 内存属性 （如，HOST_VISIBLE之类的）
	VkImage& image,  // 输出: 创建好的图像对象
	VkDeviceMemory& imageMemory // 输出: 绑定的显存对象
) {
    VkImageCreateInfo imageInfo{};
    imageInfo.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO;
    // 图像类型：二维纹理
    imageInfo.imageType = VK_IMAGE_TYPE_2D;
    imageInfo.extent.width = width;
    imageInfo.extent.height = height;
    // 图像深度，二维图像为1
    imageInfo.extent.depth = 1;
    // mipmap层数，暂时只用1层
    imageInfo.mipLevels = 1;
    // 图像数组层数，单张图片为1
    imageInfo.arrayLayers = 1;
    
    imageInfo.format = format;
    imageInfo.tiling = tiling;
    // GPU无法直接使用初始数据，第一次写入会覆盖现有内容。
    imageInfo.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    imageInfo.usage = usage;
    // 如果是多重采样渲染的目标图像，这个值会大于1。
    imageInfo.samples = VK_SAMPLE_COUNT_1_BIT;
    // 独占队列访问（仅图形队列）
    imageInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    if (vkCreateImage(device, &imageInfo, nullptr, &image) != VK_SUCCESS) {
        throw std::runtime_error("failed to create image!");
    }

	// 查询图像内存需求
    VkMemoryRequirements memRequirements;
    vkGetImageMemoryRequirements(device, image, &memRequirements);

	// 配置内存分配信息
    VkMemoryAllocateInfo allocInfo{};
    allocInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    allocInfo.allocationSize = memRequirements.size;
    allocInfo.memoryTypeIndex = findMemoryType(memRequirements.memoryTypeBits, properties);

    if (vkAllocateMemory(device, &allocInfo, nullptr, &imageMemory) != VK_SUCCESS) {
        throw std::runtime_error("failed to allocate image memory!");
    }
	// 将分配好的显存绑定到图像对象上
    vkBindImageMemory(device, image, imageMemory, 0);
}

void createTextureImage() {
	...
	// 创建Image。类似createBuffer便利函数
	createImage(texWidth, texHeight, VK_FORMAT_R8G8B8A8_SRGB, VK_IMAGE_TILING_OPTIMAL, VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, textureImage, textureImageMemory);
}
```

其中一些细节的解释：
**1. mipLevels（mipmap层数）**
- Vulkan不会自动生成 mipmaps，`mipLevels` 只是告诉 GPU 这个图像预期有多少层 mipmap。
- 如果你想使用 mipmaps，有两种方法：
    1. 预先在 CPU 上生成，然后上传到每层；
    2. 上传原始纹理后，让 GPU 在渲染或 compute pass 中生成（需要额外命令，比如 `vkCmdBlitImage`）。
- 存储上，每个 mipmap 层在内存中占用连续空间，但 Vulkan 可以自动计算偏移。

**2. arrayLayers（图像数组层数）**
- 图像数组允许你把多张图像“叠加”成一个对象。每一层就是一张图像。
- 用途：
    - **2D纹理数组**：shader里用`tex2DArray()`访问不同层的纹理
    - **立方体贴图**：本质上是 6 层 2D 图像（每个面一层）
- 对普通单张纹理，`arrayLayers = 1` 就够了。

**3. VK_SHARING_MODE_EXCLUSIVE（独占队列访问）**
- 解释你提到的两种理解：
    1. **正确理解**：图像对象一次只能被一个队列家族访问。队列家族外的访问需要显式转移。
    2. **错误理解**：独占模式不会限制队列当前仅能使用这张图像，其他资源不能用。
- 换句话说：
    - **EXCLUSIVE** → 同一时间仅一个队列家族对图像有直接访问权（效率高）
    - **CONCURRENT** → 多个队列家族可以同时访问（需声明共享队列），但效率略低

**这里面 `extent.depth` 和 `arrayLayers` 容易混淆，详细展开解释一下：**

1. **depth**
    - 描述单张图像在 Z 轴方向上的厚度。
    - 对应 `VkImageType = VK_IMAGE_TYPE_3D` 时才大于 1，否则 2D 图像 depth 始终为 1。
    - 决定 shader 中 `sampler3D` 访问的 z 方向 texel 数量。
    - 通常和图像本身的数据文件格式有关（比如 3D 体素纹理、体积数据）。
2. **arrayLayers**
    - 描述图像数组层数，即 GPU 上堆叠的多张二维图像数量。
    - 对应 2D 图像数组或者立方体贴图（cubemap）。
    - shader 可以用 `sampler2DArray` 或 `samplerCube` 访问不同的层。
    - 通常和数据文件个数有关，比如 4 张纹理打包成一张 image array。
3. **depth 和 arrayLayers 是独立维度**
    - depth 决定单张图像沿 Z 轴的厚度；
    - arrayLayers 决定图像数组的数量；
    - 它们可以组合使用，比如 3D 图像数组（少见）：
        - depth > 1 → 单张 3D 图像
        - arrayLayers > 1 → 多个 3D 图像堆叠

**记忆技巧**：
- **depth** → 单张图像的“厚度”
- **arrayLayers** → 多张图像的“堆叠”

## 布局转换（Layout transitions）
重构部分代码：
```cpp
VkCommandBuffer beginSingleTimeCommands() {
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

    return commandBuffer;
}

void endSingleTimeCommands(VkCommandBuffer commandBuffer) {
    vkEndCommandBuffer(commandBuffer);

    VkSubmitInfo submitInfo{};
    submitInfo.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submitInfo.commandBufferCount = 1;
    submitInfo.pCommandBuffers = &commandBuffer;

    vkQueueSubmit(graphicsQueue, 1, &submitInfo, VK_NULL_HANDLE);
    vkQueueWaitIdle(graphicsQueue);

    vkFreeCommandBuffers(device, commandPool, 1, &commandBuffer);
}

// 对于这种一次性执行的command（不是启动pipeline执行渲染），我们都可以重构一下
void copyBuffer(VkBuffer srcBuffer, VkBuffer dstBuffer, VkDeviceSize size) {
    VkCommandBuffer commandBuffer = beginSingleTimeCommands();

    VkBufferCopy copyRegion{};
    copyRegion.size = size;
    vkCmdCopyBuffer(commandBuffer, srcBuffer, dstBuffer, 1, &copyRegion);

    endSingleTimeCommands(commandBuffer);
}
```

对于我们要进行布局转化，我们就可以写为：
```cpp
void transitionImageLayout(VkImage image, VkFormat format, VkImageLayout oldLayout, VkImageLayout newLayout) {
    VkCommandBuffer commandBuffer = beginSingleTimeCommands();
    
    // 定义一个图像内存屏障结构，用于描述访问依赖和布局转换
	VkImageMemoryBarrier barrier{};
	barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;

	// 指定旧布局和新布局
	barrier.oldLayout = oldLayout;
	barrier.newLayout = newLayout;
	
    // 如果图像需要在不同队列族之间转移所有权，用下面字段指定
    // 这里不需要队列转移，所以使用 VK_QUEUE_FAMILY_IGNORED
	barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
	barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;	

    // 指定操作的图像	
	barrier.image = image;
    // subresourceRange 指定影响的图像子资源（mipmap层和数组层）
	barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;// 操作颜色数据
	barrier.subresourceRange.baseMipLevel = 0;// 从第0层mipmap开始
	barrier.subresourceRange.levelCount = 1;// 只影响1层mipmap
	barrier.subresourceRange.baseArrayLayer = 0;// 从第0层数组开始
	barrier.subresourceRange.layerCount = 1; // 只影响1层数组
	
	// 定义源和目标的 pipeline 阶段，用于同步
	VkPipelineStageFlags sourceStage;
	VkPipelineStageFlags destinationStage;
	
	// 判断是哪种布局转换
	if (oldLayout == VK_IMAGE_LAYOUT_UNDEFINED && newLayout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL) {
        // UNDEFINED -> TRANSFER_DST_OPTIMAL
        // 未定义布局，不需要等待任何操作	
	    barrier.srcAccessMask = 0;
	    // 下一步操作是写入图像
	    barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
	
		// 源阶段为 pipeline 开头 （stage不能为0，必须是有效阶段；所以才这么设置）
	    sourceStage = VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT;
	    // 目标阶段为 transfer 阶段
	    destinationStage = VK_PIPELINE_STAGE_TRANSFER_BIT;
	    
	} else if (oldLayout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL && newLayout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL) {
        // TRANSFER_DST_OPTIMAL -> SHADER_READ_ONLY_OPTIMAL
        // 确保 transfer 写入完成后，shader 才能读取	
	    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
	    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
	
		// 源阶段：写入阶段完成
	    sourceStage = VK_PIPELINE_STAGE_TRANSFER_BIT;
	    // 目标阶段：在片段着色器读取之前
	    destinationStage = VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
	} else {
		// 其他布局转换不支持
	    throw std::invalid_argument("unsupported layout transition!");
	}
	
	// 当然，layout transition操作，需要都记录到一个 commandBuffer，barrier才会生效。
	vkCmdPipelineBarrier(
	    commandBuffer,
	    sourceStage, destinationStage,
	    0,
	    0, nullptr,
	    0, nullptr,
	    1, &barrier
	);
	
	 endSingleTimeCommands(commandBuffer);
}

void createTextureImage(){
	...
    transitionImageLayout(textureImage, VK_FORMAT_R8G8B8A8_SRGB, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);

}

void cleanup() {
    cleanupSwapChain();

    vkDestroyImage(device, textureImage, nullptr);
    vkFreeMemory(device, textureImageMemory, nullptr);

    ...
}
```

回顾之前barrier的含义理解描述：

一句话解释: **在 src stage / access 完成前，dst stage / access 不能执行**

具体执行，举例子：

当我们执行布局转换（从 DST_OPTIMAL 到 SHARED_READ_ONLY_OPTIMAL）

- 当pipeline（隐式的），**将要** 进入到 `VK_ACCESS_SHADER_READ_BIT` 阶段，执行 `VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT` 的时候。
- 检查barrier：**是否正在** `VK_ACCESS_TRANSFER_WRITE_BIT` 阶段，正在执行 `VK_ACCESS_TRANSFER_WRITE_BIT` 。
- 如果是，屏障生效，等待执行上一步操作执行结束。


### 关于pipeline概念
在 Vulkan 中，“pipeline”分为很多类型，不只是图形渲染 pipeline：

|Pipeline 类型|用途|
|---|---|
|**Graphics Pipeline**|渲染到 framebuffer，包括 vertex/fragment shader、光栅化等|
|**Compute Pipeline**|GPU 上执行 compute shader|
|**Transfer / Blit**|并不是必须显式创建 pipeline，但 GPU 在 transfer 阶段也有自己的执行管线，Vulkan 将它抽象为 pipeline stage，例如 `VK_PIPELINE_STAGE_TRANSFER_BIT`|

从方便理解的角度：GPU执行指令的时候，要么是显示创建了pipeline。要么GPU相当于隐式创建pipeline，也会记录更新stage和access的flag。

- **显式 pipeline（Explicit Pipeline）**
    - 你自己创建的 Graphics Pipeline 或 Compute Pipeline。
    - 包括 shader、光栅化状态、混合状态等。
    - 当 GPU 执行 draw/dispatch 命令时，会启动这个 pipeline。
        
- **隐式 pipeline（Implicit Stage）**
    - 对于 copy / layout transition / buffer fill 等操作，并不需要用户创建 pipeline 对象。
    - GPU 内部有 **Transfer 阶段**、**Host 写阶段** 等。
    - Vulkan 使用 pipeline stage 标记（`VK_PIPELINE_STAGE_TRANSFER_BIT` 等）和访问掩码（`ACCESS_TRANSFER_WRITE_BIT` 等）来描述这些操作。
    - barrier 的作用就是告诉 GPU：“在 src stage / access 完成前，dst stage / access 不能执行”。

当然，需要注意的是：barrier 只对 **同一命令缓冲区内的顺序**起作用。如果命令缓冲区被反复提交（比如 drawFrame 的动作），那么整体的函数需要做 **防止重入** 的操作：
- 对同一资源（如纹理图像）在不同命令缓冲区/提交中进行 layout transition，需要用 **semaphore/event 或者 fence** 来保证前一次操作完成。
- CPU 层面也可以用锁（mutex）来保证同一张图片不会被重复 layout transition。
- Vulkan 常用做法：
    - `FRAMES_IN_FLIGHT` 分组，每帧使用独立的命令缓冲区和资源副本。
    - 每帧完成前，GPU 会通过 `vkWaitForFences` / `vkQueueSubmit` 的依赖保证安全。
## 复制 Buffer 到 Image
```cpp
void copyBufferToImage(VkBuffer buffer, VkImage image, uint32_t width, uint32_t height) {
    VkCommandBuffer commandBuffer = beginSingleTimeCommands();

	VkBufferImageCopy region{};
	region.bufferOffset = 0;
	region.bufferRowLength = 0;
	region.bufferImageHeight = 0;
	
	region.imageSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
	region.imageSubresource.mipLevel = 0;
	region.imageSubresource.baseArrayLayer = 0;
	region.imageSubresource.layerCount = 1;
	
	region.imageOffset = {0, 0, 0};
	region.imageExtent = {
	    width,
	    height,
	    1
	};
	
	vkCmdCopyBufferToImage(
	    commandBuffer,
	    buffer,
	    image,
	    VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
	    1,
	    &region
	);	

    endSingleTimeCommands(commandBuffer);
}
```

 Right now we're only copying one chunk of pixels to the whole image, but it's possible to specify an array of [`VkBufferImageCopy`](https://www.khronos.org/registry/vulkan/specs/1.0/man/html/VkBufferImageCopy.html) to perform many different copies from this buffer to the image in one operation.
## 准备 Texture Image
仍然是修改 `createTextureImage` 函数，在后面增加下面代码：

buffer要复制到texture image，需要两个步骤：
- texture image的layout转化为  `VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL`
- 执行复制： Execute the buffer to image copy operation
- texture image的layout转化为 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` ；方便shader使用。
```cpp
void createTextureImage(){
	... 
	
	transitionImageLayout(textureImage, VK_FORMAT_R8G8B8A8_SRGB, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
	copyBufferToImage(stagingBuffer, textureImage, static_cast<uint32_t>(texWidth), static_cast<uint32_t>(texHeight));

	// 当然最后还要cleanup
    transitionImageLayout(textureImage, VK_FORMAT_R8G8B8A8_SRGB, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);

    vkDestroyBuffer(device, stagingBuffer, nullptr);
    vkFreeMemory(device, stagingBufferMemory, nullptr);
}
```

# Texture Image View
为了访问图像，我们需要 ImageView

```cpp
VkImageView textureImageView;

...

void initVulkan() {
    ...
    createTextureImage();
    createTextureImageView();
    createVertexBuffer();
    ...
}

...

VkImageView createImageView(VkImage image, VkFormat format) {
    VkImageViewCreateInfo viewInfo{};
    viewInfo.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO;
    viewInfo.image = image;
    viewInfo.viewType = VK_IMAGE_VIEW_TYPE_2D;
    viewInfo.format = format;
    viewInfo.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    viewInfo.subresourceRange.baseMipLevel = 0;
    viewInfo.subresourceRange.levelCount = 1;
    viewInfo.subresourceRange.baseArrayLayer = 0;
    viewInfo.subresourceRange.layerCount = 1;

    VkImageView imageView;
    if (vkCreateImageView(device, &viewInfo, nullptr, &imageView) != VK_SUCCESS) {
        throw std::runtime_error("failed to create image view!");
    }

    return imageView;
}

void createTextureImageView() {
    textureImageView = createImageView(textureImage, VK_FORMAT_R8G8B8A8_SRGB);
}

void createImageViews() {
    swapChainImageViews.resize(swapChainImages.size());

    for (uint32_t i = 0; i < swapChainImages.size(); i++) {
        swapChainImageViews[i] = createImageView(swapChainImages[i], swapChainImageFormat);
    }
}

void cleanup() {
    cleanupSwapChain();

    vkDestroyImageView(device, textureImageView, nullptr);

    vkDestroyImage(device, textureImage, nullptr);
    vkFreeMemory(device, textureImageMemory, nullptr);
    ...
}
```

# 采样器 (Samplers)
## 基础概念原理
在shader中，虽然可以直接访问 texels，但更多使用sampler来访问（这样sampler内部可以支持一些采样算法）。

假设，texture的一个像素，对应到多个fragments 时（oversampling）。那么使用采样器，会有平滑效果：（这里oversampling过采样指的是，fragment采样的时候，对同个texel多次采样）


![[Vulkan入门04_Texture_mapping-基础概念原理-01.png]]

另一个方面，欠采样（undersampling）也会产生问题，即，一个fragment覆盖多个texel。会产生 artifacts （走样）。欠采样的本质：**欠采样**发生在 **fragment 的采样率不足以覆盖它所映射的 texel 区域**
- 典型情况：
    1. **Nearest sampling**：每个 fragment 只采样 1 个 texel
        - fragment 的颜色完全依赖于采样点命中的 texel
        - 导致 aliasing / 锯齿 / blocky artifacts
    2. **部分采样 + 融合**：fragment 对多个 texel 做采样，但采样点太少
        - 结果是丢掉纹理细节
        - 也会产生 aliasing 或模糊

下面是一个结果。（解决方法是各向异性采样 anisotropic filtering：原理：针对纹理区域为长方形条的fragment， **沿长轴方向增加采样点** → 多个 texel 加权融合；短轴方向采样少 → 节约计算）

![[Vulkan入门04_Texture_mapping-基础概念原理-02.png]]

此外，采样器也会定义超出正常范围之外的位置如何填充颜色，（address mode）：
![[Vulkan入门04_Texture_mapping-基础概念原理-03.png]]


## 创建采样器
```cpp
void initVulkan() {
    ...
    createTextureImage();
    createTextureImageView();
    createTextureSampler();
    ...
}

...

void createTextureSampler() {
	VkSamplerCreateInfo samplerInfo{};
	samplerInfo.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO;
	// 针对 oversampling (简记：纹理过小)
	samplerInfo.magFilter = VK_FILTER_LINEAR;
	// 针对 undersampling (简记：纹理过大)
	samplerInfo.minFilter = VK_FILTER_LINEAR;

	// 超出区域的采样方式
	samplerInfo.addressModeU = VK_SAMPLER_ADDRESS_MODE_REPEAT;
	samplerInfo.addressModeV = VK_SAMPLER_ADDRESS_MODE_REPEAT;
	samplerInfo.addressModeW = VK_SAMPLER_ADDRESS_MODE_REPEAT;	
	
	// 各向异性过滤
	samplerInfo.anisotropyEnable = VK_TRUE;
	// 需要查询设备获取最大各向异性采样的限制
	VkPhysicalDeviceProperties properties{};
	vkGetPhysicalDeviceProperties(physicalDevice, &properties);
	// 最多使用的采样点的限制
	samplerInfo.maxAnisotropy = properties.limits.maxSamplerAnisotropy;
	// 如果gpu不支持，那么我们也要关闭这个功能
	// samplerInfo.anisotropyEnable = VK_FALSE;
	// samplerInfo.maxAnisotropy = 1.0f;
	
	// 仅在 address mode 是 clamp to border的时候有效。
	samplerInfo.borderColor = VK_BORDER_COLOR_INT_OPAQUE_BLACK;
	// 使用sampler的坐标范围
	// - True : [0,texWidth) x [0, texHeight)
	// - False : [0,1) x [0,1)
	samplerInfo.unnormalizedCoordinates = VK_FALSE;

	// 采样结果用来先做 Compare OP，随后的结果用来做filtering
	// 常用来做 percentage closer filtering (PCF)
	// https://developer.nvidia.com/gpugems/gpugems/part-ii-lighting-and-shadows/chapter-11-shadow-map-antialiasing
	samplerInfo.compareEnable = VK_FALSE;
	samplerInfo.compareOp = VK_COMPARE_OP_ALWAYS;


	// mipmap滤波配置，暂时不开启
	samplerInfo.mipmapMode = VK_SAMPLER_MIPMAP_MODE_LINEAR;
	samplerInfo.mipLodBias = 0.0f;
	samplerInfo.minLod = 0.0f;
	samplerInfo.maxLod = 0.0f;	
	
	
    if (vkCreateSampler(device, &samplerInfo, nullptr, &textureSampler) != VK_SUCCESS) {
        throw std::runtime_error("failed to create texture sampler!");
    }	
}

void cleanup() {
    cleanupSwapChain();

    vkDestroySampler(device, textureSampler, nullptr);
    vkDestroyImageView(device, textureImageView, nullptr);

    ...
}

// 创建的时候开启 anisotropy 这个能力
void createLogicalDevice(){
	...
	VkPhysicalDeviceFeatures deviceFeatures{};
	deviceFeatures.samplerAnisotropy = VK_TRUE;
	...
}

// 通常现代GPU都有这个能力
bool isDeviceSuitable(VkPhysicalDevice device) {
    ...

    VkPhysicalDeviceFeatures supportedFeatures;
    vkGetPhysicalDeviceFeatures(device, &supportedFeatures);

    return indices.isComplete() && extensionsSupported && swapChainAdequate && supportedFeatures.samplerAnisotropy;
}
```

# 使用Descriptor (combined image sampler)
## Descriptor set layout修改 (add sampler binding)
函数 `createDescriptorSetLayout` 修改
```cpp
VkDescriptorSetLayoutBinding samplerLayoutBinding{};
samplerLayoutBinding.binding = 1;
samplerLayoutBinding.descriptorCount = 1;
samplerLayoutBinding.descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
samplerLayoutBinding.pImmutableSamplers = nullptr;
samplerLayoutBinding.stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT;

std::array<VkDescriptorSetLayoutBinding, 2> bindings = {uboLayoutBinding, samplerLayoutBinding};
VkDescriptorSetLayoutCreateInfo layoutInfo{};
layoutInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
layoutInfo.bindingCount = static_cast<uint32_t>(bindings.size());
layoutInfo.pBindings = bindings.data();
```
从上面我们可以看到，我们给现有的 DescriptorSet Layout 增加了一个binding （所以我们要复用之前的Descriptor Set）

## Descriptor pool修改(增加这个类别的descriptorCount)
函数 `createDescriptorPool` 修改
```cpp
std::array<VkDescriptorPoolSize, 2> poolSizes{};
poolSizes[0].type = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
poolSizes[0].descriptorCount = static_cast<uint32_t>(MAX_FRAMES_IN_FLIGHT);
poolSizes[1].type = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
poolSizes[1].descriptorCount = static_cast<uint32_t>(MAX_FRAMES_IN_FLIGHT);

VkDescriptorPoolCreateInfo poolInfo{};
poolInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
poolInfo.poolSizeCount = static_cast<uint32_t>(poolSizes.size());
poolInfo.pPoolSizes = poolSizes.data();
poolInfo.maxSets = static_cast<uint32_t>(MAX_FRAMES_IN_FLIGHT);
```
最后的maxSets没有调整，这也说明我们要复用我们之前的 Descriptor Set （为其增加新的Descriptor）。

## Desciptor Set修改 (绑定新的Descriptor)
函数 `createDescriptorSets` 修改：
```cpp
for (size_t i = 0; i < MAX_FRAMES_IN_FLIGHT; i++) {
	std::array<VkWriteDescriptorSet, 2> descriptorWrites{};

    VkDescriptorBufferInfo bufferInfo{};
    bufferInfo.buffer = uniformBuffers[i];
    bufferInfo.offset = 0;
    bufferInfo.range = sizeof(UniformBufferObject);

	descriptorWrites[0].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
	descriptorWrites[0].dstSet = descriptorSets[i];
	descriptorWrites[0].dstBinding = 0;
	descriptorWrites[0].dstArrayElement = 0;
	descriptorWrites[0].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
	descriptorWrites[0].descriptorCount = 1;
	descriptorWrites[0].pBufferInfo = &bufferInfo;

    VkDescriptorImageInfo imageInfo{};
    imageInfo.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    imageInfo.imageView = textureImageView;
    imageInfo.sampler = textureSampler;
	
	descriptorWrites[1].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
	descriptorWrites[1].dstSet = descriptorSets[i];
	descriptorWrites[1].dstBinding = 1;
	descriptorWrites[1].dstArrayElement = 0;
	descriptorWrites[1].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER;
	descriptorWrites[1].descriptorCount = 1;
	descriptorWrites[1].pImageInfo = &imageInfo;
	
	vkUpdateDescriptorSets(device, static_cast<uint32_t>(descriptorWrites.size()), descriptorWrites.data(), 0, nullptr);    
    
}
```
这里descriptor完成了对 imageview，sampler 的绑定。（而前面的动作，只是声明了要做这些事情做的准备）

## 顶点数据修改(增加纹理坐标)
顶点数据类型。好在这里也定义了 attributDescription。剩余部分都自动生效。
```cpp
struct Vertex {
    glm::vec2 pos;
    glm::vec3 color;
    glm::vec2 texCoord;

    static VkVertexInputBindingDescription getBindingDescription() {
        VkVertexInputBindingDescription bindingDescription{};
        bindingDescription.binding = 0;
        bindingDescription.stride = sizeof(Vertex);
        bindingDescription.inputRate = VK_VERTEX_INPUT_RATE_VERTEX;

        return bindingDescription;
    }

    static std::array<VkVertexInputAttributeDescription, 3> getAttributeDescriptions() {
        std::array<VkVertexInputAttributeDescription, 3> attributeDescriptions{};

        attributeDescriptions[0].binding = 0;
        attributeDescriptions[0].location = 0;
        attributeDescriptions[0].format = VK_FORMAT_R32G32_SFLOAT;
        attributeDescriptions[0].offset = offsetof(Vertex, pos);

        attributeDescriptions[1].binding = 0;
        attributeDescriptions[1].location = 1;
        attributeDescriptions[1].format = VK_FORMAT_R32G32B32_SFLOAT;
        attributeDescriptions[1].offset = offsetof(Vertex, color);

        attributeDescriptions[2].binding = 0;
        attributeDescriptions[2].location = 2;
        attributeDescriptions[2].format = VK_FORMAT_R32G32_SFLOAT;
        attributeDescriptions[2].offset = offsetof(Vertex, texCoord);

        return attributeDescriptions;
    }
};
```


修改具体的顶点数据
```cpp
const std::vector<Vertex> vertices = {
    {{-0.5f, -0.5f}, {1.0f, 0.0f, 0.0f}, {1.0f, 0.0f}},
    {{0.5f, -0.5f}, {0.0f, 1.0f, 0.0f}, {0.0f, 0.0f}},
    {{0.5f, 0.5f}, {0.0f, 0.0f, 1.0f}, {0.0f, 1.0f}},
    {{-0.5f, 0.5f}, {1.0f, 1.0f, 1.0f}, {1.0f, 1.0f}}
};
```

## shader的修改
vertex shader：因为pipeline先要经过vertex shader。所以传递个fragment shader的顶点数据（这里是纹理坐标，和顶点颜色）必须在 vertex shader里指定。
```cpp
#version 450
// 上面的version也必须指定，否则无法编译

layout(location = 0) in vec2 inPosition;
layout(location = 1) in vec3 inColor;
layout(location = 2) in vec2 inTexCoord;

layout(location = 0) out vec3 fragColor;
layout(location = 1) out vec2 fragTexCoord;

void main() {
    gl_Position = ubo.proj * ubo.view * ubo.model * vec4(inPosition, 0.0, 1.0);
    fragColor = inColor;
    fragTexCoord = inTexCoord;
}
```


fragment shader:
```glsl
#version 450

layout(location = 0) in vec3 fragColor;
layout(location = 1) in vec2 fragTexCoord;

layout(location = 0) out vec4 outColor;

void main() {
    outColor = vec4(fragTexCoord, 0.0, 1.0);
}
```

运行可以看到（验证纹理坐标是否正确的读取）：
![[Vulkan入门04_Texture_mapping-shader的修改-01.png]]



修改：
```glsl
#version 450

layout(location = 0) in vec3 fragColor;
layout(location = 1) in vec2 fragTexCoord;

layout(location = 0) out vec4 outColor;

layout(binding = 1) uniform sampler2D texSampler;

void main() {
    outColor = texture(texSampler, fragTexCoord);
}
```

运行可以看到（验证texture成功使用）
![[Vulkan入门04_Texture_mapping-shader的修改-02.png]]

修改：
```glsl
#version 450

layout(location = 0) in vec3 fragColor;
layout(location = 1) in vec2 fragTexCoord;

layout(location = 0) out vec4 outColor;

layout(binding = 1) uniform sampler2D texSampler;

void main() {
    outColor = texture(texSampler, fragTexCoord*2.0);
}
```

运行可以看到（验证 address mode）
![[Vulkan入门04_Texture_mapping-shader的修改-03.png]]

还可以进行颜色融合：
```glsl
#version 450

layout(location = 0) in vec3 fragColor;
layout(location = 1) in vec2 fragTexCoord;

layout(location = 0) out vec4 outColor;

layout(binding = 1) uniform sampler2D texSampler;

void main() {
	outColor = vec4(fragColor * texture(texSampler, fragTexCoord).rgb, 1.0);
}
```

![[Vulkan入门04_Texture_mapping-shader的修改-04.png]]