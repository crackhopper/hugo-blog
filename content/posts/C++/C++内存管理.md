---
id: art_31d9c405e6306a4410db3dbbea4d5c23
title: C++内存管理
date: 2025-12-16T18:16:06+08:00
tags:
  - cpp
  - memory-management
  - raii
  - gc
draft: false
---
![[C_内存管理-intro-01.png]]


本文主要围绕C++内存管理。也会介绍C++的RAII机制，以及其他语言的内存管理（GC）。

本文内容相对比较深度，对 **初级开发人员不友好** 。

<!--more-->

# C++内存管理基础

所谓内存管理，主要是管理堆上的内存。我们先从一些基础原理出发，然后不断深入和展开。
## 接口概述

先看一个总结表：

|分配方式|内存释放方式|额外行为|
|---|---|---|
|`malloc/calloc/realloc`|`free(ptr)`|不调用构造/析构函数|
|`new T`|`delete p`|调用对象析构函数|
|`new T[n]`|`delete[] arr`|调用每个元素析构函数|
|`operator new`|`operator delete(ptr)`|只释放内存，不调用析构函数|
|自定义 `operator new`|对应自定义 `operator delete`|可控制分配和释放策略|

掌握接口是基础中的基础。我们这里仅快速回顾一下。
## C语言接口
```c
void *malloc(size_t size);
```
- malloc: memory allocation
- 在堆上分配指定大小 size（字节）的连续内存空间。
- 内存未初始化，里面的内容是 **随机值（垃圾值）**。
- 返回指向分配内存的指针，如果分配失败返回 `NULL`。

```c
void *calloc(size_t nitems, size_t size);
```
- calloc: contiguous allocation
- 在堆上分配 `nitems` 个元素，每个元素大小为 `size` 字节的连续内存，并 **初始化为 0**。
- 返回指向分配内存的指针，如果分配失败返回 `NULL`。

```c
void *realloc(void *ptr, size_t new_size);
```
- 调整之前分配的内存块 `ptr` 的大小为 `new_size` 字节。
	- 如果新大小大于原大小，原有数据保持不变，新增部分未初始化。
	- 如果 `ptr` 为 `NULL`，效果等同于 `malloc(new_size)`。
	- 如果 `new_size` 为 0，效果类似于 `free(ptr)`。（注意这个是implementation-defined，常见实现等同于free；因此不要用这个特性）
	- 注意：**如果失败，返回NULL，但是原本的 ptr 仍然有效。**
- 可以扩展或缩小原有内存块。
- 可能在堆上移动内存（返回的新指针可能不同于原指针）。

```c
void free(void* ptr);
```
- 将 之前由动态内存分配函数获得的堆内存 归还 。可以释放由 `malloc/calloc/realloc`  分配的内存
- `free` **只释放内存**


## new operator (C++语法)
```cpp
T* p = new T;           // 分配一个 T 类型对象，并调用构造函数
T* arr = new T[n];      // 分配一个 T 类型数组，并调用每个元素的构造函数
```
- **类型安全**：返回对应类型的指针，无需类型转换。
- **构造函数调用**：在分配内存后，会调用对象的构造函数。
- **失败行为**：
	-  默认情况下，如果分配失败，会抛出 `std::bad_alloc` 异常。
    
**可以使用 `nothrow` 版本避免异**
```cpp
T* p = new (std::nothrow) T;
```

释放方式
- 对象：`delete p;` 会调用析构函数并释放内存。
- 数组：`delete[] arr;` 会调用每个元素析构函数并释放内存。

## operator new(C++操作符)
new operator在分配内存的时候，也需要类似C语言调用对应的malloc/calloc/realloc 。在C++中，这个动作被定义为 operator new 。默认标准库在全局作用域提供一个 `::operator new` 。整个operator new的机制和C++操作符重载机制类似。（因此，operator new 只负责分配内存，并不负责调用构造函数；因此，还有另一个操作，仅负责调用构造函数，不负责分配内存，叫 placement new，下一个小结会讲）

```cpp
// 全局 operator new。可以被替换
void* operator new(std::size_t size) {
    return std::malloc(size);
}

void operator delete(void* ptr) noexcept {
    std::free(ptr);
}

// 某个类的重载
struct B {
    static void* operator new(std::size_t size) {
        return std::malloc(size);
    }

    static void operator delete(void* ptr) noexcept {
        std::free(ptr);
    }
    // 同样可以定义
    // void* operator new[](size_t size); 
    // void operator delete[](void* ptr); 
};
```
- 注意，上面的operator定义必须成对出现。
- 仅负责分配和释放内存。不负责调用构造和析构函数。(类似C的malloc和free)
- 返回 `void*`，需要类型转换。（直接调用operator new的时候，少见）
- 如果分配失败，默认会抛出 `std::bad_alloc`。

**注意：现实中还要处理 size == 0、对齐、异常等**

## placement new(C++语法)
如果内存已经分配好，希望在该内存上调用构造函数，必须使用 placement new。

```cpp
void* buffer = /* 已分配好的内存 */;
T* obj = new (buffer) T(constructor_args...);
```
- `buffer`：已经存在、且足够大、对齐正确的内存
- `T(constructor_args...)`：正常调用构造函数
- **不会分配内存**
- **只调用构造函数**

## 如何用allocator管理对象创建和销毁
首先，什么是allocator。这里先简单介绍。

Allocator 是一种将“内存分配策略”与“对象生命周期管理”解耦的抽象机制，用于为容器或组件提供可定制的内存来源。（这个说法仍然很抽象）

更简单点，可以理解为一个类，包含两个成员函数：
```cpp
T* allocate(std::size_t n); // n是元素个数
void deallocate(T* p, std::size_t n); // n是元素个数
```
- allocator 只负责 分配和释放原始内存。（因此功能有点像被抽象出单独的类，实现 operator new/delete 的功能）
- allocator 内部实现的时候，可能自己已经创建好了比较大块的内存（比如内存池），或者实现了内存管理算法。因此allocator本身可以用来辅助C++管理内存。

仅有上面的机制，如何创建和释放C++对象呢？这就用到我们之前学习的基础语法：

（这里是简化的逻辑）
```cpp
MyAllocator alloc;

// 创建对象
void* raw = alloc.allocate(sizeof(T)); // 调用allocator创建
T* p = new (raw) T(args...); // placement new

// 销毁对象
p->~T();              // 1. 显式析构
alloc.deallocate(p); // 2. 释放内存
```

## STL容器内如何创建和销毁对象
我们只讲比较新版本的C++。答案是利用 `allocator_traits` 。

关于什么是 `traits` 可以参看 [[C++模板元编程初探]] 。这里简要来说，traits定义了allocator的接口，只要符合traits的要求，那么traits就可以把我们自定义的allocator和C++的标准库容器对接。

标准库内，如果要创建要创建/销毁对象，对应的调用为：
```cpp
// 创建
T* p = alloc.allocate(1); // 实际上这步骤也是调用 std::allocator_traits 的 allocate 函数，转发到这个调用
std::allocator_traits<A>::construct(alloc, p, args...);

// 销毁
std::allocator_traits<A>::destroy(alloc, p);
alloc.deallocate(p, 1); // 实际上这步骤也是调用 std::allocator_traits 的 deallocate 函数，转发到这个调用
```
- `std::allocator_traits<A>::construct` : 相当于调用 placement new。（内部实现也是这样）
- `std::allocator_traits<A>::destroy`  ： 相当于调用 `~T()` 析构函数。


所以，当
```cpp
std::vector<T, MyAlloc> v;
v.emplace_back(args...);
```
- 此时就是走上面的创建流程。

## 进阶：pmr 和 memory_resource (C++17)
传统allocator的“类型绑定”过强
```cpp
std::vector<int, MyAlloc<int>> v;
```
- allocator 是 **模板参数** 。改Allocator等于改类型，这导致了接口污染、类型膨胀。
- allocator 类型必须在 **编译期确定**。无法根据运行时策略切换内存来源
- allocator 之间 **难以共享内存池** 。每个 allocator 类型一套逻辑

