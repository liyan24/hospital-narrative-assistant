"""
预测性叙事 / 风险预警服务
基于知识图谱和历史数据识别高风险患者
"""
from typing import Optional

from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class RiskPredictionService:
    """风险预警与预测性叙事服务"""

    def generate_risk_narrative(self, patient_id: Optional[str] = None,
                                 top_n: int = 20) -> dict:
        """
        生成风险预警叙事
        如果指定patient_id则分析该患者；否则分析全局高风险患者
        """
        if patient_id:
            return self._analyze_single_patient(patient_id)
        return self._analyze_global_risks(top_n)

    def _analyze_single_patient(self, patient_id: str) -> dict:
        """分析单个患者的风险"""
        # 获取患者完整数据
        recs = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(d:Disease)
            OPTIONAL MATCH (v)-[:PRESCRIBED]->(dr:Drug)
            OPTIONAL MATCH (v)-[:PERFORMED_EXAM]->(e:Exam)
            OPTIONAL MATCH (v)-[:UNDERWENT]->(s:Surgery)
            RETURN p.age AS age, p.gender AS gender,
                   count(DISTINCT v) AS visit_count,
                   avg(v.length_of_stay) AS avg_los,
                   collect(DISTINCT d.name) AS diseases,
                   collect(DISTINCT dr.name) AS drugs,
                   collect(DISTINCT e.name) AS exams,
                   collect(DISTINCT s.name) AS surgeries,
                   min(v.admission_date) AS first_visit,
                   max(v.admission_date) AS last_visit
        """, {"pid": patient_id})

        if not recs:
            return {"error": f"患者 {patient_id} 不存在"}

        r = dict(recs[0])
        diseases = list(set(r.get("diseases") or []))
        drugs = list(set(r.get("drugs") or []))

        # 计算风险评分
        risk_score = 0
        risk_factors = []

        # 因素1: 就诊次数（再入院频率）
        visit_count = r.get("visit_count", 0) or 0
        if visit_count >= 10:
            risk_score += 30
            risk_factors.append(f"高频就诊（{visit_count}次），提示病情反复或慢性进展")
        elif visit_count >= 5:
            risk_score += 20
            risk_factors.append(f"多次就诊（{visit_count}次），需关注治疗依从性")
        elif visit_count >= 3:
            risk_score += 10
            risk_factors.append(f"重复就诊（{visit_count}次）")

        # 因素2: 多病共存
        western_diseases = [d for d in diseases if "::western" in d]
        tcm_diseases = [d for d in diseases if "::tcm" in d]
        if len(western_diseases) >= 5:
            risk_score += 20
            risk_factors.append(f"多病共存（{len(western_diseases)}种西医诊断），病情复杂")
        elif len(western_diseases) >= 3:
            risk_score += 10
            risk_factors.append(f"合并多种疾病（{len(western_diseases)}种）")

        # 因素3: 住院天数
        avg_los = r.get("avg_los", 0) or 0
        if avg_los >= 15:
            risk_score += 20
            risk_factors.append(f"平均住院天数长（{round(avg_los, 1)}天），提示病情严重或并发症多")
        elif avg_los >= 10:
            risk_score += 10
            risk_factors.append(f"住院天数偏长（{round(avg_los, 1)}天）")

        # 因素4: 年龄
        age = r.get("age")
        if age and age >= 75:
            risk_score += 15
            risk_factors.append(f"高龄患者（{age}岁），生理储备下降")
        elif age and age >= 65:
            risk_score += 10
            risk_factors.append(f"老年患者（{age}岁）")

        # 因素5: 恶性肿瘤相关诊断
        cancer_keywords = ["恶性肿瘤", "癌", "转移", "继发恶性肿瘤", "终末期"]
        has_cancer = any(any(kw in d for kw in cancer_keywords) for d in diseases)
        if has_cancer:
            risk_score += 20
            risk_factors.append("诊断含恶性肿瘤或终末期疾病，预后风险高")

        # 因素6: 手术史
        surgeries = list(set(r.get("surgeries") or []))
        if len(surgeries) >= 2:
            risk_score += 10
            risk_factors.append(f"多次手术史（{len(surgeries)}次），提示病情进展")

        # 风险等级
        risk_level = self._get_risk_level(risk_score)

        data = {
            "patient_id": patient_id,
            "age": age,
            "gender": r.get("gender"),
            "visit_count": visit_count,
            "avg_los": round(avg_los, 1),
            "disease_count": len(western_diseases),
            "tcm_disease_count": len(tcm_diseases),
            "drug_count": len(set(drugs)),
            "surgery_count": len(surgeries),
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "diseases": diseases[:15],
            "drugs": drugs[:10],
        }

        narrative = self._generate_single_patient_risk_narrative(data)
        return {**data, "narrative": narrative}

    def _analyze_global_risks(self, top_n: int = 20) -> dict:
        """分析全局高风险患者"""
        # 获取所有患者的风险评分（批量计算）
        query = """
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(d:Disease)
            OPTIONAL MATCH (v)-[:UNDERWENT]->(s:Surgery)
            WITH p,
                 count(DISTINCT v) AS visit_count,
                 avg(v.length_of_stay) AS avg_los,
                 count(DISTINCT CASE WHEN d.type = 'western' THEN d.name END) AS western_count,
                 count(DISTINCT s) AS surgery_count,
                 collect(DISTINCT CASE WHEN d.type = 'western' THEN d.name END) AS diseases
            RETURN p.patient_id AS patient_id, p.age AS age,
                   visit_count, avg_los, western_count, surgery_count, diseases
            ORDER BY (visit_count * 3 + western_count * 2 + avg_los * 0.5 + surgery_count) DESC
            LIMIT $limit
        """
        recs = neo4j_client.run(query, {"limit": top_n})

        high_risk_patients = []
        for r in recs:
            diseases = [d for d in r["diseases"] if d]
            risk_score = self._calculate_risk_score(
                r.get("visit_count", 0),
                r.get("western_count", 0),
                r.get("avg_los", 0) or 0,
                r.get("surgery_count", 0),
                r.get("age", 0) or 0,
                diseases,
            )
            risk_level = self._get_risk_level(risk_score)
            risk_factors = self._get_risk_factors(
                r.get("visit_count", 0),
                r.get("western_count", 0),
                r.get("avg_los", 0) or 0,
                r.get("age") or 0,
                diseases,
                r.get("surgery_count", 0),
            )

            high_risk_patients.append({
                "patient_id": r["patient_id"],
                "age": r.get("age"),
                "visit_count": r["visit_count"],
                "avg_los": round(r["avg_los"] or 0, 1),
                "disease_count": r["western_count"],
                "surgery_count": r["surgery_count"],
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_factors": risk_factors,
            })

        # 统计分布
        score_distribution = {"极高": 0, "高": 0, "中": 0, "低": 0}
        for p in high_risk_patients:
            score_distribution[p["risk_level"]] = score_distribution.get(p["risk_level"], 0) + 1

        data = {
            "type": "global_risk",
            "high_risk_patients": high_risk_patients,
            "score_distribution": score_distribution,
        }

        narrative = self._generate_global_risk_narrative(data)
        return {**data, "narrative": narrative}

    def _calculate_risk_score(self, visit_count: int, disease_count: int,
                               avg_los: float, surgery_count: int,
                               age: int, diseases: list) -> int:
        """计算风险评分"""
        score = 0
        if visit_count >= 10:
            score += 30
        elif visit_count >= 5:
            score += 20
        elif visit_count >= 3:
            score += 10

        if disease_count >= 5:
            score += 20
        elif disease_count >= 3:
            score += 10

        if avg_los >= 15:
            score += 20
        elif avg_los >= 10:
            score += 10

        if age >= 75:
            score += 15
        elif age >= 65:
            score += 10

        cancer_keywords = ["恶性肿瘤", "癌", "转移", "继发恶性肿瘤", "终末期"]
        if any(any(kw in d for kw in cancer_keywords) for d in diseases):
            score += 20

        if surgery_count >= 2:
            score += 10

        return score

    def _get_risk_level(self, score: int) -> str:
        if score >= 70:
            return "极高"
        elif score >= 50:
            return "高"
        elif score >= 30:
            return "中"
        else:
            return "低"

    def _get_risk_factors(self, visit_count: int, disease_count: int,
                           avg_los: float, age: int, diseases: list,
                           surgery_count: int) -> list:
        """获取风险因素列表"""
        factors = []
        if visit_count >= 5:
            factors.append(f"高频就诊({visit_count}次)")
        if disease_count >= 3:
            factors.append(f"多病共存({disease_count}种)")
        if avg_los >= 10:
            factors.append(f"住院天数长({round(avg_los, 1)}天)")
        if age >= 65:
            factors.append(f"高龄({age}岁)")
        cancer_keywords = ["恶性肿瘤", "癌", "转移", "继发恶性肿瘤", "终末期"]
        if any(any(kw in d for kw in cancer_keywords) for d in diseases):
            factors.append("恶性肿瘤/终末期")
        if surgery_count >= 2:
            factors.append(f"多次手术({surgery_count}次)")
        return factors

    def _generate_single_patient_risk_narrative(self, data: dict) -> str:
        """生成单患者风险预警叙事"""
        system = (
            "你是一位资深临床风险管理专家。请基于提供的患者风险评估数据，"
            "生成个性化的风险预警叙事，包括：风险等级、主要风险因素、"
            "建议关注的临床要点和随访建议。中文输出，专业简洁。"
        )

        lines = [
            f"患者: {data['patient_id']}",
            f"年龄: {data.get('age', '未知')}岁",
            f"就诊次数: {data['visit_count']}",
            f"平均住院天数: {data['avg_los']}天",
            f"西医诊断数: {data['disease_count']}",
            f"风险评分: {data['risk_score']}/100",
            f"风险等级: {data['risk_level']}",
            "",
            "风险因素:",
        ]
        for f in data["risk_factors"]:
            lines.append(f"  - {f}")

        lines.append("\n主要诊断:")
        for d in data["diseases"][:8]:
            lines.append(f"  - {d}")

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(lines)},
        ]
        return llm_service.chat(messages, temperature=0.4, max_tokens=2000, cache_namespace=f"risk:patient:{data.get('patient_id', 'unknown')}")

    def _generate_global_risk_narrative(self, data: dict) -> str:
        """生成全局风险预警叙事"""
        system = (
            "你是一位医院质量管理专家。请基于提供的科室高风险患者统计，"
            "生成科室层面的风险预警叙事，包括：高风险患者分布、主要风险特征、"
            "科室层面的管理改进建议。中文输出，专业简洁。"
        )

        patients = data["high_risk_patients"]
        dist = data["score_distribution"]

        lines = [
            "科室高风险患者分析报告",
            "",
            f"极高风险患者: {dist.get('极高', 0)}人",
            f"高风险患者: {dist.get('高', 0)}人",
            f"中风险患者: {dist.get('中', 0)}人",
            f"低风险患者: {dist.get('低', 0)}人",
            "",
            "Top 10 高风险患者:",
        ]
        for i, p in enumerate(patients[:10], 1):
            lines.append(
                f"{i}. {p['patient_id']} | 评分:{p['risk_score']} | "
                f"等级:{p['risk_level']} | 就诊:{p['visit_count']}次 | "
                f"诊断:{p['disease_count']}种 | 风险因素:{', '.join(p['risk_factors'][:3])}"
            )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(lines)},
        ]
        return llm_service.chat(messages, temperature=0.4, max_tokens=2000, cache_namespace="risk:global")


# 全局单例
risk_prediction_service = RiskPredictionService()
