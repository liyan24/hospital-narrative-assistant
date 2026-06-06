"""
中医特色
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("🌿 中医特色叙事增强")
st.markdown("基于知识图谱分析中医证型-用药关联、中西医结合对比、证型分布趋势")

tab1, tab2, tab3 = st.tabs([
    "证型-用药关联",
    "中西医结合对比",
    "证型分布趋势",
])

with tab1:
    st.subheader("证型-用药关联分析")
    input_mode = st.radio(
        "输入模式", ["中医证型", "西医疾病", "全局概览"], horizontal=True)

    if input_mode == "中医证型":
        syndrome_name = st.text_input(
            "证型名称", value="痰瘀互结证", placeholder="例如: 痰瘀互结证")
        western_disease = None
    elif input_mode == "西医疾病":
        western_disease = st.text_input(
            "西医疾病名称", value="肺恶性肿瘤", placeholder="例如: 肺恶性肿瘤")
        syndrome_name = None
    else:
        syndrome_name = None
        western_disease = None

    if st.button("🌿 生成证型用药叙事", type="primary"):
        with st.spinner("正在分析中医证型与用药关联..."):
            params = {}
            if syndrome_name:
                params["syndrome_name"] = syndrome_name
            if western_disease:
                params["western_disease"] = western_disease

            if params:
                path = "/api/narrative/tcm/syndrome-drug?" + \
                    "&".join(
                        [f"{k}={requests.utils.quote(v)}" for k, v in params.items()])
            else:
                path = "/api/narrative/tcm/syndrome-drug"

            result = api_get(path)
            if result and result.get("narrative"):
                st.success(
                    f"证型用药叙事生成完成 | 分析对象: {result.get('target', '')}")
                st.markdown("---")
                st.markdown(result["narrative"])

                # 显示统计表格
                data = result.get("data", {})
                if data.get("syndromes"):
                    with st.expander("证型分布"):
                        st.dataframe(data["syndromes"],
                                     use_container_width=True)
                if data.get("top_drugs"):
                    with st.expander("Top药品"):
                        st.dataframe(data["top_drugs"],
                                     use_container_width=True)
                if data.get("tcm_drugs"):
                    with st.expander("常用中药/中成药"):
                        st.dataframe(data["tcm_drugs"],
                                     use_container_width=True)
                if data.get("common_pairs"):
                    with st.expander("常见药品组合"):
                        st.dataframe(data["common_pairs"],
                                     use_container_width=True)
            else:
                st.error(
                    f"生成失败: {result.get('detail', '未知错误') if result else '无响应'}")

with tab2:
    st.subheader("中西医结合对比分析")
    western_disease = st.text_input(
        "西医疾病名称（留空分析全局）", value="肺恶性肿瘤", placeholder="例如: 肺恶性肿瘤", key="tcm_cmp_disease")

    if st.button("⚖️ 生成中西医结合对比叙事", type="primary"):
        with st.spinner("正在对比中西医结合治疗效果..."):
            if western_disease.strip():
                path = f"/api/narrative/tcm/integrated-comparison?western_disease={requests.utils.quote(western_disease.strip())}"
            else:
                path = "/api/narrative/tcm/integrated-comparison"

            result = api_get(path)
            if result and result.get("narrative"):
                st.success(
                    f"中西医结合对比叙事生成完成 | 分析对象: {result.get('target', '')}")
                st.markdown("---")
                st.markdown(result["narrative"])

                data = result.get("data", {})
                if data.get("comparison"):
                    with st.expander("对比数据"):
                        cmp_data = []
                        for k, v in data["comparison"].items():
                            label = "中西医结合组" if k == "integrated" else "纯西医组"
                            cmp_data.append({"组别": label, **v})
                        st.dataframe(cmp_data, use_container_width=True)
            else:
                st.error(
                    f"生成失败: {result.get('detail', '未知错误') if result else '无响应'}")

with tab3:
    st.subheader("证型分布趋势分析")
    trend_mode = st.radio(
        "分析维度", ["全局", "特定证型", "特定西医疾病"], horizontal=True, key="tcm_trend_mode")

    if trend_mode == "特定证型":
        syndrome_name = st.text_input(
            "证型名称", value="痰瘀互结证", placeholder="例如: 痰瘀互结证", key="tcm_trend_syndrome")
        western_disease = None
    elif trend_mode == "特定西医疾病":
        western_disease = st.text_input(
            "西医疾病名称", value="肺恶性肿瘤", placeholder="例如: 肺恶性肿瘤", key="tcm_trend_disease")
        syndrome_name = None
    else:
        syndrome_name = None
        western_disease = None

    if st.button("📈 生成证型趋势叙事", type="primary"):
        with st.spinner("正在分析证型分布趋势..."):
            params = {}
            if syndrome_name:
                params["syndrome_name"] = syndrome_name
            if western_disease:
                params["western_disease"] = western_disease

            if params:
                path = "/api/narrative/tcm/trend?" + \
                    "&".join(
                        [f"{k}={requests.utils.quote(v)}" for k, v in params.items()])
            else:
                path = "/api/narrative/tcm/trend"

            result = api_get(path)
            if result and result.get("narrative"):
                st.success(
                    f"证型趋势叙事生成完成 | 分析对象: {result.get('target', '')}")
                st.markdown("---")
                st.markdown(result["narrative"])

                data = result.get("data", {})
                if data.get("year_trend"):
                    with st.expander("年度趋势"):
                        st.dataframe(data["year_trend"],
                                     use_container_width=True)
                        # ECharts line chart
                        years = [x["year"] for x in data["year_trend"]]
                        counts = [x["count"] for x in data["year_trend"]]
                        if years:
                            st_echarts(options={
                                "xAxis": {"type": "category", "data": years},
                                "yAxis": {"type": "value"},
                                "series": [{"type": "line", "data": counts, "smooth": True}],
                            }, height="300px", key="tcm_year_trend")
            else:
                st.error(
                    f"生成失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()
st.info("""
**功能说明：**
- **证型-用药关联**：分析特定中医证型或西医疾病下的常用中药/中成药、西药及联合用药模式
- **中西医结合对比**：对比纯西医治疗与中西医结合治疗在住院天数等指标上的差异
- **证型分布趋势**：分析中医证型就诊的年度/季度变化趋势
""")

