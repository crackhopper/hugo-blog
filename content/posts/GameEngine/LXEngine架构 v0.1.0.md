---
title: LXEngine架构 v0.1.0
date: 2026-04-01T12:54:09+08:00
tags: []
draft: false
---

![[LXEngine架构 v0.1.0-intro-01.png]]

本文主要讲解我的渲染器项目 LXEngine：从 vulkan tutorial 出发
- 理解和识别里面的概念
- 以面向对象和领域驱动的方式

彻底重构，建立了引擎的四大核心模块。


<!--more-->

# v0.1.0 说明

核心目标：
- 分层架构：
	- core：提供渲染器核心接口。方便构建渲染场景。同时定义backend、infra层需要实现的接口。该层不依赖任何其他层（利用DI，依赖倒置）。
	- backend：实现core层的相关接口。封装图形API调用。依赖core层。
	- infra：实现外部模块接入。包括GUI、Window等。依赖core层，实现core层接口。
	- test：组合core，backend，infra。在具体场景下完成渲染任务。内部包含集成测试。
- 灵活的可扩展性：
	- backend层可以后续接入其他图形api
	- infra层中，GUI、Window模块均可以替换。同时如果有超出标准库的系统调用也会提供对应的系统调用封装。方便未来跨多系统。
- 核心概念实现：
	- 后端核心组件：device，resource manager, descriptor manager/allocator, pipeline
	- 业务层抽象：camera，light，mesh，material（初步的材质系统）
- AI工作流：
	- 架构设计和细节bug修复，主要由我个人调研和整理。（使用chat工具）
	- Agent开发：使用OpenSpec作为Agent协同的工作流。负责解决较为繁琐的细节。以及协同debug。

这个版本仅仅是第一个面向对象重构的版本。因此核心目标达成后，主要的测试是可以正常渲染出三角形。
# Core层
## 网格数据（Mesh）
网格数据最显然的两个组成部分：
- **顶点缓冲区** Vertex Buffer
- **索引缓冲区** Index Buffer

**网格（Mesh）：** 定义了物体的**形状**和**空间属性**（哪里是顶点，哪里是表面）。

### 顶点数据和顶点格式
目前预定义了若干种顶点格式。

```cpp
enum class VertexFormat {
  Pos,
  PosColor,
  PosUV,
  NormalTangent,
  BoneWeight,
  PosNormalUvBone,
};
```
- `PosNormalUvBone` ：这个是目前用来跑通MVP流程使用的格式。
- `NormalTangent` , `BoneWeight` 格式则是为了支持 **多buffer绑定 (De-Interleaved)**


## 骨骼数据(Skeleton)
动画播放，是一个游戏引擎中必不可少的环节。因此我们在架构初期就引入了骨骼的结构。

每个骨骼节点：
```cpp
struct Bone {
  std::string name;
  int parentIndex;
  Vec3f position;
  Quatf rotation;
  Vec3f scale = Vec3f(1, 1, 1);
};
```

骨骼可以理解成对顶点位置局部影响。

## 材质（Material）
**材质（Material）：** 定义了表面的**光学特性**（纹理图、法线）。简单来说，包含：
- **Shader：** 通常是材质的一部分，是材质的**数学实现**。（如何用反射率、粗糙度等等计算出光照后的颜色）
- **Shader运行时参数**：数值、向量、纹理图、或者特殊的buffer等等。这些参数都是shader的输入。

材质中最细粒度的资源，我们组织成符合下面接口模式的实例：
```cpp
class IRenderResource {
public:
  virtual ~IRenderResource() = default;

  virtual ResourcePassFlag getPassFlag() const = 0;
  virtual ResourceType getType() const = 0;
  virtual const void *getRawData() const = 0;
  virtual u32 getByteSize() const = 0;

  virtual PipelineSlotId getPipelineSlotId() const {
    return PipelineSlotId::None;
  }

  // 资源的唯一标识符，用于在渲染管线中查找资源
  // 直接使用地址作为句柄
  void *getResourceHandle() const { return (void *)this; }

  bool isDirty() const { return isDirty_; }
  void setDirty() { isDirty_ = true; }
  void clearDirty() { isDirty_ = false; }

private:
  bool isDirty_ = false;
};
```

