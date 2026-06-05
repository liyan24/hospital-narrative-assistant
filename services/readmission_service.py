"""
再入院患者时间线叙事服务
识别多次就诊患者，生成长纵向医疗叙事
"""

from typing import Dict, List, Optional
from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class ReadmissionService:
    def __init__(self):
        self.llm = llm_service

    def get_readmission_patients(self, min_visits: int = 2, limit: int = 50) -> List[Dict]:
        """
        查询多次就诊的患者列表
        返回: [{patient_id, medical_record_no, age, visit_count, visits: [...]}]
        """
        cql = """
        MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
        WITH p, count(v) AS visit_count
        WHERE visit_count >= $min_visits
        RETURN p.patient_id AS patient_id, p.medical_record_no AS mrn,
               p.age AS age, visit_count
        ORDER BY visit_count DESC
        LIMIT $limit
        """
        records = neo4j_client.run(cql, {"min_visits": min_visits, "limit": limit})

        patients = []
        for r in records:
            patient_id = r["patient_id"]
            # 查询该患者的所有Visit详情
            visits = self._get_patient_visits_summary(patient_id)
            patients.append({
                "patient_id": patient_id,
                "medical_record_no": r["mrn"],
                "age": r["age"],
                "visit_count": r["visit_count"],
                "visits": visits,
            })
        return patients

    def _get_patient_visits_summary(self, patient_id: str) -> List[Dict]:
        """获取患者每次就诊的摘要信息"""
        cql = """
        MATCH (p:Patient {patient_id: $patient_id})-[:HAS_VISIT]->(v:Visit)
        OPTIONAL MATCH (v)-[rd:DIAGNOSED_WITH]->(d:Disease)
        WHERE rd.is_main = true OR rd.diagnosis_type = 'discharge'
        WITH v, collect(DISTINCT d.display_name) AS diagnoses
        OPTIONAL MATCH (v)-[:PRESCRIBED]->(dr:Drug)
        WITH v, diagnoses, collect(DISTINCT dr.name) AS drugs
        OPTIONAL MATCH (v)-[:UNDERWENT]->(s:Surgery)
        WITH v, diagnoses, drugs, collect(DISTINCT s.name) AS surgeries
        RETURN v.visit_id AS visit_id, v.admission_date AS admission_date,
               v.discharge_date AS discharge_date, v.length_of_stay AS length_of_stay,
               v.chief_complaint AS chief_complaint,
               diagnoses, drugs, surgeries
        ORDER BY v.admission_date
        """
        records = neo4j_client.run(cql, {"patient_id": patient_id})
        visits = []
        for r in records:
            visits.append({
                "visit_id": r["visit_id"],
                "admission_date": r["admission_date"],
                "discharge_date": r["discharge_date"],
                "length_of_stay": r["length_of_stay"],
                "chief_complaint": r["chief_complaint"],
                "diagnoses": [d for d in r["diagnoses"] if d],
                "drugs": [d for d in r["drugs"] if d][:10],  # 只取Top10
                "surgeries": [s for s in r["surgeries"] if s],
            })
        return visits

    def get_readmission_stats(self) -> Dict:
        """再入院整体统计"""
        # 再入院率
        cql_rate = """
        MATCH (p:Patient)
        WITH count(p) AS total_patients
        MATCH (p)-[:HAS_VISIT]->(v:Visit)
        WITH p, total_patients, count(v) AS vc
        WHERE vc >= 2
        RETURN total_patients, count(p) AS readmit_patients,
               avg(vc) AS avg_visits
        """
        rate_records = neo4j_client.run(cql_rate)
        rate = rate_records[0] if rate_records else {}

        # 再入院间隔分布
        cql_interval = """
        MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
        WITH p, v ORDER BY v.admission_date
        WITH p, collect(v.admission_date) AS dates
        WHERE size(dates) >= 2
        UNWIND range(0, size(dates)-2) AS i
        WITH duration.between(date(dates[i]), date(dates[i+1])).days AS interval_days
        RETURN
            count(CASE WHEN interval_days <= 30 THEN 1 END) AS within_30d,
            count(CASE WHEN interval_days > 30 AND interval_days <= 90 THEN 1 END) AS within_90d,
            count(CASE WHEN interval_days > 90 AND interval_days <= 180 THEN 1 END) AS within_180d,
            count(CASE WHEN interval_days > 180 THEN 1 END) AS over_180d,
            avg(interval_days) AS avg_interval
        """
        interval_records = neo4j_client.run(cql_interval)
        interval = interval_records[0] if interval_records else {}

        # 高频再入院疾病（出院诊断）
        cql_diseases = """
        MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
        WITH p, count(v) AS vc
        WHERE vc >= 2
        MATCH (p)-[:HAS_VISIT]->(v:Visit)-[:DIAGNOSED_WITH {diagnosis_type: 'discharge'}]->(d:Disease)
        WHERE d.type = 'western'
        RETURN d.display_name AS name, count(DISTINCT p) AS patient_cnt
        ORDER BY patient_cnt DESC LIMIT 15
        """
        disease_records = neo4j_client.run(cql_diseases)
        diseases = [{"name": r["name"], "count": r["patient_cnt"]} for r in disease_records]

        return {
            "total_patients": rate.get("total_patients", 0),
            "readmit_patients": rate.get("readmit_patients", 0),
            "readmit_rate": round(rate.get("readmit_patients", 0) / rate.get("total_patients", 1) * 100, 1),
            "avg_visits_per_readmit": round(rate.get("avg_visits", 0), 1),
            "interval_distribution": {
                "within_30d": interval.get("within_30d", 0),
                "within_90d": interval.get("within_90d", 0),
                "within_180d": interval.get("within_180d", 0),
                "over_180d": interval.get("over_180d", 0),
                "avg_interval_days": round(interval.get("avg_interval", 0), 1),
            },
            "top_readmit_diseases": diseases,
        }

    def generate_patient_narrative(self, patient_id: str) -> Dict:
        """为单个再入院患者生成长纵向叙事"""
        visits = self._get_patient_visits_summary(patient_id)
        if not visits:
            return {"error": "患者不存在或无任何就诊记录"}

        if len(visits) < 2:
            return {"error": "该患者仅就诊1次，不满足再入院条件"}

        context = self._build_patient_context(visits)
        prompt = self._build_patient_prompt(context)

        narrative = self.llm.chat(
            [
                {"role": "system", "content": "你是一位资深肿瘤科主治医师，擅长纵向跟踪患者的完整诊疗历程。请基于提供的多次就诊数据，用中文生成一段纵向医疗叙事。要体现出病情的发展变化、治疗方案的调整逻辑、以及每次入院之间的关联。语气要有临床深度，体现医生对病程的把握。直接输出叙事文本，不要加标题。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return {
            "patient_id": patient_id,
            "visit_count": len(visits),
            "narrative": narrative,
            "visits": visits,
        }

    def generate_summary_narrative(self) -> Dict:
        """生成再入院整体分析叙事"""
        stats = self.get_readmission_stats()
        patients = self.get_readmission_patients(min_visits=2, limit=20)

        context = self._build_summary_context(stats, patients)
        prompt = self._build_summary_prompt(context)

        narrative = self.llm.chat(
            [
                {"role": "system", "content": "你是一位资深医院质量管理专家，擅长分析再入院数据和患者管理。请基于提供的统计数据，用中文撰写一段再入院分析叙事。要体现出再入院的整体趋势、高风险疾病、时间分布特征，以及对科室管理的建议。语气专业、数据驱动，适合科室质控会议使用。直接输出叙事文本，不要加标题。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return {
            "narrative": narrative,
            "stats": stats,
            "patients": patients,
        }

    def _build_patient_context(self, visits: List[Dict]) -> str:
        lines = []
        lines.append(f"该患者共就诊 {len(visits)} 次，时间跨度从 {visits[0].get('admission_date', '未知')} 至 {visits[-1].get('admission_date', '未知')}。\n")

        for i, v in enumerate(visits, 1):
            lines.append(f"--- 第{i}次就诊 ({v.get('admission_date', '日期未知')}) ---")
            lines.append(f"  住院天数：{v.get('length_of_stay', '未知')}天")
            if v.get("chief_complaint"):
                lines.append(f"  主诉：{v['chief_complaint']}")
            if v.get("diagnoses"):
                lines.append(f"  诊断：{', '.join(v['diagnoses'][:5])}")
            if v.get("surgeries"):
                lines.append(f"  手术：{', '.join(v['surgeries'])}")
            if v.get("drugs"):
                lines.append(f"  主要用药：{', '.join(v['drugs'][:8])}")
            lines.append("")

        return "\n".join(lines)

    def _build_patient_prompt(self, context: str) -> str:
        return f"""请根据以下患者的多次就诊记录，撰写一段纵向医疗叙事。

要求：
1. 以时间顺序叙述该患者从首次就诊到最近一次就诊的完整历程
2. 分析病情的发展或变化趋势（如：稳定/进展/好转/转移）
3. 描述治疗方案的调整逻辑（如：换药原因、手术时机选择）
4. 指出值得关注的临床特点或教训
5. 字数控制在800字以内

数据：
{context}
"""

    def _build_summary_context(self, stats: Dict, patients: List[Dict]) -> str:
        lines = []
        lines.append(f"总患者数：{stats['total_patients']}")
        lines.append(f"再入院患者数：{stats['readmit_patients']} ({stats['readmit_rate']}%)")
        lines.append(f"再入院患者平均就诊次数：{stats['avg_visits_per_readmit']}次")
        lines.append("")

        interval = stats.get("interval_distribution", {})
        lines.append("再入院间隔分布：")
        lines.append(f"  - 30天内：{interval.get('within_30d', 0)}例")
        lines.append(f"  - 31-90天：{interval.get('within_90d', 0)}例")
        lines.append(f"  - 91-180天：{interval.get('within_180d', 0)}例")
        lines.append(f"  - 180天以上：{interval.get('over_180d', 0)}例")
        lines.append(f"  - 平均间隔：{interval.get('avg_interval_days', 0)}天")
        lines.append("")

        lines.append("再入院高发疾病（Top 10）：")
        for d in stats.get("top_readmit_diseases", [])[:10]:
            lines.append(f"  - {d['name']}: {d['count']}例")

        lines.append("")
        lines.append("高频再入院患者示例：")
        for p in patients[:5]:
            lines.append(f"  - 患者{p['patient_id'][-6:]} (病案号:{p['medical_record_no']}): {p['visit_count']}次就诊")
            # 提取主要诊断变化
            all_diags = []
            for v in p["visits"][:3]:
                if v.get("diagnoses"):
                    all_diags.append(v["diagnoses"][0])
            if all_diags:
                lines.append(f"    主要诊断变化：{' -> '.join(all_diags[:3])}")

        return "\n".join(lines)

    def _build_summary_prompt(self, context: str) -> str:
        return f"""请根据以下再入院统计数据，撰写一段再入院分析叙事。

要求：
1. 总结科室再入院的整体情况和趋势
2. 分析再入院高发疾病的特点和原因
3. 描述再入院时间分布特征（短期再入院vs长期随访）
4. 提出2-3条降低再入院率或改善再入院管理的建议
5. 字数控制在800字以内

数据：
{context}
"""


# 全局单例
readmission_service = ReadmissionService()
