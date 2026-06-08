"""
科室运营简报生成
"""
import streamlit as st
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post

st.header("📄 科室运营简报生成")

# 自动加载最近一次生成的科室运营简报ID
if "last_report_id" not in st.session_state:
    latest = api_get("/api/narrative/reports/latest")
    if latest and latest.get("status") == "ok" and latest.get("report_id"):
        st.session_state["last_report_id"] = latest["report_id"]

col1, col2 = st.columns([3, 1])
with col1:
    report_id = st.text_input(
        "报告ID（留空则生成新报告）", value=st.session_state.get("last_report_id", ""))
with col2:
    st.write("")
    st.write("")
    if st.button("🚀 生成新报告", type="primary", use_container_width=True):
        with st.spinner("报告生成中，请稍候..."):
            result = api_post("/api/narrative/report/generate",
                              params={"analysis_id": "latest"})
            if result and result.get("status") == "ok":
                st.success("报告生成完成！")
                st.session_state["last_report_id"] = result.get("report_id")
                st.rerun()
            else:
                st.error("报告生成失败")

if report_id:
    report = api_get(f"/api/narrative/report/{report_id}")
    if report and report.get("status") == "ok":
        rpt = report["report"]
        texts = rpt.get("texts", {})
        charts = rpt.get("charts", {})

        st.subheader(rpt.get("title", "数据分析报告"))
        st.caption(f"生成时间: {rpt.get('generated_at', '')}")

        # 使用utils.report_layout进行文本与图表穿插展示
        from utils.report_layout import interleave_text_with_charts

        section_order = [
            ("basic", "一、基本统计"),
            ("admission_trend", "二、入院趋势分析"),
            ("patient_features", "三、患者特征分析"),
            ("hospitalization_days", "四、住院天数分析"),
            ("disease_types", "五、疾病类型提取分析"),
            ("readmission", "六、再入院分析"),
            ("discharge", "七、出院情况分析"),
            ("exam", "检查数据分析"),
            ("lab", "检验数据分析"),
            ("summary", "数据质量评估与总结"),
        ]

        for section_key, section_title in section_order:
            with st.expander(section_title, expanded=True):
                text = texts.get(section_key, "")
                blocks = interleave_text_with_charts(
                    section_key, text, charts)
                for block in blocks:
                    if block["type"] == "text":
                        st.markdown(block["content"])
                    elif block["type"] == "chart":
                        ck = block["chart_id"]
                        if ck in charts:
                            st_echarts(
                                options=charts[ck], height="400px", key=f"{report_id}_{ck}")
    else:
        st.warning("报告不存在或加载失败")
