from fastapi import APIRouter, HTTPException
from typing import Optional
from models.schemas import (
    NarrativeRequest, NarrativeResponse,
    PatientNarrativeRequest, PatientNarrativeResponse,
    PathwayNarrativeRequest, PathwayNarrativeResponse,
    ComorbidityRequest, ComorbidityResponse,
    DrugPatternRequest, DrugPatternResponse,
    ReadmissionResponse,
    KGRAGRequest, KGRAGResponse,
    TCMNarrativeRequest, TCMNarrativeResponse,
    QualityControlRequest, QualityControlResponse,
    DepartmentOperationRequest, DepartmentOperationResponse,
    SimilarPatientRequest, SimilarPatientResponse,
    RiskPredictionRequest, RiskPredictionResponse,
)
from services.narrative_service import narrative_service
from services.patient_narrative_service import patient_narrative_service
from services.pathway_narrative_service import pathway_narrative_service
from services.comorbidity_service import comorbidity_service
from services.drug_pattern_service import drug_pattern_service
from services.readmission_service import readmission_service
from services.kg_rag_service import kg_rag_service
from services.tcm_narrative_service import tcm_narrative_service
from services.quality_control_service import quality_control_service
from services.department_operation_service import department_operation_service
from services.similar_patient_service import similar_patient_service
from services.risk_prediction_service import risk_prediction_service
from database.json_store import json_store
from database.neo4j_client import neo4j_client
import uuid

router = APIRouter()


@router.post("/generate", response_model=NarrativeResponse)
async def generate_narrative(request: NarrativeRequest):
    """生成叙事简报（基于科室数据）"""
    result = narrative_service.generate_department_narrative(
        department=request.department,
        patient_id=request.patient_id,
        date_range=request.date_range,
        additional_context=request.additional_context,
    )

    # 保存到JSON存储
    narrative_id = str(uuid.uuid4())
    json_store.save(narrative_id, {
        "department": request.department,
        "patient_id": request.patient_id,
        "date_range": request.date_range,
        "narrative": result["narrative"],
        "sources": result["sources"],
    })

    return NarrativeResponse(
        narrative=result["narrative"],
        sources=result["sources"] + [f"stored:{narrative_id}"],
    )


@router.get("/history")
async def list_narrative_history():
    """列出已生成的叙事记录"""
    ids = json_store.list_all()
    return {"records": ids}


# ========== 报告生成接口 ==========

@router.post("/report/generate")
async def generate_report(analysis_id: str = "latest"):
    """生成完整数据分析报告（含图表+文本）"""
    report = narrative_service.generate_full_report(analysis_id)
    return {
        "status": "ok",
        "report_id": report["report_id"],
        "title": report["title"],
        "generated_at": report["generated_at"],
    }


@router.get("/report/{report_id}")
async def get_report(report_id: str):
    """获取完整报告内容"""
    report = json_store.load(report_id)
    if report is None:
        return {"status": "not_found", "report_id": report_id}
    return {"status": "ok", "report": report}


@router.get("/report/{report_id}/charts")
async def get_report_charts(report_id: str):
    """获取报告中的图表配置"""
    report = json_store.load(report_id)
    if report is None:
        return {"status": "not_found", "report_id": report_id}
    return {"status": "ok", "charts": report.get("charts", {})}


@router.get("/report/{report_id}/texts")
async def get_report_texts(report_id: str):
    """获取报告中的文本内容"""
    report = json_store.load(report_id)
    if report is None:
        return {"status": "not_found", "report_id": report_id}
    return {"status": "ok", "texts": report.get("texts", {})}


# ========== P0: 个体患者故事线接口 ==========

