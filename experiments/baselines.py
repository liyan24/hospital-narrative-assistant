"""4 个基线/本文方法的叙事生成器，统一接口 generate(task) -> dict。

返回 dict 字段：task_id, scenario, method, text, latency_s, error,
degraded（B2 降级标记，可选）。

所有 LLM 调用走 services.llm_service.llm_service.chat，
cache_namespace 格式为 "exp:{method}:{scenario}"。
"""

import time
from typing import Any, Callable, Dict, List, Optional

import experiments  # noqa: F401  确保 sys.path 就绪
from experiments import exp_config
from experiments.tasks import Task

ChatFn = Callable[..., str]


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


def _run_timed(fn) -> Dict[str, Any]:
    """执行生成并计时，返回统一结果结构"""
    start = time.perf_counter()
    text, error = "", None
    try:
        text = fn()
        if isinstance(text, str) and text.startswith("[LLM调用失败]"):
            error = text
    except Exception as e:  # 生成失败不中断整批实验
        error = f"{type(e).__name__}: {e}"
    return {"text": text, "latency_s": round(time.perf_counter() - start, 3), "error": error}


# ==================== 数据序列化 ====================

def data_to_text(task: Task) -> str:
    """把任务数据快照序列化为表格化文本（供 B1 / B2 / B4 使用）"""
    d = task.data
    lines: List[str] = []
    sc = task.scenario

    if sc == "patient_storyline":
        lines.append(f"患者ID：{d.get('patient_id')}，病案号：{d.get('medical_record_no') or '未知'}，"
                     f"年龄：{d.get('age') or '未知'}，就诊次数：{d.get('visit_count')}")
        for i, v in enumerate(d.get("visits", []), 1):
            lines.append(f"第{i}次就诊：入院 {v.get('admission_date') or '未知'}，"
                         f"出院 {v.get('discharge_date') or '未知'}，"
                         f"住院 {v.get('length_of_stay') or '未知'} 天")
            if v.get("chief_complaint"):
                lines.append(f"  主诉：{v['chief_complaint']}")
            for key, label in [("diseases", "诊断"), ("drugs", "用药"),
                               ("surgeries", "手术"), ("exams", "检查")]:
                items = [x for x in v.get(key, []) if x]
                if items:
                    lines.append(f"  {label}：{'、'.join(items)}")

    elif sc == "treatment_pathway":
        lines.append(f"疾病：{d.get('disease_name')}，相关就诊人次：{d.get('visit_count')}，"
                     f"平均住院天数：{d.get('avg_stay')}")
        for key, label in [("top_drugs", "常用药品"), ("top_exams", "常用检查"),
                           ("top_surgeries", "常见手术")]:
            items = d.get(key, [])
            if items:
                lines.append(f"{label}：" + "；".join(f"{x['name']}({x['count']}例)" for x in items))

    elif sc == "comorbidity":
        lines.append(f"疾病：{d.get('disease_name')}，相关就诊人次：{d.get('visit_count')}")
        items = d.get("comorbidities", [])
        if items:
            lines.append("合并症：" + "；".join(f"{x['name']}({x['count']}例)" for x in items))

    elif sc == "drug_pattern":
        lines.append(f"疾病：{d.get('disease_name')}，相关就诊人次：{d.get('visit_count')}")
        items = d.get("top_drugs", [])
        if items:
            lines.append("常用药品：" + "；".join(f"{x['name']}({x['count']}例)" for x in items))
        pairs = d.get("drug_pairs", [])
        if pairs:
            lines.append("药品组合：" + "；".join(f"{p['drug_a']}+{p['drug_b']}({p['count']}例)" for p in pairs))

    elif sc == "morning_briefing":
        lines.append(f"日期：{d.get('date')}，新入院：{d.get('new_admissions')} 人，"
                     f"当日手术：{d.get('surgeries')} 台")
        for a in d.get("admissions", []):
            lines.append(f"  新入院患者 {a['patient_id']}，年龄 {a.get('age') or '未知'}，"
                         f"主诉：{a.get('chief_complaint') or '未记录'}")

    return "\n".join(lines)


def facts_to_lines(task: Task) -> List[str]:
    """把任务的 ground truth 事实序列化为编号事实清单（供 B2 使用；B3 走 facts_list_to_lines）"""
    return facts_list_to_lines(task.ground_truth_facts)


# ==================== B1：直接 LLM ====================

