---
title: Vulkan入门08-Multisampling
date: 2025-12-09T12:45:58+08:00
tags:
  - vulkan
  - msaa
  - sample-shading
draft: false
---
![[Vulkan入门08-Multisampling-1765255768161.png|636x338]]
![[Vulkan入门08-Multisampling-1765255780014.png|636x331]]

多重采样(MSAA)也是一个常用的采样技术。对比上一节的mipmap：
- **MSAA ：减几何锯齿**  
- **Mip + Filter ： 减纹理 aliasing**

本节主要讲如何vulkan中开启MSAA。具体步骤总结：
1. 查询设备，获取开启多重采样的样本频率。
2. 创建支持multisample的Image。并设为渲染目标。
3. 把屏幕作为另一个 color attachement，设定为 resolveAttachment （修改renderPass/frameBuffer创建）
4. 管线中开启msaa（修改 pipeline创建）

<!--more-->

# 获取设备可采样数
不同设备的MSAA样本数有差别。因此我们写一个辅助函数来获取设备的最大可以开启的采样数：
```cpp
VkSampleCountFlagBits getMaxUsableSampleCount() {
    VkPhysicalDeviceProperties physicalDeviceProperties;
    vkGetPhysicalDeviceProperties(physicalDevice, &physicalDeviceProperties);

    VkSampleCountFlags counts = physicalDeviceProperties.limits.framebufferColorSampleCounts & physicalDeviceProperties.limits.framebufferDepthSampleCounts;
    if (counts & VK_SAMPLE_COUNT_64_BIT) { return VK_SAMPLE_COUNT_64_BIT; }
    if (counts & VK_SAMPLE_COUNT_32_BIT) { return VK_SAMPLE_COUNT_32_BIT; }
    if (counts & VK_SAMPLE_COUNT_16_BIT) { return VK_SAMPLE_COUNT_16_BIT; }
    if (counts & VK_SAMPLE_COUNT_8_BIT) { return VK_SAMPLE_COUNT_8_BIT; }
    if (counts & VK_SAMPLE_COUNT_4_BIT) { return VK_SAMPLE_COUNT_4_BIT; }
    if (counts & VK_SAMPLE_COUNT_2_BIT) { return VK_SAMPLE_COUNT_2_BIT; }

    return VK_SAMPLE_COUNT_1_BIT;
}
...
VkSampleCountFlagBits msaaSamples = VK_SAMPLE_COUNT_1_BIT;
...
void pickPhysicalDevice() {
    ...
    for (const auto& device : devices) {
        if (isDeviceSuitable(device)) {
            physicalDevice = device;
            msaaSamples = getMaxUsableSampleCount();
            break;
        }
    }
    ...
}
```

# 设置渲染目标
MSAA中，每个像素都在离屏(offscreen)的buffer中进行采样，随后再被渲染到屏幕上。这个新的buffer和常规我们渲染的image不同，它们有能力针对每个像素保存多个样本。当一个 mutilsampled buffer创建后，它必须解析（resolve）到默认帧缓冲区（默认帧缓冲区每个像素只存储一个样本） （补充说明：解析过程： **从多个样本计算一个颜色**，然后存入 framebuffer。）


使用MSAA的时候，我们首先要渲染到我们创建好的多采样buffer中，随后再从这个buffer，resolve到最终的Image的buffer中。


