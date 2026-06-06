"""
RAG问答
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("🤖 LLM + 知识图谱 RAG 问答")
st.markdown("基于 Neo4j 知识图谱的真实关系子图回答您的问题，避免大模型编造")

question = st.text_area(
    "请输入您的问题",
    value="患者 4116-002-000000000000000000000021 最后一次就诊的诊断是什么？",
    placeholder="例如：肺恶性肿瘤的常用药品有哪些？/ 高血压常见的合并症是什么？",
    height=80,
)

col1, col2 = st.columns([1, 5])
with col1:
    ask_clicked = st.button("💬 提问", type="primary")

if ask_clicked:
    if not question.strip():
        st.error("请输入问题")
    else:
        with st.spinner("正在检索知识图谱并生成回答..."):
            result = api_post("/api/narrative/rag/ask",
                              json_data={"question": question.strip()})
            if result and result.get("answer"):
                st.markdown("---")
                st.subheader("💡 回答")
                st.markdown(result["answer"])

                st.markdown("---")
                st.subheader("📚 数据来源")
                for src in result.get("sources", []):
                    st.caption(f"- {src}")

                with st.expander("查看检索到的原始数据"):
                    st.json(result.get("retrieved", {}))
            else:
                st.error(
                    f"回答失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()
st.info("""
**示例问题：**
- 患者 4116-002-000000000000000000000021 最后一次就诊的诊断是什么？
- 肺恶性肿瘤的常用药品有哪些？
- 高血压常见的合并症是什么？
- 本科室的再入院率是多少？
""")
