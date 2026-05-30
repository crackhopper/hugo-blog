---
title: buf和connectrpc入门01
date: 2025-12-02T18:47:04+08:00
tags:
  - buf
  - proto
  - connectrpc  
draft: false
---

Buf CLI 是现代、快速且高效的 Protobuf API 管理的终极工具

- 从管理项目来说，基于buf管理 proto文件，要比原始的 `protoc` 好用很多。
- 更进一步的 `connectrpc`。提供了方便各个平台（包括web），基于proto定义来进行通信的机制。
- 本文从文档出发，结合AI问答，梳理这个工具链的细节和要点。一方面是学习笔记，另一方面也方便未来查阅。

考虑到 `buf.build` 整个工具体系非常复杂。这里我们就只讲少部分buf基础内容+connectrpc的基础内容。

<!--more-->

# Buf基础
## 命令
- `generate` : 使用 `protoc` 插件从 Protobuf 文件生成代码框架
- `breaking` : 验证没有引入破坏性变更，以防止兼容性问题
- `lint` : 根据最佳实践校验你的 Protobuf 文件
- `format` : 格式化你的 Protobuf 文件以保持一致性
- `curl` : 通过调用 RPC 端点来测试你的 API，类似于使用 `curl`
- `convert` : 将消息从二进制转换为 JSON 或反之，在调试或测试时很有用
- `config` ：生成和管理 Buf 配置文件

## 配置文件
- `buf.yaml` : 定义工作区及其内部每个模块的配置。它是主要的配置文件，定义每个模块的目录、名称、 `lint` 和 `breaking` 配置，以及要排除的任何文件，还包括工作区的共享依赖项。
- `buf.gen.yaml` : 定义代码生成插件集、它们的选项以及 `buf generate` 在从您的 Protobuf 文件生成代码时使用的输入。
- `buf.lock` :  记录确切的依赖项版本，以确保跨团队和 CI 的一致性构建。

## 配置工作区
```sh
buf config init
```
运行后，目录中会出现 `buf.yaml`:
```yaml
# For details on buf.yaml configuration, visit https://buf.build/docs/configuration/v2/buf-yaml
version: v2
lint:
  use:
    - STANDARD
breaking:
  use:
    - FILE
```

