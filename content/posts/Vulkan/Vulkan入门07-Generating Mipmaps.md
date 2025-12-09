---
title: Vulkan入门07-Generating Mipmaps
date: 2025-12-09T12:40:32+08:00
tags:
  - vulkan
  - mipmap
  - texture
  - sampler
draft: false
---

![[Vulkan入门07-Generating Mipmaps-1765248326505.png]]

Mipmap: (Mip, Multum In Parvo拉丁语，在小中包含很多（Much in a little）)
- 把同一张纹理的多个不同分辨率版本
- 全部打包（或预计算）在一起
- 渲染时根据物体大小自动选用合适的层级

本节主要讲解如何创建mipmap（使用vulkan的blit函数；随后矫正layout，调整采样器；整体实现的代码上并不复杂）

<!--more-->

# 图像创建
在Vulkan中，每个 mip 图像保存在 `VkImage` 中不同的 mip level中。 mip level 0 是原始图像，level 0 之后的level，通常也被叫做 mip chain。

当创建 `VkImage` 的时候，可以指定 mip level 的数目。每次个mip level比它的上一级level，长度和宽度都为 1/2 。因此根据图像大小，如果要做mipmap，我们可以预先计算出mip level的数量：
```cpp
...
uint32_t mipLevels;
VkImage textureImage;
...

// 根据加载的texture的宽高，计算 mip levels
void createTextureImage(){
	int texWidth, texHeight, texChannels;
	stbi_uc* pixels = stbi_load(
		TEXTURE_PATH.c_str(), &texWidth, &texHeight, &texChannels, STBI_rgb_alpha);
	...
	mipLevels = static_cast<uint32_t>(
		std::floor(std::log2(std::max(texWidth, texHeight)))) + 1;
	...
}

// 其他位置也需要修改： image, view, layout （需要指定 mip levels）
void createImage(uint32_t width, uint32_t height, 
	uint32_t mipLevels, 
	VkFormat format, VkImageTiling tiling, VkImageUsageFlags usage, 
	VkMemoryPropertyFlags properties, 
	VkImage& image, VkDeviceMemory& imageMemory) {
    ...
    imageInfo.mipLevels = mipLevels;
    ...
}

VkImageView createImageView(VkImage image, VkFormat format, VkImageAspectFlags aspectFlags, uint32_t mipLevels) {
    ...
    viewInfo.subresourceRange.levelCount = mipLevels;
    ...


void transitionImageLayout(VkImage image, VkFormat format, VkImageLayout oldLayout, VkImageLayout newLayout, uint32_t mipLevels) {
    ...
    barrier.subresourceRange.levelCount = mipLevels;
    ...
    
// 以及所有调用函数的位置，也要修改：

// 此处调用不用mipmap，填入mip level = 1
createImage(
	swapChainExtent.width, swapChainExtent.height, 1, depthFormat,
		VK_IMAGE_TILING_OPTIMAL, 
		VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT, 
		VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, depthImage, depthImageMemory);
...
// 此处需要指定 mip level
createImage(texWidth, texHeight, mipLevels, VK_FORMAT_R8G8B8A8_SRGB, 
		VK_IMAGE_TILING_OPTIMAL, 
		VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT, 
		VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, textureImage, textureImageMemory);
...
// 此处调用不用mipmap，填入mip level = 1
swapChainImageViews[i] = createImageView(swapChainImages[i], swapChainImageFormat, VK_IMAGE_ASPECT_COLOR_BIT, 1);
...
// 此处调用不用mipmap，填入mip level = 1
depthImageView = createImageView(depthImage, depthFormat, VK_IMAGE_ASPECT_DEPTH_BIT, 1);
...
// 此处需要指定 mip level
textureImageView = createImageView(textureImage, VK_FORMAT_R8G8B8A8_SRGB, VK_IMAGE_ASPECT_COLOR_BIT, mipLevels);
...
// 此处调用不用mipmap，填入mip level = 1
transitionImageLayout(depthImage, depthFormat, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL, 1);
...
// 此处需要指定 mip level
transitionImageLayout(textureImage, VK_FORMAT_R8G8B8A8_SRGB, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, mipLevels);
```

