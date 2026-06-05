from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

from services.knowledge_graph_service import KnowledgeGraphService
from services.kg_visual_service import kg_visual_service
from database.neo4j_client import neo4j_client

router = APIRouter()


class KGBuildRequest(BaseModel):
    clear: bool = False


class KGBuildResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[str] = None


class KGStatsResponse(BaseModel):
    nodes: dict
    relationships: dict


@router.post("/build", response_model=KGBuildResponse)
async def build_knowledge_graph(request: KGBuildRequest):
    """构建/重建知识图谱（同步执行，可能耗时较长）"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败，请检查配置")

    try:
        kg = KnowledgeGraphService(neo4j_client)
        kg.build_all(clear=request.clear)
        return KGBuildResponse(
            success=True,
            message="知识图谱构建完成",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"构建失败: {str(e)}")


@router.get("/stats", response_model=KGStatsResponse)
async def get_knowledge_graph_stats():
    """获取知识图谱统计信息"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败，请检查配置")

    nodes = {}
    relationships = {}

    node_labels = ["Patient", "Visit", "Disease", "ChiefComplaint", "Exam", "LabItem", "Drug", "Surgery", "Department"]
    for label in node_labels:
        try:
            records = neo4j_client.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            nodes[label] = records[0]["cnt"] if records else 0
        except Exception:
            nodes[label] = 0

    rel_types = [
        "HAS_VISIT", "DIAGNOSED_WITH", "CHIEF_COMPLAINT", "PERFORMED_EXAM",
        "HAS_LAB_RESULT", "PRESCRIBED", "UNDERWENT", "IN_DEPARTMENT", "TREATS",
    ]
    for rel_type in rel_types:
        try:
            records = neo4j_client.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt")
            relationships[rel_type] = records[0]["cnt"] if records else 0
        except Exception:
            relationships[rel_type] = 0

    return KGStatsResponse(nodes=nodes, relationships=relationships)


@router.get("/query")
async def query_knowledge_graph(cypher: str):
    """执行Cypher查询（仅用于开发和调试）"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败，请检查配置")

    try:
        records = neo4j_client.run(cypher)
        return {"records": [{k: str(v) for k, v in r.items()} for r in records]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"查询失败: {str(e)}")


@router.get("/sample")
async def get_sample_graph(limit: int = 100):
    """获取图谱样本数据（节点和关系）"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败，请检查配置")

    try:
        # 获取样本节点
        nodes_result = neo4j_client.run("""
            MATCH (n)
            WITH labels(n)[0] AS label, n
            ORDER BY rand()
            RETURN label, collect(n {.*, _id: id(n)})[0..$limit] AS items
        """, {"limit": limit // 5})

        nodes = []
        for record in nodes_result:
            label = record["label"]
            for item in record["items"]:
                item["label"] = label
                nodes.append(item)

        # 获取样本关系
        rels_result = neo4j_client.run("""
            MATCH (a)-[r]->(b)
            RETURN type(r) AS rel_type, id(a) AS from_id, id(b) AS to_id,
                   labels(a)[0] AS from_label, labels(b)[0] AS to_label,
                   properties(r) AS rel_props
            LIMIT $limit
        """, {"limit": limit})

        relationships = []
        for record in rels_result:
            relationships.append({
                "type": record["rel_type"],
                "from_id": record["from_id"],
                "to_id": record["to_id"],
                "from_label": record["from_label"],
                "to_label": record["to_label"],
                "properties": record["rel_props"],
            })

        return {"nodes": nodes, "relationships": relationships}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取样本失败: {str(e)}")


# ========== P1: 交互式图谱可视化接口 ==========

@router.get("/subgraph/patient/{patient_id}")
async def get_patient_subgraph(patient_id: str, max_visits: int = 10):
    """
    获取患者子图可视化数据
    节点: Patient, Visit, Disease, Drug, Exam, Surgery, ChiefComplaint
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    try:
        graph = kg_visual_service.get_patient_subgraph(patient_id, max_visits)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取患者子图失败: {str(e)}")


@router.get("/subgraph/disease/{disease_name}")
async def get_disease_subgraph(disease_name: str, top_n: int = 15):
    """
    获取疾病关联子图可视化数据
    中心节点为指定疾病，关联药品、检查、合并症等
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    try:
        graph = kg_visual_service.get_disease_subgraph(disease_name, top_n)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取疾病子图失败: {str(e)}")


@router.get("/subgraph/drug-pattern/{disease_name}")
async def get_drug_pattern_subgraph(disease_name: str, top_n: int = 20):
    """
    获取药品共现网络可视化数据
    节点为药品，边为同一次就诊中的共现关系
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    try:
        graph = kg_visual_service.get_drug_cooccurrence_graph(disease_name, top_n)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取药品共现网络失败: {str(e)}")


@router.get("/subgraph/drug-pattern")
async def get_global_drug_pattern_subgraph(top_n: int = 20):
    """获取全局药品共现网络"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    try:
        graph = kg_visual_service.get_drug_cooccurrence_graph(None, top_n)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取全局药品共现网络失败: {str(e)}")


@router.get("/subgraph/comorbidity/{disease_name}")
async def get_comorbidity_subgraph(disease_name: str, top_n: int = 20):
    """
    获取疾病合并症网络可视化数据
    中心节点为指定疾病，边连接常见合并症
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    try:
        graph = kg_visual_service.get_comorbidity_network(disease_name, top_n)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取合并症网络失败: {str(e)}")


@router.get("/subgraph/comorbidity")
async def get_global_comorbidity_subgraph(top_n: int = 20):
    """获取全局疾病共现网络"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    try:
        graph = kg_visual_service.get_comorbidity_network(None, top_n)
        return graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取全局疾病共现网络失败: {str(e)}")
