"""
文档导出
支持导出：科室运营简报、周简报
"""
import streamlit as st
import requests
from utils.api_client import api_get, api_post, API_BASE

st.header("📥 文档导出")

# ==================== 科室运营简报导出 ====================
st.subheader("📄 科室运营简报导出")

if "last_report_id" not in st.session_state:
    latest = api_get("/api/narrative/reports/latest")
    if latest and latest.get("status") == "ok" and latest.get("report_id"):
        st.session_state["last_report_id"] = latest["report_id"]

col1, col2 = st.columns([3, 1])
with col1:
    report_id = st.text_input(
        "科室运营简报报告ID",
        value=st.session_state.get("last_report_id", ""),
        key="dept_report_id",
    )
with col2:
    fmt_dept = st.selectbox("导出格式", ["docx", "pdf"], key="dept_fmt")

if st.button("📥 导出门诊运营简报"):
    if not report_id:
        st.error("请输入科室运营简报报告ID")
    else:
        with st.spinner("文档生成中，请稍候..."):
            result = api_post("/api/document/report/export",
                              params={"report_id": report_id, "fmt": fmt_dept})
            if result and result.get("file_path"):
                st.success("科室运营简报导出完成！")
                download_url = result.get("download_url", "")
                st.markdown(
                    f"[点击下载 {fmt_dept.upper()} 文件]({API_BASE}{download_url})")
                try:
                    file_resp = requests.get(f"{API_BASE}{download_url}")
                    if file_resp.status_code == 200:
                        st.download_button(
                            label=f"下载 {fmt_dept.upper()}",
                            data=file_resp.content,
                            file_name=download_url.split("/")[-1],
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt_dept == "docx" else "application/pdf",
                            key="dept_download",
                        )
                except Exception as e:
                    st.warning(f"直接下载失败: {e}")
            else:
                st.error("导出失败")

st.divider()

# ==================== 周简报导出 ====================
st.subheader("📅 周简报导出")

if "last_weekly_report_id" not in st.session_state:
    latest = api_get("/api/weekly/reports/latest")
    if latest and latest.get("status") == "ok" and latest.get("report_id"):
        st.session_state["last_weekly_report_id"] = latest["report_id"]

col3, col4 = st.columns([3, 1])
with col3:
    weekly_report_id = st.text_input(
        "周简报报告ID",
        value=st.session_state.get("last_weekly_report_id", ""),
        key="weekly_report_id",
    )
with col4:
    fmt_weekly = st.selectbox("导出格式", ["docx", "pdf"], key="weekly_fmt")

if st.button("📥 导出周简报"):
    if not weekly_report_id:
        st.error("请输入周简报报告ID")
    else:
        with st.spinner("文档生成中，请稍候..."):
            result = api_post("/api/weekly/report/export",
                              params={"report_id": weekly_report_id, "fmt": fmt_weekly})
            if result and result.get("file_path"):
                st.success("周简报导出完成！")
                download_url = result.get("download_url", "")
                st.markdown(
                    f"[点击下载 {fmt_weekly.upper()} 文件]({API_BASE}{download_url})")
                try:
                    file_resp = requests.get(f"{API_BASE}{download_url}")
                    if file_resp.status_code == 200:
                        st.download_button(
                            label=f"下载 {fmt_weekly.upper()}",
                            data=file_resp.content,
                            file_name=download_url.split("/")[-1],
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt_weekly == "docx" else "application/pdf",
                            key="weekly_download",
                        )
                except Exception as e:
                    st.warning(f"直接下载失败: {e}")
            else:
                st.error("导出失败")
