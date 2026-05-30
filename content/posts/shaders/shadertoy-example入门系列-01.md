---
id: art_d82c8c5cd333bc57b1ce5bdf2ad08fed
---

# 案例
![[shadertoy-example入门系列-01-案例-01.png|606]]

例子： https://www.shadertoy.com/view/NXf3Rf

完整代码：
```glsl
// "The Quantum Core v2.0" - Visualizador de Grado Profesional ($300 USD)
// Geometría de cristal, refracciones reales y reactividad por bandas.
// iChannel0: Audio (Indispensable)

#define T iTime

// --- FUNCIONES DE ALTA PRECISIÓN ---
mat2 rot(float a) { float c=cos(a), s=sin(a); return mat2(c,s,-s,c); }

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0);
}

// Reactividad limpia
float getBass() { return pow(texture(iChannel0, vec2(0.05, 0.25)).x, 2.0); }
float getMid() { return texture(iChannel0, vec2(0.4, 0.25)).x; }

// --- EL NÚCLEO (Geometría que no genera bloques sólidos) ---
float map(vec3 p) {
    float bass = getBass();
    vec3 q = p;
    
    // El núcleo: un octaedro que se abre con el audio
    q.xy *= rot(T * 0.5 + bass);
    q.yz *= rot(T * 0.3);
    
    // Geometría fractal simple para evitar el "bloque sólido"
    for(int i=0; i<3; i++) {
        q = abs(q) - 0.2 - bass * 0.1;
        q.xy *= rot(0.5);
        q.yz *= rot(0.8);
    }
    
    return sdBox(q, vec3(0.1, 0.5, 0.1));
}

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    float bass = getBass();
    float mid = getMid();
    
    // Cámara cinematográfica (Sin saltos raros)
    vec3 ro = vec3(0.0, 0.0, -3.0);
    vec3 rd = normalize(vec3(uv, 1.5));
    
    // Movimiento suave de cámara
    ro.xz *= rot(T * 0.2);
    rd.xz *= rot(T * 0.2);

    vec3 col = vec3(0.01, 0.01, 0.02); // Fondo negro de lujo
    
    // Raymarching de superficie (No volumétrico para evitar errores de gradiente)
    float t = 0.0;
    for(int i=0; i<100; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        if(d < 0.001 || t > 10.0) break;
        t += d;
    }
    
    if(t < 10.0) {
        vec3 p = ro + rd * t;
        // Cálculo de normales para brillo metálico/cristal
        vec2 e = vec2(0.001, 0.0);
        vec3 n = normalize(map(p) - vec3(map(p-e.xyy), map(p-e.yxy), map(p-e.yyx)));
        
        // Iluminación: Cian y Magenta (Tu marca registrada)
        vec3 lightPos = vec3(2.0, 2.0, -2.0);
        vec3 lDir = normalize(lightPos - p);
        float diff = max(dot(n, lDir), 0.0);
        float spec = pow(max(dot(reflect(-lDir, n), -rd), 0.0), 64.0);
        
        // Color reactivo
        vec3 baseCol = mix(vec3(0.0, 0.8, 1.0), vec3(1.0, 0.0, 0.5), sin(p.y * 2.0 + T) * 0.5 + 0.5);
        col = baseCol * diff + spec * vec3(1.0);
        
        // Efecto de bordes brillantes (Glow)
        float edge = pow(1.0 - max(dot(n, -rd), 0.0), 3.0);
        col += baseCol * edge * 2.0;
    }
    
    // Rayos de luz "God Rays" artificiales (Para el valor de USD 300)
    float beam = pow(max(0.0, 1.0 - length(uv * vec2(1.0, 2.0))), 4.0);
    col += vec3(0.1, 0.3, 0.5) * beam * bass;

    // Post-procesado premium
    col = smoothstep(0.0, 1.0, col);
    col = pow(col, vec3(0.4545)); // Gamma
    
    fragColor = vec4(col, 1.0);
}
```
# 无模型渲染（SDF）
SDF：Signed Distance Function (有符号距离函数) 。给出任意一点，点到表面的有符号距离。**曲面的隐式表达**（不容易得到曲面上的点，但是，容易判断点到曲面的距离；非常擅长，多个曲面的拼接）


例子：
- `sdBox(vec3 p, vec3 b)` 是一个长方体的 SDF 函数。你输入空间中的一个坐标 $p$，它会告诉你这个点**距离长方体表面还有多远**。
- 如果返回值 $> 0$，说明点在物体外面；$= 0$ 在表面；$< 0$ 在物体里面。