**pmr（Polymorphic Memory Resource）正是为了解决这些问题而引入的。** 核心思想：
- **把“内存策略”从模板参数，变成运行时多态对象。**

pmr 的关键抽象是：
```cpp
std::pmr::memory_resource
```

它是一个 **运行时多态的内存分配接口**，本质上类似于：
```cpp
struct memory_resource {
    virtual void* do_allocate(size_t bytes, size_t alignment) = 0;
    virtual void  do_deallocate(void* p, size_t bytes, size_t alignment) = 0;
    virtual bool  do_is_equal(const memory_resource&) const noexcept = 0;
};
```
- 以字节为单位分配（不是元素个数）
- 支持对齐
- 使用虚函数 → 运行时多态

pmr 并没有直接让容器用 `memory_resource`，而是引入了一个桥接器：
```cpp
std::pmr::polymorphic_allocator<T>
```
- **对外表现为 allocator**
- **内部把分配请求转发给 memory_resource**

关系可以理解为：
```
STL 容器
   ↓ allocator_traits
polymorphic_allocator<T>
   ↓ 虚函数
memory_resource
```

因此：
```cpp
std::pmr::vector<int> v;

// 等价于
std::vector<int, std::pmr::polymorphic_allocator<int>> v;
```

同时我们可以运行时绑定不同的内存资源。（但是类型是一样的，并没有类型膨胀）
```cpp
std::pmr::monotonic_buffer_resource pool1;
std::pmr::monotonic_buffer_resource pool2;

std::pmr::vector<int> v1{ &pool1 };
std::pmr::vector<int> v2{ &pool2 };
```

如果没有显示传入 `memory_resource` ，那么使用：
```cpp
std::pmr::get_default_resource()
```
- 默认是 `new_delete_resource()`
- 可通过 `set_default_resource()` 替换（**谨慎使用**）

## 进阶：常见 `memory_resource` 实现
### 1. `new_delete_resource`
- 底层使用 `::operator new/delete`
- 行为接近普通 STL allocator
- **默认资源**

### 2. `monotonic_buffer_resource`
本质上类似： linear allocator ，或者说 arena/region allocator

特点：
- 只分配，不单独释放
- 整个 resource 析构时统一释放
- 分配速度快

适合场景：
- 短生命周期对象
- 批量创建、整体销毁
- 临时计算 / 解析 / 构建阶段

### 3. `unsynchronized_pool_resource`
可以理解为简化版的 `tlsf` 内存管理。

- 内部维护多个 free list
- 适合频繁小对象分配
- **非线程安全**
- 性能优于通用 allocator

### 4. `synchronized_pool_resource`
- 线程安全版本
- 有锁，性能略低

### 自定义实现(粒子池)
考虑一种自定义内存池：
- **对象固定大小**，比如 `sizeof(Particle)`
- **快速分配/释放**，O(1) 或接近 O(1)
- **复用已释放的内存**
- **支持 pmr 接口**，即继承 `std::pmr::memory_resource`
典型做法是 **自由链表（free list）+ 内存块**。

```cpp
#include <memory_resource>
#include <cstddef>
#include <cassert>

struct Particle { /* 粒子数据 */ };

class fixed_pool_resource : public std::pmr::memory_resource {
public:
    fixed_pool_resource(std::size_t object_size, std::size_t capacity,
                        std::pmr::memory_resource* upstream = std::pmr::get_default_resource())
        : object_size_(object_size), capacity_(capacity), upstream_(upstream) 
    {
        assert(object_size_ >= sizeof(void*));
        allocate_block();
    }

protected:
    void* do_allocate(std::size_t bytes, std::size_t alignment) override {
        assert(bytes <= object_size_ && alignment <= alignof(std::max_align_t));
        if (!free_list_) allocate_block();
        void* result = free_list_;
        free_list_ = *reinterpret_cast<void**>(free_list_);
        return result;
    }

    void do_deallocate(void* p, std::size_t bytes, std::size_t alignment) override {
        *reinterpret_cast<void**>(p) = free_list_;
        free_list_ = p;
    }

    bool do_is_equal(const memory_resource& other) const noexcept override {
        return this == &other;
    }

private:
    void allocate_block() {
        char* block = static_cast<char*>(upstream_->allocate(object_size_ * capacity_, alignof(std::max_align_t)));
        blocks_.push_back(block);
        // 将 block 划分为 free_list
        for (std::size_t i = 0; i < capacity_; ++i) {
            void* ptr = block + i * object_size_;
            *reinterpret_cast<void**>(ptr) = free_list_;
            free_list_ = ptr;
        }
    }

    std::size_t object_size_;
    std::size_t capacity_;
    std::pmr::memory_resource* upstream_;
    void* free_list_ = nullptr;
    std::vector<void*> blocks_; // 用于释放整个 pool
};
```
关键逻辑：
- `alignment <= alignof(std::max_align_t)` : 检查内存对齐可以支持。如果更高的内存对齐，需要在 `allocate_block` 里专门实现。
- 链表操作：**每个空闲单元的前 sizeof(void) 字节存放指针**
	- `free_list_ = *reinterpret_cast<void**>(free_list_);` 链表向后移动一个位置。
	- `*reinterpret_cast<void**>(p) = free_list_;` 把释放的p作为链表头插入进来。
	- 需要注意，内存只有是free，被管理的时候，我们才使用这个指针。而被allocate之后，对象会覆盖这个指针（但不影响我们管理free）


使用示例：
```cpp
int main() {
    fixed_pool_resource particle_pool(sizeof(Particle), 1024);
    std::pmr::polymorphic_allocator<Particle> alloc(&particle_pool);
    std::pmr::vector<Particle> particles{&alloc};

    // 构造对象
    Particle* p = alloc.allocate(1);
    new (p) Particle();  // placement new

    // 销毁对象
    p->~Particle();
    alloc.deallocate(p, 1);
}
```

当然这个对新手不友好，可以再封装一层：
```cpp
class ParticlePool {
public:
    ParticlePool(std::size_t capacity)
        : pool_(sizeof(Particle), capacity) {}

    // create 对象：分配 + 构造
    template<typename... Args>
    Particle* create(Args&&... args) {
        void* mem = pool_.allocate(1);
        return new (mem) Particle(std::forward<Args>(args)...);
    }

    // destroy 对象：析构 + 释放
    void destroy(Particle* p) {
        if (!p) return;
        p->~Particle();
        pool_.deallocate(p, 1);
    }

private:
    fixed_pool_resource pool_;
};
```

# 资源获取即初始化 (RAII, Resource Acquisition Is Initialization）
RAII（**Resource Acquisition Is Initialization，资源获取即初始化**）是一种重要的编程范式，最早系统化地出现在 **C++** 中，但其思想对许多现代语言和资源管理机制都产生了深远影响。RAII 的核心目标是：**用对象的生命周期来严格、自动地管理资源的生命周期**，从而避免资源泄漏、状态不一致和异常路径下的管理错误。

我们这里提到这个，主要是内存管理的时候，为了更好的管理内存资源、以及方便使用。用到RAII也非常常见。

## RAII 的核心思想
RAII 的基本原则可以概括为两点：
1. **资源的获取发生在对象构造阶段**
2. **资源的释放发生在对象析构阶段**

这里的“资源”是一个广义概念，包括但不限于：
- 动态内存（`new` / `malloc`）
- 文件句柄（`FILE*`、`std::fstream`）
- 互斥锁 / 自旋锁
- 网络 socket
- 数据库连接
- GPU / OS 句柄等系统资源

在 RAII 中：
- **只要对象存在，资源一定处于有效状态**
- **对象一旦离开作用域，资源必然被释放**

这使得资源管理与作用域（scope）形成了强绑定关系。
## RAII 的工作机制（以 C++ 为例）
### 构造函数：获取资源
```cpp
class File {
public:
    File(const char* path) {
        fp = fopen(path, "r");
        if (!fp) {
            throw std::runtime_error("open failed");
        }
    }
```
构造函数要么成功获取资源并建立不变式，要么直接失败（抛异常），**不存在“半初始化”状态**。

