---
title: Vulkan入门05-Depth buffering
date: 2025-12-08T15:37:04+08:00
tags:
  - vulkan
  - depth-test
  - 3d
draft: false
---
![[Vulkan入门05-Depth buffering-intro-01.png]]


深度缓冲，对于有图形基础的人来说是很熟悉的概念。Vulkan中是如何管理的呢？
1. 创建 Depth Image 和 Depth Image View, Depth Image Memory
2. 在 RenderPass 创建的时候，增加深度附件。（在渲染的时候，指定RenderPass的ClearValue）
3. 创建FrameBuffer的时候，绑定具体的深度数据。
4. 渲染：创建渲染Pipine的时候，开启深度测试（填充对应的结构体）
5. 资源管理：注意和swapchain image数据的生命周期一致。

<!--more-->

## 3D几何
顶点修改为3D顶点：
```cpp
struct Vertex {
    glm::vec3 pos;
    glm::vec3 color;
    glm::vec2 texCoord;

    ...

    static std::array<VkVertexInputAttributeDescription, 3> getAttributeDescriptions() {
        std::array<VkVertexInputAttributeDescription, 3> attributeDescriptions{};

        attributeDescriptions[0].binding = 0;
        attributeDescriptions[0].location = 0;
        attributeDescriptions[0].format = VK_FORMAT_R32G32B32_SFLOAT;
        attributeDescriptions[0].offset = offsetof(Vertex, pos);

        ...
    }
};
```

更新VertexShader
```glsl
layout(location = 0) in vec3 inPosition;

...

void main() {
    gl_Position = ubo.proj * ubo.view * ubo.model * vec4(inPosition, 1.0);
    fragColor = inColor;
    fragTexCoord = inTexCoord;
}
```

更新顶点数据，增加z坐标
```cpp
const std::vector<Vertex> vertices = {
    {{-0.5f, -0.5f, 0.0f}, {1.0f, 0.0f, 0.0f}, {0.0f, 0.0f}},
    {{0.5f, -0.5f, 0.0f}, {0.0f, 1.0f, 0.0f}, {1.0f, 0.0f}},
    {{0.5f, 0.5f, 0.0f}, {0.0f, 0.0f, 1.0f}, {1.0f, 1.0f}},
    {{-0.5f, 0.5f, 0.0f}, {1.0f, 1.0f, 1.0f}, {0.0f, 1.0f}}
};
```

随后，我们为了表明3D渲染，在之前的矩形下方再增加一个矩形。
![[Vulkan入门05-Depth buffering-intro-01.png]]

更新顶点和索引数据：
```cpp
const std::vector<Vertex> vertices = {
    {{-0.5f, -0.5f, 0.0f}, {1.0f, 0.0f, 0.0f}, {0.0f, 0.0f}},
    {{0.5f, -0.5f, 0.0f}, {0.0f, 1.0f, 0.0f}, {1.0f, 0.0f}},
    {{0.5f, 0.5f, 0.0f}, {0.0f, 0.0f, 1.0f}, {1.0f, 1.0f}},
    {{-0.5f, 0.5f, 0.0f}, {1.0f, 1.0f, 1.0f}, {0.0f, 1.0f}},

    {{-0.5f, -0.5f, -0.5f}, {1.0f, 0.0f, 0.0f}, {0.0f, 0.0f}},
    {{0.5f, -0.5f, -0.5f}, {0.0f, 1.0f, 0.0f}, {1.0f, 0.0f}},
    {{0.5f, 0.5f, -0.5f}, {0.0f, 0.0f, 1.0f}, {1.0f, 1.0f}},
    {{-0.5f, 0.5f, -0.5f}, {1.0f, 1.0f, 1.0f}, {0.0f, 1.0f}}
};

const std::vector<uint16_t> indices = {
    0, 1, 2, 2, 3, 0,
    4, 5, 6, 6, 7, 4
};
```

我们注意到，更高的矩形，应该在矮矩形的上方。但此时我们的显示内容为：
![[Vulkan入门05-Depth buffering-3d几何-01.png]]


