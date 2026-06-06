"""
知识图谱可视化数据服务
为Streamlit ECharts等前端组件提供子图数据（nodes + links）
"""
from typing import List, Optional

from database.neo4j_client import neo4j_client


class KGVisualService:
    """知识图谱可视化数据服务"""

    MAX_NODES = 200  # 限制最大节点数，避免前端渲染卡死

    def get_patient_subgraph(self, patient_id: str, max_visits: int = 10) -> dict:
        """
        获取患者子图数据
        节点: Patient, Visit, Disease, Drug, Exam, Surgery, ChiefComplaint
        关系: HAS_VISIT, DIAGNOSED_WITH, PRESCRIBED, PERFORMED_EXAM, UNDERWENT, CHIEF_COMPLAINT
        """
        # 限制就诊数量，避免节点爆炸
        visit_records = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)
            RETURN v.visit_id AS visit_id, id(v) AS vid
            ORDER BY v.admission_date
            LIMIT $limit
        """, {"pid": patient_id, "limit": max_visits})

        visit_ids = [r["vid"] for r in visit_records]
        visit_id_map = {r["vid"]: r["visit_id"] for r in visit_records}

        if not visit_ids:
            return {"nodes": [], "links": [], "stats": {"nodes": 0, "links": 0}}

        # 构建Cypher参数
        nodes = {}
        links = []

        # 患者节点
        p_records = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})
            RETURN id(p) AS node_id, p.patient_id AS pid, p.age AS age, p.gender AS gender
        """, {"pid": patient_id})
        for r in p_records:
            nodes[r["node_id"]] = {
                "id": r["node_id"],
                "label": "Patient",
                "name": r["pid"],
                "category": "患者",
                "symbolSize": 30,
                "age": r["age"],
                "gender": r["gender"],
            }

        # 就诊节点及其关联实体
        visit_records = neo4j_client.run("""
            MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)
            RETURN id(p) AS pid, id(v) AS vid, v.visit_id AS visit_id,
                   v.admission_date AS admission_date, v.discharge_date AS discharge_date,
                   v.length_of_stay AS los
            ORDER BY v.admission_date
            LIMIT $limit
        """, {"pid": patient_id, "limit": max_visits})

        patient_node_id = None
        for r in visit_records:
            patient_node_id = r["pid"]
            vid = r["vid"]
            nodes[vid] = {
                "id": vid,
                "label": "Visit",
                "name": r["visit_id"],
                "category": "就诊",
                "symbolSize": 20,
                "admission_date": r["admission_date"],
                "discharge_date": r["discharge_date"],
                "length_of_stay": r["los"],
            }
            links.append({
                "source": r["pid"],
                "target": vid,
                "relation": "HAS_VISIT",
                "name": "就诊",
            })

        # 关系批量查询
        rel_configs = [
            (", (v)-[:DIAGNOSED_WITH]->(d:Disease)", "Disease", "诊断", "诊断", 15),
            (", (v)-[:PRESCRIBED]->(d:Drug)", "Drug", "用药", "用药", 12),
            (", (v)-[:PERFORMED_EXAM]->(d:Exam)", "Exam", "检查", "检查", 10),
            (", (v)-[:UNDERWENT]->(d:Surgery)", "Surgery", "手术", "手术", 15),
            (", (v)-[:CHIEF_COMPLAINT]->(d:ChiefComplaint)", "ChiefComplaint", "主诉", "主诉", 12),
        ]

        for pattern, label, relation_name, category, size in rel_configs:
            query = f"""
                MATCH (p:Patient {{patient_id: $pid}})-[:HAS_VISIT]->(v:Visit){pattern}
                RETURN id(v) AS vid, id(d) AS did, d.name AS name
                ORDER BY v.admission_date
                LIMIT $limit
            """
            records = neo4j_client.run(query, {"pid": patient_id, "limit": max_visits * 30})
            for r in records:
                did = r["did"]
                if did not in nodes:
                    nodes[did] = {
                        "id": did,
                        "label": label,
                        "name": r["name"],
                        "category": category,
                        "symbolSize": size,
                    }
                links.append({
                    "source": r["vid"],
                    "target": did,
                    "relation": relation_name,
                    "name": relation_name,
                })

        return self._format_graph(nodes, links, f"患者 {patient_id} 子图")

    def _resolve_disease_names(self, keyword: str) -> List[str]:
        """通过CONTAINS模糊查询解析疾病名列表"""
        records = neo4j_client.run("""
            MATCH (d:Disease)
            WHERE d.name CONTAINS $keyword
            RETURN d.name AS name
            LIMIT 50
        """, {"keyword": keyword})
        names = [r["name"] for r in records if r["name"]]
        seen = set()
        unique = []
        for n in names:
            if n not in seen:
                seen.add(n)
                unique.append(n)
        return unique

    def get_disease_subgraph(self, disease_name: str, top_n: int = 15) -> dict:
        """
        获取疾病关联子图
        中心节点: Disease
        关联: Drug, Exam, Surgery, Disease(合并症)
        支持模糊匹配（如"肺恶性肿瘤"匹配"左肺恶性肿瘤::western"等）
        """
        nodes = {}
        links = []

        # 模糊匹配疾病名
        disease_names = self._resolve_disease_names(disease_name)
        if not disease_names:
            # fallback: 精确匹配
            d_records = neo4j_client.run("""
                MATCH (d:Disease {name: $name})
                RETURN id(d) AS did, d.name AS dname
            """, {"name": disease_name})
            if not d_records:
                return {"nodes": [], "links": [], "stats": {"nodes": 0, "links": 0}}
            disease_names = [disease_name]
            center_id = d_records[0]["did"]
            display_name = disease_name
        else:
            # 以第一个匹配疾病作为中心节点
            d_records = neo4j_client.run("""
                MATCH (d:Disease {name: $name})
                RETURN id(d) AS did
            """, {"name": disease_names[0]})
            center_id = d_records[0]["did"] if d_records else 0
            display_name = disease_names[0] if len(disease_names) == 1 else f"{disease_names[0]} 等{len(disease_names)}种"

        nodes[center_id] = {
            "id": center_id,
            "label": "Disease",
            "name": display_name,
            "category": "疾病",
            "symbolSize": 40,
        }

        # 药品（聚合多疾病）
        drug_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
            WHERE d.name IN $names
            RETURN id(dr) AS did, dr.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT $limit
        """, {"names": disease_names, "limit": top_n})
        for r in drug_records:
            did = r["did"]
            nodes[did] = {
                "id": did, "label": "Drug", "name": r["name"],
                "category": "药品", "symbolSize": 15,
                "count": r["cnt"],
            }
            links.append({"source": center_id, "target": did, "relation": "用药", "name": "常用药品"})

        # 检查（聚合多疾病）
        exam_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PERFORMED_EXAM]->(e:Exam)
            WHERE d.name IN $names
            RETURN id(e) AS eid, e.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT $limit
        """, {"names": disease_names, "limit": top_n})
        for r in exam_records:
            eid = r["eid"]
            nodes[eid] = {
                "id": eid, "label": "Exam", "name": r["name"],
                "category": "检查", "symbolSize": 12,
                "count": r["cnt"],
            }
            links.append({"source": center_id, "target": eid, "relation": "检查", "name": "常规检查"})

        # 合并症（排除自身匹配的疾病）
        comorb_records = neo4j_client.run("""
            MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(co:Disease)
            WHERE d.name IN $names AND NOT co.name IN $names
            RETURN id(co) AS coid, co.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT $limit
        """, {"names": disease_names, "limit": top_n})
        for r in comorb_records:
            coid = r["coid"]
            nodes[coid] = {
                "id": coid, "label": "Disease", "name": r["name"],
                "category": "合并症", "symbolSize": 18,
                "count": r["cnt"],
            }
            links.append({"source": center_id, "target": coid, "relation": "合并症", "name": "合并症"})

        return self._format_graph(nodes, links, f"疾病 '{display_name}' 关联子图")

    def get_drug_cooccurrence_graph(self, disease_name: Optional[str] = None, top_n: int = 20) -> dict:
        """
        获取药品共现网络
        节点: Drug
        边: 在同一次就诊中共现的药品对
        """
        nodes = {}
        links = []

        if disease_name:
            # 特定疾病的药品共现（支持模糊匹配）
            disease_names = self._resolve_disease_names(disease_name)
            if not disease_names:
                disease_names = [disease_name]
            pair_records = neo4j_client.run("""
                MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
                WHERE d.name IN $names
                WITH v, collect(dr.name) AS drugs, collect(id(dr)) AS drug_ids
                UNWIND range(0, size(drugs)-1) AS i
                UNWIND range(0, size(drugs)-1) AS j
                WITH drugs[i] AS d1, drug_ids[i] AS id1,
                     drugs[j] AS d2, drug_ids[j] AS id2
                WHERE id1 < id2
                RETURN d1, id1, d2, id2, count(*) AS pair_count
                ORDER BY pair_count DESC LIMIT $limit
            """, {"names": disease_names, "limit": top_n})
        else:
            # 全局药品共现
            pair_records = neo4j_client.run("""
                MATCH (v:Visit)-[:PRESCRIBED]->(dr:Drug)
                WITH v, collect(dr.name) AS drugs, collect(id(dr)) AS drug_ids
                UNWIND range(0, size(drugs)-1) AS i
                UNWIND range(0, size(drugs)-1) AS j
                WITH drugs[i] AS d1, drug_ids[i] AS id1,
                     drugs[j] AS d2, drug_ids[j] AS id2
                WHERE id1 < id2
                RETURN d1, id1, d2, id2, count(*) AS pair_count
                ORDER BY pair_count DESC LIMIT $limit
            """, {"limit": top_n})

        for r in pair_records:
            id1 = r["id1"]
            id2 = r["id2"]
            if id1 not in nodes:
                nodes[id1] = {
                    "id": id1, "label": "Drug", "name": r["d1"],
                    "category": "药品", "symbolSize": 15,
                }
            if id2 not in nodes:
                nodes[id2] = {
                    "id": id2, "label": "Drug", "name": r["d2"],
                    "category": "药品", "symbolSize": 15,
                }
            links.append({
                "source": id1,
                "target": id2,
                "relation": "共现",
                "name": "共现",
                "value": r["pair_count"],
            })

        title = f"疾病 '{disease_name}' 药品共现网络" if disease_name else "全局药品共现网络"
        return self._format_graph(nodes, links, title)

    def get_comorbidity_network(self, disease_name: Optional[str] = None, top_n: int = 20) -> dict:
        """
        获取疾病共现网络
        节点: Disease
        边: 在同一次就诊中共现的疾病对
        """
        nodes = {}
        links = []

        if disease_name:
            # 模糊匹配疾病名
            disease_names = self._resolve_disease_names(disease_name)
            if not disease_names:
                disease_names = [disease_name]
            display_name = disease_names[0] if len(disease_names) == 1 else f"{disease_names[0]} 等{len(disease_names)}种"

            # 以某疾病为中心的共现星型图（聚合多疾病）
            records = neo4j_client.run("""
                MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(co:Disease)
                WHERE d.name IN $names AND NOT co.name IN $names
                RETURN id(co) AS coid, co.name AS co_name, count(DISTINCT v) AS cnt
                ORDER BY cnt DESC LIMIT $limit
            """, {"names": disease_names, "limit": top_n})

            # 中心节点（取第一个匹配疾病的ID，若不存在则虚拟一个负ID）
            center_records = neo4j_client.run("""
                MATCH (d:Disease {name: $name})
                RETURN id(d) AS did
            """, {"name": disease_names[0]})
            center_id = center_records[0]["did"] if center_records else -1
            nodes[center_id] = {
                "id": center_id, "label": "Disease", "name": display_name,
                "category": "疾病", "symbolSize": 35,
            }

            for r in records:
                coid = r["coid"]
                if coid not in nodes:
                    nodes[coid] = {
                        "id": coid, "label": "Disease", "name": r["co_name"],
                        "category": "合并症", "symbolSize": 18,
                        "count": r["cnt"],
                    }
                links.append({
                    "source": center_id, "target": coid,
                    "relation": "合并症", "name": "合并症", "value": r["cnt"],
                })
        else:
            # 全局Top疾病共现对
            records = neo4j_client.run("""
                MATCH (v:Visit)-[:DIAGNOSED_WITH]->(d:Disease)
                WITH v, collect(d.name) AS diseases, collect(id(d)) AS disease_ids
                UNWIND range(0, size(diseases)-1) AS i
                UNWIND range(0, size(diseases)-1) AS j
                WITH diseases[i] AS d1, disease_ids[i] AS id1,
                     diseases[j] AS d2, disease_ids[j] AS id2
                WHERE id1 < id2
                RETURN d1, id1, d2, id2, count(*) AS pair_count
                ORDER BY pair_count DESC LIMIT $limit
            """, {"limit": top_n})

            for r in records:
                id1 = r["id1"]
                id2 = r["id2"]
                if id1 not in nodes:
                    nodes[id1] = {
                        "id": id1, "label": "Disease", "name": r["d1"],
                        "category": "疾病", "symbolSize": 20,
                    }
                if id2 not in nodes:
                    nodes[id2] = {
                        "id": id2, "label": "Disease", "name": r["d2"],
                        "category": "疾病", "symbolSize": 20,
                    }
                links.append({
                    "source": id1, "target": id2,
                    "relation": "共现", "name": "共现", "value": r["pair_count"],
                })

        title = f"'{disease_name}' 合并症网络" if disease_name else "全局疾病共现网络"
        return self._format_graph(nodes, links, title)

    def _format_graph(self, nodes: dict, links: list, title: str) -> dict:
        """统一格式化输出"""
        # 去重节点
        node_list = list(nodes.values())
        # 如果节点过多，截断并提示
        if len(node_list) > self.MAX_NODES:
            node_list = node_list[:self.MAX_NODES]
            node_ids = {n["id"] for n in node_list}
            links = [l for l in links if l["source"] in node_ids and l["target"] in node_ids]

        return {
            "title": title,
            "nodes": node_list,
            "links": links,
            "stats": {
                "nodes": len(node_list),
                "links": len(links),
            },
            "categories": [
                {"name": "患者"},
                {"name": "就诊"},
                {"name": "疾病"},
                {"name": "合并症"},
                {"name": "药品"},
                {"name": "检查"},
                {"name": "手术"},
                {"name": "主诉"},
            ],
        }


# 全局单例
kg_visual_service = KGVisualService()