### 析构函数：释放资源
```cpp
    ~File() {
        if (fp) {
            fclose(fp);
        }
    }

private:
    FILE* fp;
};
```
析构函数具有以下关键特性：
- **自动调用**（离开作用域时）
- **异常安全**（不会被绕过）
- **与控制流无关**（`return`、`break`、`throw` 均可）
### 使用方式
```cpp
void process() {
    File f("data.txt");
    // 使用 f
} // 离开作用域，f 析构，文件自动关闭
```
调用者无需关心资源释放逻辑，这正是 RAII 的价值所在。
## RAII 与异常安全（Exception Safety）
RAII 被认为是 **C++ 异常安全的基石**，原因在于：
- 异常会导致栈展开（stack unwinding）
- 栈展开过程中，所有已构造完成的对象都会被析构
- RAII 保证析构函数释放资源

```cpp
void foo() {
    std::lock_guard<std::mutex> lock(m);
    risky_operation(); // 即使这里抛异常，锁也会被释放
}
```
无需 try/catch 或 finally，异常路径与正常路径具备完全一致的资源释放语义。

## RAII 的典型应用场景
### 智能指针
```cpp
std::unique_ptr<Foo> p(new Foo());
// 离开作用域自动 delete
```
智能指针本质上就是“**把裸指针的资源管理 RAII 化**”。
### 锁管理
```cpp
std::lock_guard<std::mutex> guard(m);
```
避免以下错误：
- 忘记解锁
- 多重 return
- 异常路径遗漏解锁
### 文件与流
```cpp
{
    std::ofstream out("log.txt");
    out << "hello";
} // 自动 flush + close

```
### 事务管理（逻辑资源）
```cpp
Transaction tx(db);
tx.commit();
```
析构函数中：
- 未提交则自动 rollback

这属于 **扩展意义上的 RAII**。

### RAII 的设计原则
一个“合格的 RAII 类型”通常具备以下特征：
1. **构造即完全可用**
2. **析构必然释放资源**
3. **析构函数不抛异常**
4. **资源所有权清晰**
5. **禁止或显式定义拷贝 / 移动语义**

例如：
- 禁止拷贝，只允许移动（`unique_ptr`）
- 明确共享语义（`shared_ptr`）

## Go语言如何实现RAII
因为Go也是我主力语言。这里简单增加一些内容。
### defer：Go 的核心 RAII 工具
`defer` 用于在函数退出时执行清理操作。特点：
- **执行时机确定**：函数返回（正常或 panic）时自动调用。
- **顺序栈**：多个 defer 语句按 **后进先出** 执行。

```go
func readFile(path string) error {
    f, err := os.Open(path)
    if err != nil {
        return err
    }
    defer f.Close() // 离开函数时自动关闭

    // 使用文件
    data := make([]byte, 100)
    _, err = f.Read(data)
    return err
}
```

### 通过封装实现 RAII 风格
```go
type File struct {
    *os.File
}

func OpenFile(path string) (*File, error) {
    f, err := os.Open(path)
    if err != nil {
        return nil, err
    }
    return &File{f}, nil
}

func (f *File) Close() {
    f.File.Close()
}

// 使用
func process() error {
    f, err := OpenFile("data.txt")
    if err != nil {
        return err
    }
    defer f.Close() // 类似 RAII 的析构释放
    // 使用 f
    return nil
}
```

### 总结
在 Go 中可以总结为：
1. **构造函数负责获取资源**
2. **Close/Release 方法负责释放资源**
3. **函数作用域结束时，用 `defer` 调用释放方法**


## Typescript如何实现RAII
同样，Typescript也是我的主力语言。这里补充一些说明。
### 通过类封装 + dispose 方法
```ts
class FileResource {
    private handle: any;

    constructor(path: string) {
        // 模拟打开文件
        console.log(`Opening file: ${path}`);
        this.handle = { path };
    }

    read() {
        console.log(`Reading file: ${this.handle.path}`);
    }

    dispose() {
        console.log(`Closing file: ${this.handle.path}`);
        this.handle = null;
    }
}

```
### 使用时结合 try/finally
```ts
function processFile(path: string) {
    const file = new FileResource(path);
    try {
        file.read();
        // 其他操作
    } finally {
        file.dispose(); // 确保资源释放
    }
}

processFile("data.txt");
```

### 总结
- **构造函数负责获取资源**
- **`dispose()` 方法负责释放资源**
- **作用域结束用 `try/finally` 调用 `dispose()`**

# 智能指针基础
智能指针是基于RAII对动态内存管理的一种实践。目标是：
- 明确 **对象所有权**
- 自动释放资源
- 提供异常安全保证
- 与 STL 容器、算法良好协作

掌握智能指针的使用，基本是C++最基础的基础功。我们这篇文章讲解上则要相对更深入一些。
## `unique_ptr`
### 核心语义
**独占所有权（Exclusive Ownership）**

同一时刻，只能有一个 `unique_ptr` 拥有对象。**不可拷贝，但可以移动** 。（关于C++移动语义，是现代C++的核心特性，本身也有较多的内容，等有空再补充对应的文章吧。可以简单理解为 **移动=内存的复用** ，这个机制主要用来解决C++语言定义下大量临时对象所有权转移产生的开销。而rust受此印象，以转移语义为基础设计了语言）
```cpp
std::unique_ptr<Foo> p(new Foo);

std::unique_ptr<Foo> p1 = std::make_unique<Foo>();
std::unique_ptr<Foo> p2 = std::move(p1); // OK
```

### 内存模型
`unique_ptr` **几乎等价于一个裸指针 + deleter**
- 不含引用计数
- 零额外堆分配（默认）
- 通常可以被优化为 **零成本抽象**
	- 注：如果自定义deleter，则还额外包含一个deleter的指针。

```cpp
template<class T, class Deleter>
class unique_ptr {
    T* ptr;
    Deleter del;
};
```
注意： **Deleter 是 `unique_ptr` 类型的一部分**  会影响 sizeof
### 自定义 deleter（重点）
可以使用函数对象（lambda）定义deleter：
```cpp
auto deleter = [](Foo* p) {
    std::cout << "custom delete\n";
    delete p;
};

std::unique_ptr<Foo, decltype(deleter)> p(new Foo, deleter);
```


适配非 `new/delete` 资源
```cpp
std::unique_ptr<FILE, decltype(&fclose)> fp(fopen("a.txt", "r"), fclose);
```
- 注：这里 `fopen` 返回的是 `FILE*` 类型。

### 使用场景
- 单一持有者
- 容器中存放
- 高性能
- 不共享生命周期
## `shared_ptr`
### 核心语义
**共享所有权（Shared Ownership）**
- 包含引用计数
- 对象在 **最后一个 `shared_ptr` 销毁时释放**。

### 内存模型
`shared_ptr` 的关键在于 **控制块**（Control Block） 。每个具体指针(ptr) 的 `shared_ptr` 会共享一个控制块。同时 `shared_ptr` 为了符合多线程模型，对控制块的操作定义了原子操作。

控制块通常包含：
- 强引用计数（use_count）
- 弱引用计数（weak_count）
- deleter
- allocator（可能）

内存结构：
```
┌────────────┐        ┌─────────────────┐
│ shared_ptr │ ────▶  │ control block   │
└────────────┘        │  strong count   │ (control block 也有大概率内嵌object)
            │         │  weak count     │
            │         │  deleter        │
	        │         └─────────────────┘
		    │
		    ▼
		  ┌────────┐
		  │ object │
		  └────────┘
```

