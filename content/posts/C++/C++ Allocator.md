---
id: art_975aff2370f7d22dffe82fe76d5a9ce2
title: C++ Allocator
date: 2025-12-10T15:30:01+08:00
tags: []
draft: true
---


摘要：

<!--more-->

# 正文
```cpp
template <typename T>
struct Alloc {
    template <typename U>
    struct rebind {
        using other = Alloc<U>; // 重绑定类型
    };

    T* allocate(size_t n) { return new T[n]; }
    void deallocate(T* p, size_t n) { delete[] p; }
};
```


```cpp
template <typename Alloc>
struct allocator_traits {
    using allocator_type = Alloc;
    using value_type = typename Alloc::value_type;

    template <typename U>
    using rebind_alloc = typename Alloc::template rebind<U>::other;

    static value_type* allocate(Alloc& a, size_t n);
    static void deallocate(Alloc& a, value_type* p, size_t n);
    
    template <typename... Args>
    static void construct(Alloc& a, value_type* p, Args&&... args);

    static void destroy(Alloc& a, value_type* p);
};

```

推到 element_type:
```cpp
using value_type = typename std::pointer_traits<typename Alloc::pointer>::element_type;
// or
using value_type = typename Alloc::template rebind<void>::other; // 特殊处理
```


# `allocator_traits` 作用
## 1. 类型成员
容器需要获取分配器类型或对象类型，以便定义内部指针、节点类型。
### 没有 allocator_traits 的情况：
```cpp
std::allocator<int> alloc; 
using ValueType = decltype(alloc)::value_type; // 很简单，但复杂分配器可能没有直接 value_type
```

- 如果用户自定义分配器没有 `value_type`，容器代码就会报错。
- 容器代码必须对每个分配器做不同处理。

### 使用 allocator_traits：
```cpp
using Traits = std::allocator_traits<std::allocator<int>>; 
using ValueType = Traits::value_type; // 一致性保证，兼容自定义分配器
```
- 这种情况，不强制要求 allocator一定有value_type。
- 但是，allocator仍然需要有至少几个成员之一：value_type, pointer_type 之类的。
- 所以整体上，`allocator_traits` **放松** 了对 allocator “结构”上的约束。

## 2. rebind_alloc

容器内部可能需要不同类型的分配器。例如 `list<T>` 内部节点是 `Node`，不是 `T`。

### 没有 allocator_traits：
```cpp
std::allocator<int> alloc; // 直接用 alloc 分配 Node 会报错
```
- 自己手动处理 rebind 很麻烦，还要写 SFINAE 处理老分配器。
    

### 使用 allocator_traits：
```cpp
struct Node {
	int value; 
};
std::allocator<int> alloc; 
using NodeAlloc = std::allocator_traits<decltype(alloc)>::rebind_alloc<Node>;
NodeAlloc nodeAlloc; // 可以分配 Node
```

**这里一方面放松约束，另一方面，traits可能本身提供一种rebind_alloc的实现？毕竟只是返回一个模板类**

**实际行为（简化）是：**
```cpp
template<class Alloc, class T>
using rebind_alloc =
  // if Alloc::template rebind<T>::other exists:
  typename Alloc::template rebind<T>::other
  // else:
  Alloc<T>  // assuming Alloc is a template
```
也就是说：
- 兼容 **旧 allocator（C++03 style rebind）**
- 兼容 **新 allocator（模板本身就是 `Alloc<T>`）
- 容器无需关心历史包袱


## 3. allocate / deallocate

在容器内部分配和释放内存。
### 没有 allocator_traits：
```cpp
std::allocator<int> alloc;
int* p = alloc.allocate(5);    // OK，但不同分配器可能接口不同
alloc.deallocate(p, 5);
```

- 如果分配器缺少 `allocate` 或使用自定义签名，容器必须写很多分支代码。
- 对自定义分配器的兼容性差。

### 使用 allocator_traits：
```cpp
std::allocator<int> alloc;
int* p = std::allocator_traits<decltype(alloc)>::allocate(alloc, 5); // 统一接口
std::allocator_traits<decltype(alloc)>::deallocate(alloc, p, 5);
```

**这里整体类似类型成员的访问，相当于放松了约束**


