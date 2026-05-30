
# PBR 材质
- 表面：主要是 microfacet 和 disney principled
- 体积：困难一些。（single scattering 和 multiple scattering）
- 通常不用太多新理论，主要用hacks+离线渲染的理论
# Microfacet BRDF
## Recap
![[RT-14-基于物理的材质 (PBR, PBR Materials)-recap-01.png|546x370]]


## Fresnel Term
菲涅尔现象：入射方向越偏，反射能量越高。
### Schlick approximation

## Normal Distributin Function (NDF)
### Backmann
$$
D(h)=\frac{1}{\pi\alpha^2\cos^4\theta_h} e^{-\frac{\tan^2\theta_h}{\alpha^2}}
$$
- $\alpha$ : 粗糙度 , $\theta_h$ ：查询的角度
- 表示各向同性。
- 定义到坡度空间上 (slope space)
	- ![[RT-14-基于物理的材质 (PBR, PBR Materials)-backmann-01.png|184|198x186]]
	- 在上面的平面上定义了高斯函数。
	- 即，一个角度（即$\theta$），对应的法向的密度（相当于如图的画线，可以得到一个x值）。然后带入到高斯函数，得到这个方向的法线密度。即 Gaussian(\tan\theta)。

### GGX (Trowbridge-Reitz)

公式：
$$D_{GGX}(N, H, \alpha) = \frac{\alpha^2}{\pi ((N \cdot H)^2 (\alpha^2 - 1) + 1)^2}$$
- $N$: 宏观表面法线
- $H$: 半角向量
- $\alpha$ ：粗糙度。通常，美术调节的是 $\alpha^2$ 。

**好处：更加长尾**
![[RT-14-基于物理的材质 (PBR, PBR Materials)-ggx-trowbridge-reitz-01.png]]
好的性质：
- 高光边缘更加柔和，有光晕。
- 对于diffuse，描述也更好
 
![[RT-14-基于物理的材质 (PBR, PBR Materials)-ggx-trowbridge-reitz-02.png]]

### GTR (Generialized Trowbridge-Reitz)

![[RT-14-基于物理的材质 (PBR, PBR Materials)-gtr-generialized-trowbridge-reitz-01.png|662]]

## Geometry Term (Shadowing-Masking Term)
解决微表面自遮挡问题。同时，避免grazing angle下，分母接近0导致渲染白色的问题。

![[RT-14-基于物理的材质 (PBR, PBR Materials)-geometry-term-shadowing-masking-term-01.png|665]]
### Smith Shadowing-masking term
在无线通信、雷达探测以及计算机图形学（光学漫反射/镜面反射）中，Smith 阴影遮蔽函数（Smith Shadowing-Masking Function）是一个非常经典的物理模型。

当粗糙表面受到电磁波或光线照射时，会发生两种阻挡现象：
- **阴影 (Shadowing)：** 入射光被粗糙表面的微小山峰挡住，导致某些区域根本“照不到”。
- **遮蔽 (Masking)：** 反射光在离开表面时，被旁边的微小山峰挡住，导致观察者（或接收机）“看不到”。

Smith 模型就是通过统计学方法，完美计算出这两者共同作用下的**未被阻挡的概率**。

最经典的形式是将阴影和遮蔽拆解为两个独立项的乘积（虽然严格来说它们有相关性，但分离式在工程上最常用）：

$$G(\mathbf{l}, \mathbf{v}, \mathbf{h}) \approx G_1(\mathbf{l}) \cdot G_1(\mathbf{v})$$

其中：
- $G_1(\mathbf{l})$ 是**入射方向**的可见性概率（阴影项）。
- $G_1(\mathbf{v})$ 是**观察方向**的可见性概率（遮蔽项）。

对于符合高斯分布的表面，$G_1$ 的标准 Smith 形式为：

$$G_1(\mathbf{v}) = \frac{1}{1 + \Lambda(\nu)}$$

这里的 $\Lambda(\nu)$ 是一个与表面粗糙度 $\alpha$ 和入射/观察夹角（$\theta$）相关的几何积分函数。角度越倾斜（擦着表面），$\Lambda$ 越大，$G_1$ 越接近 0（阻挡越严重）；角度越垂直表面，$G_1$ 越接近 1（无阻挡）。


