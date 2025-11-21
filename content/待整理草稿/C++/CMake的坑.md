---
title: CMake错误依赖的坑
date: 2022-01-12T09:33:41+08:00
tags:
draft: true
---

不知道依赖怎么找到的
set(CMAKE_FIND_DEBUG_MODE TRUE)

自定义查找： (自己编写findxxx.cmake)
https://stackoverflow.com/questions/5529186/what-is-the-right-place-for-findxxx-cmake-files-for-locally-compiled-libs

https://stackoverflow.com/questions/20746936/what-use-is-find-package-when-you-need-to-specify-cmake-module-path

https://cmake.org/cmake/help/latest/manual/cmake-developer.7.html#find-modules

如果是module模式（cmake安装路径提供的FindXXX.cmake），通用名称
https://cmake.org/cmake/help/latest/manual/cmake-modules.7.html
linux下通常是：/usr/share/cmake-{ver}/Modules/ 反正找找总是能找到的。

不知道有那些变量
macro(print_all_variables)
    message(STATUS "print_all_variables------------------------------------------{")
    get_cmake_property(_variableNames VARIABLES)
    foreach (_variableName ${_variableNames})
        message(STATUS "${_variableName}=${${_variableName}}")
    endforeach()
    message(STATUS "print_all_variables------------------------------------------}")
endmacro()

不知道设置了哪些变量。
macro(isearch_varname keyword)
    message(STATUS "isearch_varname------------------------------------------{")
    get_cmake_property(_variableNames VARIABLES)
    foreach (_variableName ${_variableNames})
        string(TOLOWER "${_variableName}" _variableNameLower )
        string(TOLOWER "${keyword}" _keywordLower )
        string(FIND ${_variableNameLower} ${_keywordLower} _keyFound)
        if (NOT ${_keyFound} EQUAL -1)
            message(STATUS "${_variableName}=${${_variableName}}")
        endif()
    endforeach()
    message(STATUS "isearch_varname------------------------------------------}")
endmacro()

cmake坑：

target依赖可以include文件夹
https://stackoverflow.com/questions/47175683/cmake-target-link-libraries-propagation-of-include-directories

没有统一的target来import
https://stackoverflow.com/questions/45524666/in-cmake-how-can-i-find-the-imported-target-after-calling-find-package

## 关于CMAKE错误依赖的问题
如果没有关闭WITH_EIGEN的开关，很容易发生错误依赖问题。这个问题有两个原因：
1. 设定prefix会导致搜索到错误的依赖：https://cmake.org/cmake/help/latest/variable/CMAKE_INSTALL_PREFIX.html 。PREFIX会增加搜索目录，因此会自动查找到一些依赖。
2. 即使不设置PREFIX，仍然会找到Eigen，这是因为[User Package Registry](https://cmake.org/cmake/help/latest/manual/cmake-packages.7.html#user-package-registry)，CMake会搜索这里面的配置 `~/.cmake/xxx` 来快速定位软件包。（可以用 `CMAKE_FIND_USE_PACKAGE_REGISTRY` 关闭这个行为）

此外，通过在cmake文件中增加 `set(CMAKE_FIND_DEBUG_MODE TRUE)` 可以分析依赖文件的查找过程。
