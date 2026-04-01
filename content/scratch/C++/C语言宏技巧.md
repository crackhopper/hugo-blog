---
title: C语言宏技巧
date: 2022-01-15T21:26:04+08:00
tags:
draft: true
---

http://ybin.cc/c/c-nested-macro/


https://zhuanlan.zhihu.com/p/344240420

## 变长参数

## 宏的展开规则

## 变长长度内容的展开
```
#define UAV_JSON_EXPAND( x ) x
#define UAV_JSON_GET_MACRO(_1, _2, _3, _4, _5, NAME,...) NAME
#define UAV_JSON_PASTE(...) UAV_JSON_EXPAND(UAV_JSON_GET_MACRO(__VA_ARGS__, \
        UAV_JSON_PASTE5, \
        UAV_JSON_PASTE4, \
        UAV_JSON_PASTE3, \
        UAV_JSON_PASTE2, \
        UAV_JSON_PASTE1)(__VA_ARGS__))

#define UAV_JSON_PASTE2(func, v1) func(v1)
#define UAV_JSON_PASTE3(func, v1, v2) UAV_JSON_PASTE2(func, v1) UAV_JSON_PASTE2(func, v2)
#define UAV_JSON_PASTE4(func, v1, v2, v3) UAV_JSON_PASTE2(func, v1) UAV_JSON_PASTE3(func, v2, v3)
#define UAV_JSON_PASTE5(func, v1, v2, v3, v4) UAV_JSON_PASTE2(func, v1) UAV_JSON_PASTE4(func, v2, v3, v4)

#define UAV_JSON_TO(v1) uav_json_j[#v1] = uav_json_t.v1;
#define UAV_JSON_FROM(v1) uav_json_j.at(#v1).get_to(uav_json_t.v1);


// see NLOHMANN_DEFINE_TYPE_INTRUSIVE
#define UAV_DEFINE_TYPE_INTRUSIVE(Type, ...)  \
    friend void to_json(uav::json& uav_json_j, const Type& uav_json_t) { UAV_JSON_EXPAND(UAV_JSON_PASTE(UAV_JSON_TO, __VA_ARGS__)) } \
    friend void from_json(const uav::json& uav_json_j, Type& uav_json_t) { UAV_JSON_EXPAND(UAV_JSON_PASTE(UAV_JSON_FROM, __VA_ARGS__)) }

// see NLOHMANN_DEFINE_TYPE_INTRUSIVE
#define UAV_DEFINE_TYPE_NON_INTRUSIVE(Type, ...)  \
    inline void to_json(uav::json& uav_json_j, const Type& uav_json_t) { UAV_JSON_EXPAND(UAV_JSON_PASTE(UAV_JSON_TO, __VA_ARGS__)) } \
    inline void from_json(const uav::json& uav_json_j, Type& uav_json_t) { UAV_JSON_EXPAND(UAV_JSON_PASTE(UAV_JSON_FROM, __VA_ARGS__)) }

// 下面简单引入一个例子：
// 比如：
// UAV_DEFINE_TYPE_NON_INTRUSIVE(Point, x, y, z)
// ->展开到->
//  inline void to_json(uav::json& uav_json_j, const Point& uav_json_t) { UAV_JSON_EXPAND(UAV_JSON_PASTE(UAV_JSON_TO, __VA_ARGS__)) } \
//  inline void from_json(const uav::json& uav_json_j, Point& uav_json_t) { UAV_JSON_EXPAND(UAV_JSON_PASTE(UAV_JSON_FROM, __VA_ARGS__)) }
// 主要需要理解的是：UAV_JSON_EXPAND(UAV_JSON_PASTE(UAV_JSON_TO, __VA_ARGS__))
// ->1.展开到-> UAV_JSON_EXPAND(UAV_JSON_PASTE(UAV_JSON_TO, x, y, z))
// ->2.展开到-> UAV_JSON_EXPAND(UAV_JSON_GET_MACRO(UAV_JSON_TO, x, y, z, UAV_JSON_PASTE16, ....., UAV_JSON_PASTE1)(UAV_JSON_TO, x, y, z))
// ->3.展开到-> UAV_JSON_EXPAND(UAV_JSON_PASTE4(UAV_JSON_TO, x, y, z))
// ->4.展开到-> UAV_JSON_EXPAND(UAV_JSON_PASTE2(UAV_JSON_TO, x) UAV_JSON_PASTE3(UAV_JSON_TO, y, z))
// ->5.展开到-> UAV_JSON_EXPAND(UAV_JSON_TO(x) UAV_JSON_PASTE2(UAV_JSON_TO, y) UAV_JSON_PASTE2(UAV_JSON_TO, z))
// ->6.展开到-> UAV_JSON_EXPAND(uav_json_j["x"] = uav_json_t.x; \
//    UAV_JSON_TO(y) UAV_JSON_TO(z))
// ->7.展开到-> UAV_JSON_EXPAND(uav_json_j["x"] = uav_json_t.x; uav_json_j["y"] = uav_json_t.y; uav_json_j["z"] = uav_json_t.z;)
// ->最终->uav_json_j["x"] = uav_json_t.x; uav_json_j["y"] = uav_json_t.y; uav_json_j["z"] = uav_json_t.z;

// 最外层UAV_JSON_EXPAND是为了防止在UAV_JSON_TO的调用上仍然有宏没展开
// 具体参见：http://ybin.cc/c/c-nested-macro/
```
