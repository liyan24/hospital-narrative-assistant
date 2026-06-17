# 一键启动脚本说明

本目录包含医院叙事生成助手的跨平台一键启动脚本，支持 Windows 和 Linux 系统。

## 文件清单

| 文件 | 适用系统 | 说明 |
|------|----------|------|
| `start_windows.bat` | Windows | Windows 服务管理批处理脚本 |
| `start_linux.sh` | Linux / macOS | Linux/macOS 服务管理 Shell 脚本 |

## 功能特性

- **自动读取端口配置**：从项目根目录 `.env` 文件中读取 `APP_PORT` 和 `FRONTEND_PORT`
- **自动激活虚拟环境**：优先使用 `.venv` 虚拟环境
- **端口占用检测**：启动前检测端口是否被占用，避免冲突
- **后台运行**：启动后窗口可关闭，服务继续运行
- **一键停止**：通过端口或 PID 查找并停止服务
- **状态查看**：实时查看前后端服务运行状态
- **自动创建日志目录**：日志保存于 `logs/backend.log` 和 `logs/frontend.log`

## Windows 使用说明

### 1. 直接双击启动

双击 `scripts/start_windows.bat`，默认执行 `start` 命令启动前后端服务。

### 2. 命令行使用

```cmd
cd scripts

:: 启动服务（默认）
start_windows.bat

:: 或显式指定命令
start_windows.bat start

:: 停止服务
start_windows.bat stop

:: 查看状态
start_windows.bat status

:: 重启服务
start_windows.bat restart

:: 查看帮助
start_windows.bat help
```

### 3. 注意事项

- 脚本会自动查找项目根目录的 `.venv\Scripts\activate.bat` 激活虚拟环境
- 停止服务时可能需要管理员权限（特别是占用端口的进程由其他用户启动时）
- 日志文件位于 `logs\backend.log` 和 `logs\frontend.log`

## Linux / macOS 使用说明

### 1. 赋予执行权限（首次使用）

```bash
cd scripts
chmod +x start_linux.sh
```

### 2. 启动服务

```bash
./start_linux.sh
```

### 3. 其他命令

```bash
./start_linux.sh start    # 启动服务（默认）
./start_linux.sh stop     # 停止服务
./start_linux.sh status   # 查看状态
./start_linux.sh restart  # 重启服务
./start_linux.sh help     # 查看帮助
```

### 4. 后台运行

由于脚本内部使用 `nohup &` 启动服务，执行 `./start_linux.sh` 后可以直接关闭终端，服务会继续运行。

### 5. 注意事项

- 脚本会自动查找项目根目录的 `.venv/bin/activate` 激活虚拟环境
- 停止服务时会优先使用 PID 文件，如果失败会通过端口查找进程
- 日志文件位于 `logs/backend.log` 和 `logs/frontend.log`

## 默认访问地址

如果 `.env` 中使用默认端口：

- 后端 API: http://localhost:8005
- 前端页面: http://localhost:8501
- API 文档: http://localhost:8005/docs

## 故障排查

### 服务启动失败

1. 检查端口是否被占用：`start_windows.bat status` 或 `./start_linux.sh status`
2. 查看日志文件：`logs/backend.log` 和 `logs/frontend.log`
3. 确认 `.env` 配置正确
4. 确认虚拟环境已安装依赖：`pip install -r requirements.txt`

### 停止服务失败

- Windows：尝试以管理员身份运行 `start_windows.bat stop`
- Linux：尝试使用 `sudo` 执行 `./start_linux.sh stop`

### 端口被占用

1. 先执行停止命令
2. 或修改 `.env` 中的 `APP_PORT` / `FRONTEND_PORT` 为其他端口
3. 重新执行启动命令