这个接口定义，对应到backend层，会唯一的对应相关的GPU资源。

由于材质定义了管线中shader的输入参数，因此我们在渲染的时候，切换材质就必然要重新绑定和刷新pipeline上的槽位（descriptor）。因此，多个材质一定会带来多个drawcall。


### 着色器(Shader)
着色器是材质的数学表现。我们初期的重构，主要基于Blinn-Phong模型，完成项目跑通。同时为了方便未来扩展 PBR， shadow 等，做好扩展的能力。

在Shader中，通常可以通过开关来指定渲染的行为。比如是否开启光照等等。这种能力我们在初期版本中，主要靠 材质中的参数（通常是UBO）来定义。

核心代码：

vertex shader
```glsl
mat4 finalModel = object.model * skinMatrix;
vec4 worldPos = finalModel * vec4(inPosition, 1.0);

gl_Position = camera.proj * camera.view * worldPos;
// NDC_coord = proj * view * model (skin) * pos
vWorldPos = worldPos.xyz;
vUV = inUV;

// 2. TBN 矩阵构建 (世界空间)
// 使用法线矩阵处理非统一缩放
mat3 normalMatrix = mat3(transpose(inverse(finalModel)));

vec3 N = normalize(normalMatrix * inNormal);
vec3 T = normalize(normalMatrix * inTangent.xyz);
// 重建副切线 B
vec3 B = normalize(cross(N, T) * inTangent.w);
```

fragment shader
```glsl
vec3 baseCol = material.baseColor;
if (material.enableAlbedo == 1) {
	baseCol *= texture(albedoMap, vUV).rgb;
}
vec3 ambient = baseCol * 0.1; // 基础环境光项
vec3 finalColor = ambient;

if (object.enableLighting == 1) {
	vec3 L = normalize(-sceneLight.dir.xyz);
	vec3 V = normalize(camera.eyePos - vWorldPos);
	
	// --- 漫反射 (Diffuse) ---
	float diff = max(dot(N, L), 0.0);
	vec3 diffuse = diff * sceneLight.color.rgb;

	// --- 高光 (Specular) ---
	// 使用强度系数代替开关，0.0 自动抵消计算结果
	vec3 H = normalize(L + V); 
	float spec = pow(max(dot(N, H), 0.0), material.shininess);
	vec3 specular = spec * sceneLight.color.rgb * material.specularIntensity;

	// 最终叠加：(物体色 * 漫反射) + 镜面反射
	finalColor += (baseCol * diffuse) + specular;
}
```

## 相机（Camera）
Camera 定义了观察者的视角，主要将 3D 世界坐标转换到 2D 屏幕坐标。这个整体概念比较简单清晰，为了配套实现相机操作，我也专门开发了对应的数学库。

- **核心数学：**
    - **View Matrix (视图矩阵):** 处理相机的位移和旋转（通常用 LookAt 矩阵表示）。
    - **Projection Matrix (投影矩阵):** 处理透视或正交投影，定义视锥体（Frustum）。
        
Camera 提供全局的矩阵供 Shader 使用（主要是Vertex Shader）。它还负责**视锥剔除 (Frustum Culling)**，即不在相机视野内的物体不提交给 GPU。

此外，相机通常包括透视和正交相机两种类型的相机。

相机的结构（伪代码）：
```cpp
struct CameraUBO {
    // 基础矩阵
    Mat4f view;           // 64 bytes
    Mat4 projection;     // 64 bytes
    Mat4 viewProjection; // 64 bytes (VP 矩阵，顶点着色器最常用)

    // 相机空间信息
    Vec4 position;       // 16 bytes (xyz 是坐标, w 通常填充 1.0f)
    
    // 屏幕/裁剪信息
    Vec4 nearFarAspect;  // x: near, y: far, z: aspect, w: unused
    
    // (可选) 逆矩阵：用于延迟渲染中从深度还原世界坐标
    Mat4 invView;        // 64 bytes
    Mat4 invProjection;  // 64 bytes
};
```
## 光源（Light）
光源：渲染的能量来源。

