"""
患者全息视图
整合患者历次就诊、诊断、用药、检查、手术时间线
"""
import streamlit as st
from utils.ui_style import apply_global_style, render_section_header, render_card
from utils.api_client import api_get

apply_global_style()

st.header("👤 患者全息视图")
st.caption("整合患者历次就诊、诊断、用药、检查、手术，3 分钟掌握患者全貌")

# 患者搜索
search_col1, search_col2 = st.columns([4, 1])
with search_col1:
    patient_id = st.text_input(
        "输入患者ID",
        value=st.session_state.get("selected_patient_id", ""),
        placeholder="例如：P000001",
        label_visibility="collapsed",
    )
with search_col2:
    st.write("")
    st.write("")
    search_clicked = st.button("🔍 查询", use_container_width=True, type="primary")

if search_clicked and patient_id:
    st.session_state["selected_patient_id"] = patient_id

if patient_id:
    # 调用真实 API 获取患者故事线
    with st.spinner("加载患者数据..."):
        storyline = api_get(f"/api/narrative/patient/storyline/{patient_id}", timeout=60)
        risk_data = api_get(f"/api/narrative/risk-prediction?patient_id={patient_id}&top_n=10", timeout=60)
        qc_data = api_get(f"/api/narrative/patient/{patient_id}/quality-control", timeout=60)

    if not storyline or storyline.get("status") != "ok":
        error_msg = storyline.get("detail", "患者不存在或加载失败") if storyline else "接口调用失败"
        st.warning(error_msg)
        st.stop()

    patient = storyline.get("patient", {}) or {}
    timeline = storyline.get("timeline", {}) or {}
    visits = timeline.get("visits", []) if timeline else []
    narrative = storyline.get("narrative", "")

    st.divider()

    # 患者基本信息
    render_section_header("基本信息")
    info_col1, info_col2, info_col3, info_col4, info_col5 = st.columns(5)
    with info_col1:
        render_card("患者ID", patient.get("patient_id", patient_id))
    with info_col2:
        render_card("年龄", f"{patient.get('age', '-')} 岁")
    with info_col3:
        render_card("性别", patient.get("gender", "-"))
    with info_col4:
        render_card("婚姻", patient.get("marital_status", "-"))
    with info_col5:
        render_card("入院次数", f"{len(visits)} 次")

    # 关键指标与风险
    render_section_header("关键指标")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        risk_level = risk_data.get("risk_level", "-") if risk_data else "-"
        risk_score = risk_data.get("risk_score", "-") if risk_data else "-"
        st.metric("再入院风险", risk_level, f"评分 {risk_score}")
    with k2:
        avg_los = round(sum(v.get('length_of_stay', 0) or 0 for v in visits) / len(visits), 1) if visits else "-"
        st.metric("平均住院日", f"{avg_los} 天", "本次入院")
    with k3:
        disease_count = len(set(d.get("name") for v in visits for d in v.get("diseases", []) if d.get("name")))
        st.metric("诊断数", f"{disease_count} 种", "多病共存")
    with k4:
        drug_count = len(set(d.get("name") for v in visits for d in v.get("drugs", []) if d.get("name")))
        st.metric("用药数", f"{drug_count} 种", "需关注相互作用")

    # 异常提醒
    render_section_header("异常提醒", "系统自动识别的需要关注事项")
    issues = qc_data.get("issues", []) if qc_data and qc_data.get("status") == "ok" else []
    if issues:
        for issue in issues:
            level = issue.get("level", "warning")
            color = "#F59E0B" if level == "warning" else "#EF4444"
            st.markdown(f"""
            <div style="background: white; border-left: 4px solid {color}; padding: 12px 16px; margin-bottom: 10px; border-radius: 0 8px 8px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                <div style="font-weight: 600;">{issue['type']}</div>
                <div style="color: #6B7280; font-size: 13px; margin-top: 4px;">{issue['description']}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ 未发现明显质控异常")

    # 就诊时间线
    render_section_header("就诊时间线")
    if visits:
        for v in visits:
            diseases = [d.get("display_name", d.get("name", "")) for d in v.get("diseases", []) if d.get("display_name") or d.get("name")]
            drugs = [d.get("name", "") for d in v.get("drugs", []) if d.get("name")]
            surgeries = [s.get("name", "") for s in v.get("surgeries", []) if s.get("name")]

            tags = []
            if surgeries:
                tags.append("手术")
            if len(drugs) > 5:
                tags.append("复杂用药")
            if v.get("length_of_stay", 0) and v["length_of_stay"] > 14:
                tags.append("超长住院")

            tags_html = "".join([
                f'<span style="background: #EFF6FF; color: #2563EB; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-right: 6px;">{t}</span>'
                for t in tags
            ])

            desc_parts = []
            if v.get("chief_complaint"):
                desc_parts.append(f"主诉：{v['chief_complaint']}")
            if diseases:
                desc_parts.append(f"诊断：{', '.join(diseases[:5])}")
            if drugs:
                desc_parts.append(f"用药：{', '.join(drugs[:5])}")
            if surgeries:
                desc_parts.append(f"手术：{', '.join(surgeries[:3])}")

            st.markdown(f"""
            <div class="timeline-item">
                <div class="timeline-date">{v.get('admission_date', '')} ~ {v.get('discharge_date', '在院')}</div>
                <div class="timeline-title">第 {visits.index(v) + 1} 次入院 · 住院 {v.get('length_of_stay', '-')} 天</div>
                <div class="timeline-desc">{'；'.join(desc_parts)}</div>
                <div style="margin-top: 8px;">{tags_html}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("暂无就诊记录")

    # 当前就诊详情
    current_visit = visits[-1] if visits else None
    if current_visit:
        render_section_header("当前就诊详情", "本次入院诊断、用药、检查、手术")

        tab1, tab2, tab3, tab4 = st.tabs(["诊断", "用药", "检查", "手术"])
        with tab1:
            diagnosis_data = []
            for d in current_visit.get("diseases", []):
                diagnosis_data.append({
                    "类型": {"western": "西医", "tcm": "中医", "tcm_syndrome": "中医证型"}.get(d.get("type", ""), d.get("type", "")),
                    "名称": d.get("display_name", d.get("name", "")),
                    "是否主诊断": "是" if d.get("is_main") else "否",
                })
            st.dataframe(diagnosis_data, use_container_width=True, hide_index=True)
        with tab2:
            drug_data = []
            for d in current_visit.get("drugs", []):
                drug_data.append({
                    "药品": d.get("name", ""),
                    "单次剂量": d.get("dosage", ""),
                    "频率": d.get("frequency", ""),
                    "给药途径": d.get("route", ""),
                    "开始时间": d.get("start_date", ""),
                })
            st.dataframe(drug_data, use_container_width=True, hide_index=True)
        with tab3:
            exam_data = []
            for e in current_visit.get("exams", []):
                exam_data.append({
                    "检查": e.get("name", ""),
                    "类别": e.get("category", ""),
                    "检查日期": e.get("exam_date", ""),
                    "描述": e.get("description", "") or e.get("diagnosis", ""),
                })
            st.dataframe(exam_data, use_container_width=True, hide_index=True)
        with tab4:
            surgery_data = []
            for s in current_visit.get("surgeries", []):
                surgery_data.append({
                    "手术": s.get("name", ""),
                    "类别": s.get("category", ""),
                    "麻醉": s.get("anesthesia_method", ""),
                    "开始时间": s.get("start_date", ""),
                })
            st.dataframe(surgery_data, use_container_width=True, hide_index=True)

    # 智能病程小结
    render_section_header("智能病程小结", "基于本次入院数据自动生成，需医生审核后使用")
    with st.expander("查看 AI 生成的患者故事线叙事", expanded=False):
        st.markdown(narrative or "暂无叙事")

    if st.button("🤖 生成 SOAP 病程小结", type="primary"):
        with st.spinner("生成中..."):
            # 使用 RAG 接口生成 SOAP 病程小结
            question = f"请为患者 {patient_id} 生成一段 SOAP 格式的病程小结，包含主观资料、客观资料、评估和计划。"
            soap_result = api_get(f"/api/narrative/rag/ask?question={question}", timeout=120)
            if soap_result and soap_result.get("status") == "ok":
                st.markdown(f"""
                <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; line-height: 1.8;">
                    {soap_result.get('answer', '').replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)
                st.info("⚠️ 以上内容由 AI 辅助生成，请医生审核确认后使用。")
            else:
                st.error("病程小结生成失败")

else:
    st.info("请输入患者ID开始查询")
