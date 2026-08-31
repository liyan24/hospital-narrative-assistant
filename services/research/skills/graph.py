"""图谱挖掘类算子：图谱概览、疾病共现、中心性排行。Neo4j 不可用时返回提示结果。"""
from database.neo4j_client import neo4j_client
from services.research.skills.base import (
    BaseSkill, SkillMeta, make_result, bar_option, horizontal_bar_option,
)

GRAPH_UNAVAILABLE = (
    "知识图谱不可用：Neo4j 连接失败。图谱类算子依赖 Neo4j 服务，"
    "请确认 Neo4j 已启动且连接配置正确后重试；在此之前可先使用基于 Excel 的挖掘算子。"
)


def _graph_available() -> bool:
    try:
        return neo4j_client.test_connection()
    except Exception:
        return False


class GraphOverviewSkill(BaseSkill):
    meta = SkillMeta(
        id="graph_overview",
        name="知识图谱概览",
        category="图谱挖掘",
        description="节点/关系计数统计，了解图谱规模",
        params_schema=[],
        data_requirements="Neo4j 知识图谱",
    )

    def run(self, params: dict) -> dict:
        if not _graph_available():
            return make_result(GRAPH_UNAVAILABLE, facts={"graph_available": False})

        node_records = neo4j_client.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC")
        rel_records = neo4j_client.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC")

        node_stats = {r["label"]: r["count"] for r in node_records}
        rel_stats = {r["type"]: r["count"] for r in rel_records}

        tables = [
            {"title": "节点统计", "columns": ["节点类型", "数量"],
             "rows": [[k, v] for k, v in node_stats.items()]},
            {"title": "关系统计", "columns": ["关系类型", "数量"],
             "rows": [[k, v] for k, v in rel_stats.items()]},
        ]
        charts = [
            {"title": "节点分布", "option": bar_option("图谱节点计数",
             list(node_stats.keys()), list(node_stats.values()), "", "数量")},
            {"title": "关系分布", "option": horizontal_bar_option("图谱关系计数",
             list(rel_stats.keys())[::-1], list(rel_stats.values())[::-1], "数量")},
        ]

        summary = (
            f"知识图谱共 {sum(node_stats.values())} 个节点（{len(node_stats)} 类）、"
            f"{sum(rel_stats.values())} 条关系（{len(rel_stats)} 类）；"
            f"节点以 {max(node_stats, key=node_stats.get)} 最多，"
            f"关系以 {max(rel_stats, key=rel_stats.get)} 最多。"
        )
        facts = {"graph_available": True, "node_stats": node_stats, "rel_stats": rel_stats}
        return make_result(summary, tables, charts, facts)


class KGComorbiditySkill(BaseSkill):
    meta = SkillMeta(
        id="kg_comorbidity",
        name="图谱疾病共现分析",
        category="图谱挖掘",
        description="基于 Cypher 查询同一就诊下疾病共现对 Top N",
        params_schema=[
            {"name": "top_n", "label": "输出对数", "type": "number",
             "default": 20, "min": 5, "max": 100},
        ],
        data_requirements="Neo4j 知识图谱（Visit-DIAGNOSED_WITH-Disease）",
    )

    def run(self, params: dict) -> dict:
        if not _graph_available():
            return make_result(GRAPH_UNAVAILABLE, facts={"graph_available": False})

        top_n = int(self.get_param(params, "top_n"))
        records = neo4j_client.run(
            """
            MATCH (v:Visit)-[:DIAGNOSED_WITH]->(d1:Disease)
            MATCH (v)-[:DIAGNOSED_WITH]->(d2:Disease)
            WHERE elementId(d1) < elementId(d2)
            RETURN d1.name AS disease1, d2.name AS disease2, count(DISTINCT v) AS co_count
            ORDER BY co_count DESC
            LIMIT $top_n
            """,
            {"top_n": top_n},
        )
        if not records:
            return make_result("图谱中未查询到疾病共现记录，可能图谱未导入诊断关系。")

        rows = [[r["disease1"], r["disease2"], r["co_count"]] for r in records]
        tables = [{
            "title": f"疾病共现对 Top{len(rows)}",
            "columns": ["疾病A", "疾病B", "共现就诊数"],
            "rows": rows,
        }]
        charts = [{"title": "疾病共现对", "option": bar_option(
            f"图谱疾病共现对 Top{len(rows)}",
            [f"{r[0]}+{r[1]}" for r in rows], [r[2] for r in rows], "", "共现就诊数")}]

        best = records[0]
        summary = (
            f"图谱中共现最强的疾病对为「{best['disease1']} — {best['disease2']}」，"
            f"共同出现在 {best['co_count']} 次就诊中。共列出 Top{len(rows)} 对高频合并症组合。"
        )
        facts = {
            "graph_available": True,
            "top_pairs": [{"disease1": r["disease1"], "disease2": r["disease2"],
                           "co_count": r["co_count"]} for r in records[:10]],
        }
        return make_result(summary, tables, charts, facts)


class CentralitySkill(BaseSkill):
    meta = SkillMeta(
        id="centrality",
        name="图谱中心性排行",
        category="图谱挖掘",
        description="度中心性 Top20 节点排行（识别图谱中最核心的实体）",
        params_schema=[
            {"name": "top_n", "label": "输出数量", "type": "number",
             "default": 20, "min": 5, "max": 100},
        ],
        data_requirements="Neo4j 知识图谱",
    )

    def run(self, params: dict) -> dict:
        if not _graph_available():
            return make_result(GRAPH_UNAVAILABLE, facts={"graph_available": False})

        top_n = int(self.get_param(params, "top_n"))
        records = neo4j_client.run(
            """
            MATCH (n)-[r]-()
            RETURN labels(n)[0] AS label,
                   coalesce(n.name, n.patient_id, n.visit_no, n.id, elementId(n)) AS name,
                   count(r) AS degree
            ORDER BY degree DESC
            LIMIT $top_n
            """,
            {"top_n": top_n},
        )
        if not records:
            return make_result("图谱中未查询到任何关系，无法计算中心性。")

        rows = [[i + 1, str(r["name"]), r["label"], r["degree"]] for i, r in enumerate(records)]
        tables = [{
            "title": f"度中心性 Top{len(rows)}",
            "columns": ["排名", "节点", "类型", "度数"],
            "rows": rows,
        }]
        charts = [{"title": "度中心性排行", "option": horizontal_bar_option(
            f"度中心性 Top{len(rows)}",
            [str(r[1]) for r in rows][::-1], [r[3] for r in rows][::-1], "度数")}]

        top = records[0]
        summary = (
            f"度中心性最高的节点为「{top['name']}」（类型 {top['label']}，度数 {top['degree']}），"
            "高度数节点通常是科室核心病种或高频用药，是研究选题的候选切入点。"
        )
        facts = {
            "graph_available": True,
            "top_nodes": [{"name": str(r["name"]), "label": r["label"], "degree": r["degree"]}
                          for r in records[:10]],
        }
        return make_result(summary, tables, charts, facts)


graph_overview_skill = GraphOverviewSkill()
kg_comorbidity_skill = KGComorbiditySkill()
centrality_skill = CentralitySkill()
