"""
诊疗路径
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("🛤️ 诊疗路径模式叙事")
st.markdown("基于知识图谱挖掘某疾病的典型诊疗路径，生成科室诊疗规范叙事")

disease_name = st.text_input("疾病名称", placeholder="例如: 肺恶性肿瘤")

if st.button("📋 生成诊疗路径叙事", type="primary"):
    if not disease_name:
        st.error("请输入疾病名称")
    else:
        with st.spinner("正在从知识图谱分析诊疗路径..."):
            result = api_get(f"/api/narrative/pathway/{disease_name}")
            if result and result.get("narrative"):
                st.success(
                    f"诊疗路径叙事生成完成！疾病: {result.get('disease_name', '')}")
                st.markdown("---")
                st.markdown(result["narrative"])
            else:
                st.error(
                    f"生成失败: {result.get('detail', '未找到该疾病的诊疗数据') if result else '无响应'}")

st.divider()
st.info("""
**说明：**
- 输入疾病名称（如"肺恶性肿瘤"、"高血压"、"痰瘀互结证"等）
- 系统会分析该疾病在本科室的：常用药品、常规检查、常见手术、合并症分布、住院天数等
- 用LLM生成专业的诊疗路径模式叙事
""")
