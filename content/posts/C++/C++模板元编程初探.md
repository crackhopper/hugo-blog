---
title: C++模板元编程初探
date: 2025-12-11T00:16:03+08:00
tags:
  - cpp
  - template
  - meta-programming
draft: false
---
![[C++模板元编程初探-1765422624800.png|697x392]]

说起来我也是C++老鸟了，本科的时候就深入学习了C++，那个时候还没有C++11。微软的msvc编译器针对当前的C++0x上还有大量的不兼容（学习的时候试出来的）。自认为对C++的掌握算是精通的水平，不过，多年来一直没有对模板技术进行深入系统的学习。

最近，确立了成为渲染大师的目标。我打算推进渲染器开发的过程中，再强化一下C++的学习。

本文则是我学习模板元编程的初探。不过自认为掌握之后，足以应对常规的模板开发。

**注：本文不适合C++初级水平的开发人员阅读。**

<!--more-->

# C++模板基础
## 语法概述

模板是 C++ 的泛型编程机制 —— 编译时生成类型与/或值的参数化代码。模板不是运行时的多态（如 virtual），而是在 **编译期通过实例化（instantiation）产生具体实体（函数、类）** 。

这个加黑的部分要重点理解：模板实际上是开发者和编译器沟通的手段（更精确的描述：模板是编译器可执行的代码生成规则（code generation patterns），类似一种约定描述，编译器遇到模板的时候，存储规则；遇到使用模板的时候，按照模板开发者定义好的规则来生成）
- 从效果上看，模板让开发者像是在给编译器提供一套‘可执行的代码生成脚本’，有类似 **插件** 的感觉。但这仍是语言内建机制，而不是外部插件。
- 模板在效果上能够完成比 **宏** 更强的代码生成任务，因此从使用体验上像是‘更高级的泛型化代码生成工具’，但两者在技术原理上完全不同： **宏做文本替换，模板操作 AST** 。

接下来主要简单举例子，列举常见模板语法。不深入讲。看不懂的，需要自己深入学习，或者说本文还不太适合你。
## 函数模板 / 类模板 / 别名模板

```cpp
// 函数模板
template<typename T>
T add(T a, T b) { return a + b; }

int x = add<int>(1, 2);   // 显式指定模板实参
int y = add(1, 2);        // 类型推导，编译器 deduce 为 int

// 类模板
template<typename T, std::size_t N>
struct Array {
    T data[N];
    T& operator[](std::size_t i) { return data[i]; }
};

Array<int, 10> a;

// 别名模板
template<typename T>
using Vec = std::vector<T>;

Vec<int> v; // 等价于 std::vector<int>

```

## 模板参数种类
**类型模板参数（type template parameter）**：`typename` 或 `class`（等价）。最常见的模板类型。
```cpp
template<typename T, std::size_t N>
struct Array {
    T data[N];
    T& operator[](std::size_t i) { return data[i]; }
};
```

**非类型模板参数（non-type template parameter）**：整型、指针、引用等常量值（必须在编译期可确定）。 **很重要，实现traits的关键**
```cpp
template<int N> struct X { };
X<5> x;
```

**模板模板参数（template template）**：参数类型是一个模板。在元编程中大量使用，只是阅读起来会麻烦点，理解上并不困难（递归的概念）。(C++11要求严格匹配，C++17要求兼容匹配)
```cpp
template<template<typename, typename> class Container, typename T>
struct Wrapper {
    Container<T, std::allocator<T>> c;
};

// 使用：以 std::vector 作为模板参数
Wrapper<std::vector, int> w;
```

## 变长模板参数（Variadic Templates）
这个话题稍微复杂一点。C++11 引入了 **模板参数包（parameter pack）**，可以表示**任意数量的模板参数**：
```cpp
// 类型 parameter pack
template<typename... Ts>
struct Tuple { };
Tuple<int, double, char> t;

// 非类型 parameter pack
template<int... Ns>
struct ArrayHolder { };
ArrayHolder<1,2,3> a;


// 函数模板参数包（匹配任意函数参数列表）
template<typename... Args>
void func(Args&&... args) {
    // 可以转发参数，逐一处理
}
int main() {
    func(1, 2.0, "hello");   // 任意数量和类型的参数
}
```

基本概念比较容易。我们看一些细节用法
### 如何unpack？
**1.递归展开（经典元编程）**
```cpp
template<typename T, typename... Ts>
void printTypes() {
    std::cout << typeid(T).name() << "\n";
    if constexpr (sizeof...(Ts) > 0) {
        printTypes<Ts...>(); // 递归展开剩余类型
    }
}
```

**2.直接展开到表达式**
- `(expr, 0)...` 是 **pack expansion** 。把 `Ts...` 中的每个类型套用到表达式中
```cpp
template<typename... Ts>
void printSizes() {
    int arr[] = { (std::cout << sizeof(Ts) << "\n", 0)... }; // pack expansion
    (void)arr; // 防止未使用警告
}
```

**3.C++17 fold expression**
```cpp
template<typename... Ts>
void printSizes() {
    ((std::cout << sizeof(Ts) << "\n"), ...); // fold expression
}

template<typename... Args>
void func(Args&&... args) {
    (std::cout << ... << args) << "\n"; // C++17 fold
}
```
形式上：
- `(... op pack)`       // 左折叠，无初值
- `(init op ... op pack)` // 左折叠，有初值 
- `(pack op ...)`       // 右折叠，无初值
- `(pack op ... op init)` // 右折叠，有初值
- 理解上，把整个形式打括号，随后根据pack的位置，延申一个pack出来。
	- `(... op pack)` -> `((... op pack) op pack)` 
	- 有init的情况： `(init op ... op pack)` -> `((init op ... op pack) op pack)` 
	- 全部展开完了，从左到右，填入 pack中的各个元素。
	- 注意，这里pack代表有 args 的expression
