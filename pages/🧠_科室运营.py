"""
科室运营
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("📈 科室运营深度叙事")
st.markdown("基于知识图谱的多维度运营分析，支持周期对比和趋势洞察")

col1, col2 = st.columns(2)
with col1:
    period = st.selectbox(
        "分析周期",
        [
            ("latest_year", "最近完整年度"),
            ("latest_quarter", "最近完整季度"),
            ("latest_month", "最近完整月份"),
            ("y2024", "2024年全年"),
            ("y2023", "2023年全年"),
        ],
        format_func=lambda x: x[1],
    )[0]
with col2:
    compare = st.checkbox("对比上一周期", value=True)

if st.button("📊 生成运营分析报告", type="primary"):
    with st.spinner("正在从知识图谱提取运营数据并生成分析叙事，请稍候..."):
        path = f"/api/narrative/department-operation?period={period}&compare={str(compare).lower()}"
        result = api_get(path)

        if result and result.get("narrative"):
            current = result.get("current_period", {})
            previous = result.get("previous_period")
            current_metrics = result.get("current_metrics", {})
            changes = result.get("changes", {})

            st.success(f"运营分析完成 | 周期: {current.get('label', '')}")

            # 总体指标卡片
            st.markdown("---")
            st.subheader("📊 核心运营指标")
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            with c1:
                val = current_metrics.get("visit_count", 0)
                delta = changes.get("visit_count_change")
                st.metric(
                    "就诊人次", f"{val:,}", f"{delta:+.1f}%" if delta is not None else None)
            with c2:
                val = current_metrics.get("patient_count", 0)
                delta = changes.get("patient_count_change")
                st.metric(
                    "患者人数", f"{val:,}", f"{delta:+.1f}%" if delta is not None else None)
            with c3:
                val = current_metrics.get("avg_los", 0)
                delta = changes.get("avg_los_change")
                st.metric(
                    "平均住院", f"{val}天", f"{delta:+.1f}%" if delta is not None else None)
            with c4:
                val = current_metrics.get("surgery_rate", 0)
                delta = changes.get("surgery_rate_change")
                st.metric(
                    "手术率", f"{val}%", f"{delta:+.1f}%" if delta is not None else None)
            with c5:
                val = current_metrics.get("readmit_rate", 0)
                delta = changes.get("readmit_rate_change")
                st.metric(
                    "再入院率", f"{val}%", f"{delta:+.1f}%" if delta is not None else None)
            with c6:
                val = current_metrics.get("multi_disease_rate", 0)
                delta = changes.get("multi_disease_rate_change")
                st.metric(
                    "多病共存率", f"{val}%", f"{delta:+.1f}%" if delta is not None else None)

            # 叙事
            st.markdown("---")
            st.subheader("📝 运营分析叙事")
            st.markdown(result["narrative"])

            # 详细数据
            st.markdown("---")
            st.subheader("🔎 详细运营数据")

            dcol1, dcol2 = st.columns(2)
            with dcol1:
                if current_metrics.get("top_diseases"):
                    with st.expander("Top 10 西医疾病", expanded=True):
                        st.dataframe(
                            current_metrics["top_diseases"], use_container_width=True)

                if current_metrics.get("top_drugs"):
                    with st.expander("Top 10 药品"):
                        st.dataframe(
                            current_metrics["top_drugs"], use_container_width=True)

                if current_metrics.get("top_comorbidities"):
                    with st.expander("Top 10 合并症对"):
                        st.dataframe(
                            current_metrics["top_comorbidities"], use_container_width=True)

            with dcol2:
                if current_metrics.get("top_tcm_diseases"):
                    with st.expander("Top 5 中医证型/病名", expanded=True):
                        st.dataframe(
                            current_metrics["top_tcm_diseases"], use_container_width=True)

                if current_metrics.get("top_exams"):
                    with st.expander("Top 5 检查"):
                        st.dataframe(
                            current_metrics["top_exams"], use_container_width=True)

                if current_metrics.get("top_surgeries"):
                    with st.expander("Top 5 手术"):
                        st.dataframe(
                            current_metrics["top_surgeries"], use_container_width=True)

            # 中西医结合
            integrated = current_metrics.get("integrated", {})
            if integrated.get("total", 0) > 0:
                with st.expander("中西医结合运营"):
                    total = integrated["total"]
                    ig_data = [
                        {"类型": "中西医结合", "人次": integrated.get(
                            "integrated", 0), "占比": f"{round(integrated.get('integrated', 0)/total*100, 1)}%"},
                        {"类型": "纯西医", "人次": integrated.get(
                            "western_only", 0), "占比": f"{round(integrated.get('western_only', 0)/total*100, 1)}%"},
                        {"类型": "纯中医", "人次": integrated.get(
                            "tcm_only", 0), "占比": f"{round(integrated.get('tcm_only', 0)/total*100, 1)}%"},
                    ]
                    st.dataframe(ig_data, use_container_width=True)
        else:
            st.error(
                f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()
st.info("""
**功能说明：**
- 基于知识图谱提取科室运营核心指标（患者量、病种、用药、检查、手术、再入院等）
- 支持最近年度/季度/月份及固定年度分析
- 自动对比上一周期，计算环比变化
- 融入中西医结合运营特色指标
- 多病共存率反映患者病情复杂程度
""")