代码：(3D 图形学界的大神 Inigo Quilez（SDF 和 Shadertoy 的核心推手）写出的经典公式)
```glsl
float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q,0.0)) + min(max(q.x,max(q.y,q.z)),0.0);
}
```
- 长方体的参数 `b` 代表它的**半长、半宽、半高**（即从中心到各个面的距离）。
- **`abs(p)`（第一象限对称）**：利用绝对值，把整个 3D 空间全部折叠到了 $X, Y, Z$ 轴均为正数的“第一卦限”（类似 2D 的第一象限）。这意味着我们**只需要考虑长方体右上角的那一个区域**，其他七个角的情况完全是对称的。
- **`- b`（原点平移）**：把长方体的**右上角顶点**，平移成了新的“数学原点 $(0,0,0)$”。
	- **`q` 的某个轴大于 0**：说明点在长方体**外部**。
	- **`q` 的所有轴都小于 0**：说明点在长方体**内部**。


这个公式的本构逻辑非常纯粹：

![[shadertoy-example入门系列-01-无模型渲染sdf-01.png]]


更多例子：比如有隐式表达的各种表面。（因此可以积累一些SDF函数，通过一些组合的方式，可以表达复杂几何体）。
- $x^2+y^2+z^2=1$ ，得到SDF函数 ： $f(p)=x^2+y^2+z^2-1$


显示表达：（容易取面上的点）
- f(u,v)=(x(u),y(u),z(u)) ：典型例子，球面极坐标， $f(\theta,\phi)=(r\cos\phi\cos\theta,r\sin\phi\cos\theta,r\sin\theta)$
优点：非常容易得到曲面上的一个点。（选择参数值，带入即可）。但是，判断任意一个点到曲面的距离，难。

# Ray Marching
主要用来解决射线和SDF表达的几何体求交的问题。

假设你的屏幕分辨率是 $1920 \times 1080$。GPU 会**同时**为这 200 多万个像素运行这段代码。我们只盯着其中一个像素（比如屏幕正中央的那个像素）来看：

1. 打出光线
	- 在 `mainImage` 里，屏幕中央的像素发射了一条光线。
	- 起点（相机位置 `ro`）：$(0, 0, -3.0)$
	- 方向（光线方向 `rd`）：$(0, 0, 1.0)$ （正对着屏幕深处冲过去）
2. 疯狂的“盲人摸象”循环 `for(int i=0; i<100; i++)`
	1. **第 1 次循环 ($i=0$)**：- 调用 `map(P)`。数学裁判计算了一下 $P$ 到那个虚拟长方体的距离，发现最近的距离是 `2.5`。**光线大步向前跳跃 `2.5` 距离**。现在光线到了 $P = (0, 0, -0.5)$。
	2. **第 2 次循环 ($i=1$)**：再次调用 `map(P)`。裁判说：“嗯，现在你离长方体表面很近了，距离还有 `0.4`。”
	3. **第 3 次循环 ($i=2$)**：调用 `map(P)`。裁判说：“距离只有 `0.0005` 了！”

对应代码：

```glsl
    float t = 0.0;
    for(int i=0; i<100; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        if(d < 0.001 || t > 10.0) break;
        t += d;
    }
    
```

其中map函数：（可以理解为到表面距离的判断。但中间还有很多令人费解的环节）
```glsl
// --- EL NÚCLEO (Geometría que no genera bloques sólidos) ---
float map(vec3 p) {
    float bass = getBass();
    vec3 q = p;
    
    // El núcleo: un octaedro que se abre con el audio
    q.xy *= rot(T * 0.5 + bass);
    q.yz *= rot(T * 0.3);
    
    // Geometría fractal simple para evitar el "bloque sólido"
    for(int i=0; i<3; i++) {
        q = abs(q) - 0.2 - bass * 0.1;
        q.xy *= rot(0.5);
        q.yz *= rot(0.8);
    }
    
    return sdBox(q, vec3(0.1, 0.5, 0.1));
}
```

其中，最简单的是：对查询的射线进行旋转。（等价于对几何体旋转）：

```glsl
    q.xy *= rot(T * 0.5 + bass);
    q.yz *= rot(T * 0.3);
```

这里面，rot函数是二位旋转函数。

![[shadertoy-example入门系列-01-ray-marching-01.png|352]]

# 分形几何入门
而另外的部分，看起来也是对查询射线的变换，解释起来就比较复杂了。

但同样类似q的旋转理解为形体的旋转，我们可以把

```glsl
    for(int i=0; i<3; i++) {
        q = abs(q) - 0.2 - bass * 0.1;
        q.xy *= rot(0.5);
        q.yz *= rot(0.8);
    }
    
```
对应的变换，理解为对空间的变换。空间的变换会影响几何形体（类似于把镜面的内容和原本的实体拼接到了一起），从而构造出了复杂的几何形体。

