# Obsidian 图片语法支持

本 Hugo 站点支持 Obsidian 的图片语法 `![[filename.png]]`，无需修改原始 Markdown 文件。

## 工作原理

由于 Hugo 的 Goldmark 解析器不会将 `![[...]]` 识别为图片语法，我们使用预处理方案：

1. **预处理脚本** (`preprocess_obsidian.py`) 将 `![[filename.png]]` 转换为标准 Markdown 图片语法 `![alt](/images/filename.png)`
2. 创建临时内容目录 `.hugo_temp_content`，不修改原始文件
3. Hugo 使用临时目录构建站点

## 使用方法

### 方法 1: 使用构建脚本（推荐）

```bash
# Windows
.\build.ps1 -Server        # 启动开发服务器（自动预处理）
.\build.ps1                # 构建站点（自动预处理）

# Linux/macOS
./build.sh --server        # 启动开发服务器（自动预处理）
./build.sh                 # 构建站点（自动预处理）
```

### 方法 2: 手动预处理

```bash
# 预处理内容
python preprocess_obsidian.py

# 使用预处理后的内容构建
hugo --contentDir .hugo_temp_content
```

### 方法 3: 开发时刷新内容

如果在开发过程中修改了原始文件，需要刷新临时目录：

```bash
# Windows
.\refresh_content.ps1

# Linux/macOS
./refresh_content.sh
```

或者使用文件监听（自动刷新）：

```bash
# 需要先安装: pip install watchdog
python watch_content.py
```

## 图片路径

- 图片文件应存放在 `static/images/` 目录
- 在 Markdown 中使用 `![[filename.png]]` 引用
- Hugo 会将其转换为 `/images/filename.png` 路径

## 增量更新

预处理脚本支持增量更新：
- 只处理修改过的文件，提高效率
- 使用 `--force` 参数强制重新处理所有文件
- 开发服务器模式会自动使用 `--force` 确保最新内容

## 注意事项

- Obsidian 图片语法 `![[...]]` 不是标准 Markdown，Hugo 的 Goldmark 解析器不会自动识别
- 原始文件保持不变，Obsidian 可以正常显示
- 临时目录 `.hugo_temp_content/` 已加入 `.gitignore`，不会被提交
- 如果修改了原始文件，记得刷新临时目录或重启开发服务器

## 故障排除

### 图片显示为 broken

1. 检查图片文件是否存在于 `static/images/` 目录
2. 运行 `python preprocess_obsidian.py --force` 强制重新预处理
3. 重启 Hugo 开发服务器

### 修改文件后网页未更新

1. 运行刷新脚本：`.\refresh_content.ps1` 或 `./refresh_content.sh`
2. 或者重启开发服务器（会自动重新预处理）