# 生成mipmap
staging buffer只能填充 mip level 0，其他level仍然是undefined。为了填充这些level，我们需要从level0生成。我们将会使用 `VkCmdBlitImage` 命令，多次调用这个指令来生成各个level的mip图像。（注释 ：**BLIT/BLT, BLock Image Transfer**，指 **在图像（image）之间进行成块的数据拷贝**，可以在拷贝过程中做 **缩放（scale）、翻转、格式转换（有限）** ）‘

为了方便对图像处理，我们需要创建的时候指定对应的flags：
```cpp
...
createImage(texWidth, texHeight, mipLevels, 
	VK_FORMAT_R8G8B8A8_SRGB, VK_IMAGE_TILING_OPTIMAL, 
	VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT, 
	VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, textureImage, textureImageMemory);
...
```

和其他的图像操作类似，`vkCmdBlitImage` 操作也依赖图像的布局。为了更优的性能，我们需要把输入图像的布局调整为 `VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL` ，输出图像的布局调整成 `VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL` 。

```cpp

void generateMipmaps(VkImage image, int32_t texWidth, int32_t texHeight, 
	uint32_t mipLevels) {
    VkCommandBuffer commandBuffer = beginSingleTimeCommands();

    VkImageMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
    barrier.image = image;
    barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
    barrier.subresourceRange.baseArrayLayer = 0;
    barrier.subresourceRange.layerCount = 1;
    barrier.subresourceRange.levelCount = 1;
    
    // 复用上面的barrier，来做若干次转化
    
	int32_t mipWidth = texWidth;
	int32_t mipHeight = texHeight;
	
	for (uint32_t i = 1; i < mipLevels; i++) {
		// 注意循环从1开始
		barrier.subresourceRange.baseMipLevel = i - 1;
		// 上一级mip level计算结束后，其布局为 VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL
		barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
		// 本次执行前，上一级mip level需要切换为 VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL
		barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
		// 上一级mip level计算结束的动作，VK_ACCESS_TRANSFER_WRITE_BIT;
		barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
		// 本次执行前，上一级mip level需要准备好VK_ACCESS_TRANSFER_READ_BIT
		barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
		
		// 记录这个barrier，让布局转化生效。
		vkCmdPipelineBarrier(commandBuffer,
		    VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0,
		    0, nullptr,
		    0, nullptr,
		    1, &barrier);
		    
		// 布局准备好了，我们可以执行 blit了
		// source level: i-1 , dest level: i
		VkImageBlit blit{};

		// 表示源区域的定义：
		// 区域覆盖的像素为 [offset0, offset1)。
		
		// 源区域的最小角（offset0）
		// 包含(x,y,z)的坐标，表示源区域的起始 texel（**inclusive**）
		// 这里设置为 (0,0,0) 表示从源 mip 的左上角（或原点）开始。
		blit.srcOffsets[0] = { 0, 0, 0 };
		// 源区域的最大角（offset1），表示源区域的结束坐标（**exclusive**）。
		// 这里表示 到 源 mip 的右下角结束。
		blit.srcOffsets[1] = { mipWidth, mipHeight, 1 };
		
		// 指定源图像子资源的“面”(aspect)。对于彩色纹理通常是 COLOR_BIT。
		blit.srcSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
		// 源子资源使用的 mip 级别。这里是 i-1，说明源是上一级（更高分辨率）的 mip 级别。
		blit.srcSubresource.mipLevel = i - 1;
		// 源的起始 array layer（针对 array textures 或 cubemaps），
		// 这里从 layer 0 开始。
		blit.srcSubresource.baseArrayLayer = 0;
		// 源使用的层数（从 baseArrayLayer 开始的连续层数）。这里是 1，表示只 blit 单层。
		blit.srcSubresource.layerCount = 1;
		
		// 目标区域和一些参数定义，可以参见源区域定义来类比。
		blit.dstOffsets[0] = { 0, 0, 0 };
		blit.dstOffsets[1] = { 
			mipWidth > 1 ? 
				mipWidth / 2 : 
				1, 
			mipHeight > 1 ? 
				mipHeight / 2 : 
				1, 
			1 
		};
		blit.dstSubresource.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
		blit.dstSubresource.mipLevel = i;
		blit.dstSubresource.baseArrayLayer = 0;
		blit.dstSubresource.layerCount = 1;
		
		// 执行blit操作
		vkCmdBlitImage(commandBuffer,
			// 源图像，源图像布局
		    image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
			// 目标图像，目标图像布局
		    image, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
		    1, // region count
		    &blit, /// blit参数列表（对应 region count）
		    VK_FILTER_LINEAR // 使用的滤波器
		);
		// 注意，blit操作必须被提交到具备 graphics能力的队列。
		
		// blit结束后，再将layout转化为 VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT
		barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
		barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
		barrier.srcAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
		barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
		
		// 向pipeline中插入barrier（指定具体的源阶段和目标阶段，然后插入barrier）
		// barrier中定义了等待的动作
		vkCmdPipelineBarrier(commandBuffer,
		    VK_PIPELINE_STAGE_TRANSFER_BIT,// 源阶段阶段掩码（必须完成）
		    VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, // 目标阶段掩码（要进入）
		    0, // 队列内同步；如果有其他subpass依赖，这里要指定
		    0, nullptr, // 用于全局（buffer/image 通用）的内存依赖
		    0, nullptr, // 用于 buffer 的同步和 layout/ownership 管理
		    1, &barrier); // 用于image同步。	
		
		// 循环中不断缩小 mipWidth和mipHeight    
		if (mipWidth > 1) mipWidth /= 2;
	    if (mipHeight > 1) mipHeight /= 2;
	}
	// 最后1个level，还没有做布局转化，补上
    barrier.subresourceRange.baseMipLevel = mipLevels - 1;
    barrier.oldLayout = VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
    barrier.newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;
    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;

    vkCmdPipelineBarrier(commandBuffer,
        VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT, 0,
        0, nullptr,
        0, nullptr,
        1, &barrier);	

    endSingleTimeCommands(commandBuffer);
}
```