解决这个问题，两个办法：
1. 根据深度，对所有的draw call排序。先绘制更深的图元，然后绘制浅的图元。 （这个方法通常处理透明物体： 因为 order-independent transparency 是很困难的问题）
	- 关于透明材料的思考： **透明材料在物理上是通过波长相关的吸收系数来定义的，其颜色表现来自未被吸收的透射光；吸收的是背景光本身，因此不存在“材料吸收固定颜色”的直观定义。只有在图形学简化模型（如 alpha blending）中，才人为引入“材料颜色”作为独立的注入项。**
	- 现实中的透明材料，本身也有散射光线（体散射）。现实中的透明材料，本身也有散射光线。因此， **alpha融合本身，是透明吸收模型+材料自身体散射的这种构造意图产生的颜色；它既不是严格的物理模型，也不满足真实散射的基本约束。**
	- PBR中，会根据透明色颜色，使用 Transmisson Color 来计算颜色吸收（简化处理，考虑材料厚度，实际是对 **Beer–Lambert 透射公式** 的 **RGB 近似**）。而对于体散射，区分材质来处理。比如，对于类似塑料的材质（实时处理），在材质面上加一个体积雾近似，用alpha融合/半透明叠加代替体散射。
2. 使用深度缓冲 (depth buffer)
	- **Fragment 的概念**：  光栅化后对应屏幕像素采样点的候选，包含该像素位置及被其射线穿过的图元信息，是 **像素空间与图元几何信息的结合体**。
	- **Fragment 属性**：  来自图元顶点，通过 **重心插值 (barycentric interpolation)** 计算深度、颜色、纹理坐标等信息。
	- **光栅化阶段流程**：
	    1. **计算图元覆盖像素区域** → 生成对应的 fragment（或多个 MSAA 采样点）。
	    2. **Hierarchical-Z（Hi-Z）优化**
	        - 利用 depth buffer 金字塔结构，对图元覆盖区域做快速粗粒度深度测试。
	        - 可在 Early-Z 前剔除整个图元或大区域，减少 fragment 生成和后续深度测试计算量。
	    3. **Early-Z（片段着色器前深度测试）**
	        - 对每个 fragment（或 MSAA 采样点）在进入片段着色器前做深度测试。
	        - 若深度大于 depth buffer 值，则该 fragment（或采样点）被丢弃，避免执行片段着色器。
	        - GPU 可以利用 **粗粒度剔除**（例如图元包围盒 + 顶点深度）来减少 fragment 生成，但 Early-Z 核心仍是 **fragment / sample 级别的提前深度测试**。

使用GLM为了兼容vulkan的深度范围(0,1)，我们需要开启一些宏开关：（OGL默认是-1,1）
```cpp
#define GLM_FORCE_RADIANS
#define GLM_FORCE_DEPTH_ZERO_TO_ONE
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
```

## Depth image and view
我们只需要创建一个深度图像即可，因为绘制指令不会并行（即1次仅有1个绘制指令再执行，这是硬件保障的）
```cpp
VkImage depthImage;
VkDeviceMemory depthImageMemory;
VkImageView depthImageView;
```

接着我们来创建深度缓冲相关的资源:
```cpp
void initVulkan() {
    ...
    createCommandPool();
    createDepthResources();
    createTextureImage();
    ...
}

...

void createDepthResources() {

}
```

关于深度缓冲：宽高选择 swap chain extend的宽高，usage选择 depth attachment，选择最优的tiling，以及 device local memory，这些选择是显而易见的。还有一个问题，depth image的格式如何选择？常见的格式有：
- `VK_FORMAT_D32_SFLOAT`: 32-bit float for depth
- `VK_FORMAT_D32_SFLOAT_S8_UINT`: 32-bit signed float for depth and 8 bit stencil component  （模板测试本文先不提，实际上和深度测试类似，可以组合使用）
- `VK_FORMAT_D24_UNORM_S8_UINT`: 24-bit float for depth and 8 bit stencil component