### 如何提取函数的第一个参数类型？
```cpp
// primary template（默认）
template<typename Func>
struct FirstArg;

// 偏特化，匹配普通函数类型
template<typename R, typename T1, typename... Ts>
struct FirstArg<R(T1, Ts...)> {
    using type = T1;
};
```

有针对这个能力的 meta function
```cpp
#include <tuple>
#include <type_traits>
#include <iostream>

template<typename... Args>
struct FunctionTraits {
    using FirstArg = std::tuple_element_t<0, std::tuple<Args...>>;
};
```

### 如何提取args中的某一个类型？
即上一节中的meta function的原理是什么。

答案是：利用偏特化 （在模板内调用另一个模板，触发偏特化）
```cpp
// 用于提取参数包第一个类型
template<typename T, typename... Ts>
struct FirstType {
    using type = T;
};

template<typename... Args>
void func() {
    using First = typename FirstType<Args...>::type;
    std::cout << typeid(First).name() << "\n";
}

```

## 模板参数推导（template argument deduction）
模板参数推导在标准里的基本描述是：将 **参数声明的类型模式**（记为 **P**）与 **实际实参的类型**（记为 **A**）比较，从而推导出模板参数 `T` 等。

### 推导时的关键原则
- **模板推导不进行用户定义转换**（user-defined conversions）。推导只“匹配”类型结构（identity、引用调整、数组/函数退化等），不是一般的 overload-conversion 过程。
- 某些 _调整_ 是允许且自动发生的（例如数组 → 指针、函数 → 指针、顶层 `const` 忽略）。
- 如果 P 是引用类型（`T&`、`T&&`），推导的规则与是否为左值/右值有关（这会产生引用折叠/通用引用行为）。
### 引用推导case01
```cpp
template<typename T>
void f(T&);   // lvalue 引用

int a = 0;
f(a); // T 推导为 int
f(5); // 错误：不能将临时赋给 int&
```
- 对于 `f(a)`：P = `T&`，A = `int`（`a` 的实际类型是 `int`，且是 lvalue），推导出 `T = int`，参数类型变为 `int&`，匹配成功。
- 对于 `f(5)`：A 的类型为 `int`，但是 prvalue（临时）。`T&` 不能绑定到非 `const` prvalue，因此没有可行推导 — 推导失败（并非“以转换方式”接受）。
	- lvalue : 左值，有名字、可寻址的对象或引用。 `int a; a`
	- xvalue ：expiring value，可移动的对象，可寻址。 `std::move(a)` 
		- 可以简单记为 **可以转化为左值的右值** 。类别仍然是右值。但被引用接收后，可以当作左值来操作：
		- `std::string&& r1 = std::move(a);` 随后使用r1可以访问这个对象进行修改。（注意，r1是左值，只有 `std::move` 返回的是右值xvalue，因此要触发移动语义，需要手动move）
	- prvalue: pure rvalue，临时值，不可寻址。 `1+2` , `std::string("hi")`
		- 即使绑定了 T&& 之类的，也无法修改内部的数据。
	- 注： xvalue, prvalue 在绑定参数的类别上一样，仅可以绑定 `const T&` 和 `T&&`
### 引用推导case02
```cpp
template<typename T>
void g(T&&);  // 通用引用（在模板参数推导上下文中）
g(a); // T -> int&, g 参数类型 becomes int& &&
g(5); // T -> int, g 参数类型 becomes int&&
```
- `T&&` 在模板参数中且 `T` 是待推导的模板参数时，被称为 **通用引用**（forwarding/reference-collapsing 情况）。（即推导的时候，得到的参数类型一定为引用）
- 若实参是 **左值**（如 `a`），规则会将 `T` 推导为 `int&`，于是 `T&&` 展开为 `int& &&`，根据引用折叠规则变为 `int&`（函数参数成为 `int&`）。
- 若实参是 **右值/prvalue**（如 `5`），`T` 推导为 `int`，参数类型为 `int&&`。

这里有引用折叠规则：
- `& &` 折叠为 `&`
- `& &&` 折叠为 `&`
- `&& &` 折叠为 `&`
- `&& &&` 折叠为 `&&`
### 常见调整
- **顶层 cv（const/volatile）忽略**：`T` 不会保留顶层 `const`。  
	- 例：`template<typename T> void h(T); const int ci = 0; h(ci);` → `T` 推导为 `int`（不是 `const int`）。
- **数组/函数 退化**：当参数是按值或按指针接收时，数组会退化为指针、函数会退化为函数指针（但若 P 是 `T (&)[N]` 则不会退化）。    
	- 例：`template<class T> void p(T*); int a[10]; p(a);` → `T` 为 `int`（数组退化为 `int*`）。
- **引用参数时**：如果 P 是引用，会根据 A 的值类别调整（参见前面的两个case）。
- **指针/引用到成员等有较复杂规则**：（参见后面展开讲解）

推导**不**允许（因此会导致 SFINAE 或失败）的情形：
- 通过用户定义的转换来匹配模板参数（例：class -> int via operator int() 不用于推导）。
- 需要多步隐式转换（除非在重载解析阶段通过 conversion sequence 被考虑，但推导本身不做）。

### 成员指针推导
先看基础概念
```cpp
// 指向 数据成员的指针
struct S { int a; };
int S::* p = &S::a;
// 指向 成员函数的指针
struct S { void f(int); };
void (S::*mf)(int) = &S::f;
```

