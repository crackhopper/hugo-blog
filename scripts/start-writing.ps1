# 启动写作环境脚本
# 同时启动 Hugo 开发服务器和 Python 内容监听服务
# 注意：此脚本应在项目根目录运行（./scripts/start-writing.ps1）

$ErrorActionPreference = "Stop"

# 确保在项目根目录运行
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "=== 启动写作环境 ===" -ForegroundColor Cyan
Write-Host "工作目录: $projectRoot" -ForegroundColor Gray
Write-Host ""

# 检查 Python 环境
Write-Host "[1/3] 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ 未找到 Python，请先安装 Python" -ForegroundColor Red
    exit 1
}

# 检查依赖
Write-Host "`n[2/3] 检查 Python 依赖..." -ForegroundColor Yellow
$requirementsFile = Join-Path $projectRoot "requirements.txt"
if (Test-Path $requirementsFile) {
    Write-Host "检查 requirements.txt..." -ForegroundColor Gray
    # 检查是否安装了 watchdog
    $watchdogCheck = python -c "import watchdog" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "警告: watchdog 未安装，正在安装..." -ForegroundColor Yellow
        pip install -r $requirementsFile
        if ($LASTEXITCODE -ne 0) {
            Write-Host "✗ 依赖安装失败" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "✓ 依赖已安装" -ForegroundColor Green
    }
} else {
    Write-Host "警告: 未找到 requirements.txt" -ForegroundColor Yellow
}

# 初始预处理
Write-Host "`n[3/3] 初始预处理内容..." -ForegroundColor Yellow
python scripts/preprocess_obsidian.py --force
if ($LASTEXITCODE -ne 0) {
    Write-Host "警告: 预处理失败，继续启动..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 启动服务 ===" -ForegroundColor Cyan
Write-Host ""

# 清空 public 目录，避免残留文件
Write-Host "清理 public 目录..." -ForegroundColor Yellow
$publicDir = Join-Path $projectRoot "public"
if (Test-Path $publicDir) {
    try {
        Remove-Item -Path $publicDir -Recurse -Force
        Write-Host "✓ 已清空 public 目录" -ForegroundColor Green
    } catch {
        Write-Host "警告: 无法清空 public 目录: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "public 目录不存在，跳过清理" -ForegroundColor Gray
}

# 启动 Python 监听服务（后台）
Write-Host "启动 Python 内容监听服务..." -ForegroundColor Yellow
$pythonJob = Start-Job -ScriptBlock {
    Set-Location $using:projectRoot
    python scripts/watch_content.py
}

# 等待一下，让监听服务启动
Start-Sleep -Seconds 2

# 启动 Hugo 开发服务器（前台）
Write-Host "启动 Hugo 开发服务器（跳过 build.ps1，仅使用预处理内容）..." -ForegroundColor Yellow
Write-Host "按 Ctrl+C 停止所有服务`n" -ForegroundColor Gray

try {
    # 直接以预处理目录启动，不再执行 build.ps1
    hugo server --contentDir .hugo_temp_content
} finally {
    # 清理：停止 Python 监听服务
    Write-Host "`n正在停止 Python 监听服务..." -ForegroundColor Yellow
    Stop-Job -Job $pythonJob -ErrorAction SilentlyContinue
    Remove-Job -Job $pythonJob -ErrorAction SilentlyContinue
    Write-Host "✓ 所有服务已停止" -ForegroundColor Green
}