解释：
1. control block 再第一次创建 `shared_ptr` 的时候，和对象内存同时创建。因此创建到一起只会有一次内存分配。因此，control block这个模板类提供了一个封装，通常会内嵌一个object。（尤其是通过 `make_shared` 和 `allocate_shared` 创建的 `shared_ptr` ；当然如果是传入的裸指针，那么不在额外分配对象的内存)
	1. 但是随后基于同一个智能指针创建的 `shared_ptr` ，会共享这个control block。
	2. 注意：**基于同一个裸指针创建的shared_ptr，并不会共享control block** ，因为要支持这个操作明显需要查表，性能上不会允许这么做。这样的用法也是错误用法。
2. 如果创建的时候指定了 allocator，那么allocator的引用（指针）也会保存在 control block中。 `shared_ptr` 会在释放的时候调用allocator。
3. 如果创建的时候指定了 `deleter` ，类似allocator，也是在释放的时候使用。

### 自定义deleter/allocator
自定义deleter，类似 `unique_ptr` ，但要注意 `make_shared` 调用无法自定义deleter。
```cpp
std::shared_ptr<FILE> fp(
    fopen("a.txt", "r"),
    [](FILE* f) {
        if (f) fclose(f);
    }
);
```
- `shared_ptr<T>` **始终持有的是 `T*`**
- deleter：
    - 只存 **一份**（在 control block 中）
    - 被 **所有共享该 control block 的 shared_ptr 使用**
- 当 `use_count == 0` 时：
    - control block 调用 deleter 销毁对象

注意： **deleter 被 类型擦除（type-erased）** 即deleter的类型并不会让 `shared_ptr` 的类型发生改变（即该模板参数不影响模板类型定义）。这个做法和 `unique_ptr` 是不一样的，这是因为 `shared_ptr` 要支持赋值语义，为了更方便支持跟不包含deleter定义的ptr兼容，必须要擦除掉deleter的类型。deleter具体的实现方式是通过虚函数或函数指针表 ，具体这里不展开。


此外，`shared_ptr` 还支持传入allocator：
```cpp
std::allocator<Foo> alloc;

std::shared_ptr<Foo> sp(
    new Foo,
    [](Foo* p) { delete p; },
    alloc
);
```
**重要语义（必须理解）**
- allocator **只用于 control block**
- **不负责 object**
- object 的释放由 deleter 决定


更加推荐的用法 `allocate_shared`:
```cpp
// template<class T, class A, class... Args>
// shared_ptr<T> allocate_shared(const A& a, Args&&... args);

std::pmr::polymorphic_allocator<Foo> alloc{resource};
auto sp = std::allocate_shared<Foo>(alloc, 1, 2, 3);
```
- allocator用于同时创建 control block 和 object 。且仅进行1次分配。
- 异常安全。

常见误区： 
- 误区 1：allocator 控制 object 生命周期 （正解：仅控制control block，除非用 `allocate_shared`）
- 误区 2：每个 shared_ptr 都有自己的 deleter / allocator （正解：每个control block一份）
- 误区 3：make_shared 比 shared_ptr(p, d) 慢： （正解：通常更快，因为仅一次分配）

使用建议：

|需求|推荐方案|
|---|---|
|普通共享对象|`make_shared`|
|需要自定义释放|`shared_ptr(p, deleter)`|
|高性能内存管理|`allocate_shared` + pmr|
|管理 C 资源|`shared_ptr<T>(p, deleter)`|
|对象池|自定义 deleter|

### 循环引用问题（重点）
因为 `shared_ptr` 靠引用计数管理，因此，循环引用会造成内存泄露。

假设我们有三个对象 A, B, C，每个对象都持有 `shared_ptr` 指向下一个对象：
```cpp
{
    auto a = std::make_shared<Node>("A");
    auto b = std::make_shared<Node>("B");
    auto c = std::make_shared<Node>("C");

    // 构建循环引用：A -> B -> C -> A
    a->next = b;
    b->next = c;
    c->next = a;

    // 离开作用域
}
```
- 当创建结束时，每个对象引用计数是1
- 当互相持有时，每个对象引用计数是2
- 离开作用域时：（仅减少自身计数）
	- 于是，A，B，C引用计数均减1，最后仍然有1个引用计数。导致内存泄露。

而如果没有构成循环，比如 `A->B->C` 的情况下：
- A引用计数1，B和C引用计数为2.
- 离开作用域时:
	- A计数归零，导致A节点被析构
	- 此时才会触发 `a->next` 被析构，从而进一步降低B的引用计数，最终整体都成功析构

上面的根本原因是： **循环引用阻碍了对象自身的析构，而对象自身析构又是触发成员 shared_ptr 析构的前提，因此成员 shared_ptr 永远不会被释放，从而导致内存泄漏。**


如何解决这个问题？避免互相持有的语义，而使用 `weak_ptr` 的引用语义。严格区分什么时候持有，什么时候引用。
## `weak_ptr`
### 核心语义
**观察者，不拥有对象**
- 不增加强引用计数
- 用于打破循环引用

```cpp
// 可以通过 shared_ptr 直接创建
std::weak_ptr<Foo> wp = sp; // 拷贝初始化 copy-initialization。（不一定调用拷贝构造函数，同时一般也不会拷贝，因为有copy elision；所以说这个初始化名字确实很误导人；这个用法和使用参数初始化用法没有本质区别）

// 可以通过 lock 返回 shared_ptr
if (auto sp = wp.lock()) {
    sp->do_something();
}
```

当然因为其不拥有对象，所以不涉及到 deleter 和 allocator 的设定。
### 内存模型
和 `shared_ptr` 一样共享 control block。只不过使用的是weak count。

当然只有存在了 `shared_ptr` 才能创建 `weak_ptr`

### 使用场景

|场景|用途|
|---|---|
|父子节点|子引用父|
|缓存|非拥有引用|
|观察者模式|observer|

## 如何配合`pmr::memory_resource` 使用？

### unique_ptr + pmr 
```cpp
struct PmrDeleter {
    std::pmr::memory_resource* res;

    void operator()(Foo* p) noexcept {
        p->~Foo();
        res->deallocate(p, sizeof(Foo), alignof(Foo));
    }
};
```

使用：
```cpp
void* mem = res->allocate(sizeof(Foo), alignof(Foo));
Foo* f = new (mem) Foo(1, 2);

std::unique_ptr<Foo, PmrDeleter> p(f, {res});
```


### shared_ptr + pmr
```cpp
std::pmr::polymorphic_allocator<Foo> alloc{resource};
auto p = std::allocate_shared<Foo>(alloc);
```

### 高性能场景示例（对象池）
```cpp
std::pmr::unsynchronized_pool_resource pool;
auto alloc = std::pmr::polymorphic_allocator<Foo>(&pool);

auto p = std::allocate_shared<Foo>(alloc);
```
适用于：
- 游戏引擎
- 高频交易
- 实时系统

局限性和注意：
- **对象大小不固定时效率下降**
    - `unsynchronized_pool_resource` 内部使用多个 block size
    - 对象大小大于 block → heap fallback
    - 对象非常小 → 内存可能浪费
- **缺少固定大小对象池的确定性**
    - 对固定大小对象池：
        - 分配/释放非常快，O(1)
        - 内存紧凑，没有分块浪费
        - 可控内存上限，避免 heap 扩张
    - `unsynchronized_pool_resource` 更通用，但可能有少量 overhead
- **多线程需要注意**
    - `unsynchronized_pool_resource` **不是线程安全的**
    - 多线程共享必须使用 `synchronized_pool_resource` 或自定义同步

## 最佳实践

|场景 / 特点|推荐智能指针|
|---|---|
|单一所有权、局部对象|`unique_ptr`|
|多处共享、生命周期复杂|`shared_ptr + weak_ptr`|
|临时访问共享对象|`weak_ptr`|
|高频分配 / 内存池 / 对象内嵌控制块|`allocate_shared + PMR`|

一种常见的做法：
- 高层对象持有低层对象 ，使用 `unique_ptr` / shared_ptr （尽可能更多使用 `unique_ptr`）
- 低层对象引用高层对象 ，使用 `weak_ptr`