举例子对应的模板
```cpp
template<typename T, typename C>
void f(T C::* mem);

struct S { int x; };
f(&S::x);
```
- 注意：模板函数定义的时候，需要两个类型。
	- 一个是成员的类型 T。（实例化时匹配 int）
	- 一个是成员指针的所属类的类型 C（实例化时匹配 S）。

更多不展开。原理上差不多。需要注意的：
- cv匹配修饰，不能忽略。
- 遇到成员重载的时候，不能有二义性。
## 重载解析（overload resolution）
1. **构造候选集合（candidate functions）**：包括可见的普通函数与函数模板实例（模板以原型形式加入候选集）。
2. **对每个函数模板做模板参数推导**（deduction）：
    - 如果推导失败或导致替换错误（并且是在 SFINAE 环境），该函数模板被视为不可行（removed）。
    - 对推导成功的模板，会得到一个“可行候选”（viable candidate）及对应的实参转换序列。
3. **对所有可行候选评估转换序列（conversion sequences）**：
    - 计算从每个函数实参到形参所需的标准转换序列（exact match、promotion、conversion 等）；注意：在此阶段用户定义转换可被计入转换序列（区别于推导阶段）。
4. **比较各候选的转换序列来选出“最优”**（best viable function）：
    - 一般规则：**更精确的匹配（更短、更少的转换）优先**。
    - 在转换序列相同的情况下，有一些 tie-break 规则：
        - **非模板函数优于函数模板**（如果两者转换序列同等，非模板被选择）。
        - **对于两个函数模板，采用模板部分排序（partial ordering）来选择更特化的模板**（更特化者优先）。
        - 其它规则如模板实参显式指定、模板特化程度也会影响。
## SFINAE
这个词出现了很多次。现在详细解释。

**SFINAE** 全称：**Substitution Failure Is Not An Error**  。翻译：**替换失败不是错误**

**核心思想**：
- 当编译器在模板实例化（instantiation）过程中，尝试把模板参数替换到模板定义时，如果**类型不匹配或语法不成立**，**不会报错**
- 相反，编译器会 **忽略这个模板实例**，继续尝试其他可行的模板重载或特化
- 如果所有模板都替换失败，才算真正的编译错误

SFINAE 是模板推导/替换阶段的核心规则：当用某个模板参数替换模板参数导致模板的类型匹配或形成无效类型时，不视为编译错误，而是将该模板从候选集中移除，从而允许其他重载生效。SFINAE 常用于启发式重载选择（enable_if、检测 idiom）实现不同实现路径。


### 元编程中如何使用SFINAE
- 如果模板推导失败，那么对应的模板代码不会生成。这让我们有了可以 “检查” 的机会。把SFINAE作为一个检查接口和编译器通信。
	- 定义一个模板，增加一个默认参数，里面定义一套复杂的模板推导规则。
	- 实例化的时候，模板推导规则被执行，
		- 最后规则通过，那么检查通过；
		- 规则不通过，没有可行的模板以及重载，那么会报错。
## 名称查找与“二阶段查找”（two-phase lookup）
模板编译涉及两阶段语义检查：
1. **模板定义阶段（phase 1）**：编译器解析非依赖名 —— 在模板定义处就必须能解析的名字（非依赖表达式）。
	1. `typename` 告诉编译器某个依赖名是类型 （尤其是从模板类型中访问成员，成员是类型的时候）
	2. `template` 告诉编译器后面的 `<...>` 是对模板的引用（同上，模板类型的成员，还是模板的时候）
    
2. **模板实例化阶段（phase 2）**：编译器在具体实例化模板、并给定模板实参后，解析依赖名（dependent names）。

## 特化（specialization）
- **完全特化（full specialization）**：针对特定模板实参写专门实现（类或函数）。函数模板的完全特化语法较少用，类模板常用。

```cpp
template<typename T> struct Traits { static const bool is_special = false; };
template<> struct Traits<int> { static const bool is_special = true; }; // 完全特化
```

    
- **偏特化（partial specialization）**：仅类模板支持偏特化（函数模板不支持偏特化；可用重载代替）。

```cpp
template<typename T> struct Wrapper<T*> { /* 指针版本 */ }; // 偏特化
```

# 模板编程范式
## 概述
看一个简单的例子：定义一个模板函数，仅接收整数作为参数：
```cpp
template<typename T,
    typename = std::enable_if_t<std::is_integral_v<T>>
>
void f(T);
```

- `typename=...` 默认模板参数实参。
	- 这个参数名都没有。说第二个参数仅仅用来做 SFINAE，只是指挥编译器做事情。


上面的模板函数中，第二个模板参数有默认值，因此会在实例化的时候，触发模板参数推导，里面用到了两个meta function。从命名上很容易理解，一个是检查是不是整数，另一个是enable是否开启。

具体怎么定义的呢？
```cpp
template<bool B>
struct integral_constant {
    static constexpr bool value = B;
    using value_type = bool;
    using type = integral_constant;
    // 到 bool 类型的隐式转换；
    // 代码中可以构造临时变量，强制转化true和false形成分支。编译器会同时生成两个分支代码
    // 这个是C++17之前的解决手段。目前被 if constexpr 条件编译代替了
    constexpr operator value_type() const noexcept { return value; }
};

using true_type  = integral_constant<true>;
using false_type = integral_constant<false>;


// minimal enable_if
// T的类型不重要。重要的是 enable_if 是否导出了type成员。
template<bool B, typename T = void>
struct enable_if { };                // 当 B == false：没有成员 typedef -> 替换失败
template<typename T>
struct enable_if<true, T> { using type = T; }; // B == true 时提供 type

// C++14 alias template
template<bool B, typename T = void>
using enable_if_t = typename enable_if<B, T>::type;

// minimal is_integral: 默认 false，但为整型特化为 true
template<typename T>
struct is_integral : false_type { };

template<> struct is_integral<int> : true_type { };
template<> struct is_integral<short> : true_type { };
template<> struct is_integral<long> : true_type { };
template<> struct is_integral<unsigned int> : true_type { };
// ... 以及其他整型 specializations (char, bool, unsigned long long, 等)

// C++17 variable template
template<typename T>
inline constexpr bool is_integral_v = is_integral<T>::value;
```