class DirectLLM:
    """B1：把表格化数据摘要连同 prompt 直接给 LLM，无图谱结构化约束"""

    name = "B1_direct"

    def __init__(self, chat_fn: Optional[ChatFn] = None):
        self.chat_fn = chat_fn or _default_chat

    def generate(self, task: Task) -> Dict[str, Any]:
        context = data_to_text(task)

        def _call():
            return self.chat_fn(
                [
                    {"role": "system", "content": "你是一位资深临床医生，擅长撰写专业的医疗叙事。请根据提供的数据用中文生成叙事，直接输出叙事文本，不要加标题。"},
                    {"role": "user", "content": f"{task.prompt}\n\n数据：\n{context}"},
                ],
                temperature=exp_config.LLM_TEMPERATURE,
                max_tokens=exp_config.LLM_MAX_TOKENS,
                cache_namespace=exp_config.cache_namespace(self.name, task.scenario),
            )

        result = _run_timed(_call)
        return {"task_id": task.task_id, "scenario": task.scenario, "method": self.name, **result}


# ==================== B2：向量 RAG ====================

def _keyword_retrieve(lines: List[str], query: str, k: int) -> List[str]:
    """关键词重叠检索（向量库不可用时的降级方案）"""
    tokens = [t for t in query.replace("，", " ").replace("。", " ").split() if t]
    scored = []
    for line in lines:
        score = sum(line.count(t) for t in tokens)
        if score > 0:
            scored.append((score, line))
    scored.sort(key=lambda x: -x[0])
    return [line for _, line in scored[:k]] or lines[:k]


def _vector_retrieve(lines: List[str], query: str, k: int) -> tuple:
    """向量检索；返回 (命中文本列表, 是否降级)"""
    try:
        import chromadb
        client = chromadb.EphemeralClient()
        coll = client.create_collection("exp_b2")
        coll.add(documents=lines, ids=[str(i) for i in range(len(lines))])
        res = coll.query(query_texts=[query], n_results=min(k, len(lines)))
        docs = (res.get("documents") or [[]])[0]
        if docs:
            return docs, False
        raise RuntimeError("向量检索无结果")
    except Exception:
        return _keyword_retrieve(lines, query, k), True


class VectorRAG:
    """B2：检索（向量库，不可用时降级为关键词检索）+ LLM"""

    name = "B2_vector_rag"

    def __init__(self, chat_fn: Optional[ChatFn] = None, top_k: int = 10):
        self.chat_fn = chat_fn or _default_chat
        self.top_k = top_k

    def generate(self, task: Task) -> Dict[str, Any]:
        # 候选片段：数据文本按行 + 事实清单
        lines = [l for l in data_to_text(task).split("\n") if l.strip()]
        lines += facts_to_lines(task)
        if not lines:
            return {"task_id": task.task_id, "scenario": task.scenario, "method": self.name,
                    "text": "", "latency_s": 0.0, "error": "无可检索片段", "degraded": True}

        retrieved, degraded = _vector_retrieve(lines, task.prompt, self.top_k)
        context = "\n".join(retrieved)

        def _call():
            return self.chat_fn(
                [
                    {"role": "system", "content": "你是一位资深临床医生。请基于检索到的参考资料用中文撰写医疗叙事，直接输出叙事文本，不要加标题。"},
                    {"role": "user", "content": f"{task.prompt}\n\n检索到的参考资料：\n{context}"},
                ],
                temperature=exp_config.LLM_TEMPERATURE,
                max_tokens=exp_config.LLM_MAX_TOKENS,
                cache_namespace=exp_config.cache_namespace(self.name, task.scenario),
            )

        result = _run_timed(_call)
        return {"task_id": task.task_id, "scenario": task.scenario, "method": self.name,
                "degraded": degraded, **result}


# ==================== B3：KG-grounded（本文方法） ====================

B3_SYSTEM_PROMPT = (
    "你是一位资深临床医生。请仅依据下面给出的事实清单撰写医疗叙事。\n"
    "事实约束（必须遵守）：\n"
    "1. 只能使用事实清单中的信息，不得添加清单之外的任何实体、数值或关系；\n"
    "2. 叙事中涉及的事实在句末标注来源编号；每个句子只在句末标注一次，"
    "多个来源合并为 [F1,F2] 形式，不要每半句都标注；\n"
    "3. 事实清单未覆盖的内容不要提及。\n"
    "叙事质量要求（同等重要）：\n"
    "4. 按主题组织段落（如诊断、治疗、检查检验），不要逐条罗列事实，"
    "段落之间使用过渡句衔接；\n"
    "5. 结尾给出一段综合性总结或临床提示；\n"
    "6. 语言流畅、面向临床读者，允许在不引入新事实的前提下进行归纳与解释。\n"
    "直接输出叙事文本，不要加标题。"
)


