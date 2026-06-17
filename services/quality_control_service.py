"""
质控异常叙事服务
基于知识图谱规则自动发现医疗数据中的异常模式
"""
from typing import Optional

from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class QualityControlService:
    """质控异常检测与叙事服务"""

    # ========== 质控规则库 ==========

    # 疾病 → 应做检查规则（疾病关键词: [检查关键词]）
    MISSING_EXAM_RULES = [
        {
            "rule_id": "lung_cancer_ct",
            "name": "肺部肿瘤患者应做CT检查",
            "disease_keywords": ["肺恶性肿瘤", "肺占位", "肺结节", "肺癌", "支气管恶性肿瘤", "肺继发恶性肿瘤"],
            "exam_keywords": ["CT平扫", "CT", "胸部CT"],
            "min_cases": 20,
            "expected_rate": 0.5,  # 期望检查率50%
        },
        {
            "rule_id": "cerebral_infarction_mri",
            "name": "脑梗死患者应做磁共振/CT检查",
            "disease_keywords": ["脑梗死", "脑出血", "脑血管病"],
            "exam_keywords": ["磁共振", "CT平扫", "CT", "脑血管"],
            "min_cases": 20,
            "expected_rate": 0.5,
        },
        {
            "rule_id": "gastric_endoscopy",
            "name": "胃病患者应做胃镜检查",
            "disease_keywords": ["慢性胃炎", "胃溃疡", "胃癌", "胃恶性肿瘤", "上消化道出血", "幽门螺旋杆菌"],
            "exam_keywords": ["胃镜", "肠镜", "消化道造影", "幽门螺杆菌"],
            "min_cases": 10,
            "expected_rate": 0.2,
        },
        {
            "rule_id": "cardiac_ecg",
            "name": "心脏病患者应做心电图",
            "disease_keywords": ["冠心病", "心力衰竭", "心律失常", "心房颤动", "心肌梗死", "高血压病3级"],
            "exam_keywords": ["心电图", "心脏彩超", "动态心电图"],
            "min_cases": 20,
            "expected_rate": 0.8,
        },
        {
            "rule_id": "liver_ultrasound",
            "name": "肝病患者应做腹部超声/CT",
            "disease_keywords": ["肝囊肿", "脂肪肝", "肝硬化", "肝占位", "慢性乙型肝炎", "肝恶性肿瘤"],
            "exam_keywords": ["腹部彩色多普勒超声", "腹部超声", "腹部CT", "肝"],
            "min_cases": 20,
            "expected_rate": 0.5,
        },
        {
            "rule_id": "anemia_blood",
            "name": "贫血患者应查血常规",
            "disease_keywords": ["贫血", "白细胞减少", "血小板减少", "骨髓抑制"],
            "exam_keywords": ["血常规", "血细胞分析", "骨髓", "血生化"],
            "min_cases": 20,
            "expected_rate": 0.8,
        },
    ]

    # 诊断 → 应使用药品规则
    DIAGNOSIS_DRUG_RULES = [
        {
            "rule_id": "anemia_iron",
            "name": "贫血患者应使用铁剂/促红素",
            "disease_keywords": ["贫血"],
            "drug_keywords": ["铁", "促红素", "EPO", "叶酸", "维生素B12", "蔗糖铁"],
            "min_cases": 20,
            "expected_rate": 0.3,
        },
        {
            "rule_id": "hypoproteinemia_albumin",
            "name": "低蛋白血症应补充白蛋白/营养支持",
            "disease_keywords": ["低蛋白血症", "营养不良", "恶病质"],
            "drug_keywords": ["白蛋白", "人血白蛋白", "氨基酸", "脂肪乳", "肠内营养"],
            "min_cases": 20,
            "expected_rate": 0.3,
        },
        {
            "rule_id": "hypertension_antihypertensive",
            "name": "高血压应使用降压药",
            "disease_keywords": ["高血压"],
            "drug_keywords": ["氨氯地平", "缬沙坦", "硝苯地平", "贝那普利", "美托洛尔", "厄贝沙坦", "利尿", "降压"],
            "min_cases": 20,
            "expected_rate": 0.5,
        },
        {
            "rule_id": "diabetes_antidiabetic",
            "name": "糖尿病应使用降糖药/胰岛素",
            "disease_keywords": ["糖尿病", "血糖升高", "2型糖尿病"],
            "drug_keywords": ["胰岛素", "二甲双胍", "格列", "阿卡波糖", "瑞格列奈", "利拉鲁肽"],
            "min_cases": 20,
            "expected_rate": 0.5,
        },
    ]

    # 潜在药物相互作用规则（简化版）
    DRUG_INTERACTION_RULES = [
        {
            "rule_id": "warfarin_aspirin",
            "name": "华法林与阿司匹林/NSAIDs联用（出血风险）",
            "drug1_keywords": ["华法林"],
            "drug2_keywords": ["阿司匹林", "布洛芬", "双氯芬酸"],
        },
        {
            "rule_id": "two_nsaid",
            "name": "两种NSAIDs联用",
            "drug1_keywords": ["阿司匹林", "布洛芬", "双氯芬酸", "塞来昔布", "吲哚美辛"],
            "drug2_keywords": ["阿司匹林", "布洛芬", "双氯芬酸", "塞来昔布", "吲哚美辛"],
        },
        {
            "rule_id": "acei_diuretic_potassium",
            "name": "ACEI/ARB与保钾利尿剂联用（高钾风险）",
            "drug1_keywords": ["缬沙坦", "厄贝沙坦", "贝那普利", "培哚普利"],
            "drug2_keywords": ["螺内酯", "氨苯蝶啶", "阿米洛利"],
        },
        {
            "rule_id": "opioid_benzodiazepine",
            "name": "阿片类与苯二氮䓬类联用（呼吸抑制风险）",
            "drug1_keywords": ["吗啡", "羟考酮", "芬太尼", "曲马多"],
            "drug2_keywords": ["地西泮", "劳拉西泮", "阿普唑仑", "艾司唑仑"],
        },
    ]

    # ========== 核心接口 ==========

    def generate_quality_control_narrative(self, rule_type: Optional[str] = None,
                                           disease_name: Optional[str] = None) -> dict:
        """
        生成质控异常分析叙事
        rule_type: missing_exam | abnormal_los | short_readmission | diagnosis_drug_mismatch | drug_interaction | all
        """
        results = {}

        if rule_type in ("missing_exam", "all"):
            results["missing_exams"] = self.detect_missing_exams(disease_name)

        if rule_type in ("abnormal_los", "all"):
            results["abnormal_los"] = self.detect_abnormal_los(disease_name)

        if rule_type in ("short_readmission", "all"):
            results["short_readmissions"] = self.detect_short_readmission(disease_name)

        if rule_type in ("diagnosis_drug_mismatch", "all"):
            results["diagnosis_drug_mismatch"] = self.detect_diagnosis_drug_mismatch(disease_name)

        if rule_type in ("drug_interaction", "all"):
            results["drug_interactions"] = self.detect_drug_interactions(disease_name)

        # 汇总统计
        summary = self._summarize_results(results)

        narrative = self._generate_narrative(summary, disease_name)

        return {
            "type": "quality_control",
            "rule_type": rule_type or "all",
            "disease_name": disease_name,
            "summary": summary,
            "details": results,
            "narrative": narrative,
        }

    # ========== 异常检测方法 ==========

    def detect_missing_exams(self, disease_name: Optional[str] = None) -> list:
        """检测缺失必要检查"""
        findings = []

        for rule in self.MISSING_EXAM_RULES:
            # 构建疾病匹配条件
            disease_conditions = " OR ".join([f"d.name CONTAINS '{kw}'" for kw in rule["disease_keywords"]])
            if disease_name:
                # 如果指定了疾病，只检查相关规则
                if not any(kw in disease_name for kw in rule["disease_keywords"]):
                    continue

            query = f"""
                MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)
                WHERE d.type = 'western' AND ({disease_conditions})
                OPTIONAL MATCH (v)-[:PERFORMED_EXAM]->(e:Exam)
                WITH v, collect(DISTINCT e.name) AS exams
                RETURN count(DISTINCT v) AS total_visits,
                       sum(CASE WHEN any(e IN exams WHERE {' OR '.join([f"e CONTAINS '{kw}'" for kw in rule['exam_keywords']])}) THEN 1 ELSE 0 END) AS with_exam
            """
            recs = neo4j_client.run(query)
            if not recs:
                continue

            r = dict(recs[0])
            total = r.get("total_visits", 0) or 0
            with_exam = r.get("with_exam", 0) or 0

            if total < rule["min_cases"]:
                continue

            rate = with_exam / total if total > 0 else 0
            if rate < rule["expected_rate"]:
                missing = total - with_exam
                findings.append({
                    "rule_id": rule["rule_id"],
                    "rule_name": rule["name"],
                    "disease_keywords": rule["disease_keywords"],
                    "exam_keywords": rule["exam_keywords"],
                    "total_visits": total,
                    "with_exam": with_exam,
                    "missing_count": missing,
                    "exam_rate": round(rate * 100, 1),
                    "expected_rate": round(rule["expected_rate"] * 100, 1),
                    "severity": "high" if rate < rule["expected_rate"] * 0.5 else "medium",
                })

        return findings

    def detect_abnormal_los(self, disease_name: Optional[str] = None, z_threshold: float = 2.5) -> dict:
        """检测住院天数异常"""
        params = {}
        if disease_name:
            disease_name_norm = self._normalize_disease_name(disease_name)
            match_clause = "MATCH (d:Disease {name: $disease})<-[:DIAGNOSED_WITH]-(v:Visit)"
            params = {"disease": disease_name_norm}
        else:
            match_clause = "MATCH (v:Visit)"

        # 统计分布
        stats_query = f"""
            {match_clause}
            RETURN count(v) AS n,
                   avg(v.length_of_stay) AS mean_los,
                   stDev(v.length_of_stay) AS std_los,
                   percentileCont(v.length_of_stay, 0.5) AS median_los,
                   min(v.length_of_stay) AS min_los,
                   max(v.length_of_stay) AS max_los
        """
        stats_recs = neo4j_client.run(stats_query, params)
        if not stats_recs:
            return {"stats": {}, "abnormal_cases": []}

        stats = dict(stats_recs[0])
        n = stats.get("n", 0) or 0
        mean = stats.get("mean_los", 0) or 0
        std = stats.get("std_los", 0) or 0
        median = stats.get("median_los", 0) or 0

        if n == 0:
            return {"stats": stats, "abnormal_cases": []}

        # 异常阈值
        upper = mean + z_threshold * std if std else mean * 3
        lower = max(0, mean - z_threshold * std) if std else 0

        # 找出异常病例（取Top 30）
        cases_query = f"""
            {match_clause}
            MATCH (p:Patient)-[:HAS_VISIT]->(v)
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(d:Disease)
            WHERE v.length_of_stay > $upper OR v.length_of_stay < $lower
            WITH v, p, collect(DISTINCT d.name) AS diseases
            RETURN v.visit_id AS visit_id, p.patient_id AS patient_id,
                   v.admission_date AS admission_date, v.length_of_stay AS los, diseases
            ORDER BY v.length_of_stay DESC
            LIMIT 30
        """
        cases_recs = neo4j_client.run(cases_query, {**params, "upper": upper, "lower": lower})

        abnormal_cases = []
        for r in cases_recs:
            los = r.get("los", 0) or 0
            abnormal_cases.append({
                "visit_id": r["visit_id"],
                "patient_id": r["patient_id"],
                "admission_date": r["admission_date"],
                "length_of_stay": los,
                "diagnoses": [d for d in r["diseases"] if d],
                "type": "过长" if los > upper else "过短",
            })

        return {
            "stats": {
                "total_visits": n,
                "mean_los": round(mean, 1),
                "median_los": round(median, 1),
                "std_los": round(std, 1) if std else 0,
                "min_los": stats.get("min_los"),
                "max_los": stats.get("max_los"),
                "upper_threshold": round(upper, 1),
                "lower_threshold": round(lower, 1),
            },
            "abnormal_cases": abnormal_cases,
        }

    def detect_short_readmission(self, disease_name: Optional[str] = None, days: int = 30) -> list:
        """检测短时间内再入院"""
        params = {"days": days}
        if disease_name:
            disease_name_norm = self._normalize_disease_name(disease_name)
            match_clause = "MATCH (d:Disease {name: $disease})<-[:DIAGNOSED_WITH]-(v:Visit)"
            params["disease"] = disease_name_norm
        else:
            match_clause = "MATCH (v:Visit)"

        query = f"""
            {match_clause}
            MATCH (p:Patient)-[:HAS_VISIT]->(v)
            WITH p, v ORDER BY p.patient_id, v.admission_date
            WITH p, collect(v) AS visits
            UNWIND range(0, size(visits)-2) AS i
            WITH p, visits[i] AS v1, visits[i+1] AS v2
            WHERE duration.inDays(date(v1.discharge_date), date(v2.admission_date)).days <= $days
              AND duration.inDays(date(v1.discharge_date), date(v2.admission_date)).days >= 0
            OPTIONAL MATCH (v1)-[:DIAGNOSED_WITH]->(d1:Disease)
            OPTIONAL MATCH (v2)-[:DIAGNOSED_WITH]->(d2:Disease)
            RETURN p.patient_id AS patient_id,
                   v1.visit_id AS visit1_id, v1.discharge_date AS discharge_date,
                   v2.visit_id AS visit2_id, v2.admission_date AS readmit_date,
                   duration.inDays(date(v1.discharge_date), date(v2.admission_date)).days AS interval_days,
                   collect(DISTINCT d1.name) AS diagnoses1, collect(DISTINCT d2.name) AS diagnoses2
            ORDER BY interval_days
            LIMIT 50
        """
        recs = neo4j_client.run(query, params)

        findings = []
        for r in recs:
            findings.append({
                "patient_id": r["patient_id"],
                "previous_visit_id": r["visit1_id"],
                "previous_discharge_date": r["discharge_date"],
                "readmit_visit_id": r["visit2_id"],
                "readmit_date": r["readmit_date"],
                "interval_days": r["interval_days"],
                "previous_diagnoses": [d for d in r["diagnoses1"] if d],
                "readmit_diagnoses": [d for d in r["diagnoses2"] if d],
            })

        return findings

    def detect_diagnosis_drug_mismatch(self, disease_name: Optional[str] = None) -> list:
        """检测诊断-药品不匹配（应使用但未使用）"""
        findings = []

        for rule in self.DIAGNOSIS_DRUG_RULES:
            if disease_name and not any(kw in disease_name for kw in rule["disease_keywords"]):
                continue

            disease_conditions = " OR ".join([f"d.name CONTAINS '{kw}'" for kw in rule["disease_keywords"]])

            query = f"""
                MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)
                WHERE d.type = 'western' AND ({disease_conditions})
                OPTIONAL MATCH (v)-[:PRESCRIBED]->(dr:Drug)
                WITH v, collect(DISTINCT dr.name) AS drugs
                RETURN count(DISTINCT v) AS total_visits,
                       sum(CASE WHEN any(dr IN drugs WHERE {' OR '.join([f"dr CONTAINS '{kw}'" for kw in rule['drug_keywords']])}) THEN 1 ELSE 0 END) AS with_drug
            """
            recs = neo4j_client.run(query)
            if not recs:
                continue

            r = dict(recs[0])
            total = r.get("total_visits", 0) or 0
            with_drug = r.get("with_drug", 0) or 0

            if total < rule["min_cases"]:
                continue

            rate = with_drug / total if total > 0 else 0
            if rate < rule["expected_rate"]:
                findings.append({
                    "rule_id": rule["rule_id"],
                    "rule_name": rule["name"],
                    "disease_keywords": rule["disease_keywords"],
                    "drug_keywords": rule["drug_keywords"],
                    "total_visits": total,
                    "with_drug": with_drug,
                    "missing_count": total - with_drug,
                    "drug_rate": round(rate * 100, 1),
                    "expected_rate": round(rule["expected_rate"] * 100, 1),
                    "severity": "high" if rate < rule["expected_rate"] * 0.5 else "medium",
                })

        return findings

    def detect_drug_interactions(self, disease_name: Optional[str] = None) -> list:
        """检测潜在药物相互作用"""
        params = {}
        if disease_name:
            disease_name_norm = self._normalize_disease_name(disease_name)
            match_clause = "MATCH (d:Disease {name: $disease})<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr1:Drug), (v)-[:PRESCRIBED]->(dr2:Drug)"
            params = {"disease": disease_name_norm}
        else:
            match_clause = "MATCH (v:Visit)-[:PRESCRIBED]->(dr1:Drug), (v)-[:PRESCRIBED]->(dr2:Drug)"

        findings = []
        seen_pairs = set()

        for rule in self.DRUG_INTERACTION_RULES:
            cond1 = " OR ".join([f"dr1.name CONTAINS '{kw}'" for kw in rule["drug1_keywords"]])
            cond2 = " OR ".join([f"dr2.name CONTAINS '{kw}'" for kw in rule["drug2_keywords"]])

            query = f"""
                {match_clause}
                WHERE id(dr1) < id(dr2) AND ({cond1}) AND ({cond2})
                RETURN dr1.name AS drug1, dr2.name AS drug2, count(DISTINCT v) AS cnt
                ORDER BY cnt DESC LIMIT 20
            """
            recs = neo4j_client.run(query, params)
            pair_cases = []
            for r in recs:
                pair = tuple(sorted([r["drug1"], r["drug2"]]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                pair_cases.append({
                    "drug1": r["drug1"],
                    "drug2": r["drug2"],
                    "visit_count": r["cnt"],
                })

            if pair_cases:
                findings.append({
                    "rule_id": rule["rule_id"],
                    "rule_name": rule["name"],
                    "cases": pair_cases,
                })

        return findings

    def detect_patient_issues(self, patient_id: str) -> list:
        """查询单个患者的质控异常提醒"""
        issues = []

        # 1. 住院天数异常
        los_query = """
            MATCH (p:Patient {patient_id: $patient_id})-[:HAS_VISIT]->(v:Visit)
            WITH v, v.length_of_stay AS los
            ORDER BY los DESC
            LIMIT 1
            MATCH (all_v:Visit)
            WITH v, los, avg(all_v.length_of_stay) AS mean_los, stDev(all_v.length_of_stay) AS std_los
            WHERE los > mean_los + 2.5 * std_los
            RETURN v.visit_id AS visit_id, v.admission_date AS admission_date, los, mean_los
        """
        los_recs = neo4j_client.run(los_query, {"patient_id": patient_id})
        for r in los_recs:
            issues.append({
                "type": "住院天数异常",
                "level": "warning",
                "description": f"住院 {r['los']} 天，高于科室均值 {r['mean_los']:.1f} 天",
                "visit_id": r["visit_id"],
                "date": r["admission_date"],
            })

        # 2. 30天内再入院
        readmit_query = """
            MATCH (p:Patient {patient_id: $patient_id})-[:HAS_VISIT]->(v:Visit)
            WITH p, v ORDER BY v.admission_date
            WITH p, collect(v) AS visits
            UNWIND range(0, size(visits)-2) AS i
            WITH visits[i] AS v1, visits[i+1] AS v2
            WHERE duration.inDays(date(v1.discharge_date), date(v2.admission_date)).days <= 30
              AND duration.inDays(date(v1.discharge_date), date(v2.admission_date)).days >= 0
            RETURN v2.visit_id AS visit_id, v2.admission_date AS admission_date,
                   duration.inDays(date(v1.discharge_date), date(v2.admission_date)).days AS interval_days
        """
        readmit_recs = neo4j_client.run(readmit_query, {"patient_id": patient_id})
        for r in readmit_recs:
            issues.append({
                "type": "30天内再入院",
                "level": "danger",
                "description": f"距离上次出院仅 {r['interval_days']} 天再次入院",
                "visit_id": r["visit_id"],
                "date": r["admission_date"],
            })

        # 3. 药物相互作用
        drug_query = """
            MATCH (p:Patient {patient_id: $patient_id})-[:HAS_VISIT]->(v:Visit)-[:PRESCRIBED]->(d:Drug)
            WITH v, collect(DISTINCT d.name) AS drugs
            RETURN v.visit_id AS visit_id, drugs
        """
        drug_recs = neo4j_client.run(drug_query, {"patient_id": patient_id})
        for r in drug_recs:
            drugs = r["drugs"]
            for rule in self.DRUG_INTERACTION_RULES:
                matched1 = [d for d in drugs if any(kw in d for kw in rule["drug1_keywords"])]
                matched2 = [d for d in drugs if any(kw in d for kw in rule["drug2_keywords"])]
                if matched1 and matched2:
                    # 排除同一药品
                    pair_drugs = list(set(matched1 + matched2))
                    if len(pair_drugs) >= 2:
                        issues.append({
                            "type": "药物相互作用",
                            "level": "danger",
                            "description": f"{rule['name']}: {', '.join(pair_drugs[:2])}",
                            "visit_id": r["visit_id"],
                            "rule_id": rule["rule_id"],
                        })

        # 4. 缺失检查（基于规则）
        for rule in self.MISSING_EXAM_RULES:
            query = f"""
                MATCH (p:Patient {{patient_id: $patient_id}})-[:HAS_VISIT]->(v:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
                WHERE d.type = 'western' AND ({" OR ".join([f"d.name CONTAINS '{kw}'" for kw in rule['disease_keywords']])})
                OPTIONAL MATCH (v)-[:PERFORMED_EXAM]->(e:Exam)
                WITH v, collect(DISTINCT e.name) AS exams
                WHERE NOT any(e IN exams WHERE {' OR '.join([f"e CONTAINS '{kw}'" for kw in rule['exam_keywords']])})
                RETURN v.visit_id AS visit_id, v.admission_date AS admission_date
                LIMIT 5
            """
            missing_recs = neo4j_client.run(query, {"patient_id": patient_id})
            for r in missing_recs:
                issues.append({
                    "type": "缺失检查",
                    "level": "warning",
                    "description": f"{rule['name']}",
                    "visit_id": r["visit_id"],
                    "date": r["admission_date"],
                    "rule_id": rule["rule_id"],
                })

        # 5. 诊断-药品不匹配
        for rule in self.DIAGNOSIS_DRUG_RULES:
            query = f"""
                MATCH (p:Patient {{patient_id: $patient_id}})-[:HAS_VISIT]->(v:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
                WHERE d.type = 'western' AND ({" OR ".join([f"d.name CONTAINS '{kw}'" for kw in rule['disease_keywords']])})
                OPTIONAL MATCH (v)-[:PRESCRIBED]->(dr:Drug)
                WITH v, collect(DISTINCT dr.name) AS drugs
                WHERE NOT any(dr IN drugs WHERE {' OR '.join([f"dr CONTAINS '{kw}'" for kw in rule['drug_keywords']])})
                RETURN v.visit_id AS visit_id, v.admission_date AS admission_date
                LIMIT 5
            """
            mismatch_recs = neo4j_client.run(query, {"patient_id": patient_id})
            for r in mismatch_recs:
                issues.append({
                    "type": "诊断-药品不匹配",
                    "level": "warning",
                    "description": f"{rule['name']}",
                    "visit_id": r["visit_id"],
                    "date": r["admission_date"],
                    "rule_id": rule["rule_id"],
                })

        return issues

    # ========== 辅助方法 ==========

    def _normalize_disease_name(self, name: str) -> str:
        """规范化疾病名"""
        name = name.strip()
        if "::" not in name:
            recs = neo4j_client.run(
                "MATCH (d:Disease) WHERE d.type = 'western' AND d.name CONTAINS $name RETURN d.name AS name LIMIT 1",
                {"name": name}
            )
            if recs:
                return recs[0]["name"]
        return name

    def _summarize_results(self, results: dict) -> dict:
        """汇总异常统计"""
        missing_exams = results.get("missing_exams", [])
        abnormal_los = results.get("abnormal_los", {})
        short_readmissions = results.get("short_readmissions", [])
        diagnosis_drug = results.get("diagnosis_drug_mismatch", [])
        drug_interactions = results.get("drug_interactions", [])

        total_missing_exams = sum(f["missing_count"] for f in missing_exams)
        total_drug_mismatch = sum(f["missing_count"] for f in diagnosis_drug)
        total_interaction_cases = sum(len(rule.get("cases", [])) for rule in drug_interactions)

        return {
            "missing_exam_rules_triggered": len(missing_exams),
            "total_missing_exams": total_missing_exams,
            "abnormal_los_cases": len(abnormal_los.get("abnormal_cases", [])),
            "short_readmission_cases": len(short_readmissions),
            "diagnosis_drug_rules_triggered": len(diagnosis_drug),
            "total_diagnosis_drug_missing": total_drug_mismatch,
            "drug_interaction_rules_triggered": len(drug_interactions),
            "total_drug_interaction_cases": total_interaction_cases,
            "overall_risk_score": self._calculate_risk_score(
                len(missing_exams), len(abnormal_los.get("abnormal_cases", [])),
                len(short_readmissions), len(diagnosis_drug), total_interaction_cases
            ),
        }

    def _calculate_risk_score(self, missing_exams: int, abnormal_los: int,
                              readmissions: int, drug_mismatch: int,
                              drug_interactions: int) -> str:
        """计算综合风险等级"""
        score = missing_exams + abnormal_los // 10 + readmissions // 10 + drug_mismatch + drug_interactions
        if score >= 10:
            return "高风险"
        elif score >= 5:
            return "中风险"
        elif score >= 1:
            return "低风险"
        return "正常"

    def _generate_narrative(self, summary: dict, disease_name: Optional[str] = None) -> str:
        """调用LLM生成质控叙事"""
        target = f"疾病 '{disease_name}'" if disease_name else "本科室全量数据"

        system = (
            "你是一位医院质量管理专家。请基于下方的质控异常检测数据，生成结构化、专业的质控分析报告。"
            "报告应包括：1) 总体风险评级；2) 各类异常问题的具体情况和改进建议；"
            "3) 重点关注的高风险病例提示。注意：这些是基于统计规则发现的疑似异常，需人工复核确认。"
            "语言专业、客观，中文输出。"
        )

        lines = [f"质控分析对象: {target}", ""]
        lines.append("=== 总体风险评级 ===")
        lines.append(f"综合风险等级: {summary.get('overall_risk_score', '未知')}")
        lines.append(f"触发缺失检查规则数: {summary.get('missing_exam_rules_triggered', 0)}")
        lines.append(f"缺失检查总人次: {summary.get('total_missing_exams', 0)}")
        lines.append(f"住院天数异常病例数: {summary.get('abnormal_los_cases', 0)}")
        lines.append(f"30天内再入院病例数: {summary.get('short_readmission_cases', 0)}")
        lines.append(f"触发诊断-药品不匹配规则数: {summary.get('diagnosis_drug_rules_triggered', 0)}")
        lines.append(f"应用药未用药总人次: {summary.get('total_diagnosis_drug_missing', 0)}")
        lines.append(f"触发药物相互作用规则数: {summary.get('drug_interaction_rules_triggered', 0)}")
        lines.append(f"潜在药物相互作用案例数: {summary.get('total_drug_interaction_cases', 0)}")

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(lines)},
        ]
        ns = f"quality_control:{disease_name}" if disease_name else "quality_control:all"
        return llm_service.chat(messages, temperature=0.4, max_tokens=2500, cache_namespace=ns)


# 全局单例
quality_control_service = QualityControlService()
