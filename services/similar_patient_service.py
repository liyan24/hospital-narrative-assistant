"""
相似患者推荐服务
基于知识图谱共同邻居算法计算患者相似度
"""
from typing import Optional

from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class SimilarPatientService:
    """相似患者推荐服务"""

    # 相似度权重配置
    WEIGHTS = {
        "disease": 0.35,
        "drug": 0.25,
        "exam": 0.20,
        "surgery": 0.15,
        "complaint": 0.05,
    }

    def find_similar_patients(self, patient_id: str, top_n: int = 10,
                               min_similarity: float = 0.05) -> dict:
        """
        基于图谱共同邻居算法寻找相似患者
        返回: 相似患者列表及相似原因
        """
        # 1. 获取目标患者的基本信息
        target_info = self._get_patient_profile(patient_id)
        if not target_info:
            return {"error": f"患者 {patient_id} 不存在"}

        # 2. 通过共同疾病快速筛选候选患者（提高性能）
        candidate_pids = self._get_candidates_by_disease(patient_id, max_candidates=200)
        if not candidate_pids:
            return {
                "patient_id": patient_id,
                "target_profile": target_info,
                "similar_patients": [],
                "narrative": "未找到具有足够相似度的患者。",
            }

        # 3. 计算相似度
        similarities = []
        for candidate_pid in candidate_pids:
            sim = self._calculate_similarity(patient_id, candidate_pid)
            if sim["score"] >= min_similarity:
                similarities.append(sim)

        # 4. 排序取TopN
        similarities.sort(key=lambda x: x["score"], reverse=True)
        top_similar = similarities[:top_n]

        # 5. 生成叙事
        narrative = self._generate_similarity_narrative(target_info, top_similar)

        return {
            "patient_id": patient_id,
            "target_profile": target_info,
            "similar_patients": top_similar,
            "narrative": narrative,
        }

    def _get_patient_profile(self, patient_id: str) -> Optional[dict]:
        """获取患者画像"""
        recs = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(d:Disease)
            OPTIONAL MATCH (v)-[:PRESCRIBED]->(dr:Drug)
            OPTIONAL MATCH (v)-[:PERFORMED_EXAM]->(e:Exam)
            OPTIONAL MATCH (v)-[:UNDERWENT]->(s:Surgery)
            OPTIONAL MATCH (v)-[:CHIEF_COMPLAINT]->(c:ChiefComplaint)
            RETURN p.age AS age,
                   count(DISTINCT v) AS visit_count,
                   collect(DISTINCT d.name) AS diseases,
                   collect(DISTINCT dr.name) AS drugs,
                   collect(DISTINCT e.name) AS exams,
                   collect(DISTINCT s.name) AS surgeries,
                   collect(DISTINCT c.name) AS complaints,
                   min(v.admission_date) AS first_visit,
                   max(v.admission_date) AS last_visit
        """, {"pid": patient_id})

        if not recs:
            return None

        r = dict(recs[0])
        return {
            "patient_id": patient_id,
            "age": r.get("age"),
            "visit_count": r.get("visit_count", 0),
            "diseases": list(set(r.get("diseases", []) or [])),
            "drugs": list(set(r.get("drugs", []) or [])),
            "exams": list(set(r.get("exams", []) or [])),
            "surgeries": list(set(r.get("surgeries", []) or [])),
            "complaints": list(set(r.get("complaints", []) or [])),
            "first_visit": r.get("first_visit"),
            "last_visit": r.get("last_visit"),
        }

    def _get_candidates_by_disease(self, patient_id: str, max_candidates: int = 200) -> list:
        """通过共同疾病筛选候选患者"""
        recs = neo4j_client.run("""
            MATCH (p1:Patient {patient_id: $pid})-[:HAS_VISIT]->(v1:Visit)
                  -[:DIAGNOSED_WITH]->(d:Disease)<-[:DIAGNOSED_WITH]-(v2:Visit)
                  <-[:HAS_VISIT]-(p2:Patient)
            WHERE p1 <> p2
            WITH p2, count(DISTINCT d) AS common_disease_count
            ORDER BY common_disease_count DESC
            RETURN p2.patient_id AS pid
            LIMIT $limit
        """, {"pid": patient_id, "limit": max_candidates})

        return [r["pid"] for r in recs if r["pid"]]

    def _get_patient_entities(self, patient_id: str) -> dict:
        """获取患者的所有实体（分别查询，避免复杂Cypher）"""
        entities = {"diseases": set(), "drugs": set(), "exams": set(), "surgeries": set(), "complaints": set(), "visit_count": 0}

        # 疾病
        recs = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
            RETURN collect(DISTINCT d.name) AS items, count(DISTINCT v) AS vcount
        """, {"pid": patient_id})
        if recs:
            entities["diseases"] = set(recs[0]["items"] or [])
            entities["visit_count"] = recs[0]["vcount"]

        # 药品
        recs = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)-[:PRESCRIBED]->(dr:Drug)
            RETURN collect(DISTINCT dr.name) AS items
        """, {"pid": patient_id})
        if recs:
            entities["drugs"] = set(recs[0]["items"] or [])

        # 检查
        recs = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)-[:PERFORMED_EXAM]->(e:Exam)
            RETURN collect(DISTINCT e.name) AS items
        """, {"pid": patient_id})
        if recs:
            entities["exams"] = set(recs[0]["items"] or [])

        # 手术
        recs = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)-[:UNDERWENT]->(s:Surgery)
            RETURN collect(DISTINCT s.name) AS items
        """, {"pid": patient_id})
        if recs:
            entities["surgeries"] = set(recs[0]["items"] or [])

        # 主诉
        recs = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)-[:CHIEF_COMPLAINT]->(c:ChiefComplaint)
            RETURN collect(DISTINCT c.name) AS items
        """, {"pid": patient_id})
        if recs:
            entities["complaints"] = set(recs[0]["items"] or [])

        return entities

    def _calculate_similarity(self, pid1: str, pid2: str) -> dict:
        """计算两个患者之间的加权Jaccard相似度"""
        e1 = self._get_patient_entities(pid1)
        e2 = self._get_patient_entities(pid2)

        def jaccard(a: set, b: set) -> float:
            union = a | b
            if not union:
                return 0.0
            return len(a & b) / len(union)

        disease_sim = jaccard(e1["diseases"], e2["diseases"])
        drug_sim = jaccard(e1["drugs"], e2["drugs"])
        exam_sim = jaccard(e1["exams"], e2["exams"])
        surgery_sim = jaccard(e1["surgeries"], e2["surgeries"])
        complaint_sim = jaccard(e1["complaints"], e2["complaints"])

        score = (
            disease_sim * self.WEIGHTS["disease"] +
            drug_sim * self.WEIGHTS["drug"] +
            exam_sim * self.WEIGHTS["exam"] +
            surgery_sim * self.WEIGHTS["surgery"] +
            complaint_sim * self.WEIGHTS["complaint"]
        )

        common_diseases = list(e1["diseases"] & e2["diseases"])
        common_drugs = list(e1["drugs"] & e2["drugs"])
        common_exams = list(e1["exams"] & e2["exams"])

        return {
            "patient_id": pid2,
            "score": round(score, 3),
            "visit_count": e2["visit_count"],
            "details": {
                "disease_similarity": round(disease_sim, 3),
                "drug_similarity": round(drug_sim, 3),
                "exam_similarity": round(exam_sim, 3),
                "surgery_similarity": round(surgery_sim, 3),
                "complaint_similarity": round(complaint_sim, 3),
            },
            "common_diseases": common_diseases[:10],
            "common_drugs": common_drugs[:10],
            "common_exams": common_exams[:10],
        }

    def _generate_similarity_narrative(self, target: dict, similar_patients: list) -> str:
        """生成相似患者推荐叙事"""
        if not similar_patients:
            return f"在知识图谱中未找到与患者 {target['patient_id']} 具有足够相似度的其他患者。"

        system = (
            "你是一位资深临床医生。请基于下方的患者相似度分析数据，为患者推荐最相似的参考病例，"
            "并解释相似原因和可借鉴的诊疗经验。注意：推荐仅供参考，不能替代临床判断。"
            "中文输出，专业简洁。"
        )

        lines = [
            f"目标患者: {target['patient_id']}",
            f"年龄: {target.get('age', '未知')}岁",
            f"就诊次数: {target.get('visit_count', 0)}",
            f"主要诊断: {', '.join(target.get('diseases', [])[:8])}",
            f"主要用药: {', '.join(target.get('drugs', [])[:8])}",
            "",
            "=== 相似患者推荐 ===",
        ]

        for i, sim in enumerate(similar_patients[:5], 1):
            lines.append(f"\nTop {i}: 患者 {sim['patient_id']} (相似度: {sim['score']})")
            lines.append(f"  就诊次数: {sim.get('visit_count', 0)}")
            lines.append(f"  疾病相似度: {sim['details']['disease_similarity']}")
            lines.append(f"  用药相似度: {sim['details']['drug_similarity']}")
            if sim.get("common_diseases"):
                lines.append(f"  共同诊断: {', '.join(sim['common_diseases'][:5])}")
            if sim.get("common_drugs"):
                lines.append(f"  共同用药: {', '.join(sim['common_drugs'][:5])}")

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(lines)},
        ]
        ns = f"similar_patient:{target.get('patient_id', 'unknown')}"
        return llm_service.chat(messages, temperature=0.4, max_tokens=2000, cache_namespace=ns)


# 全局单例
similar_patient_service = SimilarPatientService()
