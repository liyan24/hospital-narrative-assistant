from fastapi import APIRouter
from services.weekly_analysis_service import weekly_analysis_service
from services.weekly_narrative_service import weekly_narrative_service
from services.weekly_document_service import weekly_document_service
from database.json_store import json_store
from datetime import datetime

router = APIRouter()


@router.post("/analysis/run")
async def run_weekly_analysis(week_start: str = None):
    """运行周数据分析"""
    if week_start:
        dt = datetime.strptime(week_start, "%Y-%m-%d")
        filepath = weekly_analysis_service.save_weekly_analysis(f"weekly_{week_start}")
        # 重新运行并保存
        weekly_analysis_service.set_week(dt)
        result = weekly_analysis_service.run_weekly_analysis(dt)
        import json
        def convert(obj):
            import numpy as np
            import pandas as pd
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(v) for v in obj]
            elif isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif pd.isna(obj):
                return None
            return obj
        result = convert(result)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "week_start": week_start, "filepath": filepath}
    else:
        filepath = weekly_analysis_service.save_weekly_analysis("latest_weekly")
        return {"status": "ok", "analysis_id": "latest_weekly", "filepath": filepath}


@router.get("/analysis/{analysis_id}")
async def get_weekly_analysis(analysis_id: str = "latest_weekly"):
    """获取周分析结果"""
    data = weekly_analysis_service.load_weekly_analysis(analysis_id)
    if data is None:
        return {"status": "not_found", "analysis_id": analysis_id}
    return {"status": "ok", "analysis_id": analysis_id, "data": data}


@router.post("/report/generate")
async def generate_weekly_report(analysis_id: str = "latest_weekly"):
    """生成周简报"""
    report = weekly_narrative_service.generate_full_report(analysis_id)
    return {
        "status": "ok",
        "report_id": report["report_id"],
        "title": report["title"],
        "week_range": report["week_range"],
        "generated_at": report["generated_at"],
    }


@router.get("/report/{report_id}")
async def get_weekly_report(report_id: str):
    """获取周简报内容"""
    report = json_store.load(report_id)
    if report is None:
        return {"status": "not_found", "report_id": report_id}
    return {"status": "ok", "report": report}


@router.post("/report/export")
async def export_weekly_report(report_id: str, fmt: str = "docx"):
    """导出周简报为Word或PDF"""
    report = json_store.load(report_id)
    if report is None:
        return {"error": "报告不存在", "report_id": report_id}

    file_path = weekly_document_service.export_weekly(report, fmt=fmt)
    filename = file_path.split("/")[-1].split("\\")[-1]

    return {
        "file_path": file_path,
        "download_url": f"/api/weekly/download/{filename}",
    }


from fastapi.responses import FileResponse
from pathlib import Path


@router.get("/download/{filename}")
async def download_weekly_file(filename: str):
    """下载周简报文件"""
    fp = Path("./data/outputs") / filename
    if fp.exists():
        return FileResponse(str(fp), filename=filename)
    return {"error": "文件不存在", "filename": filename}
