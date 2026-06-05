from fastapi import APIRouter
from models.schemas import DocumentExportRequest, DocumentExportResponse
from services.document_service import document_service
from database.json_store import json_store

router = APIRouter()


@router.post("/export")
async def export_document(request: DocumentExportRequest):
    """导出叙事简报为Word或PDF"""
    # 从JSON存储加载叙事内容
    data = json_store.load(request.narrative_id)
    if data is None:
        return {"error": "叙事记录不存在", "narrative_id": request.narrative_id}

    narrative = data.get("narrative", "")
    title = f"{data.get('department', '科室')}叙事简报"

    file_path = document_service.export(narrative, title, fmt=request.format)
    filename = file_path.split("/")[-1].split("\\")[-1]

    return DocumentExportResponse(
        file_path=file_path,
        download_url=f"/api/document/download/{filename}",
    )


# ========== 报告导出接口 ==========

@router.post("/report/export")
async def export_report(report_id: str, fmt: str = "docx"):
    """导出完整报告为Word或PDF（包含图表和文本）"""
    report = json_store.load(report_id)
    if report is None:
        return {"error": "报告不存在", "report_id": report_id}

    file_path = document_service.export_report(report, fmt=fmt)
    filename = file_path.split("/")[-1].split("\\")[-1]

    return DocumentExportResponse(
        file_path=file_path,
        download_url=f"/api/document/download/{filename}",
    )


from fastapi.responses import FileResponse
from pathlib import Path


@router.get("/download/{filename}")
async def download_file(filename: str):
    """下载已生成的文件"""
    # 搜索可能的输出目录
    for dir_path in ["./data/outputs", "./output"]:
        fp = Path(dir_path) / filename
        if fp.exists():
            return FileResponse(str(fp), filename=filename)
    return {"error": "文件不存在", "filename": filename}
