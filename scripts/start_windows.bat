@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
:: 医院叙事生成助手 - Windows 一键启动脚本
:: 用法: start_windows.bat [start|stop|status|restart|help]
:: 默认操作: start
:: ============================================================

title 医院叙事生成助手 - 服务管理

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

:: 默认端口
set "APP_PORT=8005"
set "FRONTEND_PORT=8501"

:: 读取 .env 文件中的端口配置
if exist "%PROJECT_ROOT%\.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in ("%PROJECT_ROOT%\.env") do (
        set "key=%%a"
        set "val=%%b"
        :: 去除前后空格
        for /f "tokens=*" %%i in ("!key!") do set "key=%%i"
        for /f "tokens=*" %%i in ("!val!") do set "val=%%i"
        if "!key!"=="APP_PORT" set "APP_PORT=!val!"
        if "!key!"=="FRONTEND_PORT" set "FRONTEND_PORT=!val!"
    )
)

set "BACKEND_URL=http://localhost:%APP_PORT%"
set "FRONTEND_URL=http://localhost:%FRONTEND_PORT%"
set "BACKEND_LOG=%PROJECT_ROOT%\logs\backend.log"
set "FRONTEND_LOG=%PROJECT_ROOT%\logs\frontend.log"

:: 创建日志目录
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"

:: 激活虚拟环境
if exist "%PROJECT_ROOT%\.venv\Scripts\activate.bat" (
    call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
) else (
    echo [警告] 未找到 .venv 虚拟环境，将使用系统 Python
)

:: 解析命令
set "COMMAND=%~1"
if "%COMMAND%"=="" set "COMMAND=start"

if "%COMMAND%"=="start" goto :start
if "%COMMAND%"=="stop" goto :stop
if "%COMMAND%"=="status" goto :status
if "%COMMAND%"=="restart" goto :restart
if "%COMMAND%"=="help" goto :help
if "%COMMAND%"=="-h" goto :help
if "%COMMAND%"=="--help" goto :help

echo [错误] 未知命令: %COMMAND%
goto :help

:: ============================================================
:: 启动服务
:: ============================================================
:start
call :check_status

if "!BACKEND_RUNNING!"=="true" (
    echo [提示] 后端服务已在运行: %BACKEND_URL%
) else (
    :: 检查端口占用
    call :check_port %APP_PORT%
    if !PORT_OCCUPIED! equ 1 (
        echo [错误] 后端端口 %APP_PORT% 已被占用
        echo        请先执行 stop 或更换 APP_PORT
        exit /b 1
    )
)

if "!FRONTEND_RUNNING!"=="true" (
    echo [提示] 前端服务已在运行: %FRONTEND_URL%
) else (
    call :check_port %FRONTEND_PORT%
    if !PORT_OCCUPIED! equ 1 (
        echo [错误] 前端端口 %FRONTEND_PORT% 已被占用
        echo        请先执行 stop 或更换 FRONTEND_PORT
        exit /b 1
    )
)

echo.
echo ============================================================
echo  医院叙事生成助手 - 启动服务
echo ============================================================
echo 后端地址: %BACKEND_URL%
echo 前端地址: %FRONTEND_URL%
echo 日志目录: %PROJECT_ROOT%\logs
echo ============================================================
echo.

:: 启动后端
if "!BACKEND_RUNNING!"=="false" (
    echo [1/2] 正在启动后端 API ...
    start /B "hospital-backend" cmd /c "cd /d "%PROJECT_ROOT%" && python main.py > "%BACKEND_LOG%" 2>&1"
    timeout /t 3 /nobreak >nul
    call :check_port %APP_PORT%
    if !PORT_OCCUPIED! equ 1 (
        echo        后端启动成功
    ) else (
        echo        [警告] 后端可能未正常启动，请查看日志: %BACKEND_LOG%
    )
)

:: 启动前端
if "!FRONTEND_RUNNING!"=="false" (
    echo [2/2] 正在启动前端 Streamlit ...
    start /B "hospital-frontend" cmd /c "cd /d "%PROJECT_ROOT%" && streamlit run streamlit_app.py --server.port %FRONTEND_PORT% > "%FRONTEND_LOG%" 2>&1"
    timeout /t 5 /nobreak >nul
    call :check_port %FRONTEND_PORT%
    if !PORT_OCCUPIED! equ 1 (
        echo        前端启动成功
    ) else (
        echo        [警告] 前端可能未正常启动，请查看日志: %FRONTEND_LOG%
    )
)

