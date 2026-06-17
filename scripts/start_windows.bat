@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: Hospital Narrative Assistant - Windows Startup Script
:: Usage: start_windows.bat [start|stop|status|restart|help]
:: Default: start
:: ============================================================

title Hospital Narrative Assistant - Service Manager

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

:: Default ports
set "APP_PORT=8005"
set "FRONTEND_PORT=8501"

:: Read ports from .env
if exist "%PROJECT_ROOT%\.env" (
    for /f "usebackq tokens=1,2 delims==" %%a in ("%PROJECT_ROOT%\.env") do (
        set "key=%%a"
        set "val=%%b"
        set "key=!key: =!"
        set "val=!val: =!"
        if "!key!"=="APP_PORT" set "APP_PORT=!val!"
        if "!key!"=="FRONTEND_PORT" set "FRONTEND_PORT=!val!"
    )
)

set "BACKEND_URL=http://localhost:%APP_PORT%"
set "FRONTEND_URL=http://localhost:%FRONTEND_PORT%"
set "BACKEND_LOG=%PROJECT_ROOT%\logs\backend.log"
set "FRONTEND_LOG=%PROJECT_ROOT%\logs\frontend.log"
set "BACKEND_PID_FILE=%PROJECT_ROOT%\.backend.pid"
set "FRONTEND_PID_FILE=%PROJECT_ROOT%\.frontend.pid"

:: Create logs directory
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"

:: Activate virtual environment
if exist "%PROJECT_ROOT%\.venv\Scripts\activate.bat" (
    call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
)

:: ============================================================
:: Subroutines (defined before main logic)
:: ============================================================

goto :main

:check_port
set "PORT_OCCUPIED=0"
netstat -ano | findstr ":%~1 " | findstr "LISTENING" >nul
if !errorlevel! equ 0 set "PORT_OCCUPIED=1"
goto :eof

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

:kill_by_port
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%~1 " ^| findstr "LISTENING"') do (
    echo [Stop] %~2 service PID: %%a
    taskkill /PID %%a /F >nul 2>&1
)
goto :eof

:find_python_pid
for /f "tokens=2 delims=," %%a in ('wmic process where "commandline like '%%python main.py%%'" get processid /format:csv ^| findstr "[0-9]"') do (
    echo %%a
    goto :eof
)
goto :eof

:find_streamlit_pid
for /f "tokens=2 delims=," %%a in ('wmic process where "commandline like '%%streamlit run streamlit_app.py%%'" get processid /format:csv ^| findstr "[0-9]"') do (
    echo %%a
    goto :eof
)
goto :eof

:: ============================================================
:: Main logic
:: ============================================================
:main

:: Parse command
set "COMMAND=%~1"
if "%COMMAND%"=="" set "COMMAND=start"

if "%COMMAND%"=="start" goto :do_start
if "%COMMAND%"=="stop" goto :do_stop
if "%COMMAND%"=="status" goto :do_status
if "%COMMAND%"=="restart" goto :do_restart
if "%COMMAND%"=="help" goto :do_help
if "%COMMAND%"=="-h" goto :do_help
if "%COMMAND%"=="--help" goto :do_help

echo [Error] Unknown command: %COMMAND%
goto :do_help

:do_start
call :check_status

if "!BACKEND_RUNNING!"=="true" (
    echo [Backend] Already running: %BACKEND_URL%
) else (
    call :check_port %APP_PORT%
    if !PORT_OCCUPIED! equ 1 (
        echo [Error] Backend port %APP_PORT% is occupied
        exit /b 1
    )
)

if "!FRONTEND_RUNNING!"=="true" (
    echo [Frontend] Already running: %FRONTEND_URL%
) else (
    call :check_port %FRONTEND_PORT%
    if !PORT_OCCUPIED! equ 1 (
        echo [Error] Frontend port %FRONTEND_PORT% is occupied
        exit /b 1
    )
)

echo.
echo ============================================================
echo  Hospital Narrative Assistant - Start Services
echo ============================================================
echo Backend:  %BACKEND_URL%
echo Frontend: %FRONTEND_URL%
echo Logs:     %PROJECT_ROOT%\logs
echo ============================================================
echo.

