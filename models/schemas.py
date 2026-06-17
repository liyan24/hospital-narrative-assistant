from pydantic import BaseModel
from typing import Optional, Any


class NarrativeRequest(BaseModel):
    department: str
    patient_id: Optional[str] = None
    date_range: Optional[str] = None
    additional_context: Optional[str] = None


class NarrativeResponse(BaseModel):
    narrative: str
    sources: list[str] = []


class DocumentExportRequest(BaseModel):
    narrative_id: str
    format: str = "docx"  # docx or pdf
    template: Optional[str] = None


class DocumentExportResponse(BaseModel):
    file_path: str
    download_url: str


class QueryRequest(BaseModel):
    collection: Optional[str] = "default"
    query: str
    top_k: int = 5


class HealthResponse(BaseModel):
    mysql: bool = False
    neo4j: bool = False
    vector_db: bool = False
    llm: bool = False


class PatientNarrativeRequest(BaseModel):
    patient_id: str


class PatientNarrativeResponse(BaseModel):
    patient_id: str
    visit_count: int
    narrative: str
    patient: Optional[dict] = None
    timeline: Optional[dict] = None


class PathwayNarrativeRequest(BaseModel):
    disease_name: str


class PathwayNarrativeResponse(BaseModel):
    disease_name: str
    narrative: str


class ComorbidityRequest(BaseModel):
    disease_name: Optional[str] = None


class ComorbidityResponse(BaseModel):
    target_disease: Optional[str]
    narrative: str


class DrugPatternRequest(BaseModel):
    disease_name: Optional[str] = None


class DrugPatternResponse(BaseModel):
    disease_name: Optional[str]
    narrative: str


class ReadmissionResponse(BaseModel):
    narrative: str
    stats: Optional[dict] = None


# ========== RAG 问答 Schema ==========


class KGRAGRequest(BaseModel):
    question: str


class KGRAGResponse(BaseModel):
    question: str
    answer: str
    sources: list[str] = []
    retrieved: dict = {}


# ========== 图谱可视化 Schema ==========


class KGVisualNode(BaseModel):
    id: int
    label: str
    name: str
    category: str
    symbolSize: int


class KGVisualLink(BaseModel):
    source: int
    target: int
    relation: str
    name: str


class KGVisualResponse(BaseModel):
    title: str
    nodes: list[dict]
    links: list[dict]
    stats: dict
    categories: list[dict]


# ========== 中医特色叙事 Schema ==========


class TCMNarrativeRequest(BaseModel):
    syndrome_name: Optional[str] = None
    western_disease: Optional[str] = None


class TCMNarrativeResponse(BaseModel):
    narrative: str
    target: Optional[str] = None
    data: dict = {}


# ========== 质控异常 Schema ==========


class QualityControlRequest(BaseModel):
    rule_type: Optional[str] = "all"
    disease_name: Optional[str] = None


class QualityControlResponse(BaseModel):
    rule_type: str
    disease_name: Optional[str]
    narrative: str
    summary: dict
    details: dict


# ========== 科室运营深度叙事 Schema ==========


class DepartmentOperationRequest(BaseModel):
    period: Optional[str] = "latest_year"
    compare: bool = True


class DepartmentOperationResponse(BaseModel):
    period: str
    narrative: str
    current_period: dict
    previous_period: Optional[dict]
    current_metrics: dict
    previous_metrics: Optional[dict]
    changes: dict


# ========== 相似患者推荐 Schema ==========


class SimilarPatientRequest(BaseModel):
    patient_id: str
    top_n: int = 10


class SimilarPatientResponse(BaseModel):
    patient_id: str
    narrative: str
    target_profile: dict
    similar_patients: list[dict]


# ========== 风险预警 Schema ==========


class RiskPredictionRequest(BaseModel):
    patient_id: Optional[str] = None
    top_n: int = 20


class RiskPredictionResponse(BaseModel):
    type: str
    narrative: str
    patient_id: Optional[str]
    risk_level: Optional[str]
    risk_score: Optional[int]
    risk_factors: list[str] = []
    high_risk_patients: list[dict] = []
    score_distribution: dict = {}
