---
id: art_32344ad2f03937f4965d5488930f7fd5
title: RT-13-全局光照(Global Illumination)
date: '2026-05-30T19:44:34+08:00'
draft: true
tags:
- 实时全局光照
- RSM
- LPV
- 间接光照
- 游戏渲染
---
实时GI，通常考虑：直接光照+1次bounce的间接光照
- 通常思路： 直接光照的结果，作为secondary light来照其他点。

本文深入探讨了两种实时全局光照技术：反射阴影贴图（RSM）和光传播体积（LPV）。RSM将Shadow Map像素视为次级光源，通过邻域截断、重要性采样和Mipmap等加速策略，高效模拟一次弹射漫反射间接光照，但存在漏光和仅适用于漫反射等局限。LPV则在三维网格中注入并传播直接光照的辐射度，利用球谐函数压缩方向信息，实现空间中的间接光照估计，但面临几何遮挡导致的漏光问题。文章详细分析了原理、步骤、优劣及工程实现技巧。

<!-- more -->

# 3D空间 (3d space)
## Reflective Shadow Maps(RSM)
### 原理
shadow map就可以描述，secondary light的分布。

Reflective Shadow Maps (RSM) 的核心思想是：**把 Shadow Map 上的每一个像素（Pixel）都看作一个微小的次级光源（Virtual Light Source, VLS）**。


回顾对光源采样的图：

![[RT_13_全局光照_Global_Illumination-原理-01.png|308]]

渲染方程：
$$
L_o(p, \omega_o)=\int_{A_{patch}} L_i(q\rightarrow p) V(p,\omega_i) f_r(p,q\rightarrow p, \omega_o) \frac{\cos\theta_p\cos\theta_q}{\|q-p\|^2} dA
$$


我们假设 Shadow Map 上的一个像素对应的微小表面（Patch）面积为 $dA_q$，它接收到了来自光源的直接光照。

**第一步：这个小 Patch 接收到的辐射通量（Flux）** 既然是 shadow map 的一个像素，它接收到的总能量（Flux）是一个微小量，我们记为 $d\Phi_q$

**第二步：计算这个 Patch 出射的 Radiance ($L_o$)**  这里RSM做了大胆假设，认为所有reflector都是完美漫反射（diffuse）。所以它向半球所有方向出射的 Radiance $L_o(q)$ 是一个常数。

根据漫反射的性质，出射度（Exitance） $M$ 和 Radiance $L_o$ 的关系为：
$$M = \int_{\Omega} L_o(q) \cdot \cos\theta \cdot d\omega = \pi L_o(q)$$


同时，出射度定义为单位面积出射的通量：

$$M = \frac{d\Phi_{out}}{dA_q} = \frac{\rho \cdot d\Phi_q}{dA_q}$$

_其中 $\rho$ 是该材质的反射率（Albedo），$d\Phi_q$ 是入射通量。_

把这两个式子联立，就能得到这个 Patch **向外发射的 Radiance**：

$$L_o(q) = \frac{\rho}{\pi} \cdot \frac{d\Phi_q}{dA_q}$$


**第三步，带入到渲染方程中**

$$
L_o(p, \omega_o)=\int \frac{\rho}{\pi}  \cdot  f_r(p,q\rightarrow p, \omega_o) \frac{\cos\theta_p\cos\theta_q}{\|q-p\|^2} d\Phi_q
$$

最后，考虑离散化。得到 

$$
L_o(p,\omega_o)=\sum_q \frac{\rho}{\pi} f_r(p)\frac{\cos\theta_p\cos\theta_q}{\|q-p\|^2} \Delta \Phi_q
$$
通常在这个步骤里， $f_r$ 也假设了漫反射。对漫反射来说， $L_o(p,\omega_o)= f_r(p)\cdot E_p$ 。因此，$E_p=\sum_q \frac{\rho}{\pi} \frac{\cos\theta_p\cos\theta_q}{\|q-p\|^2} \Delta \Phi_q$  （所以RSM技术计算漫反射反射，保留到shadow map的图上记录通量）。即对shadow map中的每个点记录通量后，使用的时候，可以快速采样得到 $\Delta \Phi_q$

