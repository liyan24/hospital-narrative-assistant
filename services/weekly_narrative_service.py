"""
周简报文本生成服务：基于周统计数据使用大模型生成报告文本。
"""
import uuid
from services.llm_service import llm_service
from services.weekly_analysis_service import weekly_analysis_service
from database.json_store import json_store


class WeeklyNarrativeService:
    def __init__(self):
        self.llm = llm_service

    def _build_prompt(self, section: str, data: dict) -> str:
        import json
        prompts = {
            "operation": """你是一位资深医院数据分析师。请根据以下肿瘤血液科本周运营统计数据，撰写"模块1：本周运营概况"的分析文本（300字以内），包含核心运营指标解读和每日入院分布趋势提示。
要求：中文，专业严谨，指出环比变化趋势，给出管理建议。数据包含本周、上周环比、去年同期同比。
数据：{data}""",
            "diseases": """你是一位资深医院数据分析师。请根据以下肿瘤血液科本周病种统计数据，撰写"模块2：病种分析"的分析文本（300字以内），包含Top5病种分布和新发病种趋势分析。
要求：中文，专业严谨，分析病种构成变化，指出需要关注的趋势。
数据：{data}""",
            "exam_lab": """你是一位资深医院数据分析师。请根据以下肿瘤血液科本周检查检验统计数据，撰写"模块3：检查检验汇总"的分析文本（400字以内），包含检查量统计、CT阳性发现、检验统计和异常指标分析。
要求：中文，专业严谨，分析检查检验工作量和阳性/异常率。
数据：{data}""",
            "treatment": """你是一位资深医院数据分析师。请根据以下肿瘤血液科本周治疗动态数据，撰写"模块4：治疗动态"的分析文本（300字以内），包含手术统计、化疗统计和不良反应汇总。
要求：中文，专业严谨，分析治疗动态，指出安全问题。
数据：{data}""",
            "quality": """你是一位资深医院数据分析师。请根据以下肿瘤血液科本周质控指标数据，撰写"模块5：质控指标"的分析文本（200字以内），包含核心质控指标和病历质控问题。
要求：中文，专业严谨，指出达标情况和整改要求。
数据：{data}""",
            "focus_patients": """你是一位资深医院数据分析师。请根据以下肿瘤血液科本周重点关注患者数据，撰写"模块6：重点关注患者"的分析文本（300字以内），包含高龄患者和超长住院患者分析。
要求：中文，专业严谨，给出管理建议。
数据：{data}""",
            "next_week": """你是一位资深医院数据分析师。请根据以下肿瘤血液科下周预警数据，撰写"模块7：下周预警"的分析文本（300字以内），包含入院高峰预警、床位预警、手术排程和特殊事件提醒。
要求：中文，专业严谨，给出具体建议和应对措施。
数据：{data}""",
            "summary": """你是一位资深医院数据分析师。请根据以下肿瘤血液科本周全部统计数据，撰写一段200字以内的周简报总结。
要求：中文，专业严谨，总结本周核心发现和下周重点。
数据：{data}""",
        }
        return prompts.get(section, "").format(data=json.dumps(data, ensure_ascii=False, indent=2))

    def generate_section(self, section: str, weekly_data: dict) -> str:
        """生成单个模块的文本"""
        section_data = weekly_data.get(section, {})
        prompt = self._build_prompt(section, section_data)
        if not prompt:
            return ""
        return self.llm.chat(
            [
                {"role": "system", "content": "你是一位资深医院数据分析师，擅长撰写专业的医疗数据周简报。请使用中文，风格专业、清晰、有条理。直接输出分析文本，不要加引言或总结语。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

    def generate_full_report(self, analysis_id: str = "latest_weekly") -> dict:
        """生成完整周简报（文本+数据）"""
        weekly_data = weekly_analysis_service.load_weekly_analysis(analysis_id)
        if weekly_data is None:
            weekly_analysis_service.save_weekly_analysis(analysis_id)
            weekly_data = weekly_analysis_service.load_weekly_analysis(analysis_id)

        sections = [
            "operation",
            "diseases",
            "exam_lab",
            "treatment",
            "quality",
            "focus_patients",
            "next_week",
            "summary",
        ]

        texts = {}
        for section in sections:
            texts[section] = self.generate_section(section, weekly_data)

        report = {
            "report_id": str(uuid.uuid4()),
            "report_type": "weekly",
            "analysis_id": analysis_id,
            "title": weekly_data.get("report_title", "肿瘤血液科每周临床简报"),
            "week_range": weekly_data.get("week_range", ""),
            "generated_at": weekly_data.get("generated_at", ""),
            "data": weekly_data,
            "texts": texts,
        }

        json_store.save(report["report_id"], report)
        return report


# 全局单例
weekly_narrative_service = WeeklyNarrativeService()
