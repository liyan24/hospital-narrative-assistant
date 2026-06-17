"""
查房助手
基于知识图谱和病历数据回答医生问题，答案可溯源
"""
import streamlit as st
from utils.ui_style import apply_global_style, render_section_header
from utils.api_client import api_get, api_post

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
        # 加载患者基本信息
        patient_info = api_get(f"/api/narrative/patient/storyline/{patient_id}", timeout=30)
        if patient_info and patient_info.get("status") == "ok":
            patient = patient_info.get("patient", {}) or {}
            visits = (patient_info.get("timeline", {}) or {}).get("visits", [])
            current_visit = visits[-1] if visits else {}
            current_diagnoses = [d.get("display_name", d.get("name", "")) for d in current_visit.get("diseases", []) if d.get("display_name") or d.get("name")]
            st.markdown(f"""
            <div style="background: #F3F4F6; padding: 12px; border-radius: 8px; font-size: 13px;">
                <div><strong>{patient.get('patient_id', patient_id)}</strong></div>
                <div style="color: #6B7280; margin-top: 4px;">{patient.get('age', '-')}岁 · {patient.get('gender', '-')}</div>
                <div style="color: #6B7280; margin-top: 4px;">{' · '.join(current_diagnoses[:3]) if current_diagnoses else '暂无诊断'}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("未找到该患者信息")

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
    voice_clicked = st.button("🎙️ 语音", use_container_width=True)
    if voice_clicked:
        st.info("语音输入功能需后续对接语音识别服务")
with col2:
    ask_clicked = st.button("💬 发送", use_container_width=True, type="primary")

if voice_clicked:
    st.stop()

if ask_clicked and question:
    with st.spinner("思考中..."):
        # 如果设置了患者ID，把患者ID加入问题
        final_question = question
        if patient_id:
            final_question = f"患者 {patient_id}：{question}"

        result = api_get(f"/api/narrative/rag/ask?question={final_question}", timeout=120)

        if result and result.get("status") == "ok":
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            retrieved = result.get("retrieved", {})

            st.markdown(f"""
            <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px; padding: 20px; margin-top: 16px;">
                <div style="font-weight: 600; font-size: 16px; margin-bottom: 12px;">回答</div>
                <div style="line-height: 1.8; color: #1F2937;">{answer.replace(chr(10), '<br>')}</div>
            </div>
            """, unsafe_allow_html=True)

            render_section_header("答案溯源", "以下数据来源支撑了上述回答")

            # 从 retrieved 中提取溯源信息
            source_items = []
            rtype = retrieved.get("type", "")
            if rtype == "patient_timeline":
                visits = retrieved.get("visits", [])
                for v in visits[:5]:
                    source_items.append({"type": "visit", "id": v.get("visit_id", ""), "desc": f"就诊 {v.get('admission_date', '')}"})
            elif rtype == "disease_pathway":
                source_items.append({"type": "disease", "id": retrieved.get("disease_name", ""), "desc": "疾病诊疗路径统计"})
            elif rtype == "drug_pattern":
                source_items.append({"type": "drug", "id": retrieved.get("drug_name", ""), "desc": "用药模式统计"})
            elif rtype == "comorbidity":
                source_items.append({"type": "disease", "id": retrieved.get("target_disease", ""), "desc": "合并症网络统计"})
            elif rtype == "readmission_summary":
                source_items.append({"type": "stats", "id": "readmission", "desc": "再入院全局统计"})

            # 同时展示 sources 字符串
            for s in sources[:5]:
                source_items.append({"type": "source", "id": "", "desc": s})

            if source_items:
                for source in source_items:
                    icon = {"lab": "🧪", "exam": "🩻", "order": "💊", "visit": "📋", "disease": "🦠", "drug": "💊", "stats": "📊", "source": "📄"}.get(source["type"], "📄")
                    st.markdown(f"""
                    <div style="background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; font-size: 13px;">
                        {icon} <strong>{source['id']}</strong> · {source['desc']}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("未找到具体数据来源")

            st.info("⚠️ 本回答仅供临床参考，不构成最终诊疗建议，请结合患者实际情况判断。")

            # 反馈按钮
            f1, f2, f3 = st.columns([1, 1, 4])
            with f1:
                st.button("👍 有用", key="feedback_good")
            with f2:
                st.button("👎 不准确", key="feedback_bad")
        else:
            error_msg = result.get("detail", "未知错误") if result else "接口调用失败"
            st.error(f"问答失败：{error_msg}")

# 历史问答（存储在 session_state 中）
render_section_header("历史问答")
if "qa_history" not in st.session_state:
    st.session_state["qa_history"] = []

if ask_clicked and result and result.get("status") == "ok":
    st.session_state["qa_history"].insert(0, {
        "question": question,
        "answer": result.get("answer", "")[:200] + "...",
        "time": "刚刚",
    })

if st.session_state["qa_history"]:
    for h in st.session_state["qa_history"][:10]:
        with st.expander(f"{h['question']} · {h['time']}", expanded=False):
            st.write(h["answer"])
else:
    st.caption("暂无历史问答")
