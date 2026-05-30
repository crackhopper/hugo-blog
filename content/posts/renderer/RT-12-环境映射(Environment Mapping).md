---
id: art_d9fc359086a1e568c3b6320f11df2bb9
---
# 环境光照介绍
- 用一个图片表达从无穷远+各个方向出来的光。

# Image-Based Lighting (IBL)
## 原理思路
给了IBL，如何对一个点着色？

$$
L_o(p,\omega_o)=\int_{\Omega^+} L_i(p, \omega_i) f_r(p,\omega_i,\omega_w)\cos\theta_i d\omega_i
$$

- 注意，不考虑遮蔽：($V(p,\omega_i)$)
- 这里IBL相当于给定 $L_i(p,\omega_i)$ 。
- 求解办法：Monte Carlo 积分（但很慢）。因此shader中，不考虑采样算法。（除非配合TAA的方式）

BRDF材质：如果足够glossy（表面光滑）则BRDF support小，如果足够diffuse（表面粗糙）则BRDF更光滑。

![[RT_12_环境映射_Environment_Mapping-原理思路-01.png]]

因此我们可以用常见的逼近方式（积分中值定理）：

$$
L_o(p,\omega_o)\approx \frac{\int L_i d\omega_i}{\int d\omega_i} \int f_r \cos\theta_i d\omega_i
$$

这样做的时候，拆分的中值项，实际就是取IBL的图上进行filter。

##  $IBL$ 积分 (第一项)

![[RT_12_环境映射_Environment_Mapping-ibl_积分_第一项-01.png]]

所以IBL部分的积分的求解方式：
1. 根据 $f_r$ 的support（由于反射角度决定，因此，可以得到入射角的support，这样可以在对应的support上，求 $L_i$ 的均值）
2. 而如果 $f_r$ 的support很大比较光滑的时候。那么其实相当于对整个 $L_i$ 求均值来着色。

所以，主要是根据 $f_r$ 的support来决定filter的大小。而为了支持查询，IBL显然可以做mipmap/SAT 之类的。

## BRDF积分 (第二项)
**上面仅解决了积分的第一部分，还有另一个积分的部分**

$$
\int_{\Omega^+} f_r(p,\omega_i,\omega_o) \cos\theta_i d\omega_i
$$

进一步，可以拆分 $f_r$ 。按照microfacet的方法，拆分为 FDG。 （F:Fresnel项、D:法线分布项(粗糙度)、G:几何项）。当然需要想办法预计算。

## Microfacet BRDF 下的近似计算
回顾 Microfacet BRDF

$$
f_r(\omega_i,\omega_o) = \frac{F(\omega_i,h)D(h)G(\omega_i,\omega_o,h)}{4(n\cdot \omega_i)(n\cdot \omega_o)}
$$
求解中，忽略几何项。


先看F项（Schlick逼近）
$$
\begin{array}{rcl}
F(\omega_i,h) &= & R_0 + (1-R_0) (1-\cos\theta)^2 \\
R_0&=&  \left( \frac{n_1-n_2}{n_1+n_2} \right)^2 \\
\end{array}
$$
- 这里 $\theta$  是入射角
	- 不过需要注意的是：入射角、反射角、或者光线和半程向量的夹角。（在一定条件下，这几个角都假定相等，当作近似计算的时候；显然此时，要求 发现和半程向量夹角 $\theta_h$ 要足够小）

![[RT_12_环境映射_Environment_Mapping-microfacet_brdf_下的近似计算-01.png]]


再看D项（Beckmann 分布，不过后来更常用的是GGX）
$$
D(h)=\frac{1}{\pi\alpha^2\cos^4\theta_h} e^{-\frac{\tan^2\theta_h}{\alpha^2}}
$$
- 这个分布是在平面上假设高度符合高斯变化，推导得到的法线分布。（非归一化的，也没有做投影矫正；这个函数乘 \cos\theta_h 后，就得到投影后归一化的法线分布；）
	- 这个分布得到结果是法线也符合高斯分布
	- 固定角度，\alpha 越大，越粗糙。法线分布越平均。
	- 固定粗糙度，半程夹角越大，法线密度越低，即法线还是分布在主法线附近。