```cpp
// 用来渲染的target
VkImage colorImage;
VkDeviceMemory colorImageMemory;
VkImageView colorImageView;

// 调整创建Image函数，指定 sample数量
void createImage(uint32_t width, uint32_t height, uint32_t mipLevels, VkSampleCountFlagBits numSamples, VkFormat format, VkImageTiling tiling, VkImageUsageFlags usage, VkMemoryPropertyFlags properties, VkImage& image, VkDeviceMemory& imageMemory) {
    ...
    imageInfo.samples = numSamples;
    ...
    
// 调整相关代码
...
createImage(texWidth, texHeight, mipLevels, VK_SAMPLE_COUNT_1_BIT, VK_FORMAT_R8G8B8A8_SRGB, VK_IMAGE_TILING_OPTIMAL, VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, textureImage, textureImageMemory);
...
// 深度缓冲，也需要适配MSAA采样。
createImage(swapChainExtent.width, swapChainExtent.height, 1, msaaSamples, depthFormat, VK_IMAGE_TILING_OPTIMAL, VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, depthImage, depthImageMemory)

// 创建渲染目标
void createColorResources() {
    VkFormat colorFormat = swapChainImageFormat;

    createImage(swapChainExtent.width, swapChainExtent.height, 1, msaaSamples, colorFormat, VK_IMAGE_TILING_OPTIMAL, VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT | VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT, VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT, colorImage, colorImageMemory);
    colorImageView = createImageView(colorImage, colorFormat, VK_IMAGE_ASPECT_COLOR_BIT, 1);
}

void initVulkan() {
    ...
    createColorResources();
    createDepthResources();
    ...
}

// 清理/重建数据
void cleanupSwapChain() {
    vkDestroyImageView(device, colorImageView, nullptr);
    vkDestroyImage(device, colorImage, nullptr);
    vkFreeMemory(device, colorImageMemory, nullptr);
    ...
}
void recreateSwapChain() {
    ...
    createImageViews();
    createColorResources();
    createDepthResources();
    ...
}

// 修改渲染流程：attachment（"槽位"）配置修改
void createRenderPass() {
    ...
    colorAttachment.samples = msaaSamples;
    colorAttachment.finalLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
    ...
    depthAttachment.samples = msaaSamples;
    ...
    
// 修改渲染数据
void createFramebuffers() {
        ...
        std::array<VkImageView, 3> attachments = {
            colorImageView, // 这里是渲染目标
            depthImageView,
            // 这块会最后resolve上面的渲染结果，因此 createRenderPass 还有需要修改的地方，后面会讲
            swapChainImageViews[i]  
        };
        ...
}

// 渲染管线中开启MSAA
void createGraphicsPipeline() {
    ...
    multisampling.rasterizationSamples = msaaSamples;
    ...
}
```

## 添加新Color Attachments
现在渲染目标到了一个显存的Image中，我们最终需要渲染到屏幕上。因此MSAA还需要配置一个用来resolve的attachment

```cpp
void createRenderPass() {
    ...
    VkAttachmentDescription colorAttachmentResolve{};
    colorAttachmentResolve.format = swapChainImageFormat;
    colorAttachmentResolve.samples = VK_SAMPLE_COUNT_1_BIT;
    colorAttachmentResolve.loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    colorAttachmentResolve.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
    colorAttachmentResolve.stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
    colorAttachmentResolve.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
    colorAttachmentResolve.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
    colorAttachmentResolve.finalLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
    ...
    VkAttachmentReference colorAttachmentResolveRef{};
    colorAttachmentResolveRef.attachment = 2;
    colorAttachmentResolveRef.layout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
    ...
    subpass.pResolveAttachments = &colorAttachmentResolveRef;
    ...
    // 这里是读取前，保证写入；不过和depth buffer的共享使用一样，也有一些问题，可以参见depth buffer笔记中最后一章
    dependency.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;
    ...
    std::array<VkAttachmentDescription, 3> attachments = {colorAttachment, depthAttachment, colorAttachmentResolve};
    ...    
```

# 渲染结果

![[Vulkan入门08-Multisampling-1765268690445.png]]

更细节对比：
![[Vulkan入门08-Multisampling-1765268839864.png]]

# 质量提升
我们当前的 MSAA 实现存在一些局限性，可能会影响在更精细场景中输出图像的质量。例如，我们目前尚未解决由shader aliasing引起的潜在问题，即 MSAA 仅平滑几何体的边缘，而不会平滑内部填充。这可能导致在屏幕上渲染出平滑的多边形，但若纹理包含高对比度颜色，其外观仍会显得 aliased。解决这个问题的一种方法是通过启用 Sample Shading 来进一步提升图像质量，尽管这会带来额外的性能开销：

```cpp
void createLogicalDevice() {
    ...
    deviceFeatures.sampleRateShading = VK_TRUE; // enable sample shading feature for the device
    ...
}

void createGraphicsPipeline() {
    ...
    multisampling.sampleShadingEnable = VK_TRUE; // enable sample shading in the pipeline
    multisampling.minSampleShading = .2f; // min fraction for sample shading; closer to one is smoother
    ...
}
```


**传统MSAA（Multisample Anti-Aliasing）**：
1. 对每个像素在 **采样位置**（sample points）进行深度/模板测试
2. 执行fragment shader 1次，得到fragment的颜色。
3. 在所有 sample 上做 resolve：然后根据采样命中率将fragment颜色和背景融合。

优缺点：
- 优点：减少锯齿，同时 **shader 执行次数少** → 性能较好
- 缺点：如果像素内部有多个不同的材质/纹理，需要对每个 sample 的颜色单独计算，MSAA 不能做到 ： 出现 “shader aliasing”

**开启 Sample Shading**
- 对每个 sample 而不是每个像素执行 fragment shader
- 不再只计算一次 fragment color，而是对 MSAA 中的每个 sample 独立计算颜色


这块的效果目前的场景很难对比出来。不给图例了。