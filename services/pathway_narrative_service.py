"""
诊疗路径模式叙事服务
基于知识图谱挖掘某疾病的典型诊疗路径，生成科室诊疗规范叙事
"""

from typing import Dict, List, Optional
from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class PathwayNarrativeService:
    def __init__(self):
        self.llm = llm_service

    def get_disease_pathway(self, disease_name: str) -> Optional[Dict]:
        """
        从Neo4j查询某疾病的典型诊疗路径数据
        返回: {
            disease_name, visit_count,
            top_drugs: [{name, count, pct}],
            top_exams: [{name, count, pct}],
            top_surgeries: [{name, count, pct}],
            top_labs: [{name, count, pct}],
            avg_stay, stay_distribution,
            department_distribution,
            comorbidities: [{name, count, pct}]
        }
        """
        # 基础统计
        cql_base = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[rd:DIAGNOSED_WITH]-(v:Visit)
        RETURN count(DISTINCT v) AS visit_count,
               avg(v.length_of_stay) AS avg_stay,
               percentileDisc(v.length_of_stay, 0.5) AS median_stay
        """
        base_records = neo4j_client.run(cql_base, {"disease_name": disease_name})
        if not base_records or base_records[0]["visit_count"] == 0:
            return None

        base = base_records[0]
        visit_count = base["visit_count"]

        # 常用药品
        cql_drugs = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
        RETURN dr.name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 20
        """
        drug_records = neo4j_client.run(cql_drugs, {"disease_name": disease_name})
        top_drugs = [{"name": r["name"], "count": r["cnt"],
                      "pct": round(r["cnt"] / visit_count * 100, 1)} for r in drug_records]

        # 常用检查
        cql_exams = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PERFORMED_EXAM]->(e:Exam)
        RETURN e.name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 15
        """
        exam_records = neo4j_client.run(cql_exams, {"disease_name": disease_name})
        top_exams = [{"name": r["name"], "count": r["cnt"],
                      "pct": round(r["cnt"] / visit_count * 100, 1)} for r in exam_records]

        # 常见手术
        cql_surgeries = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:UNDERWENT]->(s:Surgery)
        RETURN s.name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 10
        """
        surgery_records = neo4j_client.run(cql_surgeries, {"disease_name": disease_name})
        top_surgeries = [{"name": r["name"], "count": r["cnt"],
                          "pct": round(r["cnt"] / visit_count * 100, 1)} for r in surgery_records]

        # 常见检验
        cql_labs = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:HAS_LAB_RESULT]->(l:LabItem)
        RETURN l.name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 15
        """
        lab_records = neo4j_client.run(cql_labs, {"disease_name": disease_name})
        top_labs = [{"name": r["name"], "count": r["cnt"],
                     "pct": round(r["cnt"] / visit_count * 100, 1)} for r in lab_records]

        # 科室分布
        cql_depts = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:IN_DEPARTMENT]->(dept:Department)
        RETURN dept.name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 10
        """
        dept_records = neo4j_client.run(cql_depts, {"disease_name": disease_name})
        dept_dist = [{"name": r["name"], "count": r["cnt"],
                      "pct": round(r["cnt"] / visit_count * 100, 1)} for r in dept_records]

        # 常见合并症（同一次就诊的其他诊断）
        cql_comorb = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(d2:Disease)
        WHERE d2 <> d
        RETURN d2.display_name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 15
        """
        comorb_records = neo4j_client.run(cql_comorb, {"disease_name": disease_name})
        comorbidities = [{"name": r["name"], "count": r["cnt"],
                          "pct": round(r["cnt"] / visit_count * 100, 1)} for r in comorb_records]

        # 住院天数分布
        cql_stay = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)
        RETURN
            count(CASE WHEN v.length_of_stay <= 3 THEN 1 END) AS stay_1_3,
            count(CASE WHEN v.length_of_stay > 3 AND v.length_of_stay <= 7 THEN 1 END) AS stay_4_7,
            count(CASE WHEN v.length_of_stay > 7 AND v.length_of_stay <= 14 THEN 1 END) AS stay_8_14,
            count(CASE WHEN v.length_of_stay > 14 THEN 1 END) AS stay_14plus
        """
        stay_records = neo4j_client.run(cql_stay, {"disease_name": disease_name})
        stay_dist = stay_records[0] if stay_records else {}

        return {
            "disease_name": disease_name,
            "visit_count": visit_count,
            "avg_stay": round(base["avg_stay"], 1) if base.get("avg_stay") else None,
            "median_stay": base.get("median_stay"),
            "top_drugs": top_drugs,
            "top_exams": top_exams,
            "top_surgeries": top_surgeries,
            "top_labs": top_labs,
            "department_distribution": dept_dist,
            "comorbidities": comorbidities,
            "stay_distribution": stay_dist,
        }

    def generate_narrative(self, disease_name: str) -> Dict:
        """生成诊疗路径模式叙事"""
        pathway = self.get_disease_pathway(disease_name)
        if pathway is None:
            return {"error": f"未找到疾病 '{disease_name}' 的诊疗数据"}

        context = self._build_context(pathway)

        prompt = self._build_prompt(context)
        narrative = self.llm.chat(
            [
                {"role": "system", "content": "你是一位资深医院科室主任，擅长总结科室诊疗规范和临床路径。请基于提供的统计数据，用中文撰写一段专业的诊疗路径模式叙事。要体现出该疾病在本科室的规范化诊疗流程、常用方案特点和临床管理经验。语气权威、专业，适合科室内部培训或质量汇报使用。直接输出叙事文本，不要加标题。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            cache_namespace=f"pathway:{disease_name}",
        )

        return {
            "disease_name": disease_name,
            "narrative": narrative,
            "pathway": pathway,
        }

    def _build_context(self, pathway: Dict) -> str:
        lines = []
        lines.append(f"疾病名称：{pathway['disease_name']}")
        lines.append(f"相关就诊人次：{pathway['visit_count']}")
        if pathway.get("avg_stay"):
            lines.append(f"平均住院天数：{pathway['avg_stay']}天（中位数：{pathway.get('median_stay', 'N/A')}天）")

        sd = pathway.get("stay_distribution", {})
        if sd:
            lines.append(f"住院天数分布：1-3天({sd.get('stay_1_3', 0)}人) / 4-7天({sd.get('stay_4_7', 0)}人) / 8-14天({sd.get('stay_8_14', 0)}人) / 14天以上({sd.get('stay_14plus', 0)}人)")

        if pathway.get("department_distribution"):
            lines.append(f"\n科室分布：")
            for d in pathway["department_distribution"][:5]:
                lines.append(f"  - {d['name']}: {d['count']}例 ({d['pct']}%)")

        if pathway.get("comorbidities"):
            lines.append(f"\n常见合并症：")
            for c in pathway["comorbidities"][:10]:
                lines.append(f"  - {c['name']}: {c['count']}例 ({c['pct']}%)")

        if pathway.get("top_drugs"):
            lines.append(f"\n最常用药品（Top 10）：")
            for d in pathway["top_drugs"][:10]:
                lines.append(f"  - {d['name']}: {d['count']}例 ({d['pct']}%)")

        if pathway.get("top_exams"):
            lines.append(f"\n最常用检查（Top 8）：")
            for e in pathway["top_exams"][:8]:
                lines.append(f"  - {e['name']}: {e['count']}例 ({e['pct']}%)")

        if pathway.get("top_labs"):
            lines.append(f"\n最常用检验（Top 8）：")
            for l in pathway["top_labs"][:8]:
                lines.append(f"  - {l['name']}: {l['count']}例 ({l['pct']}%)")

        if pathway.get("top_surgeries"):
            lines.append(f"\n常见手术：")
            for s in pathway["top_surgeries"][:8]:
                lines.append(f"  - {s['name']}: {s['count']}例 ({s['pct']}%)")

        return "\n".join(lines)

    def _build_prompt(self, context: str) -> str:
        return f"""请根据以下肿瘤血液科某疾病的诊疗统计数据，撰写一段诊疗路径模式叙事。

要求：
1. 描述该疾病在本科室的典型诊疗流程，从入院检查到治疗方案再到出院
2. 总结最常用的药品组合和用药策略
3. 提及常规的检查检验项目及其临床意义
4. 分析常见合并症对诊疗的影响
5. 如果有手术数据，描述手术适应症和类型分布
6. 结合住院天数分布，评价治疗效率
7. 字数控制在800字以内

数据：
{context}
"""


# 全局单例
pathway_narrative_service = PathwayNarrativeService()
