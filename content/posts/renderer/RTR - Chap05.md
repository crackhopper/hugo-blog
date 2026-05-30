---
id: art_9e4b687a4ba10f142a26acf1bd4c94e0
---
# 着色模型
## Gooch Shading
**Gooch Shading （非真实感 NPR 冷暖着色）** 。经典的 ”风格化漫反射 + 硬镜面高光“ 极简模型，专门用来做 **机械 / 科幻 / 卡通硬表面** 画风。

### 动机
**传统 Phong/Blinn 问题**
- 真实感光照：明暗过渡太灰、发闷，物体轮廓、体积感不突出；
- 漫反射是纯黑白亮度变化，没有色彩倾向，风格单调；
- 高光柔滑，缺少工业 / 科幻感的「锐利高光点」。

**Gooch 模型设计目标（核心意图）**
- 不用复杂 PBR，低成本风格化渲染；
- 把「明暗亮度差异」改成冷暖色彩偏移：
	- 背光 / 暗部 → 冷色（蓝调）
	- 受光 / 亮部 → 暖色（黄 / 棕调）
- 保留一个极窄、硬切割的纯白高光，模拟金属 / 塑料锐利高光；
- 全部用基础向量运算，GPU 极轻量，早期实时渲染常用。

### 公式
**符号定义**
- $\mathbf{n}$ ： 片元世界 / 切线空间 **法线** 。（单位向量）
- $\mathbf{l}$ ：片元指向光源的单位向量。（光照反方向）
- $\mathbf{v}$ ：片元指向相机的单位向量。（视线反方向）
- $\mathbf{r}$ ：入射光（ $\mathbf{l}$ ） 对应的反射光向量 $\mathbf{r}=2(\mathbf{n}\cdot \mathbf{l})\mathbf{n} -\mathbf{l}$  


**基础颜色定义**
- `csurface` ：物体本身固有颜色 （base albedo）
- `ccool = (0, 0, 0.55) + 0.25 * csurface` ：冷色暗部，基底固定冷蓝色 `(0,0,0.55)` ；叠加25%物体固有颜色，防止染色过度。用途：漫反射暗部。
- `cwarm = (0.3, 0.3, 0.0) + 0.25 * csurface` ：cwarm 暖色亮部。基地固定暖黄 `(0.3,0.3,0)` 同样叠加 25% 固有色；用途：漫反射亮面、受光区域。
- `chighlight = (1, 1, 1)` ：纯白高光，硬边缘镜面高光专用叠加色。

核心设计： **不靠「亮度变暗」做阴影，靠冷色替代暗部、暖色替代亮部，视觉体积感更强。**

**冷暖混合系数 t**
$$
t=\frac{(\mathbf{n}\cdot \mathbf{l})+1}{2}
$$
- 当正对光照，值最大；背对光照，值最小。


**高光开关系数 s**
$$
s=(100(\mathbf{r}⋅\mathbf{v})−97)^{\mp}
$$
- $\mp$ 运算符：按照 `[0,1]` 区间截断。
- 参数的含义：
	- $\mathbf{r}\cdot \mathbf{v}>0.98$ 时， s=1 ，高光开足，此时反射方向和视角很接近。
	- $\mathbf{r}\cdot \mathbf{v}<0.97$ 时， s=0 ，高光关闭，此时反射方向和视角稍微有点偏离。
	- 内部之所以数量这么大，是为了限制高光区域，做一个足够“硬”的高光点，体现金属和科技感。

**着色公式**
$$
c_{shaded}=sc_{highlight}+(1-s)(tc_{warm}+(1-t)c_{cool})
$$
把上面结合起来，简单线性插值得到。

### 我们的实现

# 光源
## 光源着色模型
光照系统下的着色公式

$$
c_{shaded} = f_{unlit}(\mathbf{n},\mathbf{v}) + \sum_{i=1}^n c_{light_i} f_{lit}(\mathbf{l}_i,\mathbf{n},\mathbf{v})
$$

这里面：
- $f_{unlit}$ ：对应的是，没有被光照影响的着色部分。 （这个部分主要用来做一些风格化的外观；或者比如说不是直接从光源得到的颜色，例如从sky或者周围环境得到的颜色）

通常光照的能量和光源与法线夹角有关（将光理解为粒子，光线理解为一条线，光线的密度就是能量的，这个和夹角有关，正好是夹角的cos值）。因此，上面的公式可以调整为。