注意：写代码的人为了省去一次开销昂贵的 `normalize()`（开平方）操作，故意把分母凑成 4 次方，同时分子不用标准 $\cos\theta$，而是直接用向量点积。
- $\frac{\cos\theta_p \cos\theta_q}{\|q-p\|^2}$ （物理标准版，分母是 **2次方**）
- $\equiv \frac{\text{dot}(n_p, q-p) \cdot \text{dot}(n_q, p-q)}{\|q-p\|^4}$ （工程凑数版，分母是 **4次方**）
这两个公式算出来的数值**完全等于同一个数**。

**“能量衰减不会发生在 $L$ 上（Radiance 具有距离不变性）”是辐射度学的核心铁律。距离变远导致 $E_p$ 变小，本质是因为接收面看到的次级光源立体角 $d\omega$ 变小了。**

如果考虑 $f_r$ 不是漫反射，那么求和的时候，针对所有间接光源q，都要计算求和。（本身也是可行的）。


### 加速方案
> “哪怕 $p$ 点是 Diffuse，不用在循环里算复杂的 PBR 高光 BRDF 了，但我们依然要面对 **Shadow Map 上成千上万个像素 $q$**。难道每一个 Shading Point $p$，都要和所有的 $q$ 算一遍距离、算一遍点积吗？这 GPU 绝对直接卡死！”

**答案是：当然不能暴力全算。** 工业界为了加快计算，并没有选择去“预计算”那些角度和距离（因为物体会动、手电筒会晃，根本没办法预计算）。相反，RSM 引入了两个极其天才的**大胆假设与工程工程trick**，把复杂度直接从 $O(N \cdot M)$ 砍成了常数级别。

#### 只找“邻居”像素（屏幕空间截断）

**投影连续性假设** 

RSM 假设：**如果在三维空间中 $q$ 和 $p$ 很近，那么把它们投影到主光源的 Shadow Map 上时，它们的像素位置也应该离得很近。**

因此，写代码时的具体做法是：
1. 把当前屏幕上的 Shading Point $p$ 投影到主光源的 Shadow Map 上，得到一个二维坐标 $(u, v)$。
2. **重点来了：** 我们不再遍历整张 Shadow Map，而是**只在以 $(u, v)$ 为中心、半径为 $R$ 的小圆圈（邻域）里进行采样！**
3. 这样，原本需要遍历整张图（比如 $512 \times 512$ 个点），现在缩减到只需要看圆圈里的几十个像素，计算量瞬间暴跌。

#### 重要性采样（Importance Sampling）与低频过滤
即使限制在了一个圆圈里，如果每个像素都采样，开销依然很大。为了进一步提速，RSM 引入了蒙特卡洛积分的**重要性采样**。

在那个半径为 $R$ 的圆圈里，什么样的像素 $q$ 贡献最大？
- 离中心点 $(u, v)$ 越近的像素（因为距离近，衰减小）。
- 角度夹角好的像素。

因此，论文设计了一个特殊的**概率密度函数（PDF）**。在采样时，离中心点越近，采样的密度越高；离得越远，采样越稀疏。

![[RT_13_全局光照_Global_Illumination-重要性采样importance_sampling与低频过滤-01.png|420]]


#### 多级渐远纹理（Mipmaps）高能压缩
最后，RSM存什么？
- Depth， coordinate， normal，flux
![[RT_13_全局光照_Global_Illumination-多级渐远纹理mipmaps高能压缩-01.png]]

还有一种更激进的工业界优化方案： interleaved sampling + Mipmaps。

既然 Diffuse 是低频的，我甚至不需要看 Shadow Map 的原图（高分辨率）。

1. 把 RSM（包含 Flux、Normal、Depth 的图）预先生成好 **Mipmaps**（低分辨率的图，比如 $64 \times 64$ 或 $32 \times 32$）。
    
2. 当 $p$ 点离次级光源较远时，直接去采样 RSM 的**高层级 Mipmap（低分辨率像素）**。这时候，低分辨率图里的一个像素，其实就代表了原图中一大片像素的“平均通量”和“平均法线”。
    
3. 这样，通过采样极少量的低分辨率像素，就相当于隔空打包计算了成百上千个原图像素的贡献！


### 为什么不计算高光 $f_r$
**在数学和逻辑上，这套采样架构完全可以直接支持 $f_r(p)$ 是高光（Specular）的情况。** 只要把 $f_r(p, \omega_i, \omega_o)$ 丢进那个已经优化到只有 64 次的循环里，GPU 跑起来完全没有压力。

