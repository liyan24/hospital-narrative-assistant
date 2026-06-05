"""
Streamlit前端：医院数据分析报告展示与导出系统。
"""
import streamlit as st
import requests
import json
from streamlit_echarts import st_echarts

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="医院叙事生成助手",
    page_icon="🏥",
    layout="wide",
)

st.title("🏥 医院叙事生成助手")
st.markdown("基于大模型的科室历史数据智能辅助平台")

st.sidebar.title("导航")

page = st.sidebar.radio(
    "选择功能",
    [
        "🏠 首页",
        "--- 📊 统计分析与报告 ---",
        "📊 数据概览",
        "📊 报告生成",
        "📊 文档导出",
        "📊 周简报",
        "--- 🧠 知识图谱叙事 ---",
        "🧠 患者故事线",
        "🧠 诊疗路径",
        "🧠 合并症分析",
        "🧠 用药模式",
        "🧠 再入院分析",
        "🧠 RAG问答",
        "🧠 图谱可视化",
        "🧠 中医特色",
        "🧠 质控异常",
        "🧠 科室运营",
        "🧠 相似患者",
        "🧠 风险预警",
        "--- ⚙️ 系统管理 ---",
        "⚙️ 知识图谱管理",
    ],
)

# 去除前缀得到实际页面名
page_clean = page.replace("🏠 ", "").replace("📊 ", "").replace("🧠 ", "").replace("⚙️ ", "")
# 分隔符不能作为实际页面
if page_clean.startswith("---"):
    page_clean = "首页"
page = page_clean


def api_get(path):
    try:
        resp = requests.get(f"{API_BASE}{path}", timeout=30)
        return resp.json()
    except Exception as e:
        st.error(f"API请求失败: {e}")
        return None


def api_post(path, params=None, json_data=None):
    try:
        resp = requests.post(f"{API_BASE}{path}", params=params, json=json_data, timeout=120)
        return resp.json()
    except Exception as e:
        st.error(f"API请求失败: {e}")
        return None


