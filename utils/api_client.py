"""
Streamlit 前端公共 API 客户端
被多页面共享，避免每个页面重复定义 api_get / api_post
"""
import requests
import streamlit as st
from config import settings

API_BASE = f"http://localhost:{settings.app_port}"


def api_get(path, timeout=30):
    try:
        resp = requests.get(f"{API_BASE}{path}", timeout=timeout)
        return resp.json()
    except Exception as e:
        st.error(f"API请求失败: {e}")
        return None


def api_post(path, params=None, json_data=None, timeout=120):
    try:
        resp = requests.post(
            f"{API_BASE}{path}", params=params, json=json_data, timeout=timeout
        )
        return resp.json()
    except Exception as e:
        st.error(f"API请求失败: {e}")
        return None
