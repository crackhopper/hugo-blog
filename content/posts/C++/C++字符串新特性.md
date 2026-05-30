---
id: art_612e6b3653a6498a9178a76a9c0875a7
title: C++字符串新特性
date: 2025-11-26T00:28:26+08:00
tags:
  - cpp
  - string
draft: false
---

C++11之后，字符串有很多新特性。这里主要罗列了所有特性，需要重点关注 
- 明确编码字面量
- Raw String Literals
- User-Defined Literals
- `std::string_view`
- 以及一些 便利函数 


<!--more-->

# 宽字符串 L"" (老特性)
这个是老特性了。L代表宽字符串。它的字符集取决于你使用的编译器和平台，但它的核心是对应于 `wchar_t` 类型的：
- 在 Windows 平台上使用 MSVC 编译器，`L""` 的处理方式通常如下：
	- 类型 `wchat_t` ，2字节，UTF-16 Little Endian
- 其他平台：
	- 类型 `wchat_t` ，4字节，UTF-32 (有机器本身的字节序决定是BE还是LE)

于是，**在跨平台 C++ 开发中，如果使用标准 `wchar_t` 和 `L""` 宽字符串，你确实很难获得真正的“一致性”。** 它们在不同平台上的底层实现和编码是天然不一致的。

# 明确编码字面量(C++11)
**推荐的现代 C++ 解决方案**

为了解决 `L""` 的不一致性，C++11 引入了新的明确编码字面量。这些字面量是**跨平台一致的**：

|**字面量前缀**|**对应的类型**|**编码标准**|**字节大小**|**跨平台一致性**|
|---|---|---|---|---|
|**`u8""`**|`const char*` (C++20 是 `const char8_t*`)|**UTF-8**|1-4 字节（变长）|**最高**|
|**`u""`**|`const char16_t*`|**UTF-16**|2 字节（定长或变长）|**高**|
|**`U""`**|`const char32_t*`|**UTF-32**|4 字节（定长）|**高**|

**所以，如果代码中有字符串存储非ASCII编码，更推荐使用 `u8""` 来确定编码类型。**

C++20中，新增： **`char8_t` 和 `u8""` 的类型改变** 
- 引入了独立的 **`char8_t`** 类型，并将 `u8""` 字面量的类型正式改为 `const char8_t*`，从而更好地支持 UTF-8 编码。

# Raw String Literals (C++11)
它的主要目的是解决在常规字符串字面量中处理**转义字符（Escape Characters）** 带来的麻烦，特别是在涉及文件路径、正则表达式、HTML/XML/JSON 片段等包含大量反斜杠 或引号 的场景。


语法结构：
$$\text{Prefix} \ R \ \text{Delimiter} \ ( \ \text{Content} \ ) \ \text{Delimiter}$$
- Prefix: 指定字符串编码 (L, u, U, u8)
- R: 代表Raw String。即内部内容不会被转移。
- Delimiter： 一个可选的字符串（最多 16 个字符），用于标记字符串的开始和结束，防止内容中包含 `)` 或 `"` 导致提前结束。
	- 比如 ： `R"(C:\Windows)"`  和 `R##(C:\Windows)##`  这两种是等价的。


# 字符串新函数 
## C++11
- **`std::to_string`** 用于将数字类型（如 `int`, `double`）转换为 `std::string`。
- **`std::stoi`, `std::stod`** 用于将 `std::string` 转换为各种数字类型（如 `int`, `double`, `long`）。
## C++17
- `std::to_chars` 将数字转化为字符串。无异常版本。不处理locale。
- `std::from_chars` 将字符串转化为数字。无异常版本。不处理locale。

不处理locale：不会添加千位分隔符、小数点始终是句点（`.`）
## C++20
- **`std::basic_string::starts_with` / `ends_with`** 提供了检查字符串是否以特定前缀或后缀开始/结束的便捷方法。
- **`std::string::contains`** 提供了检查字符串是否包含特定子字符串的便捷方法。

