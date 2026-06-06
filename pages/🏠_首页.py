"""
首页内容
"""
import streamlit as st
from utils.api_client import api_get

st.markdown(
    "<h1 style='text-align: center;'>🏥 医院叙事生成助手</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; font-size: 1.2em; color: #666;'>"
    "基于大语言模型与医疗知识图谱的科室历史数据智能分析与叙事生成平台"
    "</p>",
    unsafe_allow_html=True,
)
st.divider()

st.markdown("### 📋 平台简介")
st.write(
    "本平台面向医院科室管理者与临床医生，整合科室历史运营数据，"
    "通过**大语言模型**与**Neo4j知识图谱**双引擎驱动，"
    "提供从数据统计分析到深度医疗叙事的完整智能辅助能力。"
)

# 三大板块静态介绍卡片（不可点击）
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        "<div style='padding: 20px; border-radius: 10px; background-color: #f0f7ff;'>"
        "<h3>📊 统计分析与报告</h3>"
        "<p>基于Excel原始数据进行多维度统计分析，自动生成科室数据分析报告、周简报，"
        "支持Word/PDF一键导出。</p>"
        "<ul>"
        "<li>数据概览与ECharts交互图表</li>"
        "<li>智能报告生成（LLM驱动）</li>"
        "<li>每周临床简报自动生成</li>"
        "<li>文档导出（DOCX / PDF）</li>"
        "</ul>"
        "</div>",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        "<div style='padding: 20px; border-radius: 10px; background-color: #f6fff0;'>"
        "<h3>🧠 知识图谱叙事</h3>"
        "<p>构建患者-就诊-疾病-药品-检查-手术等多实体医疗知识图谱，"
        "挖掘深层关联模式，生成专业医疗叙事。</p>"
        "<ul>"
        "<li>患者故事线与再入院分析</li>"
        "<li>疾病诊疗路径与合并症网络</li>"
        "<li>用药模式与中医特色分析</li>"
        "<li>质控异常监测与风险预警</li>"
        "<li>相似患者推荐与科室运营分析</li>"
        "</ul>"
        "</div>",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        "<div style='padding: 20px; border-radius: 10px; background-color: #fff8f0;'>"
        "<h3>⚙️ 系统管理</h3>"
        "<p>管理知识图谱构建、系统状态监控与后端服务配置，保障平台稳定运行。</p>"
        "<ul>"
        "<li>Neo4j 知识图谱构建与重建</li>"
        "<li>图谱统计与Cypher查询调试</li>"
        "<li>后端服务健康检查</li>"
        "<li>数据规模实时监控</li>"
        "</ul>"
        "</div>",
        unsafe_allow_html=True,
    )

st.divider()

# 系统数据规模
st.markdown("### 📈 系统数据规模")
if st.button("🔄 刷新统计", key="home_refresh"):
    with st.spinner("获取统计..."):
        stats = api_get("/api/kg/stats")
        if stats:
            sc1, sc2 = st.columns(2)
            with sc1:
                nodes = stats.get("nodes", {})
                total_nodes = sum(nodes.values())
                st.metric("总节点数", f"{total_nodes:,}")
                for label, cnt in nodes.items():
                    if cnt > 0:
                        st.caption(f"{label}: {cnt:,}")
            with sc2:
                rels = stats.get("relationships", {})
                total_rels = sum(rels.values())
                st.metric("总关系数", f"{total_rels:,}")
                for rel_type, cnt in rels.items():
                    if cnt > 0:
                        st.caption(f"{rel_type}: {cnt:,}")
        else:
            st.info("暂无图谱数据，请前往「⚙️ 知识图谱管理」页面构建知识图谱")
else:
    st.info("点击「刷新统计」查看知识图谱数据规模")

st.divider()
st.caption(
    "💡 **使用提示**：左侧导航栏分为「📊 统计分析与报告」、「🧠 知识图谱叙事」"
    "和「⚙️ 系统管理」三大模块，请选择对应功能开始使用。"
)
