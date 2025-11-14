# Hugo 构建脚本（Windows PowerShell）
# 自动预处理 Obsidian 图片链接并构建 Hugo 站点
# 使用预处理方式，不修改原始文件，保持 Obsidian 兼容

param(
  [switch]$Server,      # 启动开发服务器
  [switch]$Draft,        # 包含草稿
  [switch]$NoPreprocess  # 跳过预处理（直接使用原始文件）
)

$ErrorActionPreference = "Stop"

Write-Host "=== Hugo 博客构建脚本 ===" -ForegroundColor Cyan

# 1. 预处理 Obsidian 图片链接（创建临时副本，不修改原始文件）
$ContentDir = "content"
if (-not $NoPreprocess) {
  Write-Host "`n[1/2] 预处理 Obsidian 图片链接..." -ForegroundColor Yellow
  # 删除旧的临时目录（如果存在）
  Remove-Item -Path ".hugo_temp_content" -Recurse -Force -ErrorAction SilentlyContinue
  # 开发服务器模式：每次启动时强制更新，确保最新内容
  if ($Server) {
    python scripts/preprocess_obsidian.py --force
  }
  else {
    python scripts/preprocess_obsidian.py
  }
  if ($LASTEXITCODE -eq 0) {
    $ContentDir = ".hugo_temp_content"
    Write-Host "✓ 预处理完成（使用临时内容目录）" -ForegroundColor Green
  }
  else {
    Write-Host "警告: 预处理失败，使用原始内容目录..." -ForegroundColor Yellow
    $ContentDir = "content"
  }
}
else {
  Write-Host "`n[1/2] 跳过预处理，使用原始内容目录" -ForegroundColor Gray
}

# 2. 构建或启动 Hugo
if ($Server) {
  Write-Host "`n[2/2] 启动 Hugo 开发服务器..." -ForegroundColor Yellow
  if ($Draft) {
    hugo server -D --contentDir $ContentDir
  }
  else {
    hugo server --contentDir $ContentDir
  }
}
else {
  Write-Host "`n[2/2] 构建 Hugo 站点..." -ForegroundColor Yellow
  hugo --minify --contentDir $ContentDir
  if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 构建完成！输出目录: public/" -ForegroundColor Green
  }
  else {
    Write-Host "✗ 构建失败" -ForegroundColor Red
    exit 1
  }
}

