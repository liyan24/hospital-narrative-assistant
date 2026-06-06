"""
相似患者
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("👥 相似患者推荐")
st.markdown("基于知识图谱共同邻居算法，为指定患者推荐最相似的参考病例")

patient_id = st.text_input(
    "患者ID",
    value="4116-002-000000000000000000000021",
    placeholder="例如: 4116-002-000000000000000000000021",
    key="similar_patient_id",
)
top_n = st.slider("推荐数量", 3, 20, 10)

if st.button("🔍 查找相似患者", type="primary"):
    with st.spinner("正在基于知识图谱计算患者相似度..."):
        result = api_get(
            f"/api/narrative/similar-patients/{patient_id}?top_n={top_n}")

        if result and result.get("narrative"):
            profile = result.get("target_profile", {})
            st.success(
                f"相似患者查找完成 | 目标患者就诊 {profile.get('visit_count', 0)} 次")

            # 目标患者画像
            st.markdown("---")
            st.subheader("👤 目标患者画像")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("年龄", profile.get("age", "未知"))
            with col2:
                st.metric("就诊次数", profile.get("visit_count", 0))
            with col3:
                st.metric("西医诊断", len(
                    [d for d in profile.get("diseases", []) if "western" in d]))
            with col4:
                st.metric("中医诊断", len(
                    [d for d in profile.get("diseases", []) if "tcm" in d]))

            with st.expander("查看完整画像"):
                st.write(
                    "**主要诊断:**", ", ".join(profile.get("diseases", [])[:10]))
                st.write(
                    "**主要用药:**", ", ".join(profile.get("drugs", [])[:10]))
                st.write(
                    "**主要检查:**", ", ".join(profile.get("exams", [])[:10]))

            # 相似患者
            st.markdown("---")
            st.subheader("📝 相似患者推荐")
            st.markdown(result["narrative"])

            # 相似患者表格
            similar = result.get("similar_patients", [])
            if similar:
                st.markdown("---")
                st.subheader("📊 相似度排名")
                for i, sim in enumerate(similar, 1):
                    with st.container():
                        scol1, scol2 = st.columns([1, 3])
                        with scol1:
                            st.markdown(f"**Top {i}**")
                            st.metric("相似度", f"{sim['score']:.3f}")
                            st.caption(f"就诊 {sim.get('visit_count', 0)} 次")
                        with scol2:
                            st.caption(f"患者ID: {sim['patient_id']}")
                            detail = sim.get("details", {})
                            st.write(
                                f"疾病相似: {detail.get('disease_similarity', 0):.2f} | "
                                f"用药相似: {detail.get('drug_similarity', 0):.2f} | "
                                f"检查相似: {detail.get('exam_similarity', 0):.2f} | "
                                f"手术相似: {detail.get('surgery_similarity', 0):.2f}"
                            )
                            if sim.get("common_diseases"):
                                st.caption(
                                    f"共同诊断: {', '.join(sim['common_diseases'][:5])}")
                            if sim.get("common_drugs"):
                                st.caption(
                                    f"共同用药: {', '.join(sim['common_drugs'][:5])}")
                        st.divider()
        else:
            st.error(
                f"查找失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()
st.info("""
**算法说明：**
- 基于知识图谱中患者-就诊-实体（疾病/药品/检查/手术/主诉）的共享关系计算相似度
- 采用加权Jaccard相似度：疾病(35%) + 用药(25%) + 检查(20%) + 手术(15%) + 主诉(5%)
- 先通过共同疾病快速筛选候选患者，再精确计算相似度
- 推荐结果仅供参考，不能替代临床判断
""")