# 垃圾回收机制基础 (Garbage Collection)
垃圾回收机制（Garbage Collection，简称 **GC**）是计算机科学中的一种内存管理技术，它的核心目标是**自动回收**程序中不再使用的内存空间。

GC机制通过**自动判断**哪些内存是“垃圾”（即程序后续不会再访问的对象），并将其清理掉，从而避免了这些问题，极大地减轻了开发者的负担。

在 C++ 中，**原生语言并不自带 GC**，内存管理主要依靠手动管理 (`new/delete`) 或智能指针（如 `std::shared_ptr`、`std::unique_ptr`）。  

但为了应对复杂对象图、循环引用等问题，也有一些 C++ GC 框架或技术存在（如 **Boehm GC** 或 Unreal Engine 的 UObject GC）。  

基本思路仍与传统 GC 相似：**标记可达对象、回收不可达对象**。

## 主要的GC算法
### Mark-Sweep算法
**Mark-Sweep** 是最基础的垃圾回收算法，原理如下：
1. **Mark（标记阶段）**  
    从根对象（stack/global/static）出发，递归标记所有可达对象。
2. **Sweep（清扫阶段）**  
    扫描堆中所有对象，将未被标记的对象回收。

优缺点：
- **优点:** 实现简单。
- **缺点:** 会产生大量的**内存碎片**，导致后续分配大对象时可能没有足够的连续空间。

### Copying算法
将内存分为大小相等的两块，每次只使用其中一块。当这块用完时，将**存活对象**复制到另一块上，然后清空当前块。

优缺点：
- 优点: 不产生碎片，回收效率高。
- 缺点: 内存利用率低，永远只有一半内存可用。常用于对象生命周期很短的新生代。
### Mark-Compact算法
分为“标记”和“整理”两个阶段：
1. **标记**所有可达对象。
2. **整理**（移动）所有存活对象，使其向一端移动，然后清理掉边界以外的内存。

优缺点：
- 优点: 不产生碎片。
- 缺点: 移动对象需要进行大量的引用更新，效率较低。常用于对象生命周期较长的老年代。

### Stop-The-World (STW)
在执行 GC 时，为了保证数据的一致性，有时需要暂停所有的应用线程，直到垃圾回收工作完成，这个现象称为 Stop-The-World (STW)。

STW 是所有 GC 机制都无法避免的，但现代 GC 算法（如 G1、ZGC、Shenandoah）通过并发（与应用线程同时运行）和增量（分小片执行）等技术，已经将 STW 的时间降到极低，从而减少对用户程序的影响。


## 精确GC和保守GC
- **精确式 GC (Accurate/Precise GC)** : 
	- 在内存中，每个对象通常包含**字段**，这些字段可能是：对象引用（指针）或原始数据。
	- 精确GC的特点是：GC **完全知道**对象中哪些字段是指针，哪些是非指针值
	- 在标记阶段，只跟踪指针字段来判断可达对象
	- 非指针字段（整数、浮点数）不会被当作指针误判
	- 通常有rootset，从rootset的对象出发，进行mark标记。
- **保守式 GC (Conservative GC)** : Boehm GC 运行在 C/C++ 这样的环境中
	- 无法完全确定内存中的一个值是否真的是一个指针。
	- 一个 32 位的整数和一个恰好指向堆内存的地址值在位模式上可能是完全相同的。
	- 保守策略：任何看起来像指针的值，**都会被当作指针来处理**。 （会导致一些整数有一定概率被当作堆上的指针，从而让对应的指针被mark，而不被释放）

## 标记数据的存储方式
### 对象头（Object Header）标记
大多数 JVM 和一些 C++ GC（如 UE GC）在**每个对象头**存储一个或几个标志位，用于记录对象是否被标记。

- 优点：
    - 内存访问局部化
    - 标记直接在对象上修改，快速
- 缺点：
    - 每个对象增加头部开销（通常 1–2 字节）
    - 并发 GC 需要注意写屏障，防止覆盖标记

**示例（Java 对象头）**：
```
[Mark Word | Klass Pointer | Fields...]
Mark Word 可以包含：
- hashcode
- GC 标记位
- 偏向锁标志等
```

### 外部标记表（Bit Map / Side Table）
GC 维护一张单独的**位图（bitmap）** 或数组， 每个堆对象对应一位或几位表示是否被标记 。
- 优点：
    - 不修改对象头，适合只读或不可修改对象
    - 并发 GC 易于管理，多线程安全
- 缺点：
    - 需要额外内存
    - 访问对象标记需要间接索引 ： 可能降低访问效率

当然仅靠这个表也不够，因为不知道对象在堆上具体占有的空间大小。通常还要配合对象头，或者额外的其他信息表才行。


### 两种方式结合（Hybrid）
JVM 一些实现（如 HotSpot）：
- 对象头存放部分标记信息（快速、短期标记）
- 对于并发或增量 GC，额外使用 bit map / remembered set 保存标记变化

## Boehm GC
Boehm-Demers-Weiser Garbarge Collector（简称 **Boehm GC**）是一个非常独特且具有历史意义的垃圾回收器。

Boehm GC 采用标准的**可达性分析**来判断对象存活，但其根集（GC Roots）的确定方式是保守的：

### 算法过程
- **确定根集 (Roots):**
    - **全局变量区 (Static Data):** 扫描所有静态/全局变量的值。
    - **栈 (Stack):** 扫描当前所有线程的栈帧中的值。
    - **寄存器 (Registers):** 扫描所有 CPU 寄存器中的值。
        
- **保守扫描 (Conservative Scan):**
    - 在上述所有根集区域中，如果一个内存地址中的值 $V$ 落在当前的堆分配区域内（即 $V$ 是一个有效的堆地址），则**保守地认为 $V$ 是一个指向堆对象的指针**。
    - 即使 $V$ 实际上是一个非指针数据，它指向的对象也会被标记为存活。
        
- **标记过程 (Marking):**
    - 从所有被识别的“指针”开始，递归地遍历和标记它们所指向的对象及其所有内部字段。
    - **内部指针 (Interior Pointers):** Boehm GC 允许一个指针指向一个对象的**内部**（比如 C++ 中指向数组中间元素的指针）。因此，它需要维护一个数据结构来快速查找：给定一个地址，它是哪个对象的内部？（通常使用平衡树或哈希表来实现）。
### 标记如何存储
- **位图（Bitmap）**
    - 堆被分割成 **分配块（allocation blocks）** 或 **页面（page）**。
    - 每个块对应一个位或几个位，用来表示块内对象是否被标记。
    - 当对象被扫描到时，对应的位被置为“已标记（marked）”。
    - 位图通常在 **堆管理结构中维护**，而不是在对象本身。
        
- **对象头（Object Header）**
    - 对于需要额外信息的对象（例如可移动或需要快速大小查找的对象），Boehm GC 会在对象前面保留一个小的 **header**。
    - Header 通常包含：
        - 对象大小
        - 类型信息（可选）
        - 标记位（有时用于快速扫描）
    - 但是 Boehm GC 的默认策略是 **尽量不修改对象布局**，所以大部分标记信息是在 GC 内部的数据结构中维护的，而不是每个对象中。
        
- **内部数据结构**
    - Boehm GC 会维护一个 **哈希表或平衡树** 来快速查找堆对象及其状态：
        - 给定一个内存地址，判断它是否属于堆。
        - 判断对象是否已经被标记。
    - 这样在 **保守扫描**时，找到一个可能的指针，就可以在内部结构中标记对应对象。

### 如何知道对象的大小
#### 自己记录大小
**每次分配时（`GC_malloc`）**，Boehm GC 会在内部维护：
-  对象起始地址
- 对象大小
这可以通过 **哈希表/平衡树/链表** 实现
        
当扫描到一个可能的指针时：查找哈希表， 得到对象起始地址， 再得到大小
        
这也是处理 **内部指针（interior pointer）** 的关键：
-  如果指针指向对象中间，GC 会查找该地址对应的整个对象，从而知道对象的边界和大小。

#### 在对象前面加 header（可选）
对象前面存一个小 header，记录对象大小。

