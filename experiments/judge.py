"""LLM-as-Judge：按 4 个维度对叙事文本打 1-5 分。

维度：coherence（连贯性）、coverage（信息覆盖）、readability（可读性）、
clinical_usefulness（临床有用性）。
要求模型输出 JSON：{dimension: {"score": int, "reason": str}}；
解析失败重试一次，仍失败记 None。
"""

import json
import re
from typing import Any, Callable, Dict, Optional

import experiments  # noqa: F401  确保 sys.path 就绪
from experiments import exp_config

ChatFn = Callable[..., str]

JUDGE_SYSTEM = (
    "你是一名严格、客观的医学叙事质量评测专家。请只依据给出的评分细则，"
    "对医疗叙事文本按以下 4 个维度分别打 1-5 分（整数）：\n"
    "1. coherence（连贯性）：1=支离破碎，逻辑混乱，只是事实的堆砌；"
    "3=基本连贯，偶有跳跃，段落间缺少过渡；"
    "5=行文流畅，时间与逻辑线索清晰，段落组织合理。\n"
    "2. coverage（信息覆盖）：1=遗漏绝大多数关键信息；3=覆盖部分关键信息；"
    "5=关键诊断、治疗、检查等信息覆盖完整。\n"
    "3. readability（可读性）：1=难以阅读；3=可读但表达平庸；"
    "5=语言专业、简洁、有条理。\n"
    "4. clinical_usefulness（临床有用性）：1=对临床工作无参考价值；"
    "3=有一定参考意义；5=可直接用于科室汇报或病例讨论。\n"
    "评分注意事项：\n"
    "A. 文中形如 [F1]、[F2,F3] 的方括号标记是事实来源标注，属于正常的溯源格式，"
    "请完全忽略它们，不得因此扣 readability 等任何维度的分；\n"
    "B. 按信息质量而非篇幅评分：简洁但信息完整的叙事不应低于冗长叙事，"
    "篇幅长短本身不构成加分或扣分理由；\n"
    "C. 严格对照各维度 1/3/5 分的锚点描述打分，不要凭整体印象给分。\n"
    "只输出如下格式的 JSON，不要输出任何其他文字：\n"
    '{"coherence": {"score": 1-5, "reason": "一句话理由"}, '
    '"coverage": {"score": 1-5, "reason": "..."}, '
    '"readability": {"score": 1-5, "reason": "..."}, '
    '"clinical_usefulness": {"score": 1-5, "reason": "..."}}'
)


def _default_chat(messages, temperature, max_tokens, cache_namespace):
    """默认 LLM 调用（惰性 import，便于测试时注入假的 chat_fn）"""
    from services.llm_service import llm_service
    return llm_service.chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        cache_namespace=cache_namespace,
        cache_metadata={"experiment": True},
    )


def parse_scores_json(raw: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """解析评测器输出的 JSON。

    成功返回 {dimension: {"score": int|None, "reason": str}}（4 个维度齐全，
    单个维度非法时该维度 score 记 None）；整体解析失败返回 None。

    三级容错：
    1. 直接/去代码块后 json.loads；
    2. 截取首个 { 到末个 } 再 json.loads；
    3. 正则修复：模型偶发在 score 值里混入乱码 token（如 "score":һ3），
       此时按维度名定位，抓取 "score": 之后的第一个 1-5 数字。
    """
    if not raw or not raw.strip():
        return None

    candidates = [raw.strip()]
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        candidates.append(m.group(1))
    start = raw.find("{")
    end = raw.rfind("}")
    if 0 <= start < end:
        candidates.append(raw[start:end + 1])

    obj = None
    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            obj = parsed
            break
    if obj is None:
        # 第 3 级：正则修复乱码 score 值
        scores: Dict[str, Dict[str, Any]] = {}
        found = 0
        for dim in exp_config.JUDGE_DIMENSIONS:
            dm = re.search(
                re.escape(dim) + r'"?\s*:\s*\{[^{}]*?"score"\s*:\s*[^\d]{0,10}([1-5])',
                raw, re.DOTALL)
            if dm:
                scores[dim] = {"score": int(dm.group(1)), "reason": ""}
                found += 1
            else:
                scores[dim] = {"score": None, "reason": ""}
        return scores if found == len(exp_config.JUDGE_DIMENSIONS) else None

    scores = {}
    for dim in exp_config.JUDGE_DIMENSIONS:
        entry = obj.get(dim)
        score, reason = None, ""
        if isinstance(entry, dict):
            raw_score = entry.get("score")
            try:
                raw_score = int(raw_score)
                if 1 <= raw_score <= 5:
                    score = raw_score
            except (TypeError, ValueError):
                pass
            reason = str(entry.get("reason", ""))
        scores[dim] = {"score": score, "reason": reason}
    return scores


def score_narrative(
    text: str,
    task_prompt: str = "",
    chat_fn: Optional[ChatFn] = None,
    *,
    cache_namespace: str = "exp:judge",
) -> Optional[Dict[str, Dict[str, Any]]]:
    """对一条叙事打分；解析失败重试一次，仍失败返回 None。"""
    chat_fn = chat_fn or _default_chat
    if not text or not text.strip():
        return None

    user_content = f"【写作要求】\n{task_prompt}\n\n【叙事文本】\n{text}" if task_prompt else text

    for attempt in range(2):  # 首次 + 重试一次
        if attempt == 1:
            user_content += "\n\n（请严格只输出 JSON，不要输出任何其他文字。）"
        raw = chat_fn(
            [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            temperature=exp_config.JUDGE_TEMPERATURE,
            max_tokens=exp_config.JUDGE_MAX_TOKENS,
            cache_namespace=cache_namespace,
        )
        if isinstance(raw, str) and raw.startswith("[LLM调用失败]"):
            return None  # LLM 不可用，重试无意义
        scores = parse_scores_json(raw)
        if scores is not None:
            return scores
    return None
