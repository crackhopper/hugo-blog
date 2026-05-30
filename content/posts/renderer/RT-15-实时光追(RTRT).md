# RTRT概要
目前只能做到 1 spp (一个像素一个样本 1 sample per pixel) 。（性能 RT Core提供 1G per second的光线并行的能力）


## 什么是1 SPP
1SPP path tracing = 
- 1 rasterization(primary) （所以，一趟光栅化的结果，保存一下。然后继续做后面的）
- 1 ray (primary visibility)
- 1 ray (secondary bounce)
- 1 ray (secondary visibility)

![[RT-15-实时光追(RTRT)-什么是1-spp-01.png|464]]

这个结果，noisy。

 **RTRT最关键的技术：Denoising**

## 降噪的效果

![[RT-15-实时光追(RTRT)-降噪的效果-01.png]]

## 目标(with 1SPP)
- Quality (no overblur, no artifacts, keep all details)
- Speed (<2 ms to denoise one frame)

用下列都不能做：
- Sheared filtering series (SF,AAF,FSF,MAAF,...)
- Other offline filtering methods (IPP, BM3D, APR, ...)
- Deep learning series (CNN, Autoencoder, ...)

实际做法： Temporal
- 假设上一帧是滤波好了的，并且可以reuse
- 使用 motion vector ，找到 previous location （像素点的一一对应）
- 直接复用上一帧，提升SPP效果。

# 具体技术路线
## The G-Buffers
- 逐pixel的几何信息，保存到buffer中；就是一个前置的pass。

![[RT-15-实时光追(RTRT)-the-g-buffers-01.png]]

## Back Projection
找当前i帧像素x的内容，在i-1帧的位置？

![[RT-15-实时光追(RTRT)-back-projection-01.png]]

方法：
1. 当前i帧，x点的世界坐标。 s (或者从G-Buffer中直接取到，或者逆变换)
2. 前一帧 i-1 ：
	1. 假设 世界坐标 的运动也知道（因此要保存） 。所以 $s'=T^{-1}s$ 
	2. 利用上一帧的 MVP变换 $x'=P'V'M's'$

因此，可以百分百算出来，每个像素上一帧的位置。


## Temporal Accum./Denoising

1. 当前帧，做一次空间上的滤波 
	1. $\bar{C}^i=Filter[\tilde{C}^i]$
2. 当前帧，利用 motion vector，把上一帧对应位置的信息进行融合
	1. $\bar{C}^i=\alpha \bar{C}^i +(1-\alpha) \bar{C}^{i-1}$

如何选取alpha呢？0.1-0.2 

## Temporal Failure

**1. 切换场景（switching scenes）**

需要一段时间 burn-in period（预热一段时间）

**2. 倒退着走的问题（walking backwards in a hallway）** 

突然出现大量之前没有的点。

**3. 突然出现的背景（suddenly appearing background；disocclusion）**

同样，被遮挡的突然显示出来。


强行用：造成的问题 Lagging。


## Adjustments to Temporal Failure
都存在问题： re-introducing noise
### Clamping
特殊的位置，融合的时候，更看重当前的渲染结果。（把上一帧信息，拉到当前帧）

![[RT-15-实时光追(RTRT)-clamping-01.png]]

即，融合前先clamp。

### Detection
额外做一次判断，判断是否是同一个物体。找出来，motion vector不生效的情况。由两个方法：
- 调整alpha，更考虑当前帧
- 强化当前帧的空间filter

## More Temporal Failure

**光源移动的情况**

![[RT-15-实时光追(RTRT)-more-temporal-failure-01.png]]


**glossy反射的问题**

反射会需要更多时间，才能出现。（滞后效果，lagging）。

## 空间滤波：Gauss Filter实现

比较大范围的滤波

![[RT-15-实时光追(RTRT)-空间滤波gauss-filter实现-01.png]]