我们接下来详细讲解上面的实现。这里先给出简要总结：

- **值模板** ：
	- `integral_constant<B>` 是**值模板**，它把布尔值（或整数值）包装成一个类型。
	- 实例化后类型里有静态成员 `value`
	- 这些类型可以作为 **标签类型（tag）**，用于模板特化或继承。
	 
- **特性模板** （traits）：
	- **核心中的核心：提供了一个 类型对应的值(tag) **
	- **特性模板继承自值模版** ： `is_integral<T>` 继承自 `true_type` 或 `false_type` 
	- 这种继承关系在 **类型层面**表示“满足特性或不满足特性” （因此本身也是一个tag类型）
	- `value` 成员提供 **编译期常量值**

- **类型求值函数（enable_if）** ：
	- 根据tag内包含的具体值做偏特化
	- 输出：
		- 提供 type： 利用 `using` 或 `typedef` ，
		- 不提供 type 

- **使用位置/SFINAE** ：
	- 追加额外的模板参数，
	- 提供上面的meta函数，利用返回的类型作为默认模板参数，从而触发 SFINAE 。

## 值类型(Value Types)
### 概念
在模板元编程中，**值类型**指的是将“值”作为类型的一部分进行编码。C++ 允许我们通过 `std::integral_constant` 或自定义类型将整数、布尔值等常量封装为类型，这样编译器在编译期就可以进行运算和推导。

### 实现方式
```cpp
template<int N>
struct IntValue {
    static constexpr int value = N;
};
```

- `value` 是静态成员，在编译期就可以访问。(**编译器可以访问，意味着可以作为模板参数**)
- 可以用来在模板参数中传递整数或布尔值。

C++ 标准库提供了 `std::integral_constant`，是这种模式的标准实现：
```cpp
#include <type_traits>

using TrueType = std::true_type;   // 相当于 std::integral_constant<bool, true>
using FalseType = std::false_type; // 相当于 std::integral_constant<bool, false>
```

### `integral_constant` 简化版
```cpp
// 简化版 integral_constant
template<typename T, T v>
struct integral_constant {
    // 编译期常量值
    static constexpr T value = v;

    // 类型别名，方便 TMP 使用
    using value_type = T;
    using type = integral_constant<T, v>;

    // 编译期隐式转换到 T
    constexpr operator T() const noexcept { return value; }

    // 调用运算符，返回 value
    constexpr T operator()() const noexcept { return value; }
};

// 类型别名，方便使用布尔值
using true_type = integral_constant<bool, true>;
using false_type = integral_constant<bool, false>;
```


### 示例用法-编译期求解表达式
把非类型模板参数，理解为函数参数。把类型内定义的成员 `value` （也可以是其他成员），理解为函数输出。可以利用递归的方式，完成复杂的编译期计算

```cpp
#include <iostream>
#include <type_traits>

template<int N>
struct Factorial {
    static constexpr int value = N * Factorial<N-1>::value;
};

template<>
struct Factorial<0> {
    static constexpr int value = 1;
};

int main() {
    std::cout << "Factorial<5>::value = " << Factorial<5>::value << std::endl;
    // 输出 120
}
```

### 更核心的用法-继承
在 TMP 的设计哲学中，**值类型更多是作为类型的一部分被继承或组合，起到“类型标签”和编译期信息载体的作用”**。

它既包含**值** (`value`) 又是**类型** (`integral_constant<T, v>` 本身就是一个类型)。
- **值**：允许编译期运算
- **类型**：可以继承或作为模板参数传递

#### 继承提供统一接口
```cpp
struct TrueType : integral_constant<bool, true> {};
struct FalseType : integral_constant<bool, false> {};
```
- `TrueType` 和 `FalseType` 都有 `::value` 和 `::type`
- 允许不同特性模板统一接口，方便模板元编程中做条件判断和类型选择。

#### 类型标签（Tag Dispatching）
```cpp
template<typename T>
void process(T, std::true_type) { /* 特化行为 */ }

template<typename T>
void process(T, std::false_type) { /* 默认行为 */ }

process(42, std::is_integral<int>{}); // 编译期选择函数
```
- `std::is_integral<int>` 是一个 **值类型** 。通常这个模板类会继承自 `std::true_type` 或 `std::false_type` （通过特化/偏特化，从而会是其中一个类型）
#### 组合模板逻辑
```cpp
template<typename T>
struct my_trait : std::integral_constant<bool,
    std::is_pointer<T>::value || std::is_reference<T>::value> {};
```
- 这个新的值类型，可以组合两种值类型的概念。
- 可以在编译期被其他模板继承或组合
- **值和类型合二为一**，方便 TMP 进行递归或组合逻辑

## 特性模板(Traits)
**特性模板（Traits）本质上就是一种值类型的“包装”**，它在编译期承载类型特性信息，同时作为类型存在，可以被继承或组合。
### 概念
**特性模板**是一种模板元编程手段，用来描述类型的某种属性或特性。常见用途包括：
- 类型是否是指针、引用、数组
- 类型是否是 POD（Plain Old Data）
- 类型之间的关系（可赋值、可拷贝等）

