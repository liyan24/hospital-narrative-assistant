"""
科室晨会简报
每日自动推送：新入院、重点关注患者、手术安排、质控异常
"""
import streamlit as st
from utils.ui_style import apply_global_style, render_section_header, render_metric_card
from utils.api_client import api_get, api_post
from datetime import datetime

apply_global_style()

st.header("📋 科室晨会简报")
st.caption("每日 7:30 自动生成的科室晨会摘要，帮助医生快速掌握今日重点")

# 日期选择
briefing_date = st.date_input("选择日期", value=datetime.now())
briefing_date_str = briefing_date.strftime("%Y-%m-%d")

# 加载简报
@st.cache_data(ttl=300)
def load_daily_briefing(date_str: str):
    return api_get(f"/api/daily/briefing?date={date_str}", timeout=120)

with st.spinner("加载晨会简报..."):
    briefing = load_daily_briefing(briefing_date_str)

# 刷新按钮
if st.button("🔄 刷新简报", type="primary"):
    st.cache_data.clear()
    briefing = api_get(f"/api/daily/briefing?date={briefing_date_str}", timeout=120)
    if briefing and briefing.get("status") == "ok":
        st.success("简报已刷新")
    else:
        st.error("简报刷新失败")

if not briefing or briefing.get("status") != "ok":
    error_msg = briefing.get("message", "简报加载失败") if briefing else "接口调用失败"
    st.warning(error_msg)
    st.stop()

briefing_data = briefing.get("briefing", {})
overview = briefing_data.get("overview", {})

# 关键指标
render_section_header("今日概览")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("新入院", str(overview.get("new_admissions", 0)), "今日")
with c2:
    render_metric_card("在院患者", str(overview.get("inpatients", 0)), "当前")
with c3:
    render_metric_card("今日手术", str(overview.get("surgeries", 0)), "已安排")
with c4:
    render_metric_card("重点关注", str(overview.get("focus_patients", 0)), "高风险")
with c5:
    render_metric_card("质控异常", str(overview.get("quality_control_issues", 0)), "待处理")

# 新入院患者
render_section_header("新入院患者", f"{briefing_date_str} 0:00 至今")
new_admissions = briefing_data.get("new_admissions", [])
if new_admissions:
    st.dataframe(new_admissions, use_container_width=True, hide_index=True)
else:
    st.info("今日暂无新入院患者")

# 重点关注患者
render_section_header("重点关注患者", "再入院风险高、住院天数异常或恶性肿瘤患者")
focus_patients = briefing_data.get("focus_patients", [])
if focus_patients:
    for p in focus_patients:
        level_color = "#EF4444" if p.get("risk") == "高" else "#F59E0B"
        st.markdown(f"""
        <div style="background: white; border: 1px solid #E5E7EB; border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <div style="font-weight: 600; font-size: 15px;">{p.get('name', '')} ({p.get('patient_id', '')}) · 床号 {p.get('bed', '-')}</div>
                    <div style="color: #6B7280; font-size: 13px; margin-top: 4px;">{p.get('reason', '')}</div>
                    <div style="color: #2563EB; font-size: 13px; margin-top: 6px;">💡 建议：{p.get('action', '')}</div>
                </div>
                <span style="background: {level_color}20; color: {level_color}; padding: 3px 12px; border-radius: 12px; font-size: 12px; font-weight: 500;">{p.get('risk', '')}风险</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("今日无重点关注患者")

# 今日手术安排
render_section_header("今日手术安排")
surgeries = briefing_data.get("surgeries", [])
if surgeries:
    st.dataframe(surgeries, use_container_width=True, hide_index=True)
else:
    st.info("今日暂无手术安排")

# 质控异常
render_section_header("质控异常提醒")
qc_issues = briefing_data.get("quality_control_issues", [])
if qc_issues:
    for issue in qc_issues:
        type_color = {
            "缺失检查": "#F59E0B",
            "住院天数异常": "#EF4444",
            "药物相互作用": "#EF4444",
            "30天内再入院": "#EF4444",
            "诊断-药品不匹配": "#F59E0B",
        }.get(issue.get("type", ""), "#6B7280")
        st.markdown(f"""
        <div style="background: white; border-left: 4px solid {type_color}; padding: 10px 14px; margin-bottom: 8px; border-radius: 0 8px 8px 0;">
            <div style="display: flex; justify-content: space-between;">
                <span style="font-weight: 600;">{issue.get('type', '')}</span>
                <span style="color: #6B7280; font-size: 12px;">患者：{issue.get('name', issue.get('patient_id', ''))}</span>
            </div>
            <div style="color: #374151; font-size: 13px; margin-top: 4px;">{issue.get('description', '')}</div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.success("✅ 未发现质控异常")

# 底部操作
st.divider()
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("📤 推送到企业微信", use_container_width=True):
        st.info("推送功能需对接企业微信后启用")
with c2:
    if st.button("📧 发送邮件", use_container_width=True):
        st.info("邮件发送功能需配置 SMTP 后启用")
with c3:
    if st.button("📥 导出 PDF", use_container_width=True):
        st.info("导出功能需对接文档服务后启用")
