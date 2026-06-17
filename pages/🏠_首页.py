"""
角色化工作台首页
"""
import streamlit as st
from utils.ui_style import apply_global_style, render_card, render_metric_card, render_section_header
from utils.api_client import api_get

apply_global_style()

# 角色选择（实际产品中应从登录态获取）
if "user_role" not in st.session_state:
    st.session_state["user_role"] = "doctor"

with st.sidebar:
    st.markdown("### 👤 当前角色")
    role = st.selectbox(
        "选择角色",
        options=[("doctor", "一线医生"), ("director", "科主任"), ("admin", "医务管理")],
        format_func=lambda x: x[1],
        index=0,
    )
    st.session_state["user_role"] = role[0]

user_role = st.session_state["user_role"]

st.markdown(
    "<h1 style='text-align: center;'>🏥 科室智能叙事助手</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; font-size: 1.1em; color: #6B7280;'>"
    "把分散的医疗数据转化为医生可信任的叙事和洞察"
    "</p>",
    unsafe_allow_html=True,
)
st.divider()

# 加载全局风险患者（用于重点关注）
@st.cache_data(ttl=300)
def load_global_risk_patients():
    return api_get("/api/narrative/risk-prediction?top_n=20", timeout=120)

# 加载科室运营数据（主任/管理角色）
@st.cache_data(ttl=300)
def load_department_operation():
    return api_get("/api/narrative/department-operation?period=latest_month&compare=true", timeout=120)

# 加载质控异常
@st.cache_data(ttl=300)
def load_quality_control():
    return api_get("/api/narrative/quality-control?rule_type=all", timeout=120)

risk_data = load_global_risk_patients()
dept_data = load_department_operation()
qc_data = load_quality_control()

