"""
科室晨会简报
每日自动推送：新入院、重点关注患者、手术安排、质控异常
"""
import streamlit as st
from utils.ui_style import apply_global_style, render_section_header, render_metric_card, render_card
from utils.api_client import api_get, api_post
from datetime import datetime, timedelta

apply_global_style()

st.header("📋 科室晨会简报")
st.caption("每日 7:30 自动生成的科室晨会摘要，帮助医生快速掌握今日重点")

# 日期选择
briefing_date = st.date_input("选择日期", value=datetime.now())

# 刷新按钮
if st.button("🔄 刷新简报", type="primary"):
    with st.spinner("生成晨会简报..."):
        # 实际调用 API 生成当日简报
        # result = api_post("/api/daily/briefing", params={"date": briefing_date.strftime("%Y-%m-%d")})
        st.success("简报已刷新")

# 关键指标
render_section_header("今日概览")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("新入院", "8", "较昨日 +2")
with c2:
    render_metric_card("在院患者", "86", "持平")
with c3:
    render_metric_card("今日手术", "5", "上午 3 / 下午 2")
with c4:
    render_metric_card("重点关注", "6", "高风险 2")
with c5:
    render_metric_card("质控异常", "3", "待处理")

# 新入院患者
render_section_header("新入院患者", "今日 0:00 至今")
new_admissions = [
    {"bed": "12A", "id": "P10234", "name": "陈**", "age": 62, "gender": "男", "diagnosis": "胃恶性肿瘤", "doctor": "王医生"},
    {"bed": "15B", "id": "P10235", "name": "刘**", "age": 48, "gender": "女", "diagnosis": "乳腺癌术后化疗", "doctor": "李医生"},
    {"bed": "18C", "id": "P10236", "name": "赵**", "age": 71, "gender": "男", "diagnosis": "多发性骨髓瘤", "doctor": "张医生"},
]
new_df = [
    {"床号": p["bed"], "患者ID": p["id"], "姓名": p["name"], "年龄": p["age"], "性别": p["gender"], "主要诊断": p["diagnosis"], "主管医生": p["doctor"]}
    for p in new_admissions
]
st.dataframe(new_df, use_container_width=True, hide_index=True)

# 重点关注患者
render_section_header("重点关注患者", "再入院风险高、住院天数异常或存在药物相互作用")
focus_patients = [
    {"name": "张**", "id": "P10001", "bed": "08A", "risk": "高", "reason": "30天内再入院，肿瘤晚期", "action": "主任查房重点讨论"},
    {"name": "李**", "id": "P10023", "bed": "11B", "risk": "中", "reason": "住院天数 > 14 天", "action": "评估出院计划"},
    {"name": "王**", "id": "P10056", "bed": "21C", "risk": "中", "reason": "药物相互作用风险", "action": "请药剂科会诊"},
    {"name": "孙**", "id": "P10089", "bed": "05A", "risk": "高", "reason": "化疗后 IV 度骨髓抑制", "action": "隔离护理，监测感染指标"},
]
for p in focus_patients:
    level_color = "#EF4444" if p["risk"] == "高" else "#F59E0B"
    st.markdown(f"""
    <div style="background: white; border: 1px solid #E5E7EB; border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div>
                <div style="font-weight: 600; font-size: 15px;">{p['name']} ({p['id']}) · 床号 {p['bed']}</div>
                <div style="color: #6B7280; font-size: 13px; margin-top: 4px;">{p['reason']}</div>
                <div style="color: #2563EB; font-size: 13px; margin-top: 6px;">💡 建议：{p['action']}</div>
            </div>
            <span style="background: {level_color}20; color: {level_color}; padding: 3px 12px; border-radius: 12px; font-size: 12px; font-weight: 500;">{p['risk']}风险</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 今日手术安排
render_section_header("今日手术安排")
surgeries = [
    {"time": "08:30", "name": "张**", "id": "P10012", "surgery": "胃癌根治术", "room": "手术室 3", "doctor": "陈主任"},
    {"time": "10:00", "name": "刘**", "id": "P10034", "surgery": "乳腺肿块切除术", "room": "手术室 2", "doctor": "王医生"},
    {"time": "14:00", "name": "赵**", "id": "P10045", "surgery": "胸腔镜肺叶切除", "room": "手术室 5", "doctor": "李主任"},
    {"time": "16:00", "name": "钱**", "id": "P10067", "surgery": "骨髓穿刺活检", "room": "手术室 1", "doctor": "张医生"},
    {"time": "18:00", "name": "孙**", "id": "P10089", "surgery": "PICC 置管", "room": "处置室", "doctor": "周护士"},
]
surgery_df = [
    {"时间": s["time"], "姓名": s["name"], "患者ID": s["id"], "手术名称": s["surgery"], "手术室": s["room"], "主刀医生": s["doctor"]}
    for s in surgeries
]
st.dataframe(surgery_df, use_container_width=True, hide_index=True)

# 质控异常
render_section_header("质控异常提醒")
qc_issues = [
    {"type": "缺失检查", "patient": "P10023 李**", "desc": "入院 3 天未记录肿瘤标志物", "owner": "李医生"},
    {"type": "住院天数异常", "patient": "P10023 李**", "desc": "住院 16 天，超过科室均值 8.3 天", "owner": "李医生"},
    {"type": "药物相互作用", "patient": "P10056 王**", "desc": "奥美拉唑 + 氯吡格雷", "owner": "张医生"},
]
for issue in qc_issues:
    type_color = {
        "缺失检查": "#F59E0B",
        "住院天数异常": "#EF4444",
        "药物相互作用": "#EF4444",
    }.get(issue["type"], "#6B7280")
    st.markdown(f"""
    <div style="background: white; border-left: 4px solid {type_color}; padding: 10px 14px; margin-bottom: 8px; border-radius: 0 8px 8px 0;">
        <div style="display: flex; justify-content: space-between;">
            <span style="font-weight: 600;">{issue['type']}</span>
            <span style="color: #6B7280; font-size: 12px;">责任人：{issue['owner']}</span>
        </div>
        <div style="color: #374151; font-size: 13px; margin-top: 4px;">{issue['patient']} · {issue['desc']}</div>
    </div>
    """, unsafe_allow_html=True)

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