在 Smith 1967 年的原始论文以及无线通信、雷达散射领域中，通常假设表面粗糙度符合高斯正态分布。

定义变量 $a$（表示表面坡度与粗糙度的相对关系）：

$$a = \frac{1}{\alpha \tan\theta}$$

其中：

- $\theta$ 是入射角或观察角（与宏观表面法线的夹角）。
    
- $\alpha$ 是表面的粗糙度参数。
    

在高斯分布下，$\Lambda(a)$ 的精确解析式为：

$$\Lambda(a) = \frac{1}{2} \left( \frac{\exp(-a^2)}{\sqrt{\pi} \cdot a} - \text{erf}(c) + 1 \right)$$

- $\text{erf}(x)$ 是误差函数（Error Function）。
- 因为这个高斯公式包含误差函数，在计算机图形学中计算量太大，所以现在更常用下面这种分布。


对于 GGX 分布，$\Lambda(\mathbf{v})$ 有一个非常优雅、没有误差函数的纯代数解。定义 $\mathbf{v}$ 为观察方向（或入射方向 $\mathbf{l}$）：

$$\Lambda(\mathbf{v}) = \frac{-1 + \sqrt{1 + \alpha^2 \tan^2\theta}}{2}$$

为了方便计算机硬件（GPU）计算，图形学大牛 Eric Heitz 等人将其展开并写成了**无三角函数**的向量点积形式（更适合 Shader 编程）：

$$\Lambda(\mathbf{v}) = \frac{-1 + \sqrt{1 + \alpha^2 \frac{1 - (\mathbf{n} \cdot \mathbf{v})^2}{(\mathbf{n} \cdot \mathbf{v})^2}}}{2} = \frac{\sqrt{(\mathbf{n} \cdot \mathbf{v})^2 + \alpha^2(1 - (\mathbf{n} \cdot \mathbf{v})^2)} - (\mathbf{n} \cdot \mathbf{v})}{2(\mathbf{n} \cdot \mathbf{v})}$$

其中：

- $\mathbf{n}$ 是宏观表面法线。
- $\mathbf{v}$ 是视线方向向量。
- $\mathbf{n} \cdot \mathbf{v} = \cos\theta$。


拿到 $\Lambda(\mathbf{v})$ 后，单向的可见性函数 $G_1(\mathbf{v})$ 就是：

$$G_1(\mathbf{v}) = \frac{1}{1 + \Lambda(\mathbf{v})}$$

如果代入上面 **GGX 分布**的的 $\Lambda(\mathbf{v})$，分母上的 $+1$ 和 $\Lambda$ 中的 $-1$ 刚好抵消，化简后会得到非常漂亮的经典 **GGX-Smith 单向遮蔽公式**：

$$G_1(\mathbf{v}) = \frac{2(\mathbf{n} \cdot \mathbf{v})}{(\mathbf{n} \cdot \mathbf{v}) + \sqrt{\alpha^2 + (1 - \alpha^2)(\mathbf{n} \cdot \mathbf{v})^2}}$$

$\Lambda$ 的物理直觉：看作是一个“阻挡系数”。
-  当视角垂直于表面时（$\theta = 0^\circ$），$\tan\theta = 0$，此时 $\Lambda = 0$，代入 $G_1 = \frac{1}{1+0} = 1$（完全没有阻挡，100% 可见）。
- 当视角逼近地平线时（$\theta \to 90^\circ$），$\tan\theta \to \infty$，此时 $\Lambda \to \infty$，代入 $G_1 = \frac{1}{1+\infty} = 0$（阻挡无穷大，完全不可见）。

## Problem: 多次弹射-能量损失
![[RT-14-基于物理的材质 (PBR, PBR Materials)-problem-多次弹射-能量损失-01.png]]

粗糙度高了之后，越来越暗。能量损失了。 （下面的就是白炉测试，希望都是白色）

由于实时渲染微表面弹射1次，很多光线没有进入到眼睛，从而导致光照能量缺失。

### Kulla-Conty Approximation
用经验模型，补全由于多次弹射，没有计算所损失的能量。

对brdf积分

$$
E(\mu_o)=\int_0^{2\pi}\int_0^1 f(\mu_o,\mu_i,\phi)\mu_id\mu_id\phi
$$
这个积分损失的值就是缺失的能量。