漫反射的 BRDF 是一个**非常平滑的半球**（低频信号）。
- 无论间接光从哪个角度射入，$p$ 点对它的接受度都是一样的。
- 此时我们在 RSM 的小圆圈里随机抽 64 个点，虽然这 64 个点不能完全代表周围成千上万个像素，但因为由于漫反射的“平滑”特性，算出来的能量结果和真实值差得并不多。
- 即使有一点点噪声，由于它是低频的，我们在屏幕空间用一个**双边滤波（Bilateral Blur）**，就像美颜相机磨皮一样，轻松就能把噪声抹得平平整整。

高光（尤其是粗糙度较低、比较光滑的材质）的 BRDF 是一个**极窄、极尖锐的波瓣（Specular Lobe）**（高频信号）。

这就带来了两个致命的视觉工程问题：

 **问题一：概率极低的“盲人摸象”（采样爆炸）**
- 只有当间接光源 $q$ 刚好落在 $p$ 点的这个“高光窄瓣”里时，$p$ 点才能看到强烈的高光。
- 如果你只随机采样 64 个点，这 64 个点**大概率全部脱靶**（落在了高光瓣外面），此时你算出来的间接光是 0。
- 突然，摄像机移动了一点点，或者光源晃了一下，在下一帧的随机采样里，有一个点**不幸刚好撞中了**这个高光窄瓣，这一像素的亮度瞬间暴增到 100。
- **视觉后果：** 画面开始疯狂地闪烁、跳变，出现满屏巨大的、像雪花点一样的白色噪点（Fireflies）。

**问题二：工业界没有能“磨平”高光的模糊算法**
- Diffuse 噪点能用 Blur 抹平，是因为 Diffuse 间接光本来就应该是一片模糊的。
- 但高光间接光（比如镜子、大理石地面上的反射）具有明确的**几何结构和边缘**。如果你对高光间接光套用 Blur，反射出来的物体就会像高度近视眼看到的一样，高光的质感（大理石的灵魂）直接被洗掉了。
- 如果不用 Blur，想要靠增加采样率来把高光硬生生堆平，采样数可能需要从 64 暴涨到 **1024 甚至 4096**。这时候，RSM 的性能优势荡然无存，GPU 直接被干烧了。

### 如何解决高光 $f_r$
- **重要性采样升级（BRDF Importance Sampling）：** 既然在 Shadow Map 的圆圈里瞎随机采样撞不中高光，那我们就**反过来**。根据 $p$ 点的高光波瓣方向（反射方向），去反推应该去 RSM 的哪个具体位置采样。这就叫按 BRDF 重要性采样。
    
- **时域超分辨率滤波（Temporal Denoiser - TAA / ASVGF）：** 这一帧只采 64 个点噪声大没关系。我们把上一帧、上十帧的采样结果通过运动矢量（Motion Vector）对齐，“偷”过来融合在一起。这样在时间轴上，相当于每像素累积了 640 个采样点，噪点被彻底消灭，高光边缘还能保持锐利。

### pros/cons
优点：
- 实现简单

缺点：
- 跟primary light数量相关。越多越计算量越大。
- 没有考虑环境光的 visibility（目前认为做不了）
- 过多假设：间接光源都认为是 diffuse，depth直接当作距离，等等。
- 采样率会影响效率和效果

RSM 从 2005 年提出到 2016 年局部落地，再到今天，它依然只是一个“特种兵”技术（多用于手电筒、车灯等局部强光源的实时弹射），未能全面统治 GI，主要原因在于其天生的**Visibility（阴影）硬伤**：

- RSM 在算间接光时，**默认不计算间接光的阴影**（即不考虑次级光源 $q$ 到 $p$ 之间有没有遮挡物）。如果要算遮挡，每个 $q$ 都需要自己的一张 shadow map，计算量当场爆炸。
    
- 如果在场景里塞满 RSM（比如太阳光的 GI），由于没有遮挡，光线会严重的“漏光（Light Leaking）”—— 比如隔着一面墙，墙背后的房间会被莫名其妙照亮。
    

所以，工业界对 RSM 的定位非常精准：**只适合做局部、小范围、强光源（如手电筒、霓虹灯）的一 bounce 漫反射实时弹射。**