`buf.yaml` 文件位于工作区根目录，它定义的工作区是所有 Buf 操作的默认输入。[[#Buf CLI 输入|_index]]

## 基础知识

### Buf Image (Buf镜像文件)
Buf images 是一种强大的工具，用于在组织内分发和共享编译好的 Protocol Buffer（Protobuf）模式。它们提供了一种紧凑且高效的 Protobuf 模式表示方式，使您能够轻松管理模式的演进，并确保跨多个系统的兼容性。

Buf images 设计为向前和向后兼容，使您能够在不破坏现有系统兼容性的情况下，随着时间的推移管理模式的演进。它们还包含丰富的元数据，例如源代码位置和注释，可用于提供有关schema的额外上下文和理解。

Linting 和 Breaking 检测操作主要使用 **Buf Image**（由CLI动态生成，或者从外部读取）。因此，镜像 Image ，代表了一种稳定、广泛使用的 protobuf schema 。（所以可以理解 image文件作为 protobuf 的schema存在）

#### Image文件原理
使用 `buf build` 命令，会将 `.proto` 文件集 编译成一个单独的 二进制文件。这个二进制文件包含了所有信息（包括proto文件和配置选项）

构建好的Buf Image文件，本身多平台兼容。可以直接分发或者放到 vcs （比如git） 中 。

如果要使用 Buf Image ，需要在系统中安装 Buf 工具，以及把 Buf Image 作为依赖整合到构建流程中。Buf 工具提供了很多基于 Buf Image 的工具，包括不限于： 验证、代码生成。

```
Buf Image = 标准 protobuf FileDescriptorSet + Buf 自己额外的字段
```

因此可以理解 Buf Image 本身是 一种 `protobuf FileDescriptorSet` 文件的扩展。关于这个文件，我在下面补充了一些描述。可以理解为 `protobuf` 的 schema ，但本身也用protobuf来存储。


	补充知识： protobuf FileDescriptorSet (简单理解为编译器中间产物，或 protobuf schema)
	
	protoc 编译器，不会直接只生成代码，它会先把 .proto 文件解析成一套标准化结构Descriptor。
	
	protoc --descriptor_set_out=out.pb --include_imports user.proto

	这个命令生成的 out.pb 就是 FileDescriptorSet 文件 。本身也是一个.pb文件(由protobuf序列化得到)。

	官方定义为：
	message FileDescriptorSet {
	  repeated FileDescriptorProto file = 1;
	}
	
	结构层级示例如下：
	FileDescriptorSet
	└── FileDescriptorProto (user.proto)
	    ├── message_type
	    │   └── DescriptorProto (User)
	    │       └── FieldDescriptorProto (id, name)
	    ├── enum_type
	    ├── service
	    ├── dependency (import 的 proto)

Buf工具利用了这个文件，并扩展了字段。（因此本身Buf Image实际上也是兼容 DescriptorSet 格式的，可以被protoc处理）


下面是Buf的Image文件格式定义：
```proto
// Image is an extended FileDescriptorSet.
message Image {
  repeated ImageFile file = 1;
}

// ImageFile is an extended FileDescriptorProto.
//
// Since FileDescriptorProto doesn't have extensions, we copy the fields from
// FileDescriptorProto, and then add our own extensions via the buf_extension
// field. This is compatible with a FileDescriptorProto.
message ImageFile {
  optional string name = 1;
  optional string package = 2;
  repeated string dependency = 3;
  repeated int32 public_dependency = 10;
  repeated int32 weak_dependency = 11;
  repeated google.protobuf.DescriptorProto message_type = 4;
  repeated google.protobuf.EnumDescriptorProto enum_type = 5;
  repeated google.protobuf.ServiceDescriptorProto service = 6;
  repeated google.protobuf.FieldDescriptorProto extension = 7;
  optional google.protobuf.FileOptions options = 8;
  optional google.protobuf.SourceCodeInfo source_code_info = 9;
  optional string syntax = 12;

  // buf_extension contains buf-specific extensions to FileDescriptorProtos.
  //
  // The prefixed name and high tag value is used to all but guarantee there
  // will never be any conflict with Google's FileDescriptorProto definition.
  // The definition of a FileDescriptorProto has not changed in years, so
  // we're not too worried about a conflict here.
  optional ImageFileExtension buf_extension = 8042;
}

message ImageFileExtension {
  // is_import denotes whether this file is considered an "import".
  optional bool is_import = 1;
  // ModuleInfo contains information about the Buf module this file belongs to.
  optional ModuleInfo module_info = 2;
  // is_syntax_unspecified denotes whether the file did not have a syntax explicitly specified.
  optional bool is_syntax_unspecified = 3;
  // unused_dependency are the indexes within the dependency field on
  // FileDescriptorProto for those dependencies that aren't used.
  repeated int32 unused_dependency = 4;
}
```

#### Plugins工作原理
考虑 
```sh
protoc -I . --go_out=gen/go foo.proto
```
这个命令的执行细节：
- `protoc` 编译文件 `foo.proto` （以及任何导入）并在内部生成一个 `FileDescriptorSet` ，这是一个包含 `FileDescriptorProto` 消息的列表。这些消息包含有关您的 `.proto` 文件的所有信息，包括可选的源代码信息，例如每个 `.proto` 文件元素的起始/结束行/列，以及相关的注释。
- `FileDescriptorSet` 转换为一个 `CodeGeneratorRequest` 对象。包含： `FileDescriptorProto` 列表（当前例子就 `foo.proto` 自己）、`go_out` 参数信息， `go_opt` 参数信息。（命令行参数，即 `=` 后面的内容）
- `protoc` 然后查找名为 `protoc-gen-go` 的二进制文件，并调用它，将序列化的 `CodeGeneratorRequest` 作为标准输入。
- `protoc-gen-go` 运行，要么出错，要么生成一个 `CodeGeneratorResponse` ，该文件指定要生成的文件及其内容。序列化的 CodeGeneratorResponse 写入 `protoc-gen-go` 的标准输出。
- 在 `protoc-gen-go` 成功后， `protoc` 读取 stdout，然后写入这些生成的文件。

内部的生成器，例如 `--java_out, --cpp_out` 工作方式大致相同。（尽管不是外部的二进制，而是在protoc内部完成的）。

**`FileDescriptorSet` 是整个 Protobuf 生态系统中用来表示编译后的 Protobuf 模板的核心基础。它们也是 `protoc` 产生的主要产物。**

你使用 `protoc` 以及任何你使用的插件，都是基于 `FileDescriptorSet` 进行交流的。gRPC Reflection 在底层也使用它们。

**所以，更进一步理解： FileDescriptorSet 可以理解为 protobuf 编译后的schema数据文件，从它可以容易的得到.proto文件中的结构和各种生成需要的信息；它也方便我们动态做一些生成**


手动生成 `FileDescriptorSet` ( **注意：由于是pb二进制文件，所以下面的 命令虽然会输出到 stdout ，但是会有很多无法显示的字符** )
```
protoc -I . --include_imports --include_source_info -o /dev/stdout foo.proto
```
- `--include_imports` : 将文件中的 `import` 也包含到生成的 `FileDescriptorSet` 中。
- `--include_source_info` :  将对应的源代码的行号信息，也包含到 `FileDescriptorSet` 中。
这些信息方便：生成文档，lint。

当然 `FileDescriptorSet` 本身也是 Buf Image（Buf做了兼容处理），因此结果可以直接送给 `Buf` 命令:
```
protoc -I . -o /dev/stdout proto/fetcher/market_data.proto   --experimental_allow_proto3_optional  --include_source_info | buf lint -
```

由于 `buf` "理解" `FileDescriptorSet` ，我们还提供 `protoc-gen-buf-lint` 和 `protoc-gen-buf-breaking` 作为标准的 Protobuf 插件。

### Buf CLI 输入
通常，你的唯一目标是处理磁盘上的 `.proto` 文件。Buf CLI 默认按此方式工作。但有时你可能需要处理本地文件以外的其他文件。

#### 术语

- **Source**： 未编译的 Protobuf 文件集合。
- **Image** ： A set of Protobuf files compiled into an [`Image`](https://buf.build/bufbuild/buf/docs/main/buf.alpha.image.v1#buf.alpha.image.v1.Image) binary using the `buf build` command. （使用 `buf build` 命令将一组 Protobuf 文件编译成的 `Image` 二进制文件。）_image_ represents everything inside a Protobuf project and can be used as the input to most commands. （镜像文件，可以认为是protobuf编译后的平台独立的schema字节码；包含了生成所需要的所有信息） [[#Buf Image (Buf镜像文件)|_index]]
- **Input** : 输入，Source 或 Image
- **Format** : 对输入类型的描述，常用类型 `dir` , `git` 。通常自动生成。
- **Buf Schema Registry (BSR)**： Buf 的 核心原语(core primitive)是模块( **module**)。Protobuf 本身没有模块的概念，只有文件。Buf Schema注册中心 (BSR) 是一个用于跨团队甚至跨组织管理 Buf 模块的注册中心。 （可以理解一些围绕一个业务的独立的proto文件集合，构成一个module）。BSR的URL可以指定为一个source，作为命令输入。比如 `buf lint buf.build/acme/petapis`

#### input类别：Source或Image
可以作为输入的两个类别。每个类别又有若干格式。

#### input的命令行位置
普通命令
```sh
buf build <input>
buf lint <input>
buf generate <input>
```

breaking命令(两个输入)
```sh
buf breaking <current-input> --against <previous-input>
```

#### input参数选项
```
path#option_key1=option_value1,option_key2=option_value2
```
- path : 可以是 `.`, `proto/` , `file.binpb` , `https://github.com/googleapis/googleapis`, `-` 等等。
- 选项：
	- `format` : 用来**强制指定输入的类型**，覆盖 Buf 自动推断的格式。
		- 默认的根据path自动推断格式，比如： 目录: `dir` ；`.git` : `git`；`.zip` : `zip`；`.tar.gz` : `tar`；`-` : `stdin` 。更多格式参考 [[#source格式|_index]]
	- `branch=<branch-name>` : 指定 Git 仓库的分支。
	- `tag=<tag-name>` : 指定 Git tag。
	- `ref=<git-ref>` : 任意 `git checkout` 支持的引用
	- `depth=<number>` : `depth` 控制 **git shallow clone** 的“深度”（等同于 `git clone --depth <N>`），也就是说只从远端拉取最近 N 层提交历史，而不是整个仓库的完整历史。这样可以显著减小下载量和速度提高，但历史会被截断。
	- `recurse_submodules=true` : 等价于 `git clone --recurse-submodules` （默认不拉取子模块）
	- `strip_components=<n>` : 解压时 **去掉前 n 层目录**
	- `subdir=<path>` : 只使用仓库或压缩包中的某个子目录
	- `filter=<filter-expression>` : 用于 **partial clone** , 减少 clone 的数据量, 高级使用场景（大型仓库）

#### source格式
所有源都包含一组可编译的 `.proto` 文件。
- **dir** :  一个本地目录。路径可以是相对的或绝对的。默认情况， `buf` 使用当前目录作为所有命令的输入。
- **mod** : Buf Schema Registry 上的一个模块。这个模块使用其包含的内容作为源。
	- `buf.build/googleapis/googleapis` 告诉我们编译 buf.build/googleapis/googleapis 中的文件。
	- `buf.build/bufbuild/protovalidate:v0.13.4` 告知在 buf.build/bufbuild/protovalidate 中编译文件，该文件位于由标签 v0.13.4 所解析的提交版本。
	- 这使用与 buf.yaml 中的依赖项相同的格式，而不是用于其他输入选项的 `option_key1=option_value1` 格式。
- **tar** : 一个压缩包。这个压缩包的路径可以是一个本地文件、一个远程 http/https 位置，或者 `-` 表示标准输入。
- **zip** : 一个 zip 归档文件。此归档文件的路径可以是本地文件、远程 http/https 位置，或 `-` 表示标准输入。
- **git** : 一个 Git 仓库。Git 仓库的路径可以是一个本地 `.git` 目录，或是一个远程 `http://` 、 `https://` 、 `ssh://` 或 `git://` 位置。
- **protofile** : 一个本地 Protobuf 文件。路径可以是相对的或绝对的，类似于 dir 输入。这是一个特殊输入，它使用文件及其导入作为 `buf` 命令的输入。如果找到本地配置文件，则首先使用指定的依赖项解析文件导入，然后使用本地文件系统。如果没有本地配置，则使用本地文件系统解析文件导入。(import解析方式，除了本地源代码，还可以是buf.yaml中配置的依赖项；依赖项是一个mod)
- **Symlinks** ： 请注意，只有 `dir` 和 `protofile` 输入支持符号链接，而 `mod` 、 `git` 、 `tar` 和 `zip` 输入会忽略所有符号链接。

#### image格式
可以使用 `buf build` 创建 buf image: 
```sh
buf build -o image.binpb
buf build -o image.binpb.gz
buf build -o image.binpb.zst
buf build -o image.json
buf build -o image.json.gz
buf build -o image.json.zst
buf build -o image.txtpb
buf build -o image.txtpb.gz
buf build -o image.txtpb.zst
buf build -o -
buf build -o -#format=json
buf build -o -#format=json,compression=gzip
buf build -o -#format=json,compression=zstd
buf build -o -#format=txtpb
```

我自己测试：(截断部分输出)
```sh
buf build -o -#format=txtpb proto/fetcher/market_data.proto

# 输出结果
file: {
  name: "proto/fetcher/market_data.proto"
  package: "fetcher"
  message_type: {
    name: "Kline"
    field: {
      name: "symbol"
      number: 1
      label: LABEL_OPTIONAL
      type: TYPE_STRING
      json_name: "symbol"
    }
    field: {
      name: "type"
      number: 2
      label: LABEL_OPTIONAL
      type: TYPE_ENUM
      type_name: ".fetcher.KlineType"
      json_name: "type"
    }
...
    location: {
      path: 4
      path: 4
      path: 2
      path: 2
      path: 3
      span: 56
      span: 24
      span: 25
    }
  }
  syntax: "proto3"
  buf_extension: {
    is_import: false
    module_info: {
      name: {
        remote: "hushine-tech.com"
        owner: "quant"
        repository: "proto"
      }
    }
    is_syntax_unspecified: false
  }
}
```


Image输入格式：
- **binpb** ： Buf Image的二进制格式。[[#Buf Image (Buf镜像文件)|_index]]
- **json** : 一个 JSON 格式的 Buf Image 。 解析速度较慢，但生成的差异比较结果会以可读的格式显示两个 Buf Image之间的实际差异。
- **txtpb** : 文本格式的 Buf Image。在现代 Protobuf 使用中，JSON 更受欢迎，但许多 Protobuf 的遗留使用仍然使用文本格式。

#### 身份认证-HTTPS
`buf` 首先在 `$NETRC` 查找 netrc 文件，默认为 `~/.netrc` 。

还可以使用环境变量
- `BUF_INPUT_HTTPS_USERNAME` 是用户名。对于 GitHub，这是您的 GitHub 用户。
- `BUF_INPUT_HTTPS_PASSWORD` 是密码。对于 GitHub，这是您的 GitHub 用户的个人访问令牌。

#### 身份认证-SSH
Git 仓库通过 `git` 命令克隆，因此 `buf` 默认使用您现有的 Git SSH 配置，包括添加到 `ssh-agent` 的任何身份。

还可以使用环境变量
- `BUF_INPUT_SSH_KEY_FILE` 是私钥文件路径。
- `BUF_INPUT_SSH_KNOWN_HOSTS_FILES` 是以冒号分隔的已知主机文件路径列表。

## 基础配置文件说明
### `buf.yaml` 路径和模块
`buf.yaml` 文件默认为一个包含一个模块的工作区，模块路径设置为当前目录。

要显式定义工作区中的模块，提供包含 `.proto` 文件的目录路径。使用 `modules` 键将 `proto` 目录添加到 `buf.yaml` 文件
```yaml
version: v2
+modules:
+  - path: proto
lint:
  use:
    - STANDARD
breaking:
  use:
    - FILE
```

继续之前，请验证一切是否设置正确且模块可以构建。如果没有错误，您就知道已经正确设置了 Buf 模块：
```sh
buf build
echo $?
# 0
```

#### `import`写法注意
考虑我的项目组织代码为:
```
.
├── proto
│   ├── fetcher
│   │   └── market_data.proto
│   └── trading
│       ├── account.proto
│       └── order.proto
└── buf.yaml
```
其中 ，`buf.yaml` 如下：

```yaml
version: v2
modules:
  - path: proto    
lint:
  use:
    - STANDARD
breaking:
  use:
    - FILE
```

假设我们在 `account.proto` 中要导入 `order.proto` 文件，怎么做？

**导入要从 `buf.yaml` 定义的模块根路径为起点进行导入** ，即我们应该 `import "trading/order.proto";`

### `buf.gen.yaml` 生成代码
文件作用： 控制 `buf generate` 命令如何在给定模块上执行 `protoc` 插件。可以用它来配置每个 `protoc` 插件写入结果的位置，并为每个插件指定选项。

```yaml
version: v2
managed:
  enabled: true
  override:
    - file_option: go_package_prefix
      value: github.com/bufbuild/buf-examples/gen
plugins:
  - remote: buf.build/protocolbuffers/go
    out: gen
    opt: paths=source_relative
  - remote: buf.build/connectrpc/gosimple
    out: gen
    opt:
      - paths=source_relative
      - simple
inputs:
  - directory: proto
```

#### managed (托管模式)
`managed` 模式是 **Buf 的托管选项**，主要解决 Protobuf 文件中的 **file options** 配置混乱问题。
启用后，Buf 会根据语言和插件自动生成合适的 file options，不需要手动在 `.proto` 文件中写。

```yaml
managed:
  enabled: true
  override:
    - file_option: go_package_prefix
      value: github.com/bufbuild/buf-examples/gen
```

- 表示 **生成的 Go 文件的 package 前缀**全部统一设置为 `github.com/bufbuild/buf-examples/gen`。

总结：
- **托管模式 = 自动管理 file options**
- **override = 对托管行为进行定制**

这个确实好，之前都是手动在每个proto文件中写一些option。

#### `plugins`（插件配置）
```yaml
plugins:
  - remote: buf.build/protocolbuffers/go
    out: gen
    opt: paths=source_relative
  - remote: buf.build/connectrpc/gosimple
    out: gen
    opt:
      - paths=source_relative
      - simple
```
- **remote** : 指向 **远程插件**，存储在 **Buf Schema Registry**。(使用 remote plugin 的好处：不需要在本地下载和维护 protoc 插件; 保证版本可控、统一)
	- `buf.build/protocolbuffers/go` → 官方 Go plugin
	- `buf.build/connectrpc/gosimple` → Connect-Go plugin
- **out** ： 输出目录，插件生成的代码会放在 `gen` 目录中，Buf CLI 会在目录不存在时自动创建
- **opt** ：插件参数。`paths=source_relative`：相对路径生成，对于每个proto文件，计算其与input根目录（例子中是 `proto` 这个目录）的相对路径。随后在当前 buf.gen.yaml 所在路径创建 `gen` 文件夹，按照相对路径创建生成的文件。

#### inputs (输入源)
```sh
inputs:
  - directory: proto
```
- `inputs` 指定 **Buf 处理的 Protobuf 源文件位置**

因此，这个 `buf.gen.yaml` 不需要和 `buf.yaml` 配合就可以直接生成。

如果不指定 `inputs` 。那么 `buf.gen.yaml` 就需要指定输入源（默认是当前目录，也可以手动指定；如果指定的目录有 `buf.yaml` 文件，那么使用这个文件规定的 `mod` 作为输入源）。（针对目录的输入源会遍历，找到所有的proto文件作为输入源）。


### `buf.yaml` v.s. `buf.gen.yaml`

|特性|`buf.yaml`|`buf.gen.yaml`|
|---|---|---|
|**主要用途**|管理 Protobuf 模块、lint、breaking 等规则|管理代码生成（generate）插件、输出目录、file options|
|**核心作用**|模块定义、代码质量控制|插件执行、生成代码|
|**是否必须**|是 Buf module 的核心文件|可独立存在（不依赖 buf.yaml），也可配合 buf.yaml 使用|
|**命令关联**|`buf build`、`buf lint`、`buf breaking`|`buf generate`|
|**输入源（proto 文件）**|模块 root 目录或指定目录|可以通过 `inputs` 指定目录/Git/tar，也可以不指定（默认用 buf.yaml 模块）|
|**默认输入源**|模块根目录（buf.yaml 所在目录）|当前目录（buf.gen.yaml 所在目录）；若存在 buf.yaml，则使用模块作为默认 input|
|**递归查找 proto 文件**|会递归查找模块目录下所有 proto 文件|如果没有指定 inputs，则递归 buf.yaml 模块目录下的 proto；如果指定 inputs，则按输入目录递归|
|**插件配置**|不配置插件|配置远程或本地插件、输出目录、插件参数（如 paths=source_relative）|
|**托管模式（managed）**|N/A|可启用 managed 模式，自动设置 file options 并可 override|
|**依赖关系**|无法单独生成代码，需要配合 buf.gen.yaml|可以单独生成代码，也可以依赖 buf.yaml 的模块信息|
|**输出目录**|N/A|插件生成代码的目录（`out`）|

因此，关于生成的动作，主要看 `buf.gen.yaml` 的配置，以及参考： [[#Buf CLI 输入|_index]] 这里面关于输入的默认定义。

## 生成stubs (buf.gen.yaml) 
使用当前目录中的 `buf.gen.yaml` 可以执行生成命令（注意，严格来说不需要 `buf.yaml` ，这个文件仅仅是将proto文件组织成了模块，是项目描述文件。生成的时候，会引用 `buf.yaml` ，也可以直接手动指定或者按照规则指定inputs）

```sh
buf generate
```
目录结构如下：
```
.
├── gen
│   ├── google
│   │   └── type
│   │       └── datetime.pb.go
│   └── pet
│       └── v1
│           ├── pet.pb.go
│           └── petv1connect
│               └── pet.connect.go
├── proto
├   ├── google
├   │   └── type
├   │       └── datetime.proto
├   └── pet
├       └── v1
├           └── pet.proto
├── buf.gen.yaml
└── buf.yaml
```

## Lint检查 (buf.yaml) 
按照最佳实践给出代码中的建议：
```sh
buf lint

# proto/google/type/datetime.proto:17:1:Package name "google.type" should be suffixed with a correctly formed version, such as "google.type.v1".
# proto/pet/v1/pet.proto:56:10:Field name "petID" should be lower_snake_case, such as "pet_id".
# proto/pet/v1/pet.proto:61:9:Service name "PetStore" should be suffixed with "Service".
```

不过我现在项目已经组织好，被多个模块依赖了，所以lint错误我也只能先忽略了。QAQ 

忽略lint的配置
```yaml
version: v2
modules:
  - path: proto
lint:
  use:
    - STANDARD
+  ignore:
+    - proto/google/type/datetime.proto
breaking:
  use:
    - FILE
```

## Breaking检查  (buf.yaml) 
```sh
buf breaking --against HEAD
```
作用：
1. 检查 **buf.yaml 中列出的所有模块**。
2. 对比 **当前版本 vs 过去版本** 的 Protobuf schema。
3. 根据 **选定的 breaking rules** 检测潜在破坏性更改。

规则类型：默认规则是 **FILE**，推荐使用它以保证 **最大兼容性**。

|规则类型|检测内容|说明|
|---|---|---|
|**FILE**|文件级别|检测 **生成代码移动到不同文件** 的情况。适合确保生成的代码结构不破坏现有客户端/服务端引用。|
|**PACKAGE**|包级别|检测 **包级别的破坏性更改**。主要针对生成的 stubs（客户端/服务端代理代码），不关注单个文件变化。|
|**WIRE_JSON**|JSON/Wire 编码|检测 **JSON 或二进制编码的不兼容更改**。JSON 广泛使用，因此推荐至少启用此规则。|
|**WIRE**|二进制 Wire 编码|检测 **二进制编码不兼容**，是最低层面的破坏性检测。|

- 举例子 **FILE 级别检查**： proto文件移动了位置。那么生成代码的目录结构也有变化，就会触发 breaking警报。
# ConnectRPC基础 (基于Go)
## 介绍
Connect 框架旨在提供一种灵活且兼容的机制，用于连接服务器和客户端。它支持三种核心协议：**gRPC**、**gRPC-Web** 和 **Connect 自己的协议**。

1. Connect **完全支持** gRPC 协议，包括流式传输（streaming）、尾部元数据（trailers）和错误详情（error details）。
	- **互操作性：** 任何语言的 gRPC 客户端都可以调用 Connect 服务器，反之，Connect 客户端也可以调用任何 gRPC 服务器。
	- **兼容性验证：** Connect 通过 Google 自己的互操作性测试的**扩展版本**来验证其 gRPC 兼容性。
2. gRPC-Web 协议支持
	- **无需代理：** 它无需依赖像 Envoy 这样的翻译代理即可工作。
3. Connect 自己的协议
	- **跨 HTTP 版本：** 可以在 HTTP/1.1、HTTP/2 和 HTTP/3 上运行。
	- **优势整合：** 它汲取了 gRPC 和 gRPC-Web 的优点，包括流式传输，非常适合用于浏览器、单体应用（monoliths）和微服务（microservices）。
	- **编码支持：** 默认支持 **JSON** 和二进制编码的 **Protobuf** 两种格式。

curl示例
```sh
curl \
    --header "Content-Type: application/json" \
    --data '{"sentence": "I feel happy."}' \
    https://demo.connectrpc.com/connectrpc.eliza.v1.ElizaService/Say
```

- 服务器默认： Connect 服务器默认支持所有三种协议的入站请求（ingress）。
- 客户端默认： 客户端默认使用 Connect 协议，但可以通过配置切换到 gRPC 或 gRPC-Web，无需进一步的代码修改。

## 快速开始
### 工具包安装
这些会安装到全局：
```sh
go install github.com/bufbuild/buf/cmd/buf@latest
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install connectrpc.com/connect/cmd/protoc-gen-connect-go@latest
```
### 快速示例
#### 1. 定义一个服务
文件 `greet/v1/greet.proto`
```proto
syntax = "proto3";

package greet.v1;

import "buf/validate/validate.proto";

message GreetRequest {
  string name = 1 [(buf.validate.field).string = {
    min_len: 1,
    max_len: 50,
  }];
}

message GreetResponse {
  string greeting = 1;
}

service GreetService {
  rpc Greet(GreetRequest) returns (GreetResponse) {}
}
```

#### 2. 配置buf工具生成代码
`buf.yaml` （定义proto项目）
```yaml
version: v2
deps:
  - buf.build/bufbuild/protovalidate
lint:
  use:
    - STANDARD
breaking:
  use:
    - FILE
```

`buf.gen.yaml` （定义生成动作）
```yaml
version: v2
plugins:
  - local: protoc-gen-go
    out: gen
    opt: paths=source_relative
  - local: protoc-gen-connect-go
    out: gen
    opt:
      - paths=source_relative
      - simple
managed:
  enabled: true
  override:
    - file_option: go_package_prefix
      value: example/gen
  disable:
    - file_option: go_package
      module: buf.build/bufbuild/protovalidate
```

执行指令，检查proto，生成：
```sh
buf dep update
buf lint
buf generate
```

生成后的目录结构：
```
gen
└── greet
    └── v1
        ├── greet.pb.go
        └── greetv1connect
            └── greet.connect.go
```

#### 3. 实现Handler
```go
package main

import (
  "context"
  "fmt"
  "net/http"

  greetv1 "example/gen/greet/v1"        // generated by protoc-gen-go
  "example/gen/greet/v1/greetv1connect" // generated by protoc-gen-connect-go

  "connectrpc.com/connect"
  "connectrpc.com/validate"
)

type GreetServer struct{}

func (s *GreetServer) Greet(
  _ context.Context,
  req *greetv1.GreetRequest,
) (*greetv1.GreetResponse, error) {
  res := &greetv1.GreetResponse{
    Greeting: fmt.Sprintf("Hello, %s!", req.Name),
  }
  return res, nil
}

func main() {
  greeter := &GreetServer{}
  mux := http.NewServeMux()
  path, handler := greetv1connect.NewGreetServiceHandler(
    greeter,
    // Validation via Protovalidate is almost always recommended
    connect.WithInterceptors(validate.NewInterceptor()),
  )
  mux.Handle(path, handler)
  p := new(http.Protocols)
  p.SetHTTP1(true)
  // Use h2c so we can serve HTTP/2 without TLS.
  p.SetUnencryptedHTTP2(true)
  s := http.Server{
    Addr:      "localhost:8080",
    Handler:   mux,
    Protocols: p,
  }
  s.ListenAndServe()
}
```

#### 4. 启动运行
```sh
go get connectrpc.com/connect
go get connectrpc.com/validate
go get buf.build/go/protovalidate
go run ./cmd/server/main.go
```

#### 5. curl测试
```sh
curl \
    --header "Content-Type: application/json" \
    --data '{"name": "Jane"}' \
    http://localhost:8080/greet.v1.GreetService/Greet
```

响应内容为：
```json
{"greeting": "Hello, Jane!"}
```

当然也支持grpc调用，可以用buf工具模拟grpc调用：
```sh
buf curl \
  --schema ./greet/v1/greet.proto \
  --protocol grpc \
  --http2-prior-knowledge \
  --data '{"name": "Jane"}' \
  http://localhost:8080/greet.v1.GreetService/Greet
```

也可以模拟connect协议调用
```sh
buf curl \
  --schema . \
  --data '{"name": "Jane"}' \
  http://localhost:8080/greet.v1.GreetService/Greet
```

#### 6. Client代码测试
```go
package main

import (
  "context"
  "log"
  "net/http"

  greetv1 "example/gen/greet/v1"
  "example/gen/greet/v1/greetv1connect"
)

func main() {
  client := greetv1connect.NewGreetServiceClient(
    http.DefaultClient,
    "http://localhost:8080",
  )
  res, err := client.Greet(
    context.Background(),
    &greetv1.GreetRequest{Name: "Jane"},
  )
  if err != nil {
    log.Println(err)
    return
  }
  log.Println(res.Greeting)
}
```

运行代码:
```sh
go run ./cmd/client/main.go
```

### 仅使用 gRPC

**默认支持所有协议：** 默认情况下，**Connect-Go 服务器**支持来自所有三种协议（Connect、gRPC 和 gRPC-Web）的**入站请求 (ingress)**，**无需任何额外配置**。

使用下面的代码，可以关闭connect协议，仅用gGPC协议通信
```go
client := greetv1connect.NewGreetServiceClient(
  http.DefaultClient,
  "http://localhost:8080",
  connect.WithGRPC(),
)
```


## Routing(路由)
默认connect会支持下面的路由访问:
```
:method post
:path /<Package>.<Service>/<Method>
```

如果想要把路由地址修改，增加前缀，可以用下面的做法。（不过这种做法， `grpc-go` 是不能支持的， 如果要支持 gRPC 最好不要把connect的handler进行prefix）
```go
api := http.NewServeMux()
api.Handle(greetv1connect.NewGreetServiceHandler(&greetServer{}))

mux := http.NewServeMux()
mux.Handle("/", newHTMLHandler())
mux.Handle("/api/", http.StripPrefix("/api", api))
http.ListenAndServe(":http", mux)
```

解释：
1. `NewServerMux` : 创建一个 **总路由器** (`ServeMux`)，Mux(Multilexer) ，可以理解聚合了一系列url路由的handler。
2. `ServeMux` 可以嵌套使用。因此，上面代码里，顶层 `mux` 下面有两个Handle注册，其中一个，api（也是一个 `ServeMux` 对象）
3. `http.StripPrefix` ：包装 `Handler` 的类似middleware的组件，负责把请求中URL的前缀去除掉。

## Error(错误处理)
在 Connect 中，一个错误（`error`）不仅仅是普通的 Go 错误，它还附带了一个 **错误码（error code）**。
- **错误码**类似于 gRPC 的 status code（例如 `InvalidArgument`, `DeadlineExceeded`, `Canceled`, `Unknown` 等），用于让客户端知道这个错误的类型，从而决定如何处理，比如重试、回退或直接报错。
- **底层错误消息**仍然是标准 Go `error` 的 `Error()` 字符串，这个消息会被传给客户端。
    
所以 Connect 的错误是 **带代码的 Go 错误**，发送给客户端后，客户端可以根据错误码做不同的处理逻辑。

```go
connect.NewError(connect.CodeInvalidArgument, err)
```
- 第一个参数是错误码，例如 `CodeInvalidArgument`。
- 第二个参数是原始错误 `err`。
- 返回值仍然是 `error` 类型，但它已经包含了错误码


如果你的 handler 没有返回带错误码的错误，Connect 会帮你自动处理一些特殊错误：

|原始错误|Connect 错误码|
|---|---|
|`context.DeadlineExceeded`|`deadline_exceeded`|
|`context.Canceled`|`canceled`|
|其他错误|`unknown`|

示例代码:
```go
func (s *GreetServer) Greet(
  ctx context.Context,
  req *greetv1.GreetRequest,
) (*greetv1.GreetResponse, error) {
  if err := ctx.Err(); err != nil {
    return nil, err // automatically coded correctly
  }
  if err := validateGreetRequest(req); err != nil {
    return nil, connect.NewError(connect.CodeInvalidArgument, err)
  }
  greeting, err := doGreetWork(ctx, req)
  if err != nil {
    return nil, connect.NewError(connect.CodeUnknown, err)
  }
  return &greetv1.GreetResponse{
    Greeting: greeting,
  }, nil
}
```
- 第一行 `if err := ctx.Err(); err != nil` 处的逻辑： 如果 `ctx` 被取消或超时，`ctx.Err()` 会返回 `context.Canceled` 或 `context.DeadlineExceeded`。
- 后面的都比较直观，容易理解。

对客户端来说，会得到标准的 go 错误。解析错误用 CodeOf 函数
```go
connect.CodeOf(err)
```

获取更多信息的做法(如果是 connect 的错误类型)：
```go
if connectErr := new(connect.Error); errors.As(err, &connectErr) {
    fmt.Println(connectErr.Message())
    fmt.Println(connectErr.Details())
}
```

从http请求得到的错误信息，大概格式为：
```json
{
  "code": "invalid_argument",
  "message": "data cannot be empty"
}
```

### 利用 ErrorDetail 传递详细错误信息
server代码
```go
package example

import (
  "errors"

  "connectrpc.com/connect"
  "google.golang.org/genproto/googleapis/rpc/errdetails"
  "google.golang.org/protobuf/types/known/durationpb"
)

func newTransientError() error {
  err := connect.NewError(
    connect.CodeUnavailable,
    errors.New("overloaded: back off and retry"),
  )
  retryInfo := &errdetails.RetryInfo{
    RetryDelay: durationpb.New(10*time.Second),
  }
  if detail, detailErr := connect.NewErrorDetail(retryInfo); detailErr == nil {
    err.AddDetail(detail)
  }
  return err
}
```
- 行 `retryInfo := &errdetails.RetryInfo{`  : `RetryInfo` 是 gRPC 标准错误详情之一，用于告诉客户端：**多久之后可以重试请求**。
- 根据gRPC规范，error可以添加errorDetails的列表，来详细描述error。上面就是增加了一个detail。


client提取这个信息
```go
package example

import (
  "errors"

  "connectrpc.com/connect"
  "google.golang.org/genproto/googleapis/rpc/errdetails"
  "google.golang.org/protobuf/types/known/durationpb"
)

func extractRetryInfo(err error) (*errdetails.RetryInfo, bool) {
  var connectErr *connect.Error
  if !errors.As(err, &connectErr) {
    return nil, false
  }
  for _, detail := range connectErr.Details() {
    msg, valueErr := detail.Value()
    if valueErr != nil {
      // Usually, errors here mean that we don't have the schema for this
      // Protobuf message.
      continue
    }
    if retryInfo, ok := msg.(*errdetails.RetryInfo); ok {
      return retryInfo, true
    }
  }
  return nil, false
}
```
这里需要注意的：
- `msg.(T)` 这个用法是因为 `msg` 是一个interface。使用的是接口断言的语法。断言，接口内的数据类型为 `T` 

## Header和Trailer
```
HTTP/1.1 200 OK
Transfer-Encoding: chunked
Trailer: X-Checksum

...response body...
0
X-Checksum: 123456
```

- 普通的 header 在请求/响应 **开始**就发送。
- trailer 在消息体 **结束后**发送。

这个能力，connect库也提供了设置的能力。这里略不细表。

## Interceptors (拦截器)
这个类似其他框架的middleware或者decorator。主要用来扩展connect框架的。

对于 unaray RPC来说，函数接口为：
```go
type UnaryFunc func(context.Context, AnyRequest) (AnyResponse, error)
```

对应的interceptor接口为：
```go
type UnaryInterceptorFunc func(UnaryFunc) UnaryFunc
```

例子：
```go
package example

import (
  "context"
  "errors"

  "connectrpc.com/connect"
)

const tokenHeader = "Acme-Token"

func NewAuthInterceptor() connect.UnaryInterceptorFunc {
  return func(next connect.UnaryFunc) connect.UnaryFunc {
    return func(
      ctx context.Context,
      req connect.AnyRequest,
    ) (connect.AnyResponse, error) {
      if req.Spec().IsClient {
        // Send a token with client requests.
        req.Header().Set(tokenHeader, "sample")
      } else if req.Header().Get(tokenHeader) == "" {
        // Check token in handlers.
        return nil, connect.NewError(
          connect.CodeUnauthenticated,
          errors.New("no token provided"),
        )
      }
      return next(ctx, req)
    }
  }
}
```

## Observability(可观测性)
OpenTelemetry（简称 **OTel**）本质上是一个 **可观测性（Observability）工具集**，它帮你 **了解应用在运行时发生了什么**。

在现代微服务或分布式系统里，应用通常分散在很多服务、容器和服务器上。如果系统出问题，你需要知道：
- 哪个服务慢了？
- 哪个服务报错了？
- 请求是怎么在服务之间流动的？

传统日志只能告诉你一些信息，但不够系统化，也不容易关联多个服务的请求。  
这时候就需要 **可观测性工具**，比如 OpenTelemetry。

**OpenTelemetry 的核心概念**
1. **Tracer / Span（追踪）**
    - 一个请求会产生一个 **Trace**，由多个 **Span** 组成
    - 每个 Span 表示请求的一个步骤，例如：
        - 网关收到请求 → 创建 span
        - 调用后端服务 → 创建 span
    - 这样就能可视化请求的完整路径和耗时
2. **Meter / Metric（指标）**
    - 用于收集数值数据，例如：
        - 每秒请求数（QPS）
        - 请求失败数
        - CPU 或内存使用率
3. **Propagator（传播器）**
    - 让 trace 可以跨服务传递
    - 当请求从服务 A 到服务 B，Propagator 会把 trace 信息附带过去，保证 span 能关联起来

OpenTelemetry 就是给你的应用装上“感知能力”，它能告诉你每个请求怎么走、耗时多少、是否出错，并生成统计数据。

可以以 Interceptor (拦截器)的方式启动otel
```go
import "connectrpc.com/otelconnect"

otelInterceptor, err := otelconnect.NewInterceptor()
if err != nil {
	log.Fatal(err)
}

path, handler := greetv1connect.NewGreetServiceHandler(
	greeter,
	connect.WithInterceptors(otelInterceptor),
)

client := greetv1connect.NewGreetServiceClient(
	http.DefaultClient,
	"http://localhost:8080",
	connect.WithInterceptors(otelInterceptor),
)
```



OpenTelemetry 本身不存数据，它只负责收集和发送。发送目标由 Exporter 配置 决定，例如：
```go
tp := sdktrace.NewTracerProvider(
    sdktrace.WithBatcher(jaegerExporter),
)
otel.SetTracerProvider(tp)
```

如果要自定义 export的配置，可以用下面办法自定义拦截器
```go
// newInterceptor instruments Connect clients and handlers using custom OpenTelemetry metrics, tracing, and propagation.
func newInterceptor(tp trace.TracerProvider, mp metric.MeterProvider, p propagation.TextMapPropagator) (connect.Interceptor, error) {
	return otelconnect.NewInterceptor(
		otelconnect.WithTracerProvider(tp),
		otelconnect.WithMeterProvider(mp),
		otelconnect.WithPropagator(p),
	)
}
```
## Streaming (流处理)
### proto定义
```proto
syntax = "proto3";

package greet.v1;

import "buf/validate/validate.proto";

message GreetRequest {
  string name = 1 [(buf.validate.field).string = {
    min_len: 1,
    max_len: 50,
  }];
}

message GreetResponse {
  string greeting = 1;
}

service GreetService {
  rpc Greet(stream GreetRequest) returns (GreetResponse) {}
}
```
- 当然参数和返回值都可以是流。这样就可以双向通信。（注意： **支持 Connect 的双向流就能替代 WebSocket**，实现前端和后端的实时双向通信）

针对上面的定义，
### server端代码
```go
package main

import (
  "context"
  "errors"
  "fmt"
  "log"
  "net/http"
  "strings"

  "connectrpc.com/connect"
  "connectrpc.com/validate"

  greetv1 "example/gen/greet/v1"
  "example/gen/greet/v1/greetv1connect"
)

type GreetServer struct{}

func (s *GreetServer) Greet(
  ctx context.Context,
  stream *connect.ClientStream[greetv1.GreetRequest],
) (*greetv1.GreetResponse, error) {
  callInfo, ok := connect.CallInfoForHandlerContext(ctx)
  if !ok {
    return nil, errors.New("can't access headers: no CallInfo for handler context")
  }
  log.Println("Request headers: ", callInfo.RequestHeader())
  var greeting strings.Builder
  for stream.Receive() {
    g := fmt.Sprintf("Hello, %s!\n", stream.Msg().Name)
    if _, err := greeting.WriteString(g); err != nil {
      return nil, connect.NewError(connect.CodeInternal, err)
    }
  }
  if err := stream.Err(); err != nil {
    return nil, connect.NewError(connect.CodeUnknown, err)
  }
  callInfo.ResponseHeader().Set("Greet-Version", "v1")
  res := &greetv1.GreetResponse{
    Greeting: greeting.String(),
  }
  return res, nil
}

func main() {
  greeter := &GreetServer{}
  mux := http.NewServeMux()
  path, handler := greetv1connect.NewGreetServiceHandler(
    greeter,
    // Validation via Protovalidate is almost always recommended
    connect.WithInterceptors(validate.NewInterceptor()),
  )
  mux.Handle(path, handler)
  p := new(http.Protocols)
  p.SetHTTP1(true)
  // Use h2c so we can serve HTTP/2 without TLS.
  p.SetUnencryptedHTTP2(true)
  s := http.Server{
    Addr:      "localhost:8080",
    Handler:   mux,
    Protocols: p,
  }
  s.ListenAndServe()
}
```
- 服务端接收流，拼接字符串。
### Interceptor(验证拦截器)
统一处理 ConnectRPC 的认证逻辑，在客户端自动添加 token，在服务端校验 token，覆盖 Unary 和流式 RPC。

```go
const tokenHeader = "Acme-Token"

var errNoToken = errors.New("no token provided")

type authInterceptor struct{}

func NewAuthInterceptor() *authInterceptor {
  return &authInterceptor{}
}

func (i *authInterceptor) WrapUnary(next connect.UnaryFunc) connect.UnaryFunc {
  // Same as previous UnaryInterceptorFunc.
  return func(
    ctx context.Context,
    req connect.AnyRequest,
  ) (connect.AnyResponse, error) {
    if req.Spec().IsClient {
      // Send a token with client requests.
      req.Header().Set(tokenHeader, "sample")
    } else if req.Header().Get(tokenHeader) == "" {
      // Check token in handlers.
      return nil, connect.NewError(connect.CodeUnauthenticated, errNoToken)
    }
    return next(ctx, req)
  }
}

func (*authInterceptor) WrapStreamingClient(next connect.StreamingClientFunc) connect.StreamingClientFunc {
  return func(
    ctx context.Context,
    spec connect.Spec,
  ) connect.StreamingClientConn {
    conn := next(ctx, spec)
    conn.RequestHeader().Set(tokenHeader, "sample")
    return conn
  }
}

func (i *authInterceptor) WrapStreamingHandler(next connect.StreamingHandlerFunc) connect.StreamingHandlerFunc {
  return func(
    ctx context.Context,
    conn connect.StreamingHandlerConn,
  ) error {
    if conn.RequestHeader().Get(tokenHeader) == "" {
      return connect.NewError(connect.CodeUnauthenticated, errNoToken)
    }
    return next(ctx, conn)
  }
}
```
- **常量与错误**
    - `tokenHeader = "Acme-Token"`：自定义 HTTP 头名称，用于传递 token
    - `errNoToken`：服务端在请求缺少 token 时返回的错误
        
- **Unary RPC 拦截器 (`WrapUnary`)**
    - 客户端请求时：自动在请求头加 `Acme-Token: sample`
    - 服务端处理时：如果请求头缺少 token，则返回 `Unauthenticated` 错误
        
- **客户端流式拦截器 (`WrapStreamingClient`)**
    - 客户端发起流式 RPC 时，自动在流请求头加 token
        
- **服务端流式拦截器 (`WrapStreamingHandler`)**
    - 服务端接收流式 RPC 时，校验请求头是否有 token
    - 缺失 token 则拒绝连接并返回 `Unauthenticated`

### client端代码

```go
package main

import (
	"context"
	"fmt"
	"log"

	"connectrpc.com/connect"

	greetv1 "example/gen/greet/v1"
	"example/gen/greet/v1/greetv1connect"
)

// 假设 authInterceptor 已经实现
// tokenHeader := "Acme-Token"
// func NewAuthInterceptor() *authInterceptor { ... }

func main() {
	// 创建拦截器
	auth := NewAuthInterceptor()

	// 创建 GreetService 客户端
	client := greetv1connect.NewGreetServiceClient(
		"http://localhost:8080",
		connect.WithInterceptors(auth), // 包含 Unary 和流式拦截器
	)

	ctx := context.Background()

	// 打开客户端流
	stream, err := client.Greet(ctx)
	if err != nil {
		log.Fatalf("failed to create client stream: %v", err)
	}

	// 要发送的名字列表
	names := []string{"Alice", "Bob", "Charlie"}

	// 循环发送消息
	for _, name := range names {
		req := &greetv1.GreetRequest{Name: name}
		if err := stream.Send(req); err != nil {
			log.Fatalf("failed to send request: %v", err)
		}
		fmt.Printf("Sent: %s\n", name)
	}

	// 关闭客户端流并接收服务端响应
	resp, err := stream.CloseAndReceive()
	if err != nil {
		log.Fatalf("failed to receive response: %v", err)
	}

	fmt.Println("Server Response:")
	fmt.Println(resp.Msg.Greeting)
}

```

- 客户端通过：先调用rpc，然后得到一个stream。随后可以写入。
	- 所以，服务端如果返回流，也是先返回，然后得到一个流。

## 超时和连接池
- **连接池**
    - RPC 客户端通常会频繁请求少数服务器。
    - 可以增加 `Transport.MaxIdleConnsPerHost` 来复用连接，提高效率。
        
- **禁止重定向**
    - RPC 很少用 HTTP 重定向，客户端可以通过 `CheckRedirect` 禁止自动跟随。
        
- **压缩**
    - Connect 自动设置 `Accept-Encoding`，所以 `Transport.DisableCompression` 对 RPC 无效。
        
- **超时**
    - **流式 RPC**：超时适用于整个消息交换。
    - 服务器需在 unary（单次请求）和 streaming（流式请求）之间平衡超时设置。
    - Go 的 `net/http` 用 `SetDeadline` 实现超时，没有“空闲超时”，所以如果客户端打开流但不发送数据，可能会占用服务器资源。
    - 对公网 API，建议：
        - 超时不要设置过长
        - 尽量避免流式 RPC
            
- **http.Server 超时字段**
    - `ReadTimeout` 和 `WriteTimeout` 会作用于整个操作，包括 streaming RPC。
## h2c
也叫做 HTTP/2 without TLS 。有时候需要用这个版本的协议
```go
package main

import (
  "net/http"
)

func main() {
  mux := http.NewServeMux()
  // Mount some handlers here.
  p := new(http.Protocols)
  p.SetHTTP1(true)
  p.SetUnencryptedHTTP2(true)
  server := &http.Server{
    Addr:      ":http",
    Handler:   mux,
    Protocols: p,
    // Don't forget timeouts!
  }
}
```

## CORS
```go
import (
	"net/http"

	connectcors "connectrpc.com/cors"
	"github.com/rs/cors"
)

// withCORS adds CORS support to a Connect HTTP handler.
func withCORS(h http.Handler) http.Handler {
	middleware := cors.New(cors.Options{
		AllowedOrigins: []string{"example.com"},
		AllowedMethods: connectcors.AllowedMethods(),
		AllowedHeaders: connectcors.AllowedHeaders(),
		ExposedHeaders: connectcors.ExposedHeaders(),
	})
	return middleware.Handler(h)
}
```
