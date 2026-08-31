"""科研算子注册表。"""
from services.research.skills.base import BaseSkill
from services.research.skills.overview import dataset_profile_skill, trend_analysis_skill
from services.research.skills.mining import (
    frequent_itemsets_skill, association_rules_skill, similar_items_skill,
    cooccurrence_network_skill, anomaly_detection_skill,
)
from services.research.skills.ml import (
    classification_skill, clustering_skill, dimensionality_reduction_skill,
    feature_importance_skill, regression_skill,
)
from services.research.skills.stats import (
    descriptive_stats_skill, group_comparison_skill, correlation_skill,
)
from services.research.skills.graph import (
    graph_overview_skill, kg_comorbidity_skill, centrality_skill,
)
from services.research.skills.writing import (
    topic_suggestion_skill, literature_search_skill, paper_outline_skill,
    paper_writing_skill, reference_format_skill, paper_review_skill,
)

_ALL_SKILLS: list[BaseSkill] = [
    # 数据概览
    dataset_profile_skill, trend_analysis_skill,
    # 数据挖掘
    frequent_itemsets_skill, association_rules_skill, similar_items_skill,
    cooccurrence_network_skill, anomaly_detection_skill,
    # 机器学习
    classification_skill, clustering_skill, dimensionality_reduction_skill,
    feature_importance_skill, regression_skill,
    # 统计分析
    descriptive_stats_skill, group_comparison_skill, correlation_skill,
    # 图谱挖掘
    graph_overview_skill, kg_comorbidity_skill, centrality_skill,
    # 论文写作
    topic_suggestion_skill, literature_search_skill, paper_outline_skill,
    paper_writing_skill, reference_format_skill, paper_review_skill,
]

SKILL_REGISTRY: dict[str, BaseSkill] = {s.meta.id: s for s in _ALL_SKILLS}


def list_skills_by_category() -> dict[str, list[dict]]:
    """按类别分组返回算子元信息"""
    categories: dict[str, list[dict]] = {}
    for skill in _ALL_SKILLS:
        meta = skill.meta
        categories.setdefault(meta.category, []).append({
            "id": meta.id,
            "name": meta.name,
            "category": meta.category,
            "description": meta.description,
            "params_schema": meta.params_schema,
            "data_requirements": meta.data_requirements,
        })
    return categories


def get_skill(skill_id: str) -> BaseSkill | None:
    return SKILL_REGISTRY.get(skill_id)
