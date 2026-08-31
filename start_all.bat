@echo off
chcp 65001 >nul
title 医院叙事生成助手-一键启动
cd /d %~dp0

echo 正在启动后端服务（新窗口，端口 8005）...
start "HNA-后端" cmd /k "%~dp0start_backend.bat"

echo 等待后端就绪...
timeout /t 8 /nobreak >nul

echo 正在启动前端服务（新窗口，端口 8501）...
start "HNA-前端" cmd /k "%~dp0start_frontend.bat"

echo.
echo ============================================
echo  后端 API : http://localhost:8005/docs
echo  前端页面 : http://localhost:8501
echo  注意：8000 端口保留给本机其他项目，勿占用
echo  关闭对应的命令行窗口即可停止服务
echo ============================================
pause
