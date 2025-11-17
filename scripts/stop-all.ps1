# 停止写作环境脚本
# 停止所有相关的后台进程

$ErrorActionPreference = "Continue"

Write-Host "=== 停止写作环境 ===" -ForegroundColor Cyan
Write-Host ""

# 查找并停止 Python 监听进程
Write-Host "查找 Python 监听进程..." -ForegroundColor Yellow
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*watch_content.py*" -or
    $_.Path -like "*watch_content.py*"
}

if ($pythonProcesses) {
    foreach ($proc in $pythonProcesses) {
        Write-Host "停止进程: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✓ Python 监听进程已停止" -ForegroundColor Green
} else {
    Write-Host "未找到运行中的 Python 监听进程" -ForegroundColor Gray
}

# 查找并停止 Hugo 服务器进程
Write-Host "`n查找 Hugo 服务器进程..." -ForegroundColor Yellow
$hugoProcesses = Get-Process hugo -ErrorAction SilentlyContinue

if ($hugoProcesses) {
    foreach ($proc in $hugoProcesses) {
        Write-Host "停止进程: $($proc.ProcessName) (PID: $($proc.Id))" -ForegroundColor Gray
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✓ Hugo 服务器进程已停止" -ForegroundColor Green
} else {
    Write-Host "未找到运行中的 Hugo 服务器进程" -ForegroundColor Gray
}

# 停止所有 PowerShell 后台作业
Write-Host "`n清理 PowerShell 后台作业..." -ForegroundColor Yellow
$jobs = Get-Job -ErrorAction SilentlyContinue
if ($jobs) {
    foreach ($job in $jobs) {
        Write-Host "停止作业: $($job.Name) (ID: $($job.Id))" -ForegroundColor Gray
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -ErrorAction SilentlyContinue
    }
    Write-Host "✓ 后台作业已清理" -ForegroundColor Green
} else {
    Write-Host "未找到运行中的后台作业" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== 所有服务已停止 ===" -ForegroundColor Cyan

