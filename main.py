from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import settings
from routers import data, narrative, document, weekly, knowledge_graph, daily, auth, admin

app = FastAPI(
    title="医院叙事生成助手 API",
    description="基于大模型的医院科室历史数据叙事生成系统",
    version="0.2.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(data.router, prefix="/api/data", tags=["数据管理"])
app.include_router(narrative.router, prefix="/api/narrative", tags=["叙事生成"])
app.include_router(document.router, prefix="/api/document", tags=["文档生成"])
app.include_router(weekly.router, prefix="/api/weekly", tags=["周简报"])
app.include_router(knowledge_graph.router, prefix="/api/kg", tags=["知识图谱"])
app.include_router(daily.router, prefix="/api/daily", tags=["每日简报"])
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(admin.router, prefix="/api/admin", tags=["后台管理"])


@app.get("/")
async def root():
    return {"message": "医院叙事生成助手 API 运行中", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
