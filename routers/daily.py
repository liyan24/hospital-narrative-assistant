from fastapi import APIRouter
from services.daily_briefing_service import daily_briefing_service
from database.neo4j_client import neo4j_client

router = APIRouter()


@router.get("/briefing")
async def get_daily_briefing(date: str = None):
    """获取科室每日晨会简报"""
    if not neo4j_client.test_connection():
        return {"status": "error", "message": "Neo4j连接失败"}

    briefing = daily_briefing_service.generate_briefing(date)
    return {"status": "ok", "briefing": briefing}


@router.post("/briefing/generate")
async def generate_daily_briefing(date: str = None):
    """手动触发生成每日晨会简报"""
    if not neo4j_client.test_connection():
        return {"status": "error", "message": "Neo4j连接失败"}

    briefing = daily_briefing_service.generate_briefing(date)
    return {"status": "ok", "briefing": briefing}
