"""
每周临床简报
"""
import streamlit as st
import requests
from utils.api_client import api_get, api_post, API_BASE
from utils.weekly_charts import render_weekly_charts

st.header("📅 每周临床简报")

# 自动加载最近一次生成的周简报ID
if "last_weekly_report_id" not in st.session_state:
    latest = api_get("/api/weekly/reports/latest")
    if latest and latest.get("status") == "ok" and latest.get("report_id"):
        st.session_state["last_weekly_report_id"] = latest["report_id"]

week_start = st.date_input("选择周开始日期（周一）", value=None)
week_start_str = week_start.strftime("%Y-%m-%d") if week_start else None

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🔍 运行周分析"):
        with st.spinner("周数据分析中..."):
            result = api_post("/api/weekly/analysis/run",
                              params={"week_start": week_start_str})
            if result and result.get("status") == "ok":
                st.success(f"周分析完成！周期: {result.get('week_start', '最新周')}")
                st.session_state["weekly_analysis_id"] = result.get(
                    "week_start", "latest_weekly")
                # 显示周分析结果
                analysis_id = st.session_state.get("weekly_analysis_id", "latest_weekly")
                analysis_result = api_get(f"/api/weekly/analysis/{analysis_id}")
                if analysis_result and analysis_result.get("status") == "ok":
                    st.session_state["weekly_analysis_data"] = analysis_result.get("data", {})
                else:
                    st.session_state["weekly_analysis_data"] = None
            else:
                st.error("周分析失败")
with col2:
    if st.button("🤖 生成周简报"):
        analysis_id = st.session_state.get(
            "weekly_analysis_id", "latest_weekly")
        with st.spinner("周简报生成中，请稍候..."):
            result = api_post("/api/weekly/report/generate",
                              params={"analysis_id": analysis_id})
            if result and result.get("status") == "ok":
                st.success(f"周简报生成完成！报告ID: {result.get('report_id')}")
                st.session_state["last_weekly_report_id"] = result.get(
                    "report_id")
            else:
                st.error("周简报生成失败")
with col3:
    if st.button("📥 导出周简报"):
        report_id = st.session_state.get("last_weekly_report_id", "")
        if report_id:
            with st.spinner("导出中..."):
                result = api_post(
                    "/api/weekly/report/export", params={"report_id": report_id, "fmt": "docx"})
                if result and result.get("file_path"):
                    st.success("周简报导出完成！")
                    download_url = result.get("download_url", "")
                    st.markdown(
                        f"[点击下载 Word 文件]({API_BASE}{download_url})")
                    try:
                        file_resp = requests.get(
                            f"{API_BASE}{download_url}")
                        if file_resp.status_code == 200:
                            st.download_button(
                                label="下载 Word",
                                data=file_resp.content,
                                file_name=download_url.split("/")[-1],
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            )
                    except Exception as e:
                        st.warning(f"直接下载失败: {e}")
                else:
                    st.error("导出失败")
        else:
            st.error("请先生成周简报")

# 显示周分析结果（如果存在）
if st.session_state.get("weekly_analysis_data"):
    st.divider()
    st.subheader("📊 周分析结果")
    data = st.session_state["weekly_analysis_data"]

    modules = [
        ("operation", "模块1：本周运营概况"),
        ("diseases", "模块2：病种分析"),
        ("exam_lab", "模块3：检查检验汇总"),
        ("treatment", "模块4：治疗动态"),
        ("quality", "模块5：质控指标"),
        ("focus_patients", "模块6：重点关注患者"),
        ("next_week", "模块7：下周预警"),
        ("summary", "总结"),
    ]

    for section_key, section_title in modules:
        with st.expander(section_title, expanded=False):
            section_data = data.get(section_key, {})
            if isinstance(section_data, dict):
                # 优先渲染图表
                if section_key in (
                    "operation", "diseases", "exam_lab",
                    "treatment", "quality", "focus_patients",
                ):
                    render_weekly_charts(section_key, section_data)

                # 再渲染剩余表格/文本
                for k, v in section_data.items():
                    if isinstance(v, list) and v and k not in (
                        "top5", "new_trends", "exam_types",
                        "lab_types", "ct_top5", "adverse_events",
                        "surgeries", "elderly", "long_stay",
                    ):
                        st.dataframe(v, use_container_width=True)
                    elif k != "week_range" and not isinstance(v, (list, dict)):
                        st.write(f"**{k}**: {v}")

# 显示周简报内容
weekly_report_id = st.text_input(
    "周简报报告ID", value=st.session_state.get("last_weekly_report_id", ""))
if weekly_report_id:
    report = api_get(f"/api/weekly/report/{weekly_report_id}")
    if report and report.get("status") == "ok":
        rpt = report["report"]
        data = rpt.get("data", {})
        texts = rpt.get("texts", {})

        st.subheader(
            f"{rpt.get('title', '周简报')} ({data.get('week_range', '')})")

        modules = [
            ("operation", "模块1：本周运营概况"),
            ("diseases", "模块2：病种分析"),
            ("exam_lab", "模块3：检查检验汇总"),
            ("treatment", "模块4：治疗动态"),
            ("quality", "模块5：质控指标"),
            ("focus_patients", "模块6：重点关注患者"),
            ("next_week", "模块7：下周预警"),
            ("summary", "总结"),
        ]

        for section_key, section_title in modules:
            with st.expander(section_title, expanded=True):
                text = texts.get(section_key, "")
                if text:
                    st.markdown(text)

                section_data = data.get(section_key, {})
                if isinstance(section_data, dict):
                    # 优先渲染图表
                    if section_key in (
                        "operation", "diseases", "exam_lab",
                        "treatment", "quality", "focus_patients",
                    ):
                        render_weekly_charts(section_key, section_data)

                    # 再渲染剩余表格/文本
                    for k, v in section_data.items():
                        if isinstance(v, list) and v and k not in (
                            "top5", "new_trends", "exam_types",
                            "lab_types", "ct_top5", "adverse_events",
                            "surgeries", "elderly", "long_stay",
                        ):
                            st.dataframe(v, use_container_width=True)
                        elif k != "week_range" and not isinstance(v, (list, dict)):
                            st.write(f"**{k}**: {v}")
    else:
        st.warning("周简报不存在或加载失败")