因为它本质上继承自值类型（通常 `std::true_type` 或 `std::false_type` ），所以特征模板本身包含成员 `value` 。值为 true 或 false。

如何让不同的模板参数，得到不同的答案？ **偏特化**

简单类比理解： **偏特化** 类似于正常编程里的if分支结构。而整个类型的定义，就是把 if 分支结构组合到一起了。这样，traits相当于利用模板的“if”，完成编译期的判断。

### 实现方式
特性模板通常通过**偏特化**实现：
```cpp
template<typename T>
struct is_pointer {
    static constexpr bool value = false;
};

template<typename T>
struct is_pointer<T*> {
    static constexpr bool value = true;
};

```

不过更常见的做法是：继承 `std::true_type` 或 `std::false_type` 。保证一个统一的形式。

```cpp
// 通用模板：默认不是指针
template<typename T>
struct is_pointer : std::false_type {};

// 偏特化：指针类型
template<typename T>
struct is_pointer<T*> : std::true_type {};
```

### 使用示例
```cpp
#include <iostream>

template<typename T>
void check_pointer() {
    if constexpr(is_pointer<T>::value) {
        std::cout << "It's a pointer type.\n";
    } else {
        std::cout << "It's not a pointer type.\n";
    }
}

int main() {
    check_pointer<int>();    // 输出: It's not a pointer type.
    check_pointer<int*>();   // 输出: It's a pointer type.
}
```

### 使用Traits的好处
1. 编译期，可以对类型的结构进行 **检查** 。
2. 编译期，如果类型结构不符合预期，可以 **对类型进行自动补全或适配** ，让类型具备统一接口。：
	1. 某个模板函数实现，需要使用 `value_type` ，但是某个T，比如没有 `value_type` 之类的成员。
	2. Traits可以做一些常规的尝试，比如通过 `pointer_type` ，来自动定义对应成员，从而让traits包装的类，具备统一的接口。（相当于也有了 `value_type` ）
3. 把 **约束相关逻辑集中到 traits 中** ，减少模板类的复杂度
	1. 可以把模板类实现过程中，对T的各种约束性要求，可能比较分散的处于实现细节的各个位置上。而有了一层traits封装，可以确保约束都集中到traits中。实现的时候，只需要考虑约束已经满足即可。
4. 作为 **编译期信息的统一入口** （type/value 提供点），每个 trait 提供：
	1. `::value`
	2. `::type`

### Traits 全家桶示例模板库
这里面很多属于 类型求值函数 (type functions)
#### 基础工具：`void_t`
```cpp
template<typename...>
using void_t = void;
```
- 接收任意模板参数。（但是并不使用）

上面代码等价于：
```cpp
template<typename... Ts>
struct void_
{
    using type = void;
};

template<typename... Ts>
using void_t = typename void_<Ts...>::type;
```
但是可以简化写，因为： `void 永远不依赖 Ts...` 

#### has_xxx：检测是否有某个内置成员
```cpp
template<typename T, typename = void>
struct has_value_type : std::false_type {};

template<typename T>
struct has_value_type<T, void_t<typename T::value_type>> 
    : std::true_type {};
```

#### fallback 适配 traits（接口统一）
如果 `T` 有 `value_type` → 使用  
如果没有 → 默认使用 `T` 本身
```cpp
template<typename T, typename = void>
struct value_type_trait {
    using type = T;
};

template<typename T>
struct value_type_trait<T, void_t<typename T::value_type>> {
    using type = typename T::value_type;
};
```
#### 类型判断 traits（偏特化版）
```cpp
template<typename T>
struct is_pointer : std::false_type {};

template<typename T>
struct is_pointer<T*> : std::true_type {};
```

#### 类型计算 traits（编译期“元函数”）
```cpp
template<typename T>
struct remove_pointer { using type = T; };

template<typename T>
struct remove_pointer<T*> { using type = T; };
```

#### 组合型 traits（traits 的 traits）
```cpp
template<typename T>
struct normalized_type {
    using raw = typename remove_pointer<T>::type;
    using value = typename value_type_trait<raw>::type;
};
```
说明：
- 去掉指针，例如 `int* -> int`
- 从最终类型中取 value_type（如果有）

组合 traits 常用于构建复杂泛型库。

#### 使用示例
```cpp
struct Foo { using value_type = double; };

static_assert(has_value_type<Foo>::value);
static_assert(!has_value_type<int>::value);

using A = value_type_trait<Foo>::type;   // double
using B = value_type_trait<int>::type;   // int

static_assert(is_pointer<int*>::value);
static_assert(!is_pointer<int>::value);

using C = remove_pointer<int*>::type;    // int
using D = normalized_type<Foo*>::value;  // double
```

## ValueTypes/Traits小结
在模板编程中：
- 模板参数：可以类比为 函数参数。
	- 通常使用 类型模板参数，作为待推断的内容。
- 模板类的成员(比如如 `type`, `value`) ：可以类比为函数的返回值。
	- 为了包含对应的值，通常继承链上，存在 非类型模板参数 。从而实现类型和值的绑定。（值类型）
- 如何实现if分支结构？ 偏特化。
	- 根据不同的参数，偏特化一个类，并提供对应的value。（如何提供？选择对应的值类型进行继承）

