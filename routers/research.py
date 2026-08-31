from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from models.schemas import (
    ResearchSkillRunRequest, ResearchCodeRunRequest,
    ResearchRecommendRequest, ResearchInterpretRequest,
    LiteratureSearchRequest, PaperGenerateRequest,
    AutoResearchStartRequest, AutoTopicsRequest, AutoCustomTopicRequest,
)
from services.research.auto_research_service import auto_research_service
from services.research.dataset_service import dataset_service
from services.research.custom_code_service import custom_code_service
from services.research.research_assistant_service import research_assistant_service
from services.research.skills.registry import list_skills_by_category, get_skill

router = APIRouter()


def _flatten(payload: dict) -> dict:
    """将 run_skill 返回中嵌套的 result 字段拍平到顶层（匹配前端契约：
    summary/tables/charts/facts 与 result_id/interpretation 同级）"""
    flat = dict(payload)
    nested = flat.pop("result", None) or {}
    return {**flat, **nested}


@router.get("/data-assets")
async def get_data_assets() -> dict:
    """数据资产清单：表规模 / 图谱状态 / 文本数据 / 向量库"""
    return {"status": "ok", "assets": dataset_service.detect_data_assets()}


@router.get("/skills")
async def list_research_skills() -> dict:
    """按类别列出全部科研算子及其参数表单 schema（前端契约：list[{category, skills}]）"""
    grouped = list_skills_by_category()
    categories = [{"category": cat, "skills": skills} for cat, skills in grouped.items()]
    return {"status": "ok", "categories": categories}


@router.post("/skills/{skill_id}/run")
async def run_research_skill(skill_id: str, request: ResearchSkillRunRequest) -> dict:
    """执行科研算子（含 LLM 解读），返回带 result_id 的完整结果"""
    if get_skill(skill_id) is None:
        raise HTTPException(status_code=404, detail=f"未知算子: {skill_id}")
    try:
        return {"status": "ok", **_flatten(research_assistant_service.run_skill(skill_id, request.params))}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/results/{result_id}")
async def get_research_result(result_id: str) -> dict:
    """获取已保存的算子结果"""
    result = research_assistant_service.get_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="结果不存在")
    return {"status": "ok", **_flatten(result)}


@router.post("/code/run")
async def run_custom_code(request: ResearchCodeRunRequest) -> dict:
    """执行自定义 pandas 代码（实验性受限执行），返回结构与算子结果一致"""
    return {"status": "ok", **custom_code_service.run(request.code)}


@router.post("/recommend")
async def recommend_analysis_path(request: ResearchRecommendRequest) -> dict:
    """LLM 根据研究问题推荐分析路径"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="研究问题不能为空")
    return {"status": "ok", **research_assistant_service.recommend_path(request.question)}


@router.post("/interpret")
async def interpret_result(request: ResearchInterpretRequest) -> dict:
    """对已保存的结果重新生成 LLM 解读"""
    result = research_assistant_service.get_result(request.result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="结果不存在")
    skill = get_skill(result.get("skill_id", ""))
    if skill is None:
        raise HTTPException(status_code=400, detail="结果对应的算子已不存在")
    interpretation = research_assistant_service._interpret(
        skill.meta, result.get("params", {}), result.get("result", {}))
    return {"status": "ok", "result_id": request.result_id, "interpretation": interpretation}


@router.post("/literature/search")
async def search_literature(request: LiteratureSearchRequest) -> dict:
    """PubMed 文献检索（走 literature_search 算子，含 LLM 要点总结）"""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="检索式不能为空")
    flat = _flatten(research_assistant_service.run_skill(
        "literature_search", {"query": request.query, "max_results": request.max_results}))
    # 前端契约：articles 置于顶层
    flat["articles"] = flat.get("facts", {}).get("articles", [])
    return {"status": "ok", **flat}


@router.post("/paper/generate")
async def generate_paper(request: PaperGenerateRequest) -> dict:
    """汇总选定分析结果与文献，生成 IMRaD 中文论文 docx"""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="研究问题不能为空")
    try:
        return {"status": "ok", **research_assistant_service.generate_paper(
            question=request.question,
            result_ids=request.result_ids,
            articles=request.articles,
            title=request.title,
        )}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/paper/download/{filename}")
async def download_paper(filename: str):
    """下载生成的论文文件（防路径穿越）"""
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.endswith(".docx"):
        raise HTTPException(status_code=400, detail="非法文件名")
    fp = Path("./data/outputs") / safe_name
    if not fp.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(str(fp), filename=safe_name)


# ========== 智能自动科研流水线 ==========


@router.post("/auto/topics")
async def propose_auto_topics(request: AutoTopicsRequest = AutoTopicsRequest()) -> dict:
    """LLM 基于数据画像推荐 3-5 个数据可支撑的研究议题；
    refresh=True 时跳过缓存并排除已推荐过的议题标题"""
    return {"status": "ok", "topics": auto_research_service.propose_topics(
        refresh=request.refresh, exclude_titles=request.exclude_titles)}


@router.post("/auto/topics/custom")
async def evaluate_custom_topic(request: AutoCustomTopicRequest) -> dict:
    """LLM 评估用户自定义研究设想的数据可支撑性，返回细化议题与 supported 标记"""
    if not request.idea.strip():
        raise HTTPException(status_code=400, detail="研究设想不能为空")
    return {"status": "ok", **auto_research_service.evaluate_custom_topic(request.idea)}


@router.get("/auto/history")
async def list_auto_history() -> dict:
    """历史自动流水线任务列表（含论文下载信息），按创建时间倒序"""
    return {"status": "ok", "jobs": auto_research_service.list_history()}


@router.post("/auto/start")
async def start_auto_pipeline(request: AutoResearchStartRequest) -> dict:
    """按选定议题启动自动流水线（后台线程），返回 job_id 供轮询"""
    if not request.topic or not request.topic.get("skills"):
        raise HTTPException(status_code=400, detail="议题不能为空且需包含 skills")
    return {"status": "ok", "job_id": auto_research_service.start_pipeline(request.topic)}


@router.get("/auto/{job_id}")
async def get_auto_job(job_id: str) -> dict:
    """查询流水线任务状态（current_step 为当前 running 步骤下标，无则 -1）"""
    job = auto_research_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    current_step = next(
        (i for i, s in enumerate(job.get("steps", [])) if s.get("state") == "running"), -1)
    return {"status": "ok", "job": {
        "job_id": job.get("job_id"),
        "state": job.get("state"),
        "current_step": current_step,
        "steps": job.get("steps", []),
        "topic": job.get("topic"),
        "result_ids": job.get("result_ids", []),
        "paper": job.get("paper"),
        "filename": job.get("filename"),
        "download_url": job.get("download_url"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "finished_at": job.get("finished_at"),
    }}
