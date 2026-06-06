"""
再入院分析
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("🔄 再入院患者时间线叙事")
st.markdown("识别多次就诊患者，分析再入院模式和纵向诊疗历程")

tab1, tab2 = st.tabs(["整体分析", "个体患者叙事"])

with tab1:
    if st.button("📈 生成再入院整体分析", type="primary"):
        with st.spinner("正在分析再入院数据..."):
            result = api_get("/api/narrative/readmission/summary")
            if result and result.get("narrative"):
                st.success("再入院整体分析完成")
                st.markdown("---")
                st.markdown(result["narrative"])
                # 显示统计
                stats = result.get("stats", {})
                if stats:
                    st.divider()
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("总患者数", stats.get("total_patients", 0))
                    with col2:
                        st.metric("再入院患者", stats.get(
                            "readmit_patients", 0))
                    with col3:
                        st.metric(
                            "再入院率", f"{stats.get('readmit_rate', 0)}%")
            else:
                st.error(
                    f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

with tab2:
    patient_id = st.text_input("患者ID", value="4116-002-000000000000000000000021",
                               placeholder="例如: 4116-002-000000000000000000000021", key="readmit_patient")
    if st.button("📝 生成患者纵向叙事", key="readmit_btn"):
        if not patient_id:
            st.error("请输入患者ID")
        else:
            with st.spinner("正在查询患者多次就诊记录..."):
                result = api_get(
                    f"/api/narrative/readmission/patient/{patient_id}")
                if result and result.get("narrative"):
                    st.success(
                        f"患者纵向叙事生成完成！共 {result.get('visit_count', 0)} 次就诊")
                    st.markdown("---")
                    st.markdown(result["narrative"])
                else:
                    st.error(
                        f"生成失败: {result.get('detail', '患者不存在或仅就诊1次') if result else '无响应'}")

st.divider()
st.info("""
**说明：**
- **整体分析**：统计科室再入院率、间隔分布、高发疾病，识别管理改进点
- **个体叙事**：追踪特定患者多次就诊的完整历程，分析病情演变和治疗调整
- 再入院定义为同一患者有2次及以上就诊记录
""")