### 备注
VPL 和 RSM 很像。

## Light Propagation Valumes (LPV)
思路：在三维空间中传播光线。

### 思路
- Key Problem: 对任意shading point，从任何方向查询radiance
- Key Idea: Radiance在传播过程中不变。
- Key Solution： 用3D grid 来 传播 直接光照的结果，得到对应的radiance 。

这个算法细节很多。

### 步骤
1. Generation of radiance point set scene representation (生成直接光照后，用点集来表示场景；利用RSM，计算哪些点接受直接光照)
2. Injection of point claude of virtual light sources into radiance volume (把点集注入到空间格子中，计算 radiance； 把点放入到格子里)
3. Volumetric radiance propagation (空间中，radiance传播)
4. Scene lighting with final light propagation volume (利用空间中计算好的 LVP ，协助计算全局光照着色)

#### 1. Generation
用RSM找到场景中被直接光照照亮的表面。 （**当然每个光源都要做**)

![[RT_13_全局光照_Global_Illumination-1_generation-01.png]]

#### 2. Injection
用三维纹理来记录。对格子内部包含一些虚拟光源，叠加后，形成基于包围盒表面定义的一个光源辐射的函数。然后用SH来逼近这个局部的光源

![[RT_13_全局光照_Global_Illumination-2_injection-01.png]]

#### 3. Propagation
考虑包围盒。然后从每个格子，向周围的6个格子传播radiance。
- 格子里：a. 空的。 b. 存在光源，那么则SH展开，保留低频系数。
- 迭代：每个格子收到周边6个格子的 radiance，叠加。（叠加SH系数即可）随后反复操作。
	- 格子附近的其他格子如果有光源：那么，把对应的radiance按照方向，仅投影incident方向，得到新的系数。随后，每个基的系数叠加。（这部一定要考虑方向性，这会导致不同的谐波系数发生较大变化，从而表达了方向性）
	- 注意：对于格子内本身就有的光源，仅在第一次计算的时候用到，作为初始能量向外传播。第一次迭代结束后，如果这个格子周围都是黑的，那么光源格子自然就是黑的。（但直接光照会对其正常着色）。
- 整体迭代 5 次左右。

![[RT_13_全局光照_Global_Illumination-3_propagation-01.png]]

#### 4. Rendering
对任意的 shading point ，如果其处于某个格子内，那么这个格子本身我们计算了 incident radiance，所以可以直接用这个来进行间接光照着色。（当然，实际做法的时候，根据 shading point的位置，可以做和周边格子的插值，得到更加平滑的过度）

### Problem: Light Leaking
格子内Radiance假设了均匀，但会有几何遮挡，导致错误（light leaking） ，原因是因为格子不够细。如下图，如果p点右侧接收到了radiance，但我们不考虑遮挡，这个radiance仍然会被透传到p的左侧，从而照亮左侧的格子。

当然，实际上，墙只要不够厚，不能覆盖多个格子，那么propagation按照我们的算法都会漏光。不过，如果格子完全被几何体覆盖，可以对格子标记专门的阻挡信息，隔断propagation。这里也是实现上的trick点。（有可能需要对格子内几何体的法线分布（用面积做权重）做压缩，来近似计算，得到阻挡概率分布）

![[RT_13_全局光照_Global_Illumination-problem_light_leaking-01.png|453]]


![[RT_13_全局光照_Global_Illumination-problem_light_leaking-02.png]]

### 实时工作流
| **阶段**             | **实时计算的具体操作**                                                                            | **耗时与复用机制**                                           |
| ------------------ | ---------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| **1. Generation**  | 针对场景中的动态光源，渲染出 **RSM（反射阴影贴图）**。如果光源在移动（比如手电筒、太阳光移动），RSM 会**每帧实时更新**。                     | **极快**：复用了游戏原本就要画的 Shadow Map，只是多输出了法线和颜色。            |
| **2. Injection**   | 启动一个计算着色器（Compute Shader），把 RSM 的成千上万个像素像素（VPL）和场景的 G-Buffer 几何表面，**实时投射并写入**到 3D 纹理网格中。 | **极快**：纯粹的原子操作或屏幕空间散布（Scatter）。                       |
| **3. Propagation** | 在 GPU 里利用**乒乓双缓存（Ping-Pong Buffer）**，对这个 3D 纹理连续执行 4~5 次渲染通行（Pass）。能量在格子间流动，生成最终的辐射场。    | **LPV 最核心的开销**：完全在 GPU 显存内部完成，不涉及 CPU，5次迭代大约消耗 1~2ms。 |
| **4. Rendering**   | 正常渲染场景物体表面时，Shader **实时采样**这个 3D 纹理，通过三线性插值把间接光颜色加到画面上。                                  | **极快**：普通的 3D 纹理采样。                                   |
整体相当于4pass的算法
## Voxel Global Illumination (VXGI)
### 思路
2pass算法。整体来说：场景离散化格子；然后，着色点，用BRDF反射视线，查询锥的区域，得到对应的格子。通过这些格子的信息来获取间接光照。

