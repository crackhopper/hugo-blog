# 部署脚本
# 编译 Hugo 站点并部署到 GitHub Pages
# 注意：此脚本应在项目根目录运行（./scripts/deploy.ps1）

param(
    [switch]$Force,       # 强制部署（即使有未提交的更改）
    [switch]$ForcePush    # 部署完成后是否使用 git push -f
)

$ErrorActionPreference = "Stop"

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

# 确保在项目根目录运行
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

Write-Host "=== Hugo 博客部署脚本 ===" -ForegroundColor Cyan
Write-Host "工作目录: $projectRoot" -ForegroundColor Gray
Write-Host ""

$envFile = Join-Path $projectRoot ".env"
Write-Host "[0/6] 加载环境变量..." -ForegroundColor Yellow
$dotenvValues = Get-DotEnvVariables -Path $envFile

if (-not $dotenvValues.Count) {
    Write-Host "警告: 未在 $envFile 中找到任何变量" -ForegroundColor Yellow
} else {
    foreach ($entry in $dotenvValues.GetEnumerator()) {
        Set-Item -Path ("Env:{0}" -f $entry.Key) -Value $entry.Value
    }
    Write-Host "✓ 已从 .env 加载环境变量" -ForegroundColor Green
}

$deployRepo = $env:DEPLOY_REPO
$deployBranch = $env:DEPLOY_BRANCH
$deployDirName = if ($env:DEPLOY_DIR) { $env:DEPLOY_DIR } else { "repo_to_deploy" }
$deployDirPath = Join-Path $projectRoot $deployDirName
$initScript = Join-Path $PSScriptRoot "init-deploy-submodule.ps1"

if (-not $deployRepo -or -not $deployBranch) {
    Write-Host "✗ 缺少 DEPLOY_REPO 或 DEPLOY_BRANCH 环境变量，请检查 .env" -ForegroundColor Red
    exit 1
}

# 检查 Git 状态
Write-Host "[1/6] 检查 Git 状态..." -ForegroundColor Yellow
$gitStatus = git status --porcelain
if ($gitStatus -and -not $Force) {
    Write-Host "警告: 检测到未提交的更改:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Gray
    $response = Read-Host "是否继续部署? (Y/n)"
    if (-not $response) {
        $response = "y"
    }
    if ($response.ToLower() -notmatch "^(y|yes)$") {
        Write-Host "部署已取消" -ForegroundColor Gray
        exit 0
    }
} else {
    Write-Host "✓ Git 状态正常" -ForegroundColor Green
}

# 检查 Python 环境
Write-Host "`n[2/6] 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ 未找到 Python，请先安装 Python" -ForegroundColor Red
    exit 1
}

# 预处理内容
Write-Host "`n[3/6] 预处理 Obsidian 图片链接..." -ForegroundColor Yellow
python scripts/preprocess_obsidian.py --force
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 预处理失败" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 预处理完成" -ForegroundColor Green

# 准备部署目录（子模块 + 清理旧内容）
Write-Host "`n[4/6] 准备部署目录..." -ForegroundColor Yellow
if (-not (Test-Path $deployDirPath)) {
    if (-not (Test-Path $initScript)) {
        Write-Host "✗ 找不到初始化脚本：$initScript" -ForegroundColor Red
        exit 1
    }
    Write-Host "检测到目录 $deployDirName 不存在，执行初始化脚本..." -ForegroundColor Gray
    & $initScript -DeployRepo $deployRepo -DeployDir $deployDirName
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 子模块初始化失败" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ 子模块目录已存在：$deployDirName" -ForegroundColor Green
}

Write-Host "清理目录 $deployDirName ..." -ForegroundColor Gray
Push-Location $deployDirPath
Get-ChildItem -Force | Where-Object { $_.Name -ne ".git" } | ForEach-Object {
    if ($_.PSIsContainer) {
        Remove-Item $_.FullName -Recurse -Force
    } else {
        Remove-Item $_.FullName -Force
    }
}
Pop-Location
Write-Host "✓ 目录已清空（保留 .git）" -ForegroundColor Green

# 构建 Hugo 站点
Write-Host "`n[5/6] 构建 Hugo 站点..." -ForegroundColor Yellow
hugo --minify --contentDir .hugo_temp_content --destination $deployDirPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 构建失败" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 构建完成" -ForegroundColor Green

# 部署到 GitHub Pages
Write-Host "`n[6/6] 部署到 GitHub Pages..." -ForegroundColor Yellow

# 进入部署目录
Push-Location $deployDirPath

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
    
    # 禁用自动换行转换，避免 git 提示 LF/CRLF
    git config core.autocrlf false | Out-Null
    git config core.eol lf | Out-Null

    # 添加所有文件
    Write-Host "添加文件到 Git..." -ForegroundColor Gray
    git add -A
    
    # 检查是否有更改
    $status = git status --porcelain
    $hasChanges = [bool]$status
    if (-not $hasChanges -and -not $ForcePush) {
        Write-Host "✓ 没有更改需要部署" -ForegroundColor Green
        Pop-Location
        exit 0
    } elseif (-not $hasChanges -and $ForcePush) {
        Write-Host "⚠ 没有内容更改，但根据 --force-push 继续推送当前提交" -ForegroundColor Yellow
    }
    
    if ($hasChanges) {
        # 提交
        $commitMessage = "Deploy: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        Write-Host "提交更改..." -ForegroundColor Gray
        git commit -m $commitMessage
    } else {
        Write-Host "跳过提交（无文件变化）" -ForegroundColor Gray
    }
    
    # 推送到 GitHub
    if ($ForcePush) {
        Write-Host "推送到 GitHub (force)..." -ForegroundColor Gray
        git push -f origin HEAD:$deployBranch
    } else {
        Write-Host "推送到 GitHub..." -ForegroundColor Gray
        git push origin HEAD:$deployBranch
    }
    
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

