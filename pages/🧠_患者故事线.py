"""
患者故事线
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("👤 个体患者故事线")
st.markdown("基于知识图谱生成某位患者的完整就诊故事线叙事")

patient_id = st.text_input("患者ID", value="4116-002-000000000000000000000021",
                           placeholder="例如: 4116-002-000000000000000000000021")

if st.button("📝 生成患者故事线", type="primary"):
    if not patient_id:
        st.error("请输入患者ID")
    else:
        with st.spinner("正在从知识图谱查询患者数据并生成叙事..."):
            result = api_get(
                f"/api/narrative/patient/storyline/{patient_id}")
            if result and result.get("narrative"):
                st.success(
                    f"患者故事线生成完成！共 {result.get('visit_count', 0)} 次就诊")
                st.markdown("---")
                st.markdown(result["narrative"])
            else:
                st.error(
                    f"生成失败: {result.get('detail', '患者不存在或数据为空') if result else '无响应'}")

st.divider()
st.info("""
**说明：**
- 患者ID可从原始Excel数据中的"患者ID"列获取
- 系统会查询该患者在知识图谱中的所有就诊记录、诊断、用药、检查、手术等信息
- 基于真实数据用LLM生成连贯的就诊故事线
""")