![[RT_13_全局光照_Global_Illumination-思路-01.png]]

### 步骤
对整个场景，建立 hiearchy 的格子。

![[RT_13_全局光照_Global_Illumination-步骤-01.png]]

#### Pass1 - light pass - 得到直接光照的voxel
![[RT_13_全局光照_Global_Illumination-pass1_light_pass_得到直接光照的voxel-01.png]]

- 记录：（当然都是记录SH）
	- 光源方向
	- 法线方向
#### pass2 - rendering pass - 渲染基于cone tracing

![[RT_13_全局光照_Global_Illumination-pass2_rendering_pass_渲染基于cone_tracing-01.png]]

cone碰撞到平面的时候，可能距离会远会近。根据这个距离，可以得到层级。采样的时候，类似mipmap采样对应层级即可。

### 问题
解决glossy比较好，如果diffuse呢？

![[RT_13_全局光照_Global_Illumination-问题-01.png]]
# 屏幕空间方法 (screen space)
什么是屏幕空间？仅能看到屏幕渲染的结果，然后进行处理（即后处理的效果）。
## 环境光遮蔽: Screen Space Ambient Occlusion (SSAO)
基于contact shadow，增强立体感

因AO 模拟的不是某个具体光源（如太阳、路灯）投射的阴影，它模拟的是**全局环境光（Ambient Light）**。

在现实世界中，哪怕一个房间里没有直射光，光线在墙壁之间经过无数次漫反射（Global Illumination, 简称 GI），也会让整个空间充满微弱的、来自**四面八方**的散射光。
- **AO 的本质**：计算一个点有多少角度能“看到天空/看到周围环境”。
- **折角、缝隙处**：能够接收到来自四面八方漫反射光线的“窗口”变小了。所以即使没有直射光，这些地方也应该更暗。

SSAO：
- 全局光照的近似
- 在屏幕空间
- Key Idea1 ： 不知道 incident indirect lighting （于是假设间接光照为常数）
- Key Idea2 ： 每个shading point（屏幕空间）的 visibility 不一样。
- 假设diffuse物体

整体做法，很简单：看起来像是给物体贴了个阴影图的做法。
### Ambient Occlusion理论
![[RT_13_全局光照_Global_Illumination-ambient_occlusion理论-01.png]]

考虑 渲染方程，用split sum拆分，把Visibily 函数从积分中拆分出来。
$$
L_o(p,\omega_o)=\int_{\Omega^{+}}L_i f_r V \cos\theta_id\omega_i \approx \frac{1}{\pi} \int_{\Omega^+} V\cos\theta_i d\omega_i \int_{\Omega^+} L_i f_r \cos\theta_i d\omega_i
$$
- $\frac{1}{\pi}$ ，其实是对 \cos\theta 在半球积分。
- $k_A$ 定义为，从视角方向看到某个点，这个点朝着各个方向上，光照的visibility：
	- $k_A=\frac{1}{\pi} \int_{\Omega^+} V\cos\theta_i d\omega_i$
- 为什么split sum后，有两个 $\cos$ ？
	- 实际上可以理解为一种球面积分的换元。用 $\mu=\cos\theta$ 。具体参见 [[深入思考曲面积分]] 中的 “换元剪切技巧” 。


进一步考虑 $L_i, f_r$ 都为常数。且 $f_r=\frac{\rho}{\pi}$ ，那么上面式子：
$$
L_o(p,\omega_o)\approx k_A L_i \rho
$$
所以，AO就是平均的visibility，乘以固定光照。

