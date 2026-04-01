---
title: LXEngine-AI Native渲染器
date: 2024-01-01T10:00:00+08:00
draft: false
image: /images/game-engine.jpg
---
LXEngine 是我从 高级 AI 工程师 向 底层图形学 跨越的技术结晶。它不仅是一个基于 Vulkan 的现代渲染器，更是我探索 “AI Native” 渲染范式的实验场。

项目状态：Active Development (v0.1.1 Core Architecture)

核心理念：打破物理渲染与神经渲染的边界，构建 AI 时代的数据驱动渲染管线。

在实时渲染步入“神经渲染”时代的今天，传统引擎的硬编码管线正面临巨大挑战。LXEngine 旨在通过 高性能 C++ 架构 与 神经计算算子 的深度融合，实现从传统 PBR 到 3D Gaussian Splatting 的全频谱渲染支持。

<!--more-->

## 技术栈
- **核心语言**：现代 C++ (C++20), Python (用于 Agent 工作流)
- **图形 API**：Vulkan 1.3 (利用 Descriptor Indexing, Dynamic Rendering 等新特性)
- **着色器语言**：GLSL / SPIR-V
- **AI/神经计算**：Compute Shader 自研算子, LLM (用于 Shader/Material 自动化生成)
- **第三方集成**：TinyGLTF, Shaderc，SDL3/GLFW, EnTT (ECS 架构预留)


## 项目目标
- 高性能 Backend：基于数据驱动设计，实现 Bindless Texture 架构与异步计算调度，压榨 GPU 并行性能。
- 物理精确渲染 (PBR)：实现符合能量守恒的 Cook-Torrance BRDF 模型与高质量 IBL。
- 神经渲染集成 (AI Native)：原生支持 3D Gaussian Splatting (3DGS) 渲染，并探索神经材质压缩技术。
- 智能生产力工作流：通过集成大语言模型，实现自然语言驱动的材质系统与 Shader 变体自动生成。
## 当前状态 (v0.1.0)

本版本完成了从“面向过程的单文件调用”向“面向对象分层架构”的彻底重构，建立了引擎的四大核心模块：

### 1. 深度分层架构 (Layered Architecture)
- **Core 层**：定义渲染核心接口（Mesh, Material, Camera, Light），利用**依赖倒置 (DI)** 原则，使核心逻辑不依赖于具体的图形 API 或窗口系统。
- **Backend 层**：封装 Vulkan 1.3 调用。实现了物理设备管理、资源生命周期监控及 Descriptor Set 的分帧回收重用机制。
- **Infra 层**：窗口系统解耦，支持 SDL2 与 GLFW 动态切换；自研基础数学库（Vec/Mat/Quat），支持 LookAt 与四元数旋转。

### 2. 渲染支柱抽象 (Rendering Pillars)
- **材质系统初探**：定义 `IRenderResource` 接口，将 Shader 参数（UBO/Texture）抽象为槽位（Slot），支持 Blinn-Phong 光照模型。
- **网格与骨骼 (Skinning)**：预定义多 buffer 顶点格式（Pos/Normal/Tangent/Bone），原生支持骨骼数据结构，为骨骼动画预留数据通路。
- **Uniform 方案**：采用 **Push Constant** 传递逐物体变换矩阵（Model Matrix），结合 UBO 传递场景级数据（Camera/Light），兼顾灵活性与性能。
 
### 3. AI 辅助工程流 (AI-Driven Workflow)
- **Agent 协同**：引入 **OpenSpec Agent** 工作流，辅助解决 Vulkan 复杂的同步与 Debug 细节，极大提升了底层重构效率。

更多内容: [LXEngine架构 v0.1.0]({{< relref "posts/renderer/LXEngine架构 v0.1.0.md" >}})

## RoadMap (核心开发计划)
### 阶段一：基础设施与静态渲染 (v0.1.0 - 已完成)
- [x] **架构解耦**：实现 Core/Backend/Infra 三层解耦，支持多 RenderPass 静态编排。
- [x] **资源管理**：基于 RAII 的资源生命周期控制与分帧 Descriptor 回收复用。
- [x] **场景基础**：跑通 MVP 流程，支持基础 Blinn-Phong 光照与网格渲染。

### 阶段二：架构演进与多 Pass 管线 (v0.1.1 - 进行中)
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

### 阶段三：工业级 PBR 与 现代管线 (v0.1.2 - 规划中)
- [ ] **物理精确渲染**：实现 Cook-Torrance BRDF 与 IBL (基于图像的光照)。
- [ ] **FrameGraph 演进**：引入渲染依赖图，自动处理 Image Layout Transition 与同步 
- [ ] **自动化 Shader 链**：集成 `shaderc` 实现 `.vert/.frag` 到 `.spv` 的自动实时编译。
- [ ] **高性能计算**：基于 Compute Shader 实现百万级 GPU 粒子系统。

### 阶段四：AI Native 深度集成 (v0.1.3 - 规划中)
- [ ] **Bindless 架构**：实现万级纹理实时寻址，支持现代 GPU 的 Bindless 设计。
- [ ] **神经渲染集成**：实现基于 Compute Shader 的 **3D Gaussian Splatting (3DGS)** Tile-based 渲染 Pass。
- [ ] **智能生产力**：利用 LLM 实现“自然语言 -> Shader 代码 -> 材质实例”的自动闭环。
- [ ] **超分与压缩**：集成 DLSS 2.x/FSR 并探索神经材质压缩 (NTC) 技术。

