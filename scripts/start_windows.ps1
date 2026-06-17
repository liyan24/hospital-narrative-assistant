# ============================================================
# 医院叙事生成助手 - Windows PowerShell 一键启动脚本
# 用法: .\start_windows.ps1 [start|stop|status|restart|help]
# 默认操作: start
# 需要执行策略: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# ============================================================

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [string]$Command = "start"
)

# 设置输出编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 获取项目根目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path "$ScriptDir\.." | Select-Object -ExpandProperty Path

# 默认端口
$AppPort = 8005
$FrontendPort = 8501

# 读取 .env 文件中的端口配置
$EnvPath = Join-Path $ProjectRoot ".env"
if (Test-Path $EnvPath) {
    Get-Content $EnvPath -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -match "^\s*([^#\s=]+)\s*=\s*(.*?)\s*$") {
            $key = $Matches[1]
            $val = $Matches[2]
            if ($key -eq "APP_PORT") { $AppPort = [int]$val }
            if ($key -eq "FRONTEND_PORT") { $FrontendPort = [int]$val }
        }
    }
}

$BackendUrl = "http://localhost:$AppPort"
$FrontendUrl = "http://localhost:$FrontendPort"
$LogsDir = Join-Path $ProjectRoot "logs"
$BackendLog = Join-Path $LogsDir "backend.log"
$FrontendLog = Join-Path $LogsDir "frontend.log"
$BackendPidFile = Join-Path $ProjectRoot ".backend.pid"
$FrontendPidFile = Join-Path $ProjectRoot ".frontend.pid"

# 创建日志目录
if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

# 激活虚拟环境
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $VenvActivate) {
    & $VenvActivate
} else {
    Write-Host "[Warning] Virtual environment not found, using system Python" -ForegroundColor Yellow
}

# ============================================================
# 工具函数
# ============================================================
function Test-PortListening($Port) {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return ($null -ne $connection)
}

function Get-ProcessByPort($Port) {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connection) {
        return Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    }
    return $null
}

function Stop-ServiceByPort($Port, $Name) {
    $proc = Get-ProcessByPort $Port
    if ($proc) {
        Write-Host "[Stop] $Name service PID: $($proc.Id)" -ForegroundColor Cyan
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-Host "       $Name stopped" -ForegroundColor Green
    }
}

function Show-Status {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host " Hospital Narrative Assistant - Service Status" -ForegroundColor Blue
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host ""

    $backendRunning = Test-PortListening $AppPort
    $frontendRunning = Test-PortListening $FrontendPort

    if ($backendRunning) {
        Write-Host "[Backend] Running - $BackendUrl" -ForegroundColor Green
    } else {
        Write-Host "[Backend] Not running" -ForegroundColor Gray
    }

    if ($frontendRunning) {
        Write-Host "[Frontend] Running - $FrontendUrl" -ForegroundColor Green
    } else {
        Write-Host "[Frontend] Not running" -ForegroundColor Gray
    }

    Write-Host ""
    if ($backendRunning -and $frontendRunning) {
        Write-Host "[Status] All services are running" -ForegroundColor Green
    } else {
        Write-Host "[Status] Some services are not running" -ForegroundColor Yellow
    }
}

