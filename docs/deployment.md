# 构建与发布

## 本地构建

```bash
python scripts/build.py
```

这个命令会先把 `content/` 导出到 `.hugo_temp_content/`，然后让 Hugo 使用这个目录作为 `--contentDir` 构建站点。构建时默认不包含草稿，并会清理 `public/` 里已经不再生成的旧文件。

常用选项：

```bash
python scripts/build.py --drafts
python scripts/build.py --destination repo_to_deploy
python scripts/build.py --no-minify
```

## 本地预览

```bash
python scripts/serve.py
```

预览服务会：

- 默认不包含草稿文章
- 默认绑定到 `0.0.0.0`，方便局域网远程访问
- 在 `1313` 端口启动 Hugo 预览站
- 在 `1314` 端口启动 React Admin 和 Docs
- 监听 `content/` 的 Markdown 变化并重新导出

当前访问入口：

```text
http://<host>:1313/        # Hugo 博客预览
http://<host>:1314/admin/  # 文章管理
http://<host>:1314/docs/   # 开发文档
```

如需查看草稿，可以在 Admin 页面勾选 `Preview drafts`，然后点击 `Save all & restart preview`。

## 发布

```bash
python scripts/deploy.py
```

发布命令读取 `.env` 里的配置：

```bash
DEPLOY_REPO="git@github.com:crackhopper/crackhopper.github.io.git"
DEPLOY_BRANCH="master"
DEPLOY_DIR="repo_to_deploy"
```

部署流程是：构建到 `DEPLOY_DIR`，提交输出变更，然后推送到 `DEPLOY_BRANCH`。