## 双边滤波 （Bilateral Filter）
希望高斯滤波的同时，边缘的高频也保留。

- 如果 pixel j和 pixel i是否相差很大？
	- 是：不融合，或者说，权重降低。
	- 否：融合，或者说，权重提升。

![[RT-15-实时光追(RTRT)-双边滤波-bilateral-filter-01.png]]

![[RT-15-实时光追(RTRT)-双边滤波-bilateral-filter-02.png]]

**问题：对于高噪声的图，很多时候分不清边缘和噪声**

## 联合双边滤波 (Joint Bilateral Filter/Cross Bilateral Filter)
引入更多的约束。之前考虑了颜色value的差距。

我们用G-Buffer来，携带更多信息，指导滤波

![[RT-15-实时光追(RTRT)-联合双边滤波-joint-bilateral-filtercross-bilateral-filter-01.png]]

考虑G-Buffer中的三种信息：
- Depth
- Normal
- Color （光栅化结果）

具体原理：
- **深度** 如果深度差距大，就削弱滤波权重。
- **法线** 法线夹角差距大，就削弱滤波权重。
- **光栅化颜色** 如果差距大，就削弱滤波权重。

最终，权重的影响其实都是相乘的。

## Implementing Large Filters
### Solution 1: Separate Pass
![[RT-15-实时光追(RTRT)-solution-1-separate-pass-01.png]]

- 对gaussian来说的化，是合法的。可以直接拆分。（不过对修改的kernel就不是了）
- 实际上是用low-rank filter来逼近原来的filter。

![[RT-15-实时光追(RTRT)-solution-1-separate-pass-02.png]]

实际上，我们强行用。

### Solution 2: Progressiely Growing Sizes
类似CNN。用小的核做多次。

考虑 a-trous wavelet ：（5x5 的filter，但是调节间隔）

![[RT-15-实时光追(RTRT)-solution-2-progressiely-growing-sizes-01.png]]

直观理解：
- Why growing sizes?
	- applying larger filter == removing lower frequencies
- Why is it safe to skip sample?
	- sampling == repeating the spectrum

![[RT-15-实时光追(RTRT)-solution-2-progressiely-growing-sizes-02.png]]

## Outlier Removal
过亮和过暗的点？滤波之前处理掉。

### Detection
用分位数过滤呗。（各种类似的情况）找到概率上小的点。

![[RT-15-实时光追(RTRT)-detection-01.png]]

### Clamping
把outlier，clamp到我们定好的范围。

工业上实现会更加复杂。不会简单的clamp。

# Specific Filter For RTRT
## Spatiotemporal Variance-Guide Filter(SVGF)
Joint Bilateral Filtering

深度权重衰减

$$
w_z=exp(-\frac{z(p)-z(q)}{\sigma_z|\nabla z(p)\cdot(p-q)|+\epsilon})
$$
- 深度的梯度是什么？沿着法线方向的深度的变化。（即考虑，切平面上的深度差异，而不是视角的深度差异）


法线衰减
$$
w_n=max(0,n(p)\cdot n(q))^{\sigma_n}
$$
- 指数控制衰减的速度。
- 如果应用了法线贴图，那么不用法线贴图的normal。

颜色衰减
$$
w_l=exp(-\frac{|l_i(p)-l_q(q)|}{\sigma_l \sqrt{g_{3\times 3}(Var(l_i(p)))}+\epsilon})
$$
- Variance。当方差大的时候，归一化一下；这样判断颜色距离会更准。
	- 在空间 7x7 上，统计样本
	- 在时间上用 motion vector 统计样本
	- 最后，空间上 3x3 再统计一次。得到更准确的方差估计。

**改进：A-SVGF**

## RAE

用 Recurrent denoising AutoEncoder:
- 输入 G-Buffer + noisy RTRT
- 输出 滤波好的结果
- 此外，recurrent保证了利用temporal信息。

![[RT-15-实时光追(RTRT)-rae-01.png]]