![[RT_12_环境映射_Environment_Mapping-microfacet_brdf_下的近似计算-02.png]]


**基于用Split Sum (积分中值定理) 来简化** Fresnel项如果使用Schlick逼近处理：

$$
\int f_r\cos\theta_id\omega_i = R_0\int \frac{f_r}{F} (1-(1-\cos\theta_i)^5)\cos\theta_id\omega_i+\int\frac{f_r}{F}(1-\cos\theta_i)^5\cos\theta_id\omega_i
$$

拆分后，基础反射率就被单独拆出一项来，被积函数内部，不考虑几何自遮挡，仅剩下 D(\alpha, h) 项。

预计算仅需要考虑， roughness 和 $\cos\theta_v$  两个变量下的积分（后者是因为有了这个相当于通过 \theta_i （被积变量）可以得到 \theta_h ，从而被积分函数内部都可以计算，可以用monte carlo方法预计算出积分来）。最后，确定参数下，可以打两张表。然后两次查表就可以快速计算积分。 这个表也叫做 **Specular LUT**

![[RT_12_环境映射_Environment_Mapping-microfacet_brdf_下的近似计算-03.png]]


之前都没考虑遮蔽项G。如果考虑的话，实际上，固定 \cos\theta_v ，那么有了G的公式，也可以再打表的时候，直接带入到里面去。

如果各向异性怎么做？引入两个不同方向的粗糙度 \alpha_1 和 \alpha_2 。然后对形状进行拉伸，即 x/\alpha1, y/\alpha2 ，再积分打表。这样需要考虑确定4个变量 \alpha_1, \alpha_2, \theta_v, \phi_v。(随后有个等效视线角的概念，即方位角上的变化，可以去除掉方位角得到在\theta上调整，得到一样的视觉效果；配合等效粗糙度，从而得到一个正确的着色计算)。


## 总结思路
求解渲染方程：
- 分离光照相关积分和材质相关积分：实际上可以让这两块工程上更独立，生成得到的LUT积分表可以组合复用。用split sum的方法。
	- 不分离也是可以预计算的。但每个不同的光照和材质组合都要计算一遍。（而性能提升并不见得多大；但存储开销极大）
	- split sum方法要注意遗留在原积分内部的函数的support。这样决定了另一个积分的大小。
- 光照部分的积分：（查表主要的外部变量 ($\cos\theta_v, filtersize$) ，filtersize也可以理解为level）
	- 最终形成光照区域可查的表。可以考虑mipmap。
	- 要考虑积分的范围，即滤波范围。（这个根据输入 $\omega_o$ ，得到的 $f_r$ 的support来决定）
	- 采样方法：根据范围，结合类似possion分布，确定样本点。
	- 直接区域查询：在mipmap上，根据范围得到对应的level。从而直接得到平均值。
- 材质部分的积分：（查表主要变量：粗糙度和 $\cos\theta_v$  ；或者等效的这两个值）
	- 固定这两个个值，材质积分内部的都可以计算。从而可以用monte carlo方法预计算好积分。
	- 需要打表为2个表。可以存在一个图上。这个图叫做 Specular LUT
	- 各向异性：引入两个粗糙度，并对查表变量进行处理。
	- 自遮蔽：积分计算的时候引入对应的G函数即可。
- 数学技巧的总结：
	- 主体概念不同的计算部分，考虑split sum拆分。
	- 积分中的外部变量，尽量压缩到2个。（如果有多个，考虑引入约束，从而降低到2个自由变量）
	- monte carlo方法都预计算。不要实时渲染。（但实时采样求解积分，如果结合TAA类的技术，是可以考虑的）