我们可以直接使用第一个格式。 `VK_FORMAT_D32_SFLOAT` （因为被广泛支持）。但我们还是写一个函数来更加动态的检测：
```cpp
// 从 candidates 中，选择符合 tiling 和 features 设定的格式
VkFormat findSupportedFormat(const std::vector<VkFormat>& candidates, VkImageTiling tiling, VkFormatFeatureFlags features) {
	for (VkFormat format : candidates) {
	    VkFormatProperties props;
		vkGetPhysicalDeviceFormatProperties(physicalDevice, format, &props);
		if (tiling == VK_IMAGE_TILING_LINEAR && 
		// props.linearTilingFeatures 返回了格式所支持的 linear tiling 下的 feature
		(props.linearTilingFeatures & features) == features) {
		    return format;
		} else if (tiling == VK_IMAGE_TILING_OPTIMAL &&
		// props.optimalTilingFeatures 返回了格式所支持的 optimal tiling 下的 feature
		 (props.optimalTilingFeatures & features) == features) {
		    return format;
		}		    
	}
	// 查找格式失败，扔出异常。
    throw std::runtime_error("failed to find supported format!");
}

// 我们具体查找格式的用法
VkFormat findDepthFormat() {
    return findSupportedFormat(
        {
	        VK_FORMAT_D32_SFLOAT, 
	        VK_FORMAT_D32_SFLOAT_S8_UINT, 
	        VK_FORMAT_D24_UNORM_S8_UINT
	    },
        VK_IMAGE_TILING_OPTIMAL,
        VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT
    );
}

// 判断选择的格式是否支持stencil(模板)
bool hasStencilComponent(VkFormat format) {
    return format == VK_FORMAT_D32_SFLOAT_S8_UINT || format == VK_FORMAT_D24_UNORM_S8_UINT;
}
```

现在我们可以回到 `createDepthResources` 函数中：
```cpp
VkImage depthImage;
VkDeviceMemory depthImageMemory;
VkImageView depthImageView;

void createDepthResources(){
	VkFormat depthFormat = findDepthFormat();
	createImage(
		swapChainExtent.width, swapChainExtent.height, 
		depthFormat, 
		VK_IMAGE_TILING_OPTIMAL,
		VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT, 
		VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, 
		depthImage, depthImageMemory);
		
	depthImageView = createImageView(
		depthImage, depthFormat, VK_IMAGE_ASPECT_DEPTH_BIT);
	
	// 手动显式转化layout （实际上并不需要，renderPass会自动搞定，这里只是演示）
	transitionImageLayout(depthImage, depthFormat, 
		VK_IMAGE_LAYOUT_UNDEFINED, 
		VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL);	
}

// 更新这个函数，增加一个参数，可以指定 aspectFlags (这个可有理解为 image view 关注 image 的部分， 我们这里和用途一致)
VkImageView createImageView(VkImage image, VkFormat format, VkImageAspectFlags aspectFlags) {
    ...
    viewInfo.subresourceRange.aspectMask = aspectFlags;
    ...
}

// 为了支持显示转化格式，我们需要调整一下。
// 增加了新的barrier，并且使用了 barrier 的 aspectMask
void transitionImageLayout(VkImage image, VkFormat format,
						 VkImageLayout oldLayout, VkImageLayout newLayout) {
	...
	if (newLayout == VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL) {
	    barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT;
	
	    if (hasStencilComponent(format)) {
	        barrier.subresourceRange.aspectMask |= VK_IMAGE_ASPECT_STENCIL_BIT;
	    }
	} else {
	    barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
	}
	

	if (oldLayout == VK_IMAGE_LAYOUT_UNDEFINED && newLayout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL) {
	    barrier.srcAccessMask = 0;
	    barrier.dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
	
	    sourceStage = VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT;
	    destinationStage = VK_PIPELINE_STAGE_TRANSFER_BIT;
	} else if (oldLayout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL && newLayout == VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL) {
	    barrier.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
	    barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;
	
	    sourceStage = VK_PIPELINE_STAGE_TRANSFER_BIT;
	    destinationStage = VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT;
	} else if (oldLayout == VK_IMAGE_LAYOUT_UNDEFINED && newLayout == VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL) {
	    barrier.srcAccessMask = 0;
	    barrier.dstAccessMask = VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;
	
	    sourceStage = VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT;
	    destinationStage = VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
	} else {
	    throw std::invalid_argument("unsupported layout transition!");
	}


    vkCmdPipelineBarrier(commandBuffer, sourceStage, destinationStage, 0, 0,
                         nullptr, 0, nullptr, 1, &barrier);

    endSingleTimeCommands(commandBuffer);
}
```

