---
id: art_de3c9b98ec9e1ec650d90ccabe8c6815
title: Vulkan入门06-Loading models
date: 2025-12-08T19:33:46+08:00
tags:
  - vulkan
  - 3d
  - obj
  - tinyobjloader
draft: false
---

![[Vulkan入门06_Loading_models-intro-01.png|695x522]]

本节基于简单的 `tinyobjloader` 库来加载OBJ文件。整体比较简单，只是把之前手写的顶点数据替换为动态从文件中读取。

此外，为了去除顶点的重复性，使用了 hashmap (unorder_set) ，并自定义hash函数来解决问题。

<!--more-->

# tinyobjloader集成
因为这是一个header only的库，直接下载 `tiny_obj_loader.h` ( https://github.com/tinyobjloader/tinyobjloader/blob/release/tiny_obj_loader.h
)，是存入到 includes 目录下的 tinyobjloader 下即可。

此外，我们还需要模型数据。因为本章节不考虑光照，所以我们最好是找一个预先烘焙了光照纹理的模型。 https://sketchfab.com/ 这个网站上有很多免费可用的模型。我们本节的渲染采用了下面的两个模型：

- obj模型文件: https://vulkan-tutorial.com/resources/viking_room.obj
- 对应纹理贴图： https://vulkan-tutorial.com/resources/viking_room.png

下载好之后，分别存入 models 和 textures 文件夹中。最后整体的目录结构为：
![[Vulkan入门06_Loading_models-tinyobjloader集成-01.png]]

接着我们写代码使用库来加载这些数据
```cpp
#define TINYOBJLOADER_IMPLEMENTATION
#include <tinyobjloader/tiny_obj_loader.h>

...
const std::string MODEL_PATH = "models/viking_room.obj";
const std::string TEXTURE_PATH = "textures/viking_room.png";

...
// 纹理贴图换成模型的纹理。
void createTextureImage() {
    int texWidth, texHeight, texChannels;
    // 加载图像像素为一个指针
    // stbi_uc *pixels = stbi_load("textures/texture.jpg", &texWidth, &texHeight,
    //                            &texChannels, STBI_rgb_alpha);
    stbi_uc* pixels = stbi_load(TEXTURE_PATH.c_str(), &texWidth, &texHeight, &texChannels, STBI_rgb_alpha);
    VkDeviceSize imageSize = texWidth * texHeight * 4;
    ...
}

...
// 顶点数据动态加载
std::vector<Vertex> vertices;
std::vector<uint32_t> indices; // 注意更改到了 uint32_t
VkBuffer vertexBuffer;
VkDeviceMemory vertexBufferMemory;
// 对应在更改 indexbuffer的数据类型
void recordCommandBuffer(VkCommandBuffer commandBuffer, uint32_t imageIndex) {
	...
    vkCmdBindIndexBuffer(commandBuffer, indexBuffer, 0, VK_INDEX_TYPE_UINT32);
    ...	
}

void initVulkan() {
    ...
    loadModel();
    createVertexBuffer();
    createIndexBuffer();
    ...
}

...
// 加载模型的函数 
void loadModel() {
    tinyobj::attrib_t attrib;
    std::vector<tinyobj::shape_t> shapes;
    std::vector<tinyobj::material_t> materials;
    std::string warn;
    std::string err;

    if (!tinyobj::LoadObj(&attrib, &shapes, &materials, &warn, &err,
                          MODEL_PATH.c_str())) {
      throw std::runtime_error(err);
    }

    // OBJ 文件，包含： 位置(positions)、法项(normals)、纹理坐标(texture coords) 
    // 保存在 `attrib.vertices` , `attrib.normals` 和 `attrib.texcoords` (整体的数据)
    // 
    // `shapes` 包含了所有对象以及它们的面(face)的索引信息。
    // 每个面包含了一组顶点，每个顶点包含了对应的 position, normal 和 texture coords 信息。 OBJ文件还可以对每个face定义对应的material 和 texture。我们暂时i忽略这些。
    
    // 我们接下来要把所有的face拼接到一个顶点数据中。
	for (const auto& shape : shapes) {
	    for (const auto& index : shape.mesh.indices) {
	        Vertex vertex{};
	        // 由于 attrib.vertices 中是展开保存的数据，所以我们要用 3*idx+i 的方式取数值
			vertex.pos = {
			    attrib.vertices[3 * index.vertex_index + 0],
			    attrib.vertices[3 * index.vertex_index + 1],
			    attrib.vertices[3 * index.vertex_index + 2]
			};
			// 纹理坐标类似
			vertex.texCoord = {
			    attrib.texcoords[2 * index.texcoord_index + 0],
			    attrib.texcoords[2 * index.texcoord_index + 1]
			};
			vertex.color = {1.0f, 1.0f, 1.0f};
			
			// 暂时我们不考虑去除重复的顶点数据。
	        vertices.push_back(vertex);
	        
	        // 这里也直接新增索引值。
	        indices.push_back(indices.size());
	    }
	}
}
```

![[Vulkan入门06_Loading_models-tinyobjloader集成-02.png]]

这个里面 OBJ 文件中纹理坐标的定义和vulkan中不一致，尤其是y坐标。因此我们需要flip y坐标，修复为：
```cpp
vertex.texCoord = {
    attrib.texcoords[2 * index.texcoord_index + 0],
    1.0f - attrib.texcoords[2 * index.texcoord_index + 1]
};
```
![[Vulkan入门06_Loading_models-intro-01.png|695x522]]

当模型旋转起来的时候，背面会比较有意思（因为模型并没考虑到从那个方向观看）
![[Vulkan入门06_Loading_models-tinyobjloader集成-03.png]]

# 顶点重复问题 (vertex duduplication)
我们每次用到索引的时候，都是新建一个顶点，新建一个索引。这样并没有利用到索引的优势（可以复用顶点数据）。因此我们调整 `loadModel` 代码：

```cpp
#include <unordered_map>

// 为了计算 glm 数据结构的hash，需要引入
#define GLM_ENABLE_EXPERIMENTAL
#include <glm/gtx/hash.hpp>

...

void loadModel(){
	...
	// 这里面我们用一个 unorder_map (hashmap) ，以顶点作为key，来确保顶点数据唯一性。
	std::unordered_map<Vertex, uint32_t> uniqueVertices{};
	for (const auto& shape : shapes) {
	    for (const auto& index : shape.mesh.indices) {
	        Vertex vertex{};
	
	        ...
	
	        if (uniqueVertices.count(vertex) == 0) {
	            uniqueVertices[vertex] = static_cast<uint32_t>(vertices.size());
	            vertices.push_back(vertex);
	        }
	
	        indices.push_back(uniqueVertices[vertex]);
	    }
	}
}
// 为了支持 unorder_map 的key需要的trait，我们需要重载opcerator== 
struct Vertex {
	...
	bool operator==(const Vertex &other) const {
	    return pos == other.pos && color == other.color &&
	           texCoord == other.texCoord;
	}
}
// 为了支持 unorder_map 的key需要的trait，我们还需要特化 std::hash<T> ，提供计算hash的方法
// 下面的计算方法是参照 https://en.cppreference.com/w/cpp/utility/hash.html 提供的一个快速便携计算hash的方法
namespace std {
    template<> struct hash<Vertex> {
        size_t operator()(Vertex const& vertex) const {
            return ((hash<glm::vec3>()(vertex.pos) ^
                   (hash<glm::vec3>()(vertex.color) << 1)) >> 1) ^
                   (hash<glm::vec2>()(vertex.texCoord) << 1);
        }
    };
}


```