常见类型：
- Directional Light (平行光): 模拟太阳，只有方向，没有衰减。
- Point Light (点光源): 向四周发散，有距离衰减。
- Spot Light (聚光灯): 锥形照射范围。

光源的结构（伪代码）：
```cpp
struct LightData {
    Vec4 position;  // w 为类型或开关
    Vec4 color;     // w 为强度 Intensity
    Vec4 direction; // w 为聚光灯角度等
    // 其他属性如衰减因子...
};
```

目前我们仅支持了单光源。

对于多光源，我们将光源数据用SSBO来存储。并开启g-buffer pass，利用延迟渲染来处理。
## ObjectInfo(Push Constant)
针对每个具体的物体（Object），我们都有对应的model matrix。这个数据通常我们放到 Push Constant 中来方便shader读取。

```cpp
struct alignas(16) ObjectInfoInternal {
  Mat4f mat = Mat4f::identity();
};
```
## RenderableObject
针对每个可渲染的对象，内部主要由下面四个组成：
- mesh
- material
- skeleton
- info

## 场景(Scene)
场景就是整个渲染器要渲染内容的容器。暂时我仅实现了空的类，并没有展开实现场景。而我们的渲染器也不会过于深度的关心场景的能力。（场景能力完善，实际上意味着向引擎迈进）

场景和场景里的对象，更多的是逻辑层方便用户使用。

## Backend接口相关
### RenderingItem (最小渲染单元)
这个是渲染的最小单元。实际会形成一个drawcall。目前我仅实现了基础的版本。

目前我们的RenderingItem仅能对一个 RenderableObject进行渲染。其结构较为简单：

```cpp
struct RenderingItem {
  ShaderPtr shaderInfo;

  ObjectInfoPtr objectInfo;
  VertexFormat vertexFormat;
  IRenderResourcePtr vertexBuffer;
  IRenderResourcePtr indexBuffer;
  
  std::vector<IRenderResourcePtr> descriptorResources; // 材质 + skeleton 等资源
  
  ResourcePassFlag passMask;
};
```

### IRenderResource(GPU资源接口)
我们之前在material中提到过。这个类会对应具体gpu设备上的一个资源（概念上）。

```cpp
class IRenderResource {
public:
  virtual ~IRenderResource() = default;

  virtual ResourcePassFlag getPassFlag() const = 0;
  virtual ResourceType getType() const = 0;
  virtual const void *getRawData() const = 0;
  virtual u32 getByteSize() const = 0;

  virtual PipelineSlotId getPipelineSlotId() const {
    return PipelineSlotId::None;
  }

  // 资源的唯一标识符，用于在渲染管线中查找资源
  // 直接使用地址作为句柄
  void *getResourceHandle() const { return (void *)this; }

  bool isDirty() const { return isDirty_; }
  void setDirty() { isDirty_ = true; }
  void clearDirty() { isDirty_ = false; }

private:
  bool isDirty_ = false;
};
```

### Renderer(渲染器接口)
后端需要主要实现的类。后端主要的导出类。
```cpp
class Renderer {
public:
  virtual ~Renderer() = default;

  // 初始化 GPU 设备 / context
  virtual void initialize(WindowPtr window, const char *appName) = 0;

  // 清理 GPU 资源
  virtual void shutdown() = 0;

  // 初始化，根据场景创建后端资源。
  virtual void initScene(ScenePtr scene) = 0;

  // --- 每帧的动作
  // 逻辑计算（力学模拟，通常比较简单，刚体力学为主） + 上传数据
  virtual void uploadData() = 0;
  // 绘制渲染对象：录制命令+提交
  virtual void draw() = 0;
  
};
```

