"""
Streamlit 前端入口：医院叙事生成助手
采用 Streamlit Pages (v2 navigation) 多页面结构
"""
import streamlit as st

st.set_page_config(
    page_title="医院叙事生成助手",
    page_icon="🏥",
    layout="wide",
)

# ========== 显式定义多页面导航（兼容 Streamlit 1.58+）==========
pages = {
    "🏠 首页": [
        st.Page("pages/🏠_首页.py", title="🏠 首页", icon="🏥", default=True),
    ],
    "📊 统计分析与报告": [
        st.Page("pages/📊_数据概览.py", title="📊 数据概览"),
        st.Page("pages/📊_报告生成.py", title="📄 报告生成"),
        st.Page("pages/📊_文档导出.py", title="📥 文档导出"),
        st.Page("pages/📊_周简报.py", title="📅 周简报"),
    ],
    "🧠 知识图谱叙事": [
        st.Page("pages/🧠_患者故事线.py", title="👤 患者故事线"),
        st.Page("pages/🧠_诊疗路径.py", title="🛤️ 诊疗路径"),
        st.Page("pages/🧠_合并症分析.py", title="🔗 合并症分析"),
        st.Page("pages/🧠_用药模式.py", title="💊 用药模式"),
        st.Page("pages/🧠_再入院分析.py", title="🔄 再入院分析"),
        st.Page("pages/🧠_RAG问答.py", title="🤖 RAG问答"),
        st.Page("pages/🧠_图谱可视化.py", title="🕸️ 图谱可视化"),
        st.Page("pages/🧠_中医特色.py", title="🌿 中医特色"),
        st.Page("pages/🧠_质控异常.py", title="⚠️ 质控异常"),
        st.Page("pages/🧠_科室运营.py", title="📈 科室运营"),
        st.Page("pages/🧠_相似患者.py", title="👥 相似患者"),
        st.Page("pages/🧠_风险预警.py", title="⚡ 风险预警"),
    ],
    "⚙️ 系统管理": [
        st.Page("pages/⚙️_知识图谱管理.py", title="🧠 知识图谱管理"),
    ],
}

# 使用顶部导航栏，确保用户一定能看到导航
pg = st.navigation(pages, position="top")
pg.run()
