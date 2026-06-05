"""
个体患者故事线生成服务
基于知识图谱中的患者-就诊-诊断-用药-检查-手术链条，生成个体化叙事
"""

from typing import Dict, List, Optional
from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class PatientNarrativeService:
    def __init__(self):
        self.llm = llm_service

    def get_patient_timeline(self, patient_id: str) -> Optional[Dict]:
        """
        从Neo4j查询患者的完整就诊时间线
        返回: {
            patient: {patient_id, medical_record_no, age, marital_status, ...},
            visits: [
                {
                    visit_id, admission_date, discharge_date, length_of_stay, chief_complaint,
                    diseases: [{name, display_name, type, diagnosis_type, is_main}],
                    drugs: [{name, dosage, frequency, route}],
                    exams: [{name, category, exam_date}],
                    labs: [{name, value, unit, abnormal_flag}],
                    surgeries: [{name, category, anesthesia_method}],
                    departments: [name]
                }
            ]
        }
        """
        # 查询患者基本信息和所有Visit
        cql_patient = """
        MATCH (p:Patient {patient_id: $patient_id})
        OPTIONAL MATCH (p)-[:HAS_VISIT]->(v:Visit)
        RETURN p, collect(v) AS visits
        """
        records = neo4j_client.run(cql_patient, {"patient_id": patient_id})
        if not records:
            return None

        patient_node = records[0]["p"]
        visit_nodes = records[0]["visits"]

        patient = {
            "patient_id": patient_node.get("patient_id"),
            "medical_record_no": patient_node.get("medical_record_no"),
            "age": patient_node.get("age"),
            "marital_status": patient_node.get("marital_status"),
            "occupation": patient_node.get("occupation"),
            "allergy_history": patient_node.get("allergy_history"),
        }

        visits = []
        for v_node in sorted(visit_nodes, key=lambda x: x.get("admission_date") or ""):
            visit_id = v_node.get("visit_id")
            visit_data = {
                "visit_id": visit_id,
                "admission_date": v_node.get("admission_date"),
                "discharge_date": v_node.get("discharge_date"),
                "length_of_stay": v_node.get("length_of_stay"),
                "chief_complaint": v_node.get("chief_complaint"),
                "diseases": [],
                "drugs": [],
                "exams": [],
                "labs": [],
                "surgeries": [],
                "departments": [],
            }

            # 查询该Visit的关联实体
            cql_details = """
            MATCH (v:Visit {visit_id: $visit_id})
            OPTIONAL MATCH (v)-[rd:DIAGNOSED_WITH]->(d:Disease)
            OPTIONAL MATCH (v)-[rp:PRESCRIBED]->(dr:Drug)
            OPTIONAL MATCH (v)-[re:PERFORMED_EXAM]->(e:Exam)
            OPTIONAL MATCH (v)-[rl:HAS_LAB_RESULT]->(l:LabItem)
            OPTIONAL MATCH (v)-[ru:UNDERWENT]->(s:Surgery)
            OPTIONAL MATCH (v)-[rdept:IN_DEPARTMENT]->(dept:Department)
            RETURN
                collect(DISTINCT {name: d.name, display_name: d.display_name, type: d.type,
                                  diagnosis_type: rd.diagnosis_type, is_main: rd.is_main}) AS diseases,
                collect(DISTINCT {name: dr.name, dosage: rp.dosage, frequency: rp.frequency,
                                  route: rp.route, start_date: rp.start_date}) AS drugs,
                collect(DISTINCT {name: e.name, category: e.category, exam_date: re.exam_date,
                                  description: re.description, diagnosis: re.diagnosis}) AS exams,
                collect(DISTINCT {name: l.name, value: rl.value, unit: rl.unit,
                                  abnormal_flag: rl.abnormal_flag, hint: rl.hint}) AS labs,
                collect(DISTINCT {name: s.name, category: s.category, anesthesia_method: s.anesthesia_method,
                                  start_date: ru.start_date}) AS surgeries,
                collect(DISTINCT dept.name) AS departments
            """
            detail_records = neo4j_client.run(cql_details, {"visit_id": visit_id})
            if detail_records:
                d = detail_records[0]
                visit_data["diseases"] = [x for x in d["diseases"] if x.get("name")]
                visit_data["drugs"] = [x for x in d["drugs"] if x.get("name")]
                visit_data["exams"] = [x for x in d["exams"] if x.get("name")]
                visit_data["labs"] = [x for x in d["labs"] if x.get("name")]
                visit_data["surgeries"] = [x for x in d["surgeries"] if x.get("name")]
                visit_data["departments"] = [x for x in d["departments"] if x]

            visits.append(visit_data)

        return {"patient": patient, "visits": visits}

    def generate_narrative(self, patient_id: str) -> Dict:
        """生成个体患者故事线叙事"""
        timeline = self.get_patient_timeline(patient_id)
        if timeline is None:
            return {"error": "患者不存在或无任何就诊记录"}

        patient = timeline["patient"]
        visits = timeline["visits"]

        if not visits:
            return {"error": "患者无任何就诊记录"}

        # 构建结构化上下文
        context = self._build_context(patient, visits)

        # 调用LLM生成叙事
        prompt = self._build_prompt(context)
        narrative = self.llm.chat(
            [
                {"role": "system", "content": "你是一位资深临床医生，擅长撰写专业的患者就诊记录摘要。请基于提供的结构化数据，用中文生成一段连贯、专业、有温度的患者故事线叙事。要体现诊疗过程的完整性和时间线，适当提及关键诊断、用药、检查和手术。语气专业但不冰冷，适合科室汇报或病例讨论使用。直接输出叙事文本，不要加标题。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return {
            "patient_id": patient_id,
            "patient": patient,
            "visit_count": len(visits),
            "narrative": narrative,
            "timeline": timeline,
        }

    def _build_context(self, patient: Dict, visits: List[Dict]) -> str:
        """将患者时间线数据格式化为文本上下文"""
        lines = []
        lines.append(f"患者基本信息：")
        lines.append(f"  病案号：{patient.get('medical_record_no', '未知')}")
        lines.append(f"  年龄：{patient.get('age', '未知')}岁")
        lines.append(f"  婚姻：{patient.get('marital_status', '未知')}")
        lines.append(f"  职业：{patient.get('occupation', '未知')}")
        if patient.get('allergy_history'):
            lines.append(f"  过敏史：{patient['allergy_history']}")

        lines.append(f"\n该患者共有 {len(visits)} 次就诊记录：\n")

        for i, v in enumerate(visits, 1):
            lines.append(f"--- 第{i}次就诊 ({v.get('admission_date', '日期未知')}) ---")
            lines.append(f"  住院天数：{v.get('length_of_stay', '未知')}天")

            if v.get("chief_complaint"):
                lines.append(f"  主诉：{v['chief_complaint']}")

            if v.get("departments"):
                lines.append(f"  科室：{', '.join(v['departments'])}")

            # 诊断
            main_diag = [d for d in v["diseases"] if d.get("is_main")]
            other_diag = [d for d in v["diseases"] if not d.get("is_main")]
            if main_diag:
                lines.append(f"  主要诊断：{', '.join([d['display_name'] for d in main_diag])}")
            if other_diag:
                names = [d['display_name'] for d in other_diag[:5]]
                lines.append(f"  其他诊断：{', '.join(names)}")

            # 手术
            if v.get("surgeries"):
                s_names = [s["name"] for s in v["surgeries"]]
                lines.append(f"  手术：{', '.join(s_names)}")

            # 用药（Top 10）
            if v.get("drugs"):
                drug_names = []
                for d in v["drugs"][:10]:
                    name = d["name"]
                    if d.get("frequency"):
                        name += f"({d['frequency']})"
                    drug_names.append(name)
                lines.append(f"  用药：{', '.join(drug_names)}")

            # 检查
            if v.get("exams"):
                exam_names = [e["name"] for e in v["exams"][:5]]
                lines.append(f"  检查：{', '.join(exam_names)}")

            # 检验异常
            abnormal_labs = [l for l in v.get("labs", []) if l.get("abnormal_flag")]
            if abnormal_labs:
                lab_names = [l["name"] for l in abnormal_labs[:5]]
                lines.append(f"  异常检验：{', '.join(lab_names)}")

            lines.append("")

        return "\n".join(lines)

    def _build_prompt(self, context: str) -> str:
        return f"""请根据以下患者的结构化就诊数据，撰写一段完整的患者故事线叙事。

要求：
1. 以第三人称、时间顺序叙述该患者的就诊历程
2. 包含每次入院的主诉、诊断、治疗（用药/手术）、检查检验等关键信息
3. 如果患者有多次就诊，要体现出病情的发展或治疗的延续性
4. 对中医诊断和证型可适当提及
5. 字数控制在800字以内
6. 结尾可简要总结该患者的诊疗特点或值得关注的地方

数据：
{context}
"""


# 全局单例
patient_narrative_service = PatientNarrativeService()