def facts_list_to_lines(facts: List[Dict[str, Any]]) -> List[str]:
    """把事实列表序列化为编号事实清单（重新从 F1 编号）"""
    lines = []
    for i, f in enumerate(facts, 1):
        text = f"{f['subject']} —{f['predicate']}→ {f['object']}"
        if f.get("qualifiers"):
            q = "，".join(f"{k}={v}" for k, v in f["qualifiers"].items())
            text += f"（{q}）"
        lines.append(f"[F{i}] {text}")
    return lines


class KGGrounded:
    """B3：图谱事实清单约束生成——只允许使用给定事实并逐条标注来源。

    消融变体通过覆盖 fact_filter()（检索/事实层）或 SYSTEM_PROMPT（生成层）实现，
    其余逻辑与 B3 完全一致。
    """

    name = "B3_kg_grounded"
    SYSTEM_PROMPT = B3_SYSTEM_PROMPT

    def __init__(self, chat_fn: Optional[ChatFn] = None):
        self.chat_fn = chat_fn or _default_chat

    def fact_filter(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """事实过滤钩子：B3 不过滤；消融变体在此模拟检索层退化"""
        return facts

    def generate(self, task: Task) -> Dict[str, Any]:
        facts = self.fact_filter(task.ground_truth_facts)
        fact_lines = "\n".join(facts_list_to_lines(facts))

        def _call():
            return self.chat_fn(
                [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"{task.prompt}\n\n事实清单：\n{fact_lines}"},
                ],
                temperature=exp_config.LLM_TEMPERATURE,
                max_tokens=exp_config.LLM_MAX_TOKENS,
                cache_namespace=exp_config.cache_namespace(self.name, task.scenario),
            )

        result = _run_timed(_call)
        return {"task_id": task.task_id, "scenario": task.scenario, "method": self.name, **result}


# ==================== B3 消融变体（Table 5） ====================

# 共现/二阶关系原语产生的谓词（A2 禁用）
_COOC_PREDICATES = {"cooccurs_with", "cooccur_count", "co_prescribed_with", "pair_count"}


def _merged_disease_names() -> set:
    """ICD-10 标准化/同义合并的 target 疾病名集合（即会被合并非同名变体的标准名）。

    直接复用 services.kg_data_cleaner.KGDataCleaner.DISEASE_SYNONYMS：
    key≠value 的 value 表示有原始诊断名变体被归并到该标准名。
    """
    from services.kg_data_cleaner import KGDataCleaner
    return {v for k, v in KGDataCleaner.DISEASE_SYNONYMS.items() if k != v}


class A1NoICD10(KGGrounded):
    """A1：去除疾病名标准化/同义合并。

    模拟方式：图谱中的疾病聚合事实（visit_count、top_drug、cooccurs_with 等）依赖
    把原始诊断名变体（如"高血压病/原发性高血压"→"高血压"、"肺癌"→"肺恶性肿瘤"）
    归并到标准名后统计得到。未标准化时，这些标准名的计数被拆散到各原始变体上，
    Top-N 聚合事实中不再出现该标准名 —— 因此把涉及"被合并标准名"的事实视为
    检索不可得，从事实清单中剔除（疾病名出现在 subject/object/字符串 qualifiers
    中任一位置即剔除该条事实）。
    """

    name = "A1_no_icd10"

    def fact_filter(self, facts):
        dropped = _merged_disease_names()
        kept = []
        for f in facts:
            names = [str(f.get("subject", "")), str(f.get("object", ""))]
            names += [v for v in (f.get("qualifiers") or {}).values() if isinstance(v, str)]
            if any(n in dropped for n in names):
                continue
            kept.append(f)
        return kept


class A2FirstHop(KGGrounded):
    """A2：检索仅限一度邻居，禁用共现检索与二阶关系原语。

    实现：剔除共现谓词事实（cooccurs_with / cooccur_count / co_prescribed_with /
    pair_count）。comorbidity 场景退化为只有疾病就诊人次等直接统计，
    drug_pattern 场景退化为疾病-药品的直接关联（top_drug/drug_count），
    其余场景的事实本身即一度关联，不受影响。
    """

    name = "A2_first_hop"

    def fact_filter(self, facts):
        return [f for f in facts if f.get("predicate") not in _COOC_PREDICATES]


class A3NoProvenance(KGGrounded):
    """A3：生成 prompt 去掉来源标注约束（不要求 [Fk] 标注），其余与 B3 相同"""

    name = "A3_no_provenance"

    SYSTEM_PROMPT = (
        "你是一位资深临床医生。请仅依据下面给出的事实清单撰写医疗叙事。\n"
        "事实约束（必须遵守）：\n"
        "1. 只能使用事实清单中的信息，不得添加清单之外的任何实体、数值或关系；\n"
        "2. 事实清单未覆盖的内容不要提及。\n"
        "叙事质量要求（同等重要）：\n"
        "3. 按主题组织段落（如诊断、治疗、检查检验），不要逐条罗列事实，"
        "段落之间使用过渡句衔接；\n"
        "4. 结尾给出一段综合性总结或临床提示；\n"
        "5. 语言流畅、面向临床读者，允许在不引入新事实的前提下进行归纳与解释。\n"
        "直接输出叙事文本，不要加标题。"
    )


