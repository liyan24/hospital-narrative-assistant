"""
叙事生成服务：基于统计数据使用大模型生成报告文本。
"""
from services.llm_service import llm_service
from services.data_analysis_service import data_analysis_service
from services.chart_service import chart_service
from database.json_store import json_store
import uuid


class NarrativeService:
    def __init__(self):
        self.llm = llm_service

    def _build_prompt(self, section: str, data: dict) -> str:
        """构建各章节的提示词"""
        prompts = {
            "basic": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的基本统计数据，撰写"一、基本统计"章节的专业分析文本（300字以内）。
要求：中文，专业严谨，包含关键数据。
数据：{data}""",
            "admission_trend": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的入院趋势统计数据，撰写"二、入院趋势分析"章节的专业分析文本（400字以内），包含年度趋势、月度分布、季度特征三个小节。
要求：中文，专业严谨，指出增长趋势和季节性特征，包含关键数据。
数据：{data}""",
            "patient_features": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的患者特征统计数据，撰写"三、患者特征分析"章节的专业分析文本（500字以内），包含年龄分布、婚姻状况、职业分布、入院次数四个小节。
要求：中文，专业严谨，分析患者群体特征，指出数据质量问题，包含关键数据。
数据：{data}""",
            "hospitalization_days": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的住院天数统计数据，撰写"四、住院天数分析"章节的专业分析文本（400字以内），包含基本统计、分段分布、超长住院、超短住院四个小节。
要求：中文，专业严谨，分析住院天数特征及可能原因，包含关键数据。
数据：{data}""",
            "disease_types": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的疾病类型统计数据，撰写"五、疾病类型提取分析"章节的专业分析文本（400字以内），包含疾病类型Top15和季节性分布两个小节。
要求：中文，专业严谨，分析病种构成和季节性规律，包含关键数据。
数据：{data}""",
            "readmission": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的再入院统计数据，撰写"六、再入院分析"章节的专业分析文本（400字以内），包含再入院率、间隔时间、高频患者特征三个小节。
要求：中文，专业严谨，分析再入院特征及其临床意义，包含关键数据。
数据：{data}""",
            "discharge": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的出院情况统计数据，撰写"七、出院情况分析"章节的专业分析文本（400字以内），包含出院时间分布、病种与住院天数关系、出院结局三个小节。
要求：中文，专业严谨，分析出院特征，指出数据质量问题，包含关键数据。
数据：{data}""",
            "exam": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的检查数据统计，撰写"检查数据分析"章节的专业分析文本（500字以内），包含基本统计、检查类型分布、时间趋势、阳性率、报告间隔五个小节。
要求：中文，专业严谨，分析检查工作量和效率，包含关键数据。
数据：{data}""",
            "lab": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的检验数据统计，撰写"检验数据分析"章节的专业分析文本（500字以内），包含基本统计、样本种类、检验类型、时间趋势、异常指标、肿瘤标志物六个小节。
要求：中文，专业严谨，分析检验工作量和异常指标特征，包含关键数据。
数据：{data}""",
            "summary": """你是一位资深医院数据分析师。请根据以下肿瘤血液科的全部统计数据，撰写一段300字以内的数据质量评估与总结。
要求：中文，专业严谨，总结主要发现和数据质量问题。
数据：{data}""",
        }
        import json
        return prompts.get(section, "").format(data=json.dumps(data, ensure_ascii=False, indent=2))

    # 章节名到分析数据键名的映射
    SECTION_DATA_KEY_MAP = {
        "basic": "basic_stats",
        "admission_trend": "admission_trend",
        "patient_features": "patient_features",
        "hospitalization_days": "hospitalization_days",
        "disease_types": "disease_types",
        "readmission": "readmission",
        "discharge": "discharge",
        "exam": "exam",
        "lab": "lab",
        "summary": None,  # summary使用全部数据
    }

    def generate_section(self, section: str, analysis_data: dict) -> str:
        """生成单个章节的文本"""
        data_key = self.SECTION_DATA_KEY_MAP.get(section, section)
        if data_key is None:
            section_data = analysis_data
        else:
            section_data = analysis_data.get(data_key, {})
        prompt = self._build_prompt(section, section_data)
        if not prompt:
            return ""
        return self.llm.chat(
            [
                {"role": "system", "content": "你是一位资深医院数据分析师，擅长撰写专业的医疗数据分析报告。请使用中文，风格专业、清晰、有条理。直接输出分析文本，不要加引言或总结语。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            cache_namespace=f"narrative:{section}",
        )

    def generate_full_report(self, analysis_id: str = "latest") -> dict:
        """生成完整报告（文本+图表）"""
        # 获取分析数据
        analysis_data = data_analysis_service.load_analysis(analysis_id)
        if analysis_data is None:
            # 重新运行分析
            data_analysis_service.save_analysis(analysis_id)
            analysis_data = data_analysis_service.load_analysis(analysis_id)

        # 生成图表配置
        charts = chart_service.generate_all_charts(analysis_data)

        # 生成各章节文本
        sections = [
            "basic",
            "admission_trend",
            "patient_features",
            "hospitalization_days",
            "disease_types",
            "readmission",
            "discharge",
            "exam",
            "lab",
            "summary",
        ]

        texts = {}
        for section in sections:
            texts[section] = self.generate_section(section, analysis_data)

        report = {
            "report_id": str(uuid.uuid4()),
            "analysis_id": analysis_id,
            "title": analysis_data.get("report_title", "肿瘤血液科数据分析报告"),
            "generated_at": analysis_data.get("generated_at", ""),
            "data_sources": analysis_data.get("data_sources", {}),
            "texts": texts,
            "charts": charts,
        }

        # 保存报告
        json_store.save(report["report_id"], report)
        return report

    def generate_report_async(self, analysis_id: str = "latest") -> str:
        """启动异步报告生成，返回report_id"""
        report_id = str(uuid.uuid4())
        # 这里只做初始化，实际生成由前端轮询或后台任务完成
        # 简化版本：直接同步生成
        report = self.generate_full_report(analysis_id)
        return report["report_id"]


# 全局单例
narrative_service = NarrativeService()
