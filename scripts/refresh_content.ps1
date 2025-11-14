# 刷新预处理内容（Windows PowerShell）
# 在开发时，如果修改了原始文件，运行此脚本更新临时目录

Write-Host "刷新预处理内容..." -ForegroundColor Yellow
python scripts/preprocess_obsidian.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ 内容已更新" -ForegroundColor Green
} else {
    Write-Host "✗ 更新失败" -ForegroundColor Red
    exit 1
}