# ==================== B4：规则模板 ====================

class TemplateMethod:
    """B4：规则模板填空生成（下界参照，不调用 LLM）"""

    name = "B4_template"

    def generate(self, task: Task) -> Dict[str, Any]:
        result = _run_timed(lambda: self._render(task))
        return {"task_id": task.task_id, "scenario": task.scenario, "method": self.name, **result}

    def _render(self, task: Task) -> str:
        d = task.data
        sc = task.scenario

        if sc == "patient_storyline":
            age = f"{d.get('age')}岁" if d.get("age") is not None else "年龄未知"
            parts = [f"患者（病案号{d.get('medical_record_no') or d.get('patient_id')}），"
                     f"年龄{age}，就诊次数{d.get('visit_count')}次。"]
            for i, v in enumerate(d.get("visits", []), 1):
                seg = f"第{i}次于{v.get('admission_date') or '未知日期'}入院"
                if v.get("length_of_stay"):
                    seg += f"，住院{v['length_of_stay']}天"
                seg += "。"
                diseases = [x for x in v.get("diseases", []) if x]
                drugs = [x for x in v.get("drugs", []) if x]
                surgeries = [x for x in v.get("surgeries", []) if x]
                if diseases:
                    seg += f"诊断为：{'、'.join(diseases)}。"
                if drugs:
                    seg += f"用药包括：{'、'.join(drugs)}。"
                if surgeries:
                    seg += f"行手术：{'、'.join(surgeries)}。"
                parts.append(seg)
            return "".join(parts)

        if sc == "treatment_pathway":
            parts = [f"本科室{d.get('disease_name')}相关就诊人次共{d.get('visit_count')}人次"]
            if d.get("avg_stay") is not None:
                parts.append(f"，平均住院天数{d['avg_stay']}天")
            parts.append("。")
            if d.get("top_drugs"):
                parts.append("常用药品：" + "、".join(x["name"] for x in d["top_drugs"]) + "。")
            if d.get("top_exams"):
                parts.append("常规检查：" + "、".join(x["name"] for x in d["top_exams"]) + "。")
            if d.get("top_surgeries"):
                parts.append("常见手术：" + "、".join(x["name"] for x in d["top_surgeries"]) + "。")
            return "".join(parts)

        if sc == "comorbidity":
            parts = [f"{d.get('disease_name')}相关就诊人次共{d.get('visit_count')}人次。"]
            if d.get("comorbidities"):
                parts.append("常见合并症：" + "、".join(
                    f"{x['name']}（{x['count']}例）" for x in d["comorbidities"]) + "。")
            return "".join(parts)

        if sc == "drug_pattern":
            parts = [f"{d.get('disease_name')}相关就诊人次共{d.get('visit_count')}人次。"]
            if d.get("top_drugs"):
                parts.append("常用药品：" + "、".join(
                    f"{x['name']}（{x['count']}例）" for x in d["top_drugs"]) + "。")
            if d.get("drug_pairs"):
                parts.append("常见药品组合：" + "、".join(
                    f"{p['drug_a']}+{p['drug_b']}（{p['count']}例）" for p in d["drug_pairs"]) + "。")
            return "".join(parts)

        if sc == "morning_briefing":
            parts = [f"{d.get('date')}晨会简报：新入院{d.get('new_admissions')}人，"
                     f"当日手术{d.get('surgeries')}台。"]
            for a in d.get("admissions", []):
                parts.append(f"新入院患者{a['patient_id']}，主诉：{a.get('chief_complaint') or '未记录'}。")
            return "".join(parts)

        raise ValueError(f"未知场景: {sc}")


# 方法注册表
METHOD_REGISTRY = {
    DirectLLM.name: DirectLLM,
    VectorRAG.name: VectorRAG,
    KGGrounded.name: KGGrounded,
    TemplateMethod.name: TemplateMethod,
    # B3 消融变体
    A1NoICD10.name: A1NoICD10,
    A2FirstHop.name: A2FirstHop,
    A3NoProvenance.name: A3NoProvenance,
}


def build_methods(names: Optional[List[str]] = None) -> List:
    """按名称实例化生成方法"""
    names = names or list(exp_config.METHODS)
    methods = []
    for name in names:
        if name not in METHOD_REGISTRY:
            raise ValueError(f"未知方法: {name}，可选: {list(METHOD_REGISTRY)}")
        methods.append(METHOD_REGISTRY[name]())
    return methods