### 如何计算 $k_A$
世界空间：
- raycasting 针对几何体，slow，依赖于场景复杂度

屏幕空间：
- 直接在后处理完成。场景复杂度不影响结果。物理上不那么准确。

具体如何做？考虑反射光在有限的范围内，是否被其他物体遮挡。

![[RT_13_全局光照_Global_Illumination-如何计算_k_a-01.png|597]]

Screen Space （实际上是NDC空间） 的做法的假设：
1. 任何一个shading point，都在一个局部的球的内部，撒点，看点是否能被shading point看到
2. 直接用一个点的深度，如果这个点深度，大于depth buffer的值，那么此时认为这个点可以被shading point看不到 （红点）。如果，深度小于depth buffer，就认为shading point能看到（绿点）。
3. 考虑：应该只有法线方向的半球上，才可能有遮挡。因此，一个快速方法：下图中红点数量过半，才考虑 AO 
	1. 如果有法线：那么采样，可以仅采样半球了，且可以对采样点进行加权。

![[RT_13_全局光照_Global_Illumination-如何计算_k_a-02.png]]

### False occlusion, halos
![[RT_13_全局光照_Global_Illumination-false_occlusion_halos-01.png]]

问题原因：
- 取屏幕空间一个点，然后取球。由于深度突变，所以采样点显然被 石凳 上的点遮挡，这里错误的被认为石凳附近的地板，周边有复杂的几何遮挡，从而叠加了AO（环境光遮蔽）。就会导致局部变暗。
### samping细节
- 更多采样，更精确。
- 通常只用16个 sample
- 采样位置要随机
- noisy的结果：做一下blur，AO就变得更光滑一些。

### 扩展：HBAO
但 SSAO 的 False Occlusion 主要源于以下两个痛点：

**痛点一：法线缺失导致的“自我遮挡”（Self-Occlusion）**

经典的 SSAO（如 Crysis 最初的版本）在采样时不考虑几何体的法线，直接在点周围采一个**完整的球体**。
- **结果**：对于一个完全平坦的墙面，球体有一半的采样点必然会落在墙面“内部”（深度大于 Depth Buffer）。
- **副作用**：这会导致平坦的墙面自己绿油油/黑乎乎一片（错误的自遮挡）。后来 SSAO 引入了法线，将球体改为**面向法线的半球体（Oriented Hemisphere）**，解决了这个平坦表面的自遮挡问题。

**痛点二：深度断层导致的“远景遮挡”（Haloing / False Occlusion）**
- 当我们在角色边缘（靠近背景墙的像素）进行采样时，半球体内的某些采样点在屏幕空间投射到了**背景墙**上。
- 此时去查 Depth Buffer，背景墙的深度值自然大得多（距离相机更远）。
- 如果算法仅仅简单地判断 `采样点深度 > Depth Buffer深度`，那么这些本该是空旷天空或遥远背景的点，就会被判定为“被背景墙遮挡了”。
- **结果**：角色的边缘会出现一圈阴暗的“光晕”（Halo），这就是典型的**由于深度突变引起的 False Occlusion**。

HBAO（Horizon-Based Ambient Occlusion）的核心思想并不是简单的“采样半球”，它是基于地平线仰角（Horizon Angle）的物理光学模型。

为了完美解决你说的“远处的物体产生遮挡”以及“深度断层”问题，HBAO（以及现代优化后的 SSAO）主要采用了以下两层防护：

**距离衰减函数（Distance Attenuation）**

当采样点和当前像素点的实际三维距离（或者深度差 $\Delta z$）超过一个设定的**最大半径（Max Radius）**时，这个采样点对 AO 的贡献就会**直接衰减为 0**。

$$Attenuation(\Delta z) = \max\left(0, 1 - \left(\frac{\Delta z}{R}\right)^2\right)$$

- 如果背景墙距离前景角色超出了采样半径 $R$，它对前景点的遮挡贡献就是 0。
- 这样就从数学上直接切断了“远景物体对近景的错误遮挡”。

**地平线追踪（Horizon Tracing）与法线结合**

HBAO 不是在半球内随机撒点，而是在屏幕空间沿着几个固定的方向（比如 4 或 8 个方向）进行**射线步进（Ray-marching）**。
1. **寻找最大仰角**：在每个方向上向前步进时，它会对比周围几何体与当前点形成的夹角，寻找全图的“最高地平线”仰角（Horizon Angle）。
2. **法线切线裁剪**：通过当前点的法线，可以算出一个表面切线角（Tangent Angle）。只有当“地平线仰角”大于“切线角”时，才证明真的有东西凸起、产生了遮挡。

