---
id: art_9c13948c43bf015d3dab72cee4acacf3
title: Python之包管理
date: 2022-01-17T10:00:00+08:00
tags:
draft: true
---

# 环境管理

https://stackoverflow.com/questions/41573587/what-is-the-difference-between-venv-pyvenv-pyenv-virtualenv-virtualenvwrappe

## Python多版本
多个python版本：推荐使用pyenv，这个是第三方工具，用来管理多个python版本的。
```bash
sudo apt-get update; sudo apt-get install make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-devapt 

curl https://pyenv.run | bash
```

其他平台安装参见： https://github.com/pyenv/pyenv

安装好后，就可以配置python版本了。也可以参见：https://realpython.com/intro-to-pyenv/


## 虚拟环境和包管理
保证包管理工具是最新的
```bash
python -m pip install --upgrade pip setuptools wheel
```
虚拟环境：不涉及到python版本，在单一版本下，维护多个环境。主要是隔离安装包，防止引入错误依赖。

```bash
python3 -m venv tutorial_env
source tutorial_env/bin/activate
```

# 安装包
## sdist v.s.Wheels
sdist指的是源代码包，Wheel则是构建过的二进制包，安装更加快速。如果pip没找到Wheel包，那么它仍然会在本地构建一个Wheel包，方便后续其他项目使用。

## 安装指令
- 从 `requirements.txt` 文件： `pip install -r requirements.txt`
- 从VCS安装 `pip install -e git+https://git.repo/some_pkg.git#egg=SomeProject`
- 指定Index `pip install --index-url http://my.package.repo/simple/ SomeProject`
- 额外搜索Index `pip install --extra-index-url http://my.package.repo/simple SomeProject`
- 从源码安装
  - 可编辑安装（用link安装） ： `pip install -e <path>`
  - 普通安装 : `pip install <path>`
- 从archive文档安装
  - `pip install ./downloads/SomeProject-1.0.4.tar.gz`
  - `pip install --no-index --find-links=/local/dir/ SomeProject`
- 从其他源安装：应该参照PEP503做个代理，转化为pip支持的格式，比如 `s3helper`
- 安装预发布版本 `pip install --pre SomeProject`
- 安装setuptools "Extras" : `pip install SomePackage[PDF]`

# 管理依赖：pipenv
## 安装 pipenv
pipenv是类似npm一样的包管理工具。推荐使用这个来进行依赖管理
```bash
pip install pipenv
```
## 安装项目依赖
比如给 myproject 添加 requests 的依赖
```bash
cd myproject
pipenv install requests
```
这个命令会新建个虚拟环境(virtualenv)，在其中安装 `Request` 库 并且创建 `Pipfile` 文件， 这个文件有点类似 `npm` 的 `package.json` 会保存项目依赖的库。

启动程序需要使用pipenv命令 `pipenv run python main.py`

通过 `pipenv --venv` 可以显示项目的venv。

