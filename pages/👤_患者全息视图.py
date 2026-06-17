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

# 模拟患者数据（实际应调用 API）
if patient_id:
    # 这里应该调用 patient_narrative_service 的 API
    # result = api_get(f"/api/narrative/patient/storyline/{patient_id}")

    # 模拟展示
    st.divider()

    # 患者基本信息
    render_section_header("基本信息")
    info_col1, info_col2, info_col3, info_col4, info_col5 = st.columns(5)
    with info_col1:
        render_card("患者ID", patient_id)
    with info_col2:
        render_card("年龄", "56 岁")
    with info_col3:
        render_card("性别", "女")
    with info_col4:
        render_card("婚姻", "已婚")
    with info_col5:
        render_card("入院次数", "3 次")

    # 关键指标与风险
    render_section_header("关键指标")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("再入院风险", "高", "30 天内再入院")
    with k2:
        st.metric("平均住院日", "11.5 天", "高于科室均值")
    with k3:
        st.metric("诊断数", "7 种", "多病共存")
    with k4:
        st.metric("用药数", "12 种", "需关注相互作用")

    # 异常提醒
    render_section_header("异常提醒", "系统自动识别的需要关注事项")
    alerts = [
        ("⚠️", "30 天内再入院", "该患者 28 天前因同一诊断入院，建议评估治疗方案", "warning"),
        ("💊", "药物相互作用", "奥美拉唑与氯吡格雷联用可能降低抗血小板效果", "danger"),
        ("📋", "缺失检查", "本次入院未记录肿瘤标志物检测", "warning"),
    ]
    for icon, title, desc, level in alerts:
        color = "#F59E0B" if level == "warning" else "#EF4444"
        st.markdown(f"""
        <div style="background: white; border-left: 4px solid {color}; padding: 12px 16px; margin-bottom: 10px; border-radius: 0 8px 8px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <div style="font-weight: 600;">{icon} {title}</div>
            <div style="color: #6B7280; font-size: 13px; margin-top: 4px;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    # 就诊时间线
    render_section_header("就诊时间线")
    timeline_data = [
        {
            "date": "2024-03-15",
            "title": "第 3 次入院 · 肿瘤血液科",
            "desc": "主诉：乏力、纳差1月余。诊断：左肺恶性肿瘤、高血压。入院西医主要诊断：左肺恶性肿瘤。",
            "tags": ["当前在院", "化疗周期 3"],
        },
        {
            "date": "2024-02-20",
            "title": "第 2 次入院 · 肿瘤血液科",
            "desc": "化疗后骨髓抑制入院。住院 8 天，出院带药：重组人粒细胞刺激因子。",
            "tags": ["化疗", "骨髓抑制"],
        },
        {
            "date": "2024-01-10",
            "title": "第 1 次入院 · 肿瘤血液科",
            "desc": "首次确诊左肺恶性肿瘤，行肺穿刺活检。住院 12 天，出院诊断：左肺恶性肿瘤（腺癌）。",
            "tags": ["确诊", "活检"],
        },
    ]
    for item in timeline_data:
        tags_html = "".join([f'<span style="background: #EFF6FF; color: #2563EB; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-right: 6px;">{t}</span>' for t in item["tags"]])
        st.markdown(f"""
        <div class="timeline-item">
            <div class="timeline-date">{item['date']}</div>
            <div class="timeline-title">{item['title']}</div>
            <div class="timeline-desc">{item['desc']}</div>
            <div style="margin-top: 8px;">{tags_html}</div>
        </div>
        """, unsafe_allow_html=True)

    # 当前就诊详情
    render_section_header("当前就诊详情", "本次入院诊断、用药、检查、手术")

    tab1, tab2, tab3, tab4 = st.tabs(["诊断", "用药", "检查", "手术"])
    with tab1:
        diagnosis_data = [
            {"类型": "西医主要诊断", "名称": "左肺恶性肿瘤", "是否主诊断": "是"},
            {"类型": "西医次要诊断", "名称": "高血压", "是否主诊断": "否"},
            {"类型": "中医诊断", "名称": "肺积", "是否主诊断": "否"},
            {"类型": "中医证型", "名称": "痰瘀互结证", "是否主诊断": "否"},
        ]
        st.dataframe(diagnosis_data, use_container_width=True, hide_index=True)
    with tab2:
        drug_data = [
            {"药品": "紫杉醇", "单次剂量": "175mg/m²", "频率": "D1", "给药途径": "静脉滴注", "开始时间": "2024-03-16"},
            {"药品": "卡铂", "单次剂量": "AUC 5", "频率": "D1", "给药途径": "静脉滴注", "开始时间": "2024-03-16"},
            {"药品": "奥美拉唑", "单次剂量": "40mg", "频率": "QD", "给药途径": "静脉注射", "开始时间": "2024-03-15"},
        ]
        st.dataframe(drug_data, use_container_width=True, hide_index=True)
    with tab3:
        exam_data = [
            {"检查": "胸部CT", "部位": "胸部", "检查日期": "2024-03-15", "报告日期": "2024-03-16", "诊断": "左肺占位"},
            {"检查": "血常规", "部位": "静脉血", "检查日期": "2024-03-16", "报告日期": "2024-03-16", "诊断": "白细胞降低"},
        ]
        st.dataframe(exam_data, use_container_width=True, hide_index=True)
    with tab4:
        surgery_data = [
            {"手术": "CT引导下肺穿刺活检", "类别": "诊断性操作", "等级": "二级", "麻醉": "局部麻醉", "开始时间": "2024-03-17 09:30"},
        ]
        st.dataframe(surgery_data, use_container_width=True, hide_index=True)

    # 智能病程小结
    render_section_header("智能病程小结", "基于本次入院数据自动生成，需医生审核后使用")
    if st.button("🤖 生成病程小结", type="primary"):
        with st.spinner("生成中..."):
            # 实际调用 narrative_service 或专门的小结生成 API
            st.markdown("""
            <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; line-height: 1.8;">
                <p><strong>S（主观）：</strong>患者乏力、纳差1月余，无发热、咯血。</p>
                <p><strong>O（客观）：</strong>胸部CT提示左肺占位，血常规示白细胞降低。既往高血压病史。</p>
                <p><strong>A（评估）：</strong>左肺恶性肿瘤（腺癌）化疗后骨髓抑制，目前处于第3周期化疗中。</p>
                <p><strong>P（计划）：</strong>继续监测血常规，必要时给予升白治疗；评估化疗反应。</p>
            </div>
            """, unsafe_allow_html=True)
            st.info("⚠️ 以上内容由 AI 辅助生成，请医生审核确认后使用。")

else:
    st.info("请输入患者ID开始查询")
