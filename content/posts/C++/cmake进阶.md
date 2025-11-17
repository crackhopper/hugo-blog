---
title: cmake进阶
date: 2020-02-15T20:48:22+08:00
tags:
  - cmake
  - c++
  - c
  - 技术
  - 项目管理
draft: false  
---
# cmake进阶用法
## 变量
### 基础知识
cmake使用 `${}` 进行变量的引用。例如：
```cmake
${PROJECT_NAME} #返回项目名称，由project命令定义的
```

关于变量的知识：
- 虽然cmake不区分命令的大小写，但区分变量的大小写
- 使用 `set` 命令，自定义变量
- 使用 `$ENV{NAME}` 命令，调用系统的环境变量了。
- 使用 `message` 命令可以打印内容。类似shell，双引号引用的内容内部的变量会展开。
```cmake
SET(HELLO_SRC main.c)
MESSAGE(STATUS "HOME dir: $ENV{HOME}")
```

cmake的变量作用域：
- 函数作用域
- 目录作用域
- 保存在全局Cache中
使用的时候要额外注意。

### 常用变量

| 变量名                           | 变量说明                                             |
|----------------------------------|------------------------------------------------------|
| `PROJECT_NAME`                   | 返回通过PROJECT指令定义的项目名称                    |
| `PROJECT_SOURCE_DIR`             | CMake源码地址，即cmake命令后指定的地址               |
| `PROJECT_BINARY_DIR`             | 运行cmake命令的目录                                  |
| `CMAKE_CURRENT_SOURCE_DIR`       | 当前处理的CMakeLists.txt所在的路径                   |
| `CMAKE_CURRENT_LIST_DIR`         | 当前文件夹                                           |
| `CMAKE_CURRENT_LIST_FILE`        | 当前文件                                             |
| `CMAKE_CURRENT_LIST_LINE`        | 当前行                                               |
| `CMAKE_RUNTIME_OUTPUT_DIRECTORY` | 生成可执行文件路径                                   |
| `CMAKE_LIBRARY_OUTPUT_DIRECTORY` | 生成库的文件夹路径                                   |
| `CMAKE_BUILD_TYPE`               | 指定基于make的产生器的构建类型（Release，Debug）     |
| `CMAKE_C_FLAGS`                  | .C文件编译选项，如 `-std=c99 -O3 -march=native*`     |
| `CMAKE_CXX_FLAGS`                | .CPP文件编译选项，如 `-std=c++11 -O3 -march=native*` |
| `CMAKE_CURRENT_BINARY_DIR`       | target编译目录                                       |
| `CMAKE_INCLUDE_PATH`             | 查找头文件的目录                                     |
| `CMAKE_LIBRARY_PATH`             | 查找库文件的目录                                     |
| `CMAKE_INSTALL_PREFIX`           | 配置安装路径，默认为 `/usr/local`                    |
| `CMAKE_MAJOR_VERSION`            | CMAKE 主版本号,比如 2.4.6 中的 2                     |
| `CMAKE_MINOR_VERSION`            | CMAKE 次版本号,比如 2.4.6 中的 4                     |
| `CMAKE_PATCH_VERSION`            | CMAKE 补丁等级,比如 2.4.6 中的 6                     |
| `CMAKE_SYSTEM_NAME`              | 不包含版本的系统名,比如 Linux                        |
| `CMAKE_SYSTEM_PROCESSOR`         | 处理器名称,比如 i686                                 |

## 批量查找文件
批量查找可以按照规则查找对应的文件。常用两个命令：
- `file(GLOB <variable> <pattern>)` : 这个命令按照模式查找文件，并保存在变量中
- `aux_source_directory(<dir> <variable>)` ：将文件夹下所有文件找到，并保存在变
  量中。

注意：不推荐使用这个方式管理源文件。大型项目手动逐个管理源文件会更加不容易出错误。

## 管理源文件
最佳实践：
- 使用变量保存源文件
- 增加源文件时，更新 `CMakeLists.txt` 。这样cmake知道项目需要重新初始化。

注意：不要用批量查找文件的功能管理源文件。

## 设置编译器选项
有部分变量，比如： `CMAKE_CXX_FLAGS` 不需要手动设置，可以使用命令：
```cmake
add_compile_options(-std=c++0x) # CMake 2.8.12 or newer
```
一般这个命令用来开启优化或者C++新特性。

如果要设定预处理的宏：
```cmake
add_definitions(-DFOO -DBAR ...)
```
借助这个命令可以实现不同平台的条件编译


## 自定义target
有时候，我们需要在编译前或后，调用一些命令来生成一些文件。

### 生成文件
如果想要在cmake生成的Makefile里，定义一个生成文件的规则，可以使用
`add_custom_command` 命令：

```cmake
add_custom_command(
  OUTPUT <output...>
  COMMAND <command...>
  DEPENDS <depends...>
)
```
最终生成的 `Makefile` 里的内容是：
```Makefile
OUTPUT: DEPENDS
        COMMAND
```

### 给现有的target增加hook钩子

此外，如果想要在已有的target的流程前后，增加命令 (即，增加hook钩子)，也可以使用
`add_custom_command` ：

```cmake
add_custom_command(
  TARGET <target>
  PRE_BUILD | PRE_LINK | POST_BUILD
  COMMAND <command>
  WORKING_DIRECTORY <dir>
)
```

### 增加一个没有输出的target

使用 `add_custom_target` 可以新建一个没有输出的target。只要依赖变更，它总是会触
发构建。

```cmake
add_custom_target(
  <name> ALL 
  COMMAND <commands...>
  DEPENDS <depends...>
  WORKING_DIRECTORY <dir>
  SOURCES <srcs..>
)
```

## 调试CMake

当项目很大很复杂的时候，往往cmake文件也需要调试。最常见的调试办法就是打log。在
cmake中，就是使用 `message` 命令：

```cmake
message([<mode>] "message to display" ...)
````

其中mode可以选择：
- STATUS ： 普通打印状态
- WARNING ： 打印警告，cmake继续执行，并生成构建文件
- SEND_ERROR ： 打印错误，cmake继续执行，但不生成构建文件
- FATAL_ERROR ： 打印错误，cmake停止执行。

如果你的cmake过于复杂，且有bug，通过打印log来进行调试吧！
## 集成单元测试
## 安装和打包
### 版本号

### 打包成deb

### 使用dpkg安装


# 案例：真实的项目
## 目录结构


# 其他补充(放入动态库专题)
## 动态库的加载问题 
### LD_LIBRARY
### --rpath, --rpath-link