- 我们可以在观察方向lobe上，补上 $1-E(\mu_o)$

构造 brdf补偿项(考虑 reciprocity) ： 使得积分得到 ：$c(1-E(\mu_i))(1-E(\mu_o))$ 。

![[RT-14-基于物理的材质 (PBR, PBR Materials)-kulla-conty-approximation-01.png]]

最终，设计的brdf：
$$
f_{ms}(\mu_o,\mu_i)=\frac{(1-E(\mu_o))(1-E(\mu_i))}{\pi(1-2\int_0^1 E(\mu)\mu d\mu)}
$$

但这里分母要求积分，很复杂：预计算，打表。


最终，我们计算光照用的整体的brdf加上这个补偿的 brdf。

因为 $E(\mu)$ 取决于**两个变量**：粗糙度（Roughness $\alpha$）与 角度余弦（$\mu$），所以它必须是一张 2D 纹理。
而 $E_{avg}$ 只取决于**一个变量**：粗糙度（Roughness $\alpha$）。 为了节省显存和采样次数，我们会这样设计这张 2D 纹理：

- **横坐标（U轴）**：对应 $\mu$（即 $\vec{N}\cdot\vec{V}$ 或 $\vec{N}\cdot\vec{L}$），范围 $[0, 1]$。
- **纵坐标（V轴）**：对应粗糙度 $\alpha$ (Roughness)，范围 $[0, 1]$。

**通道分配方案：**

- **R 通道（红色）**：存储 **$E(\mu, \alpha)$**。因为它随着角度 $\mu$ 和粗糙度 $\alpha$ 改变，所以在整张图上每个像素的值都不同。
- **G 通道（绿色）**：存储 **$E_{avg}(\alpha)$**。因为它只跟粗糙度有关，所以在“同一行（即相同的 $\alpha$）”上的所有像素值都是完全一样的（相当于沿着横轴拉伸复制）。

补偿后：

![[RT-14-基于物理的材质 (PBR, PBR Materials)-kulla-conty-approximation-02.png]]


## Problem: 多次弹射-颜色被多次吸收
为什么“有颜色材质”必须引入 Fresnel 颜色补偿？

现实世界中，几乎没有 100% 全反射的材质。比如**黄金**（吸收蓝绿光，反射红黄光）或**铜**。

当一束白光射入高粗糙度的黄金表面时，物理过程变成了这样：
- **第 1 次碰撞**：光线没逃逸出来。因为黄金只反射部分光，它**吸收了一部分蓝绿光**。此时光线已经开始变黄，且能量减弱了。
- **第 2 次碰撞**：光线还是没出来。它在微表面内部又撞了一次黄金表面，**再一次被吸收了蓝绿光**。光线变得更黄、更暗了。
- **第 3 次碰撞**：……
    

你看，光线在微表面内部每“反复横跳”弹射一次，就会**被材质剥掉一层皮（吸收一次能量）**。
- 如果材质是**纯白**的，弹射 5 次出来的光，亮度依然是 100%。
- 如果材质是**有颜色（如黄金）**的，弹射 5 次出来的光，就会连续乘以 5 次黄金的菲涅尔颜色（$F_{avg}^5$）。这会导致逃逸出来的光**不仅亮度变暗了，而且颜色会变得极度饱和（黄得发红）**。
    

因此，为了模拟这种“每撞击一次就改变一次颜色和能量”的物理现象，我们就不能只计算逃逸比例了，必须把材质的反射率（菲涅尔项 $F_{avg}$）通过等比数列求和引入进来。



定义平均Frensel项
$$
F_{avg}=\frac{\int_0^1 F(\mu)\mu d\mu}{ \int_0^1 \mu dmu} = 2\int_0^1 F(\mu)\mu d\mu
$$

假设光线射入表面，单次反射的平均能量比例是 $E_{avg}$（这就是你之前积分算出来的），而每一次碰撞表面时，材质能反射出来的颜色/能量比例由菲涅尔平均值 $F_{avg}$ 决定。

- **第 1 次碰撞（单次反射）**：光线出来，携带的能量/颜色是：
    $$F_{avg} \cdot E_{avg}$$
    
