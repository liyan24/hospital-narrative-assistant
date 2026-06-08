"""
LLM + 知识图谱 RAG 问答服务
基于Neo4j检索真实关系子图，避免LLM编造
"""
import re
from typing import List, Optional

from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class KGRAGService:
    """基于知识图谱的检索增强生成服务"""

    DEFAULT_PATIENT_ID = "4116-002-000000000000000000000021"

    def answer(self, question: str) -> dict:
        """
        回答用户问题
        返回: {"question": str, "answer": str, "sources": list, "retrieved": dict}
        """
        if not question or not question.strip():
            return {
                "question": "",
                "answer": "请输入问题",
                "sources": [],
                "retrieved": {},
            }

        question = question.strip()

        # 1. 意图识别 + 实体抽取
        intent, entity, entity_type = self._parse_intent(question)

        # 2. 基于意图检索图谱子图
        retrieved = self._retrieve(intent, entity, entity_type, question)

        # 3. 构建prompt并调用LLM
        answer = self._generate_answer(question, retrieved)

        # 4. 整理来源
        sources = self._build_sources(retrieved)

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "retrieved": retrieved,
        }

    def _parse_intent(self, question: str) -> tuple:
        """
        简单规则意图识别
        返回: (intent, entity, entity_type)
        intent: patient | disease | drug | comorbidity | readmission | general
        """
        q = question.lower()

        # 患者ID匹配 (4116-xxx... 或类似格式)
        patient_match = re.search(r"(4116-\d{3}-\d{24})", question)
        if not patient_match:
            # 尝试匹配 "患者" 后面的ID
            patient_match = re.search(r"患者[\s:：]*(\S{10,})", question)
        if not patient_match:
            patient_match = re.search(r"病人[\s:：]*(\S{10,})", question)

        if patient_match:
            return "patient", patient_match.group(1), "patient_id"

        # 用药相关意图
        if any(k in q for k in ["用什么药", "吃什么药", "药物", "药品", "用药", "治疗方案"]):
            disease = self._extract_disease(question)
            if disease:
                return "drug", disease, "disease"
            return "drug", None, None

        # 合并症相关
        if any(k in q for k in ["合并症", "并发症", "共现", "一起", "同时患有"]):
            disease = self._extract_disease(question)
            if disease:
                return "comorbidity", disease, "disease"
            return "comorbidity", None, None

        # 再入院相关
        if any(k in q for k in ["再入院", "复诊", "多次就诊", "回来", "重复入院"]):
            return "readmission", None, None

        # 诊疗路径 / 疾病相关
        if any(k in q for k in ["诊疗路径", "怎么治疗", "如何治疗", "诊疗", "诊断", "疗法"]):
            disease = self._extract_disease(question)
            if disease:
                return "disease", disease, "disease"
            return "disease", None, None

        # 默认尝试提取疾病名
        disease = self._extract_disease(question)
        if disease:
            return "disease", disease, "disease"

        return "general", None, None

    def _extract_disease(self, question: str) -> Optional[str]:
        """从问题中提取可能的疾病名（简单规则）"""
        # 常见疾病关键词库
        disease_keywords = [
            "肺恶性肿瘤", "高血压", "糖尿病", "冠心病", "脑梗死", "肺炎", "肺癌",
            "痰瘀互结证", "气血两虚证", "脾胃不和证", "肝肾阴虚证", "脾虚痰湿证",
            "继发性肺部感染", "骨质疏松", "贫血", "白细胞减少", "血小板减少",
            "肺积", "血证", "胃脘痛", "腹痛", "眩晕", "头痛", "咳嗽", "咯血",
        ]
        for d in disease_keywords:
            if d in question:
                return d

        # 尝试匹配"患有XXX"、"XXX患者"、"XXX的治疗"
        patterns = [
            r"患有[\s]*([^，。？！；]+?)[的患者",
            r"([^，。？！；]{2,20})患者",
            r"([^，。？！；]{2,20})的治疗",
            r"([^，。？！；]{2,20})用什么药",
            r"([^，。？！；]{2,20})合并症",
        ]
        for p in patterns:
            m = re.search(p, question)
            if m:
                candidate = m.group(1).strip()
                if len(candidate) >= 2:
                    return candidate
        return None

    def _resolve_disease_names(self, keyword: str) -> List[str]:
        """通过CONTAINS模糊查询，将关键词解析为图谱中实际存在的疾病名列表"""
        records = neo4j_client.run("""
            MATCH (d:Disease)
            WHERE d.name CONTAINS $keyword
            RETURN d.name AS name
            LIMIT 50
        """, {"keyword": keyword})
        names = [r["name"] for r in records if r["name"]]
        # 去重并保持顺序
        seen = set()
        unique = []
        for n in names:
            if n not in seen:
                seen.add(n)
                unique.append(n)
        return unique

    def _retrieve(self, intent: str, entity: Optional[str], entity_type: Optional[str], question: str) -> dict:
        """根据意图从Neo4j检索数据"""
        if intent == "patient" and entity:
            return self._retrieve_patient(entity, question)

        # 疾病相关意图：先解析关键词为图谱中的实际疾病名列表
        if intent in ("disease", "drug", "comorbidity") and entity:
            disease_names = self._resolve_disease_names(entity)
            if not disease_names:
                # fallback: 用原关键词再试一次（可能完全一致匹配）
                disease_names = [entity]
            if intent == "disease":
                return self._retrieve_disease(disease_names)
            if intent == "drug":
                return self._retrieve_drug_pattern(disease_names)
            if intent == "comorbidity":
                return self._retrieve_comorbidity(disease_names)

        if intent == "readmission":
            return self._retrieve_readmission_summary()

        # general / 无实体: 返回全局统计
        return self._retrieve_global_stats()

    def _is_recent_query(self, question: str) -> bool:
        """判断问题是否在询问最近/最后一次就诊"""
        q = question.lower()
        return any(k in q for k in ["最后一次", "最近", "最后", "最近一次", "最近一次", "latest", "recent", "last"])

    def _retrieve_patient(self, patient_id: str, question: str = "") -> dict:
        """检索患者完整就诊时间线"""
        records = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)
            OPTIONAL MATCH (v)-[rd:DIAGNOSED_WITH]->(d:Disease)
            OPTIONAL MATCH (v)-[:PRESCRIBED]->(dr:Drug)
            OPTIONAL MATCH (v)-[:PERFORMED_EXAM]->(e:Exam)
            OPTIONAL MATCH (v)-[:UNDERWENT]->(s:Surgery)
            OPTIONAL MATCH (v)-[:CHIEF_COMPLAINT]->(c:ChiefComplaint)
            RETURN v.visit_id AS visit_id,
                   v.admission_date AS admission_date,
                   v.discharge_date AS discharge_date,
                   v.length_of_stay AS los,
                   collect(DISTINCT d.name) AS diseases,
                   collect(DISTINCT dr.name) AS drugs,
                   collect(DISTINCT e.name) AS exams,
                   collect(DISTINCT s.name) AS surgeries,
                   collect(DISTINCT c.name) AS complaints
            ORDER BY v.admission_date
        """, {"pid": patient_id})

        visits = []
        for r in records:
            visits.append({
                "visit_id": r["visit_id"],
                "admission_date": r["admission_date"],
                "discharge_date": r["discharge_date"],
                "length_of_stay": r["los"],
                "diseases": [x for x in r["diseases"] if x],
                "drugs": [x for x in r["drugs"] if x],
                "exams": [x for x in r["exams"] if x],
                "surgeries": [x for x in r["surgeries"] if x],
                "complaints": [x for x in r["complaints"] if x],
            })

        # 患者基本信息
        info_records = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})
            RETURN p.age AS age, p.gender AS gender
        """, {"pid": patient_id})
        info = info_records[0] if info_records else {}

        # 根据问题选择返回前20次或后20次
        if self._is_recent_query(question):
            displayed_visits = visits[-20:]
        else:
            displayed_visits = visits[:20]

        return {
            "type": "patient_timeline",
            "patient_id": patient_id,
            "patient_age": info.get("age"),
            "patient_gender": info.get("gender"),
            "visit_count": len(visits),
            "visits": displayed_visits,  # 限制数量避免token爆炸
        }

    def _retrieve_disease(self, disease_names: List[str]) -> dict:
        """检索疾病诊疗路径数据（支持多疾病聚合）"""
        # Top 药品
        drug_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
            WHERE d.name IN $names
            RETURN dr.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, {"names": disease_names})
        top_drugs = [{"name": r["name"], "count": r["cnt"]} for r in drug_records]

        # Top 检查
        exam_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PERFORMED_EXAM]->(e:Exam)
            WHERE d.name IN $names
            RETURN e.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, {"names": disease_names})
        top_exams = [{"name": r["name"], "count": r["cnt"]} for r in exam_records]

        # Top 合并症（排除自身）
        comorb_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(co:Disease)
            WHERE d.name IN $names AND NOT co.name IN $names
            RETURN co.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, {"names": disease_names})
        comorbidities = [{"name": r["name"], "count": r["cnt"]} for r in comorb_records]

        # 住院天数统计
        los_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)
            WHERE d.name IN $names
            RETURN count(v) AS visit_count,
                   avg(v.length_of_stay) AS avg_los,
                   percentileCont(v.length_of_stay, 0.5) AS median_los
        """, {"names": disease_names})
        los = los_records[0] if los_records else {}

        display_name = disease_names[0] if len(disease_names) == 1 else f"{disease_names[0]} 等{len(disease_names)}种"
        return {
            "type": "disease_pathway",
            "disease_name": display_name,
            "matched_diseases": disease_names,
            "visit_count": los.get("visit_count", 0),
            "avg_los": round(los.get("avg_los", 0) or 0, 1),
            "median_los": round(los.get("median_los", 0) or 0, 1),
            "top_drugs": top_drugs,
            "top_exams": top_exams,
            "comorbidities": comorbidities,
        }

    def _retrieve_drug_pattern(self, disease_names: List[str]) -> dict:
        """检索疾病用药模式（支持多疾病聚合）"""
        drug_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
            WHERE d.name IN $names
            WITH dr.name AS name, count(DISTINCT v) AS cnt, collect(DISTINCT v.visit_id) AS visits
            ORDER BY cnt DESC LIMIT 10
            RETURN name, cnt, visits
        """, {"names": disease_names})
        top_drugs = [{"name": r["name"], "count": r["cnt"]} for r in drug_records]

        pair_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
            WHERE d.name IN $names
            WITH v, collect(dr.name) AS drugs
            UNWIND drugs AS d1
            UNWIND drugs AS d2
            WITH d1, d2, count(*) AS pair_count WHERE d1 < d2
            RETURN d1, d2, pair_count ORDER BY pair_count DESC LIMIT 10
        """, {"names": disease_names})
        pairs = [{"drug1": r["d1"], "drug2": r["d2"], "count": r["pair_count"]} for r in pair_records]

        display_name = disease_names[0] if len(disease_names) == 1 else f"{disease_names[0]} 等{len(disease_names)}种"
        return {
            "type": "drug_pattern",
            "disease_name": display_name,
            "matched_diseases": disease_names,
            "top_drugs": top_drugs,
            "common_pairs": pairs,
        }

    def _retrieve_comorbidity(self, disease_names: List[str]) -> dict:
        """检索疾病合并症（支持多疾病聚合）"""
        records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(co:Disease)
            WHERE d.name IN $names AND NOT co.name IN $names
            RETURN co.name AS name, count(DISTINCT v) AS cnt,
                   avg(v.length_of_stay) AS avg_los
            ORDER BY cnt DESC LIMIT 15
        """, {"names": disease_names})

        total_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)
            WHERE d.name IN $names
            RETURN count(DISTINCT v) AS total
        """, {"names": disease_names})
        total = total_records[0]["total"] if total_records else 0

        comorbidities = []
        for r in records:
            pct = round(r["cnt"] / total * 100, 1) if total else 0
            comorbidities.append({
                "name": r["name"],
                "count": r["cnt"],
                "percentage": pct,
                "avg_los": round(r["avg_los"] or 0, 1),
            })

        display_name = disease_names[0] if len(disease_names) == 1 else f"{disease_names[0]} 等{len(disease_names)}种"
        return {
            "type": "comorbidity",
            "disease_name": display_name,
            "matched_diseases": disease_names,
            "total_visits": total,
            "comorbidities": comorbidities,
        }

    def _retrieve_readmission_summary(self) -> dict:
        """检索再入院统计"""
        total_records = neo4j_client.run("MATCH (p:Patient) RETURN count(p) AS cnt")
        total_patients = total_records[0]["cnt"] if total_records else 0

        readmit_records = neo4j_client.run("""
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WITH p, count(v) AS vcount
            WHERE vcount >= 2
            RETURN count(p) AS cnt, avg(vcount) AS avg_visits
        """)
        readmit = readmit_records[0] if readmit_records else {}
        readmit_count = readmit.get("cnt", 0)
        avg_visits = round(readmit.get("avg_visits", 0) or 0, 1)

        # 再入院高发疾病
        disease_records = neo4j_client.run("""
            MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
            WITH p, count(v) AS vcount
            WHERE vcount >= 2
            MATCH (p)-[:HAS_VISIT]->(v2:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
            RETURN d.name AS name, count(DISTINCT p) AS patient_count
            ORDER BY patient_count DESC LIMIT 10
        """)
        top_diseases = [{"name": r["name"], "count": r["patient_count"]} for r in disease_records]

        return {
            "type": "readmission_summary",
            "total_patients": total_patients,
            "readmit_patients": readmit_count,
            "readmit_rate": round(readmit_count / total_patients * 100, 1) if total_patients else 0,
            "avg_visits_per_readmit": avg_visits,
            "top_diseases": top_diseases,
        }

    def _retrieve_global_stats(self) -> dict:
        """全局统计"""
        stats = {}
        try:
            for label in ["Patient", "Visit", "Disease", "Drug", "Exam", "Surgery"]:
                recs = neo4j_client.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
                stats[label.lower() + "s"] = recs[0]["cnt"] if recs else 0
        except Exception:
            pass

        # Top 10 疾病
        disease_records = neo4j_client.run("""
            MATCH (v:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
            RETURN d.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """)
        top_diseases = [{"name": r["name"], "count": r["cnt"]} for r in disease_records]

        # Top 10 药品
        drug_records = neo4j_client.run("""
            MATCH (v:Visit)-[:PRESCRIBED]->(dr:Drug)
            RETURN dr.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """)
        top_drugs = [{"name": r["name"], "count": r["cnt"]} for r in drug_records]

        return {
            "type": "global_stats",
            "stats": stats,
            "top_diseases": top_diseases,
            "top_drugs": top_drugs,
        }

    def _generate_answer(self, question: str, retrieved: dict) -> str:
        """基于检索结果调用LLM生成回答"""
        rtype = retrieved.get("type")

        if rtype == "patient_timeline":
            return self._answer_patient(question, retrieved)
        if rtype == "disease_pathway":
            return self._answer_disease(question, retrieved)
        if rtype == "drug_pattern":
            return self._answer_drug(question, retrieved)
        if rtype == "comorbidity":
            return self._answer_comorbidity(question, retrieved)
        if rtype == "readmission_summary":
            return self._answer_readmission(question, retrieved)

        return self._answer_general(question, retrieved)

    def _build_prompt(self, system: str, user: str, cache_namespace: str = "kg_rag:general") -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return llm_service.chat(messages, temperature=0.3, max_tokens=2000, cache_namespace=cache_namespace)

    def _answer_patient(self, question: str, retrieved: dict) -> str:
        visits = retrieved.get("visits", [])
        if not visits:
            return f"在知识图谱中未找到患者 {retrieved.get('patient_id')} 的就诊记录。"

        system = (
            "你是一位资深的医院数据分析师。请严格基于下方提供的患者真实就诊数据回答问题，"
            "不要编造任何数据。如果数据中没有答案，请明确说明'根据现有数据无法回答'。"
            "回答要简洁、专业，使用中文。"
        )

        # 构建时间线文本
        lines = [
            f"患者ID: {retrieved.get('patient_id')}",
            f"总就诊次数: {len(visits)}",
        ]
        for i, v in enumerate(visits, 1):
            lines.append(
                f"\n第{i}次就诊 (ID: {v['visit_id']}, 时间: {v['admission_date']} ~ {v['discharge_date']}, "
                f"住院{int(v['length_of_stay'] or 0)}天)"
            )
            if v.get("complaints"):
                lines.append(f"  主诉: {', '.join(v['complaints'])}")
            if v.get("diseases"):
                lines.append(f"  诊断: {', '.join(v['diseases'])}")
            if v.get("drugs"):
                drugs = v["drugs"][:15]
                lines.append(f"  用药: {', '.join(drugs)}{' 等' if len(v['drugs']) > 15 else ''}")
            if v.get("exams"):
                exams = v["exams"][:10]
                lines.append(f"  检查: {', '.join(exams)}{' 等' if len(v['exams']) > 10 else ''}")
            if v.get("surgeries"):
                lines.append(f"  手术: {', '.join(v['surgeries'])}")

        user = f"问题: {question}\n\n患者就诊数据:\n" + "\n".join(lines)
        return self._build_prompt(system, user, cache_namespace=f"kg_rag:patient:{retrieved.get('patient_id', 'unknown')}")

    def _answer_disease(self, question: str, retrieved: dict) -> str:
        system = (
            "你是一位资深的临床数据分析专家。请严格基于下方提供的疾病诊疗统计数据回答问题，"
            "所有百分比和数量必须来自提供的数据，不要编造。如果问题超出数据范围，请明确说明。"
            "回答简洁、专业，中文。"
        )

        lines = [
            f"疾病: {retrieved.get('disease_name')}",
            f"相关就诊次数: {retrieved.get('visit_count')}",
            f"平均住院天数: {retrieved.get('avg_los')}",
            f"中位住院天数: {retrieved.get('median_los')}",
        ]
        if retrieved.get("top_drugs"):
            lines.append("\n常用药品（按使用就诊次数排序）:")
            for d in retrieved["top_drugs"]:
                lines.append(f"  - {d['name']}: {d['count']}次")
        if retrieved.get("top_exams"):
            lines.append("\n常规检查:")
            for e in retrieved["top_exams"]:
                lines.append(f"  - {e['name']}: {e['count']}次")
        if retrieved.get("comorbidities"):
            lines.append("\n常见合并症:")
            for c in retrieved["comorbidities"]:
                lines.append(f"  - {c['name']}: {c['count']}次")

        user = f"问题: {question}\n\n诊疗统计数据:\n" + "\n".join(lines)
        return self._build_prompt(system, user, cache_namespace=f"kg_rag:disease:{retrieved.get('disease_name', 'unknown')}")

    def _answer_drug(self, question: str, retrieved: dict) -> str:
        system = (
            "你是一位资深药学分析师。请基于下方提供的用药统计数据回答问题，"
            "注意识别中西医结合用药特点，不要编造任何数据。中文回答。"
        )

        lines = [f"疾病: {retrieved.get('disease_name')}"]
        if retrieved.get("top_drugs"):
            lines.append("\n常用药品:")
            for d in retrieved["top_drugs"]:
                lines.append(f"  - {d['name']}: {d['count']}次就诊使用")
        if retrieved.get("common_pairs"):
            lines.append("\n常见药品组合:")
            for p in retrieved["common_pairs"]:
                lines.append(f"  - {p['drug1']} + {p['drug2']}: {p['count']}次")

        user = f"问题: {question}\n\n用药统计数据:\n" + "\n".join(lines)
        return self._build_prompt(system, user, cache_namespace=f"kg_rag:drug:{retrieved.get('drug_name', 'unknown')}")

    def _answer_comorbidity(self, question: str, retrieved: dict) -> str:
        system = (
            "你是一位资深临床数据分析专家。请基于下方合并症统计数据回答问题，"
            "所有百分比必须基于提供的数据计算，不要编造。中文回答。"
        )

        lines = [
            f"目标疾病: {retrieved.get('disease_name')}",
            f"该疾病总就诊次数: {retrieved.get('total_visits')}",
        ]
        if retrieved.get("comorbidities"):
            lines.append("\n常见合并症（按共现就诊次数排序）:")
            for c in retrieved["comorbidities"]:
                lines.append(
                    f"  - {c['name']}: {c['count']}次 ({c['percentage']}%), "
                    f"平均住院{c['avg_los']}天"
                )

        user = f"问题: {question}\n\n合并症统计数据:\n" + "\n".join(lines)
        return self._build_prompt(system, user, cache_namespace=f"kg_rag:comorbidity:{retrieved.get('target_disease', 'unknown')}")

    def _answer_readmission(self, question: str, retrieved: dict) -> str:
        system = (
            "你是一位医院质量管理专家。请基于下方再入院统计数据回答问题，"
            "不要编造。中文回答。"
        )

        lines = [
            f"总患者数: {retrieved.get('total_patients')}",
            f"再入院患者数（≥2次就诊）: {retrieved.get('readmit_patients')}",
            f"再入院率: {retrieved.get('readmit_rate')}%",
            f"再入院患者平均就诊次数: {retrieved.get('avg_visits_per_readmit')}",
        ]
        if retrieved.get("top_diseases"):
            lines.append("\n再入院患者中高发的疾病:")
            for d in retrieved["top_diseases"]:
                lines.append(f"  - {d['name']}: {d['count']}人")

        user = f"问题: {question}\n\n再入院统计数据:\n" + "\n".join(lines)
        return self._build_prompt(system, user, cache_namespace="kg_rag:readmission:summary")

    def _answer_general(self, question: str, retrieved: dict) -> str:
        system = (
            "你是一位医院数据分析师。请基于下方知识图谱全局统计信息回答问题，"
            "如果数据无法回答问题，请说明。中文回答。"
        )

        lines = ["知识图谱全局统计:"]
        for k, v in retrieved.get("stats", {}).items():
            lines.append(f"  - {k}: {v}")
        if retrieved.get("top_diseases"):
            lines.append("\nTop疾病:")
            for d in retrieved["top_diseases"]:
                lines.append(f"  - {d['name']}: {d['count']}次就诊")
        if retrieved.get("top_drugs"):
            lines.append("\nTop药品:")
            for d in retrieved["top_drugs"]:
                lines.append(f"  - {d['name']}: {d['count']}次就诊")

        user = f"问题: {question}\n\n" + "\n".join(lines)
        return self._build_prompt(system, user, cache_namespace="kg_rag:general")

    def _build_sources(self, retrieved: dict) -> list:
        """构建数据来源说明"""
        rtype = retrieved.get("type")
        if rtype == "patient_timeline":
            return [f"患者 {retrieved.get('patient_id')} 的就诊时间线（{retrieved.get('visit_count')}次就诊）"]
        if rtype == "disease_pathway":
            return [
                f"疾病 '{retrieved.get('disease_name')}' 的诊疗路径统计",
                f"基于 {retrieved.get('visit_count')} 次就诊记录",
            ]
        if rtype == "drug_pattern":
            return [f"疾病 '{retrieved.get('disease_name')}' 的用药模式统计"]
        if rtype == "comorbidity":
            return [f"疾病 '{retrieved.get('disease_name')}' 的合并症共现统计"]
        if rtype == "readmission_summary":
            return ["再入院患者全局统计分析"]
        return ["知识图谱全局统计"]


# 全局单例
kg_rag_service = KGRAGService()
