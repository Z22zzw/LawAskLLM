# Windows 11 PowerShell 本地开发启动脚本
param(
    [switch]$SkipDb,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "   $msg" -ForegroundColor Gray }

if (-not $SkipDb -and -not $BackendOnly -and -not $FrontendOnly) {
    Write-Step "启动开发数据库 (MySQL)..."
    docker compose -f docker-compose.dev.yml up -d
    Start-Sleep -Seconds 5
    Write-Ok "MySQL 启动完成"
}

if ($BackendOnly) {
    Write-Step "启动 FastAPI 后端..."
    conda run -n langchain_env --no-capture-output `
        uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 `
        --app-dir backend
    exit
}

if ($FrontendOnly) {
    Write-Step "启动 React 前端..."
    Set-Location frontend
    if (-not (Test-Path node_modules)) { npm install }
    npm run dev
    exit
}

Write-Ok "开发环境准备完成"
Write-Host ""
Write-Host "请分别在新 PowerShell 窗口运行：" -ForegroundColor Yellow
Write-Host ""
Write-Info "# 后端"
Write-Info "  .\start_dev.ps1 -BackendOnly"
Write-Host ""
Write-Info "# 前端"
Write-Info "  .\start_dev.ps1 -FrontendOnly"
Write-Host ""
Write-Host "访问地址：" -ForegroundColor Yellow
Write-Info "  React 前端:  http://localhost:3000"
Write-Info "  FastAPI:     http://localhost:8000/api/docs"
Write-Info "  Streamlit:   python start.py  (原有功能，端口 8501)"