那么具体怎那么做的呢？
## 入门：2D 轴对称折叠
考虑下面的变换：
```
p.x = abs(p.x)
```
这意味着什么？
- 当光线走到右边 $p = (1, 0)$ 时，`abs(1)` 保持不变，它正常测距。
- 当光线走到左边 $p = (-1, 0)$ 时，`abs(-1)` 变成了 $1$！原本处于左边的坐标，被**强行映射**到了右边。

所以，整个空间，按照 x=0 进行了轴对称的折叠。因此，所有在 x>0 的物体，被复制到了 x<0 的位置。两者一起形成了新的几何体。（从几何体视角，而不是从射线视角来看）

## 进阶：带偏移的镜像折叠
进一步，考虑：
```glsl
p.x = abs(p.x) - 1.0;
```
这意味着：
- 如果一个几何体在原点，首先它被向右移动了 1 ，
- 随后用 x=0 做镜面反射，
- 然后做拼接。

为什么？
- 首先对称轴容易看出来，就是 x=0。因为关于这个轴对称的点，我们得到的映射到原空间的位置(左侧的p.x)的值是一样的。
- 其次，对于x>0的点，实际上都被映射为了原空间中 x-1的位置。因此几何体向右移动了。
- 最后就是拼接。类似上一节的拼接。

## 八卦限折叠
```glsl
p = abs(p) - vec3(1.0, 1.0, 1.0);
```
这个显然是，移动后，沿着 x=0,y=0,z=0都分别折叠。因此产生了8个镜像+本体。最后拼接。这个步骤实际上做了一次分形操作。

同样，除了移动，我们还可以组合旋转。下面的是先旋转，后折叠。（因为我们从SDF物体的视角来看，因此，3先作用到物体让，然后是2作用到物体上。最后是1进行分形操作。）
```glsl
    q = abs(q) - 0.2 - bass * 0.1; // 1. 镜像并拉开距离
    q.xy *= rot(0.5);              // 2. 局部扭转空间
    q.yz *= rot(0.8);              // 3. 再次扭转空间
```

而代码中上述循环做了3次。因此我们得到了一个用 8^3 个长方体拼接得到的物体：
```
for(int i=0; i<3; i++) {
    q = abs(q) - 0.2 - bass * 0.1; // 1. 镜像并拉开距离
    q.xy *= rot(0.5);              // 2. 局部扭转空间
    q.yz *= rot(0.8);              // 3. 再次扭转空间
}
```

### 分形调整的试验
当分型次数变多，因为每次都拉开距离，所以物体会变大。如何控制物体不超出屏幕呢？

**可以让物体小一些。**
```
// 如果原本是 vec3(0.1, 0.5, 0.1)，调大循环后，直接手工把它改得很小：
return sdBox(q, vec3(0.02, 0.1, 0.02));
```

**动态缩小平移量** 
```glsl
float shift = 0.2; // 初始平移量
for(int i=0; i<6; i++) {
    q = abs(q) - shift;
    q.xy *= rot(0.5);
    q.yz *= rot(0.8);
    shift *= 0.5; // 核心：下一轮的平移量减半！
}
```

**空间整体缩放**
```glsl
float scale = 1.0;
for(int i=0; i<5; i++) {
    q = abs(q) - 0.2;
    q *= 1.5; // 把空间放大 1.5 倍（等同于把这一轮的物体缩小 1.5 倍）
    scale *= 1.5; // 记录总共放大了多少倍
    q.xy *= rot(0.5);
}
return sdBox(q, vec3(0.1)) / scale; // 核心：最后必须除以总缩放比例，修正SDF距离！
```

# 描边特效
```glsl
// Efecto de bordes brillantes (Glow)
float edge = pow(1.0 - max(dot(n, -rd), 0.0), 3.0);
col += baseCol * edge * 2.0;
```
- **`dotd(n, -rd)`**：计算物体的表面朝向（法线 `n`）和你的视线方向（`-rd`）的接近程度。
    - 如果你正对着水晶的一个平面看，两个方向平行，结果接近 `1.0`。
    - 如果是水晶的侧面，或者是复杂的裂缝边缘，表面朝向和你的视线垂直，结果接近 `0.0`。
- **`1.0 - ...`**：把上面的结果反转过来。正对你的平面变成了 `0.0`，**而侧面和边缘变成了 `1.0`**。（这导致边缘处，值很大）
- **`pow(..., 3.0)`**：通过 3 次方进行指数级压制。让中间平面的过渡区域变得更暗（接近 0），而让边缘处变得极其锐利和明亮。
- **`col += baseCol * edge * 2.0`**：把这个亮度乘以核心的基础渐变色（青/玫红），狠狠地叠加到画面上。
# 颜色渐变
```glsl
vec3 baseCol = mix(vec3(0.0, 0.8, 1.0), vec3(1.0, 0.0, 0.5), sin(p.y * 2.0 + T) * 0.5 + 0.5);
```

