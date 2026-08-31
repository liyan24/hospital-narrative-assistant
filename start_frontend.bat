@echo off
chcp 65001 >nul
title 医院叙事生成助手-前端(8501)
cd /d %~dp0

echo [1/3] 检查 8501 端口占用...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501 " ^| findstr LISTENING') do (
    echo     端口 8501 被 PID=%%a 占用，正在结束该进程...
    taskkill /F /PID %%a >nul 2>&1
)

echo [2/3] 设置 API 代理目标（后端固定 8005，8000 是本机其他项目）
set VITE_FRONTEND_PORT=8501
set VITE_API_BASE_URL=http://localhost:8005

echo [3/3] 启动前端开发服务器: http://localhost:8501  (Ctrl+C 停止)
cd /d %~dp0frontend
npm run dev
pause
