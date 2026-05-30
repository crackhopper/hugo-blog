# `src/hugo_blog/cli/deploy.py`

这个文件是发布入口，负责把 Hugo 输出推送到部署仓库。

## 主要职责

- 读取 `.env` 中的部署配置。
- 克隆或复用部署目录。
- 清空部署目录中除 `.git` 外的旧文件。
- 调用 `blog-build --destination` 构建。
- 提交并推送部署仓库。

## 依赖配置

- `DEPLOY_REPO`
- `DEPLOY_BRANCH`
- `DEPLOY_DIR`

## 修改注意

这是会改写部署目录并执行 git push 的代码。新增行为时要优先补测试，并避免影响源仓库工作区。