@router.post("/patient/storyline", response_model=PatientNarrativeResponse)
async def generate_patient_storyline(request: PatientNarrativeRequest):
    """
    基于知识图谱生成个体患者故事线叙事
    输入患者ID，返回该患者的完整就诊故事线
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败，无法查询患者数据")

    result = patient_narrative_service.generate_narrative(request.patient_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return PatientNarrativeResponse(
        patient_id=result["patient_id"],
        visit_count=result["visit_count"],
        narrative=result["narrative"],
    )


@router.get("/patient/storyline/{patient_id}")
async def get_patient_storyline(patient_id: str):
    """GET方式获取患者故事线"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败，无法查询患者数据")

    result = patient_narrative_service.generate_narrative(patient_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return PatientNarrativeResponse(
        patient_id=result["patient_id"],
        visit_count=result["visit_count"],
        narrative=result["narrative"],
    )


# ========== P0: 诊疗路径模式叙事接口 ==========

@router.post("/pathway", response_model=PathwayNarrativeResponse)
async def generate_pathway_narrative(request: PathwayNarrativeRequest):
    """
    基于知识图谱生成某疾病的诊疗路径模式叙事
    输入疾病名称，返回该疾病在本科室的典型诊疗路径分析
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败，无法查询图谱数据")

    result = pathway_narrative_service.generate_narrative(request.disease_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return PathwayNarrativeResponse(
        disease_name=result["disease_name"],
        narrative=result["narrative"],
    )


@router.get("/pathway/{disease_name}")
async def get_pathway_narrative(disease_name: str):
    """GET方式获取诊疗路径叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败，无法查询图谱数据")

    result = pathway_narrative_service.generate_narrative(disease_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return PathwayNarrativeResponse(
        disease_name=result["disease_name"],
        narrative=result["narrative"],
    )


# ========== P1: 疾病共现网络叙事接口 ==========

@router.post("/comorbidity", response_model=ComorbidityResponse)
async def generate_comorbidity_narrative(request: ComorbidityRequest):
    """
    基于知识图谱生成疾病共现网络叙事
    输入疾病名称分析该疾病的合并症；不输入则分析全局共现模式
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = comorbidity_service.generate_narrative(request.disease_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return ComorbidityResponse(
        target_disease=result.get("target_disease"),
        narrative=result["narrative"],
    )


@router.get("/comorbidity/{disease_name}")
async def get_comorbidity_narrative(disease_name: str):
    """GET方式获取疾病共现叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = comorbidity_service.generate_narrative(disease_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return ComorbidityResponse(
        target_disease=result.get("target_disease"),
        narrative=result["narrative"],
    )


@router.get("/comorbidity")
async def get_global_comorbidity_narrative():
    """获取全局疾病共现叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = comorbidity_service.generate_narrative(None)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return ComorbidityResponse(
        target_disease=None,
        narrative=result["narrative"],
    )


# ========== P1: 用药模式叙事接口 ==========

@router.post("/drug-pattern", response_model=DrugPatternResponse)
async def generate_drug_pattern_narrative(request: DrugPatternRequest):
    """
    基于知识图谱生成用药模式与合理性叙事
    输入疾病名称分析该疾病的用药；不输入则分析全局用药模式
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = drug_pattern_service.generate_narrative(request.disease_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return DrugPatternResponse(
        disease_name=result.get("disease_name"),
        narrative=result["narrative"],
    )


@router.get("/drug-pattern/{disease_name}")
async def get_drug_pattern_narrative(disease_name: str):
    """GET方式获取用药模式叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = drug_pattern_service.generate_narrative(disease_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return DrugPatternResponse(
        disease_name=result.get("disease_name"),
        narrative=result["narrative"],
    )


@router.get("/drug-pattern")
async def get_global_drug_pattern_narrative():
    """获取全局用药模式叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = drug_pattern_service.generate_narrative(None)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return DrugPatternResponse(
        disease_name=None,
        narrative=result["narrative"],
    )


# ========== P1: 再入院患者时间线叙事接口 ==========

@router.get("/readmission/summary")
async def get_readmission_summary():
    """获取再入院整体分析叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = readmission_service.generate_summary_narrative()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return ReadmissionResponse(
        narrative=result["narrative"],
        stats=result.get("stats"),
    )


@router.get("/readmission/patient/{patient_id}")
async def get_readmission_patient_narrative(patient_id: str):
    """获取单个再入院患者的纵向叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = readmission_service.generate_patient_narrative(patient_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return {
        "patient_id": result["patient_id"],
        "visit_count": result["visit_count"],
        "narrative": result["narrative"],
    }


@router.get("/readmission/patients")
async def list_readmission_patients(min_visits: int = 2, limit: int = 50):
    """列出多次就诊的患者列表"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    patients = readmission_service.get_readmission_patients(min_visits, limit)
    return {"patients": patients}


# ========== P1: LLM + 知识图谱 RAG 问答接口 ==========

@router.post("/rag/ask", response_model=KGRAGResponse)
async def kg_rag_ask(request: KGRAGRequest):
    """
    基于知识图谱的RAG问答
    LLM基于Neo4j检索的真实关系子图生成回答，避免编造
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = kg_rag_service.answer(request.question)
    return KGRAGResponse(
        question=result["question"],
        answer=result["answer"],
        sources=result["sources"],
        retrieved=result["retrieved"],
    )


@router.get("/rag/ask")
async def kg_rag_ask_get(question: str):
    """GET方式RAG问答（便于浏览器直接测试）"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    if not question or not question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    result = kg_rag_service.answer(question)
    return KGRAGResponse(
        question=result["question"],
        answer=result["answer"],
        sources=result["sources"],
        retrieved=result["retrieved"],
    )


# ========== P2: 中医特色叙事增强接口 ==========

@router.post("/tcm/syndrome-drug", response_model=TCMNarrativeResponse)
async def tcm_syndrome_drug_narrative(request: TCMNarrativeRequest):
    """
    中医证型-用药关联叙事
    输入中医证型名或西医疾病名，分析其用药规律
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    if not request.syndrome_name and not request.western_disease:
        result = tcm_narrative_service.generate_syndrome_drug_narrative()
    else:
        result = tcm_narrative_service.generate_syndrome_drug_narrative(
            syndrome_name=request.syndrome_name,
            western_disease=request.western_disease,
        )
    if "narrative" not in result:
        raise HTTPException(status_code=404, detail="无法生成叙事")

    target = request.syndrome_name or request.western_disease or "全局中医概览"
    return TCMNarrativeResponse(
        narrative=result["narrative"],
        target=target,
        data={k: v for k, v in result.items() if k != "narrative"},
    )


@router.get("/tcm/syndrome-drug")
async def get_tcm_syndrome_drug_narrative(
    syndrome_name: Optional[str] = None,
    western_disease: Optional[str] = None,
):
    """GET方式获取证型用药叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = tcm_narrative_service.generate_syndrome_drug_narrative(
        syndrome_name=syndrome_name,
        western_disease=western_disease,
    )
    if "narrative" not in result:
        raise HTTPException(status_code=404, detail="无法生成叙事")

    target = syndrome_name or western_disease or "全局中医概览"
    return TCMNarrativeResponse(
        narrative=result["narrative"],
        target=target,
        data={k: v for k, v in result.items() if k != "narrative"},
    )


@router.post("/tcm/integrated-comparison", response_model=TCMNarrativeResponse)
async def tcm_integrated_comparison_narrative(request: TCMNarrativeRequest):
    """
    中西医结合对比叙事
    对比中西医结合治疗与纯西医治疗的住院天数等差异
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = tcm_narrative_service.generate_integrated_comparison_narrative(
        western_disease=request.western_disease,
    )
    if "narrative" not in result:
        raise HTTPException(status_code=404, detail="无法生成叙事")

    target = request.western_disease or "全局"
    return TCMNarrativeResponse(
        narrative=result["narrative"],
        target=target,
        data={k: v for k, v in result.items() if k != "narrative"},
    )


@router.get("/tcm/integrated-comparison")
async def get_tcm_integrated_comparison_narrative(western_disease: Optional[str] = None):
    """GET方式获取中西医结合对比叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = tcm_narrative_service.generate_integrated_comparison_narrative(western_disease)
    if "narrative" not in result:
        raise HTTPException(status_code=404, detail="无法生成叙事")

    target = western_disease or "全局"
    return TCMNarrativeResponse(
        narrative=result["narrative"],
        target=target,
        data={k: v for k, v in result.items() if k != "narrative"},
    )


@router.post("/tcm/trend", response_model=TCMNarrativeResponse)
async def tcm_trend_narrative(request: TCMNarrativeRequest):
    """
    证型分布趋势叙事
    分析证型就诊的年度/季度变化趋势
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = tcm_narrative_service.generate_syndrome_trend_narrative(
        syndrome_name=request.syndrome_name,
        western_disease=request.western_disease,
    )
    if "narrative" not in result:
        raise HTTPException(status_code=404, detail="无法生成叙事")

    target = request.syndrome_name or request.western_disease or "全局"
    return TCMNarrativeResponse(
        narrative=result["narrative"],
        target=target,
        data={k: v for k, v in result.items() if k != "narrative"},
    )


@router.get("/tcm/trend")
async def get_tcm_trend_narrative(
    syndrome_name: Optional[str] = None,
    western_disease: Optional[str] = None,
):
    """GET方式获取证型趋势叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = tcm_narrative_service.generate_syndrome_trend_narrative(
        syndrome_name=syndrome_name,
        western_disease=western_disease,
    )
    if "narrative" not in result:
        raise HTTPException(status_code=404, detail="无法生成叙事")

    target = syndrome_name or western_disease or "全局"
    return TCMNarrativeResponse(
        narrative=result["narrative"],
        target=target,
        data={k: v for k, v in result.items() if k != "narrative"},
    )



# ========== P2: 质控异常叙事接口 ==========

@router.post("/quality-control", response_model=QualityControlResponse)
async def quality_control_narrative(request: QualityControlRequest):
    """
    质控异常分析叙事
    基于知识图谱规则自动发现医疗数据中的异常模式
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    valid_types = ["missing_exam", "abnormal_los", "short_readmission",
                   "diagnosis_drug_mismatch", "drug_interaction", "all"]
    if request.rule_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"rule_type必须是以下之一: {valid_types}")

    result = quality_control_service.generate_quality_control_narrative(
        rule_type=request.rule_type,
        disease_name=request.disease_name,
    )

    return QualityControlResponse(
        rule_type=result["rule_type"],
        disease_name=result["disease_name"],
        narrative=result["narrative"],
        summary=result["summary"],
        details=result["details"],
    )


@router.get("/quality-control")
async def get_quality_control_narrative(
    rule_type: str = "all",
    disease_name: Optional[str] = None,
):
    """GET方式获取质控异常叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    valid_types = ["missing_exam", "abnormal_los", "short_readmission",
                   "diagnosis_drug_mismatch", "drug_interaction", "all"]
    if rule_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"rule_type必须是以下之一: {valid_types}")

    result = quality_control_service.generate_quality_control_narrative(
        rule_type=rule_type,
        disease_name=disease_name,
    )

    return QualityControlResponse(
        rule_type=result["rule_type"],
        disease_name=result["disease_name"],
        narrative=result["narrative"],
        summary=result["summary"],
        details=result["details"],
    )


# ========== P2: 科室运营深度叙事接口 ==========

@router.post("/department-operation", response_model=DepartmentOperationResponse)
async def department_operation_narrative(request: DepartmentOperationRequest):
    """
    科室运营深度叙事
    基于知识图谱生成科室运营分析报告，支持多周期对比
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = department_operation_service.generate_operation_narrative(
        period=request.period,
        compare=request.compare,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return DepartmentOperationResponse(
        period=result["period"],
        narrative=result["narrative"],
        current_period=result["current_period"],
        previous_period=result.get("previous_period"),
        current_metrics=result["current_metrics"],
        previous_metrics=result.get("previous_metrics"),
        changes=result["changes"],
    )


@router.get("/department-operation")
async def get_department_operation_narrative(
    period: str = "latest_year",
    compare: bool = True,
):
    """GET方式获取科室运营叙事"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = department_operation_service.generate_operation_narrative(
        period=period,
        compare=compare,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return DepartmentOperationResponse(
        period=result["period"],
        narrative=result["narrative"],
        current_period=result["current_period"],
        previous_period=result.get("previous_period"),
        current_metrics=result["current_metrics"],
        previous_metrics=result.get("previous_metrics"),
        changes=result["changes"],
    )


# ========== P2: 相似患者推荐接口 ==========

@router.post("/similar-patients", response_model=SimilarPatientResponse)
async def find_similar_patients(request: SimilarPatientRequest):
    """
    基于知识图谱共同邻居算法寻找相似患者
    输入患者ID，返回最相似的参考病例
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = similar_patient_service.find_similar_patients(
        patient_id=request.patient_id,
        top_n=request.top_n,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return SimilarPatientResponse(
        patient_id=result["patient_id"],
        narrative=result["narrative"],
        target_profile=result["target_profile"],
        similar_patients=result["similar_patients"],
    )


@router.get("/similar-patients/{patient_id}")
async def get_similar_patients(patient_id: str, top_n: int = 10):
    """GET方式获取相似患者推荐"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = similar_patient_service.find_similar_patients(
        patient_id=patient_id,
        top_n=top_n,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return SimilarPatientResponse(
        patient_id=result["patient_id"],
        narrative=result["narrative"],
        target_profile=result["target_profile"],
        similar_patients=result["similar_patients"],
    )


# ========== P2: 风险预警接口 ==========

@router.post("/risk-prediction", response_model=RiskPredictionResponse)
async def risk_prediction(request: RiskPredictionRequest):
    """
    预测性叙事 / 风险预警
    输入患者ID分析该患者风险；不输入则分析全局高风险患者
    """
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = risk_prediction_service.generate_risk_narrative(
        patient_id=request.patient_id,
        top_n=request.top_n,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return RiskPredictionResponse(
        type=result.get("type", "unknown"),
        narrative=result["narrative"],
        patient_id=result.get("patient_id"),
        risk_level=result.get("risk_level"),
        risk_score=result.get("risk_score"),
        risk_factors=result.get("risk_factors", []),
        high_risk_patients=result.get("high_risk_patients", []),
        score_distribution=result.get("score_distribution", {}),
    )


@router.get("/risk-prediction")
async def get_risk_prediction(patient_id: Optional[str] = None, top_n: int = 20):
    """GET方式获取风险预警"""
    if not neo4j_client.test_connection():
        raise HTTPException(status_code=503, detail="Neo4j连接失败")

    result = risk_prediction_service.generate_risk_narrative(
        patient_id=patient_id,
        top_n=top_n,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return RiskPredictionResponse(
        type=result.get("type", "unknown"),
        narrative=result["narrative"],
        patient_id=result.get("patient_id"),
        risk_level=result.get("risk_level"),
        risk_score=result.get("risk_score"),
        risk_factors=result.get("risk_factors", []),
        high_risk_patients=result.get("high_risk_patients", []),
        score_distribution=result.get("score_distribution", {}),
    )

@router.get("/reports/latest")
async def get_latest_report():
    """获取最近生成的科室运营简报报告ID"""
    recent = json_store.list_recent(limit=100)
    for item in recent:
        data = item["data"]
        # 排除周简报(report_type=weekly)和分析数据(没有report_id)
        if data.get("report_id") and data.get("report_type") != "weekly":
            return {
                "status": "ok",
                "report_id": item["doc_id"],
                "title": data.get("title", ""),
                "generated_at": data.get("generated_at", ""),
            }
    return {"status": "not_found", "report_id": None}


# ========== LLM 缓存管理接口 ==========

from database.llm_cache import llm_cache_store
from fastapi import Query


@router.get("/cache/stats")
async def get_cache_stats():
    """获取LLM缓存统计信息"""
    return {"status": "ok", "stats": llm_cache_store.get_stats()}


@router.get("/cache/namespaces")
async def list_cache_namespaces():
    """列出所有缓存命名空间及其数量"""
    return {"status": "ok", "namespaces": llm_cache_store.list_namespaces()}


@router.get("/cache/list/{namespace}")
async def list_cache_by_namespace(namespace: str):
    """列出指定命名空间的所有缓存元数据"""
    return {"status": "ok", "namespace": namespace, "entries": llm_cache_store.list_by_namespace(namespace)}


@router.post("/cache/clear/{namespace}")
async def clear_cache_namespace(namespace: str):
    """清理指定命名空间的所有缓存"""
    count = llm_cache_store.delete_by_namespace(namespace)
    return {"status": "ok", "deleted": count, "namespace": namespace}


@router.post("/cache/clear-expired")
async def clear_expired_cache():
    """清理所有过期的缓存"""
    count = llm_cache_store.delete_expired()
    return {"status": "ok", "deleted": count}


@router.post("/cache/clear-all")
async def clear_all_cache():
    """清空所有LLM缓存（慎用）"""
    count = llm_cache_store.clear_all()
    return {"status": "ok", "deleted": count}