上面的meta function和普通函数逻辑上讲，类似的。因此，也可以递归符合调用。
## 类型求值函数（Type Computation / Type Functions）
### 概念
在模板元编程中，**类型求值函数**是指通过模板机制在编译期生成新的类型。它类似于函数，但输入输出都是类型。
- 输入：类型或值类型
- 输出：类型

可以类比，类型求值函数，即为一个meta function。只不过不必继承值类型。而通过对参数的检查（利用traits），就可以直接在成员（type）里输出结果。

比如前面其实举例子的 `remove_pointer` ，本质就是一个类型求值函数。
### 实现和使用
类型求值通常依赖于**模板偏特化**和嵌套类型 `::type`：

元函数 `conditional` ，根据condition，条件选择类型。
```cpp
template<bool Condition, typename TrueType, typename FalseType>
struct conditional {
    using type = TrueType;
};

template<typename TrueType, typename FalseType>
struct conditional<false, TrueType, FalseType> {
    using type = FalseType;
};
```

元函数 `enable_if` 
```cpp
template<bool B, typename T = void>
struct enable_if {};

template<typename T>
struct enable_if<true, T> {
    using type = T;
};
```

元函数 `void_t` 
```cpp
template<typename...>
using void_t = void;
```

上面三个元函数，用法：
- `enable_if_t`：基于布尔条件启用/禁用模板（逻辑判断）**根据condition启用禁用模板**（通常配合true和false的偏特化使用，参数为false时，模板参数替换失败时触发 SFINAE。）
- `conditional_t` : 基于布尔条件在类型之间选择，**根据condition选择类型，而不是启用/禁用**（类型三元运算符）(可以用于类型协变)
- `void_t`：基于表达式是否可展开进行类型检测（结构探测）**检查成员/表达式合法性**（检查表达式是否合法，从而在模板参数替换失败时触发 SFINAE。）

使用的时候，应该从语义上思考去使用。而不是用不符合语义的办法来实现，比如，约束模板类型为整数：
```cpp
// 方法1: enable_if_t（语义最清晰，推荐）
template <typename T, typename = std::enable_if_t<std::is_integral_v<T>>>
void func(T value) {
    std::cout << "Integral version: " << value << std::endl;
}

// 方法2: 组合 conditiional_t 和 void_t ，完成一样的功能 。（显然不清晰，也过于复杂）
template <typename T, typename = std::conditional_t<
    std::is_integral_v<T>,
    T, // true 时，触发的路径
    std::void_t<decltype(T::non_exist)>> // false时，才会求值，导致SFINAE，匹配失败
>>
void func_conditional(T value) {
    std::cout << "Conditional  version: " << value << std::endl;
}
```


# concept(C++20)
concept 是对模板参数语义约束的“显式、可命名、可组合”的语言级机制。一句话： **concept = 把“隐式模板约束”变成“显式接口契约”**

## 基础介绍
**没有 concept 之前** 模板的约束是：
- 隐式的
- 分散在实现中 （不过我们通常用traits，所以某种程度来说，concept替代了traits的部分能力）
- 依赖报错触发（SFINAE）

**使用 concept 之后**
```cpp
template<typename T>
concept Range =
    requires(T t) {
        t.begin();
        t.end();
    };

template<Range T>
void sort(T& x) { }
```
- 约束是**显式**
- 约束是**可复用的**
- 错误信息是**语义级别的**（不满足 Range）

**concept 和 traits 的关系**
- traits 解决的是“如何适配类型”
- concept 解决的是“类型是否满足某种语义” (以前traits也能处理这块)

### 旧写法和新写法
检查是否符合 iterable 接口的写法：
```cpp
template<typename T>
struct is_iterable {
private:
    template<typename U>
    static auto test(int) -> decltype(std::declval<U>().begin(),
                                      std::declval<U>().end(),
                                      std::true_type{});
    template<typename>
    static auto test(...) -> std::false_type;
public:
    static constexpr bool value = decltype(test<T>(0))::value;
};
```
- 隐式约束：不满足条件时报错是模板实例化错误。
- 可读性差：错误信息冗长，不语义化。
- 分散：traits 与模板实现分开，难以组合语义约束。

**使用concept**
```cpp
template<typename T>
concept Iterable = requires(T t) {
    t.begin();
    t.end();
};
```
- 显式语义：`Iterable` 直接表述类型契约。
- 可复用：多个模板直接使用 `Iterable<T>`。
- 错误信息清晰：不满足 `Iterable` 时，编译器提示“concept not satisfied”。
### 从 traits 过渡到 concept 的方法
1. **直接替换型**：原本 traits 检查的条件，改写为 concept 的 `requires` 表达式。
2. **组合型**：多个 traits 条件可以组合成一个 concept。
3. **保留辅助型 traits**：
    - **提取类型信息**：`std::iterator_traits<T>::value_type`。
    - **计算型属性**：`std::rank<T>::value`。
    - **SFINAE 辅助**：某些复杂类型适配仍需 traits。
        
**总结**：概念负责 **语义验证**，traits 负责 **类型信息提取**。

## 基本语法
### 定义concept
```cpp
template<typename T>
concept Range = requires(T t) {
    t.begin();
    t.end();
};

template<typename T>
concept Iterable = requires(T t) {
    { t.begin() } -> std::same_as<typename T::iterator>;
    { t.end() } -> std::same_as<typename T::iterator>;
};
```

- `template<typename T>`：模板参数。
- `concept Range`：定义一个名为 `Range` 的概念。
- `requires` 后面可以接：
	- `{ expr }-> Trait` 
		- `{ expr }`：要求类型 `T` 必须能在该上下文中进行该操作（调用、访问等）。
		- `-> Trait`：指定**返回值约束**，本质是一个 **类型谓词（type predicate）**。参数为返回值类型，返回为`value` 成员（bool值）
	- 还可以直接跟 Trait （只要是类型谓词即可）