回忆我们的texture的创建过程：
- 调整image布局： VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL 
- 从staging buffer上传到image： `copyBufferToImage`
- 调整image布局： VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL  
我们把最后一个步骤替换为生成mipmap。（这个操作最后转化了我们需要的layout）
```cpp
...
transitionImageLayout(textureImage, 
	VK_FORMAT_R8G8B8A8_SRGB, 
	VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 
	mipLevels);
copyBufferToImage(
	stagingBuffer, textureImage, 
	static_cast<uint32_t>(texWidth), static_cast<uint32_t>(texHeight));
generateMipmaps(textureImage, texWidth, texHeight, mipLevels);
...
```

## 检查 linear filter支持
我们上面的blit操作需要 texture image format 支持 linear filtering。可以用 `vkGetPhysicalDeviceFormatProperties` 方法来检查。我们补充这个部分。

```cpp
void createTextureImage() {
    ...
	// 增加一个参数
    generateMipmaps(textureImage, VK_FORMAT_R8G8B8A8_SRGB, texWidth, texHeight, mipLevels);
}

void generateMipmaps(VkImage image, VkFormat imageFormat, int32_t texWidth, int32_t texHeight, uint32_t mipLevels) {
    // Check if image format supports linear blitting
    VkFormatProperties formatProperties;
    vkGetPhysicalDeviceFormatProperties(
	    physicalDevice, imageFormat, &formatProperties);
	    
	if (!(formatProperties.optimalTilingFeatures & 
		VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT)) {
	    throw std::runtime_error("textureimage format unsupport linear blitting!");
	}
    ...
}
```
如果不支持，有两种办法：
1. 选择支持 linear filtering 的图像格式。
2. 用第三方库，比如 `stb_image_resize` 来生成mipmap，然后上传到image中。


