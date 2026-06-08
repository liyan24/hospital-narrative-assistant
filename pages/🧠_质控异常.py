"""
质控异常
"""
import streamlit as st
import requests
from streamlit_echarts import st_echarts
from utils.api_client import api_get, api_post, API_BASE

st.header("⚠️ 质控异常叙事分析")
st.markdown("基于知识图谱规则自动发现医疗数据中的异常模式，辅助质量改进")

col1, col2 = st.columns(2)
with col1:
    rule_type = st.selectbox(
        "选择质控维度",
        [
            ("all", "全部维度"),
            ("missing_exam", "缺失必要检查"),
            ("abnormal_los", "住院天数异常"),
            ("short_readmission", "30天内再入院"),
            ("diagnosis_drug_mismatch", "诊断-药品不匹配"),
            ("drug_interaction", "药物相互作用"),
        ],
        format_func=lambda x: x[1],
    )[0]
with col2:
    disease_name = st.text_input(
        "限定疾病名称（留空分析全局）",
        value="",
        placeholder="例如: 肺恶性肿瘤",
        key="qc_disease",
    )

if st.button("🔍 运行质控分析", type="primary"):
    with st.spinner("正在运行质控规则检测，这可能需要一些时间..."):
        params = {"rule_type": rule_type}
        if disease_name.strip():
            params["disease_name"] = disease_name.strip()

        path = "/api/narrative/quality-control?" + \
            "&".join(
                [f"{k}={requests.utils.quote(v)}" for k, v in params.items()])
        result = api_get(path, timeout=120)

        if result and result.get("narrative"):
            summary = result.get("summary", {})
            st.success(
                f"质控分析完成 | 综合风险: {summary.get('overall_risk_score', '未知')}")

            # 总体指标
            st.markdown("---")
            st.subheader("📊 总体风险指标")
            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            with mcol1:
                st.metric("缺失检查规则", summary.get(
                    "missing_exam_rules_triggered", 0))
            with mcol2:
                st.metric("住院天数异常", summary.get("abnormal_los_cases", 0))
            with mcol3:
                st.metric("30天再入院", summary.get(
                    "short_readmission_cases", 0))
            with mcol4:
                st.metric("用药不匹配", summary.get(
                    "diagnosis_drug_rules_triggered", 0))

            # 叙事
            st.markdown("---")
            st.subheader("📝 质控分析叙事")
            st.markdown(result["narrative"])

            # 详细信息
            st.markdown("---")
            st.subheader("🔎 详细异常数据")
            details = result.get("details", {})

            if details.get("missing_exams"):
                with st.expander(f"缺失必要检查 ({len(details['missing_exams'])}条规则触发)"):
                    for item in details["missing_exams"]:
                        st.markdown(
                            f"**{item['rule_name']}** — 检查率 {item['exam_rate']}% (期望≥{item['expected_rate']}%)")
                        st.write(
                            f"- 总就诊: {item['total_visits']} | 已检查: {item['with_exam']} | 缺失: {item['missing_count']}")

            if details.get("abnormal_los") and details["abnormal_los"].get("abnormal_cases"):
                with st.expander(f"住院天数异常 ({len(details['abnormal_los']['abnormal_cases'])}例)"):
                    stats = details["abnormal_los"].get("stats", {})
                    st.write(
                        f"平均住院: {stats.get('mean_los')}天 | 中位: {stats.get('median_los')}天 | 异常阈值: >{stats.get('upper_threshold')} 或 <{stats.get('lower_threshold')}")
                    st.dataframe(
                        details["abnormal_los"]["abnormal_cases"], use_container_width=True)

            if details.get("short_readmissions"):
                with st.expander(f"30天内再入院 ({len(details['short_readmissions'])}例)"):
                    st.dataframe(
                        details["short_readmissions"], use_container_width=True)

            if details.get("diagnosis_drug_mismatch"):
                with st.expander(f"诊断-药品不匹配 ({len(details['diagnosis_drug_mismatch'])}条规则触发)"):
                    for item in details["diagnosis_drug_mismatch"]:
                        st.markdown(
                            f"**{item['rule_name']}** — 用药率 {item['drug_rate']}% (期望≥{item['expected_rate']}%)")
                        st.write(
                            f"- 总就诊: {item['total_visits']} | 已用药: {item['with_drug']} | 缺失: {item['missing_count']}")

            if details.get("drug_interactions"):
                with st.expander(f"潜在药物相互作用 ({len(details['drug_interactions'])}条规则触发)"):
                    for rule in details["drug_interactions"]:
                        st.markdown(f"**{rule['rule_name']}**")
                        st.dataframe(rule.get("cases", []),
                                     use_container_width=True)
        else:
            st.error(
                f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

st.divider()
st.info("""
**质控规则说明：**
- **缺失必要检查**：如心脏病患者未做心电图、肺肿瘤患者未做CT、胃病患者未做胃镜等
- **住院天数异常**：识别住院天数显著偏离平均水平（>2.5倍标准差）的病例
- **30天内再入院**：识别同一患者出院后30天内再次入院的情况
- **诊断-药品不匹配**：如贫血未补铁、低蛋白血症未补充白蛋白等
- **药物相互作用**：识别可能存在相互作用的药品组合（需人工复核）

**注意：** 所有异常均为基于规则的统计提示，最终需结合临床实际人工判断。
""")