对于 C/C++，Boehm GC 尽量不做，因为会改变对象布局，影响程序。

大部分情况下，GC 使用自己的堆元信息（heap metadata）来存储大小，而不是对象本身。

### 应用
由于 Boehm GC 是一个稳定且经过充分测试的**保守式** GC，它被用作许多早期的或跨平台运行时环境的基础，尤其是那些需要在原生代码上运行的语言：

- **早期的 Unity/Mono 运行时:**
    - 在 Unity 引擎的早期版本（如 1.x 到 2.x，以及一些通过 **IL2CPP** 编译的 Unity 工程）中，Mono 虚拟机（Microsoft .NET 移植平台）最初使用的是 **Boehm GC** 作为其托管堆的垃圾回收器。
    - 后来，Mono 切换到了更现代的 **SGen GC**，但 Boehm GC 在这个领域留下了深远影响。
        
- **GNU Java 编译器运行时环境 (GCJ):**
    - GCJ 是 GNU 编译器集合（GCC）的一部分，它能够将 Java 源代码编译成本地机器代码。在它的运行时环境中，Boehm GC 被用于管理 Java 对象的内存。
        
- **D 语言:**
    - **D 语言**是一种旨在结合 C++ 性能和 Java/C# 安全性的系统级编程语言。在其早期实现中，Boehm GC 是其默认的垃圾回收器。
        
- **各种脚本语言和解释器:**
    - 一些需要在 C/C++ 核心上实现的脚本语言（如一些 Lisp、Scheme 或 Smalltalk 的实现），可能会选择使用 Boehm GC 来快速为其提供内存管理能力。

总结： **Boehm GC，更加适用于开发一个语言编译器或者解释器的时候，采用的简单技术** 。后续迭代的时候，则需要完善语言的对象系统，从而嵌入更加高级的GC，比如SGen GC
## Unreal Engine UObject GC
Unreal Engine (UE) 的垃圾回收系统专为游戏的高性能和确定性需求设计。它主要针对继承自 `UObject` 类的对象进行管理，采用**非自动的引用计数机制（`TWeakObjectPtr`, `TSoftObjectPtr`）**与**精确的 Mark-Sweep 机制**相结合的方式。

### 算法过程
UE 的 GC 流程与传统的 Mark-Sweep 类似，但其触发和根集确定与 C++ 环境高度集成。

#### 确定根集 (GC Roots)
UE 的 GC Roots 是**精确**的，而不是保守的。它依赖于 UE 对象系统（`UObject`）和其特殊的指针类型（`TArray`, `TMap`, `UPROPERTY` 宏等）来精确识别哪些对象被持有。

**全局根集 (Global Roots):**
- 所有**当前正在引用的**（例如，通过 `AddToRoot()` 或作为全局结构的一部分）对象。
- **Persistent Roots:** 如 `UWorld`、`UGameInstance` 等顶级对象。
- 任何嵌入在 `UObject` 的 UPROPERTY 成员指针也间接形成可达链，但根对象本身通常是这些全局/持久对象。

**栈/局部变量 (Stack/Local Variables):**
- **`UObject` 指针的局部变量通常不会被视为 GC Roots**。UE GC 是**不安全**的，因为它不会扫描 C++ 栈或寄存器。（因此这个GC无法支持多线程）
- **唯一例外**：通过 `TGuardValue` 或特定的 GC 保护机制（如 **Fast Path**）显式添加到根集的对象。

**属性引用 (Property References):**
- 通过反射系统（**Reflection System**）识别，所有被 `UPROPERTY()` 宏标记的指针字段，指向的对象都被视为可达。

从这部分描述可以看出，UEGC本身被触发的时候，大部分运行栈应该已经退出，GC运行在更底层的栈上。因此不用考虑栈上的对象是否要添加到RootSet中。下面是AI的补充：
- 栈上的局部变量确实不自动成为根，但如果你在 `AddReferencedObjects` 或 `FGCObject::AddReferencedObjects` 中引用了它们，它们就会被 GC 遍历。
- 所以在复杂系统中，如果临时对象需要在 GC 扫描期间存活，你必须用显式机制保护它。
#### 标记阶段 (Marking)
从根集开始，GC 递归地遍历所有可达的 `UObject`。
- **遍历机制：** GC 使用 **Reflection** 获得对象的类结构，并只沿着被 `UPROPERTY()` 宏标记的指针（属性）进行深度遍历。
- **标记存储：** 每个 `UObject` 的**对象头（Header）**中都包含一个**标记位（Mark Bit）**。当对象被遍历到时，该标记位会被设置（通常在 `GUObjectArray` 这个全局数据结构中）。

#### 清扫阶段 (Sweeping)
清扫阶段会遍历 GUObjectArray（全局对象列表），并处理所有未被标记的对象。
- 未标记对象： 未被标记的对象被视为垃圾。
	- 首先，调用对象的 BeginDestroy() 生命周期方法，进行资源释放前的清理工作。
	- 然后，对象的内存被释放，并从 GUObjectArray 中移除。
- 被标记对象： 清除标记位，等待下一轮 GC。
### 应用与特点
UE GC 是一个为**游戏开发**高度优化的 GC 系统。
- **精确性和可控性：** GC 仅通过 **Reflection** 识别的指针进行遍历，因此它是**精确**的。GC 周期是**可控**的，不会在关键帧自动触发，而是由开发者在安全点（如关卡加载、帧结束等）手动或定时触发。
- **性能优化：** 标记和清扫可以进行**增量（Incremental）**操作，将工作分散到多帧中，以避免在游戏运行时造成卡顿（Stuttering）。
- **处理循环引用：** 传统的引用计数无法处理循环引用，但 UE GC 使用 **Mark-Sweep** 机制，能够优雅地回收相互引用的垃圾对象（A 引用 B，B 引用 A，但两者都不可达）。

### 对比Boehm GC

|**特点**|**Boehm GC**|**Unreal Engine UObject GC**|
|---|---|---|
|**解决的根本问题**|在 **原生 C/C++ 环境** 中，没有对象系统，栈和寄存器中可能的值类型不可知，**如何安全地进行自动内存管理**。|在 **有反射的 C++ 框架** 中，如何提供**可控、增量、高性能**的 GC，以避免游戏卡顿。|
|**GC 根集的复杂度**|**极高。** 需要保守地扫描所有寄存器和栈上的内存地址，并判断其是否指向堆。这是**实现最困难**的部分，因为它跨越了 GC 和 CPU/OS 边界。|**低/中等。** 根集是**精确**的，只扫描 `GUObjectArray` 和 `UPROPERTY` 标记的指针。复杂度在于**集成 C++ 的反射系统**。|
|**GC 触发与控制**|自动触发（**Automatic**）。当内存分配失败或达到阈值时运行，GC 暂停时间不可控。|手动或定时触发（**Controlled**）。由开发者决定何时运行，支持**增量运行**，需要复杂的调度系统。|
|**对象信息依赖**|**不依赖**对象本身。所有元数据（大小、标记）都在 GC 内部的**哈希表或平衡树**中维护。|**高度依赖** UE 的 **Reflection System** 和 `UObject` 的对象头。没有反射系统，GC 就无法工作。|
|**系统兼容性**|**高。** 目标是尽可能不修改 C/C++ 程序的布局和语义。|**低。** 仅适用于继承自 `UObject` 的对象，且必须使用 UE 的宏和指针类型。|
## Java的GC
为了确保 GC 能够准确、安全地工作，JVM 在代码编译、即时编译（JIT）和运行时中，会额外添加以下关键机制：
### SafePoint（安全点）
**定义与目的：** SafePoint 是 JVM 代码执行流中，一个允许 GC **安全地**和**精确地**检查所有线程栈和寄存器中 GC Root 引用位置的“暂停点”。

