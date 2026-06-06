"""
合并症分析
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("🔗 疾病共现网络叙事")
st.markdown("基于知识图谱分析合并症组合，发现疾病之间的关联模式")

disease_name = st.text_input("疾病名称（留空分析全局模式）", placeholder="例如: 肺恶性肿瘤")

if st.button("📊 生成共现分析", type="primary"):
    with st.spinner("正在分析疾病共现网络..."):
        if disease_name:
            result = api_get(
                f"/api/narrative/comorbidity/{requests.utils.quote(disease_name)}")
        else:
            result = api_get("/api/narrative/comorbidity")
        if result and result.get("narrative"):
            target = result.get("target_disease")
            if target:
                st.success(f"疾病 '{target}' 的共现分析完成")
            else:
                st.success("全局疾病共现分析完成")
            st.markdown("---")
            st.markdown(result["narrative"])
        else:
            st.error(
                f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()
st.info("""
**说明：**
- 输入疾病名称：分析该疾病的常见合并症、中医证型分布、三元疾病组合
- 留空：分析全科室最常见的合并症对
- 基于同一次就诊中的多个诊断建立共现关系
""")