## Infra接口相关
### Window(窗口接口)
为了让我们的系统可以适配各种窗口系统。我们在core层抽象了Window类。

```cpp
class Window {
public:
  static void Initialize(); // 初始化窗口系统

protected:
  Window() = default;
  ~Window() = default;

public:
  virtual int getWidth() const = 0;
  virtual int getHeight() const = 0;
  virtual void updateSize(bool* closed, int *width, int *height) = 0;
  virtual void getRequiredExtensions(std::vector<const char *> &extensions) const = 0;

  virtual WindowGraphicsHandle createGraphicsHandle(GraphicsAPI api,
                                     GraphicsInstanceHandle instance) const = 0;

  // 辅助销毁方法（因为 Surface 必须在 Instance 销毁前销毁）
  virtual void destroyGraphicsHandle(GraphicsAPI api, GraphicsInstanceHandle instance,
                                     WindowGraphicsHandle handle) const = 0;

  virtual void onClose(std::function<void()> cb) = 0;
  virtual bool shouldClose() = 0;
};
```

## 数学库(math)
实现了简单的数学库。未来如果接入第三方库，那么则可以从数学库的实现上进行重构（可以考虑引入CMAKE开关）。
- `vec` ：向量
- `mat` ：矩阵，同时支持lookat操作。
- `quat` ： 4元数。常规旋转相关的计算均支持。
# Backend层

## VulkanRenderer
主要负责组合和调度 `VulkanDetails` 中的各种组件。负责 ：
- 初始化 `device`
- 初始化 `command buffer manager`
- 初始化 `swapchain`
- 初始化 `resource manager`

此外，目前还做了部分syncObject的管理。

## VulkanDetails
主要分5个子模块：
- device
- resources
- descriptors
- render_objects
- pipeline
### device
主要封装了下面一些全局handle的创建
- instance
- device: (phyical, logical)
- queue
### resources
包含了需要在gpu上创建的资源，通常这些资源是在cpu层从硬盘上加载的。主要是：
- buffer
- texture
- shader

同时提供了一个 `resource_manager` 负责这些资源的管理（创建、释放、上传、下载）。

### descriptors
descriptor，可以理解为 **shader参数** 的 **绑定协议** （或者理解为操作器） 。用来连接 cpu 侧动态资源（比如各种矩阵），和 shader参数 （uniform，SSBO） 。是这个连接概念的抽象。

提供了 `VulkanDescriptorManager` ，管理 descriptor set 相关资源。
- 封装了 descriptorPool ，以及相关创建pool、销毁pool的方法。（预设了较大的poolsize）
- 分帧处理，每帧有独立的pool。
- 复用回收 descriptorSet 对象。根据 layout 持有可用的对象。
- 提供封装的 `DescriptorSet` ，支持RAII，调用manager来管理释放动作。

我们这里的descriptor管理，实现了 **逐帧回收** , **descriptor set复用** 。
### render_objects
跟渲染输出相关的类和方法：
- `VulkanFrameBuffer` : 渲染pass的目标，是一个framebuffer对象。framebuffer对象通常关联多个attachment（这些都是具体的图像对象，即 ImageView + Image）
- `VulkanRenderPass` : 渲染相关的描述性配置，包含framebuffer，格式等等。是对pipeline的补充。（pipeline不仅仅可以用作渲染，更多的可以理解为一套可执行的模块；而renderpass补充了渲染相关的配置）
- `VulkanSwapchain` ：屏幕输出的抽象。这里封装了多帧对应的Image+ImageView，以及提交图像相关的命令，和所有在提交时处理的syncObjects

### pipeline
Pipeline 是 GPU 执行逻辑的**全状态快照**。它将 Shader 代码、固定管线状态（如深度测试、混合模式）以及资源布局（DescriptorSet Layout）绑定为一个不可变的、预编译的可执行实体。