如果在步进过程中，采样点突然跨越到了非常远的背景（深度剧增），由于前面提到的**距离衰减**，这个远景采样点会被判定为无效，不会拉高地平线仰角，从而保证了遮挡的正确性。

## Screen Space Directional Occlusion (SSDO)
- AO： 考虑有一个全局环境光
- DO： 否定上面的假设，直接用次级光源来做。这样可以做到 color bleeding 的效果（如下图）
 
![[RT_13_全局光照_Global_Illumination-screen_space_directional_occlusion_ssdo-01.png]]

### 思路
虽然用次级光源信息，但不用RSM，而从屏幕空间来做。

对shading point p，发出一个随机光线：
- 如果打到物体，接收到间接光照
- 如果打不到物体，就没有间接光照

所以和SSAO做法相反。但AO考虑的是全局环境光（足够远），增量局部颜色。而DO认为局部颜色变化由小范围其他间接光（足够近）来着色，远处不考虑。

![[RT_13_全局光照_Global_Illumination-思路-02.png]]
- SSAO考虑第一个式子
- SSBO考虑第二个式子

**前提假设**： 不考虑光照方向。或者说，认为视线方向是光照方向。（类似SSAO）

![[RT_13_全局光照_Global_Illumination-思路-03.png]]

1. 从P点附近，找一个半球。sample附近的像素。
2. 命中的像素点，看是否遮挡P点。如果遮挡的点，对应的像素的值会被考虑
3. 第三张图是 SSDO出问题的场合（前提假设不对的时候）。
	1. A：会被错误的认为P点看不傲。
	2. B：这个点取得不好，为了说明，视线看得到，但P看不到。


### SS的问题
一切SS（Screen Space）的问题
- 丢失相机看不到的面，产生的GI。

## Screen Space Reflection (SSR)
### 思路
在屏幕空间（即Camera看过去的壳）做光线追踪。

解决两个task：
- 给定光线和 Camera场景壳 求交。
- Shading： 求交后如何着色。


![[RT_13_全局光照_Global_Illumination-思路-04.png|560]]

也可以考虑brdf的lobe

![[RT_13_全局光照_Global_Illumination-思路-05.png]]

### 核心步骤：求像素反射点

Linear Raymarch
- 通过视线、着色点、法线，找到反射方向。
- 按照步长进行移动，会有对应的depth变化（和本身记录的depth做比较）
- 当depth大于记录值，说明发生了求交。

![[RT_13_全局光照_Global_Illumination-核心步骤求像素反射点-01.png]]

步长如何确定？ hierachy ray trace
- 把depth变为mipmap（做 min pooling，取最小值）
- 随后用这个mipmap可以快速尝试测试步长。

一次步进 (marching) 首先在一个高level上走一个步长。
- 如果相交了，那么再调整一个更低的level。
- 如果没相交，那么继续步进即可（此时可以调大一个level）。
- 注意：不用回退，因为是 min map 。所以相交对应的点，调低level后，直接测试是否相交。（因为交点可以得到具体的子节点索引(finer 1 level)，这个子节点要么相交，得解；如果没相交，还可以步进）

![[RT_13_全局光照_Global_Illumination-核心步骤求像素反射点-02.png]]

算法：
```
mip = 0;
while (level > -1)
	setp through current cell;
	if (above Z plane) ++level;
	if (below Z plane) --level;
```

### 核心步骤：shading
和path tracing没有区别。

前着色点(receiver)是考虑BRDF的，而步进得到的点 hit point(caster) 假设是diffuse的，因为像素保留的仅有camera上看到的值，我们直接用这个值假设它是一个次级光源。（如果不考虑它是diffuse的，那么就需要用它本身的brdf，再往前找上一层的光源进行采样；SSR本身并没有做这个步骤，仅计算一次bounce）

![[RT_13_全局光照_Global_Illumination-核心步骤shading-01.png]]
### 问题和解决方案
超出 screen space 的位置？
- 步进过大的点

此时做一个虚化，颜色慢慢消失。



diffuse上，计算开销比较大。