$$
c_{shaded} = f_{unlit}(\mathbf{n},\mathbf{v}) + \sum_{i=1}^n (\mathbf{l}_i\cdot \mathbf{n})^+ c_{light_i} f_{lit}(\mathbf{l}_i,\mathbf{n},\mathbf{v})
$$
这里，用 $^+$ 代表截断负数为0，因为此时光线从面的背面照过来，因此不影响表面着色。

最简单的 $f_{lit}$ 函数就是常量: $f_{lit}=c_{surface}$ 此时叫做 Lambertian shading model。通常作为哑光或者完美漫反射平面的颜色。是一个核心的基础着色模块。 （Blinn Phong就用了Lambertian shading model作为反射光的一部分）

## 方向光（Directional Lights）

这个是最简单的一种光源：
- $\mathbf{l}$ ： 是一个常量，在空间所有位置都是常量。
- $c_{light}$ ：是一个常量，在空间所有位置都是常量。

不过也有一些变种，会让光色（能量）部分，随着空间位置变化。常见的做法是划定一个区域被方向光影响，离开区域后就没有光照。可以提升性能，或者用来做特殊的表现风格。

## 点状光源(Punctual Lights)
对应的光源有一个位置向量 $\mathbf{p}_{light}$ 。

因此，对着色面上的一个点 $\mathbf{p}_0$ 来说，光源方向 $\mathbf{l}$ 为

$$
\mathbf{l}=normalize(\mathbf{p}_{light}-\mathbf{p}_0)=\frac{\mathbf{p}_{light}-\mathbf{p}_0}{||\mathbf{p}_{light}-\mathbf{p}_0||}
$$
为了后续更方便表述各类 Punctual Lights， 我们引入：
- $\mathbf{d}=\mathbf{p}_{light}-\mathbf{p}_0$ 这个是点到光源的距离向量
- $r=||\mathbf{d}||$ 代表点到光源的距离
- $\mathbf{l}$ 就可以写作 $\mathbf{l}=\mathbf{d}/r$

剩余的部分是光照强度（或者说颜色）的定义部分。这块根据不同的光源，公式不一样。
### 点光源 (Point Light)
点光源最主要的特点是 光 的能量会随着距离 $r$ 衰减。（显然，按照光线密度来说，是平方衰减；因为同样的能量，被扩散到更大的表面上，而表面公式和r的平方相关）。假设我们考虑在 $r_0$ 这个位置，光照强度为 $\mathbf{c}_{light_0}$ ，那么对应的光源强度公式为：

$$
\mathbf{c}_{light}(r)=\mathbf{c}_{light_0}\left (\frac{r_0}{r}\right )^2
$$
这个公式也被叫做： 光照平方反比衰减（ inverse-square light attenuation ）。

这个公式有一些问题：

**1. 当r特别小怎么办？**

常见做法有两类：
- 分母加入一个 $\epsilon$  ，防止除以0带来的问题。 $\mathbf{c}_{light}(r)=\mathbf{c}_{light_0}\left (\frac{r_0}{r+\epsilon}\right )^2$
- 或者限制分母，对其做截断，防止其变得更小。$\mathbf{c}_{light}(r)=\mathbf{c}_{light_0}\left (\frac{r_0}{\min(r, r_{min})}\right )^2$

**2. 平方衰减当r变大的时候，值衰减变慢但始终为正**

这个问题带来的主要是性能问题，即光源会影响到无限远距离的着色面。但如果直接截断，又会造成光源突然消失带来的硬边界。所以常见的做法是用一个 windowing function 来限制光源范围并平滑衰减曲线。（最终我们得到的光照公式为 $f_{win}(r) \mathbf{c}_{light}(r)$。因此，我们要求这个函数，在一个具体的数值 $f_{win}(r_{max})=0$ ，并且，光滑变化要求导数也为零， 即 $(f_{win}(r_{max})\mathbf{c}_{light}(r))'=0$

一个常见的窗口函数：

$$
f_{win}(r)=\left(\left(1-\frac{r}{r_{max}}\right)^4\right)^{+2}
$$
这里 $^{+2}$ 代表先$+$ 即截断负数，然后再平方。

![[RTR - Chap05-点光源-point-light-01.png]]

为什么有截断+平滑的效果？原因是 $f'_{win}(r_{max})=f_{win}(r_{max})=0$ ，因此会在 $r_{max}$ 处强制为0，且强制导数为0。 这个效果对于较低的空间采样率非常有必要（因为截断会带来高频，高频信号被低频采样会映入alias），比如 in light maps 或 per-vertex。

