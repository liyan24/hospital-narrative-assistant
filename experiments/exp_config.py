"""实验配置：输出目录、采样数、随机种子、LLM 参数、缓存命名空间等。"""

import os
from pathlib import Path

# 项目根目录与实验输出目录
# 可用环境变量 EXP_OUTPUT_DIR 覆盖（消融实验隔离输出用，如 experiments/output_ablation_A1）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path(os.environ["EXP_OUTPUT_DIR"]) if os.environ.get("EXP_OUTPUT_DIR") \
    else Path(__file__).resolve().parent / "output"

# 场景与方法
SCENARIOS = [
    "patient_storyline",   # 患者故事线
    "treatment_pathway",   # 诊疗路径
    "comorbidity",         # 合并症分析
    "drug_pattern",        # 用药模式
    "morning_briefing",    # 晨会简报
]

METHODS = [
    "B1_direct",       # 直接 LLM（表格化数据摘要，无图谱约束）
    "B2_vector_rag",   # 向量 RAG
    "B3_kg_grounded",  # 本文方法：KG-grounded 事实约束生成
    "B4_template",     # 规则模板（下界参照）
]

# 采样
DEFAULT_SAMPLES_PER_SCENARIO = 20
DEFAULT_SEED = 42

# LLM 参数
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 2000
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 1500
CLAIMS_TEMPERATURE = 0.0
CLAIMS_MAX_TOKENS = 4000  # 推理模型的思考 token 共享额度，断言抽取给足预算防截断

# LLM 缓存命名空间前缀
CACHE_NS_PREFIX = "exp"

# 断言核查的数值容差
NUMERIC_REL_TOL = 0.05
NUMERIC_ABS_TOL = 1e-6

# LLM-as-Judge 评分维度
JUDGE_DIMENSIONS = [
    "coherence",            # 连贯性
    "coverage",             # 信息覆盖
    "readability",          # 可读性
    "clinical_usefulness",  # 临床有用性
]

# 中间结果文件
FILE_TASKS = "tasks.jsonl"
FILE_GENERATIONS = "generations.jsonl"
FILE_CLAIMS = "claims.jsonl"
FILE_VERDICTS = "verdicts.jsonl"
FILE_SCORES = "scores.jsonl"
FILE_RESULTS_CSV = "results_summary.csv"
FILE_WILCOXON_CSV = "wilcoxon_B1_vs_B3.csv"


def cache_namespace(method: str, scenario: str) -> str:
    """实验 LLM 调用的缓存命名空间：exp:{method}:{scenario}"""
    return f"{CACHE_NS_PREFIX}:{method}:{scenario}"


def output_path(filename: str) -> Path:
    """实验输出文件路径（自动创建输出目录）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR / filename
