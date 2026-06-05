"""
疾病共现网络叙事服务
基于知识图谱分析合并症组合，生成疾病共现网络叙事
"""

from typing import Dict, List, Optional
from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class ComorbidityService:
    def __init__(self):
        self.llm = llm_service

    def get_comorbidity_data(self, target_disease: Optional[str] = None) -> Optional[Dict]:
        """
        查询疾病共现数据
        如果指定target_disease，则分析该疾病的合并症
        如果不指定，则分析全局Top合并症对
        """
        if target_disease:
            return self._get_single_disease_comorbidity(target_disease)
        else:
            return self._get_global_comorbidity()

    def _get_single_disease_comorbidity(self, disease_name: str) -> Optional[Dict]:
        """查询某特定疾病的合并症分布"""
        # 该疾病的就诊人次
        cql_base = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)
        RETURN count(DISTINCT v) AS total_visits
        """
        base_records = neo4j_client.run(cql_base, {"disease_name": disease_name})
        if not base_records or base_records[0]["total_visits"] == 0:
            return None

        total_visits = base_records[0]["total_visits"]

        # 合并症统计
        cql_comorb = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(d2:Disease)
        WHERE d2 <> d
        RETURN d2.display_name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 20
        """
        comorb_records = neo4j_client.run(cql_comorb, {"disease_name": disease_name})
        comorbidities = [{"name": r["name"], "count": r["cnt"],
                          "pct": round(r["cnt"] / total_visits * 100, 1)} for r in comorb_records]

        # 中医证型分布（如果有）
        cql_tcm = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(d2:Disease)
        WHERE d2.type = 'tcm_syndrome'
        RETURN d2.display_name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 10
        """
        tcm_records = neo4j_client.run(cql_tcm, {"disease_name": disease_name})
        tcm_syndromes = [{"name": r["name"], "count": r["cnt"],
                          "pct": round(r["cnt"] / total_visits * 100, 1)} for r in tcm_records]

        # 合并症组合（三元组）
        cql_triples = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(d2:Disease)
        WHERE d2 <> d AND d2.type <> 'tcm_syndrome'
        MATCH (v)-[:DIAGNOSED_WITH]->(d3:Disease)
        WHERE d3 <> d AND d3 <> d2 AND d3.type <> 'tcm_syndrome'
        WITH d2.display_name AS name1, d3.display_name AS name2, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC
        WHERE name1 < name2
        RETURN name1, name2, cnt
        LIMIT 15
        """
        triple_records = neo4j_client.run(cql_triples, {"disease_name": disease_name})
        triples = [{"disease_a": r["name1"], "disease_b": r["name2"],
                    "count": r["cnt"],
                    "pct": round(r["cnt"] / total_visits * 100, 1)} for r in triple_records]

        return {
            "target_disease": disease_name,
            "total_visits": total_visits,
            "comorbidities": comorbidities,
            "tcm_syndromes": tcm_syndromes,
            "triples": triples,
            "mode": "single",
        }

    def _get_global_comorbidity(self) -> Dict:
        """全局Top合并症对分析"""
        cql_pairs = """
        MATCH (v:Visit)-[:DIAGNOSED_WITH]->(d1:Disease),
              (v)-[:DIAGNOSED_WITH]->(d2:Disease)
        WHERE d1 <> d2 AND d1.type = 'western' AND d2.type = 'western'
        WITH d1.display_name AS name1, d2.display_name AS name2, count(DISTINCT v) AS cnt
        WHERE name1 < name2 AND cnt >= 5
        RETURN name1, name2, cnt
        ORDER BY cnt DESC LIMIT 20
        """
        pair_records = neo4j_client.run(cql_pairs)
        pairs = [{"disease_a": r["name1"], "disease_b": r["name2"], "count": r["cnt"]} for r in pair_records]

        # 统计涉及合并症的就诊比例
        cql_ratio = """
        MATCH (v:Visit)
        WITH count(v) AS total
        MATCH (v)-[:DIAGNOSED_WITH]->(d1:Disease),
              (v)-[:DIAGNOSED_WITH]->(d2:Disease)
        WHERE d1 <> d2
        RETURN total, count(DISTINCT v) AS multi_diag_visits
        """
        ratio_records = neo4j_client.run(cql_ratio)
        ratio = ratio_records[0] if ratio_records else {}

        return {
            "target_disease": None,
            "total_visits": ratio.get("total", 0),
            "multi_diag_visits": ratio.get("multi_diag_visits", 0),
            "pairs": pairs,
            "mode": "global",
        }

    def generate_narrative(self, target_disease: Optional[str] = None) -> Dict:
        """生成疾病共现网络叙事"""
        data = self.get_comorbidity_data(target_disease)
        if data is None:
            return {"error": f"未找到疾病 '{target_disease}' 的共现数据"}

        context = self._build_context(data)
        prompt = self._build_prompt(context)

        narrative = self.llm.chat(
            [
                {"role": "system", "content": "你是一位资深临床流行病学家，擅长分析疾病共现模式和合并症网络。请基于提供的统计数据，用中文撰写一段专业的疾病共现网络分析叙事。要体现出合并症的临床意义、不同疾病之间的关联强度、以及对诊疗决策的影响。语气专业、数据驱动，适合科室学术汇报使用。直接输出叙事文本，不要加标题。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return {
            "target_disease": target_disease,
            "narrative": narrative,
            "data": data,
        }

    def _build_context(self, data: Dict) -> str:
        lines = []

        if data["mode"] == "single":
            lines.append(f"目标疾病：{data['target_disease']}")
            lines.append(f"相关就诊人次：{data['total_visits']}")
            lines.append("")

            if data.get("comorbidities"):
                lines.append("最常见合并症（Top 15）：")
                for c in data["comorbidities"][:15]:
                    lines.append(f"  - {c['name']}: {c['count']}例 ({c['pct']}%)")

            if data.get("tcm_syndromes"):
                lines.append("")
                lines.append("常见中医证型：")
                for t in data["tcm_syndromes"][:10]:
                    lines.append(f"  - {t['name']}: {t['count']}例 ({t['pct']}%)")

            if data.get("triples"):
                lines.append("")
                lines.append("常见合并症三元组（同时存在三种疾病）：")
                for t in data["triples"][:10]:
                    lines.append(f"  - {data['target_disease']} + {t['disease_a']} + {t['disease_b']}: {t['count']}例 ({t['pct']}%)")

        else:
            lines.append("全局疾病共现分析")
            lines.append(f"总就诊人次：{data['total_visits']}")
            lines.append(f"存在多种诊断的就诊人次：{data['multi_diag_visits']}")
            lines.append("")
            lines.append("最常见合并症对（Top 20）：")
            for p in data["pairs"][:20]:
                lines.append(f"  - {p['disease_a']} + {p['disease_b']}: {p['count']}例")

        return "\n".join(lines)

    def _build_prompt(self, context: str) -> str:
        return f"""请根据以下疾病共现统计数据，撰写一段疾病共现网络分析叙事。

要求：
1. 分析目标疾病与合并症之间的关联强度和临床意义
2. 如果数据中包含中医证型，分析证型分布与西医诊断的对应关系
3. 指出值得关注的合并症组合（尤其是高发生率的三元组）
4. 讨论这些合并症对诊疗方案选择的潜在影响
5. 字数控制在800字以内

数据：
{context}
"""


# 全局单例
comorbidity_service = ComorbidityService()