这里我们编写了显示的布局转换操作。

补充，AI在这里应该没有掌握具体的细节。去调研细节也比较费时间。暂时我们根据AI给出的描述，做一定补充。这里 ImageBarrier 本身包含了到达 dstStage 时，需要完成 layout转化。但并没有说明在指定这个barrier的时候就要”立即“执行转化。

这里，barrier的理解，当 dstStage 和 dstAccessMask 要开始的时候：
- 确保 srcStage, srcAccessMask 完成
- 确保 layout 转化完成 （barrier内部的 newLayout 和 oldLayout字段定义了这个行为）

所以，布局转化操作，实际是将 这个操作 定义在了一个 管线的 时间区间之内（当然触发条件时dst的阶段和mask能达到）。

## Render pass (类比: 预留"槽位")
上面我们定义好了 Depth Image 和 view 。接着我们要在渲染管线中 `createRenderPass`，添加这些资源：
```cpp
// VkAttachmentDescription 结构体，用于描述深度附件。
VkAttachmentDescription depthAttachment{};
depthAttachment.format = findDepthFormat();
depthAttachment.samples = VK_SAMPLE_COUNT_1_BIT;
// **加载操作 (Load Op):** 在渲染开始时，如何处理深度附件中的现有数据。
// VK_ATTACHMENT_LOAD_OP_CLEAR 表示在渲染此 Render Pass 时，附件中的所有像素将被清除为预设值 (通常为 1.0f，表示最远)。
depthAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_CLEAR;
// **存储操作 (Store Op):** 在渲染结束时，如何处理深度附件中的数据。
// VK_ATTACHMENT_STORE_OP_DONT_CARE 表示渲染完成后，深度数据的内容不需要被保留或写回内存。
depthAttachment.storeOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
depthAttachment.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
depthAttachment.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
depthAttachment.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
depthAttachment.finalLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

// 方便subpass引用附件。
VkAttachmentReference depthAttachmentRef{};
depthAttachmentRef.attachment = 1;
depthAttachmentRef.layout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;

// subpass中新增depth附件
VkSubpassDescription subpass{};
subpass.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
subpass.colorAttachmentCount = 1;
subpass.pColorAttachments = &colorAttachmentRef;
subpass.pDepthStencilAttachment = &depthAttachmentRef;

...

// 修改dependency，上一个subpass需要完成，才进入下一个subpass的阶段。
// 我们的是 external 依赖，因此严格来说是上一帧的depth写入完成，下一帧才能写入。
dependency.srcStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT;
dependency.srcAccessMask = VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;
dependency.dstStageMask = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT | VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT;
dependency.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;

// RenderPass中要包含原本附件内容。 （subpass则是用引用的方式）
std::array<VkAttachmentDescription, 2> attachments = {colorAttachment, depthAttachment};
VkRenderPassCreateInfo renderPassInfo{};
renderPassInfo.sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO;
renderPassInfo.attachmentCount = static_cast<uint32_t>(attachments.size());
renderPassInfo.pAttachments = attachments.data();
renderPassInfo.subpassCount = 1;
renderPassInfo.pSubpasses = &subpass;
renderPassInfo.dependencyCount = 1;
renderPassInfo.pDependencies = &dependency;
```

