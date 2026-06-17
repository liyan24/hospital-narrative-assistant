#!/bin/bash

# ============================================================
# 医院叙事生成助手 - Linux 一键启动脚本
# 用法: ./start_linux.sh [start|stop|status|restart|help]
# 默认操作: start
# ============================================================

set -e

# 获取脚本所在目录和项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 默认端口
APP_PORT=8005
FRONTEND_PORT=8501

# 读取 .env 文件中的端口配置
if [ -f "${PROJECT_ROOT}/.env" ]; then
    while IFS='=' read -r key val; do
        # 去除前后空格
        key="$(echo "${key}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        val="$(echo "${val}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        if [ "${key}" = "APP_PORT" ]; then
            APP_PORT="${val}"
        elif [ "${key}" = "FRONTEND_PORT" ]; then
            FRONTEND_PORT="${val}"
        fi
    done < "${PROJECT_ROOT}/.env"
fi

BACKEND_URL="http://localhost:${APP_PORT}"
FRONTEND_URL="http://localhost:${FRONTEND_PORT}"
BACKEND_LOG="${PROJECT_ROOT}/logs/backend.log"
FRONTEND_LOG="${PROJECT_ROOT}/logs/frontend.log"
BACKEND_PID_FILE="${PROJECT_ROOT}/.backend.pid"
FRONTEND_PID_FILE="${PROJECT_ROOT}/.frontend.pid"

# 创建日志目录
mkdir -p "${PROJECT_ROOT}/logs"

# 激活虚拟环境
if [ -f "${PROJECT_ROOT}/.venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${PROJECT_ROOT}/.venv/bin/activate"
else
    echo "[警告] 未找到 .venv 虚拟环境，将使用系统 Python"
fi

# ============================================================
# 工具函数：检查端口是否在监听
# ============================================================
is_port_listening() {
    local port="$1"
    if command -v ss >/dev/null 2>&1; then
        ss -tuln | grep -q ":${port} "
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln | grep -q ":${port} "
    else
        # 最后的兜底方案
        (echo >"/dev/tcp/localhost/${port}") >/dev/null 2>&1
    fi
}

# ============================================================
# 工具函数：通过端口停止进程
# ============================================================
kill_by_port() {
    local port="$1"
    local name="$2"
    local pids

    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -t -i:"${port}" 2>/dev/null || true)
    elif command -v ss >/dev/null 2>&1; then
        pids=$(ss -tulnp | grep ":${port} " | grep -oP 'pid=\K[0-9]+' | sort -u || true)
    elif command -v fuser >/dev/null 2>&1; then
        pids=$(fuser "${port}/tcp" 2>/dev/null || true)
    fi

    if [ -n "${pids}" ]; then
        for pid in ${pids}; do
            echo "[停止] ${name} 服务残留进程 PID: ${pid}"
            kill "${pid}" 2>/dev/null || true
            sleep 1
            if kill -0 "${pid}" 2>/dev/null; then
                kill -9 "${pid}" 2>/dev/null || true
            fi
        done
    fi
}

# ============================================================
# 启动服务
# ============================================================
start_services() {
    echo ""
    echo "============================================================"
    echo " 医院叙事生成助手 - 启动服务"
    echo "============================================================"
    echo " 后端地址: ${BACKEND_URL}"
    echo " 前端地址: ${FRONTEND_URL}"
    echo " 日志目录: ${PROJECT_ROOT}/logs"
    echo "============================================================"
    echo ""

    # 检查后端是否已在运行
    if is_port_listening "${APP_PORT}"; then
        echo "[提示] 后端服务已在运行: ${BACKEND_URL}"
    else
        echo "[1/2] 正在启动后端 API ..."
        nohup python "${PROJECT_ROOT}/main.py" > "${BACKEND_LOG}" 2>&1 &
        echo $! > "${BACKEND_PID_FILE}"
        sleep 3
        if is_port_listening "${APP_PORT}"; then
            echo "      后端启动成功 (PID: $(cat "${BACKEND_PID_FILE}"))"
        else
            echo "      [警告] 后端可能未正常启动，请查看日志: ${BACKEND_LOG}"
        fi
    fi

    # 检查前端是否已在运行
    if is_port_listening "${FRONTEND_PORT}"; then
        echo "[提示] 前端服务已在运行: ${FRONTEND_URL}"
    else
        echo "[2/2] 正在启动前端 Streamlit ..."
        nohup streamlit run "${PROJECT_ROOT}/streamlit_app.py" --server.port "${FRONTEND_PORT}" > "${FRONTEND_LOG}" 2>&1 &
        echo $! > "${FRONTEND_PID_FILE}"
        sleep 5
        if is_port_listening "${FRONTEND_PORT}"; then
            echo "      前端启动成功 (PID: $(cat "${FRONTEND_PID_FILE}"))"
        else
            echo "      [警告] 前端可能未正常启动，请查看日志: ${FRONTEND_LOG}"
        fi
    fi

    echo ""
    echo "============================================================"
    echo " 服务启动完成"
    echo "============================================================"
    echo " 后端 API:    ${BACKEND_URL}"
    echo " 前端页面:    ${FRONTEND_URL}"
    echo " API 文档:    ${BACKEND_URL}/docs"
    echo " 日志文件:    ${PROJECT_ROOT}/logs"
    echo "============================================================"
    echo ""
    echo " 提示: ./start_linux.sh stop   停止服务"
    echo "       ./start_linux.sh status 查看状态"
}

