# 初始化部署子模块
param(
    [string]$DeployRepo,
    [string]$DeployDir
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Get-DotEnvVariables {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return @{}
    }

    $result = @{}
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $key = $parts[0].Trim()
        $value = $parts[1].Trim()

        if (
            $value.Length -ge 2 -and (
                ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            )
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        if ($key) {
            $result[$key] = $value
        }
    }

    return $result
}

$envFile = Join-Path $projectRoot ".env"
$dotenvValues = Get-DotEnvVariables -Path $envFile

if (-not $DeployRepo -and $dotenvValues.ContainsKey("DEPLOY_REPO")) {
    $DeployRepo = $dotenvValues["DEPLOY_REPO"]
}
if (-not $DeployDir -and $dotenvValues.ContainsKey("DEPLOY_DIR")) {
    $DeployDir = $dotenvValues["DEPLOY_DIR"]
}
if (-not $DeployDir) {
    $DeployDir = "repo_to_deploy"
}

if (-not $DeployRepo) {
    Write-Host "✗ 缺少 DEPLOY_REPO 环境变量或参数，无法初始化子模块" -ForegroundColor Red
    exit 1
}

Write-Host "*** 初始化部署子模块 ***" -ForegroundColor Cyan

$submoduleConfigured = $false
if (Test-Path ".gitmodules") {
    $submoduleConfigured = Select-String -Path ".gitmodules" -Pattern "path = $DeployDir" -Quiet
}

if (-not $submoduleConfigured) {
    Write-Host "添加子模块：$DeployRepo -> $DeployDir" -ForegroundColor Yellow
    git submodule add $DeployRepo $DeployDir
} else {
    Write-Host "检测到 .gitmodules 中已存在 $DeployDir，跳过 add 步骤" -ForegroundColor Gray
}

Write-Host "同步子模块内容..." -ForegroundColor Yellow
git submodule update --init --recursive $DeployDir

if (-not (Test-Path $DeployDir)) {
    Write-Host "✗ 子模块目录仍不存在：$DeployDir" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 子模块初始化完成 ($DeployDir)" -ForegroundColor Green

