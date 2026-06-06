"""
风险预警
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("⚡ 预测性叙事 / 风险预警")
st.markdown("基于知识图谱和历史数据识别高风险患者，生成风险预警叙事")

tab1, tab2 = st.tabs(["全局风险分析", "个体患者风险评估"])

with tab1:
    top_n = st.slider("显示高风险患者数量", 5, 50, 20)
    if st.button("🌐 运行全局风险分析", type="primary"):
        with st.spinner("正在分析科室高风险患者..."):
            result = api_get(
                f"/api/narrative/risk-prediction?top_n={top_n}")

            if result and result.get("narrative"):
                dist = result.get("score_distribution", {})
                st.success(
                    f"全局风险分析完成 | 极高风险: {dist.get('极高', 0)}人 | 高风险: {dist.get('高', 0)}人")

                # 风险分布
                st.markdown("---")
                st.subheader("📊 风险等级分布")
                rcol1, rcol2, rcol3, rcol4 = st.columns(4)
                with rcol1:
                    st.metric("极高风险", dist.get("极高", 0),
                              delta_color="inverse")
                with rcol2:
                    st.metric("高风险", dist.get("高", 0),
                              delta_color="inverse")
                with rcol3:
                    st.metric("中风险", dist.get("中", 0))
                with rcol4:
                    st.metric("低风险", dist.get("低", 0))

                # 叙事
                st.markdown("---")
                st.subheader("📝 风险预警叙事")
                st.markdown(result["narrative"])

                # 高风险患者列表
                patients = result.get("high_risk_patients", [])
                if patients:
                    st.markdown("---")
                    st.subheader("🔎 高风险患者列表")
                    df_data = []
                    for p in patients:
                        df_data.append({
                            "患者ID": p["patient_id"],
                            "评分": p["risk_score"],
                            "等级": p["risk_level"],
                            "年龄": p.get("age", "-"),
                            "就诊": p["visit_count"],
                            "诊断数": p["disease_count"],
                            "风险因素": ", ".join(p["risk_factors"][:3]),
                        })
                    st.dataframe(df_data, use_container_width=True)
            else:
                st.error(
                    f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

with tab2:
    patient_id = st.text_input(
        "患者ID",
        value="4116-002-000000000000000000000021",
        placeholder="例如: 4116-002-000000000000000000000021",
        key="risk_patient_id",
    )
    if st.button("⚡ 评估患者风险", type="primary"):
        with st.spinner("正在评估患者风险..."):
            result = api_get(
                f"/api/narrative/risk-prediction?patient_id={patient_id}")

            if result and result.get("narrative"):
                score = result.get("risk_score", 0)
                level = result.get("risk_level", "未知")
                color = {"极高": "red", "高": "orange",
                         "中": "yellow", "低": "green"}.get(level, "gray")

                st.success(f"风险评估完成 | 评分: {score}/100")

                # 风险指标
                st.markdown("---")
                st.subheader("📊 风险指标")
                st.markdown(
                    f"<h2 style='color:{color}'>风险等级: {level}</h2>", unsafe_allow_html=True)
                st.progress(min(score / 100, 1.0),
                            text=f"风险评分: {score}/100")

                # 风险因素
                factors = result.get("risk_factors", [])
                if factors:
                    st.markdown("**风险因素:**")
                    for f in factors:
                        st.warning(f)

                # 叙事
                st.markdown("---")
                st.subheader("📝 风险预警叙事")
                st.markdown(result["narrative"])
            else:
                st.error(
                    f"评估失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()
st.info("""
**风险评分规则：**
- **就诊频率**: ≥10次(+30分) / ≥5次(+20分) / ≥3次(+10分)
- **多病共存**: ≥5种诊断(+20分) / ≥3种(+10分)
- **住院天数**: ≥15天(+20分) / ≥10天(+10分)
- **年龄**: ≥75岁(+15分) / ≥65岁(+10分)
- **恶性肿瘤/终末期**: (+20分)
- **多次手术**: ≥2次(+10分)

**风险等级**: 极高(≥70分) | 高(50-69分) | 中(30-49分) | 低(<30分)

**注意：** 风险评分基于统计规则，仅供参考，不能替代临床专业判断。
""")