**注意：简短说明 concept 不触发 SFINAE，而是语义级布尔约束，错误信息更清晰**


### 内联约束表达式
```cpp
template<typename T>
requires std::is_integral_v<T>
T add(T a, T b) { return a + b; }
```

### 组合concept
```cpp
template<typename T>
concept RandomAccessRange = Range<T> && requires(T t) {
    { t[0] } -> std::convertible_to<typename T::value_type>;
};

```
### 模板中使用 concept
```cpp
template<Range T>
void sort(T& x) { }

template<typename T>
requires Range<T>
void sort(T& x) { }
```

## concept + traits 协同设计
### traits 提供类型信息 + concept 做语义约束
```cpp
template<typename T>
concept HasValueType = requires { typename T::value_type; };

template<typename T>
concept Container = HasValueType<T> && requires(T t) {
    t.begin();
    t.end();
};

template<Container C>
void process(C& c) {
    using value_t = typename C::value_type; // traits 风格类型提取
    // 进一步操作
}
```
- **概念负责约束**：编译期检查类型契约。
- **traits 提供元信息**：模板内部用于提取类型或计算属性。
- 形成明确分工：概念 + traits。
### 组合 concept 替代复杂 traits 检测
原本需要多层 traits 嵌套判断：
```cpp
template<typename T>
struct is_random_access_iterable {
    static constexpr bool value = is_iterable<T>::value && 
                                  std::is_same_v<typename T::iterator::iterator_category, std::random_access_iterator_tag>;
};

```

使用 concept 改写：

```cpp
template<typename T>
concept RandomAccessIterable = Iterable<T> &&
    requires(T t) {
        typename T::iterator::iterator_category;
    } && std::is_same_v<typename T::iterator::iterator_category, std::random_access_iterator_tag>;
```

### 过渡策略总结
1. **优先用 concept 表达语义约束**。
2. **traits 保留类型属性提取功能**。
3. **模板内部用 traits，模板外部用 concept**。
4. **逐步替换**：老代码可先封装 traits 为 concept，再逐步清理原 traits 判断。

# 高级技巧简介
## constexpr 与编译期计算
- **用途**：让函数、变量在编译期求值，提高效率，支持模板元编程。
- **常见用法**：
    - `constexpr` 函数：可以在编译期使用，配合非类型模板参数实现计算。
    - `consteval` 函数：强制在编译期求值。
    - 编译期状态机、递归计算（如阶乘、斐波那契）。
        
- **特点**：
    - 与模板结合可以实现“模板元编程 → 编译期编程”。
    - 编译期求值比运行时更高效。
### 概念
`constexpr` 是 C++11 引入的关键字，其核心目的是 **让表达式在编译期求值**，从而提升效率，同时支持模板元编程。

特点：
1. **编译期求值**：编译器尝试在编译期计算值，如果无法在编译期求值，也可以在运行时使用（前提是函数允许）。
2. **与 `const` 的区别**：
    - `const` 表示“值不可修改”，但不保证编译期求值。
    - `constexpr` 表示“可在编译期求值”，编译器会尽量在编译期求值。
3. **支持复杂表达式**：现代 C++（C++14 以后）允许 `constexpr` 函数包含条件语句、循环等，增强了表达力。

### 用法简要举例
```cpp
/////// 旧写法
template<int N>
struct Factorial {
    static constexpr int value = N * Factorial<N - 1>::value;
};

template<>
struct Factorial<0> {
    static constexpr int value = 1;
};

constexpr int f5 = Factorial<5>::value; // 编译期求值 120


/////// 新写法
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

constexpr int f6 = factorial(6); // 720
```
从 C++14 开始，`constexpr` 函数功能增强：
1. **允许循环**：
2. **允许局部变量和条件判断**：增强逻辑复杂度。
3. **支持递归计算**

注意事项：
- **递归深度**：编译期递归过深可能导致编译器报错或性能下降。
- **非编译期变量**：`constexpr` 函数参数必须是可在编译期确定的值才能在编译期求值。
- **限制操作**：
    - C++11：函数体只能包含单条 `return` 语句。
    - C++14 之后：允许局部变量、循环、条件分支。


## decltype技巧
- **用途**：根据表达式推导类型，尤其在模板元编程中，方便提取函数返回值类型或变量类型。
- **常见用法**：
    `template<typename T, typename U> auto add(T t, U u) -> decltype(t + u) { return t + u; }`
- **特点**：
    - 避免手动书写复杂类型。
    - 与 `auto`、模板结合可生成灵活的类型推导函数。

### 概念
`decltype` 是 C++11 引入的关键字，用于**在编译期推导表达式的类型**。它的作用类似于 `auto`，但 `auto` 是推导变量类型，而 `decltype` 更强调**获取表达式的类型，而不是变量的类型**。

```cpp
int a = 5;
decltype(a) b; // b 的类型是 int
decltype(a + 0.0) c; // c 的类型是 double，因为表达式 a + 0.0 的类型是 double
```
- 不会对表达式进行求值，只用来推导类型。
- 可以获取左值引用、右值引用、常量属性等完整类型信息。

```cpp
int x = 0;
int& xr = x;

decltype(x) a;   // int
decltype(xr) b = x; // int&
decltype((x)) c = x; // int& 注意：加括号后，表达式是左值，所以得到引用
```
- 对于变量本身，`decltype(var)` 得到的是变量类型。
- 对于括号包裹的表达式，`decltype((var))` 如果是左值，则得到左值引用类型。

