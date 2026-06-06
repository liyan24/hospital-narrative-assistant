"""
用药模式
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("💊 用药模式与合理性叙事")
st.markdown("基于知识图谱分析药品共现网络、常用药组合和潜在问题")

disease_name = st.text_input("疾病名称（留空分析全局模式）", placeholder="例如: 肺恶性肿瘤")

if st.button("📋 生成用药分析", type="primary"):
    with st.spinner("正在分析用药模式..."):
        if disease_name:
            result = api_get(
                f"/api/narrative/drug-pattern/{requests.utils.quote(disease_name)}")
        else:
            result = api_get("/api/narrative/drug-pattern")
        if result and result.get("narrative"):
            target = result.get("disease_name")
            if target:
                st.success(f"疾病 '{target}' 的用药分析完成")
            else:
                st.success("全局用药模式分析完成")
            st.markdown("---")
            st.markdown(result["narrative"])
        else:
            st.error(
                f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()
st.info("""
**说明：**
- 输入疾病名称：分析该疾病的常用药组合、中西医结合用药特点
- 留空：分析全科室最常用的药品和组合对
- 自动识别潜在的用药问题（如重复用药、相互作用风险）
""")
