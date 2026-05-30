# 回顾BRDF定义
$$
f_r(\omega_i , \omega_r)=\frac{dL_r(\omega_r)}{dE_i(\omega_i)}
$$

另一个常用的形式：
$$
dL_r(\omega_r) = f_r(w_i,w_r) L_i(\omega_i)\cos\theta_i d w_i
$$
# Lambertian 漫反射
完美漫反射的模型：光照进入后，以均匀的方式，向所有方向反射。因此，BRDF函数 $f_r$ 是一个常数。
![[RT-04-材质和BRDF-lambertian-漫反射-01.png|309]]
根据渲染方程（仅考虑反射，不考虑自发光），容易推导：

$$
\begin{array}{rcl}
L_o(\omega_o) &=& \int_{H^2} f_r L_i(\omega_i) (\mathbf{n}\cdot \omega_i) d\omega_i \\
&=&  f_rL_i\int \cos\theta_i d\omega_i \\ 
&=&  f_rL_i\pi \\ 
\end{array}
$$
这里假设了入射光在各个角度为常数。因为我们只关心 $f_r$ ，所以简化入射光光源。，图形学中经常会做这种叫做 **白炉测试（White Furnace Test）** 的理想实验，**主动假设** $L_i$ 为常数来强行求解积分。

**为什么可以用白炉测试来计算BRDF？** 因为 **BRDF（$f_r$）是材质的固有几何和物理属性，它只取决于材质微表面的结构，与外界的光照环境（$L_i$）毫无关系。**

这就好比一块镜子，无论你把它放在漆黑的屋子里、五彩斑斓的霓虹灯下，还是均匀的白光大雾里（白炉），它“反光”的物理机制（反射率、粗糙度）是绝对不变的。

既然在任何光照下都不变，那为了算出它具体的数学形式，物理学家自然会选择最简单的环境——白炉环境（$L_i = 1$ 的常数环境）来做测试。

上面的式子，我们把 $L_i=1$ 带入，然后考虑光照的能量仅有 $L_o=\rho<1$ 被反射。 就可以得到 Lambertian 下的BRDF函数 $f_r = \frac{\rho}{\pi}$ 。这里 $\rho$ 也叫做 albedo color

# Glossy 反射
![[RT-04-材质和BRDF-glossy-反射-01.png]]
# 水面模型

![[RT-04-材质和BRDF-水面模型-01.png]]

## Perfect Specular Reflection(完美镜面反射)
- 反射定律：入射角等于折射角。

可以求解反射向量：
$$
\omega_o=-\omega_i + 2(\omega_i\cdot n) n
$$
## 折射定律 (Law of Refraction, Snell's Law)
- 折射定律：折射率 乘 sin 角 不变。
$$
\eta_i\sin\theta_i=\eta_t\sin\theta_t
$$

- 折射率越高，光被扭曲更大。
- 折射如果从高折射率进入到低折射率的介质，有可能导致没有折射，从而造成全反射。
## 焦散现象(caustics)

## 全反射(Total internal reflection)
全反射的角度： 当 $\eta_i>\eta_j$

对应的角度，靠带入到snell公式中，让其中一个角度为 90 度，即：  
$$
\eta_i\sin\theta_i=\eta_j
$$
得到，当 $\theta > \theta_i$ 时，发生全反射。

由于全反射的存在，因此，对于水下的观察点来说。会存在： **Snell's Window/Circle**

![[RT-04-材质和BRDF-全反射total-internal-reflection-01.png|538]]
- 容易看出这个锥体的截面夹角就是 $2\theta_i$ (其中 $\theta_i$ 是达到全反射时候的角度)
- 靠上面的公式，可以得到 $\theta_i=\arcsin(\eta_j/\eta_i)$  
	- 如果是水面到空气。两者折射率分别是：1.333, 1.00029  。带入求解，容易得到约为 $\theta_i=48.63\degree$ 。

## 刻画折射性质：BTDF
## 刻画反射+折射：BSDF

# 反射模型：Fresnel 菲涅尔项
当入射角越大，反射的能量越高。而入射角越垂直，则反射能量则相对较低。

**绝缘体（Dielectric）的 Fresnel Term**

![[RT-04-材质和BRDF-反射模型fresnel-菲涅尔项-01.png|448]]


**金属(Conduct) 的 Fresnel Term**

![[RT-04-材质和BRDF-反射模型fresnel-菲涅尔项-02.png|460]]

## 如何计算Frenel项（严格）
严谨的计算需要考虑光的极化的下两个成分分别计算：

![[RT-04-材质和BRDF-如何计算frenel项严格-01.png]]

计算复杂。通常用简化的模型

## Schlick's approximation
![[RT-04-材质和BRDF-schlicks-approximation-01.png|466]]

- 这里 $R_0$ 是基础反射率。和两个介质的折射率有关系。用折射率算出来的。
- 这个曲线当入射角变大的时候，逼近1；当入射角小的时候，接近 $R_0$ 相对小一些。

# 微表面模型（Microfacet Theory）
现实中的表面并不是光滑的，而是由大量微小的镜面片（microfacets）组成：
- 每个微表面都是理想镜面（perfect mirror）
- 表面粗糙度 = 微表面法线分布的离散程度
- 只有**法线刚好满足反射条件的微表面**会贡献反射

![[RT-04-材质和BRDF-微表面模型microfacet-theory-01.png]]

## 微表面例子

![[RT-04-材质和BRDF-微表面例子-01.png]]

- 法线如果集中，就glossy
- 法线如果分散，则diffuse
## 微表面BRDF公式
先看公式。然后对每个项详细展开讲解。

$$
f(\omega_i,\omega_o) = \frac{F(\omega_i,h)G(\omega_i,\omega_o,h)D(h)}{4(n,i)(n,o)}
$$

## 菲涅尔项 (Fresnel Term)
**入射角越大，反射能量越大**
## 几何项 (Shadowing masking term)
考虑微表面之间的互相遮挡。当入射角很大的时候，起作用，此时角度叫做grazing angle。（一些光直接被遮蔽了）
## 法线分布 (NDF)
**微表面模型下，法线的分布** （因为要考虑反射的概率，所以用 half vector 来查询法线分布，即 $D(h)$ ）


# Cook Torrance BRDF
# Wald BRDF？

# 各向异性材质 （Anisotropic Material/BRDF）
微表面有方向性。不同方向上，法线分布完全不一样。

用数学表示：
- 各向同性： $f_r(\theta_i,\phi_i;\theta_r,\phi_r)=f_r(\theta_i,\theta_r,\phi_r-\phi_i)$ ，即入射和反射角的 \phi （方位角） 的差，直接决定其值。当相对方位角差值固定的时候，（思考入射光和反射光同时围绕法线旋转），得到的brdf一样。（这就显然是各向同性） 
	- 此时，由于BRDF光路可逆性。 $f_r(\theta_i,\theta_r,\phi_r-\phi_i)=f_r(\theta_r,\theta_i,\phi_i-\phi_r)=f_r(\theta_i,\theta_r,|\phi_i-\phi_r|)$  。最后一步考虑整体镜面翻转就可以得到。
- 各向异性：上面的式子不成立，且绕着旋转的时候，f_r 取值有很大的变化。

常见案例：
- 带条纹的金属面
- 尼龙面 （Nylo）

# BRDF性质
1. 非负性
2. 线性性
3. 光路可逆性： $f_r(\omega_i,\omega_r)=f_r(\omega_r,\omega_i)$
4. 能量守恒 $\int f_r \cos\theta d\omega \le 1$ 
