"""
文档导出
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("📄 文档导出")

report_id = st.text_input(
    "报告ID", value=st.session_state.get("last_report_id", ""))
fmt = st.selectbox("导出格式", ["docx", "pdf"])

if st.button("📥 导出报告"):
    if not report_id:
        st.error("请输入报告ID")
    else:
        with st.spinner("文档生成中，请稍候..."):
            result = api_post("/api/document/report/export",
                              params={"report_id": report_id, "fmt": fmt})
            if result and result.get("file_path"):
                st.success("文档生成完成！")
                download_url = result.get("download_url", "")
                st.markdown(
                    f"[点击下载 {fmt.upper()} 文件]({API_BASE}{download_url})")
                # 尝试直接提供下载
                try:
                    file_resp = requests.get(f"{API_BASE}{download_url}")
                    if file_resp.status_code == 200:
                        st.download_button(
                            label=f"下载 {fmt.upper()}",
                            data=file_resp.content,
                            file_name=download_url.split("/")[-1],
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt == "docx" else "application/pdf",
                        )
                except Exception as e:
                    st.warning(f"直接下载失败: {e}")
            else:
                st.error("导出失败")