# 采样器
`VkImage` 包含 mipmap数据， `VkSampler` 则控制渲染的时候如何读取数据。Vulkan
支持我们指定： `minLod`, `maxLod`, `mipLodBias` 以及 `mipmapMod` （Lod，即Level of Details，层次细节；lod越大越远）。当我们对一个texture进行采样的时候，采样器选择一个miplevel，选择的方式参考下面的伪代码：
```cpp
lod = getLodLevelFromScreenSize(); //smaller when the object is close, may be negative
lod = clamp(lod + mipLodBias, minLod, maxLod);

level = clamp(floor(lod), 0, texture.mipLevels - 1);  //clamped to the number of mip levels in the texture

if (mipmapMode == VK_SAMPLER_MIPMAP_MODE_NEAREST) {
    color = sample(level);
} else {
    color = blend(sample(level), sample(level + 1));
}
```

采样动作本身，也被lod影响，伪代码：
```cpp
if (lod <= 0) {
    color = readTexture(uv, magFilter);
} else {
    color = readTexture(uv, minFilter);
}
```

- 如果 对象 距离 camera 近，使用 `magFilter` ，而远则使用 `minFilter` 。通常lod是非负的，只有距离相机近的时候才会是0，不过通过指定 `mipLodBias` ，我们可以让Vulkan用更加小的lod和level。
	- 补充：语义来说，magFilter，maginificationFilter，纹理被放大，一个纹理 texel 被映射到多个屏幕像素（fragments）；minFilter， minificationFilter，纹理被缩小，多个纹理 texel 被映射到同一个屏幕像素（fragment）
	- lod<=0时，距离相机很近，纹理被放大（多个像素对应一个纹理像素）
	- 现代渲染常见的使用方式：
		- mipmapMode = VK_SAMPLER_MIPMAP_MODE_LINEAR; // trilinear
		- minFilter = VK_FILTER_LINEAR;
		- magFilter = VK_FILTER_LINEAR;
		- 而 mipLodBias 取值：负（更锐利，更高分辨率），正（更模糊）；常见范围 -0.5~+0.5


接下来我们修改代码，创建采样器
```cpp
void createTextureSampler() {
    ...
    samplerInfo.mipmapMode = VK_SAMPLER_MIPMAP_MODE_LINEAR;
    samplerInfo.minLod = 0.0f; // Optional
    samplerInfo.maxLod = VK_LOD_CLAMP_NONE;
    samplerInfo.mipLodBias = 0.0f; // Optional
    ...
}
```

此时，运行程序看到结果：（我们通过修改 samplerInfo 可以开启或关闭 mipmap）

![[Vulkan入门07-Generating Mipmaps-1765254853080.png]]

实际上，开启不开启mipmap的差距并不明显。复杂的场景，就能看出差别了，mipmap的速度也会更快。

# 为什么 mipmap 在复杂场景中“好”
mipmap =（近似）低通滤波 + 下采样
效果：
- 消除 moiré
- 消除 shimmering（远处闪烁）
- 防止高频纹理污染画面

没有 mipmap 的复杂场景：
- 草地
- 地砖
- 屋顶
- 远处建筑  
    几乎一定会**闪＋花＋嘈杂**

实时渲染的典型配置
```
minFilter = LINEAR
mipmapMode = LINEAR
anisotropy = 8~16
```

在复杂场景中：
- 斜视角
- 大面积地面
- 长距离可见性

mipmap + 各向异性是**唯一可扩展方案**



**注意场景： 非常近距离 + 高频纹理**
- 摄像机贴脸观察
- 负 mipLodBias 不当
- mip 级别切换明显
表现：
- 轻微模糊
- mip 边界可感知

解决：
- 负 `mipLodBias`（-0.25 ~ -0.5）
- 更高分辨率 base level
- 各向异性过滤