## 效果

![[RT_12_环境映射_Environment_Mapping-效果-01.png]]

## 局限性
- 假设所有环境光无限远。所以如果离的特别近的时候计算，会有问题。

# Precomputed Radiance Transfer (PRT)
## Background - Spherical Harmonics
[[调和分析入门]]  （用拉普拉斯算子的谱，来辅助分析；有更好的局部逼近和全局一致逼近性）

简单讲一下 球谐函数（Spherical Harmonics） （简记为 $B_i(\omega)$ ，即一个球面上的函数）

![[RT_12_环境映射_Environment_Mapping-background_spherical_harmonics-01.png]]


实际上，每个l代表一次空间折叠。 m 代表空间折叠的方向（或者有点像对空间切几刀）。一些性质：
- 每行基函数数量 : $2l-1$ ，频率都是一样的
	- 每阶的SH，编号都从 $-l$ 到 $l$
- 前 $l$ 阶一共多少个函数？ $(l+1)^2$

主要用来分析球面上的函数。


球谐基展开：求系数，等于求投影。实际上是谱分解。由于球谐基函数是已知的，所以谱分解很容易。

通用调和分析的方法理论：
- 定义内积。
- 从内积定义，得到全微分，进一步导出拉普拉斯算子。
- 基于拉普拉斯算子，是用QR/施密特正交化的思想做迭代（**Lanczos / Arnoldi**）。 从而可以谱分解。

## PRT整体思路
环境渲染

![[RT_12_环境映射_Environment_Mapping-prt整体思路-01.png]]
- 上图中，都是给定了出射角度 $\omega_o$ ，然后被积分的函数内容，可以用图像（球面来表示）
	- 盒子对应的像素： 6 x 64 x 64
	- 对每个像素（采样点），均计算一次函数值。最后通过加权求和得到积分（投射到方向垂直的面上）。
	- 这样，每次着色，需要 6 x 64 x 64 次（3个点相乘），然后求和。。。


对上面的内容，考虑预计算（其实可以转化成频域/谱域的信号）。现在渲染方程重新考虑：
![[RT_12_环境映射_Environment_Mapping-prt整体思路-02.png]]
- BRDF（包含外部遮蔽）乘角度，整体看作 **light transport**
- 实际做法：把 Lighting 和 Light Transport 分别做球谐展开。这样只需要保留两组系数即可。
- 针对不同的 $\omega_o, \alpha$ ，就可以预计算对应的球谐展开，保存几个系数（得到几张LUT图）
	- 对 Lighting： $k$ 维的向量。（因为对光照项来说，不包含出射方向。）
	- 对 Light transport ， 
		- $k$ 维的向量：完美漫反射的时候，观察的角度不影响结果。
		- 如果是其他BRDF，则需要考虑出射的角度了。（见下节）
			- 那么就会形成一个 $k  \times \text{Count}_{\cos\theta_o}$ 的矩阵。因此相乘后，就会得到一个向量，记录了不同俯仰角下的着色。
	- 两个向量在频率做内积就等于时域的积分。（显然的结论）




具体原理：

$$
\int L_i f_r \cos\theta_i d\omega_i = \sum l_j \int B_j f_r\cos\theta d\omega_i=\sum l_i T_i
$$
因此，做两次球谐展开（预计算）：
1. Lighting (环境光贴图)：的球谐展开。
2. Light Transport (BRDF项)：球谐展开。

**注意，上面考虑的是漫反射**，因此可以认为积分是对整个定义域积分的。


如果旋转了会怎么样？即 $\phi$ 发生了变化呢？
- 如果是光照旋转了：那么，对应的 $l_i$ 的系数需要做一下对应的旋转的调整。（把同阶的线性组合的系数用特定算法转化一下即可）
- 如果观察角度变化呢？
	- 如果是各向同性，其实不影响。

