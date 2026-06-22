"""
每日晨会简报服务
基于 Neo4j 知识图谱查询今日新入院、在院患者、手术安排、重点关注患者和质控异常
"""
from datetime import datetime, date
from typing import Dict, List, Optional
from database.neo4j_client import neo4j_client
from config import settings


class DailyBriefingService:
    """每日晨会简报服务"""

    def generate_briefing(self, briefing_date: Optional[str] = None) -> Dict:
        """生成指定日期的晨会简报"""
        if briefing_date is None:
            briefing_date = settings.simulation_date or date.today().isoformat()

        return {
            "date": briefing_date,
            "generated_at": datetime.now().isoformat(),
            "overview": self._get_overview(briefing_date),
            "new_admissions": self._get_new_admissions(briefing_date),
            "inpatients": self._get_inpatients(briefing_date),
            "surgeries": self._get_surgeries(briefing_date),
            "focus_patients": self._get_focus_patients(briefing_date),
            "quality_control_issues": self._get_quality_control_issues(briefing_date),
        }

    def _get_overview(self, briefing_date: str) -> Dict:
        """获取今日概览指标"""
        # 新入院
        new_admission_query = """
            MATCH (v:Visit)
            WHERE date(v.admission_date) = date($date)
            RETURN count(v) AS cnt
        """
        new_admissions = neo4j_client.run(new_admission_query, {"date": briefing_date})
        new_admission_count = new_admissions[0]["cnt"] if new_admissions else 0

        # 在院患者数
        inpatient_query = """
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WHERE date(v.admission_date) <= date($date)
              AND (v.discharge_date IS NULL OR date(v.discharge_date) > date($date))
            RETURN count(DISTINCT p) AS cnt
        """
        inpatient_recs = neo4j_client.run(inpatient_query, {"date": briefing_date})
        inpatient_count = inpatient_recs[0]["cnt"] if inpatient_recs else 0

        # 今日手术
        surgery_query = """
            MATCH (v:Visit)-[r:UNDERWENT]->(s:Surgery)
            WHERE date(r.start_date) = date($date)
            RETURN count(r) AS cnt
        """
        surgery_recs = neo4j_client.run(surgery_query, {"date": briefing_date})
        surgery_count = surgery_recs[0]["cnt"] if surgery_recs else 0

        # 重点关注（高风险在院患者）
        focus_query = """
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WHERE date(v.admission_date) <= date($date)
              AND (v.discharge_date IS NULL OR date(v.discharge_date) > date($date))
            WITH p, count(v) AS visit_count,
                 avg(v.length_of_stay) AS avg_los,
                 collect(DISTINCT v.length_of_stay) AS los_list
            MATCH (p)-[:HAS_VISIT]->(v2:Visit)
            OPTIONAL MATCH (v2)-[:DIAGNOSED_WITH]->(d:Disease)
            WITH p, visit_count, avg_los, count(DISTINCT d) AS disease_count,
                 collect(DISTINCT d.name) AS diseases
            WHERE visit_count >= 3 OR avg_los >= 14 OR any(d IN diseases WHERE d CONTAINS '恶性肿瘤')
            RETURN count(DISTINCT p) AS cnt
        """
        focus_recs = neo4j_client.run(focus_query, {"date": briefing_date})
        focus_count = focus_recs[0]["cnt"] if focus_recs else 0

        # 质控异常数
        qc_count = len(self._get_quality_control_issues(briefing_date))

        return {
            "new_admissions": new_admission_count,
            "inpatients": inpatient_count,
            "surgeries": surgery_count,
            "focus_patients": focus_count,
            "quality_control_issues": qc_count,
        }

    def _get_new_admissions(self, briefing_date: str) -> List[Dict]:
        """获取今日新入院患者"""
        query = """
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WHERE date(v.admission_date) = date($date)
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(d:Disease)
            WHERE d.type = 'western'
            WITH p, v, d
            ORDER BY d.is_main DESC
            WITH p, v, collect(d.display_name)[0] AS main_diagnosis
            RETURN p.patient_id AS patient_id,
                   p.age AS age,
                   v.admission_date AS admission_date,
                   main_diagnosis,
                   v.chief_complaint AS chief_complaint
            ORDER BY v.admission_date
            LIMIT 50
        """
        recs = neo4j_client.run(query, {"date": briefing_date})
        results = []
        for r in recs:
            results.append({
                "patient_id": r["patient_id"],
                "name": self._mask_name(r["patient_id"]),
                "age": r["age"],
                "gender": "-",
                "admission_date": r["admission_date"],
                "main_diagnosis": r["main_diagnosis"] or "未记录",
                "chief_complaint": r["chief_complaint"] or "未记录",
                "bed": "-",
                "doctor": "-",
            })
        return results

    def _get_inpatients(self, briefing_date: str) -> List[Dict]:
        """获取当前在院患者列表"""
        query = """
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WHERE date(v.admission_date) <= date($date)
              AND (v.discharge_date IS NULL OR date(v.discharge_date) > date($date))
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(d:Disease)
            WHERE d.type = 'western'
            WITH p, v, d
            ORDER BY d.is_main DESC
            WITH p, v, collect(d.display_name)[0] AS main_diagnosis
            RETURN p.patient_id AS patient_id,
                   p.age AS age,
                   v.admission_date AS admission_date,
                   v.length_of_stay AS length_of_stay,
                   main_diagnosis
            ORDER BY v.admission_date
            LIMIT 200
        """
        recs = neo4j_client.run(query, {"date": briefing_date})
        results = []
        for r in recs:
            results.append({
                "patient_id": r["patient_id"],
                "name": self._mask_name(r["patient_id"]),
                "age": r["age"],
                "gender": "-",
                "admission_date": r["admission_date"],
                "length_of_stay": r["length_of_stay"],
                "main_diagnosis": r["main_diagnosis"] or "未记录",
                "bed": "-",
                "doctor": "-",
            })
        return results

    def _get_surgeries(self, briefing_date: str) -> List[Dict]:
        """获取今日手术安排"""
        query = """
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)-[r:UNDERWENT]->(s:Surgery)
            WHERE date(r.start_date) = date($date)
            RETURN p.patient_id AS patient_id,
                   s.name AS surgery_name,
                   r.start_date AS start_time,
                   s.category AS category,
                   s.anesthesia_method AS anesthesia_method
            ORDER BY r.start_date
            LIMIT 50
        """
        recs = neo4j_client.run(query, {"date": briefing_date})
        results = []
        for idx, r in enumerate(recs, 1):
            time_str = r["start_time"] or "08:00"
            results.append({
                "time": time_str.split(" ")[-1][:5] if " " in str(time_str) else "08:00",
                "patient_id": r["patient_id"],
                "name": self._mask_name(r["patient_id"]),
                "surgery_name": r["surgery_name"],
                "room": f"手术室 {idx}",
                "doctor": "-",
            })
        return results

    def _get_focus_patients(self, briefing_date: str) -> List[Dict]:
        """获取重点关注患者（高风险 + 在院）"""
        query = """
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WHERE date(v.admission_date) <= date($date)
              AND (v.discharge_date IS NULL OR date(v.discharge_date) > date($date))
            WITH p, count(v) AS visit_count,
                 avg(v.length_of_stay) AS avg_los,
                 max(v.length_of_stay) AS max_los
            MATCH (p)-[:HAS_VISIT]->(v2:Visit)
            OPTIONAL MATCH (v2)-[:DIAGNOSED_WITH]->(d:Disease)
            WITH p, visit_count, avg_los, max_los, count(DISTINCT d) AS disease_count,
                 collect(DISTINCT d.name) AS diseases
            WHERE visit_count >= 3 OR avg_los >= 14 OR any(d IN diseases WHERE d CONTAINS '恶性肿瘤')
            RETURN p.patient_id AS patient_id,
                   p.age AS age,
                   visit_count,
                   avg_los,
                   max_los,
                   disease_count,
                   [d IN diseases WHERE d CONTAINS '恶性肿瘤'][0] AS cancer_diagnosis
            ORDER BY visit_count DESC, avg_los DESC
            LIMIT 20
        """
        recs = neo4j_client.run(query, {"date": briefing_date})
        results = []
        for r in recs:
            reasons = []
            if r["visit_count"] >= 3:
                reasons.append(f"多次入院（{r['visit_count']}次）")
            if r["avg_los"] >= 14:
                reasons.append(f"平均住院日长（{r['avg_los']:.1f}天）")
            if r["cancer_diagnosis"]:
                reasons.append("恶性肿瘤患者")

            risk = "高" if r["visit_count"] >= 5 or r["avg_los"] >= 14 or r["cancer_diagnosis"] else "中"

            results.append({
                "patient_id": r["patient_id"],
                "name": self._mask_name(r["patient_id"]),
                "bed": "-",
                "risk": risk,
                "reason": "；".join(reasons) if reasons else "在院重点关注",
                "action": "主任查房重点讨论" if risk == "高" else "密切观察病情变化",
            })
        return results

    def _get_quality_control_issues(self, briefing_date: str) -> List[Dict]:
        """获取今日在院患者的质控异常"""
        from services.quality_control_service import quality_control_service

        # 获取今日在院患者
        query = """
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WHERE date(v.admission_date) <= date($date)
              AND (v.discharge_date IS NULL OR date(v.discharge_date) > date($date))
            RETURN p.patient_id AS patient_id
            LIMIT 200
        """
        recs = neo4j_client.run(query, {"date": briefing_date})
        patient_ids = [r["patient_id"] for r in recs if r["patient_id"]]

        # 逐个检查质控异常
        issues = []
        for pid in patient_ids[:50]:  # 限制数量避免超时
            patient_issues = quality_control_service.detect_patient_issues(pid)
            for issue in patient_issues:
                issue["patient_id"] = pid
                issue["name"] = self._mask_name(pid)
                issue["owner"] = "-"
                issues.append(issue)

        # 去重并限制数量
        seen = set()
        unique_issues = []
        for issue in issues:
            key = (issue.get("patient_id"), issue["type"], issue.get("visit_id"))
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        return unique_issues[:30]

    def _mask_name(self, patient_id: str) -> str:
        """根据 patient_id 生成脱敏姓名"""
        import hashlib
        h = hashlib.md5(patient_id.encode()).hexdigest()
        surnames = ["张", "李", "王", "刘", "陈", "杨", "赵", "黄", "周", "吴"]
        return surnames[int(h, 16) % len(surnames)] + "**"


# 全局单例
daily_briefing_service = DailyBriefingService()