可以简单理解：由 大量的状态参数(各种state) + slot（descriptor） + shader程序，构成的一个可执行的单元。

- `PipelineSlotDetails` : 主要定义了一个 pipeline 和 shader 的接口。即 descriptor layout 的描述性的数据（用来创建 descriptor set layout）。“槽位”，这个词是非常贴切的描述，槽位的数据则是在drawcall前，具体由renderer从renderItem中读取并更新到gpu上。
- `VulkanPipeline` : 对pipeline的封装，包含了复杂的创建流程（各种state创建、vertex，input assembly，descriptor set layout等等）。

**硬编码 `VkPipelineBlinnPhong`**

目前渲染器架构这块简化，硬编码创建了 VkPipelineBlinnPhong 的管线。尤其是对 vertex layout, input assembly 等等，写死为主。
# Infra层
## WindowImpl
支持了 `SDL` 和 `GLFW` 两种窗口库。

# v0.1.1
本阶段的核心目标是**去硬编码化**，建立一套可扩展的渲染编排系统，并实现首个多 Pass 逻辑：阴影映射 (Shadow Mapping)。
- [ ] 渲染对象重构与类型擦除 (Type Erasure)
	- **去模板化 Mesh**：将原有的 Mesh 模板类重构为通用类，对 `VertexBuffer` 进行类型擦除。通过 `VertexLayout` 字段动态描述顶点结构，提升了材质系统的灵活性。
	- **参数化 Pipeline 构建**：废弃了 `VkPipelineBlinnPhong` 等硬编码子类，引入 `PipelineCacheManager`。现在，Pipeline 的创建完全依赖于由 Mesh 布局、Material 属性及 RenderPass 状态组合生成的 `PipelineKey`。
- [ ] 渲染编排：RenderQueue 与 FrameGraph
	- **RenderQueue (渲染队列)**：引入渲染队列聚合单个 RenderTarget 中的所有 `RenderItem`。支持基于材质、深度或不透明度进行排序，以优化状态切换开销（State Change Optimization）。
	- **FrameGraph (静态版)**：
	    - **任务编排**：初步实现 FrameGraph 逻辑，用于编排不同 RenderPass 的执行顺序。
	    - **静态依赖管理**：通过显式声明 Pass 间的依赖（如 Forward Pass 依赖 Shadow Pass 的深度纹理），自动管理执行流。
- [ ] 同步机制与内存屏障 (Synchronization)
	- **显式同步**：针对 Vulkan 繁琐的同步细节，建立了一套基于 `Fence` 和 `Semaphore` 的管理机制。
	- **Image Memory Barrier**：手动实现 Pass 间的图像布局转换（Layout Transition）。重点解决了 Shadow Pass 写入到 Forward Pass 读取之间的同步痛点，确保数据一致性。
- [ ] 功能实现：阴影映射 (Shadow Mapping)
	- **多 Pass 协同**：在 Core 层正式引入 `Shadow Pass` 和 `Forward Pass`。
	- **Shader 扩展**：开发配套的 Shadow Shader，支持基础的深度写入与采样。
	- **场景验证**：在自研架构下成功渲染包含 **地面 + 灯光 + 动态正方体** 的实时阴影场景。
## 细节和注意点
### 顶点格式
- 顶点location有限，通常16个。
- 多个顶点buffer，需要多个 binding。那么location具体绑定哪个binding的第几个offset， 就需要 VertexLayout 来描述。(因此支持 *多vertex buffer* 优先于 *Custom* )
- 如果需要支持instance draw(减少drawcall，提升效率)，那么 layout中还需要整体指定inputRate 
- 更进一步 VertexLayout 如果不想手动指定，需要支持 `SPIRV-Cross` 工具来通过反射，自动绑定生成 layout。
- **顶点相关信息，影响 `pipeline` 构建 PSO(Pipeline State Object)**

### 索引拓扑
- 内部应该包含索引拓扑，尚未实现，默认`TRIANGLE_LIST`即每3个点一个三角形

