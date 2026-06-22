from fastapi import APIRouter
from database.mysql_client import mysql_client
from database.vector_store import vector_store
from database.neo4j_client import neo4j_client
from database.json_store import json_store
from services.data_analysis_service import data_analysis_service
from services.chart_service import chart_service
from models.schemas import HealthResponse

router = APIRouter()


@router.get("/health")
async def check_health() -> HealthResponse:
    """检查各数据库连接状态"""
    health = HealthResponse()

    # MySQL
    try:
        mysql_client.get_tables()
        health.mysql = True
    except Exception:
        pass

    # Neo4j
    health.neo4j = neo4j_client.test_connection()

    # 向量数据库
    try:
        vector_store.list_collections()
        health.vector_db = True
    except Exception:
        pass

    # LLM
    from services.llm_service import llm_service
    health.llm = llm_service.test_connection()

    return health


@router.get("/tables")
async def list_mysql_tables():
    """列出MySQL中的所有表"""
    return {"tables": mysql_client.get_tables()}


@router.get("/patients")
async def list_patients(limit: int = 50, offset: int = 0):
    """分页列出患者"""
    rows = mysql_client.execute(
        "SELECT patient_id, medical_record_no, age, gender, marriage, occupation FROM patients LIMIT :limit OFFSET :offset",
        {"limit": limit, "offset": offset},
    )
    return {
        "patients": [
            {"patient_id": r[0], "medical_record_no": r[1], "age": r[2], "gender": r[3], "marriage": r[4], "occupation": r[5]}
            for r in rows
        ]
    }


@router.get("/patients/search")
async def search_patients(keyword: str, limit: int = 20):
    """按ID/姓名/病案号搜索患者"""
    like = f"%{keyword}%"
    rows = mysql_client.execute(
        "SELECT patient_id, medical_record_no, age, gender FROM patients WHERE patient_id LIKE :kw OR medical_record_no LIKE :kw LIMIT :limit",
        {"kw": like, "limit": limit},
    )
    return {
        "patients": [
            {"patient_id": r[0], "medical_record_no": r[1], "age": r[2], "gender": r[3]}
            for r in rows
        ]
    }


@router.get("/table/{table_name}")
async def get_table_schema(table_name: str):
    """获取指定表的结构"""
    schema = mysql_client.get_table_schema(table_name)
    return {"table": table_name, "columns": [dict(row._mapping) for row in schema]}


@router.get("/vector/collections")
async def list_vector_collections():
    """列出向量数据库中的所有集合"""
    return {"collections": vector_store.list_collections()}


@router.post("/json/{doc_id}")
async def save_json(doc_id: str, data: dict):
    """保存JSON文档"""
    json_store.save(doc_id, data)
    return {"status": "ok", "doc_id": doc_id}


@router.get("/json/{doc_id}")
async def load_json(doc_id: str):
    """读取JSON文档"""
    data = json_store.load(doc_id)
    if data is None:
        return {"status": "not_found", "doc_id": doc_id}
    return {"status": "ok", "doc_id": doc_id, "data": data}


# ========== 数据分析接口 ==========

@router.post("/analysis/run")
async def run_analysis(analysis_id: str = "latest"):
    """运行全量数据分析并保存"""
    filepath = data_analysis_service.save_analysis(analysis_id)
    return {"status": "ok", "analysis_id": analysis_id, "filepath": filepath}


@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: str = "latest"):
    """获取分析结果"""
    data = data_analysis_service.load_analysis(analysis_id)
    if data is None:
        return {"status": "not_found", "analysis_id": analysis_id}
    return {"status": "ok", "analysis_id": analysis_id, "data": data}


@router.get("/analysis/{analysis_id}/charts")
async def get_charts(analysis_id: str = "latest"):
    """获取图表配置"""
    data = data_analysis_service.load_analysis(analysis_id)
    if data is None:
        return {"status": "not_found", "analysis_id": analysis_id}
    charts = chart_service.generate_all_charts(data)
    return {"status": "ok", "analysis_id": analysis_id, "charts": charts}
