"""
科室运营深度叙事服务
将知识图谱洞察融入科室运营分析，支持多周期对比
"""
from typing import Optional

from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class DepartmentOperationService:
    """科室运营深度分析服务"""

    TCM_DRUG_KEYWORDS = [
        "颗粒", "汤", "丸", "胶囊", "口服液", "注射液", "散", "膏", "丹", "片",
        "复方", "华蟾素", "艾愈", "地奥心血康", "云南白药", "肝爽", "麻仁",
        "稳心", "六味地黄", "金水宝", "百令", "黄芪", "人参", "当归", "党参",
    ]

    def _is_tcm_drug(self, name: str) -> bool:
        return any(kw in name for kw in self.TCM_DRUG_KEYWORDS)

    def generate_operation_narrative(self, period: str = "latest_year",
                                     compare: bool = True) -> dict:
        """
        生成科室运营深度叙事
        period: latest_year | latest_quarter | latest_month | custom
        """
        # 解析时间范围
        current_period, previous_period = self._resolve_periods(period, compare)

        if not current_period:
            return {"error": "无法解析时间周期"}

        # 当前周期指标
        current_metrics = self._calculate_metrics(
            current_period["start"], current_period["end"]
        )

        # 对比周期指标
        previous_metrics = None
        if compare and previous_period:
            previous_metrics = self._calculate_metrics(
                previous_period["start"], previous_period["end"]
            )

        # 计算变化率
        changes = self._calculate_changes(current_metrics, previous_metrics)

        # 生成叙事
        narrative = self._generate_narrative(
            current_period, current_metrics,
            previous_period, previous_metrics, changes
        )

        return {
            "type": "department_operation",
            "period": period,
            "current_period": current_period,
            "previous_period": previous_period,
            "current_metrics": current_metrics,
            "previous_metrics": previous_metrics,
            "changes": changes,
            "narrative": narrative,
        }

    def _resolve_periods(self, period: str, compare: bool = True) -> tuple:
        """解析时间周期，返回当前周期和对比周期"""
        # 先获取数据最新日期
        recs = neo4j_client.run("MATCH (v:Visit) RETURN max(v.admission_date) AS max_date")
        if not recs or not recs[0]["max_date"]:
            return None, None
        latest_date = recs[0]["max_date"]

        from datetime import datetime, timedelta
        latest = datetime.strptime(latest_date, "%Y-%m-%d")

        if period == "latest_year":
            # 最近完整年份
            current_end = datetime(latest.year, 1, 1) - timedelta(days=1)
            current_start = datetime(latest.year - 1, 1, 1)
            previous_end = current_start - timedelta(days=1)
            previous_start = datetime(latest.year - 2, 1, 1)
        elif period == "latest_quarter":
            # 最近完整季度
            quarter = (latest.month - 1) // 3
            if quarter == 0:
                current_end = datetime(latest.year - 1, 12, 31)
                current_start = datetime(latest.year - 1, 10, 1)
            else:
                current_end = datetime(latest.year, quarter * 3, 1) - timedelta(days=1)
                current_start = datetime(latest.year, (quarter - 1) * 3 + 1, 1)
            # 上一季度
            previous_start = current_start - timedelta(days=90)
            previous_end = current_start - timedelta(days=1)
        elif period == "latest_month":
            # 最近完整月份
            current_end = datetime(latest.year, latest.month, 1) - timedelta(days=1)
            current_start = datetime(latest.year, latest.month, 1) - timedelta(days=current_end.day)
            previous_end = current_start - timedelta(days=1)
            previous_start = previous_end.replace(day=1)
        elif period == "y2024":
            current_start = datetime(2024, 1, 1)
            current_end = datetime(2024, 12, 31)
            previous_start = datetime(2023, 1, 1)
            previous_end = datetime(2023, 12, 31)
        elif period == "y2023":
            current_start = datetime(2023, 1, 1)
            current_end = datetime(2023, 12, 31)
            previous_start = datetime(2022, 1, 1)
            previous_end = datetime(2022, 12, 31)
        else:
            # 默认最近一年
            current_end = latest
            current_start = latest.replace(year=latest.year - 1)
            previous_end = current_start - timedelta(days=1)
            previous_start = previous_end.replace(year=previous_end.year - 1)

        def fmt(d):
            return d.strftime("%Y-%m-%d")

        return (
            {"start": fmt(current_start), "end": fmt(current_end),
             "label": f"{fmt(current_start)} ~ {fmt(current_end)}"},
            {"start": fmt(previous_start), "end": fmt(previous_end),
             "label": f"{fmt(previous_start)} ~ {fmt(previous_end)}"} if compare else None,
        )

    def _calculate_metrics(self, start_date: str, end_date: str) -> dict:
        """计算指定时间范围的运营指标"""
        params = {"start": start_date, "end": end_date}

        # 基础运营指标
        base_recs = neo4j_client.run("""
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WHERE v.admission_date >= $start AND v.admission_date <= $end
            RETURN count(v) AS visit_count,
                   count(DISTINCT p.patient_id) AS patient_count,
                   avg(v.length_of_stay) AS avg_los,
                   percentileCont(v.length_of_stay, 0.5) AS median_los
        """, params)
        base = dict(base_recs[0]) if base_recs else {}

        visit_count = base.get("visit_count", 0) or 0
        if visit_count == 0:
            return {"visit_count": 0}

        # 病种Top10（西医）
        disease_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
            WHERE v.admission_date >= $start AND v.admission_date <= $end AND d.type = 'western'
            RETURN d.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, params)
        top_diseases = [{"name": r["name"], "count": r["cnt"]} for r in disease_recs]

        # 病种Top10（中医）
        tcm_disease_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
            WHERE v.admission_date >= $start AND v.admission_date <= $end AND d.type IN ['tcm', 'tcm_syndrome']
            RETURN d.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, params)
        top_tcm_diseases = [{"name": r["name"], "count": r["cnt"]} for r in tcm_disease_recs]

        # Top 10 药品
        drug_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:PRESCRIBED]->(dr:Drug)
            WHERE v.admission_date >= $start AND v.admission_date <= $end
            RETURN dr.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, params)
        top_drugs = [{"name": r["name"], "count": r["cnt"], "is_tcm": self._is_tcm_drug(r["name"])} for r in drug_recs]

        # Top 5 检查
        exam_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:PERFORMED_EXAM]->(e:Exam)
            WHERE v.admission_date >= $start AND v.admission_date <= $end
            RETURN e.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 5
        """, params)
        top_exams = [{"name": r["name"], "count": r["cnt"]} for r in exam_recs]

        # 手术率 & Top 手术
        surgery_recs = neo4j_client.run("""
            MATCH (v:Visit)
            WHERE v.admission_date >= $start AND v.admission_date <= $end
            OPTIONAL MATCH (v)-[:UNDERWENT]->(s:Surgery)
            RETURN count(DISTINCT v) AS total,
                   sum(CASE WHEN s IS NOT NULL THEN 1 ELSE 0 END) AS surgery_count
        """, params)
        surgery = dict(surgery_recs[0]) if surgery_recs else {"total": 0, "surgery_count": 0}

        top_surgeries = []
        if surgery.get("surgery_count", 0) > 0:
            surgery_top_recs = neo4j_client.run("""
                MATCH (v:Visit)-[:UNDERWENT]->(s:Surgery)
                WHERE v.admission_date >= $start AND v.admission_date <= $end
                RETURN s.name AS name, count(DISTINCT v) AS cnt
                ORDER BY cnt DESC LIMIT 5
            """, params)
            top_surgeries = [{"name": r["name"], "count": r["cnt"]} for r in surgery_top_recs]

        # 合并症Top10
        comorb_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:DIAGNOSED_WITH]->(d1:Disease), (v)-[:DIAGNOSED_WITH]->(d2:Disease)
            WHERE v.admission_date >= $start AND v.admission_date <= $end
              AND d1.type = 'western' AND d2.type = 'western'
              AND id(d1) < id(d2)
            RETURN d1.name AS name1, d2.name AS name2, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, params)
        top_comorbidities = [{"disease1": r["name1"], "disease2": r["name2"], "count": r["cnt"]} for r in comorb_recs]

        # 多病共存比例（一次就诊>=3个西医诊断）
        multi_disease_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
            WHERE v.admission_date >= $start AND v.admission_date <= $end AND d.type = 'western'
            WITH v, count(d) AS dcount
            RETURN count(v) AS total,
                   sum(CASE WHEN dcount >= 3 THEN 1 ELSE 0 END) AS multi_count
        """, params)
        multi_disease = dict(multi_disease_recs[0]) if multi_disease_recs else {"total": 0, "multi_count": 0}

        # 再入院率
        readmit_recs = neo4j_client.run("""
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WHERE v.admission_date >= $start AND v.admission_date <= $end
            WITH p, count(DISTINCT v) AS vcount
            RETURN count(DISTINCT p) AS total_patients,
                   sum(CASE WHEN vcount >= 2 THEN 1 ELSE 0 END) AS readmit_patients
        """, params)
        readmit = dict(readmit_recs[0]) if readmit_recs else {"total_patients": 0, "readmit_patients": 0}

        # 中西医结合比例
        integrated_recs = neo4j_client.run("""
            MATCH (v:Visit)
            WHERE v.admission_date >= $start AND v.admission_date <= $end
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(w:Disease) WHERE w.type = 'western'
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(t:Disease) WHERE t.type IN ['tcm', 'tcm_syndrome']
            WITH v, count(w) AS has_w, count(t) AS has_t
            RETURN count(v) AS total,
                   sum(CASE WHEN has_w > 0 AND has_t > 0 THEN 1 ELSE 0 END) AS integrated,
                   sum(CASE WHEN has_w > 0 THEN 1 ELSE 0 END) AS western_only,
                   sum(CASE WHEN has_t > 0 THEN 1 ELSE 0 END) AS tcm_only
        """, params)
        integrated = dict(integrated_recs[0]) if integrated_recs else {}

        return {
            "visit_count": visit_count,
            "patient_count": base.get("patient_count", 0) or 0,
            "avg_los": round(base.get("avg_los", 0) or 0, 1),
            "median_los": round(base.get("median_los", 0) or 0, 1),
            "top_diseases": top_diseases,
            "top_tcm_diseases": top_tcm_diseases,
            "top_drugs": top_drugs,
            "top_exams": top_exams,
            "surgery_rate": round((surgery.get("surgery_count", 0) or 0) / (surgery.get("total", 1) or 1) * 100, 1),
            "top_surgeries": top_surgeries,
            "top_comorbidities": top_comorbidities,
            "multi_disease_rate": round((multi_disease.get("multi_count", 0) or 0) / (multi_disease.get("total", 1) or 1) * 100, 1),
            "readmit_rate": round((readmit.get("readmit_patients", 0) or 0) / (readmit.get("total_patients", 1) or 1) * 100, 1),
            "integrated": integrated,
        }

    def _calculate_changes(self, current: dict, previous: Optional[dict]) -> dict:
        """计算同比/环比变化"""
        if not previous or previous.get("visit_count", 0) == 0:
            return {}

        def pct_change(cur, prev):
            if not prev:
                return None
            return round((cur - prev) / prev * 100, 1)

        return {
            "visit_count_change": pct_change(current.get("visit_count", 0), previous.get("visit_count", 0)),
            "patient_count_change": pct_change(current.get("patient_count", 0), previous.get("patient_count", 0)),
            "avg_los_change": pct_change(current.get("avg_los", 0), previous.get("avg_los", 0)),
            "surgery_rate_change": pct_change(current.get("surgery_rate", 0), previous.get("surgery_rate", 0)),
            "multi_disease_rate_change": pct_change(current.get("multi_disease_rate", 0), previous.get("multi_disease_rate", 0)),
            "readmit_rate_change": pct_change(current.get("readmit_rate", 0), previous.get("readmit_rate", 0)),
        }

    def _generate_narrative(self, current_period: dict, current_metrics: dict,
                           previous_period: Optional[dict], previous_metrics: Optional[dict],
                           changes: dict) -> str:
        """调用LLM生成运营叙事"""
        system = (
            "你是一位资深的医院运营管理专家。请基于提供的科室运营数据，生成结构化、专业的科室运营深度分析报告。"
            "报告应包括：1) 总体运营概况；2) 病种结构与变化；3) 用药模式与资源使用；4) 合并症与多病共存趋势；"
            "5) 中西医结合运营特色；6) 再入院与手术分析；7) 改进建议。"
            "语言专业、数据驱动、 actionable，中文输出。"
        )

        lines = [
            f"分析周期: {current_period['label']}",
            f"对比周期: {previous_period['label'] if previous_period else '无'}",
            "",
            "=== 总体运营指标 ===",
            f"就诊人次: {current_metrics.get('visit_count', 0):,}",
            f"患者人数(去重): {current_metrics.get('patient_count', 0):,}",
            f"平均住院天数: {current_metrics.get('avg_los', 0)}天",
            f"中位住院天数: {current_metrics.get('median_los', 0)}天",
            f"手术率: {current_metrics.get('surgery_rate', 0)}%",
            f"多病共存率(>=3诊断): {current_metrics.get('multi_disease_rate', 0)}%",
            f"再入院率: {current_metrics.get('readmit_rate', 0)}%",
        ]

        if changes:
            lines.append("\n=== 环比变化 ===")
            for k, v in changes.items():
                if v is not None:
                    label = {
                        "visit_count_change": "就诊人次",
                        "patient_count_change": "患者人数",
                        "avg_los_change": "平均住院天数",
                        "surgery_rate_change": "手术率",
                        "multi_disease_rate_change": "多病共存率",
                        "readmit_rate_change": "再入院率",
                    }.get(k, k)
                    direction = "↑" if v > 0 else "↓"
                    lines.append(f"{label}: {direction}{abs(v)}%")

        lines.append("\n=== Top 10 西医疾病 ===")
        for d in current_metrics.get("top_diseases", []):
            lines.append(f"  - {d['name']}: {d['count']}次")

        lines.append("\n=== Top 5 中医证型/病名 ===")
        for d in current_metrics.get("top_tcm_diseases", []):
            lines.append(f"  - {d['name']}: {d['count']}次")

        lines.append("\n=== Top 10 药品 ===")
        for d in current_metrics.get("top_drugs", []):
            tag = "[中药]" if d["is_tcm"] else "[西药]"
            lines.append(f"  - {d['name']} {tag}: {d['count']}次")

        lines.append("\n=== Top 5 检查 ===")
        for d in current_metrics.get("top_exams", []):
            lines.append(f"  - {d['name']}: {d['count']}次")

        if current_metrics.get("top_surgeries"):
            lines.append("\n=== Top 5 手术 ===")
            for d in current_metrics.get("top_surgeries", []):
                lines.append(f"  - {d['name']}: {d['count']}次")

        lines.append("\n=== Top 10 合并症对 ===")
        for d in current_metrics.get("top_comorbidities", []):
            lines.append(f"  - {d['disease1']} + {d['disease2']}: {d['count']}次")

        integrated = current_metrics.get("integrated", {})
        total = integrated.get("total", 0)
        if total > 0:
            lines.append("\n=== 中西医结合运营 ===")
            lines.append(f"总就诊: {total}")
            lines.append(f"中西医结合: {integrated.get('integrated', 0)} ({round(integrated.get('integrated', 0)/total*100, 1)}%)")
            lines.append(f"纯西医: {integrated.get('western_only', 0)} ({round(integrated.get('western_only', 0)/total*100, 1)}%)")
            lines.append(f"纯中医: {integrated.get('tcm_only', 0)} ({round(integrated.get('tcm_only', 0)/total*100, 1)}%)")

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(lines)},
        ]
        return llm_service.chat(messages, temperature=0.4, max_tokens=3000)


# 全局单例
department_operation_service = DepartmentOperationService()