`mix(colorA, colorB, x)` 是 GLSL 中最常用的线性插值函数，它会根据第三个参数 `x`（取值在 $0.0 \sim 1.0$ 之间）来决定两者的混合比例：
- 当 `x = 0.0` 时，完全返回 `colorA`。
- 当 `x = 1.0` 时，完全返回 `colorB`。
- 当 `x = 0.5` 时，返回两者的完美中间过渡色。

代码中指定的两种颜色是：
- **`vec3(0.0, 0.8, 1.0)`**：一种极其通透、充满未来科技感的**电光青色（Cyan/赛博蓝）**。
- **`vec3(1.0, 0.0, 0.5)`**：一种极其美艳、挑逗视觉的**霓虹玫红色（Magenta/高饱和荧光粉）**。


**渐变控制器：sin(p.y * 2.0 + T)**
-  空间维度：`p.y * 2.0`
	- 它引入了物体的**垂直高度（$Y$ 轴坐标）**。这意味着，随着物体从下往上延伸，`sin` 的值会像波浪一样上下起伏。
	- **带来的视觉结果**：颜色不再是均匀一整块的，而是**变成了垂直方向的条纹渐变**。比如物体的底部是青色，中间变成了玫红，顶部又变回了青色。
	- 乘以 `2.0` 是为了加快波浪的频率，让渐变的层数变多，色彩更丰富。
- 时间维度：`+ T`（也就是 `+ iTime`）
	- 随着时间 `T` 的不断增加，整个 `sin` 波浪会**沿着 $Y$ 轴向上（或向下）不断地滚动流动**。
	- **带来的视觉结果**：你看到的彩色条纹不是静止的，而是像流云或者流体一样，不断地在 3D 水晶核心的表面向上攀升、流淌。
# 音频纹理

声音是一个一维的波。即，介质在时间t处于某个振幅处。而只要这个一维波完全一样，那么声音也是完全一样的。

我们考虑一个极短的时间段。比如，采样频率 48k Hz ，那么采样 512个样本，对应时间约为 10.67 毫秒。 512/48000 (s) 。于是，固定时间的情况下，我们得到一个512维的向量。

接着考虑频域，对时域信号直接做FFT变换，我们就可以得到 512 个频率，每个频率的系数（或者说能量）。于是，我们又得到了一个512维的向量。（推荐学习《信号与系统》，理解频域、时域相关的概念）

当时间t固定时，我们有一个 512x2 的图像（代表了一个局部的声音片段）。随着t的变化，这个图像也会发生变化。（我们从声音样本中采样即可）。

而代码中：
```glsl
float getBass() { return pow(texture(iChannel0, vec2(0.05, 0.25)).x, 2.0); }
float getMid() { return texture(iChannel0, vec2(0.4, 0.25)).x; }
```
- getBass 代表，取频域数据（x=0.05代表低频，y=0.25代表 512x2的第一行数据，这里第一行保存的是频域数据）。随后平方，加大低频信号。因此这个是拿到了当前声音中低频部分的强度。（比如bass、鼓点等）
- getMid 则是取了中频 x=0.4 左右的信号。靠近中间的位置。这在音乐里代表**中音频段（Mid Range）**，通常是人声、吉他、键盘等乐器的主要频率。


这两个信号，如何影响画面？
1. 形变同步：map函数中：
	1. `q = abs(q) - 0.2 - bass * 0.1` : 减去的数字变大，空间被狠狠地拉开。
	2. **视觉效果**：那个量子核心会**随着音乐的每一个鼓点，像心脏跳动一样猛烈膨胀和收缩**。
2. 旋转加速（低音控制）:
	1. `q.xy *= rot(T * 0.5 + bass);`
	2. 鼓点敲击时，旋转角度瞬间叠加上一个大数值。
	3. **视觉效果**：核心在平时是优雅慢速自转，**每当鼓点一响，它就会像是被鞭子抽了一下一样，猛烈地顺时针“抽搐/瞬移”一下**。
3. 环境光芒闪烁（低音控制）
	1. 在 `mainImage` 结尾：`col += vec3(0.1, 0.3, 0.5) * beam * bass;`
	2. **视觉效果**：屏幕背景后的那束神圣的上帝之光（God Rays），平时是微弱的，**每当低音炮轰鸣，光芒就会瞬间照亮整个夜空**。