## 4. construct / destroy
在分配好的内存上构造对象，以及销毁对象，但不释放内存。
### 没有 allocator_traits：
```cpp
int* p = alloc.allocate(1);
alloc.construct(p, 42); // 旧式做法
alloc.destroy(p);
alloc.deallocate(p, 1);

```

- 新标准分配器可能没有 `construct` 或 `destroy`。
- 容器必须做 SFINAE 检查或者自己写 placement new：

```cpp
new (p) int(42);  // 手动构造
p->~int();        // 手动销毁
```
    


### 使用 allocator_traits：
```cpp
int* p = std::allocator_traits<decltype(alloc)>::allocate(alloc, 1);
std::allocator_traits<decltype(alloc)>::construct(alloc, p, 42); // 自动处理兼容性
std::allocator_traits<decltype(alloc)>::destroy(alloc, p);
std::allocator_traits<decltype(alloc)>::deallocate(alloc, p, 1);
```

**作用**：
- 对缺失 `construct` / `destroy` 的分配器，`allocator_traits` 会提供默认实现（使用 placement new 和析构）。
- 容器无需判断分配器类型，统一操作。

# 总结
**allocator_traits 是一种适配器，它允许 allocator 具有更松散、演进式的结构，而容器通过 traits 获得一致、可靠的接口。**

**allocator_traits 不是简单转发，而是“检测 + 默认实现 + 规范化行为”**


更加好的描述：
- allocator_traits 是一个 规范化（normalization）与能力检测（capability detection）工具，用于将 allocator 的异构接口映射到统一的容器所需语义。

有了traits的好处是：考虑定义一个类型，可以被模板类使用
- 以前定义的时候，需要符合模板类的约束。（但很可能不同模板类的用法也有区别，同时这个用法由分散在代码的各个实现中）
- 有了traits后，只需要符合traits的约束。traits的语义相对集中，更容易查阅。并且traits本身可以放松对类型的约束，自己通过“检测 + 默认实现 + 规范化行为”，来完善约束条件。

不过需要注意： **traits 无法消除“本质语义约束”**


# SFINAE
## case 1
```cpp
template<typename T,
    typename = std::enable_if_t<std::is_integral_v<T>>
>
void f(T);
```

- `typename=...` 默认模板参数实参。
	- 这个参数名都没有。说第二个参数仅仅用来做 SFINAE，只是指挥编译器做事情。


关于这里面的meta function:
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

根据上面的定义，我们可以讲解一下面这个代码，

```cpp
enable_if<is_integral<T>::value>::type
```
- 整体作用，T为整数时，类型存在

基于这些，定义原来代码：
```cpp
template<typename T,
    typename = enable_if<is_integral<T>::value>::type
>
void f(T);
```
那么，当我们用 
```cpp
f(1); // 成功实例化，T为int，所有检查都通过
f(0.3); // 失败，is_integral<T>::value ，返回值为false，从而enable_if中不存在type成员，替换失败。编译器查找是否有其他重载，如果没有，则直接失败。
```

总结：
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

**所以，标准库容器，如果使用allocator。用法类似。额外用一个模板参数，调用 `enable_if_t<allocator_traits_v<T>>` 这样的类似的逻辑，判断某个Allocator类型传入到模板参数T的时候，是否符合要求**

传统做法 (c++11/14)：
```cpp
template<
    typename T,
    typename Allocator = std::allocator<T>,
    typename = std::enable_if_t<
        allocator_traits<Allocator>::propagate_on_container_copy_assignment::value
    >
>
class MyContainer { ... };

```

更新式的做法
```cpp
template<typename Allocator>
void foo(Allocator alloc) {
    if constexpr (std::is_same_v<typename std::allocator_traits<Allocator>::value_type,
                                 int>) {
        // Allocator::value_type 是 int 时执行
    } else {
        // 其他类型执行
    }
}
```
- `if constexpr` 条件为 `false` 的分支**不会被实例化**
- 不需要额外的模板参数，不依赖 `enable_if`

如果在模板接口层约束，写法更简洁
```cpp
template<
    typename T,
    typename Allocator = std::allocator<T>,
    typename = std::enable_if_t<std::is_copy_constructible_v<Allocator>>
>
class MyContainer { ... };

```
- `std::is_copy_constructible_v<Allocator>` 是布尔值常量，替代原先的 `::value`
- `_t` alias template 代替 `typename enable_if<...>::type`，减少冗余
- 逻辑和 C++11/14 一样，SFINAE 控制模板合法性