if "!BACKEND_RUNNING!"=="false" (
    echo [1/2] Starting backend API ...
    start /B "" cmd /c "cd /d "%PROJECT_ROOT%" && python main.py > "%BACKEND_LOG%" 2>&1"
    timeout /t 3 /nobreak >nul
    call :find_python_pid > "%BACKEND_PID_FILE%"
    call :check_port %APP_PORT%
    if !PORT_OCCUPIED! equ 1 (
        echo        Backend started
    ) else (
        echo        [Warning] Backend may not have started, check log: %BACKEND_LOG%
    )
)

if "!FRONTEND_RUNNING!"=="false" (
    echo [2/2] Starting frontend Streamlit ...
    start /B "" cmd /c "cd /d "%PROJECT_ROOT%" && streamlit run streamlit_app.py --server.port %FRONTEND_PORT% > "%FRONTEND_LOG%" 2>&1"
    timeout /t 5 /nobreak >nul
    call :find_streamlit_pid > "%FRONTEND_PID_FILE%"
    call :check_port %FRONTEND_PORT%
    if !PORT_OCCUPIED! equ 1 (
        echo        Frontend started
    ) else (
        echo        [Warning] Frontend may not have started, check log: %FRONTEND_LOG%
    )
)

echo.
echo ============================================================
echo  Services started
echo ============================================================
echo Backend API: %BACKEND_URL%
echo Frontend:    %FRONTEND_URL%
echo API Docs:    %BACKEND_URL%/docs
echo Logs:        %PROJECT_ROOT%\logs
echo ============================================================
echo.
echo Tips: start_windows.bat stop   - stop services
echo       start_windows.bat status - check status
pause
goto :eof

:do_stop
echo.
echo ============================================================
echo  Hospital Narrative Assistant - Stop Services
echo ============================================================
echo.

if exist "%BACKEND_PID_FILE%" (
    set /p PID=<"%BACKEND_PID_FILE%"
    if defined PID (
        echo [Stop] Backend service PID: !PID!
        taskkill /PID !PID! /F >nul 2>&1
    )
    del "%BACKEND_PID_FILE%" >nul 2>&1
)

if exist "%FRONTEND_PID_FILE%" (
    set /p PID=<"%FRONTEND_PID_FILE%"
    if defined PID (
        echo [Stop] Frontend service PID: !PID!
        taskkill /PID !PID! /F >nul 2>&1
    )
    del "%FRONTEND_PID_FILE%" >nul 2>&1
)

call :kill_by_port %APP_PORT% "Backend"
call :kill_by_port %FRONTEND_PORT% "Frontend"

echo.
echo [Done] All services stopped
pause
goto :eof

:do_status
call :check_status

echo.
echo ============================================================
echo  Hospital Narrative Assistant - Service Status
echo ============================================================
if "!BACKEND_RUNNING!"=="true" (
    echo [Backend] Running - %BACKEND_URL%
) else (
    echo [Backend] Not running
)

if "!FRONTEND_RUNNING!"=="true" (
    echo [Frontend] Running - %FRONTEND_URL%
) else (
    echo [Frontend] Not running
)

echo.
if "!BACKEND_RUNNING!"=="true" if "!FRONTEND_RUNNING!"=="true" (
    echo [Status] All services are running
) else (
    echo [Status] Some services are not running
)
pause
goto :eof

:do_restart
call :do_stop
timeout /t 2 /nobreak >nul
call :do_start
goto :eof

:do_help
echo.
echo ============================================================
echo  Hospital Narrative Assistant - Windows Service Manager
echo ============================================================
echo.
echo Usage: start_windows.bat [command]
echo.
echo Commands:
echo   start    Start backend and frontend services (default)
echo   stop     Stop all services
echo   status   Show service status
echo   restart  Restart all services
echo   help     Show this help
echo.
echo Examples:
echo   start_windows.bat
echo   start_windows.bat start
echo   start_windows.bat stop
echo   start_windows.bat status
echo.
echo Note: For full Chinese output and better stability, use:
echo       powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
echo.
pause
goto :eof