其他拓扑类型呢？

|**数据特征**|**推荐封装类**|**内部拓扑结构**|
|---|---|---|
|**持久的、复杂的模型**|`Mesh` / `Model`|`TRIANGLE_LIST`|
|**每帧都在变的调试线**|`ImmediateModeRenderer`|`LINE_LIST`|
|**大规模简单的点/小碎片**|`ParticleSystem`|`POINT_LIST`|
|**连续的路径/轨迹**|`TrailRenderer` / `Ribbon`|`TRIANGLE_STRIP` (比 Line Strip 更好看，有宽度)|

注意，这里面 `LINE_LIST` 和 `POINT_LIST` 都没有面积，如何光栅化插值呢？
- `LINE_LIST` ：原理上，据实际线宽度，激活所有经过的像素。随后用像素中心点向线段做垂直投影，接着用投影点来计算插值。（通常是 **Bresenham 算法** 或其变体）
- `POINT_LIST` ：原理上，不插值，需要自己在fs中算
	- `gl_PointSize` 开启：则根据这个大小选定矩形，确定像素是否激活。方块内部可以用 `gl_PonitCoord` 的纹理坐标。
	- `gl_PointSize` 不开启：仅有一个像素被激活。
- 此外，可以用MeshShader动态生成图元（现代管线的做法）。

### Shader改进
- 提供变种能力。ShaderVariants，定义一些字符串，作为编译时候的宏开关。
- 使用预编译宏，集成 `shaderc` 。
### Material改进
- **管线状态参数**：
	- 光栅化状态（Rasterization State)： Cull Mode、Fill Mode
	- 混合状态（Blend State)：Opaque, Transparent
	- 深度/模板状态(Depth/Stencil State) : 是否开启Depth test 等。
- **属性描述** ： PropertySchema ，创建descriptor set layout的数据来源。
- **Pass选择** ：通常会通过一个 tag/enum 的方式来定义。不同的pass决定了渲染pipeline外部的组合动作。（forward pass、 shadow pass、gbuffer/lighting pass ) 等等。

**材质模板 v.s. 材质实例**
- 材质模板：定义了约束、代码。主要和shader绑定。一套shader，往往对应一个材质模板。（同时也会给予材质模板里一些参数开关定义）。常见模板： PBR，Unlit、Toon、SSS(SubSurface Scattering)
- 材质实例：确定了材质模板里的参数。（其中部分参数影响PSO构建，比如CULL MODE，或者一些材质参数是否开启）。通常，比如UE/Unity中提供的材质节点编辑器，主要是基于选中材质模板的前提下，对材质实例进行编辑。
### Pass信息引入
预编码好不同pass的信息。

```cpp
// 资源用途枚举：用于自动化 Barrier 推导的关键输入
enum class ResourceUsage {
    Undefined,
    ColorAttachment,    // 作为颜色输出目标
    DepthWrite,         // 作为深度写入目标（Shadow Pass / Pre-Z）
    DepthRead,          // 作为深度测试读取
    ShaderRead,         // 作为纹理被 Shader 采样 (Texture/Sampler)
    StorageRead,        // 作为 SSBO/Storage Image 读取
    StorageWrite,       // 作为 SSBO/Storage Image 写入
    Present             // 最终呈现到屏幕
};

// 渲染路径类型定义
enum class RenderPassType {
    Shadow,             // 阴影贴图生成
    Opaque,             // 不透明物体（Forward/GBuffer）
    Transparent,        // 半透明物体
    PostProcess,        // 后处理
    Compute             // 纯计算任务
};

// 资源声明：描述 Pass 对某个具体资源（Texture/Buffer）的操作需求
struct ResourceRequirement {
    std::string resourceName;   // 资源标识符 (如 "MainColor", "ShadowMap")
    ResourceUsage usage;        // 本 Pass 中的用途
    bool isPersistent;          // 是否是跨帧持久资源
};

class PassInfo {
public:
    // --- 基础识别 ---
    std::string passName;
    RenderPassType type;
    uint32_t priority;          // 排序优先级
    // --- 资源依赖声明（FrameGraph 自动化的核心数据） ---
    // 每一个输入都会对应一个 Barrier 的 DstAccess/Stage
    std::vector<ResourceRequirement> inputs; 
    // 每一个输出都会对应一个 Barrier 的 SrcAccess/Stage
    std::vector<ResourceRequirement> outputs;

    // --- 渲染状态覆盖 (Optional Override) ---
    // 有些 Pass 可能会强制覆盖材质的状态，例如 ShadowPass 强制进行 Front-Face Culling
    struct RenderStateOverride {
        bool depthTestEnable = true;
        bool depthWriteEnable = true;
        float depthBiasConstant = 0.0f;
        float depthBiasSlope = 0.0f;
    } stateOverride;

    // --- 辅助方法声明 ---
    // 声明该 Pass 需要的资源，供 FrameGraph 构建拓扑图
    virtual void setupRequirements() = 0;
};
```

