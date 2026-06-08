"""
用药模式与合理性叙事服务
基于知识图谱分析药品共现网络、常用药组合、潜在问题
"""

from typing import Dict, List, Optional
from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class DrugPatternService:
    def __init__(self):
        self.llm = llm_service

    def get_drug_pattern_data(self, disease_name: Optional[str] = None) -> Optional[Dict]:
        """
        查询用药模式数据
        如果指定disease_name，分析该疾病下的用药模式
        否则分析全局用药模式
        """
        if disease_name:
            return self._get_disease_drug_pattern(disease_name)
        else:
            return self._get_global_drug_pattern()

    def _get_disease_drug_pattern(self, disease_name: str) -> Optional[Dict]:
        """某疾病下的用药模式分析"""
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
                      "pct": round(r["cnt"] / total_visits * 100, 1)} for r in drug_records]

        # 药品组合对
        cql_pairs = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(d1:Drug)
        MATCH (v)-[:PRESCRIBED]->(d2:Drug)
        WHERE d1 <> d2 AND d1.name < d2.name
        RETURN d1.name AS name1, d2.name AS name2, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 15
        """
        pair_records = neo4j_client.run(cql_pairs, {"disease_name": disease_name})
        pairs = [{"drug_a": r["name1"], "drug_b": r["name2"],
                  "count": r["cnt"],
                  "pct": round(r["cnt"] / total_visits * 100, 1)} for r in pair_records]

        # 中药/中成药使用情况
        cql_tcm_drugs = """
        MATCH (d:Disease)
        WHERE d.display_name = $disease_name OR d.name STARTS WITH $disease_name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
        WHERE dr.name CONTAINS '胶囊' OR dr.name CONTAINS '颗粒' OR dr.name CONTAINS '丸'
           OR dr.name CONTAINS '口服液' OR dr.name CONTAINS '注射液' AND (
               dr.name CONTAINS '华蟾素' OR dr.name CONTAINS '斑蝥' OR dr.name CONTAINS '康莱特'
               OR dr.name CONTAINS '艾迪' OR dr.name CONTAINS '参芪' OR dr.name CONTAINS '复方'
           )
        RETURN dr.name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 10
        """
        tcm_records = neo4j_client.run(cql_tcm_drugs, {"disease_name": disease_name})
        tcm_drugs = [{"name": r["name"], "count": r["cnt"],
                      "pct": round(r["cnt"] / total_visits * 100, 1)} for r in tcm_records]

        return {
            "disease_name": disease_name,
            "total_visits": total_visits,
            "top_drugs": top_drugs,
            "pairs": pairs,
            "tcm_drugs": tcm_drugs,
            "mode": "single",
        }

    def _get_global_drug_pattern(self) -> Dict:
        """全局用药模式分析"""
        # Top药品
        cql_drugs = """
        MATCH (v:Visit)-[:PRESCRIBED]->(dr:Drug)
        RETURN dr.name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 20
        """
        drug_records = neo4j_client.run(cql_drugs)
        total_visits = 0
        if drug_records:
            # 查询总就诊数
            total_r = neo4j_client.run("MATCH (v:Visit) RETURN count(v) AS cnt")
            total_visits = total_r[0]["cnt"] if total_r else 0

        top_drugs = [{"name": r["name"], "count": r["cnt"],
                      "pct": round(r["cnt"] / total_visits * 100, 1) if total_visits else 0}
                     for r in drug_records]

        # 全局药品组合对
        cql_pairs = """
        MATCH (v:Visit)-[:PRESCRIBED]->(d1:Drug)
        MATCH (v)-[:PRESCRIBED]->(d2:Drug)
        WHERE d1 <> d2 AND d1.name < d2.name
        RETURN d1.name AS name1, d2.name AS name2, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 20
        """
        pair_records = neo4j_client.run(cql_pairs)
        pairs = [{"drug_a": r["name1"], "drug_b": r["name2"], "count": r["cnt"]} for r in pair_records]

        return {
            "disease_name": None,
            "total_visits": total_visits,
            "top_drugs": top_drugs,
            "pairs": pairs,
            "tcm_drugs": [],
            "mode": "global",
        }

    def generate_narrative(self, disease_name: Optional[str] = None) -> Dict:
        """生成用药模式叙事"""
        data = self.get_drug_pattern_data(disease_name)
        if data is None:
            return {"error": f"未找到疾病 '{disease_name}' 的用药数据"}

        context = self._build_context(data)
        prompt = self._build_prompt(context)

        ns = f"drug_pattern:{disease_name}" if disease_name else "drug_pattern:global"
        narrative = self.llm.chat(
            [
                {"role": "system", "content": "你是一位资深临床药师兼肿瘤科专家，擅长分析科室用药模式和合理性。请基于提供的统计数据，用中文撰写一段用药模式分析叙事。要体现出常用药组合的规律性、中西医结合特点、以及潜在的用药问题（如重复用药、相互作用风险等）。语气专业、数据驱动，适合科室药事管理汇报使用。直接输出叙事文本，不要加标题。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            cache_namespace=ns,
        )

        return {
            "disease_name": disease_name,
            "narrative": narrative,
            "data": data,
        }

    def _build_context(self, data: Dict) -> str:
        lines = []

        if data["mode"] == "single":
            lines.append(f"目标疾病：{data['disease_name']}")
            lines.append(f"相关就诊人次：{data['total_visits']}")
            lines.append("")

            if data.get("top_drugs"):
                lines.append("最常用药品（Top 15）：")
                for d in data["top_drugs"][:15]:
                    lines.append(f"  - {d['name']}: {d['count']}例 ({d['pct']}%)")

            if data.get("pairs"):
                lines.append("")
                lines.append("常见药品组合对（Top 10）：")
                for p in data["pairs"][:10]:
                    lines.append(f"  - {p['drug_a']} + {p['drug_b']}: {p['count']}例 ({p['pct']}%)")

            if data.get("tcm_drugs"):
                lines.append("")
                lines.append("常用中成药/中药制剂：")
                for t in data["tcm_drugs"][:10]:
                    lines.append(f"  - {t['name']}: {t['count']}例 ({t['pct']}%)")

        else:
            lines.append("全局用药模式分析")
            lines.append(f"总就诊人次：{data['total_visits']}")
            lines.append("")
            lines.append("最常用药品（Top 15）：")
            for d in data["top_drugs"][:15]:
                lines.append(f"  - {d['name']}: {d['count']}例 ({d['pct']}%)")
            lines.append("")
            lines.append("常见药品组合对（Top 10）：")
            for p in data["pairs"][:10]:
                lines.append(f"  - {p['drug_a']} + {p['drug_b']}: {p['count']}例")

        return "\n".join(lines)

    def _build_prompt(self, context: str) -> str:
        return f"""请根据以下用药统计数据，撰写一段用药模式与合理性分析叙事。

要求：
1. 总结该疾病/科室最常用的药品组合及其临床意义
2. 分析是否存在固定的"基础方案"或"标准组合"
3. 如果数据中有中成药，分析中西医结合用药的特点
4. 指出可能存在的用药问题（如：重复用药风险、支持治疗药物占比过高、昂贵药物使用频率等）
5. 对药事管理提出1-2条建议
6. 字数控制在800字以内

数据：
{context}
"""


# 全局单例
drug_pattern_service = DrugPatternService()