if user_role == "doctor":
    render_section_header("今日工作", "快速访问您最常用的功能")

    # 从风险数据中提取高风险患者数
    high_risk_count = 0
    if risk_data and risk_data.get("status") == "ok":
        dist = risk_data.get("score_distribution", {})
        high_risk_count = dist.get("极高", 0) + dist.get("高", 0)

    qc_count = 0
    if qc_data and qc_data.get("status") == "ok":
        summary = qc_data.get("summary", {})
        qc_count = (
            summary.get("abnormal_los_cases", 0) +
            summary.get("short_readmission_cases", 0) +
            summary.get("total_drug_interaction_cases", 0)
        )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("管床患者", "12", "较昨日 +2")
    with col2:
        render_metric_card("今日手术", "3", "待完成 1")
    with col3:
        render_metric_card("质控提醒", str(qc_count), "需处理")
    with col4:
        render_metric_card("高风险患者", str(high_risk_count), "需关注")

    render_section_header("快捷入口")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_card(
            "👤 患者全息视图",
            "输入患者ID，快速查看完整就诊时间线、诊断、用药、检查、手术记录。",
        )
    with c2:
        render_card(
            "🩺 查房助手",
            "语音或文字提问，基于知识图谱和病历数据获得可溯源的回答。",
        )
    with c3:
        render_card(
            "📋 科室晨会简报",
            "查看今日新入院、重点关注患者、手术安排和质控异常。",
        )

    render_section_header("重点关注患者", "再入院风险高或住院天数异常")
    focus_patients = []
    if risk_data and risk_data.get("status") == "ok":
        for p in risk_data.get("high_risk_patients", [])[:5]:
            level = p.get("risk_level", "中")
            level_class = "danger" if level in ["极高", "高"] else "warning"
            reasons = p.get("risk_factors", [])
            focus_patients.append({
                "id": p.get("patient_id", ""),
                "name": p.get("patient_id", "")[:4] + "**",
                "risk": level,
                "reason": "；".join(reasons) if reasons else "高风险评分",
                "level_class": level_class,
            })

    if focus_patients:
        for p in focus_patients:
            color = "#EF4444" if p["level_class"] == "danger" else "#F59E0B"
            st.markdown(f"""
            <div style="background: white; border-left: 4px solid {color}; padding: 12px 16px; margin-bottom: 10px; border-radius: 0 8px 8px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600;">{p['name']} ({p['id']})</span>
                    <span style="background: {color}20; color: {color}; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 500;">{p['risk']}风险</span>
                </div>
                <div style="color: #6B7280; font-size: 13px; margin-top: 4px;">{p['reason']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("暂无高风险患者数据")

elif user_role == "director":
    render_section_header("科室运营概览", "本月关键指标一览")

    current_metrics = {}
    changes = {}
    if dept_data and dept_data.get("status") == "ok":
        current_metrics = dept_data.get("current_metrics", {}) or {}
        changes = dept_data.get("changes", {}) or {}

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        visit_count = current_metrics.get("visit_count", 0)
        visit_change = changes.get("visit_count_change", 0)
        render_metric_card("本月入院", f"{visit_count}", f"环比 {visit_change:+.1f}%")
    with col2:
        avg_los = current_metrics.get("avg_los", 0)
        los_change = changes.get("avg_los_change", 0)
        render_metric_card("平均住院日", f"{avg_los}", f"环比 {los_change:+.1f}%")
    with c3:
        surgery_rate = current_metrics.get("surgery_rate", 0)
        surgery_change = changes.get("surgery_rate_change", 0)
        render_metric_card("手术率", f"{surgery_rate}%", f"环比 {surgery_change:+.1f}%")
    with col4:
        readmit_rate = current_metrics.get("readmit_rate", 0)
        readmit_change = changes.get("readmit_rate_change", 0)
        render_metric_card("再入院率", f"{readmit_rate}%", f"环比 {readmit_change:+.1f}%")

    render_section_header("快捷入口")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_card(
            "📄 科室运营简报生成",
            "生成包含病种、用药、合并症、中西医结合占比等维度的深度分析报告。",
        )
    with c2:
        render_card(
            "⚠️ 质控异常",
            "查看缺失检查、住院天数异常、30天再入院、诊断-药品不匹配等问题清单。",
        )
    with c3:
        render_card(
            "📅 周简报",
            "查看本周运营概况、病种分析、检查检验汇总、治疗动态等 7 大模块。",
        )

    render_section_header("本周待处理事项")
    todo_items = []
    if qc_data and qc_data.get("status") == "ok":
        summary = qc_data.get("summary", {})
        if summary.get("abnormal_los_cases", 0) > 0:
            todo_items.append(("住院天数异常", f"{summary.get('abnormal_los_cases')} 例需确认", "warning"))
        if summary.get("short_readmission_cases", 0) > 0:
            todo_items.append(("30天内再入院", f"{summary.get('short_readmission_cases')} 例需关注", "danger"))
        if summary.get("total_drug_interaction_cases", 0) > 0:
            todo_items.append(("药物相互作用", f"{summary.get('total_drug_interaction_cases')} 例需处理", "danger"))

    if not todo_items:
        todo_items.append(("周简报发布", "周一 8:00 前完成", "normal"))

    for title, desc, level in todo_items:
        color = {"normal": "#10B981", "warning": "#F59E0B", "danger": "#EF4444"}[level]
        st.markdown(f"""
        <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px 16px; margin-bottom: 10px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 8px; height: 8px; border-radius: 50%; background: {color};"></div>
                <div>
                    <div style="font-weight: 600;">{title}</div>
                    <div style="color: #6B7280; font-size: 13px;">{desc}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

else:  # admin
    render_section_header("全院运营概览", "多科室关键指标对比")

    current_metrics = {}
    if dept_data and dept_data.get("status") == "ok":
        current_metrics = dept_data.get("current_metrics", {}) or {}

    high_risk_count = 0
    if risk_data and risk_data.get("status") == "ok":
        dist = risk_data.get("score_distribution", {})
        high_risk_count = dist.get("极高", 0) + dist.get("高", 0)

    qc_count = 0
    if qc_data and qc_data.get("status") == "ok":
        summary = qc_data.get("summary", {})
        qc_count = (
            summary.get("abnormal_los_cases", 0) +
            summary.get("short_readmission_cases", 0) +
            summary.get("total_drug_interaction_cases", 0)
        )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("在院患者", f"{current_metrics.get('visit_count', 0):,}", "本月")
    with col2:
        surgery_count = len(current_metrics.get('top_surgeries', []))
        render_metric_card("本周手术", str(surgery_count), "Top 手术数")
    with col3:
        render_metric_card("质控事件", str(qc_count), "待处理")
    with col4:
        render_metric_card("高风险患者", str(high_risk_count), "需关注")

    render_section_header("快捷入口")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_card(
            "📊 数据概览",
            "查看全院/科室多维度统计数据和交互式图表。",
        )
    with c2:
        render_card(
            "⚡ 风险预警",
            "查看全院高风险患者分布和评分详情。",
        )
    with c3:
        render_card(
            "⚙️ 知识图谱管理",
            "管理知识图谱构建、统计和查询。",
        )

st.divider()

# 系统数据规模
render_section_header("系统数据规模")
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