### Pipeline管理
- 参数化pipeline创建
- pipelineKey构造：
	- Mesh中的：Vertex Layout， Primitive Topology
	- Material中的： ShaderName, ShaderVariants(list), RenderState, PropertySchema (list) ，RenderPass
- 增加 pipelineCacheManager ： 由 device 持有。从key查询得到 pipeline
	- 支持序列化。这样加载启动的时候，统一创建好pipeline，避免每次重复创建带来资源损耗。（属于优化内容，可延后实现）
### RenderingItem改进
- 增加Priority
### RenderTarget(新增)
可以作为pass的输入和输出。同时是构建FrameGraph中pass依赖关系，核心参考的对象。
### RenderQueue(新增)
通常对应一个 `RenderTarget` 但内部包含多个 RenderableObject，并整合成对应的RenderItem。
### FrameGraph(新增)
每帧，由scene创建。同时根据 (Camera对象/RenderTarget) ，创建若干RenderQueue。

步骤简要描述：
1. 根据camera，形成显示化的若干RenderTarget 。由camera可以看见的RenderableObject，聚合为一个桶。接着对桶里所有RenderableObject，按照标记，分配其参与的pass。
2. 预设一些pass的输入和输出。根据这些输入输出，以及最后的RenderTarget，形成一个局部的pass依赖图（即 FrameGraph)。（通常由material标签fitler出pass，根据pass预设输入输出id，从BackBuffer向前回溯，得到所有依赖的pass；）
3. 合并局部的pass依赖图，形成全局的pass依赖图。（也会根据pass依赖关系，对对应的资源生成barrier）
4. 对每个pass里的 RenderableObject ，形成一个对应的 RenderTarget 以及 RenderQueue。
### 同步机制
建立一个 `VulkanSyncManager`，为每一帧（In-Flight Frames）预分配好一组 Semaphore 和 Fence，通过索引循环使用。主要将散落在swapchain和renderer中的同步对象，统一管理。并提供抽象接口，避免更加繁琐的调用。

此外，同时支持，分析pass资源依赖。自动建立barrier。

**自动化推导流程：**
1. **声明需求**：在 `FrameGraph` 编排 Pass 时，每个 Pass 声明它对资源的使用方式。
    - _ShadowPass_：我需要 `shadow_map` 作为 `DEPTH_WRITE`。
    - _ForwardPass_：我需要 `shadow_map` 作为 `SHADER_READ`。
2. **比对差异**：当执行流从 Shadow 移动到 Forward 时，系统发现：
    - `shadow_map` 的当前状态是 `DEPTH_WRITE`。
    - 下一个 Pass 请求的状态是 `SHADER_READ`。
3. **自动插入**：系统发现 `Current != Goal`，于是自动查表（或根据规则）生成 `VkImageMemoryBarrier`。
### shadow pass
用来测试和验证架构。


## 新架构图
![[LXEngine架构 v0.1.0-新架构图-01.png]]