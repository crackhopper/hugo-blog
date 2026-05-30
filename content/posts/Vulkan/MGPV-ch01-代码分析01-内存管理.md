---
id: art_4f8ad38dde84358fc4c1ebe0631233b6
title: MGPK-ch01-代码分析01
date: 2025-12-10T13:10:41+08:00
tags: []
draft: true
---
![[MGPK_ch01_代码分析01-intro-01.png]]

Vulkan Tutorial 已经读完。

接下来进入第二part，深度学习 MGPV《Mastering Programming with Vulkan》 这本书。

这个阶段我们以学习书里的代码、工具、思路为主要目的，随后跟随书里的内容，不断深化。

在这本书推进到一定程度的时候（基础框架和架构都梳理清楚明白了），那么我们就要开始手写自己的渲染器了，并把书里的效果在手写的渲染器里实现。

<!--more-->

# Raptor Engine架构简述
# 代码分析
## main.cpp
```cpp
using namespace raptor;
// Init services
MemoryService::instance()->init(nullptr);
time_service_init();

Allocator *allocator = &MemoryService::instance()->system_allocator;

StackAllocator scratch_allocator;
scratch_allocator.init(rmega(8));
```

## MemoryService
`raptor/foundation/memory.hpp`

```cpp
struct MemoryService : public Service {

	RAPTOR_DECLARE_SERVICE( MemoryService );

	void                        init( void* configuration );
	void                        shutdown();

#if defined RAPTOR_IMGUI
	void                        imgui_draw();
#endif // RAPTOR_IMGUI

	// Frame allocator
	LinearAllocator             scratch_allocator;
	HeapAllocator               system_allocator;

	//
	// Test allocators.
	void                        test();

	static constexpr cstring    k_name = "raptor_memory_service";

}; // struct MemoryService
```

## Service
`raptor/foundation/service.hpp`

```cpp
namespace raptor {

    struct Service {

        virtual void                        init( void* configuration ) { }
        virtual void                        shutdown() { }

    }; // struct Service

    #define RAPTOR_DECLARE_SERVICE(Type)        static Type* instance();

} // namespace raptor

```

## Allocator
`raptor/foundation/memory.hpp`

```cpp
struct Allocator {
	virtual ~Allocator() { }
	virtual void* allocate(sizet size, sizet alignment) = 0;
	virtual void* allocate(sizet size, sizet alignment, cstring file, i32 line)= 0;

	virtual void  deallocate( void* pointer ) = 0;
}; // struct Allocator
```

这里一些类型为了跨平台兼容性预留？ 
```cpp
typedef size_t                  sizet;
typedef const char*             cstring;
typedef int32_t                 i32;
```



## LinearAllocator
`raptor/foundation/memory.hpp`

## HeapAllocator