function Start-Services {
    Show-Status
    $backendRunning = Test-PortListening $AppPort
    $frontendRunning = Test-PortListening $FrontendPort

    if (-not $backendRunning) {
        if (Test-PortListening $AppPort) {
            Write-Host "[Error] Backend port $AppPort is occupied" -ForegroundColor Red
            exit 1
        }
    }

    if (-not $frontendRunning) {
        if (Test-PortListening $FrontendPort) {
            Write-Host "[Error] Frontend port $FrontendPort is occupied" -ForegroundColor Red
            exit 1
        }
    }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host " Hospital Narrative Assistant - Start Services" -ForegroundColor Blue
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host " Backend:  $BackendUrl"
    Write-Host " Frontend: $FrontendUrl"
    Write-Host " Logs:     $LogsDir"
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host ""

    # 启动后端
    if (-not $backendRunning) {
        Write-Host "[1/2] Starting backend API ..." -ForegroundColor Cyan
        $backendProc = Start-Process -FilePath "python" -ArgumentList "main.py" -WorkingDirectory $ProjectRoot -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendLog -WindowStyle Hidden -PassThru
        $backendProc.Id | Out-File $BackendPidFile -Encoding utf8
        Start-Sleep -Seconds 3

        if (Test-PortListening $AppPort) {
            Write-Host "      Backend started (PID: $($backendProc.Id))" -ForegroundColor Green
        } else {
            Write-Host "      [Warning] Backend may not have started, check log: $BackendLog" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[Backend] Already running: $BackendUrl" -ForegroundColor Green
    }

    # 启动前端
    if (-not $frontendRunning) {
        Write-Host "[2/2] Starting frontend Streamlit ..." -ForegroundColor Cyan
        $frontendProc = Start-Process -FilePath "streamlit" -ArgumentList "run", "streamlit_app.py", "--server.port", "$FrontendPort" -WorkingDirectory $ProjectRoot -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendLog -WindowStyle Hidden -PassThru
        $frontendProc.Id | Out-File $FrontendPidFile -Encoding utf8
        Start-Sleep -Seconds 5

        if (Test-PortListening $FrontendPort) {
            Write-Host "      Frontend started (PID: $($frontendProc.Id))" -ForegroundColor Green
        } else {
            Write-Host "      [Warning] Frontend may not have started, check log: $FrontendLog" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[Frontend] Already running: $FrontendUrl" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " Services started" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " Backend API: $BackendUrl"
    Write-Host " Frontend:    $FrontendUrl"
    Write-Host " API Docs:    $BackendUrl/docs"
    Write-Host " Logs:        $LogsDir"
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Tips: .\start_windows.ps1 stop   to stop services"
    Write-Host "      .\start_windows.ps1 status to check status"
}

function Stop-Services {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host " Hospital Narrative Assistant - Stop Services" -ForegroundColor Blue
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host ""

    # 通过 PID 文件停止后端
    if (Test-Path $BackendPidFile) {
        $pid = Get-Content $BackendPidFile -Raw
        if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
            Write-Host "[Stop] Backend service PID: $pid" -ForegroundColor Cyan
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "       Backend stopped" -ForegroundColor Green
        }
        Remove-Item $BackendPidFile -Force -ErrorAction SilentlyContinue
    }

    # 通过 PID 文件停止前端
    if (Test-Path $FrontendPidFile) {
        $pid = Get-Content $FrontendPidFile -Raw
        if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
            Write-Host "[Stop] Frontend service PID: $pid" -ForegroundColor Cyan
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "       Frontend stopped" -ForegroundColor Green
        }
        Remove-Item $FrontendPidFile -Force -ErrorAction SilentlyContinue
    }

    # 兜底：通过端口清理残留进程
    Stop-ServiceByPort $AppPort "Backend"
    Stop-ServiceByPort $FrontendPort "Frontend"

    Write-Host ""
    Write-Host "[Done] All services stopped" -ForegroundColor Green
}

function Show-Help {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host " Hospital Narrative Assistant - Windows Service Manager" -ForegroundColor Blue
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host ""
    Write-Host "Usage: .\start_windows.ps1 [command]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  start    Start backend and frontend services (default)"
    Write-Host "  stop     Stop all services"
    Write-Host "  status   Show service status"
    Write-Host "  restart  Restart all services"
    Write-Host "  help     Show this help"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\start_windows.ps1"
    Write-Host "  .\start_windows.ps1 start"
    Write-Host "  .\start_windows.ps1 stop"
    Write-Host "  .\start_windows.ps1 status"
    Write-Host ""
    Write-Host "Note: If PowerShell execution policy blocks running scripts,"
    Write-Host "      run: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
    Write-Host ""
}

# ============================================================
# 主程序入口
# ============================================================
switch ($Command.ToLower()) {
    "start" { Start-Services }
    "stop" { Stop-Services }
    "status" { Show-Status }
    "restart" { Stop-Services; Start-Sleep -Seconds 2; Start-Services }
    "help" { Show-Help }
    "-h" { Show-Help }
    "--help" { Show-Help }
    default {
        Write-Host "[Error] Unknown command: $Command" -ForegroundColor Red
        Show-Help
        exit 1
    }
}