JVM 提供的机制：
- **指令插入：** JVM 的 JIT 编译器（如 C2）会在方法调用、循环回跳（Loop Back Edge）、异常处理等**非叶子方法**的关键位置**插入 SafePoint 检查指令**。
- **状态切换：** 当 GC 准备运行时，它会发出请求，所有线程在执行到下一个 SafePoint 时，必须**主动暂停**（自愿合作）。

为什么提供？
- **实现 STW (Stop-The-World)：** GC 需要在短时间内冻结所有用户线程，以便进行**精确**的可达性分析和内存整理。SafePoint 是实现这一暂停的基础。
- **保证引用可见性：** 只有在 SafePoint 处，线程的执行状态是**已知**的（即所有 Java 引用都在明确的位置，如栈帧或寄存器中），GC 才能准确扫描。在其他任意位置暂停，可能导致 Java 引用被藏在 CPU 管道或临时寄存器中，GC 无法找到。

### OopMap（对象指针地图）/ LiveMap
**定义与目的：** OopMap（在 HotSpot JVM 中通常也称为 LiveMap 或 GC Map）是一种由 JIT 编译器生成的**元数据**，它描述了在特定 SafePoint 处，**栈帧和寄存器中哪些值是 Java 对象指针（Oop, Ordinary Object Pointer）**。

JVM 提供的机制：
- **编译期生成：** JIT 编译器在生成机器码的同时，会为每个 SafePoint 生成一个 OopMap。
- **运行时查询：** 当一个线程在 SafePoint 暂停时，GC 线程会查阅该 SafePoint 对应的 OopMap。

为什么提供？
- **实现精确 GC：** OopMap 是 JVM 实现**精确 GC** 的关键。它告诉 GC ：“在这个线程的当前栈帧中，地址 $A$ 上的值是一个对象引用，地址 $B$ 上的值是一个整数，请只扫描 $A$。”
- **避免保守扫描：** 这与 Boehm GC 的**保守扫描**形成了鲜明对比。通过 OopMap，JVM 避免了猜测，从而保证了回收的**正确性**和**高效性**。

### Card Table / Remembered Set（记忆集）
**定义与目的：** 这是 JVM 为了优化**跨代引用**（老年代对象引用了新生代对象）扫描而引入的机制，主要用于实现高效的**分代 GC**。

JVM 提供的机制：
- **写屏障（Write Barrier）插入：** 在代码中执行**指针赋值操作**（例如 `a.field = b`）时，JIT 编译器会**额外插入指令**，将引用方的内存区域标记为“脏（Dirty）”。
- **Card Table 维护：** Card Table 是一个位图数组，代表老年代的内存块（Card）。如果老年代中的 Card 引用了新生代的对象，那么对应的位会被设置为脏。

为什么提供？
- **加速 Young GC：** 在进行新生代 GC (Minor GC) 时，GC 不需要扫描整个老年代来寻找跨代引用。它只需要扫描 Card Table 中被标记为“脏”的少数 Card，大大**减少了根集的扫描范围**，是分代 GC 高效运行的核心。

### Barrier（屏障）- 特别是读写屏障
**定义与目的：** 屏障是一种特殊的、由编译器（JIT）或解释器在**对象字段访问操作**前后插入的底层代码指令。它们是实现复杂并发 GC（如 CMS、G1、ZGC、Shenandoah）的关键。

**JVM 提供的机制：** 插入额外的代码或指令来跟踪对象的引用关系变化。
- **写屏障 (Write Barrier):** 在**引用赋值**时插入。
	- 会在写入操作前增加一个 `write_barrier(A, C);`  的内联代码，判断要不要触发额外逻辑。（比如额外着色逻辑）。有多种类别的写屏障。
- **读屏障 (Read Barrier):** 在**读取对象字段**时插入。
	- 同上类似，读取操作前内联一部分代码。比如像 **ZGC/Shenandoah** 这种**并发移动**的 GC，以确保用户线程在对象被 GC 移动时能拿到**新的转发地址**。 （通常并不会有锁，同时虽然有地址的差异，但程序上不可见，因为java语言访问不到物理地址）

为什么提供？
- **实现并发标记：** 屏障让 GC 线程可以在用户线程运行时同时进行标记，通过记录用户线程对对象引用图的修改，来确保并发标记的正确性。
- **实现并发整理：** 读屏障使得 GC 可以在不暂停用户线程的情况下移动对象，解决了并发 GC 中最难的**并发移动**问题，从而实现了极低的 GC 暂停时间。


### 三色标记算法 (Tri-color Marking)
#### 三种颜色及其含义

| **颜色**         | **含义**                                                                         | **GC 状态** |
| -------------- | ------------------------------------------------------------------------------ | --------- |
| **白色 (White)** | **不可达对象**。该对象尚未被 GC 访问，或最终被证明是不可达的。在标记阶段结束后，所有白色对象都是**垃圾**，将被回收。               | 待访问/垃圾    |
| **灰色 (Gray)**  | **正在访问的对象**。该对象本身是活的，但它的**引用字段（其包含的指针）还没有全部被扫描**。灰色对象会继续被 GC 访问，直到其所有子对象都被处理完。 | 正在扫描      |
| **黑色 (Black)** | **已访问对象**。该对象是活的，且**其所有引用字段（子对象）都已经被扫描完毕**。黑色对象在本次 GC 周期内不会再被访问。               | 存活/已完成    |

#### 算法过程
从 GC 根集（GC Roots）开始：
1. **初始状态：** 所有对象都是 **白色**。
2. **根集标记：** 从 GC Roots 开始，将所有直接被根集引用的对象标记为 **灰色**。
3. **并发遍历：** GC 线程从 **灰色** 集合中取出一个对象 $A$，将其所有引用的子对象（它们此刻还是 **白色**）全部标记为 **灰色**。
4. **转为黑色：** 对象 $A$ 的所有子对象都被处理完毕后，对象 $A$ 本身被标记为 **黑色**，并放回堆中。
5. **循环结束：** 重复步骤 3 和 4，直到 **灰色** 集合为空。

### 并发 GC 引入的难题
在 GC 标记阶段，由于用户线程（Mutator）也在同时运行，对象图的引用关系可能会被修改。并发 GC 必须解决两个问题，否则会破坏三色标记的正确性：
1. **漏标 (Lost Objects)：** 将一个**存活对象**错误地标记为 **白色**，导致它被回收。这是**致命的错误**。
2. **浮动垃圾 (Floating Garbage)：** 将一个**已死亡对象**错误地标记为 **黑色** 或 **灰色**，导致它在本次 GC 中无法被回收。这是**性能问题**，需要等到下一次 GC 才能被清理。

考虑漏标问题，导致漏标的充要条件：
1. **用户线程插入了新的引用：** 一个 **黑色** 对象 $A$ 引用了一个 **白色** 对象 $C$
2. 并且 ，所有从 **灰色** 对象到 $C$ 的引用都不存在（或被删除）。

### 解决并发GC问题-屏障技术
#### 增量更新 (Incremental Update)
侧重解决条件 1， **代表 GC：** **CMS (Concurrent Mark-Sweep)**
- **机制：** **写屏障 (Write Barrier)**。当 **黑色** 对象 $A$ 尝试引用新的 **白色** 对象 $C$ 时（即满足条件 1），写屏障会拦截该操作，**将 $C$ 标记为 灰色**。
- **效果：** 即使 $C$ 的所有旧引用被删除（条件 2 发生），由于 $C$ 已经被标记为 **灰色**，GC 会在后续扫描中重新访问它，防止漏标。

#### 原始快照 (Snapshot At The Beginning, SATB) 
侧重解决条件 2，**代表 GC：** **G1 (Garbage-First)**
- **机制：** **写屏障 (Write Barrier)**。当 **灰色** 对象 $B$ 尝试删除对 **白色** 对象 $C$ 的引用时（即满足条件 2），写屏障会拦截该操作，**记录旧的引用 $C$**。 （意思是，这个node只要在并发GC开始前可达，那么就一直保证其可达）
- **效果：** GC 仍然会像并发开始时一样，扫描所有被记录的旧引用。这意味着只要 $C$ 在并发开始时是存活的，它就会被标记为活的（即使它在并发期间死亡），从而**防止漏标**。

