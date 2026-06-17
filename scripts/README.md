# 一键启动脚本说明

本目录包含医院叙事生成助手的跨平台一键启动脚本，支持 Windows 和 Linux/macOS 系统。

## 文件清单

| 文件 | 适用系统 | 说明 |
|------|----------|------|
| `start_windows.bat` | Windows (CMD) | 英文版批处理脚本，双击即可运行，最稳定兼容 |
| `start_windows.ps1` | Windows (PowerShell) | 功能完整的中文版 PowerShell 脚本 |
| `start_linux.sh` | Linux / macOS | Linux/macOS 服务管理 Shell 脚本 |

## 推荐用法

### Windows

**推荐方案：PowerShell 脚本（功能完整、中文输出）**

1. 打开 PowerShell
2. 切换到项目目录
3. 执行：

```powershell
# 首次执行需要设置执行策略（仅需一次）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 启动服务
.\scripts\start_windows.ps1

# 停止服务
.\scripts\start_windows.ps1 stop

# 查看状态
.\scripts\start_windows.ps1 status

# 重启服务
.\scripts\start_windows.ps1 restart
```

**备选方案：批处理脚本（无需 PowerShell 配置）**

直接双击 `scripts/start_windows.bat`，或在 CMD 中执行：

```cmd
cd scripts

:: 启动服务（默认）
start_windows.bat

:: 停止服务
start_windows.bat stop

:: 查看状态
start_windows.bat status

:: 重启服务
start_windows.bat restart
```

> 注意：`start_windows.bat` 使用英文输出，以避免部分 Windows 系统 CMD 中文显示乱码问题。如需中文输出，请使用 PowerShell 脚本。

### Linux / macOS

```bash
cd scripts
chmod +x start_linux.sh

./start_linux.sh          # 启动
./start_linux.sh stop     # 停止
./start_linux.sh status   # 状态
./start_linux.sh restart  # 重启
```

## 功能特性

- **自动读取端口配置**：从项目根目录 `.env` 读取 `APP_PORT` 和 `FRONTEND_PORT`
- **自动激活虚拟环境**：优先使用 `.venv`
- **端口占用检测**：启动前检查端口，避免冲突
- **后台运行**：服务在关闭终端后继续运行
- **PID 文件管理**：精确控制启动的进程
- **兜底清理**：通过端口查找并停止残留进程
- **日志输出**：`logs/backend.log` 和 `logs/frontend.log`

## 默认访问地址

- 后端 API: http://localhost:8005
- 前端页面: http://localhost:8501
- API 文档: http://localhost:8005/docs

## 故障排查

### 服务启动失败

1. 查看状态：`start_windows.ps1 status` 或 `./start_linux.sh status`
2. 查看日志：`logs/backend.log`、`logs/frontend.log`
3. 检查 `.env` 端口配置
4. 确认依赖已安装：`pip install -r requirements.txt`

### Windows PowerShell 执行策略阻止

如果看到 "cannot be loaded because running scripts is disabled"，执行：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 端口被占用

1. 执行停止命令
2. 或修改 `.env` 中的端口
3. 重新启动