C++20结合concept

完全改变了 SFINAE/`enable_if` 的传统写法，让类型约束变得更直观、语义化。下面我帮你梳理如何用 concepts 重写你之前的例子（整数约束、Allocator 约束等）。

```cpp
#include <concepts>
#include <memory>

// traits 封装到 concepts 中，做一些约束接茬
template<typename Allocator>
concept AllocatorLike = requires(Allocator a) {
    typename std::allocator_traits<Allocator>::value_type;
    
    { a.allocate(1) } -> std::same_as<typename std::allocator_traits<Allocator>::pointer>;
};

// 容器模板约束
// 直接使用 concept 代替 typename，对Alloc进行约束检查
template<typename T, AllocatorLike Alloc = std::allocator<T>>
class MyContainer {
    // ...
};
```
-  **Traits 负责提供类型特性，Concept 负责替代 enable_if 的模板约束**
- **enable_if 仅仅是根据traits的value，决定是否导出type。 concept还有更多检查！！**
- **有了concept，一些traits上的偏特化就不需要了，concepts可以直接检查。（有些检查不了的，仍然需要traits来偏特化结果**

concept语法
## case 1 - use concept
```cpp
template<std::integral T>
void f(T);
```
## 基于 traits 的 concept
```cpp
template<typename T>
concept SignedIntegral = std::is_integral_v<T> && std::is_signed_v<T>;

```
- `ConceptName` 是 concept 名称
- `T` 是模板类型参数
- 右侧表达式必须是 **编译期常量 bool**

## requires expression（定义 concept）
```cpp
template<typename T>
concept Addable = requires(T a, T b) {
    { a + b } -> std::convertible_to<T>;
};

```
- `requires(T a, T b)` 定义了一个**表达式约束**
- 花括号里可以检查表达式是否有效
- `-> std::convertible_to<T>` 表示返回类型要求可转换为 T

优点：可以检查成员函数、操作符、返回类型等，enable_if 很难做到

# 深入模板元编程
## 01-requires/detection idiom
```cpp
template<typename T>
concept HasBegin =
    requires(T t) {
        t.begin();
    };

```

## 02-类型变换与计算（Meta-functions）
你需要非常熟练：
- `std::conditional`
- `std::void_t`
- `std::type_identity`
- 偏特化
- 递归模板实例化
- constexpr if
    

这是实现 traits 的“内功”。

## 03-concept + traits 协同设计（关键）
你现在正站在这一层的门口。

设计模式是：
```cpp
template<typename T>
concept Fooable = requires { typename foo_traits<T>::type; };

template<Fooable T>
void f(T);

```

## 04-constexpr + 编译期算法
包括：
- constexpr 函数 vs 模板
- `consteval`
- 编译期状态机
- typelist / value list
- index_sequence

这是“模板元编程 → 编译期编程”的过渡层。


# decltype
获取表达式类型：
```cpp
int& a = x;
decltype(a) b = x; // b 是 int& 引用
```

技巧：
```cpp
decltype(expr, void())
```
- **整个表达式 (expr, void()) 类型是void**
- 先求值 expr，通常有哦你过来做 SFINAE

举例子：
```cpp
template<typename T>
struct has_size {
private:
    template<typename U>
    // 这里多加了一个 void() ，只是为了保险起见。隔离第一个参数的返回值
，    static auto test(int) -> decltype(std::declval<U>().size(), void(), std::true_type());

    template<typename>
    static std::false_type test(...);
public:
    using type = decltype(test<T>(0));
};

```

解析
1. `std::declval<U>().size()`
    - 检查 `U` 是否有 `size()`
    - 如果不合法 → 替换失败 → SFINAE 触发
        
2. `, void()`
    - 强制整个 `decltype` 表达式的类型为 `void`
    - 防止 `decltype(U().size())` 类型不一致或返回值干扰模板推导
        
3. `decltype(test<T>(0))`
    - 如果第一条合法 → 返回 `std::true_type`
    - 不合法 → 匹配第二个 `test(...)` → 返回 `std::false_type`

**这里的 ... 是正常的 C++ 语法，不是省略号的意思，而是 C++ 中的“可变参数函数模板”或“匹配任意类型的降级匹配”机制的一部分。我们详细解析一下。**