# User-Defined Literals, UDLs (C++11)

用户定义的字面量 (User-Defined Literals, UDLs)

用户定义的字面量（UDLs）允许程序员创建新的后缀，用于扩展标准字面量（如整数、浮点数、字符和字符串）的含义。简而言之，您可以使用自定义后缀将字面量直接转换为自定义类型或执行特定操作。

```cpp
// 示例：定义一个长度单位
long double operator"" _cm(long double val) {
    return val / 100.0; // 转换为米
}
```

```cpp
#include <iostream>
#include <chrono>

using namespace std::chrono;

// 1. 定义一个用于 "ms" 的 UDL，将数字转换为毫秒
constexpr milliseconds operator"" _ms(unsigned long long ms) {
    return milliseconds(ms);
}

int main() {
    // 使用 UDLs，代码更具可读性
    auto duration = 500ms + 2s; // 500毫秒 + 2秒

    // 完整的 duration 是 2500 毫秒
    std::cout << duration.count() << " 毫秒" << std::endl;
    
    return 0;
}
```

# `std::string` 字面量后缀 `s` (C++14)
它是一种特殊的 UDL，由标准库定义。它的作用是：当一个字符串字面量（C 风格字符串 `const char*`）后面紧跟后缀 **`s`** 时，编译器会将其自动转换为一个 `std::string` 对象。

```cpp
// C++14 之前：需要显式构造
std::string my_string = std::string("Hello World");
```

```cpp
#include <iostream>
#include <string>

// 必须包含此命名空间，std::string 的 UDLs 在其中
using namespace std::string_literals; 

int main() {
    // 1. 使用 's' 后缀创建 std::string 对象
    std::string s1 = "C++"s;
    std::cout << "s1 的类型是 std::string: " << s1 << std::endl;

    // 2. 字符串拼接，确保至少一个操作数是 std::string
    // "Hello" 是 const char*，不能直接和 " World!" 拼接
    // std::string s2 = "Hello" + " World!"; // 错误！
    
    // 's' 后缀确保左操作数是 std::string，从而启用 std::string 的 operator+
    std::string s2 = "Hello"s + " World!"; 
    std::cout << "s2 的内容: " << s2 << std::endl; 

    return 0;
}
```

# std::string_view (字符串视图) （C++17)
`std::string_view` 是一个**轻量级、只读**的对象，它代表对现有字符序列（无论是 `std::string`、C 风格字符串，还是其他字符数组）的引用。它只存储两个信息：
1. 一个指向字符序列起始位置的**指针**。
2. 字符序列的**长度**。

在 C++17 之前，当您将一个字符串（尤其是 `std::string`）作为参数传递给函数时，通常会导致字符串内容被**完整拷贝**：
```cpp
void process(std::string s); // 拷贝！低效！
```

使用 `std::string_view`，您可以在**不进行任何数据拷贝**的情况下查看和操作字符串数据，显著提升性能：
```cpp
#include <iostream>
#include <string>
#include <string_view>

using namespace std;

// 使用 string_view 作为函数参数，避免不必要的拷贝
void print_part(string_view sv) {
    cout << "View Content: " << sv << endl;
    cout << "View Length: " << sv.length() << endl;
}

int main() {
    std::string s = "C++ Programming Language"; 
    const char* c_str = "Legacy C String";

    // 1. 从 std::string 创建 view
    // 零拷贝：sv_s 只是引用了 s 的数据
    std::string_view sv_s = s; 
    print_part(sv_s);

    // 2. 从 C 风格字符串创建 view
    // 零拷贝：sv_c 只是引用了 c_str 的数据
    std::string_view sv_c = c_str;
    print_part(sv_c);

    // 3. 截取（子串）操作也是零拷贝
    // 截取 "Programming"
    std::string_view sv_sub = sv_s.substr(4, 11);
    print_part(sv_sub); // 仅调整了指针和长度，未创建新字符串
    
    return 0;
}
```