- **第 2 次碰撞（双次反射）**：光线没有出来（损失了 $1 - E_{avg}$），再次碰撞表面并反射出来的能量是：
    $$(F_{avg} \cdot E_{avg}) \times F_{avg}(1 - E_{avg})$$
    
- **第 3 次碰撞**：光线依然没出来，继续弹射：
    $$(F_{avg} \cdot E_{avg}) \times \left[ F_{avg}(1 - E_{avg}) \right]^2$$
    

如果你把第 2 次、第 3 次……直到无数次弹射出来的能量全部加起来，这在数学上是一个标准的**无穷等比数列求和**！

利用等比数列求和公式 $\sum_{n=1}^{\infty} a \cdot q^{n-1} = \frac{a}{1-q}$，其中首项 $a = F_{avg}(1-E_{avg})$，公比 $q = F_{avg}(1-E_{avg})$，最终推导出来的多次散射补偿系数就是：

$$\frac{F_{avg}}{1 - F_{avg}(1 - E_{avg})}$$


最周整体的brdf：
$$f_{total} = f_{ss} + \frac{F_{avg} \cdot f_{ms}}{1 - F_{avg}(1 - E_{avg})}$$

效果图：

![[RT-14-基于物理的材质 (PBR, PBR Materials)-problem-多次弹射-颜色被多次吸收-01.png]]


# 面光源下求解(Linearly Transformed Consines)
如何基于 Microfacet BRDF 下进行shading？

**主要考虑多边形光源！**

如果没有LTC，就需要采样来积分了。（计算量大）

![[RT-14-基于物理的材质 (PBR, PBR Materials)-面光源下求解linearly-transformed-consines-01.png]]

思路，把一个 brdf 的lobe 变换一下，转化成了cosine 。

![[RT-14-基于物理的材质 (PBR, PBR Materials)-面光源下求解linearly-transformed-consines-02.png]]

更具体的方法：

![[RT-14-基于物理的材质 (PBR, PBR Materials)-面光源下求解linearly-transformed-consines-03.png|665]]


公式上（把brdf直接变成cos函数；这里的cos不考虑\phi参数的影响）

![[RT-14-基于物理的材质 (PBR, PBR Materials)-面光源下求解linearly-transformed-consines-04.png|599x365]]


**点光源呢？直接算即可； IBL呢？通常用之前讲过的split sum来算即可；这里主要解决面光源，而为了具体求解，涉及到复杂的推导。不过Cook-Torrance模型下，brdf都是参数化的，总之是能推导出来的**


# Disey principled BRDF
1. 微表面模型，不能很好的fit真实的BRDF。 （尤其是多层材质的问题）
2. 用户不友好。尤其是对美术设计师，不友好。

disney做法是开源的。且为了更好的使用，很多做了拟合。并把可调参数范围设置到0-1之间。


![[RT-14-基于物理的材质 (PBR, PBR Materials)-disey-principled-brdf-01.png]]
- subsurface：物理上：光线能进入并退出。视觉上：会有比diffuse还要平的效果。视觉上比那的更软，比如：皮肤、玉石、蜡烛。
- metallic：物理上：关闭漫反射，镜面反射金属的颜色，specular影响被金属度覆盖；视觉上：金属性。（通常要么0，要么1）
- specular：物理上：启用漫反射，镜面反射光源颜色，specular影响高光强度。视觉上：镜面反射。（通常非金属才调整这个）
- specularTint：物理上：让镜面反射可以待一些底色。视觉上：控制高光色泽，接近材质本身的颜色。应用：丝绸、天鹅绒、昆虫甲壳等。 （所以，specular+specularTint，可以接近伪金属质感）
- roughness：物理上：微表面法向分布。视觉上：粗糙度。应用：抛光大理石、磨砂塑料
- anisotropic：物理上：模拟表面微观结构具有方向性（Directional）的微小刮痕或纹理。视觉上：将原本圆形的镜面高光点，沿着某个方向**拉伸成一条长线** 。应用：拉丝金属、CD盘、头发/丝绸。
- sheen和 sheenTint(光泽度、光泽色调)：**物理上：** 模拟织物表面那些密密麻麻、垂直竖立的微小纤维（Peach Fuzz / 边缘绒毛）**对光线的捕获和前向散射。这种微观纤维在物体正面看时不明显，但在**掠射角（边缘）时会聚集并反射大量微弱的光。 视觉上：更多毛刺感、柔软的感觉。应用上：各种布料、天鹅绒、水果表面绒毛等等。
- clearcoath和clearcoatGlass（清漆层、清漆光泽度）：**物理上：** 在基础材质（Base Layer）之上，物理性地**堆叠第二层完全透明的、具有独立粗糙度的非金属折射层**（其折射率 IOR 固定为 1.5，即 $F_0 = 0.04$）。光线会先穿过这层透明清漆（发生第一次反射/折射），然后再照到下面的基础材质上。视觉上：创造出“双层高光”的效果。一个是底层材质（比如粗糙的金属）带来的模糊高光，另一个是表面透明清漆层带来的非常锐利、清澈的表面高光。应用上：**打蜡的皮鞋、涂了亮光漆的木制小提琴、刚洗完带有水渍的表面**。