# ============================================================
# 停止服务
# ============================================================
stop_services() {
    echo ""
    echo "============================================================"
    echo " 医院叙事生成助手 - 停止服务"
    echo "============================================================"
    echo ""

    # 停止后端
    if [ -f "${BACKEND_PID_FILE}" ]; then
        PID=$(cat "${BACKEND_PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            echo "[停止] 后端服务 PID: ${PID}"
            kill "${PID}" 2>/dev/null || true
            sleep 1
            if kill -0 "${PID}" 2>/dev/null; then
                echo "       强制停止后端服务"
                kill -9 "${PID}" 2>/dev/null || true
            fi
        fi
        rm -f "${BACKEND_PID_FILE}"
    fi

    # 停止前端
    if [ -f "${FRONTEND_PID_FILE}" ]; then
        PID=$(cat "${FRONTEND_PID_FILE}")
        if kill -0 "${PID}" 2>/dev/null; then
            echo "[停止] 前端服务 PID: ${PID}"
            kill "${PID}" 2>/dev/null || true
            sleep 1
            if kill -0 "${PID}" 2>/dev/null; then
                echo "       强制停止前端服务"
                kill -9 "${PID}" 2>/dev/null || true
            fi
        fi
        rm -f "${FRONTEND_PID_FILE}"
    fi

    # 兜底：通过端口清理残留进程
    kill_by_port "${APP_PORT}" "后端"
    kill_by_port "${FRONTEND_PORT}" "前端"

    echo ""
    echo "[完成] 所有服务已停止"
}

# ============================================================
# 查看状态
# ============================================================
show_status() {
    echo ""
    echo "============================================================"
    echo " 医院叙事生成助手 - 服务状态"
    echo "============================================================"
    echo ""

    BACKEND_RUNNING=false
    FRONTEND_RUNNING=false

    if is_port_listening "${APP_PORT}"; then
        echo "[后端] 运行中 - ${BACKEND_URL}"
        BACKEND_RUNNING=true
    else
        echo "[后端] 未运行"
    fi

    if is_port_listening "${FRONTEND_PORT}"; then
        echo "[前端] 运行中 - ${FRONTEND_URL}"
        FRONTEND_RUNNING=true
    else
        echo "[前端] 未运行"
    fi

    echo ""
    if [ "${BACKEND_RUNNING}" = "true" ] && [ "${FRONTEND_RUNNING}" = "true" ]; then
        echo "[状态] 所有服务正常运行"
    else
        echo "[状态] 部分服务未运行"
    fi
}

# ============================================================
# 帮助信息
# ============================================================
show_help() {
    echo ""
    echo "============================================================"
    echo " 医院叙事生成助手 - Linux 服务管理脚本"
    echo "============================================================"
    echo ""
    echo " 用法: ./start_linux.sh [命令]"
    echo ""
    echo " 可用命令:"
    echo "   start    启动前后端服务（默认）"
    echo "   stop     停止前后端服务"
    echo "   status   查看服务运行状态"
    echo "   restart  重启前后端服务"
    echo "   help     显示帮助信息"
    echo ""
    echo " 示例:"
    echo "   ./start_linux.sh"
    echo "   ./start_linux.sh start"
    echo "   ./start_linux.sh stop"
    echo "   ./start_linux.sh status"
    echo ""
}

# ============================================================
# 主程序入口
# ============================================================
COMMAND="${1:-start}"

case "${COMMAND}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    status)
        show_status
        ;;
    restart)
        stop_services
        sleep 2
        start_services
        ;;
    help|-h|--help)
        show_help
        ;;
    *)
        echo "[错误] 未知命令: ${COMMAND}"
        show_help
        exit 1
        ;;
esac
