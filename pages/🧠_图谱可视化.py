"""
图谱可视化
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("🕸️ 交互式知识图谱可视化")
st.markdown("从 Neo4j 中提取子图数据，用 ECharts 力导向图展示")

viz_type = st.selectbox(
    "选择可视化类型",
    [
        "患者子图",
        "疾病关联子图",
        "药品共现网络",
        "合并症网络",
    ],
)

graph_data = None
error_msg = None

if viz_type == "患者子图":
    patient_id = st.text_input(
        "患者ID",
        value="4116-002-000000000000000000000021",
        placeholder="例如: 4116-002-000000000000000000000021",
        key="viz_patient",
    )
    max_visits = st.slider("最大展示就诊次数", 1, 20, 10)
    if st.button("🔍 加载患者子图", type="primary"):
        with st.spinner("正在从Neo4j查询患者子图..."):
            result = api_get(
                f"/api/kg/subgraph/patient/{patient_id}?max_visits={max_visits}")
            if result and result.get("nodes") is not None:
                graph_data = result
            else:
                error_msg = result.get(
                    "detail", "查询失败") if result else "无响应"

elif viz_type == "疾病关联子图":
    disease_name = st.text_input(
        "疾病名称",
        value="肺恶性肿瘤",
        placeholder="例如: 肺恶性肿瘤",
        key="viz_disease",
    )
    top_n = st.slider("关联节点数量", 5, 30, 15)
    if st.button("🔍 加载疾病子图", type="primary"):
        with st.spinner("正在从Neo4j查询疾病关联..."):
            enc = requests.utils.quote(disease_name)
            result = api_get(
                f"/api/kg/subgraph/disease/{enc}?top_n={top_n}")
            if result and result.get("nodes") is not None:
                graph_data = result
            else:
                error_msg = result.get(
                    "detail", "查询失败") if result else "无响应"

elif viz_type == "药品共现网络":
    disease_name = st.text_input(
        "疾病名称（留空分析全局）",
        value="肺恶性肿瘤",
        placeholder="例如: 肺恶性肿瘤",
        key="viz_drug_disease",
    )
    top_n = st.slider("边数量上限", 10, 50, 20)
    analyze_global = st.checkbox("分析全局药品共现", value=False)
    if st.button("🔍 加载药品共现网络", type="primary"):
        with st.spinner("正在从Neo4j查询药品共现..."):
            if analyze_global or not disease_name.strip():
                result = api_get(
                    f"/api/kg/subgraph/drug-pattern?top_n={top_n}")
            else:
                enc = requests.utils.quote(disease_name)
                result = api_get(
                    f"/api/kg/subgraph/drug-pattern/{enc}?top_n={top_n}")
            if result and result.get("nodes") is not None:
                graph_data = result
            else:
                error_msg = result.get(
                    "detail", "查询失败") if result else "无响应"

elif viz_type == "合并症网络":
    disease_name = st.text_input(
        "疾病名称（留空分析全局）",
        value="肺恶性肿瘤",
        placeholder="例如: 肺恶性肿瘤",
        key="viz_comorb_disease",
    )
    top_n = st.slider("关联节点数量", 5, 30, 20)
    analyze_global = st.checkbox("分析全局疾病共现", value=False)
    if st.button("🔍 加载合并症网络", type="primary"):
        with st.spinner("正在从Neo4j查询合并症网络..."):
            if analyze_global or not disease_name.strip():
                result = api_get(
                    f"/api/kg/subgraph/comorbidity?top_n={top_n}")
            else:
                enc = requests.utils.quote(disease_name)
                result = api_get(
                    f"/api/kg/subgraph/comorbidity/{enc}?top_n={top_n}")
            if result and result.get("nodes") is not None:
                graph_data = result
            else:
                error_msg = result.get(
                    "detail", "查询失败") if result else "无响应"

if error_msg:
    st.error(error_msg)

if graph_data:
    nodes = graph_data.get("nodes", [])
    links = graph_data.get("links", [])
    stats = graph_data.get("stats", {})
    categories = graph_data.get("categories", [])
    title = graph_data.get("title", "知识图谱")

    st.success(
        f"{title} 加载完成 | 节点: {stats.get('nodes', 0)} | 边: {stats.get('links', 0)}")

    # 配色方案
    color_map = {
        "患者": "#5470c6",
        "就诊": "#91cc75",
        "疾病": "#fac858",
        "合并症": "#ee6666",
        "药品": "#73c0de",
        "检查": "#3ba272",
        "手术": "#fc8452",
        "主诉": "#9a60b4",
    }

    # 为每个category分配索引
    cat_names = [c["name"] for c in categories]
    for n in nodes:
        n["category_idx"] = cat_names.index(
            n["category"]) if n["category"] in cat_names else 0
        n["itemStyle"] = {"color": color_map.get(n["category"], "#999")}

    echart_options = {
        "title": {"text": title, "left": "center"},
        "tooltip": {
            "formatter": "{b}<br/>类型: {c}",
        },
        "legend": {
            "data": cat_names,
            "orient": "vertical",
            "left": "left",
        },
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "data": [
                    {
                        "id": str(n["id"]),
                        "name": n["name"],
                        "category": n["category_idx"],
                        "symbolSize": n.get("symbolSize", 15),
                        "itemStyle": n.get("itemStyle"),
                        "value": n.get("count", 1),
                    }
                    for n in nodes
                ],
                "links": [
                    {
                        "source": str(l["source"]),
                        "target": str(l["target"]),
                        "value": l.get("value", 1),
                        "name": l.get("name", "关联"),
                    }
                    for l in links
                ],
                "categories": [{"name": c["name"]} for c in categories],
                "roam": True,
                "label": {"show": True, "position": "right", "fontSize": 10},
                "force": {
                    "repulsion": 400,
                    "edgeLength": [60, 180],
                    "gravity": 0.1,
                },
                "emphasis": {
                    "focus": "adjacency",
                    "lineStyle": {"width": 4},
                },
                "lineStyle": {
                    "width": 1.5,
                    "color": "#888",
                    "curveness": 0.2,
                    "opacity": 0.8,
                },
                "edgeLabel": {
                    "show": True,
                    "formatter": "{b}",
                    "fontSize": 9,
                    "color": "#555",
                },
            }
        ],
    }

    st_echarts(options=echart_options, height="600px",
               key=f"kg_viz_{viz_type}")

    # 节点表格
    with st.expander("查看节点数据"):
        st.dataframe(
            [{"ID": n["id"], "名称": n["name"], "类型": n["label"],
                "分类": n["category"]} for n in nodes],
            use_container_width=True,
        )

    # 关系表格
    with st.expander("查看关系数据"):
        st.dataframe(
            [{"源节点": l["source"], "目标节点": l["target"], "关系": l["name"],
                "频次": l.get("value", 1)} for l in links],
            use_container_width=True,
        )

st.divider()
st.info("""
**说明：**
- **患者子图**：展示某位患者的多次就诊及其诊断、用药、检查、手术、主诉
- **疾病关联子图**：以疾病为中心，关联常用药品、常规检查、常见合并症
- **药品共现网络**：展示在同一次就诊中经常一起出现的药品组合
- **合并症网络**：展示疾病之间的共现关系
""")