## 参数性质总结
| **参数名称**                                    | **物理本质（Shader 内部在干嘛）**                                             | **视觉核心特征（眼睛看到了什么）**                        | **经典应用场景 / 艺术家直观理解**                                              |
| ------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------ | ----------------------------------------------------------------- |
| **`Subsurface`**<br><br>  <br><br>次表面散射     | 光线射入非金属内部，发生深度散射、透射后从其他位置退出表面。                                     | 模糊并消除生硬的明暗交界线（产生散射过渡带），边缘透光。               | **视觉变“软”：** 皮肤、玉石、蜡烛、牛奶、肥皂。                                       |
| **`Metallic`**<br><br>  <br><br>金属度         | 自由电子瞬间吸收折射光。**关闭漫反射（Diffuse = 0）**，镜面反射 $F_0$ 变为 RGB 矢量。           | 暗部死黑（全靠环境反射显色），高光直接呈现 `Base Color` 的颜色。    | **视觉变“硬/冷”：** 金、银、铜、铁、电镀表面（通常非 0 即 1）。                            |
| **`Specular`**<br><br>  <br><br>镜面反射度       | 决定**非金属**正面垂直入射时的反射率 $F_0$（公式：$F_0 = 0.08 \cdot \text{Specular}$）。 | 控制非金属正面对光源的反射敏感度（高光强度）。高光永远是无色（白色）的。       | **调节非金属反光：** 默认 0.5 ($\text{IOR}\approx1.5$) 涵盖多数非金属；宝石可调高，全哑光调低。 |
| **`SpecularTint`**<br><br>  <br><br>镜面反射色调  | 艺术化打破物理限制，将 `Base Color` 的颜色部分注入到非金属的镜面反射中。                        | **非金属**的表面高光从纯白色变成带有材质固有色的彩色高光。            | **高光融入材质：** 丝绸、天鹅绒、昆虫甲壳、有色有光泽的特殊涂层。                               |
| **`Roughness`**<br><br>  <br><br>粗糙度        | 模拟物体微观表面“微几何结构”的粗糙平整程度。                                            | 决定高光点的形状：数值越低高光越**小而锐利**；数值越高高光越**大而模糊**。  | **决定材质新旧与质感：** 抛光大理石/镜子（低） vs 磨砂塑料/旧木头（高）。                        |
| **`Anisotropic`**<br><br>  <br><br>各向异性     | 模拟表面微观坑洼被拉伸成具有**方向性**的平行刮痕。                                        | 将原本圆形的镜面高光点，沿着垂直于刮痕的方向**拉伸成一条长线**。         | **具有方向性的反射：** 拉丝金属（锅底、手表盘）、CD光盘、头发丝。                              |
| **`Sheen`**<br><br>  <br><br>绒毛光泽           | 模拟织物表面密密麻麻、垂直竖立的微小纤维对光线的捕获和前向散射。                                   | 在物体的**边缘（掠射角）**增加一层柔和的、像雾一样的亮边。            | **赋予布料灵魂：** 衣服、布料、丝绸、天鹅绒，或桃子等带有绒毛的水果。                             |
| **`SheenTint`**<br><br>  <br><br>绒毛色调       | 控制 `Sheen` 产生的边缘亮边的颜色倾向。                                           | `0` 时边缘亮边为白色；`1` 时亮边强行染上 `Base Color` 的颜色。 | **织物微调：** 让有色织物（如红色丝绸）的边缘绒毛高光呈现出红色，更显高级。                          |
| **`Clearcoat`**<br><br>  <br><br>清漆层        | 在基础材质之上物理性地堆叠第二层完全透明、折射率固定（$\text{IOR}=1.5$）的非金属层。                 | 创造出**“双层高光”**：能同时看到底层的模糊高光和表面清漆层极锐利的镜面反射。  | **高级外壳涂层：** 汽车烤漆、打蜡的皮鞋、涂了亮光漆的小提琴、碳纤维表面。                           |
| **`ClearcoatGloss`**<br><br>  <br><br>清漆光泽度 | 控制最外层透明清漆层的粗糙程度。（和粗糙度相反）                                           | 数值越高，最外层的清漆高光越像镜子一样锐利清晰。                   | **控制车漆新旧：** 新车/刚洗过的车（高 Gloss），老旧落灰的车漆（低 Gloss）。                   |
## 优缺点
优点：
- 容易理解和控制（适合美术设计师）
- 非常大的范围的材质都支持
- 开源的
- 巨大的参数空间：拟合能力强，可以基于真实拍摄的东西来反向拟合brdf。
- 设计上，保证了能量守恒