echo.
echo ============================================================
echo  服务启动完成
echo ============================================================
echo 后端 API:    %BACKEND_URL%
echo 前端页面:    %FRONTEND_URL%
echo API 文档:    %BACKEND_URL%/docs
echo 日志文件:    %PROJECT_ROOT%\logs
echo ============================================================
echo.
echo 提示: 使用 start_windows.bat stop  停止服务
echo       使用 start_windows.bat status 查看状态

pause
goto :eof

:: ============================================================
:: 停止服务
:: ============================================================
:stop
echo.
echo ============================================================
echo  医院叙事生成助手 - 停止服务
echo ============================================================
echo.

:: 通过端口查找并停止后端进程
call :kill_by_port %APP_PORT% "后端"

:: 通过端口查找并停止前端进程
call :kill_by_port %FRONTEND_PORT% "前端"

echo.
echo [完成] 所有服务已停止
pause
goto :eof

:: ============================================================
:: 查看状态
:: ============================================================
:status
call :check_status

echo.
echo ============================================================
echo  服务状态
echo ============================================================
if "!BACKEND_RUNNING!"=="true" (
    echo [后端] 运行中 - %BACKEND_URL%
) else (
    echo [后端] 未运行
)

if "!FRONTEND_RUNNING!"=="true" (
    echo [前端] 运行中 - %FRONTEND_URL%
) else (
    echo [前端] 未运行
)

echo.
if "!BACKEND_RUNNING!"=="true" if "!FRONTEND_RUNNING!"=="true" (
    echo [状态] 所有服务正常运行
) else (
    echo [状态] 部分服务未运行
)

goto :eof

:: ============================================================
:: 重启服务
:: ============================================================
:restart
call :stop
timeout /t 2 /nobreak >nul
call :start
goto :eof

:: ============================================================
:: 帮助信息
:: ============================================================
:help
echo.
echo ============================================================
echo  医院叙事生成助手 - Windows 服务管理脚本
echo ============================================================
echo.
echo 用法: start_windows.bat [命令]
echo.
echo 可用命令:
echo   start    启动前后端服务（默认）
echo   stop     停止前后端服务
echo   status   查看服务运行状态
echo   restart  重启前后端服务
echo   help     显示帮助信息
echo.
echo 示例:
echo   start_windows.bat
echo   start_windows.bat start
echo   start_windows.bat stop
echo   start_windows.bat status
echo.

pause
goto :eof

:: ============================================================
:: 子程序：检查端口是否被占用
:: 参数 %%1: 端口号
:: 输出: PORT_OCCUPIED=1 表示被占用，=0 表示未占用
:: ============================================================
:check_port
set "PORT_OCCUPIED=0"
netstat -ano | findstr ":%~1 " | findstr "LISTENING" >nul
if !errorlevel! equ 0 set "PORT_OCCUPIED=1"
goto :eof

:: ============================================================
:: 子程序：检查服务状态
:: 输出: BACKEND_RUNNING, FRONTEND_RUNNING
:: ============================================================
:check_status
call :check_port %APP_PORT%
if !PORT_OCCUPIED! equ 1 (
    set "BACKEND_RUNNING=true"
) else (
    set "BACKEND_RUNNING=false"
)

call :check_port %FRONTEND_PORT%
if !PORT_OCCUPIED! equ 1 (
    set "FRONTEND_RUNNING=true"
) else (
    set "FRONTEND_RUNNING=false"
)
goto :eof

:: ============================================================
:: 子程序：通过端口停止进程
:: 参数 %%1: 端口号, %%2: 服务名称
:: ============================================================
:kill_by_port
set "TARGET_PORT=%~1"
set "SERVICE_NAME=%~2"

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%TARGET_PORT% " ^| findstr "LISTENING"') do (
    echo [停止] %SERVICE_NAME% 服务 PID: %%a
    taskkill /PID %%a /F >nul 2>&1
    if !errorlevel! equ 0 (
        echo        %SERVICE_NAME% 已停止
    ) else (
        echo        [警告] 无法停止 %SERVICE_NAME% PID %%a，可能需要管理员权限
    )
)
goto :eof