那么pipenv是如何知道项目所在的venv的呢？参见 [link](https://github.com/pypa/pipenv/issues/796) ，规则是：使用项目的路径名做hash作为后缀，因此 `<project-name>-<hash>` 就是虚拟环境的名字。显然这个方式还是有很多弊端的，并且pipenv已经停止维护很久了。

# 打包Python项目
## 示例项目结构
我们通过一个示例项目来讲解如何构建打包

```
packaging_tutorial/
└── src/
    └── example_package/
        ├── __init__.py
        └── example.py
```

在 `exmaple.py` 中，添加如下代码：
```python
def add_one(number):
    return number + 1
```

接下来，我们将这个项目打包，最终的项目结构如下：
```
packaging_tutorial/
├── LICENSE
├── pyproject.toml
├── README.md
├── setup.cfg
├── setup.py
├── src/
│   └── example_package/
│       ├── __init__.py
│       └── example.py
└── tests/
```
- `tests` 文件夹用来放测试文件的
- `pyproject.toml` 这个文件告诉构建工具（`pip` 和 `build`）一些信息来构建项目。我们用 `setuptools` 构建，因此这个文件的内容如下：

    ```ini
    [build-system]
    requires = [
        "setuptools>=42",
        "wheel"
    ]
    build-backend = "setuptools.build_meta"
    ```
    - `build-system.requires` 给出一些构建需要的依赖包，这些依赖只会影响构建过程，不影响安装。
    - `build-system.build-backend` 则是给出了用来构建的Python对象的名字。切换不同的工具需要修改这个位置。

- matadata配置文件
  - `setup.cfg` : 静态的metadata。保证每次都是一样的。
    ```ini
    [metadata]
    name = example-package-YOUR-USERNAME-HERE
    version = 0.0.1
    author = Example Author
    author_email = author@example.com
    description = A small example package
    long_description = file: README.md
    long_description_content_type = text/markdown
    url = https://github.com/pypa/sampleproject
    project_urls =
        Bug Tracker = https://github.com/pypa/sampleproject/issues
    classifiers =
        Programming Language :: Python :: 3
        License :: OSI Approved :: MIT License
        Operating System :: OS Independent

    [options]
    package_dir =
        = src
    packages = find:
    python_requires = >=3.6

    [options.packages.find]
    where = src
    ```
    - 这个配置文件是是 `setuptools` 使用的。（pyproject.toml其实是告诉Python语言构建系统工具链的，而具体的 setup.cfg 和 setup.py，则是由制定的工具链解析使用）
    - `setuptools` 配置文件的解读参见： https://setuptools.readthedocs.io/en/latest/userguide/declarative_config.html
    - options分类下的选项是控制 `setuptools` 自身的
      - `package_dir` 是映射包名称和对应文件夹的map。空的package name表示的是“root package”，因此上面的配置描述了 “root package” 是src所在的文件夹。
      - `packages` 是发布包中需要包含的引入包(import packages)。我们可以手动列出所有的引入包，我们也可以使用 `find:` 指令去自动发现列在 `options.packages.find` 中的路径下的包和子包。上面的配置下， `expample_package` 讲会是唯一被找到的包
      - `python_requires` 指定了需要的python版本。

  - `setup.py` : 动态的metadata。很多属性是安装的时候动态获取的。（optional）
    
    同上，但是是用脚本作为配置。等价的配置为
    ```python
    import setuptools

    with open("README.md", "r", encoding="utf-8") as fh:
        long_description = fh.read()

    setuptools.setup(
        name="example-package-YOUR-USERNAME-HERE",
        version="0.0.1",
        author="Example Author",
        author_email="author@example.com",
        description="A small example package",
        long_description=long_description,
        long_description_content_type="text/markdown",
        url="https://github.com/pypa/sampleproject",
        project_urls={
            "Bug Tracker": "https://github.com/pypa/sampleproject/issues",
        },
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        package_dir={"": "src"},
        packages=setuptools.find_packages(where="src"),
        python_requires=">=3.6",
    )    
    ```
    - 注意：有时候能看到从 `distutils.core` 中到处 `setup` 函数。这个是遗留问题，不建议这么使用
- `README.md` 这个文件会用来作为 long_description 。如果不提供会自动创建。
## sdist中包含其他文件
上面的文件爱你都会自动包含到sdist中。如果你想显式控制需要包含的文件，参见 [link](https://packaging.python.org/en/latest/guides/using-manifest-in/)

构建的包将包含发现的Python文件或列出的Python包。如果想要控制这里的行为，可以参见 setuptools 文档 [Including Data Files](https://setuptools.pypa.io/en/latest/userguide/datafiles.html)

## 生成发布归档(distribution archives)
只需要执行 `python -m build` 命令即可。最终会产出如下文件：
```
dist/
  example-package-YOUR-USERNAME-HERE-0.0.1-py3-none-any.whl
  example-package-YOUR-USERNAME-HERE-0.0.1.tar.gz
```

## 上传发布归档(distribution archives)
首先在 TestPyPI 上注册帐号，这个是专门用来测试和试验的环境。

为了安全的上传项目，需要PyPI的API token。可以通过网站创建一个。

上传前首先需要安装twine: `pip install --upgrade twine`

然后运行twine来上传dist目录： `python -m twine upload --repository testpypi dist/*`

随后提示username和password，这里使用之前获取到的API token。

# 创建文档
可以用sphinx。具体参加 [link](https://packaging.python.org/en/latest/tutorials/creating-documentation/)

# 打包进阶
本节我们讨论的是使用 `setuptools` 进行打包的一些细节，原版文档参见： https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/ 。示例项目参见： https://github.com/pypa/sampleproject

## `setup()` 参数
- name : 项目名字
- version ： 当前版本
- description 简要介绍； long_description 长描述，一般是文件； long_descrition_content_type 描述文件的格式
- url : 项目的主页
- author : 作者
- licence : 协议类型
- classifiers : 项目分类，参加 https://pypi.org/classifiers/ 进行选择
- keywords : 关键字
- project_urls ： 项目一些额外的url。比如汇报bug的url
- packages ： 设定项目包含的所有包，包括子包。可以借助 `setuptools.find_packages` 来查找
- py_modules ： 对于单文件非包的模块，进行引入。
- install_requires ： 指定项目依赖，当用pip安装的时候，会自动安装依赖
- python_requires ： 指定项目依赖的python版本
- package_data ： 指定额外的需要安装的文件，一般是实现所需要的数据文件
- data_files ： 一般来说 `package_data` 够用了。这个选项用来安装包外的数据文件，每个条目是 `(dir,[files])` 这样的形式。 `dir` 必须是相对路径，会想对于 `sys.prefix` 进行安装。（注意，使用egg安装的是时候，这个选项不支持）
- scripts : 更加推荐 `console_scripts` 选项
- console_scripts ： 会让工具链创建对应的脚本工具。比如下面这块会创建一个脚本工具，命名为sample，功能为启动sample.main函数的调用。语法是 `<name> = [<package>.[<subpackage>.]]<module>[:<object>.<object>]`
  ```python
  entry_points={
    'console_scripts': [
        'sample=sample:main',
    ],
  },
  ```

- entry_points : 一部分项目定义entry_points，另一部分则请求(solicit) entry_points，从而达成类似插件的能力。这个能力的另一个名字叫 Advertising Behavior （广告行为）。具体参加这个链接 [link](https://stackoverflow.com/questions/774824/explain-python-entry-points/9615473#9615473) ,实际上 setuptools 会在安装包的时候，解析entry_points并把他们写到特定的文件中（一般是每个包的.dist-info或.egg-info文件夹中的entry_points.txt [link](https://stackoverflow.com/questions/60135673/how-are-entrypoints-of-the-python-standard-library-registered)，通过pkg_resources包的API可以查找entry_point，通过importlib.metadata可以加载它）(可以理解entry_point为注册到共有空间的对象，供其他包访问)
  - 一个例子是pytest项目，允许其他库使用名为`pytest11`的entry_points来扩展pytest的能力。pytest会读取这个名字的entry_points，并对自己的能力进行扩充
  - 另一个例子是 `console_script` ，这个pip会利用这个entry_point的信息，创建对应的wrapperi脚本。
  
    考虑如下的配置
    ```ini
    [options.entry_points]
    my.plugins =
        hello-world = timmins:hello_world [pretty-printer]
    ```
    - 其中 `[pretty-printer]` 表示这个依赖必须安装。
    则另个想要使用这个entry_point的项目则可以
    ```python
    from importlib import metadata
    eps = metadata.entry_points()['my.plugins']
    for ep in eps:
        plugin = ep.load()
        plugin()    
    ```
## 版本控制策略
每个项目可以自定义，但必须符合public version scheme (PEP440)来保证被pip和setuptools支持。

推荐的版本控制是 MAJOR.MINOR.MAINTENANCE：（类似npm推荐的semver）
- MAJOR version 表示API不兼容的升级。
- MINOR version 表示功能升级但兼容性API升级
- MAINTENANCE version 表示bug修复

此外，一些后缀也是常使用的。但pip会忽略后缀。

本地version方法是用 `+` 号，比如 `1.2.0.dev1+hg.5.b11e5e6f0b0b` ，这表示这个版本并不是准备发布的版本。

## 开发者模式
用 `pip install -e xxx` 来安装，这样只会把链接安装到仓库

## 打包
- sdist : 使用build工具即可。 `pip install build` , `python -m build --sdist` 。这种发布包不是构建发布(not Built Distribution)
- Wheels : 是一个构建好的包，可以直接安装。安装速度更快。
  - Pure Python Wheels : `python -m build --wheel`
  - Platform Wheels : `python -m build --wheel` wheel内部会detect代码不是纯粹的python，因此会构建平台相关的wheel包。
  
## 单一文件定义version
参见： https://packaging.python.org/en/latest/guides/single-sourcing-package-version/

## 二进制扩展包
参加： https://packaging.python.org/en/latest/guides/packaging-binary-extensions/

## 命名空间包(namespace package)
namespace package的作用是：可以让包更加的loosely-related。相关的包可以拆分分别发布。比如有两个包：
```
path1
+--namespace
   +--module1.py
   +--module2.py
path2
+--namespace
   +--module3.py
   +--module4.py
```
此时在namespace package的支持下，可以进行如下代码：
```python
from namespace import module1, module3
```

python3.3隐式支持了namespace package(PEP420)。native namespace package就是在命名空间文件夹下忽略了 `__init__.py` ，例如：
```
setup.py
mynamespace/
    # No __init__.py here.
    subpackage_a/
        # Sub-packages have __init__.py.
        __init__.py
        module.py
```

忽略 `__init__.py` 或者使用pkgutil-style的 `__init__.py` 至关重要。

由于mynamespace没有 `__init__.py` ，因此 `setuptools.find_packages()` 无法找到子包，因此必须使用 `setuptools.find_namespace_packages(include=['mynamespaces.*'])`

## 创建和发现插件
主要有三个方法来自动的发现插件：
- 使用命名规范 (naming convention)
- 使用命名空间包 (namespace packages)
- 使用包的metadata (package metadata)
### 命名规范 (naming convention)
使用 `pkgutil.iter_modules()` 来发现包，然后自己判断并做关联。比如flask就用这种方式进行扩展。

### 命名空间包 (namespace packages)
```python
import importlib
import pkgutil

import myapp.plugins

def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

discovered_plugins = {
    name: importlib.import_module(name)
    for finder, name, ispkg
    in iter_namespace(myapp.plugins)
}
```
### 包的metadata (package metadata)
通过entry_point来访问
```python
import sys
if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points
discovered_plugins = entry_points(group='myapp.plugins')
```

## setuptools的依赖管理

### 声明必要依赖
```ini
[options]
#...
install_requires =
    docutils
    BazSpam ==1.1
```
或
```python
setup(
    ...,
    install_requires=[
        'docutils',
        'BazSpam ==1.1',
    ],
)
```
对于平台相关的
```ini
[options]
#...
install_requires =
    enum34;python_version<'3.4'
    pywin32 >= 1.0;platform_system=='Windows'
```
或
```python
setup(
    ...,
    install_requires=[
        "enum34;python_version<'3.4'",
        "pywin32 >= 1.0;platform_system=='Windows'",        
    ],
)
```
对于非PyPI的依赖，添加 `dependency_links` 信息。具体参见：[link](https://setuptools.pypa.io/en/latest/userguide/dependency_management.html#dependencies-that-aren-t-in-pypi)

### 可选依赖
```ini
[metadata]
name = Package-A

[options.extras_require]
PDF = ReportLab>=1.2; RXP
```
- PDF可选支持，依赖另外两个包才能生效
- PDF可以被其他地方引用

```ini
[metadata]
name = Project A
#...

[options]
#...
entry_points=
    [console_scripts]
    rst2pdf = project_a.tools.pdfgen [PDF]
    rst2html = project_a.tools.htmlgen
```

另一个用发是，可以用这个extra来构建自己的dependency
```ini
[metadata]
name = Project-B
#...

[options]
#...
install_requires =
    Project-A[PDF]
```

## setuptools的cfg格式
参见： https://setuptools.pypa.io/en/latest/userguide/declarative_config.html

简要介绍一点，列表一般如下表示(下面两个是等价的)
```ini
[metadata]
keywords = one, two

[metadata]
keywords =
    one
    two
```
一些key是特殊的指令，比如 `file:` , `attr:` , `find:`, `find_namespace:` 。未知的key被忽略掉了。

dict被表示为：
```ini
[metadata]
keywords =
    one = <content>
    two = <content>
```
值的解析规则：
- str : 简单的字符串
- list-comma ： 悬空列表(纵向的列表) 或 逗号分隔的值
- list-semi ： 悬空列表(纵向的列表) 或 分号分隔的值
- bool : True是1
- dict : list-comma，里面的值是 `key=value`

# 附录
## 术语介绍
- PyPA：Python Packaging Authority，是一个维护打包工具的工作组。
- PyPI：Python Package Index，是python包的官方仓库，通过pip命令来进行交互。
- Egg ： setuptools引入的发布包格式，正在被Wheel取代中。
- Wheel：有PEP427引入的发布包(Built Distribution)格式。Wheel格式目前被pip支持。
- Extension Module ： 扩展模块。用low-level语言实现的python扩展，比如c/c++，java。一般是动态库。
- Known Good Set (KGS) ： 互相兼容的发布集合
- Import Package ： 包含其他模块的python模块
- Module： 模块。python进行复用的基础单元，有两种类型：纯模块(Pure Module) 和 扩展模块 (Extension Module)
- Project： 这里指将会被打包的项目。大部分项目要么使用PEP518 build-system, distutils， 要么使用 setuptools （通常包含pyproject.toml, setup.py, setup.cfg文件）
- pyproject.toml ： 方便工具解析的文件，定义项目的specification。
- PEP: Python Enhancement Proposal standards。Python改进建议，一般是语言标准的迭代单位。

## 标准库(Standard Library)项目
- ensurepip : 构建Python distribution的时候会用到，主要是bootstrapping一个pip工具。
- distutils : 原始的Python包系统，在Python2.0添加的。功能不完善，不推荐使用。推荐用setup_tools
- venv ： Python3.3之后，用来创建虚拟环境的库。是virtualenv的子集。

## PyPA 项目
- bandersnatch ： 用来创建PyPI镜像的工具。
- build ： 兼容PEP517的包构建工具。提供CLI和Python API。
- cibuildwheel ： 用来构建 ‘常见平台的wheels、常见CI系统的python版本’ 的package。
- distlib ： 提供low-level的函数，帮助打包和发布。提供一些fallback的能力，兼容非标准包。
- flit : 提供打包上传PyPI的简单方法。使用pyproject.toml来配置项目。不依赖setuptools来构建，以及不以来twine来上传。
- packaging ： pip和setuptools使用的核心工具库(Core utilities)。这个核心工具库处理python包的 version handling, specifiers, markers, requirements, tags 以及相似的属性和任务。大部分python用户依赖这个库却不需要显式的调用它。这个项目主要是实现定义在PyPA specifications中的有关现代python包交互能力(packaging interoperability)
- pip ： 最流行的python包管理工具
- Pipfile ： Pipfile和他的姐妹Pipfile.lock提供一个针对requirements.txt文件的更高层级的替代品。（听起来有点像npm的package.json）
- Pipenv ： 融合了Pipfile，pip和virtualenv到一个工具链。帮助用户管理环境、依赖、以及从命令行导入包。但是从2018年之后就不怎么维护了。
- pipx ： 用来安装python命令行工具的工具
- readme_renderer ： 用来渲染发布包readme的工具，以便在PyPI上正确显示
- setuptools ： 包含了easy_install，是对Python的distutils进行改进的工具集合。更好的管理了依赖。
- trove-classifiers： 用来更好的给项目进行标签分类的工具
- twine ： 开发者用来上传包到PyPI或者其他仓库的主要工具。
- virtualenv ： 提供管理虚拟环境的功能。venv是这个包的子集。
- Warehouse ： PyPI的代码库
- wheel ： 主要提供了setuptools的扩展——bdist_wheel，方便创建wheel发布包。同样也提供一些工具来创建和安装工具包。

## 非PyPA 项目
- buildout : 基于Python的构建系统，允许对非python的部分进行集成。
- conda ： Anaconda公司提供的。同pip, virtualenv和wheel完全分离的工具，但提供了他们所有的包管理能力。conda不会从PyPI安装包，而是从Anaconda的服务器安装。同样，conda-skeleton则是先从PyPI获取包，然后修改metadata信息。
- devpi： 提供一个兼容PyPI的server，同时有更多功能。
- enscons ： 基于SCons的python包管理工具。
- Hashdist ： 简单理解，就是一个virtualenv和buildout的混合体，但从2016年就缺乏维护了。
- hatch ： 一个聚合工具，底层仍然用pip和twine。
- multibuild ： CI脚本，用来构建和测试Python在各个操作系统下的wheels
- pdm ： 支持PEP582提议的包管理器，更加类似npm。
- pex ： 提供库和工具，形成pex文件。这个文件会打包所有依赖到zip中，让安装跟cp一样简单。
- pip-tools ： 方便更新包以及更新包依赖的工具。
- piwheels：从PyPI获取包并编译成binary，方便Raspberry Pi上使用。同时提供了额外的index来下载包。
- peotry ： 命令行工具，优化pip解决依赖安装和隔离问题，利用pyproject.toml。
- pypiserver ： 最小化的PyPI服务器
- PyScafffold ： 脚手架工具，利用PyPI上的包快速创建项目脚手架。以来setuptools, pytest和Sphinx的一些配置。
- scikit-build ： 改进的构建系统，主要针对CPython的C/C++/Fortran/Cython扩展的。如果想要并行构建大项目，推荐使用ninja(也是python的构建系统；p.s. 叫这个名字以及ninjia的npm库也有很多，注意区分)
- shiv : 有点像pex，支持PEP441标准。
- Spack ： 不在PyPI中，但从github中可以快速复制使用。非常灵活的包管理系统支持multiple versions, configurations, platforms, compilers。主要用来构建在集群上的高性能科学应用。
- zest.releaser : 在twine上面的抽象层。用来bumping version, updating changelog, tagging release等等。

## 参考资料
- https://packaging.python.org/en/latest/key_projects/
- https://stackoverflow.com/questions/6344076/differences-between-distribute-distutils-setuptools-and-distutils2




https://stackoverflow.com/questions/25337706/setuptools-vs-distutils-why-is-distutils-still-a-thing

setuptools

https://setuptools.pypa.io/en/latest/userguide/declarative_config.html

https://docs.python.org/3/distutils/configfile.html