缺点：
- 巨大的参数空间：有冗余，难以训练。
- 不完全基于物理，但不是很大问题。
- 实时性的渲染上，目前支持度不高（因为需要针对这套重新做各种积分计算）

# Non-photorealistic rendering(NPR)
快速稳定的风格化。
## 目标
产生 artistic appearances

![[RT-14-基于物理的材质 (PBR, PBR Materials)-目标-01.png|473]]

## 特点(Characteristics)
步骤：
- 从真实感的渲染开始
- Exploit abastraction （决定处理的点）
- Strengthens important part （强化重要的部分）

## 案例分析

![[RT-14-基于物理的材质 (PBR, PBR Materials)-案例分析-01.png]]

有哪些效果，或者说处理的手段？
- 描边
- 颜色更重视过度。更加色块化。
- 表面上更强的strokes。
- 光影边缘比较重，但做了模糊处理。

## Outline Rendering

![[RT-14-基于物理的材质 (PBR, PBR Materials)-outline-rendering-01.png]]

- Sihouette edge ：轮廓/边缘，必须处于渲染的最外层。（有多个面共享）
- Boundary：边缘。（仅由一个面拥有）
- Crease：折痕。与Boundray互斥。

### Shading方法 (Sihouette边)

#### 方法一：利用法向

![[RT-14-基于物理的材质 (PBR, PBR Materials)-方法一利用法向-01.png]]

**问题：不同位置描边粗细不一样**

#### 方法二：利用Geometry
把背面三角形放大。直接指定一个颜色进行渲染。

如何扩大背面的边？

![[RT-14-基于物理的材质 (PBR, PBR Materials)-方法二利用geometry-01.png]]
- 边扩
- 法线扩

很常用

### Image上的方法

CV常见做法。《数字图像处理：冈萨雷斯》

![[RT-14-基于物理的材质 (PBR, PBR Materials)-image上的方法-01.png]]

锐化：找到边缘，然后强化边缘。

此外，可以不用color。用：法线、深度等等的。都可以找到边界。

## Color Blocks

![[RT-14-基于物理的材质 (PBR, PBR Materials)-color-blocks-01.png]]

- 阈值化/量化。让颜色落到某个区间。

不同的位置/不同的组件，不同的风格化：
![[RT-14-基于物理的材质 (PBR, PBR Materials)-color-blocks-02.png]]

## Strokes Surface Stylization
素描效果：用格子的密度来表示明暗效果

![[RT-14-基于物理的材质 (PBR, PBR Materials)-strokes-surface-stylization-01.png]]

做法：不同密度的纹理：

![[RT-14-基于物理的材质 (PBR, PBR Materials)-strokes-surface-stylization-02.png]]

- 根据明暗，找到一张图。然后用纹理贴图，可以更好的连续性。
- mipmap：缩小了之后，密度不变。这样当距离远了之后，保证密度不变。 


# 复杂材质
毛发之类的
## RTE
## BSSRDF
## single/multiple scattering
## delta tracking
## dual scattering
## layered materials