# ========== 首页 ==========
if page == "首页":
    st.markdown("<h1 style='text-align: center;'>🏥 医院叙事生成助手</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align: center; font-size: 1.2em; color: #666;'>"
        "基于大语言模型与医疗知识图谱的科室历史数据智能分析与叙事生成平台"
        "</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    # 两大板块介绍
    st.markdown("### 📋 平台简介")
    st.write(
        "本平台面向医院科室管理者与临床医生，整合科室历史运营数据，"
        "通过**大语言模型**与**Neo4j知识图谱**双引擎驱动，"
        "提供从数据统计分析到深度医疗叙事的完整智能辅助能力。"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            "<div style='padding: 20px; border-radius: 10px; background-color: #f0f7ff;'>"
            "<h3>📊 统计分析与报告</h3>"
            "<p>基于Excel原始数据进行多维度统计分析，自动生成科室数据分析报告、周简报，"
            "支持Word/PDF一键导出。</p>"
            "<ul>"
            "<li>数据概览与ECharts交互图表</li>"
            "<li>智能报告生成（LLM驱动）</li>"
            "<li>每周临床简报自动生成</li>"
            "<li>文档导出（DOCX / PDF）</li>"
            "</ul>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            "<div style='padding: 20px; border-radius: 10px; background-color: #f6fff0;'>"
            "<h3>🧠 知识图谱叙事</h3>"
            "<p>构建患者-就诊-疾病-药品-检查-手术等多实体医疗知识图谱，"
            "挖掘深层关联模式，生成专业医疗叙事。</p>"
            "<ul>"
            "<li>患者故事线与再入院分析</li>"
            "<li>疾病诊疗路径与合并症网络</li>"
            "<li>用药模式与中医特色分析</li>"
            "<li>质控异常监测与风险预警</li>"
            "<li>相似患者推荐与科室运营分析</li>"
            "</ul>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    # 系统状态与快捷操作
    st.markdown("### ⚡ 快捷操作")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("🔍 检查后端状态", use_container_width=True):
            health = api_get("/health")
            if health:
                for k, v in health.items():
                    st.write(f"- {k}: {'✅' if v else '❌'}")
    with c2:
        if st.button("📊 立即运行数据分析", use_container_width=True):
            with st.spinner("数据分析中，请稍候..."):
                result = api_post("/api/data/analysis/run", params={"analysis_id": "latest"})
                if result and result.get("status") == "ok":
                    st.success("数据分析完成！")
                else:
                    st.error("数据分析失败")
    with c3:
        if st.button("🤖 生成完整报告", use_container_width=True):
            with st.spinner("报告生成中，这可能需要几分钟..."):
                result = api_post("/api/narrative/report/generate", params={"analysis_id": "latest"})
                if result and result.get("status") == "ok":
                    st.success(f"报告生成完成！报告ID: {result.get('report_id')}")
                    st.session_state["last_report_id"] = result.get("report_id")
                else:
                    st.error("报告生成失败")
    with c4:
        if st.button("🏗️ 构建知识图谱", use_container_width=True):
            with st.spinner("知识图谱构建中，这可能需要几分钟..."):
                result = api_post("/api/kg/build", json_data={"clear": False})
                if result and result.get("success"):
                    st.success("知识图谱构建完成！")
                else:
                    st.error("构建失败")

    st.divider()

    # 数据规模展示
    st.markdown("### 📈 系统数据规模")
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
                st.info("暂无图谱数据，请点击上方「构建知识图谱」按钮")
    else:
        st.info("点击「刷新统计」查看知识图谱数据规模")

    st.divider()
    st.caption(
        "💡 **使用提示**：左侧导航栏分为「统计分析与报告」和「知识图谱叙事」两大模块，"
        "请选择对应功能开始使用。"
    )

# ========== 数据概览 ==========
elif page == "数据概览":
    st.header("📊 数据概览")

    tab1, tab2 = st.tabs(["统计指标", "交互图表"])

    with tab1:
        analysis = api_get("/api/data/analysis/latest")
        if analysis and analysis.get("status") == "ok":
            data = analysis["data"]
            st.subheader("数据来源")
            for key, val in data.get("data_sources", {}).items():
                st.write(f"- **{key}**: {val.get('file', '')} ({val.get('records', 0):,} 条记录)")

            st.subheader("基本统计")
            basic = data.get("basic_stats", {})
            st.write(f"总记录数: {basic.get('total_records', 0):,}")
            st.write(f"数据跨度: {basic.get('date_range', {}).get('start', '')} 至 {basic.get('date_range', {}).get('end', '')}")

            st.subheader("入院趋势")
            trend = data.get("admission_trend", {})
            annual = trend.get("annual", {})
            if annual.get("years"):
                df_data = {"年份": annual["years"], "入院人次": annual["counts"]}
                st.dataframe(df_data, use_container_width=True)

            st.subheader("患者特征")
            features = data.get("patient_features", {})
            age = features.get("age", {})
            st.write(f"平均年龄: {age.get('mean', '')}岁, 中位数: {age.get('median', '')}岁")
            st.write(f"年龄范围: {age.get('min', '')} - {age.get('max', '')}岁")
        else:
            st.info("暂无分析数据，请在首页点击「立即运行数据分析」")

    with tab2:
        charts_data = api_get("/api/data/analysis/latest/charts")
        if charts_data and charts_data.get("status") == "ok":
            charts = charts_data.get("charts", {})

            # 布局：每行2个图表
            chart_items = list(charts.items())
            for i in range(0, len(chart_items), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i + j < len(chart_items):
                        chart_id, chart_cfg = chart_items[i + j]
                        with cols[j]:
                            st_echarts(options=chart_cfg, height="400px", key=chart_id)
        else:
            st.info("暂无图表数据，请先运行数据分析")

# ========== 报告生成 ==========
elif page == "报告生成":
    st.header("🤖 智能报告生成")

    report_id = st.text_input("报告ID（留空则生成新报告）", value=st.session_state.get("last_report_id", ""))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 生成新报告"):
            with st.spinner("报告生成中，请稍候..."):
                result = api_post("/api/narrative/report/generate", params={"analysis_id": "latest"})
                if result and result.get("status") == "ok":
                    st.success("报告生成完成！")
                    st.session_state["last_report_id"] = result.get("report_id")
                    report_id = result.get("report_id")
                else:
                    st.error("报告生成失败")
    with col2:
        if st.button("📥 加载已有报告"):
            pass

    if report_id:
        report = api_get(f"/api/narrative/report/{report_id}")
        if report and report.get("status") == "ok":
            rpt = report["report"]
            texts = rpt.get("texts", {})
            charts = rpt.get("charts", {})

            st.subheader(rpt.get("title", "数据分析报告"))
            st.caption(f"生成时间: {rpt.get('generated_at', '')}")

            # 使用utils.report_layout进行文本与图表穿插展示
            from utils.report_layout import interleave_text_with_charts

            section_order = [
                ("basic", "一、基本统计"),
                ("admission_trend", "二、入院趋势分析"),
                ("patient_features", "三、患者特征分析"),
                ("hospitalization_days", "四、住院天数分析"),
                ("disease_types", "五、疾病类型提取分析"),
                ("readmission", "六、再入院分析"),
                ("discharge", "七、出院情况分析"),
                ("exam", "检查数据分析"),
                ("lab", "检验数据分析"),
                ("summary", "数据质量评估与总结"),
            ]

            for section_key, section_title in section_order:
                with st.expander(section_title, expanded=True):
                    text = texts.get(section_key, "")
                    blocks = interleave_text_with_charts(section_key, text, charts)
                    for block in blocks:
                        if block["type"] == "text":
                            st.markdown(block["content"])
                        elif block["type"] == "chart":
                            ck = block["chart_id"]
                            if ck in charts:
                                st_echarts(options=charts[ck], height="400px", key=f"{report_id}_{ck}")
        else:
            st.warning("报告不存在或加载失败")

# ========== 文档导出 ==========
elif page == "文档导出":
    st.header("📄 文档导出")

    report_id = st.text_input("报告ID", value=st.session_state.get("last_report_id", ""))
    fmt = st.selectbox("导出格式", ["docx", "pdf"])

    if st.button("📥 导出报告"):
        if not report_id:
            st.error("请输入报告ID")
        else:
            with st.spinner("文档生成中，请稍候..."):
                result = api_post("/api/document/report/export", params={"report_id": report_id, "fmt": fmt})
                if result and result.get("file_path"):
                    st.success("文档生成完成！")
                    download_url = result.get("download_url", "")
                    st.markdown(f"[点击下载 {fmt.upper()} 文件]({API_BASE}{download_url})")
                    # 尝试直接提供下载
                    try:
                        file_resp = requests.get(f"{API_BASE}{download_url}")
                        if file_resp.status_code == 200:
                            st.download_button(
                                label=f"下载 {fmt.upper()}",
                                data=file_resp.content,
                                file_name=download_url.split("/")[-1],
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt == "docx" else "application/pdf",
                            )
                    except Exception as e:
                        st.warning(f"直接下载失败: {e}")
                else:
                    st.error("导出失败")

# ========== 周简报 ==========
elif page == "周简报":
    st.header("📅 每周临床简报")

    week_start = st.date_input("选择周开始日期（周一）", value=None)
    week_start_str = week_start.strftime("%Y-%m-%d") if week_start else None

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 运行周分析"):
            with st.spinner("周数据分析中..."):
                result = api_post("/api/weekly/analysis/run", params={"week_start": week_start_str})
                if result and result.get("status") == "ok":
                    st.success(f"周分析完成！周期: {result.get('week_start', '最新周')}")
                    st.session_state["weekly_analysis_id"] = result.get("week_start", "latest_weekly")
                else:
                    st.error("周分析失败")
    with col2:
        if st.button("🤖 生成周简报"):
            analysis_id = st.session_state.get("weekly_analysis_id", "latest_weekly")
            with st.spinner("周简报生成中，请稍候..."):
                result = api_post("/api/weekly/report/generate", params={"analysis_id": analysis_id})
                if result and result.get("status") == "ok":
                    st.success(f"周简报生成完成！报告ID: {result.get('report_id')}")
                    st.session_state["last_weekly_report_id"] = result.get("report_id")
                else:
                    st.error("周简报生成失败")
    with col3:
        if st.button("📥 导出周简报"):
            report_id = st.session_state.get("last_weekly_report_id", "")
            if report_id:
                with st.spinner("导出中..."):
                    result = api_post("/api/weekly/report/export", params={"report_id": report_id, "fmt": "docx"})
                    if result and result.get("file_path"):
                        st.success("周简报导出完成！")
                        download_url = result.get("download_url", "")
                        st.markdown(f"[点击下载 Word 文件]({API_BASE}{download_url})")
                        try:
                            file_resp = requests.get(f"{API_BASE}{download_url}")
                            if file_resp.status_code == 200:
                                st.download_button(
                                    label="下载 Word",
                                    data=file_resp.content,
                                    file_name=download_url.split("/")[-1],
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                )
                        except Exception as e:
                            st.warning(f"直接下载失败: {e}")
                    else:
                        st.error("导出失败")
            else:
                st.error("请先生成周简报")

    # 显示周简报内容
    weekly_report_id = st.text_input("周简报报告ID", value=st.session_state.get("last_weekly_report_id", ""))
    if weekly_report_id:
        report = api_get(f"/api/weekly/report/{weekly_report_id}")
        if report and report.get("status") == "ok":
            rpt = report["report"]
            data = rpt.get("data", {})
            texts = rpt.get("texts", {})

            st.subheader(f"{rpt.get('title', '周简报')} ({data.get('week_range', '')})")

            modules = [
                ("operation", "模块1：本周运营概况"),
                ("diseases", "模块2：病种分析"),
                ("exam_lab", "模块3：检查检验汇总"),
                ("treatment", "模块4：治疗动态"),
                ("quality", "模块5：质控指标"),
                ("focus_patients", "模块6：重点关注患者"),
                ("next_week", "模块7：下周预警"),
                ("summary", "总结"),
            ]

            for section_key, section_title in modules:
                with st.expander(section_title, expanded=True):
                    text = texts.get(section_key, "")
                    if text:
                        st.markdown(text)
                    else:
                        # 显示原始数据表格
                        section_data = data.get(section_key, {})
                        if isinstance(section_data, dict):
                            for k, v in section_data.items():
                                if isinstance(v, list) and v:
                                    st.dataframe(v, use_container_width=True)
                                elif k != "week_range":
                                    st.write(f"**{k}**: {v}")
        else:
            st.warning("周简报不存在或加载失败")

# ========== 患者故事线 ==========
elif page == "患者故事线":
    st.header("👤 个体患者故事线")
    st.markdown("基于知识图谱生成某位患者的完整就诊故事线叙事")

    patient_id = st.text_input("患者ID", value="4116-002-000000000000000000000021", placeholder="例如: 4116-002-000000000000000000000021")

    if st.button("📝 生成患者故事线", type="primary"):
        if not patient_id:
            st.error("请输入患者ID")
        else:
            with st.spinner("正在从知识图谱查询患者数据并生成叙事..."):
                result = api_get(f"/api/narrative/patient/storyline/{patient_id}")
                if result and result.get("narrative"):
                    st.success(f"患者故事线生成完成！共 {result.get('visit_count', 0)} 次就诊")
                    st.markdown("---")
                    st.markdown(result["narrative"])
                else:
                    st.error(f"生成失败: {result.get('detail', '患者不存在或数据为空') if result else '无响应'}")

    st.divider()
    st.info("""
    **说明：**
    - 患者ID可从原始Excel数据中的"患者ID"列获取
    - 系统会查询该患者在知识图谱中的所有就诊记录、诊断、用药、检查、手术等信息
    - 基于真实数据用LLM生成连贯的就诊故事线
    """)

# ========== 诊疗路径 ==========
elif page == "诊疗路径":
    st.header("🛤️ 诊疗路径模式叙事")
    st.markdown("基于知识图谱挖掘某疾病的典型诊疗路径，生成科室诊疗规范叙事")

    disease_name = st.text_input("疾病名称", placeholder="例如: 肺恶性肿瘤")

    if st.button("📋 生成诊疗路径叙事", type="primary"):
        if not disease_name:
            st.error("请输入疾病名称")
        else:
            with st.spinner("正在从知识图谱分析诊疗路径..."):
                result = api_get(f"/api/narrative/pathway/{disease_name}")
                if result and result.get("narrative"):
                    st.success(f"诊疗路径叙事生成完成！疾病: {result.get('disease_name', '')}")
                    st.markdown("---")
                    st.markdown(result["narrative"])
                else:
                    st.error(f"生成失败: {result.get('detail', '未找到该疾病的诊疗数据') if result else '无响应'}")

    st.divider()
    st.info("""
    **说明：**
    - 输入疾病名称（如"肺恶性肿瘤"、"高血压"、"痰瘀互结证"等）
    - 系统会分析该疾病在本科室的：常用药品、常规检查、常见手术、合并症分布、住院天数等
    - 用LLM生成专业的诊疗路径模式叙事
    """)

# ========== 合并症分析 ==========
elif page == "合并症分析":
    st.header("🔗 疾病共现网络叙事")
    st.markdown("基于知识图谱分析合并症组合，发现疾病之间的关联模式")

    disease_name = st.text_input("疾病名称（留空分析全局模式）", placeholder="例如: 肺恶性肿瘤")

    if st.button("📊 生成共现分析", type="primary"):
        with st.spinner("正在分析疾病共现网络..."):
            if disease_name:
                result = api_get(f"/api/narrative/comorbidity/{requests.utils.quote(disease_name)}")
            else:
                result = api_get("/api/narrative/comorbidity")
            if result and result.get("narrative"):
                target = result.get("target_disease")
                if target:
                    st.success(f"疾病 '{target}' 的共现分析完成")
                else:
                    st.success("全局疾病共现分析完成")
                st.markdown("---")
                st.markdown(result["narrative"])
            else:
                st.error(f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

    st.divider()
    st.info("""
    **说明：**
    - 输入疾病名称：分析该疾病的常见合并症、中医证型分布、三元疾病组合
    - 留空：分析全科室最常见的合并症对
    - 基于同一次就诊中的多个诊断建立共现关系
    """)

# ========== 用药模式 ==========
elif page == "用药模式":
    st.header("💊 用药模式与合理性叙事")
    st.markdown("基于知识图谱分析药品共现网络、常用药组合和潜在问题")

    disease_name = st.text_input("疾病名称（留空分析全局模式）", placeholder="例如: 肺恶性肿瘤")

    if st.button("📋 生成用药分析", type="primary"):
        with st.spinner("正在分析用药模式..."):
            if disease_name:
                result = api_get(f"/api/narrative/drug-pattern/{requests.utils.quote(disease_name)}")
            else:
                result = api_get("/api/narrative/drug-pattern")
            if result and result.get("narrative"):
                target = result.get("disease_name")
                if target:
                    st.success(f"疾病 '{target}' 的用药分析完成")
                else:
                    st.success("全局用药模式分析完成")
                st.markdown("---")
                st.markdown(result["narrative"])
            else:
                st.error(f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

    st.divider()
    st.info("""
    **说明：**
    - 输入疾病名称：分析该疾病的常用药组合、中西医结合用药特点
    - 留空：分析全科室最常用的药品和组合对
    - 自动识别潜在的用药问题（如重复用药、相互作用风险）
    """)

# ========== 再入院分析 ==========
elif page == "再入院分析":
    st.header("🔄 再入院患者时间线叙事")
    st.markdown("识别多次就诊患者，分析再入院模式和纵向诊疗历程")

    tab1, tab2 = st.tabs(["整体分析", "个体患者叙事"])

    with tab1:
        if st.button("📈 生成再入院整体分析", type="primary"):
            with st.spinner("正在分析再入院数据..."):
                result = api_get("/api/narrative/readmission/summary")
                if result and result.get("narrative"):
                    st.success("再入院整体分析完成")
                    st.markdown("---")
                    st.markdown(result["narrative"])
                    # 显示统计
                    stats = result.get("stats", {})
                    if stats:
                        st.divider()
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("总患者数", stats.get("total_patients", 0))
                        with col2:
                            st.metric("再入院患者", stats.get("readmit_patients", 0))
                        with col3:
                            st.metric("再入院率", f"{stats.get('readmit_rate', 0)}%")
                else:
                    st.error(f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

    with tab2:
        patient_id = st.text_input("患者ID", value="4116-002-000000000000000000000021", placeholder="例如: 4116-002-000000000000000000000021", key="readmit_patient")
        if st.button("📝 生成患者纵向叙事", key="readmit_btn"):
            if not patient_id:
                st.error("请输入患者ID")
            else:
                with st.spinner("正在查询患者多次就诊记录..."):
                    result = api_get(f"/api/narrative/readmission/patient/{patient_id}")
                    if result and result.get("narrative"):
                        st.success(f"患者纵向叙事生成完成！共 {result.get('visit_count', 0)} 次就诊")
                        st.markdown("---")
                        st.markdown(result["narrative"])
                    else:
                        st.error(f"生成失败: {result.get('detail', '患者不存在或仅就诊1次') if result else '无响应'}")

    st.divider()
    st.info("""
    **说明：**
    - **整体分析**：统计科室再入院率、间隔分布、高发疾病，识别管理改进点
    - **个体叙事**：追踪特定患者多次就诊的完整历程，分析病情演变和治疗调整
    - 再入院定义为同一患者有2次及以上就诊记录
    """)

# ========== 知识图谱 ==========
elif page == "知识图谱管理":
    st.header("🧠 医疗知识图谱")
    st.markdown("从Excel数据中提取实体（患者、疾病、药品、检查、手术等）构建Neo4j知识图谱")

    # 连接状态
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔌 测试Neo4j连接"):
            health = api_get("/health")
            if health:
                st.write("后端服务状态: ✅")
            else:
                st.write("后端服务状态: ❌")

            # 直接测试Neo4j
            try:
                stats = api_get("/api/kg/stats")
                if stats:
                    st.success("Neo4j连接成功！")
                else:
                    st.error("Neo4j连接失败")
            except Exception as e:
                st.error(f"Neo4j连接失败: {e}")

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
            result = api_post("/api/kg/build", json_data={"clear": clear_existing})
            if result and result.get("success"):
                st.success(result.get("message", "构建完成！"))
            else:
                st.error(f"构建失败: {result.get('detail', '未知错误') if result else '无响应'}")

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
    query = st.text_area("Cypher语句", value="MATCH (n) RETURN labels(n)[0] as label, count(n) as cnt ORDER BY cnt DESC")
    if st.button("▶️ 执行查询"):
        if query.strip():
            result = api_get(f"/api/kg/query?cypher={requests.utils.quote(query.strip())}")
            if result:
                st.write("**查询结果：**")
                st.json(result)
            else:
                st.error("查询失败")
        else:
            st.warning("请输入查询语句")


# ========== RAG问答 ==========
elif page == "RAG问答":
    st.header("🤖 LLM + 知识图谱 RAG 问答")
    st.markdown("基于 Neo4j 知识图谱的真实关系子图回答您的问题，避免大模型编造")

    question = st.text_area(
        "请输入您的问题",
        value="患者 4116-002-000000000000000000000021 最后一次就诊的诊断是什么？",
        placeholder="例如：肺恶性肿瘤的常用药品有哪些？/ 高血压常见的合并症是什么？",
        height=80,
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        ask_clicked = st.button("💬 提问", type="primary")

    if ask_clicked:
        if not question.strip():
            st.error("请输入问题")
        else:
            with st.spinner("正在检索知识图谱并生成回答..."):
                result = api_post("/api/narrative/rag/ask", json_data={"question": question.strip()})
                if result and result.get("answer"):
                    st.markdown("---")
                    st.subheader("💡 回答")
                    st.markdown(result["answer"])

                    st.markdown("---")
                    st.subheader("📚 数据来源")
                    for src in result.get("sources", []):
                        st.caption(f"- {src}")

                    with st.expander("查看检索到的原始数据"):
                        st.json(result.get("retrieved", {}))
                else:
                    st.error(f"回答失败: {result.get('detail', '未知错误') if result else '无响应'}")

    st.divider()
    st.info("""
    **示例问题：**
    - 患者 4116-002-000000000000000000000021 最后一次就诊的诊断是什么？
    - 肺恶性肿瘤的常用药品有哪些？
    - 高血压常见的合并症是什么？
    - 本科室的再入院率是多少？
    """)

# ========== 图谱可视化 ==========
elif page == "图谱可视化":
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
                result = api_get(f"/api/kg/subgraph/patient/{patient_id}?max_visits={max_visits}")
                if result and result.get("nodes") is not None:
                    graph_data = result
                else:
                    error_msg = result.get("detail", "查询失败") if result else "无响应"

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
                result = api_get(f"/api/kg/subgraph/disease/{enc}?top_n={top_n}")
                if result and result.get("nodes") is not None:
                    graph_data = result
                else:
                    error_msg = result.get("detail", "查询失败") if result else "无响应"

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
                    result = api_get(f"/api/kg/subgraph/drug-pattern?top_n={top_n}")
                else:
                    enc = requests.utils.quote(disease_name)
                    result = api_get(f"/api/kg/subgraph/drug-pattern/{enc}?top_n={top_n}")
                if result and result.get("nodes") is not None:
                    graph_data = result
                else:
                    error_msg = result.get("detail", "查询失败") if result else "无响应"

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
                    result = api_get(f"/api/kg/subgraph/comorbidity?top_n={top_n}")
                else:
                    enc = requests.utils.quote(disease_name)
                    result = api_get(f"/api/kg/subgraph/comorbidity/{enc}?top_n={top_n}")
                if result and result.get("nodes") is not None:
                    graph_data = result
                else:
                    error_msg = result.get("detail", "查询失败") if result else "无响应"

    if error_msg:
        st.error(error_msg)

    if graph_data:
        nodes = graph_data.get("nodes", [])
        links = graph_data.get("links", [])
        stats = graph_data.get("stats", {})
        categories = graph_data.get("categories", [])
        title = graph_data.get("title", "知识图谱")

        st.success(f"{title} 加载完成 | 节点: {stats.get('nodes', 0)} | 边: {stats.get('links', 0)}")

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
            n["category_idx"] = cat_names.index(n["category"]) if n["category"] in cat_names else 0
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
                            "id": n["id"],
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
                            "source": l["source"],
                            "target": l["target"],
                            "value": l.get("value", 1),
                        }
                        for l in links
                    ],
                    "categories": [{"name": c["name"]} for c in categories],
                    "roam": True,
                    "label": {"show": True, "position": "right", "fontSize": 10},
                    "force": {
                        "repulsion": 300,
                        "edgeLength": [50, 150],
                    },
                    "emphasis": {
                        "focus": "adjacency",
                        "lineStyle": {"width": 4},
                    },
                    "lineStyle": {"curveness": 0.2},
                }
            ],
        }

        st_echarts(options=echart_options, height="600px", key=f"kg_viz_{viz_type}")

        # 节点表格
        with st.expander("查看节点数据"):
            st.dataframe(
                [{"ID": n["id"], "名称": n["name"], "类型": n["label"], "分类": n["category"]} for n in nodes],
                use_container_width=True,
            )

        # 关系表格
        with st.expander("查看关系数据"):
            st.dataframe(
                [{"源节点": l["source"], "目标节点": l["target"], "关系": l["name"], "频次": l.get("value", 1)} for l in links],
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


# ========== 中医特色叙事 ==========
elif page == "中医特色":
    st.header("🌿 中医特色叙事增强")
    st.markdown("基于知识图谱分析中医证型-用药关联、中西医结合对比、证型分布趋势")

    tab1, tab2, tab3 = st.tabs([
        "证型-用药关联",
        "中西医结合对比",
        "证型分布趋势",
    ])

    with tab1:
        st.subheader("证型-用药关联分析")
        input_mode = st.radio("输入模式", ["中医证型", "西医疾病", "全局概览"], horizontal=True)

        if input_mode == "中医证型":
            syndrome_name = st.text_input("证型名称", value="痰瘀互结证", placeholder="例如: 痰瘀互结证")
            western_disease = None
        elif input_mode == "西医疾病":
            western_disease = st.text_input("西医疾病名称", value="肺恶性肿瘤", placeholder="例如: 肺恶性肿瘤")
            syndrome_name = None
        else:
            syndrome_name = None
            western_disease = None

        if st.button("🌿 生成证型用药叙事", type="primary"):
            with st.spinner("正在分析中医证型与用药关联..."):
                params = {}
                if syndrome_name:
                    params["syndrome_name"] = syndrome_name
                if western_disease:
                    params["western_disease"] = western_disease

                if params:
                    path = "/api/narrative/tcm/syndrome-drug?" + "&".join([f"{k}={requests.utils.quote(v)}" for k, v in params.items()])
                else:
                    path = "/api/narrative/tcm/syndrome-drug"

                result = api_get(path)
                if result and result.get("narrative"):
                    st.success(f"证型用药叙事生成完成 | 分析对象: {result.get('target', '')}")
                    st.markdown("---")
                    st.markdown(result["narrative"])

                    # 显示统计表格
                    data = result.get("data", {})
                    if data.get("syndromes"):
                        with st.expander("证型分布"):
                            st.dataframe(data["syndromes"], use_container_width=True)
                    if data.get("top_drugs"):
                        with st.expander("Top药品"):
                            st.dataframe(data["top_drugs"], use_container_width=True)
                    if data.get("tcm_drugs"):
                        with st.expander("常用中药/中成药"):
                            st.dataframe(data["tcm_drugs"], use_container_width=True)
                    if data.get("common_pairs"):
                        with st.expander("常见药品组合"):
                            st.dataframe(data["common_pairs"], use_container_width=True)
                else:
                    st.error(f"生成失败: {result.get('detail', '未知错误') if result else '无响应'}")

    with tab2:
        st.subheader("中西医结合对比分析")
        western_disease = st.text_input("西医疾病名称（留空分析全局）", value="肺恶性肿瘤", placeholder="例如: 肺恶性肿瘤", key="tcm_cmp_disease")

        if st.button("⚖️ 生成中西医结合对比叙事", type="primary"):
            with st.spinner("正在对比中西医结合治疗效果..."):
                if western_disease.strip():
                    path = f"/api/narrative/tcm/integrated-comparison?western_disease={requests.utils.quote(western_disease.strip())}"
                else:
                    path = "/api/narrative/tcm/integrated-comparison"

                result = api_get(path)
                if result and result.get("narrative"):
                    st.success(f"中西医结合对比叙事生成完成 | 分析对象: {result.get('target', '')}")
                    st.markdown("---")
                    st.markdown(result["narrative"])

                    data = result.get("data", {})
                    if data.get("comparison"):
                        with st.expander("对比数据"):
                            cmp_data = []
                            for k, v in data["comparison"].items():
                                label = "中西医结合组" if k == "integrated" else "纯西医组"
                                cmp_data.append({"组别": label, **v})
                            st.dataframe(cmp_data, use_container_width=True)
                else:
                    st.error(f"生成失败: {result.get('detail', '未知错误') if result else '无响应'}")

    with tab3:
        st.subheader("证型分布趋势分析")
        trend_mode = st.radio("分析维度", ["全局", "特定证型", "特定西医疾病"], horizontal=True, key="tcm_trend_mode")

        if trend_mode == "特定证型":
            syndrome_name = st.text_input("证型名称", value="痰瘀互结证", placeholder="例如: 痰瘀互结证", key="tcm_trend_syndrome")
            western_disease = None
        elif trend_mode == "特定西医疾病":
            western_disease = st.text_input("西医疾病名称", value="肺恶性肿瘤", placeholder="例如: 肺恶性肿瘤", key="tcm_trend_disease")
            syndrome_name = None
        else:
            syndrome_name = None
            western_disease = None

        if st.button("📈 生成证型趋势叙事", type="primary"):
            with st.spinner("正在分析证型分布趋势..."):
                params = {}
                if syndrome_name:
                    params["syndrome_name"] = syndrome_name
                if western_disease:
                    params["western_disease"] = western_disease

                if params:
                    path = "/api/narrative/tcm/trend?" + "&".join([f"{k}={requests.utils.quote(v)}" for k, v in params.items()])
                else:
                    path = "/api/narrative/tcm/trend"

                result = api_get(path)
                if result and result.get("narrative"):
                    st.success(f"证型趋势叙事生成完成 | 分析对象: {result.get('target', '')}")
                    st.markdown("---")
                    st.markdown(result["narrative"])

                    data = result.get("data", {})
                    if data.get("year_trend"):
                        with st.expander("年度趋势"):
                            st.dataframe(data["year_trend"], use_container_width=True)
                            # ECharts line chart
                            years = [x["year"] for x in data["year_trend"]]
                            counts = [x["count"] for x in data["year_trend"]]
                            if years:
                                st_echarts(options={
                                    "xAxis": {"type": "category", "data": years},
                                    "yAxis": {"type": "value"},
                                    "series": [{"type": "line", "data": counts, "smooth": True}],
                                }, height="300px", key="tcm_year_trend")
                else:
                    st.error(f"生成失败: {result.get('detail', '未知错误') if result else '无响应'}")

    st.divider()
    st.info("""
    **功能说明：**
    - **证型-用药关联**：分析特定中医证型或西医疾病下的常用中药/中成药、西药及联合用药模式
    - **中西医结合对比**：对比纯西医治疗与中西医结合治疗在住院天数等指标上的差异
    - **证型分布趋势**：分析中医证型就诊的年度/季度变化趋势
    """)


# ========== 质控异常 ==========
elif page == "质控异常":
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

            path = "/api/narrative/quality-control?" + "&".join([f"{k}={requests.utils.quote(v)}" for k, v in params.items()])
            result = api_get(path)

            if result and result.get("narrative"):
                summary = result.get("summary", {})
                st.success(f"质控分析完成 | 综合风险: {summary.get('overall_risk_score', '未知')}")

                # 总体指标
                st.markdown("---")
                st.subheader("📊 总体风险指标")
                mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                with mcol1:
                    st.metric("缺失检查规则", summary.get("missing_exam_rules_triggered", 0))
                with mcol2:
                    st.metric("住院天数异常", summary.get("abnormal_los_cases", 0))
                with mcol3:
                    st.metric("30天再入院", summary.get("short_readmission_cases", 0))
                with mcol4:
                    st.metric("用药不匹配", summary.get("diagnosis_drug_rules_triggered", 0))

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
                            st.markdown(f"**{item['rule_name']}** — 检查率 {item['exam_rate']}% (期望≥{item['expected_rate']}%)")
                            st.write(f"- 总就诊: {item['total_visits']} | 已检查: {item['with_exam']} | 缺失: {item['missing_count']}")

                if details.get("abnormal_los") and details["abnormal_los"].get("abnormal_cases"):
                    with st.expander(f"住院天数异常 ({len(details['abnormal_los']['abnormal_cases'])}例)"):
                        stats = details["abnormal_los"].get("stats", {})
                        st.write(f"平均住院: {stats.get('mean_los')}天 | 中位: {stats.get('median_los')}天 | 异常阈值: >{stats.get('upper_threshold')} 或 <{stats.get('lower_threshold')}")
                        st.dataframe(details["abnormal_los"]["abnormal_cases"], use_container_width=True)

                if details.get("short_readmissions"):
                    with st.expander(f"30天内再入院 ({len(details['short_readmissions'])}例)"):
                        st.dataframe(details["short_readmissions"], use_container_width=True)

                if details.get("diagnosis_drug_mismatch"):
                    with st.expander(f"诊断-药品不匹配 ({len(details['diagnosis_drug_mismatch'])}条规则触发)"):
                        for item in details["diagnosis_drug_mismatch"]:
                            st.markdown(f"**{item['rule_name']}** — 用药率 {item['drug_rate']}% (期望≥{item['expected_rate']}%)")
                            st.write(f"- 总就诊: {item['total_visits']} | 已用药: {item['with_drug']} | 缺失: {item['missing_count']}")

                if details.get("drug_interactions"):
                    with st.expander(f"潜在药物相互作用 ({len(details['drug_interactions'])}条规则触发)"):
                        for rule in details["drug_interactions"]:
                            st.markdown(f"**{rule['rule_name']}**")
                            st.dataframe(rule.get("cases", []), use_container_width=True)
            else:
                st.error(f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

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


# ========== 科室运营深度叙事 ==========
elif page == "科室运营":
    st.header("📈 科室运营深度叙事")
    st.markdown("基于知识图谱的多维度运营分析，支持周期对比和趋势洞察")

    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox(
            "分析周期",
            [
                ("latest_year", "最近完整年度"),
                ("latest_quarter", "最近完整季度"),
                ("latest_month", "最近完整月份"),
                ("y2024", "2024年全年"),
                ("y2023", "2023年全年"),
            ],
            format_func=lambda x: x[1],
        )[0]
    with col2:
        compare = st.checkbox("对比上一周期", value=True)

    if st.button("📊 生成运营分析报告", type="primary"):
        with st.spinner("正在从知识图谱提取运营数据并生成分析叙事，请稍候..."):
            path = f"/api/narrative/department-operation?period={period}&compare={str(compare).lower()}"
            result = api_get(path)

            if result and result.get("narrative"):
                current = result.get("current_period", {})
                previous = result.get("previous_period")
                current_metrics = result.get("current_metrics", {})
                changes = result.get("changes", {})

                st.success(f"运营分析完成 | 周期: {current.get('label', '')}")

                # 总体指标卡片
                st.markdown("---")
                st.subheader("📊 核心运营指标")
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                with c1:
                    val = current_metrics.get("visit_count", 0)
                    delta = changes.get("visit_count_change")
                    st.metric("就诊人次", f"{val:,}", f"{delta:+.1f}%" if delta is not None else None)
                with c2:
                    val = current_metrics.get("patient_count", 0)
                    delta = changes.get("patient_count_change")
                    st.metric("患者人数", f"{val:,}", f"{delta:+.1f}%" if delta is not None else None)
                with c3:
                    val = current_metrics.get("avg_los", 0)
                    delta = changes.get("avg_los_change")
                    st.metric("平均住院", f"{val}天", f"{delta:+.1f}%" if delta is not None else None)
                with c4:
                    val = current_metrics.get("surgery_rate", 0)
                    delta = changes.get("surgery_rate_change")
                    st.metric("手术率", f"{val}%", f"{delta:+.1f}%" if delta is not None else None)
                with c5:
                    val = current_metrics.get("readmit_rate", 0)
                    delta = changes.get("readmit_rate_change")
                    st.metric("再入院率", f"{val}%", f"{delta:+.1f}%" if delta is not None else None)
                with c6:
                    val = current_metrics.get("multi_disease_rate", 0)
                    delta = changes.get("multi_disease_rate_change")
                    st.metric("多病共存率", f"{val}%", f"{delta:+.1f}%" if delta is not None else None)

                # 叙事
                st.markdown("---")
                st.subheader("📝 运营分析叙事")
                st.markdown(result["narrative"])

                # 详细数据
                st.markdown("---")
                st.subheader("🔎 详细运营数据")

                dcol1, dcol2 = st.columns(2)
                with dcol1:
                    if current_metrics.get("top_diseases"):
                        with st.expander("Top 10 西医疾病", expanded=True):
                            st.dataframe(current_metrics["top_diseases"], use_container_width=True)

                    if current_metrics.get("top_drugs"):
                        with st.expander("Top 10 药品"):
                            st.dataframe(current_metrics["top_drugs"], use_container_width=True)

                    if current_metrics.get("top_comorbidities"):
                        with st.expander("Top 10 合并症对"):
                            st.dataframe(current_metrics["top_comorbidities"], use_container_width=True)

                with dcol2:
                    if current_metrics.get("top_tcm_diseases"):
                        with st.expander("Top 5 中医证型/病名", expanded=True):
                            st.dataframe(current_metrics["top_tcm_diseases"], use_container_width=True)

                    if current_metrics.get("top_exams"):
                        with st.expander("Top 5 检查"):
                            st.dataframe(current_metrics["top_exams"], use_container_width=True)

                    if current_metrics.get("top_surgeries"):
                        with st.expander("Top 5 手术"):
                            st.dataframe(current_metrics["top_surgeries"], use_container_width=True)

                # 中西医结合
                integrated = current_metrics.get("integrated", {})
                if integrated.get("total", 0) > 0:
                    with st.expander("中西医结合运营"):
                        total = integrated["total"]
                        ig_data = [
                            {"类型": "中西医结合", "人次": integrated.get("integrated", 0), "占比": f"{round(integrated.get('integrated', 0)/total*100, 1)}%"},
                            {"类型": "纯西医", "人次": integrated.get("western_only", 0), "占比": f"{round(integrated.get('western_only', 0)/total*100, 1)}%"},
                            {"类型": "纯中医", "人次": integrated.get("tcm_only", 0), "占比": f"{round(integrated.get('tcm_only', 0)/total*100, 1)}%"},
                        ]
                        st.dataframe(ig_data, use_container_width=True)
            else:
                st.error(f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

    st.divider()
    st.info("""
    **功能说明：**
    - 基于知识图谱提取科室运营核心指标（患者量、病种、用药、检查、手术、再入院等）
    - 支持最近年度/季度/月份及固定年度分析
    - 自动对比上一周期，计算环比变化
    - 融入中西医结合运营特色指标
    - 多病共存率反映患者病情复杂程度
    """)


# ========== 相似患者推荐 ==========
elif page == "相似患者":
    st.header("👥 相似患者推荐")
    st.markdown("基于知识图谱共同邻居算法，为指定患者推荐最相似的参考病例")

    patient_id = st.text_input(
        "患者ID",
        value="4116-002-000000000000000000000021",
        placeholder="例如: 4116-002-000000000000000000000021",
        key="similar_patient_id",
    )
    top_n = st.slider("推荐数量", 3, 20, 10)

    if st.button("🔍 查找相似患者", type="primary"):
        with st.spinner("正在基于知识图谱计算患者相似度..."):
            result = api_get(f"/api/narrative/similar-patients/{patient_id}?top_n={top_n}")

            if result and result.get("narrative"):
                profile = result.get("target_profile", {})
                st.success(f"相似患者查找完成 | 目标患者就诊 {profile.get('visit_count', 0)} 次")

                # 目标患者画像
                st.markdown("---")
                st.subheader("👤 目标患者画像")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("年龄", profile.get("age", "未知"))
                with col2:
                    st.metric("就诊次数", profile.get("visit_count", 0))
                with col3:
                    st.metric("西医诊断", len([d for d in profile.get("diseases", []) if "western" in d]))
                with col4:
                    st.metric("中医诊断", len([d for d in profile.get("diseases", []) if "tcm" in d]))

                with st.expander("查看完整画像"):
                    st.write("**主要诊断:**", ", ".join(profile.get("diseases", [])[:10]))
                    st.write("**主要用药:**", ", ".join(profile.get("drugs", [])[:10]))
                    st.write("**主要检查:**", ", ".join(profile.get("exams", [])[:10]))

                # 相似患者
                st.markdown("---")
                st.subheader("📝 相似患者推荐")
                st.markdown(result["narrative"])

                # 相似患者表格
                similar = result.get("similar_patients", [])
                if similar:
                    st.markdown("---")
                    st.subheader("📊 相似度排名")
                    for i, sim in enumerate(similar, 1):
                        with st.container():
                            scol1, scol2 = st.columns([1, 3])
                            with scol1:
                                st.markdown(f"**Top {i}**")
                                st.metric("相似度", f"{sim['score']:.3f}")
                                st.caption(f"就诊 {sim.get('visit_count', 0)} 次")
                            with scol2:
                                st.caption(f"患者ID: {sim['patient_id']}")
                                detail = sim.get("details", {})
                                st.write(
                                    f"疾病相似: {detail.get('disease_similarity', 0):.2f} | "
                                    f"用药相似: {detail.get('drug_similarity', 0):.2f} | "
                                    f"检查相似: {detail.get('exam_similarity', 0):.2f} | "
                                    f"手术相似: {detail.get('surgery_similarity', 0):.2f}"
                                )
                                if sim.get("common_diseases"):
                                    st.caption(f"共同诊断: {', '.join(sim['common_diseases'][:5])}")
                                if sim.get("common_drugs"):
                                    st.caption(f"共同用药: {', '.join(sim['common_drugs'][:5])}")
                            st.divider()
            else:
                st.error(f"查找失败: {result.get('detail', '未知错误') if result else '无响应'}")

    st.divider()
    st.info("""
    **算法说明：**
    - 基于知识图谱中患者-就诊-实体（疾病/药品/检查/手术/主诉）的共享关系计算相似度
    - 采用加权Jaccard相似度：疾病(35%) + 用药(25%) + 检查(20%) + 手术(15%) + 主诉(5%)
    - 先通过共同疾病快速筛选候选患者，再精确计算相似度
    - 推荐结果仅供参考，不能替代临床判断
    """)

# ========== 风险预警 ==========
elif page == "风险预警":
    st.header("⚡ 预测性叙事 / 风险预警")
    st.markdown("基于知识图谱和历史数据识别高风险患者，生成风险预警叙事")

    tab1, tab2 = st.tabs(["全局风险分析", "个体患者风险评估"])

    with tab1:
        top_n = st.slider("显示高风险患者数量", 5, 50, 20)
        if st.button("🌐 运行全局风险分析", type="primary"):
            with st.spinner("正在分析科室高风险患者..."):
                result = api_get(f"/api/narrative/risk-prediction?top_n={top_n}")

                if result and result.get("narrative"):
                    dist = result.get("score_distribution", {})
                    st.success(f"全局风险分析完成 | 极高风险: {dist.get('极高', 0)}人 | 高风险: {dist.get('高', 0)}人")

                    # 风险分布
                    st.markdown("---")
                    st.subheader("📊 风险等级分布")
                    rcol1, rcol2, rcol3, rcol4 = st.columns(4)
                    with rcol1:
                        st.metric("极高风险", dist.get("极高", 0), delta_color="inverse")
                    with rcol2:
                        st.metric("高风险", dist.get("高", 0), delta_color="inverse")
                    with rcol3:
                        st.metric("中风险", dist.get("中", 0))
                    with rcol4:
                        st.metric("低风险", dist.get("低", 0))

                    # 叙事
                    st.markdown("---")
                    st.subheader("📝 风险预警叙事")
                    st.markdown(result["narrative"])

                    # 高风险患者列表
                    patients = result.get("high_risk_patients", [])
                    if patients:
                        st.markdown("---")
                        st.subheader("🔎 高风险患者列表")
                        df_data = []
                        for p in patients:
                            df_data.append({
                                "患者ID": p["patient_id"],
                                "评分": p["risk_score"],
                                "等级": p["risk_level"],
                                "年龄": p.get("age", "-"),
                                "就诊": p["visit_count"],
                                "诊断数": p["disease_count"],
                                "风险因素": ", ".join(p["risk_factors"][:3]),
                            })
                        st.dataframe(df_data, use_container_width=True)
                else:
                    st.error(f"分析失败: {result.get('detail', '未知错误') if result else '无响应'}")

    with tab2:
        patient_id = st.text_input(
            "患者ID",
            value="4116-002-000000000000000000000021",
            placeholder="例如: 4116-002-000000000000000000000021",
            key="risk_patient_id",
        )
        if st.button("⚡ 评估患者风险", type="primary"):
            with st.spinner("正在评估患者风险..."):
                result = api_get(f"/api/narrative/risk-prediction?patient_id={patient_id}")

                if result and result.get("narrative"):
                    score = result.get("risk_score", 0)
                    level = result.get("risk_level", "未知")
                    color = {"极高": "red", "高": "orange", "中": "yellow", "低": "green"}.get(level, "gray")

                    st.success(f"风险评估完成 | 评分: {score}/100")

                    # 风险指标
                    st.markdown("---")
                    st.subheader("📊 风险指标")
                    st.markdown(f"<h2 style='color:{color}'>风险等级: {level}</h2>", unsafe_allow_html=True)
                    st.progress(min(score / 100, 1.0), text=f"风险评分: {score}/100")

                    # 风险因素
                    factors = result.get("risk_factors", [])
                    if factors:
                        st.markdown("**风险因素:**")
                        for f in factors:
                            st.warning(f)

                    # 叙事
                    st.markdown("---")
                    st.subheader("📝 风险预警叙事")
                    st.markdown(result["narrative"])
                else:
                    st.error(f"评估失败: {result.get('detail', '未知错误') if result else '无响应'}")

    st.divider()
    st.info("""
    **风险评分规则：**
    - **就诊频率**: ≥10次(+30分) / ≥5次(+20分) / ≥3次(+10分)
    - **多病共存**: ≥5种诊断(+20分) / ≥3种(+10分)
    - **住院天数**: ≥15天(+20分) / ≥10天(+10分)
    - **年龄**: ≥75岁(+15分) / ≥65岁(+10分)
    - **恶性肿瘤/终末期**: (+20分)
    - **多次手术**: ≥2次(+10分)

    **风险等级**: 极高(≥70分) | 高(50-69分) | 中(30-49分) | 低(<30分)

    **注意：** 风险评分基于统计规则，仅供参考，不能替代临床专业判断。
    """)