## 效果图
![[RT_12_环境映射_Environment_Mapping-效果图-01.png]]
- 红色为正、蓝色为负
- 这里每个 Basis 都是一种成分的光照。（对应到影响着色上，影响的区域）
- 即，每个频率对应考虑模型表面的位置。


## PRT with Glossy

![[RT_12_环境映射_Environment_Mapping-prt_with_glossy-01.png]]

- 上图是考虑了 $\cos\theta_o$ 的不同取值，构成了矩阵的不同列。
- 这个矩阵叫做 transport matrix。形象的理解：把光照的频率，按照矩阵转移到对应的值上。
	- 进一步思考：各个角度观察看到的结果，实际上也可以理解为各个方向向外发光。

如果接近镜面反射的情况下，直接采样即可。PRT则不行。（因为不能很好的展开）


**PRT 经验数值**
- 通常选择Basis： 9/16/25 个


**考虑 Interreflections**

![[RT_12_环境映射_Environment_Mapping-prt_with_glossy-02.png|538x375]]

- L: 光照
- S: Specular （镜面 transport）
- G: Glossy （glossy transport）
- D: Diffuse （diffuse transport）
- E: 眼睛 （transport到眼睛）
- LGE：金属材质的直接光照结果
- LDE：粗糙材质的直接光照结果
- L(G|D)^2E:  一次间接光照的结果
- LSDE：打到镜面，然后到diffuse上，得到 caustics的结果。

这样，比如更多bounce。考虑第k次bounce：
- 对每次计算：里面的每个 $L_i$ 由上一次渲染结果，得到一个lightmap。
- 于是 $L_{i}^k$ 由 $L_i^{k-1}$ 得到：用 $L_i^{k-1}$ 对所有着色点（Vertex）计算光照，得到的结果，然后再这个位置方一个探针，捕获下来一个box/sphere，从而作为 $L_i^k$ 带入到公式，计算第k次bound。 $L_i^0 = L_i$ 。
- 理论做法：
	- 考虑场景中所有节点之间的可见性关系。会得到一个矩阵 $H$ （N x N 维度的）
	- 向半球方向任意采样。如果命中其他顶点，则记录这个顶点的贡献。这个是 全局光照的“公路网”。它清清楚楚地记录了光线在场景内部顶点之间“乱窜”的交通路线图。
	- 这样所有间接光照可以用 $L=(I+H+H^2+...)L^1=(I-H)^{-1}L$
- 实际中：H太大，因此会有一些工程上的近似技巧：
	- 场景里均匀放置一些probe。
	- 每个顶点把光反射给probe，然后probe的光照用球谐函数或wavelet压缩。
	- 每个顶点读取间接光照的时候，从周围的probe里读取。（假设局部间接光照一致性；或者probe上可以做一个插值）
	- 最终，H被简化为 N x Probe数量 的关系。
- 引擎的现代化做法：
	- 直接用PathTracing采样，得到，进行多次bounce。
	- 把直接采样得到的多次bounce后的光照，用SH压缩到lightmap纹理中。
	- 因为PathTracing后，可以完整得到每个Vertex的irradiance（方向下的强度），因此就是一个球面函数，可以用SH来压缩。

多次bounce后结果更加亮：
![[RT_12_环境映射_Environment_Mapping-prt_with_glossy-03.png]]


## 其他基函数
- Wavelet
	- ![[RT_12_环境映射_Environment_Mapping-其他基函数-01.png]]
	- 小波变换后：可以全频率保留，并且大部分的系数为0
	- ![[RT_12_环境映射_Environment_Mapping-其他基函数-02.png|236x321]]![[RT_12_环境映射_Environment_Mapping-其他基函数-03.png|241x317]]
	- 这里每次都分离一部分高频的阴影。
	- JPEG用了类似的DCT，得到强的压缩。

- Zonal Harmonics
- Spherical Gaussian
- Piecewise Constant

## 参考资料

PRT survey. ravi??