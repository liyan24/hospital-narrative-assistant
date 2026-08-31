@echo off
chcp 65001 >nul
title 医院叙事生成助手-后端(8005)
cd /d %~dp0

echo [1/2] 检查 8005 端口占用...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8005 " ^| findstr LISTENING') do (
    echo     端口 8005 被 PID=%%a 占用，正在结束该进程...
    taskkill /F /PID %%a >nul 2>&1
)

rem 8000 留给本机其他项目（如 ZRAdmin），本项目后端固定使用 8005
rem APP_PORT 环境变量优先级高于 .env，保证 settings.app_port 与实际端口一致
set APP_PORT=8005

echo [2/2] 启动后端 FastAPI 服务: http://localhost:8005  (Ctrl+C 停止)
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8005 --reload
pause
