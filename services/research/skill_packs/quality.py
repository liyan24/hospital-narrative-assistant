"""论文生成后质检：确定性数字一致性校验 + skills 校验脚本（lint）调用。

- check_number_consistency：正文数字与算子 facts 比对，列出可疑数字（防幻觉）。
- run_skill_lints：subprocess 调用 scientific-writing / hypothesis-generation
  的离线 lint CLI；脚本缺失或报错时返回空报告，绝不影响主流程。
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from services.research.skill_packs.paths import skill_file

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
# facts 字符串中的科学计数法（如 "2.30e-08"），需优先整体提取，
# 否则会被 _NUM_RE 拆成 "2.30" 和 "08" 两个碎片导致正文 p 值误报
_SCI_IN_STR_RE = re.compile(r"\d+(?:\.\d+)?[eE][+-]?\d+")
# 千分位空格（如 "13 743"、"3 990"，含不间断空格）合并为完整数值
_THOUSAND_SEP_RE = re.compile(r"(?<=\d)[  \u202f](?=\d{3}(?:\D|$))")
# 科学计数法（如 "2.30×10⁻⁸"、"1.5×10-6"、"5.19e-06"），整体作为一个数值处理
_SCI_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[×xX]\s*10\s*([⁻-]?\s*[0-9⁰¹²³⁴⁵⁶⁷⁸⁹]+)|[eE]\s*([+-]?\d+))")
_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")


def _preprocess_text(text: str) -> tuple[str, list[tuple[float, str]]]:
    """合并千分位空格数字；提取科学计数法数值及其所在句子，并从文本中整体剔除
    （避免拆出 '10'、'8' 等碎片误报）。返回 (清洗后文本, [(数值, 句子上下文)])"""
    sci_items = []
    for m in _SCI_RE.finditer(text):
        exp_raw = m.group(2) if m.group(2) is not None else m.group(3)
        exp = exp_raw.replace(" ", "").translate(_SUPERSCRIPT)
        try:
            sci_items.append((float(f"{m.group(1)}e{exp}"), _sentence_of(text, m.start())))
        except ValueError:
            pass
    text = _SCI_RE.sub(" ", text)
    text = _THOUSAND_SEP_RE.sub("", text)
    return text, sci_items


def _sentence_of(text: str, start: int) -> str:
    """提取命中位置所在的完整句子（按中英文句读切分），作为可读上下文"""
    left = max(text.rfind(c, 0, start) for c in "。；;！？!?\n") + 1
    rights = [text.find(c, start) for c in "。；;！？!?\n"]
    rights = [r for r in rights if r >= 0]
    right = min(rights) + 1 if rights else len(text)
    return re.sub(r"\s+", " ", text[left:right]).strip()[:120]


def _flatten_numbers(obj, out: list):
    """递归收集 facts JSON 中的全部数值"""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _flatten_numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _flatten_numbers(v, out)
    elif isinstance(obj, str):
        # 兼容 facts 中字符串化的数字（如 "23.4%"、"2.30e-08"）
        for m in _SCI_IN_STR_RE.finditer(obj):
            out.append(float(m.group()))
        cleaned = _SCI_IN_STR_RE.sub(" ", obj)
        for m in _NUM_RE.finditer(cleaned):
            out.append(float(m.group()))


def _matches(value: float, facts_numbers: list[float], decimals: int) -> bool:
    """文本数值是否与 facts 中某数值吻合（考虑百分制换算与文本精度舍入）"""
    for fv in facts_numbers:
        for candidate in (fv, fv * 100, fv / 100):
            if round(candidate, decimals) == value:
                return True
            # 极小数值（p 值等）按相对容差比对，避免科学计数法精度误报
            if abs(candidate) < 0.01 and abs(candidate - value) <= 0.05 * max(abs(value), 1e-12):
                return True
    return False


def check_number_consistency(sections: dict, facts: list | dict) -> dict:
    """比对论文章节正文中的数字与 facts，返回可疑数字清单（提示性，需人工核对）

    预处理千分位空格与科学计数法，按句子给出上下文，同一章节同一数值只报一次。
    """
    facts_numbers: list[float] = []
    _flatten_numbers(facts, facts_numbers)

    suspicious = []
    seen = set()
    for sec, content in (sections or {}).items():
        if not isinstance(content, str):
            continue
        text, sci_items = _preprocess_text(content)
        # 科学计数法数值（p 值等）整体比对
        for v, sci_ctx in sci_items:
            if not _matches(v, facts_numbers, 12):
                key = (sec, f"{v:.2e}")
                if key not in seen:
                    seen.add(key)
                    suspicious.append({
                        "section": sec,
                        "value": f"{v:.2e}",
                        "context": sci_ctx,
                    })
        for m in _NUM_RE.finditer(text):
            token = m.group()
            value = float(token)
            decimals = len(token.split(".")[1]) if "." in token else 0
            # 过滤结构性数字：小整数（小标题、关键词个数等）、年份、
            # 章节编号（如 3.1、2.4）、阈值条件（如 ≥65 岁）
            if "." not in token and (value < 10 or 1900 <= value <= 2100):
                continue
            if re.fullmatch(r"\d\.\d", token):
                continue
            prev = text[:m.start()].rstrip()
            if prev and prev[-1] in "≥><＞＜":
                continue
            if _matches(value, facts_numbers, decimals):
                continue
            if (sec, token) in seen:
                continue
            seen.add((sec, token))
            suspicious.append({
                "section": sec,
                "value": token,
                "context": _sentence_of(text, m.start()),
            })
            if len(suspicious) >= 50:
                break

    return {
        "facts_number_count": len(facts_numbers),
        "suspicious_numbers": suspicious,
        "note": "正文数字与算子 facts 自动比对结果，仅作提示，需人工核对后修订。",
    }


def _run_lint(script: Path, manuscript: Path, timeout: int = 30) -> dict | None:
    """调用单个 lint CLI，解析其 stdout 的 JSON 报告；失败返回 None"""
    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(manuscript)],
            cwd=str(script.parent),  # 脚本依赖同目录 _common 模块
            capture_output=True, text=True, timeout=timeout,
        )
        out = (proc.stdout or "").strip()
        if not out:
            return None
        # lint 发现问题时会以非零码退出，stdout 仍为 JSON 报告，属正常情况
        start = out.find("{")
        if start < 0:
            return None
        return json.loads(out[start:])
    except Exception:
        return None


# 与论文内容无关的基础设施类告警码（清单/门禁/流程类）直接过滤
_LINT_SKIP_TOKENS = ("CONFIDENTIALITY_GATE", "MANIFEST", "GATE_NOT_CHECKED",
                     "INTAKE", "AUTHORSWIP", "APPROVAL")
# 常见规则码 → 中文说明（lint 脚本的英文 message 对中文论文不可读，统一替换）
_LINT_CODE_CN = {
    "PLACEHOLDER": "存在未解决的占位符或 TODO 标记，需补全",
    "OVERSTATEMENT": "疑似夸大表述，需人工确认措辞",
    "CAUSAL": "疑似因果表述（观察性研究应使用关联性表述），需人工确认",
    "SENSITIVE": "疑似包含敏感信息，需人工核查",
    "DECLARATION": "涉及伦理/数据可用性声明，需人工核实",
    "UNVERIFIED": "存在未绑定证据的声明，需人工核实",
    "MISSING": "存在缺失项，需人工补全",
}


def _lint_message_cn(code: str, fallback: str) -> str:
    upper = (code or "").upper()
    for key, cn in _LINT_CODE_CN.items():
        if key in upper:
            return cn
    return code or fallback


def _is_lint_skipped(code: str) -> bool:
    upper = (code or "").upper()
    return any(tok in upper for tok in _LINT_SKIP_TOKENS) or not upper


def run_skill_lints(sections: dict, references: str = "") -> dict:
    """对生成的论文正文运行 skills 离线 lint 脚本，返回合并后的警告清单"""
    manuscript = "\n\n".join(
        f"## {sec}\n\n{content}" for sec, content in (sections or {}).items()
    )
    if references:
        manuscript += f"\n\n## 参考文献\n\n{references}"
    if not manuscript.strip():
        return {"lints": [], "available": False}

    scripts = [
        ("scientific-writing", skill_file("scientific-writing", "scripts", "lint_manuscript.py")),
        ("hypothesis-generation", skill_file("hypothesis-generation", "scripts", "lint_causal_claims.py")),
    ]

    lints = []
    ran_any = False
    with tempfile.TemporaryDirectory(prefix="paper_lint_") as tmp:
        md_path = Path(tmp) / "manuscript.md"
        md_path.write_text(manuscript, encoding="utf-8")
        for skill_name, script in scripts:
            if script is None:
                continue
            report = _run_lint(script, md_path)
            if report is None:
                continue
            ran_any = True
            issues = report.get("issues") or report.get("violations") or []
            for it in issues[:20]:
                if isinstance(it, dict):
                    code = it.get("code", it.get("rule", ""))
                    if _is_lint_skipped(code):
                        continue
                    lints.append({
                        "skill": skill_name,
                        "tool": report.get("tool", ""),
                        "severity": it.get("severity", "warning"),
                        "code": code,
                        "location": it.get("location", it.get("line", "")),
                        "message": _lint_message_cn(code, it.get("message", it.get("detail", ""))),
                    })

    return {"lints": lints, "available": ran_any}