### 用法简要举例
在模板编程中，经常遇到“如何自动推导返回值类型”的问题。`decltype` 可以完美解决这个问题，特别是当返回值类型依赖于模板参数时。

```cpp
template<typename T, typename U>
auto add(T t, U u) -> decltype(t + u) {
    return t + u;
}
```

类似 `void_t` ，检查表达式是否合法：
```cpp
decltype(expr, void())
```

## 利用函数签名提取类型
- **用途**：通过函数模板或偏特化，获取函数参数、返回值类型，便于模板逻辑处理。
- **常见用法**：
    - 提取函数的第一个参数类型。
    - 提取成员函数指针、返回值类型。
    - 与 `std::function_traits`、自定义 meta 函数结合。

这部分，我们在前面有提到过： [[#如何提取函数的第一个参数类型？]]

## 编译期列表
- **用途**：管理一组类型或值，实现编译期循环、映射或组合。
- **常见用法**：
    - `std::index_sequence` / `std::integer_sequence` 生成编译期序列。
    - 类型列表（TypeList）进行递归处理或模式匹配。
    - 值列表（ValueList）进行 fold、累加等编译期运算。
        
- **特点**：
    - 与变长模板参数结合，实现灵活的模板展开。
    - 是高级模板库（如 Boost.MPL / TMP）常用手段。

### Integer Sequence（整数序列）
`std::index_sequence` 和 `std::integer_sequence` 是 C++14 引入的模板工具，用于在编译期生成整数序列。
    
核心作用：配合 **变长模板参数**，实现对序列的遍历、展开、映射等。

```cpp
#include <utility>
#include <iostream>

template<std::size_t... Is>
void print_index_sequence(std::index_sequence<Is...>) {
    ((std::cout << Is << " "), ...);  // fold expression (C++17)
}

int main() {
    print_index_sequence(std::make_index_sequence<5>{});  // 输出: 0 1 2 3 4
}

```

**展开元组或数组参数包**
```cpp
#include <tuple>

template<typename Tuple, std::size_t... Is>
void print_tuple(const Tuple& t, std::index_sequence<Is...>) {
    ((std::cout << std::get<Is>(t) << " "), ...);
}

int main() {
    auto t = std::make_tuple(1, 2, 3);
    print_tuple(t, std::make_index_sequence<3>{}); // 输出: 1 2 3
}
```

### TypeList（类型列表）
TypeList 是一种将一组类型封装在模板参数包中的手段：

```cpp
template<typename... Ts>
struct TypeList {};
```
- **递归处理类型**：比如实现条件筛选、映射或连接类型。
- **编译期映射/计算**：可以对每个类型应用元函数。

**示例：获取 TypeList 长度**
```cpp
template<typename... Ts>
struct TypeList {};

template<typename List>
struct Length;

template<typename... Ts>
struct Length<TypeList<Ts...>> {
    static constexpr std::size_t value = sizeof...(Ts);
};

int main() {
    using MyTypes = TypeList<int, double, char>;
    std::cout << Length<MyTypes>::value; // 输出: 3
}
```

**示例：类型映射**
```cpp
template<typename T>
struct AddPointer { using type = T*; };

template<typename... Ts>
struct Transform;

template<typename... Ts>
struct Transform<TypeList<Ts...>> {
    using type = TypeList<typename AddPointer<Ts>::type...>;
};

using MyTypes = TypeList<int, double>;
using PtrTypes = Transform<MyTypes>::type; // TypeList<int*, double*>
```

**示例：类型筛选**
```cpp
#include <type_traits>

// Filter 元函数
template<template<typename> class Pred, typename List>
struct Filter;

template<template<typename> class Pred>
struct Filter<Pred, TypeList<>> {
    using type = TypeList<>; // 空列表
};

template<template<typename> class Pred, typename Head, typename... Tail>
struct Filter<Pred, TypeList<Head, Tail...>> {
private:
    using TailResult = typename Filter<Pred, TypeList<Tail...>>::type;

public:
    using type = std::conditional_t<
        Pred<Head>::value,
        TypeList<Head, TailResult>, // 保留 Head
        TailResult                  // 跳过 Head
    >;
};

/// 使用示例：

using MyTypes = TypeList<int, double, char, float, long>;

// 只保留整型
using IntegralTypes = Filter<std::is_integral, MyTypes>::type;

```


### ValueList（值列表）
**integer_sequence 拓展**
- `std::integer_sequence<int, ...>`
- `std::index_sequence`（用于索引）

**示例：计算编译期和**
```cpp
#include <utility>

template<int... Ns>
constexpr int sum(std::integer_sequence<int, Ns...>) {
    return (0 + ... + Ns); // fold expression
}

int main() {
    constexpr int s = sum(std::integer_sequence<int, 1, 2, 3, 4>{});
    static_assert(s == 10);
}

```

**示例：与 index_sequence 配合**
```cpp
#include <array>
#include <iostream>

template<typename T, std::size_t N, std::size_t... Is>
void print_array(const std::array<T, N>& arr, std::index_sequence<Is...>) {
    ((std::cout << arr[Is] << " "), ...);
}

int main() {
    std::array<int, 4> arr = {10, 20, 30, 40};
    print_array(arr, std::make_index_sequence<arr.size()>{}); // 10 20 30 40
}

```

### 总结
- **TypeList 与 IndexSequence 配合**
    - 用索引序列访问类型列表或元组。
        
- **值列表 Fold/累加**
    - 用整数序列进行编译期求和、乘积等。
        
- **递归元函数**
    - 通过 TypeList 递归处理每个类型，实现条件筛选或类型转换。