有些引擎则不会使用这个函数，反而在光源接近 $r_{max}$ 的位置改为线性插值。（意味着不能用 light map 和 vertex lighting，会影响光源采样的实际质量）

有时候，不一定需要满足 反比平方衰减 （inverse-square）。那么可以用下面的公式：

$$
\mathbf{c}_{light}(r)=\mathbf{c}_{light_0} f_{dist}(r)=\mathbf{c}_{light_0}\left(1-\left(\frac{r}{r_{max}}\right)^2\right)^{+2}
$$
上面公式用于  Just Cause 2  的光照计算。此外，Unreal中还引入了指数衰减的光源，有的还会用样条来做光源衰减。光源衰减可以刻画比较特别的视觉效果，比如，恐怖游戏的效果（通常更快的衰减光源）。


|效果|attenuation 行为|
|---|---|
|安全感|大范围柔和|
|压迫感|小范围急衰减|
|神秘感|边界模糊|
|聚焦|中心高亮|
|孤独感|周围快速掉黑|
|舞台感|聚光灯式衰减|
### 聚光灯 (Spotlights）
聚光灯则需要在点光源上，引入一个方向性的衰减 (directional falloff) 函数 $f_{dir}(\mathbf{l})$ ，因此最终的公式为：

$$
\mathbf{c}_{light}(r)=\mathbf{c}_{light_0} f_{dist}(r)f_{dir}(\mathbf{l})
$$
聚光灯的特点是光会聚集在特定的锥形中。

设：
- $\theta_s$ 为光线和聚光灯中心线的夹角
- $\theta_u$ 本影角（umbra angle）（也叫做： outer cone/cutoff angle ）。光照完全截止区域（zero intensity region）的边界角。即 （ $\text{if }\theta_s>\theta_u, f_{dir}=0$)
- $\theta_p$ 半影角（penumbra angle）（也叫做：inner cone/full-light angle）全亮区域（full intensity region）的边界角。即 （ $\text{if }\theta_s<\theta_p, f_{dir}=1$)

![[RTR - Chap05-聚光灯-spotlights-01.png]]

最常见做法就是在 $\cos\theta_p$ 和  $\cos\theta_u$ 之间插值。这里用 $\mp$ 运算符代表，0到1之间的截断。公式整体为：

$$
\begin{array}{rcl}
t&=&\left(\frac{\cos\theta_s-\cos\theta_u}{\cos\theta_p-\cos\theta_u} \right)^\mp \\
f_{dir_F} &=& t^2 \\ 
f_{dir_T} &=& \text{smoothstep}(t)=t^2(3-2t) \\ 
\end{array}
$$

这里：
- $f_{dir_F}$ 是 Frostbite 引擎用的公式
- $f_{dir_T}$ 则是 three.js 渲染器用的公式

这里面引入了一个光滑函数。采用复合函数/重参数化的技巧，让边缘点过度更加光滑（即边缘的变化速度趋于0）。

### 其他类型点状光源
这里面值得一提的是： IES格式 （Illuminating Engineering Society）。属于行业协会定义的，基于真实灯光测量得到的光照分布数据。部分游戏引擎直接支持这个格式，方便在游戏中还原真实世界灯光。

此外，还有跟随事件变化进行抖动的光源强度的做法。可以表达 flickering torch的效果。

## 线面光源
我们这里先忽略。这块涉及到对光照区域积分，以及soft shadow等相关内容。
# 补充
## windowing function v.s. smoothstep
smoothstep 的本质 **“重新参数化（reparameterization）”**
- 改变插值节奏
- 改变 easing
- **保持端点值**
- 调整中间曲率
- 此外，通常也让端点处导数为0

window function 的本质 **“乘法遮罩”**
- 限制 support
- 截断范围
- 保证边界消失
- 此外，通常也让截断处导数为0

**smoothstep 更像“坐标变换”** （不影响值域）， **window 更像“振幅衰减”** （影响值域）

**两者都能“修复边界不光滑”** 只是机制不同：
- 一个靠乘法零化
- 一个靠链式法则零化

这两个function都属于 shaping functions：用来控制函数行为、边界、过渡、支撑域、导数连续性的函数。

| 类型            | 数学操作                           |
| ------------- | ------------------------------ |
| smoothstep    | composition                    |
| window        | multiplication                 |
| attenuation   | multiplication                 |
| easing        | reparameterization             |
| bump function | compact-support smooth masking |
