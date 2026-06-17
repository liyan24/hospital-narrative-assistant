"""
查房助手
基于知识图谱和病历数据回答医生问题，答案可溯源
"""
import streamlit as st
from utils.ui_style import apply_global_style, render_section_header, render_card
from utils.api_client import api_post

apply_global_style()

st.header("🩺 查房助手")
st.caption("基于知识图谱和病历数据，为查房场景提供可溯源的智能问答")

# 患者上下文
with st.sidebar:
    st.markdown("### 📋 当前患者")
    patient_id = st.text_input(
        "患者ID",
        value=st.session_state.get("selected_patient_id", ""),
        placeholder="例如：P000001",
    )
    if patient_id:
        st.session_state["selected_patient_id"] = patient_id
        st.markdown("""
        <div style="background: #F3F4F6; padding: 12px; border-radius: 8px; font-size: 13px;">
            <div><strong>张**</strong> · 56岁 · 女</div>
            <div style="color: #6B7280; margin-top: 4px;">左肺恶性肿瘤 · 第3次入院</div>
        </div>
        """, unsafe_allow_html=True)

# 快捷问题
render_section_header("快捷问题")
quick_questions = [
    "该患者本次入院的主要诊断是什么？",
    "该患者有哪些药物相互作用风险？",
    "该患者为什么再入院风险高？",
    "该患者与相似患者的治疗方案有何不同？",
    "该患者是否按诊疗路径完成了必要检查？",
]

q_cols = st.columns(len(quick_questions))
for idx, q in enumerate(quick_questions):
    with q_cols[idx]:
        if st.button(q, key=f"quick_q_{idx}", use_container_width=True):
            st.session_state["current_question"] = q

st.divider()

# 问题输入
render_section_header("提问")
question = st.text_area(
    "输入您的问题",
    value=st.session_state.get("current_question", ""),
    placeholder="例如：该患者本次入院有哪些需要特别关注的异常指标？",
    height=80,
    label_visibility="collapsed",
)

col1, col2 = st.columns([1, 6])
with col1:
    ask_clicked = st.button("🎙️ 语音", use_container_width=True)
with col2:
    ask_clicked = st.button("💬 发送", use_container_width=True, type="primary")

if ask_clicked and question:
    with st.spinner("思考中..."):
        # 实际调用 kg_rag_service
        # result = api_post("/api/narrative/rag/ask", json_data={"question": question, "patient_id": patient_id})

        # 模拟回答
        response = {
            "answer": """根据该患者的病历数据，本次入院需要特别关注以下异常指标：

1. **白细胞计数降低**：2024-03-16 血常规显示白细胞 2.8×10⁹/L，考虑为化疗后骨髓抑制，建议监测并评估是否需升白治疗。

2. **肿瘤标志物未检测**：本次入院尚未记录肿瘤标志物检测，建议按诊疗路径完善。

3. **药物相互作用风险**：奥美拉唑与氯吡格雷联用可能降低抗血小板效果，如患者需长期抗血小板治疗，建议评估质子泵抑制剂选择。

建议下一步：复查血常规、完善肿瘤标志物、请药剂科会诊评估用药方案。""",
            "sources": [
                {"type": "lab", "id": "LAB20240316001", "desc": "血常规 2024-03-16"},
                {"type": "exam", "id": "EXAM20240315001", "desc": "胸部CT 2024-03-15"},
                {"type": "order", "id": "ORD20240315003", "desc": "医嘱-奥美拉唑 2024-03-15"},
            ],
            "confidence": "高",
        }

        st.markdown("""
        <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px; padding: 20px; margin-top: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span style="font-weight: 600; font-size: 16px;">回答</span>
                <span style="background: #D1FAE5; color: #065F46; padding: 2px 10px; border-radius: 12px; font-size: 12px;">置信度：{}</span>
            </div>
            <div style="line-height: 1.8; color: #1F2937;">{}</div>
        </div>
        """.format(response["confidence"], response["answer"].replace("\n", "<br>")), unsafe_allow_html=True)

        render_section_header("答案溯源", "以下数据来源支撑了上述回答")
        for source in response["sources"]:
            icon = {"lab": "🧪", "exam": "🩻", "order": "💊", "visit": "📋"}.get(source["type"], "📄")
            st.markdown(f"""
            <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; font-size: 13px;">
                {icon} <strong>{source['id']}</strong> · {source['desc']}
            </div>
            """, unsafe_allow_html=True)

        st.info("⚠️ 本回答仅供临床参考，不构成最终诊疗建议，请结合患者实际情况判断。")

        # 反馈按钮
        f1, f2, f3 = st.columns([1, 1, 4])
        with f1:
            st.button("👍 有用", key="feedback_good")
        with f2:
            st.button("👎 不准确", key="feedback_bad")

# 历史问答
render_section_header("历史问答")
history = [
    {"question": "该患者本次入院的主要诊断是什么？", "answer": "左肺恶性肿瘤（腺癌），伴有高血压。", "time": "2024-03-18 08:30"},
    {"question": "该患者有哪些药物相互作用风险？", "answer": "奥美拉唑可能降低氯吡格雷的抗血小板效果。", "time": "2024-03-18 09:15"},
]
for h in history:
    with st.expander(f"{h['question']} · {h['time']}", expanded=False):
        st.write(h["answer"])