### Clear values
因为我们有多个 clear op的定义，因此我们需要多个clear value。这个动作在绘制的时候指定，而不是创建的时候，所以，在 `recorCommandBuffer` 中修改：
```cpp
std::array<VkClearValue, 2> clearValues{};
clearValues[0].color = {{0.0f, 0.0f, 0.0f, 1.0f}};
clearValues[1].depthStencil = {1.0f, 0};

renderPassInfo.clearValueCount = static_cast<uint32_t>(clearValues.size());
renderPassInfo.pClearValues = clearValues.data();
```
## Framebuffer (类比: 填充"槽位")
那么渲染需要的framebuffer，显然要把 depth image信息作为附件添加进去。修改 `createFramebuffers` 函数
```cpp
std::array<VkImageView, 2> attachments = {
    swapChainImageViews[i],
    depthImageView
};

VkFramebufferCreateInfo framebufferInfo{};
framebufferInfo.sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO;
framebufferInfo.renderPass = renderPass;
framebufferInfo.attachmentCount = static_cast<uint32_t>(attachments.size());
framebufferInfo.pAttachments = attachments.data();
framebufferInfo.width = swapChainExtent.width;
framebufferInfo.height = swapChainExtent.height;
framebufferInfo.layers = 1;
```

确保 framebuffer的创建在 depth resource之后：
```cpp
void initVulkan() {
    ...
    createDepthResources();
    createFramebuffers();
    ...
}
```


## Pipeline中开启Depth test
修改 `createGraphicsPipeline`
```cpp
VkPipelineDepthStencilStateCreateInfo depthStencil{};
depthStencil.sType = VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO;
// 测试fragment是否通过
depthStencil.depthTestEnable = VK_TRUE;
// 测试通过后，是否写入depth
depthStencil.depthWriteEnable = VK_TRUE;

// 更小的深度值可以写入
depthStencil.depthCompareOp = VK_COMPARE_OP_LESS;

// 特殊能力，仅保留depth在某个区间的fragment 进行测试。
depthStencil.depthBoundsTestEnable = VK_FALSE;
depthStencil.minDepthBounds = 0.0f; // Optional
depthStencil.maxDepthBounds = 1.0f; // Optional

...
pipelineInfo.pDepthStencilState = &depthStencil;

```

Depth Bounds Test 常见用途：
- 延迟渲染中某个深度切片
- 特殊遮罩 / debug pass
大多数引擎根本不用（包括 Unreal 默认）


## 显示效果

![[Vulkan入门05-Depth buffering-显示效果-01.png]]

## 处理window resize
当resize发生的时候，我们需要重新创建 depthResouce；同时，销毁资源也应该和swapChain一起销毁。

```cpp
void recreateSwapChain() {
    int width = 0, height = 0;
    while (width == 0 || height == 0) {
        glfwGetFramebufferSize(window, &width, &height);
        glfwWaitEvents();
    }

    vkDeviceWaitIdle(device);

    cleanupSwapChain();

    createSwapChain();
    createImageViews();
    createDepthResources();
    createFramebuffers();
}

void cleanupSwapChain() {
    vkDestroyImageView(device, depthImageView, nullptr);
    vkDestroyImage(device, depthImage, nullptr);
    vkFreeMemory(device, depthImageMemory, nullptr);

    ...
}
```

## 疑惑点
### 为什么1个depth buffer就够了？

https://stackoverflow.com/questions/62371266/why-is-a-single-depth-buffer-sufficient-for-this-vulkan-swapchain-render-loop

- 这个帖子给出了一个方案，避免了 depth buffer写入时的race condition。却没有解决 **渲染语义上的正确性**。
	- **适用范围有限**
		- 修复只在 **场景静态或 camera 不动** 的情况下安全
		- 对于动态场景、多摄像机、多视角渲染、快速移动等情况，结果会出错

**为什么 per-frame depth buffer 才是安全的**
- 为每个 frame / swap chain image 使用 **独立 depth buffer** 可以保证：
    1. 内存访问安全（GPU 不会同时写同一 buffer）
    2. 渲染语义正确（每帧独立深度数据，深度测试结果只依赖当前帧 geometry）
- MAX_FRAMES_IN_FLIGHT > 1 时，每帧都可以并行渲染，不会互相干扰

个人想法：最好的做法还是不要节省这一点 depth buffer的存储空间了。老老实实根据frame数目，创建多个即可。