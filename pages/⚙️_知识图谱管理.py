"""
知识图谱管理
"""
import streamlit as st
import requests
from utils.api_client import api_get, api_post

st.header("🧠 医疗知识图谱")
st.markdown("从Excel数据中提取实体（患者、疾病、药品、检查、手术等）构建Neo4j知识图谱")

# 连接状态
col1, col2 = st.columns(2)
with col1:
    if st.button("🔌 测试后端与Neo4j连接"):
        health = api_get("/health")
        if health:
            st.write("后端服务状态: ✅")
        else:
            st.write("后端服务状态: ❌")

        stats = api_get("/api/kg/stats")
        if stats:
            st.success("Neo4j连接成功！")
        else:
            st.error("Neo4j连接失败")

with col2:
    st.info("""
    **配置提示：**
    如果连接失败，请在 `.env` 文件中设置正确的Neo4j密码：
    ```
    NEO4J_PASSWORD=your_password
    ```
    然后重启后端服务。
    """)

st.divider()

# 构建图谱
st.subheader("构建知识图谱")
clear_existing = st.checkbox("清空现有图谱后重建", value=False)

if st.button("🚀 开始构建知识图谱", type="primary"):
    with st.spinner("知识图谱构建中，这可能需要几分钟..."):
        result = api_post(
            "/api/kg/build", json_data={"clear": clear_existing})
        if result and result.get("success"):
            st.success(result.get("message", "构建完成！"))
        else:
            st.error(
                f"构建失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()

# 统计信息
st.subheader("图谱统计")
if st.button("📊 刷新统计"):
    stats = api_get("/api/kg/stats")
    if stats:
        col1, col2 = st.columns(2)
        with col1:
            st.write("**节点数量**")
            nodes = stats.get("nodes", {})
            for label, cnt in nodes.items():
                st.write(f"- {label}: {cnt}")
        with col2:
            st.write("**关系数量**")
            rels = stats.get("relationships", {})
            for rel_type, cnt in rels.items():
                st.write(f"- {rel_type}: {cnt}")
    else:
        st.info("暂无统计信息，请先构建知识图谱")

st.divider()

# Cypher查询
st.subheader("Cypher查询调试")
st.markdown("输入Cypher查询语句直接查询图谱（仅用于开发调试）")
query = st.text_area(
    "Cypher语句", value="MATCH (n) RETURN labels(n)[0] as label, count(n) as cnt ORDER BY cnt DESC")
if st.button("▶️ 执行查询"):
    if query.strip():
        result = api_get(
            f"/api/kg/query?cypher={requests.utils.quote(query.strip())}")
        if result:
            st.write("**查询结果：**")
            st.json(result)
        else:
            st.error("查询失败")
    else:
        st.warning("请输入查询语句")