**SATB 的代价：** SATB 倾向于保留更多的**浮动垃圾**，因为即使对象 $C$ 很快死亡，它也会被记录下来并在本次 GC 中存活。但由于它只需要记录旧引用，屏障的开销通常比增量更新小。
#### final remark
即使有写屏障 / 读屏障保障，在并发 GC 的最终回收阶段仍需短暂 Stop-The-World（STW），以避免用户线程创建的新引用未被捕获。  
在 STW 期间，GC 会：
1. **进行最终 mark**，扫描根集、线程栈和队列中尚未标记的对象
2. **进行回收（Sweep / Reclaim）**，释放不可达对象  

通过这种方式，即便在并发阶段有新引用出现，也能保证不会漏标或回收活对象。

## 其他语言GC选择
理解了java语言GC的机制，其他语言上基本类似或者是简化的版本。
### Go
- **GC 类型**：Go 使用 **并发标记-清除（Concurrent Mark-and-Sweep）** GC。
- **特点**：
    - 自动内存管理，无需手动释放对象。
    - 并发 GC 能在用户 Goroutine 执行时进行标记，减少 STW 暂停时间。
    - 使用 **写屏障（Write Barrier）** 保证并发标记的正确性，类似 Java 的 SATB 机制。
    - Go 的 GC 设计注重 **低延迟和较小暂停时间**，但吞吐量略低于完全 STW GC。
        
- **简化说明**：没有 SafePoint/OopMap 等复杂机制，Goroutine 调度和栈扫描结合实现并发标记。
### TypeScript
- **GC 类型**：主要由运行时（如 V8）实现 **分代 GC + 精确标记-清除**。
- **特点**：
    - 自动内存管理，开发者无需手动释放。
    - 分代回收：**新生代对象**采用快速复制（Scavenge）算法，**老年代对象**采用标记-清除或标记-整理。
    - 使用 **精确 GC**，跟踪对象引用，无需像 C/C++ 那样保守扫描。
    - GC 暂停通常较短，但高密度对象分配仍可能造成小幅 STW。
- **简化说明**：JavaScript GC 更依赖运行时优化，开发者不直接接触线程或屏障机制。

**单线程执行模型**
- JavaScript 在浏览器或 Node.js 中是 **单线程运行**（主线程执行用户代码）。
- 用户代码（Mutator）和 GC 线程不会同时操作堆，也就是说，**GC 运行时可以假设用户线程处于暂停状态**。
- 因此，不需要写屏障或读屏障来捕获用户线程对对象引用的修改，因为**在 GC 开始时，用户代码已经停止**。

### 总结

|**特性**|**Java**|**Go**|**TypeScript / JavaScript (V8)**|
|---|---|---|---|
|**GC 类型**|分代 GC + 并发/并行 GC（如 G1, CMS, ZGC）|并发标记-清除（Concurrent Mark-and-Sweep）|分代 GC + 标记-清除 / 标记-整理|
|**主要机制**|SafePoint, OopMap, Card Table, 写/读屏障, 三色标记|写屏障, Goroutine 栈扫描, 三色标记|分代扫描, 精确标记, 新生代快速复制, 老年代标记清除|
|**暂停策略**|STW + 并发标记（短暂停）|并发标记 + 小幅 STW|短暂停（STW）|
|**并发支持**|支持并发标记和部分并发整理|支持并发标记，写屏障保证标记正确性|支持并发，但依赖运行时优化|
|**分代支持**|新生代 + 老年代|有概念上的新生代/老生代，但实现更简化|分代（新生代/老年代）|
|**写屏障/读屏障**|写屏障（增量更新/SATB）、读屏障用于并发移动|写屏障（类似 SATB）|无明确屏障机制，GC 内部处理|
|**特点**|精确 GC，支持高并发、低延迟|简化机制，重视低延迟和可预测暂停|轻量级，运行时自动管理，无需开发者关注 GC|
# 现代C++推荐的内存管理

**现代 C++ 的主流实践并不推荐引入通用 GC（垃圾回收），而是以 RAII 为核心，配合智能指针、明确的对象所有权语义，以及在需要时使用自定义 allocator / 内存池来解决内存管理问题。**  
但这个结论有**明确的前提和边界条件**，并非“GC 在 C++ 中永远不合理”。

## 为什么现代 C++ 不推崇通用 GC
### C++ 的设计哲学与 GC 天然不匹配
C++ 的核心理念包括：
- **确定性资源管理（deterministic destruction）**
- **零成本抽象（zero-cost abstraction）**
- **资源 ≠ 内存**（文件、锁、socket、GPU 资源等）
    
而 GC 的典型特征是：
- 对象释放时间 **不确定**
- 需要运行时跟踪对象可达性
- 通常只管理“内存”，不管理其他资源

这与 C++ 的 RAII 模型存在根本冲突。
```cpp
{
    std::lock_guard<std::mutex> lock(m);
    // 临界区
} // 作用域结束，立即释放锁
```
GC 语言无法表达这种“作用域即生命周期”的语义。
### C++ 已经有非常强的静态内存管理工具链
现代 C++（C++11 之后）在内存管理方面已经发生质变：

1）明确的所有权语义
- `std::unique_ptr`：独占所有权
- `std::shared_ptr`：共享所有权（带引用计数）
- `std::weak_ptr`：打破循环引用

这使得**对象生命周期在类型系统层面是可表达的**。


2）RAII 是语言级模式
- 析构函数是确定性调用
- 与异常机制完美配合
- 无需运行时扫描堆

3）编译期即可验证大量错误
- double free
- 泄漏（大部分场景）
- use-after-free（配合 sanitizers / 静态分析）

GC 则把问题推迟到运行期。

### 性能与可预测性要求
在很多 C++ 的核心应用领域中：
- 游戏引擎
- 实时系统
- 高频交易
- 操作系统 / 驱动
- 嵌入式系统

**暂停不可接受**，哪怕是毫秒级。

GC 的问题不只是“慢”，而是：
- **暂停时间不可控**
- 内存访问局部性变差
- 与 CPU cache / NUMA / 对象布局冲突


而 RAII + 自定义 allocator 可以做到：
- 完全可预测
- cache-friendly
- 与业务模型紧密贴合

## 为什么“智能指针 + RAII + 自定义 Allocator”是主流解法
本质上是**分层内存管理模型**：
### 第一层：RAII（根基）
- 生命周期绑定作用域
- 统一管理“所有资源”

这是现代 C++ 的根。

### 第二层：智能指针（表达所有权）
- **不是为了“自动释放”**
- 而是为了**表达语义**

现代 C++ 的共识是：
> “先设计所有权模型，再决定是否需要智能指针。”

### 第三层：Allocator / 内存池（性能与规模）
当出现以下情况时，引入自定义 allocator 是合理的：
- 大量小对象频繁分配/释放
- 对象生命周期高度一致（arena / region）
- 需要减少碎片
- 需要与硬件/平台特性匹配
    

典型模式包括：
- Pool allocator
- Arena allocator
- Frame allocator
- TLSF、jemalloc、tcmalloc
- `pmr::*`（C++17）

## 那 GC 在 C++ 中完全没价值吗？
### GC 在 C++ 中的合理使用场景
- 原型系统 / 快速验证
- 复杂图结构、难以定义清晰所有权
- 上层脚本化系统（如游戏脚本层）
- 学术 / 实验性项目
    

例如：
- Boehm GC
- LLVM/Clang 内部某些子系统（有限场景）

但这些都是**局部、可选、非语言级**的 GC。

## 重要补充：避免一个常见误区
**现代 C++ ≠ 到处用 `shared_ptr`**
- `shared_ptr` 是“最后的手段”
- 默认应使用：
    - 栈对象
    - 值语义
    - `unique_ptr`
- allocator 是架构级决策，不是“随手优化”
    
GC 和 `shared_ptr` 的滥用，本质上是同一类问题：**逃避所有权建模**。