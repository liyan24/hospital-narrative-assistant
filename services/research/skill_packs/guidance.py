"""写作规范注入：提炼 scientific-writing / scientific-critical-thinking / peer-review
等 skill 的核心规范为中文 prompt 规范块，注入论文生成各阶段的 LLM 调用。

规范常量为本模块内置（提炼自对应 SKILL.md）；.agents 目录缺失不影响使用。
"""
from functools import lru_cache

# 提炼自 scientific-writing SKILL.md（证据绑定 / 不得编造 / 科学保真）
_WRITING_RULES = """【写作铁律（必须遵守）】
1. 证据绑定：论文中每一个数字、比例、统计量都必须能在给定的"分析结果事实"中找到，禁止使用任何未提供的数值；确需提及但无数据时，明确写"数据未收集/未测量"，不得用估计值冒充。
2. 不得编造：不得虚构文献、DOI、PMID、样本量、伦理批件号、软件版本或研究流程细节。
3. 区分关联与因果：本研究为回顾性观察性研究，只能表述"相关/关联/提示"，禁止"导致/证明/显著改善"等因果或决定性表述（统计学显著性除外，且须有对应检验结果支持）。
4. 保留不确定性：区分描述性结果与探索性发现；阴性/不显著结果也应如实报告。
5. 局限性具体化：讨论中必须给出本数据的具体局限（单中心、回顾性、检验覆盖率约两成、无性别字段、残余混杂等），禁止空泛套话。"""

# 提炼自 scientific-critical-thinking references（偏倚 / 混杂 / 证据分级）
_CRITICAL_CHECKLIST = """【方法学自查清单（讨论与局限性中逐项回应）】
1. 混杂：哪些基线差异可能解释观察到的关联？是否做了分层/校正？
2. 选择偏倚：纳入排除标准是否可能使样本不能代表目标人群？
3. 信息偏倚：检验覆盖率约两成，缺失检验数据的患者是否系统性不同？
4. 多重比较：同时检验多个指标时，显著结果是否为偶然？应提示谨慎解释。
5. 证据等级：本研究为单中心回顾性观察性证据（GRADE 低-中等级），外推到其他医院需谨慎。"""

# 提炼自 peer-review / scholar-evaluation 的评审维度
_REVIEW_DIMENSIONS = """【评审维度】请从以下四个维度各打 1-10 分并指出最具体的问题（引用原文位置）：
1. 创新性：选题与发现在该领域中的增量贡献。
2. 方法学严谨性：纳入排除、变量定义、统计方法与结果是否一致；是否有混杂/偏倚说明。
3. 结果呈现：正文数字与分析结果事实是否一致；表X/图X 标注是否规范；有无无中生有的数据。
4. 写作质量：IMRaD 结构完整性、逻辑衔接、学术语言、局限性是否具体。"""


@lru_cache(maxsize=None)
def writing_rules() -> str:
    """论文写作铁律规范块（注入大纲与分章写作 prompt）"""
    return _WRITING_RULES


@lru_cache(maxsize=None)
def critical_checklist() -> str:
    """方法学批判性自查清单（注入讨论章节 prompt）"""
    return _CRITICAL_CHECKLIST


@lru_cache(maxsize=None)
def review_dimensions() -> str:
    """结构化自评审维度（注入评审 prompt）"""
    return _REVIEW_DIMENSIONS
