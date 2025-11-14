# 部署脚本
# 编译 Hugo 站点并部署到 GitHub Pages
# 注意：此脚本应在项目根目录运行（./scripts/deploy.ps1）

param(
    [switch]$Force  # 强制部署（即使有未提交的更改）
)

$ErrorActionPreference = "Stop"

# 确保在项目根目录运行
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "=== Hugo 博客部署脚本 ===" -ForegroundColor Cyan
Write-Host "工作目录: $projectRoot" -ForegroundColor Gray
Write-Host ""

# 检查 Git 状态
Write-Host "[1/5] 检查 Git 状态..." -ForegroundColor Yellow
$gitStatus = git status --porcelain
if ($gitStatus -and -not $Force) {
    Write-Host "警告: 检测到未提交的更改:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Gray
    $response = Read-Host "是否继续部署? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "部署已取消" -ForegroundColor Gray
        exit 0
    }
} else {
    Write-Host "✓ Git 状态正常" -ForegroundColor Green
}

# 检查 Python 环境
Write-Host "`n[2/5] 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ 未找到 Python，请先安装 Python" -ForegroundColor Red
    exit 1
}

# 预处理内容
Write-Host "`n[3/5] 预处理 Obsidian 图片链接..." -ForegroundColor Yellow
python scripts/preprocess_obsidian.py --force
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 预处理失败" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 预处理完成" -ForegroundColor Green

# 构建 Hugo 站点
Write-Host "`n[4/5] 构建 Hugo 站点..." -ForegroundColor Yellow
hugo --minify --contentDir .hugo_temp_content
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 构建失败" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 构建完成" -ForegroundColor Green

# 部署到 GitHub Pages
Write-Host "`n[5/5] 部署到 GitHub Pages..." -ForegroundColor Yellow

# 目标仓库
$deployRepo = "git@github.com:crackhopper/crackhopper.github.io.git"
$deployBranch = "main"

# 检查 public 目录是否存在
if (-not (Test-Path "public")) {
    Write-Host "✗ public 目录不存在" -ForegroundColor Red
    exit 1
}

# 进入 public 目录
Push-Location public

try {
    # 检查是否已经是 git 仓库
    if (-not (Test-Path ".git")) {
        Write-Host "初始化 Git 仓库..." -ForegroundColor Gray
        git init
        git remote add origin $deployRepo
    } else {
        # 检查远程仓库是否正确
        $currentRemote = git remote get-url origin 2>&1
        if ($LASTEXITCODE -ne 0 -or $currentRemote -ne $deployRepo) {
            Write-Host "更新远程仓库地址..." -ForegroundColor Gray
            git remote remove origin -ErrorAction SilentlyContinue
            git remote add origin $deployRepo
        }
    }
    
    # 添加所有文件
    Write-Host "添加文件到 Git..." -ForegroundColor Gray
    git add -A
    
    # 检查是否有更改
    $status = git status --porcelain
    if (-not $status) {
        Write-Host "✓ 没有更改需要部署" -ForegroundColor Green
        Pop-Location
        exit 0
    }
    
    # 提交
    $commitMessage = "Deploy: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-Host "提交更改..." -ForegroundColor Gray
    git commit -m $commitMessage
    
    # 推送到 GitHub
    Write-Host "推送到 GitHub..." -ForegroundColor Gray
    git push -f origin HEAD:$deployBranch
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ 部署成功！" -ForegroundColor Green
        Write-Host "站点地址: https://crackhopper.github.io" -ForegroundColor Cyan
    } else {
        Write-Host "✗ 推送失败" -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "=== 部署完成 ===" -ForegroundColor Cyan

