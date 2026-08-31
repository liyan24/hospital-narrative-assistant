"""断言核查：把抽取的断言与任务 ground truth 事实比对，输出标签与任务级指标。

每条断言标签 ∈ {supported, contradicted, unverifiable}：
- supported：断言与某条事实匹配（字符串客体被提及；或数值在容差内且事实上下文被提及）；
- contradicted：保守判定——唯一数值型事实上下文匹配但数值超容差，
  或断言给出同一 (subject, predicate) 下的其他客体；
- unverifiable：无法与任何事实建立对应。

候选事实：事实的 subject 或 object 被断言提及（归一化后出现在 entities 或断言文本中）。
"提及"判断前先做日期归一化（2020年12月31日 / 2020/12/31 / 2020.12.31 → 2020-12-31）。

任务级指标：
- grounding_rate = supported / total（断言有据率，主指标）
- fact_accuracy = supported / (supported + contradicted)
- hallucination_rate = contradicted / total
- unsupported_rate = unverifiable / total

本模块全部为纯函数，不依赖 Neo4j / LLM，可直接单测。
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional

from experiments import exp_config

LABELS = ("supported", "contradicted", "unverifiable")


# ==================== 归一化与数值工具 ====================

_DATE_PATTERNS = [
    # 2020年12月31日 / 2020年1月2号
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?"),
    # 2020/12/31 或 2020.12.31
    re.compile(r"(\d{4})\s*[/\.]\s*(\d{1,2})\s*[/\.]\s*(\d{1,2})"),
]

_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def normalize_dates(text: Any) -> str:
    """把中文/斜杠/点号日期统一为 ISO 格式 YYYY-MM-DD（其余内容不变）"""
    if text is None:
        return ""
    s = str(text)
    for pat in _DATE_PATTERNS:
        s = pat.sub(lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", s)
    return s


def normalize_entity(s: Any, aliases: Optional[Dict[str, str]] = None) -> str:
    """实体归一化：日期归一化 → NFKC（全半角统一）→ 去空白 → 小写 → 别名映射。

    aliases 的 key 与 value 都应先经过本函数归一化（见 build_alias_map）。
    """
    if s is None:
        return ""
    text = normalize_dates(s)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", "", text).strip().lower()
    if aliases and text in aliases:
        text = aliases[text]
    return text


def build_alias_map(alias_pairs: Dict[str, str]) -> Dict[str, str]:
    """构建归一化后的别名映射：{归一化别名: 归一化标准名}"""
    return {normalize_entity(k): normalize_entity(v) for k, v in alias_pairs.items()}


def numbers_close(a: float, b: float, rel_tol: float = exp_config.NUMERIC_REL_TOL,
                  abs_tol: float = exp_config.NUMERIC_ABS_TOL) -> bool:
    """数值容差匹配：|a-b| <= max(abs_tol, rel_tol * max(|a|, |b|))"""
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def claim_number(claim: Dict[str, Any]) -> Optional[float]:
    """取断言的数值：优先 value 字段，否则取断言文本中的第一个数字（跳过日期）"""
    value = claim.get("value")
    if value is not None:
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    text = normalize_dates(claim.get("claim", ""))
    text = _ISO_DATE_RE.sub(" ", text)  # 去掉日期，避免把 2020 当成数值
    m = _NUMBER_RE.search(text)
    return float(m.group(0)) if m else None


# ==================== 单条断言核查 ====================

def _is_numeric(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _context_key(fact: Dict[str, Any], aliases: Optional[Dict[str, str]]) -> tuple:
    """数值事实的上下文唯一性键：优先 qualifiers 里的 item/label，否则用 subject"""
    quals = fact.get("qualifiers") or {}
    marker = quals.get("item") or quals.get("label")
    if marker:
        return (fact.get("predicate"), normalize_entity(marker, aliases))
    return (fact.get("predicate"), normalize_entity(fact.get("subject"), aliases))


def verify_claim(
    claim: Dict[str, Any],
    facts: List[Dict[str, Any]],
    *,
    rel_tol: float = exp_config.NUMERIC_REL_TOL,
    abs_tol: float = exp_config.NUMERIC_ABS_TOL,
    aliases: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """核查单条断言，返回 {"label": ..., "matched_fact": ...}。

    匹配规则：
    1. 候选事实：subject 或 object 被断言提及（数值型事实的"提及"指其上下文——
       subject 或 qualifiers 中的字符串值——被提及）；
    2. supported：字符串客体被提及；或数值客体在容差内且上下文被提及；
    3. contradicted（保守）：(a) 强上下文且唯一的数值型事实数值超容差；
       (b) 断言给出同一 (subject, predicate) 下的其他客体；
    4. 其余 → unverifiable。宁可多判 unverifiable，不误判 contradicted。
    """
    text_n = normalize_entity(claim.get("claim", ""), aliases)
    ents_n = {normalize_entity(e, aliases) for e in (claim.get("entities") or [])}
    ents_n.discard("")

    def mentioned(val: Any) -> bool:
        n = normalize_entity(val, aliases)
        if not n:
            return False
        if n in ents_n or n in text_n:
            return True
        # 复合名称部分匹配：断言实体是事实值的子串（≥2字），
        # 如 "骨疽病" ⊆ "骨疽病，气血瘀阻证"、"血红蛋白" ⊆ "血红蛋白测定"
        return any(len(e) >= 2 and e in n for e in ents_n)

    def context_strength(f: Dict[str, Any]) -> int:
        """数值事实的上下文强度：0=未提及，1=弱（通用短别名），2=强。

        强上下文：subject 被提及，或非 item 的字符串 qualifier（label/日期等）被提及，
        或 item  qualifier 为具体名称（归一化后 ≥3 字，如 "血红蛋白"）。
        弱上下文：item 为通用短别名（如 "住院"）——足以判 supported，
        但不足以判 contradicted（避免 "住院期间…1次" 误伤住院天数事实）。
        """
        if mentioned(f.get("subject")):
            return 2
        quals = f.get("qualifiers") or {}
        for k, v in quals.items():
            if k in ("unit", "item") or not isinstance(v, str):
                continue
            if mentioned(v):
                return 2
        item = quals.get("item")
        if isinstance(item, str) and mentioned(item):
            return 2 if len(normalize_entity(item, aliases)) >= 3 else 1
        return 0

    def context_mentioned(f: Dict[str, Any]) -> bool:
        return context_strength(f) >= 1

    num = claim_number(claim)

    # 1. 候选事实
    candidates = []
    for f in facts:
        obj = f.get("object")
        if mentioned(f.get("subject")):
            candidates.append(f)
        elif _is_numeric(obj):
            if context_mentioned(f):
                candidates.append(f)
        elif mentioned(obj):
            candidates.append(f)

    if not candidates:
        return {"label": "unverifiable", "matched_fact": None}

    # 2. supported
    for f in candidates:
        obj = f.get("object")
        if _is_numeric(obj):
            if num is not None and context_mentioned(f) \
                    and numbers_close(num, float(obj), rel_tol, abs_tol):
                return {"label": "supported", "matched_fact": f}
        elif mentioned(obj):
            return {"label": "supported", "matched_fact": f}

    # 3a. contradicted：强上下文且唯一的数值型事实，数值超容差
    if num is not None:
        for f in candidates:
            obj = f.get("object")
            if not _is_numeric(obj) or context_strength(f) < 2:
                continue
            if numbers_close(num, float(obj), rel_tol, abs_tol):
                continue
            key = _context_key(f, aliases)
            same_ctx = [g for g in facts
                        if _is_numeric(g.get("object")) and _context_key(g, aliases) == key]
            if len(same_ctx) == 1:
                return {"label": "contradicted", "matched_fact": f}

    # 3b. contradicted：断言给出同一 (subject, predicate) 下的其他客体
    subj_hits = [f for f in candidates if mentioned(f.get("subject"))]
    for f in subj_hits:
        same_pred_objs = {
            normalize_entity(g.get("object"), aliases)
            for g in facts
            if g.get("subject") == f.get("subject")
            and g.get("predicate") == f.get("predicate")
        }
        fact_obj_n = normalize_entity(f.get("object"), aliases)
        for e in ents_n:
            if e in same_pred_objs and e != fact_obj_n:
                # 断言提到了同谓词下的另一个客体，且不是本条事实的客体
                # （若断言同时提到正确客体，第 2 步已判 supported）
                return {"label": "contradicted", "matched_fact": f}

    # 4. 候选存在但既不支持也不冲突
    return {"label": "unverifiable", "matched_fact": None}


def verify_claims(
    claims: List[Dict[str, Any]],
    facts: List[Dict[str, Any]],
    **kwargs,
) -> List[Dict[str, Any]]:
    """核查断言列表，返回带标签的 verdict 列表"""
    verdicts = []
    for c in claims:
        v = verify_claim(c, facts, **kwargs)
        verdicts.append({"claim": c, **v})
    return verdicts


# ==================== 任务级指标 ====================

def compute_metrics(verdicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """由 verdict 列表计算任务级指标（纯函数）。

    fact_accuracy 分母为 0 时返回 None（该任务无 supported/contradicted 断言）。
    """
    counts = {label: 0 for label in LABELS}
    for v in verdicts:
        label = v.get("label")
        if label in counts:
            counts[label] += 1

    total = len(verdicts)
    supported = counts["supported"]
    contradicted = counts["contradicted"]
    unverifiable = counts["unverifiable"]

    denom = supported + contradicted
    return {
        "total": total,
        "supported": supported,
        "contradicted": contradicted,
        "unverifiable": unverifiable,
        "grounding_rate": (supported / total) if total > 0 else None,
        "fact_accuracy": (supported / denom) if denom > 0 else None,
        "hallucination_rate": (contradicted / total) if total > 0 else None,
        "unsupported_rate": (unverifiable / total) if total > 0 else None,
    }
