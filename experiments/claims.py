"""LLM 断言抽取：从叙事文本中抽取原子事实断言。

输出 JSON 列表：[{"claim": str, "type": "numeric|relation|temporal|other",
"entities": [...], "value": number|null}]

JSON 解析尽量健壮：先 json.loads，失败则提取 ```json 代码块或第一个 [...] 片段；
解析失败重试一次（跳过缓存），再失败返回空列表并标记 parse_error。
"""

import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

import experiments  # noqa: F401  确保 sys.path 就绪
from experiments import exp_config

ChatFn = Callable[..., str]

EXTRACTION_SYSTEM = (
    "你是一名医学文本事实抽取器。请从给定的中文医疗叙事文本中抽取原子事实断言，"
    "每条断言只包含一个可核查的事实。输出严格的 JSON 数组，每个元素格式为：\n"
    '{"claim": "断言的原文或简述", "type": "numeric|relation|temporal|other", '
    '"entities": ["涉及的实体名，如疾病名、药品名、患者ID、日期"], "value": 数值或null}\n'
    "要求：\n"
    "1. type=numeric 时 value 必须填断言中的数值（如人数、次数、天数、百分比）；\n"
    "2. entities 尽量使用文本中出现的原始名称；\n"
    "3. 只输出 JSON 数组，不要输出任何其他文字。"
)


def _default_chat(messages, temperature, max_tokens, cache_namespace, use_cache=True):
    """默认 LLM 调用（惰性 import，便于测试时注入假的 chat_fn）"""
    from services.llm_service import llm_service
    return llm_service.chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        cache_namespace=cache_namespace,
        use_cache=use_cache,
        cache_metadata={"experiment": True},
    )


def _normalize_claim(item: Any) -> Optional[Dict[str, Any]]:
    """校验并规整单条断言；不合法返回 None"""
    if not isinstance(item, dict):
        return None
    claim_text = item.get("claim")
    if not isinstance(claim_text, str) or not claim_text.strip():
        return None
    claim_type = item.get("type")
    if claim_type not in ("numeric", "relation", "temporal", "other"):
        claim_type = "other"
    entities = item.get("entities")
    if not isinstance(entities, list):
        entities = []
    entities = [str(e) for e in entities if e is not None and str(e).strip()]
    value = item.get("value")
    if value is not None:
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = None
    return {"claim": claim_text.strip(), "type": claim_type,
            "entities": entities, "value": value}


def parse_claims_json(raw: str) -> Tuple[List[Dict[str, Any]], bool]:
    """解析 LLM 输出的断言 JSON。

    返回 (断言列表, 是否解析失败)。解析策略：
    1. 直接 json.loads（兼容 {"claims": [...]} 包装）；
    2. 正则提取 ```json ... ``` 代码块；
    3. 提取文本中第一个 [...] 片段；
    4. 全部失败返回 ([], True)。
    """
    if not raw or not raw.strip():
        return [], True

    candidates = [raw.strip()]
    # ```json 代码块
    m = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        candidates.append(m.group(1))
    # 第一个 [...] 片段（取最外层方括号范围）
    start = raw.find("[")
    end = raw.rfind("]")
    if 0 <= start < end:
        candidates.append(raw[start:end + 1])

    for cand in candidates:
        try:
            obj = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict) and isinstance(obj.get("claims"), list):
            obj = obj["claims"]
        if not isinstance(obj, list):
            continue
        claims = [c for c in (_normalize_claim(x) for x in obj) if c is not None]
        return claims, False

    return [], True


def extract_claims(
    text: str,
    chat_fn: Optional[ChatFn] = None,
    *,
    cache_namespace: str = "exp:claims",
) -> Dict[str, Any]:
    """对一条叙事文本抽取断言。

    返回 {"claims": [...], "parse_error": bool, "error": str|None}
    """
    chat_fn = chat_fn or _default_chat
    if not text or not text.strip():
        return {"claims": [], "parse_error": False, "error": "empty_text"}

    raw = None
    claims: List[Dict[str, Any]] = []
    parse_error = True
    for attempt in range(2):  # 解析失败重试一次，重试时跳过缓存（缓存里是同一份坏输出）
        raw = chat_fn(
            [
                {"role": "system", "content": EXTRACTION_SYSTEM},
                {"role": "user", "content": f"请抽取以下叙事文本中的原子事实断言：\n\n{text}"},
            ],
            temperature=exp_config.CLAIMS_TEMPERATURE,
            max_tokens=exp_config.CLAIMS_MAX_TOKENS,
            cache_namespace=cache_namespace,
            use_cache=(attempt == 0),
        )
        if isinstance(raw, str) and raw.startswith("[LLM调用失败]"):
            return {"claims": [], "parse_error": False, "error": raw}
        claims, parse_error = parse_claims_json(raw)
        if not parse_error:
            break
    return {"claims": claims, "parse_error": parse_error, "error": None}
