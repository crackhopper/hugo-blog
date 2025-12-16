# Doing
学习
- C++内存管理
	- RAII + 智能指针
		- RAII + unique_ptr / weak_ptr 管理对象生命周期
		- 上层对象持有下层对象 → unique_ptr / shared_ptr（少用 shared_ptr）
		- 下层对象引用上层对象 → weak_ptr
		- 循环引用概率极低，析构时机可控
		- 大量小对象：内存池，Allocator， Allocator_Traits
	- Garbage Collection
		- Unreal Engine UObject GC
		- Java JVM的内存管理 (Precise GC)
			- safepoint/stack map
			- STW (Stop the world)
			- mark-sweep/compact
		- 并发/增量 GC
			- write barrier
			- SATB 模型
			- final remark
		- 分代GC
		- GO语言GC选择
	- 总结：现代C++推荐的内存管理
- TLSF内存管理算法
- MGPV-内存管理分析和改进
	- 当前做法 linear allocator + TLSF;不兼容标准库
		- 可以采用的点。
		- 需要改进的点。
	- 我们的改进实现。
		- Allocator和析构函数配合。兼容标准库的allocator_traits （借助pmr::memory_resource）
		- frame内临时数据，pmr+arena allocator
			- 要么你限制 arena 只存 trivially destructible    
			- 要么你需要 **显式析构注册/遍历**
		- 全局对象： heap + tlsf
		- 粒子对象： 对象池（可以简单用tlsf，或者直接实现一个模板），因为都是统一大小的对象。
	- Dedug和可视化：
		- 预留钩子：allocator统计，frame peak usage，pool occupancy
		- 内存管理常见工具的使用：（如何解决泄露、野指针、raw指针、循环引用等问题）
			- Valgrind，AddressSantizier之类的。
	- 我的代码和库。
	    - 内存管理（模板 + RAII + pmr）
	    - Array / HashMap（模板容器 + traits + move semantics）


游戏
- 物品道具系统设计
- 掉落池设计
- 怪物配置和掉落改进（配置+UI层）
- 更优秀的地图移动聚焦。

量化
- trading服务：人工重构AI代码
- trading服务：e2e测试人工完善
- trading服务：仓位计算和同步；
- trading服务，kafka数据流读取位置处理。
- trading服务：策略开发

# Waiting

## QUANT
- [[Kalfka一些知识的总结01]]
- [[Go和GORM的补充知识01]]
- [[TypeScript链式调用与串行锁]]
- [[脚本-导入`.env`中的环境变量]]
- [[脚本-根据端口杀死进程]]
- [[Task - go项目构建工具]]

## Renderer
### MGPK
《Mastering Graphics Programming with Vulkan》

MGPV-ch01
- foundation layer实现（参考下面实现计划：2周内）
- graphics layer梳理和理解。（1周内）
- 代码分析：main.cpp
- imgui库
- glTF文件格式 和 MeshDraw
- 简要PBR入门
- RenderDoc 用法


foundation layer实现：
1. **高价值模块（必须自己实现）**
    - 内存管理（模板 + RAII + pmr）
    - Array / HashMap（模板容器 + traits + move semantics）
2. **辅助模块（复用/轻封装）**
    - 文件系统 / Serialization
    - Logging
    - Time
    - Process
    - 字符串（可直接用 std::string / string_view）


graphic layer实现：从ch02开始，慢慢来。跟着书走。

## GAME_DEV
- 房间怪物配置和roll机制。
- 新数值玩法：装备系统。
- 新数值玩法：锻造系统。
- 玩法机制优化：冷却机制。
