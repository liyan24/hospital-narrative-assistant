"""
数据概览
"""
import streamlit as st
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post

st.header("📊 数据概览")

# 顶部操作区
if st.button("🔄 立即运行数据分析", type="primary"):
    with st.spinner("数据分析中，请稍候..."):
        result = api_post("/api/data/analysis/run", params={"analysis_id": "latest"})
        if result and result.get("status") == "ok":
            st.success("数据分析完成！")
            st.rerun()
        else:
            st.error("数据分析失败")

st.divider()

tab1, tab2 = st.tabs(["统计指标", "交互图表"])

with tab1:
    analysis = api_get("/api/data/analysis/latest")
    if analysis and analysis.get("status") == "ok":
        data = analysis["data"]
        st.subheader("数据来源")
        for key, val in data.get("data_sources", {}).items():
            st.write(
                f"- **{key}**: {val.get('file', '')} ({val.get('records', 0):,} 条记录)")

        st.subheader("基本统计")
        basic = data.get("basic_stats", {})
        st.write(f"总记录数: {basic.get('total_records', 0):,}")
        st.write(
            f"数据跨度: {basic.get('date_range', {}).get('start', '')} 至 {basic.get('date_range', {}).get('end', '')}")

        st.subheader("入院趋势")
        trend = data.get("admission_trend", {})
        annual = trend.get("annual", {})
        if annual.get("years"):
            df_data = {"年份": annual["years"], "入院人次": annual["counts"]}
            st.dataframe(df_data, use_container_width=True)

        st.subheader("患者特征")
        features = data.get("patient_features", {})
        age = features.get("age", {})
        st.write(
            f"平均年龄: {age.get('mean', '')}岁, 中位数: {age.get('median', '')}岁")
        st.write(f"年龄范围: {age.get('min', '')} - {age.get('max', '')}岁")
    else:
        st.info("暂无分析数据，请点击上方「立即运行数据分析」按钮")

with tab2:
    charts_data = api_get("/api/data/analysis/latest/charts")
    if charts_data and charts_data.get("status") == "ok":
        charts = charts_data.get("charts", {})

        # 布局：每行2个图表
        chart_items = list(charts.items())
        for i in range(0, len(chart_items), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j < len(chart_items):
                    chart_id, chart_cfg = chart_items[i + j]
                    with cols[j]:
                        st_echarts(options=chart_cfg,
                                   height="400px", key=chart_id)
    else:
        st.info("暂无图表数据，请先运行数据分析")
