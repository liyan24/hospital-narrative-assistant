"""任务采样：从知识图谱采样 5 类叙事场景的实验任务，并附带 ground truth 事实。

每个任务包含：
- task_id / scenario / subject / prompt
- ground_truth_facts: 结构化事实列表，元素为
  {"subject": str, "predicate": str, "object": str|int|float, "qualifiers": dict}
- data: 生成方法可用的原始数据快照（JSON 可序列化），避免生成阶段重复查图

所有 Cypher 的关系名/属性名以 services/knowledge_graph_service.py 实际构建代码为准：
- (Patient)-[:HAS_VISIT]->(Visit)
- (Visit)-[:DIAGNOSED_WITH {diagnosis_type, is_main}]->(Disease)
- (Visit)-[:CHIEF_COMPLAINT]->(ChiefComplaint)
- (Visit)-[:PERFORMED_EXAM {exam_date, ...}]->(Exam)
- (Visit)-[:HAS_LAB_RESULT {value, unit, abnormal_flag, ...}]->(LabItem)
- (Visit)-[:PRESCRIBED {dosage, frequency, route, start_date}]->(Drug)
- (Visit)-[:UNDERWENT {start_date}]->(Surgery)
- (Visit)-[:IN_DEPARTMENT]->(Department)
- (Drug|Surgery)-[:TREATS]->(Disease)
注意：Disease.name 是 "显示名::type" 的组合键，展示用 display_name；type 取值如 western / tcm / tcm_syndrome。
"""

import random
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import experiments  # noqa: F401  确保 sys.path 就绪
from database.neo4j_client import neo4j_client
from experiments import exp_config


@dataclass
class Task:
    """一个叙事生成实验任务"""

    task_id: str
    scenario: str
    subject: str
    prompt: str
    ground_truth_facts: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Task":
        return Task(
            task_id=d["task_id"],
            scenario=d["scenario"],
            subject=d["subject"],
            prompt=d["prompt"],
            ground_truth_facts=d.get("ground_truth_facts", []),
            data=d.get("data", {}),
        )


def _fact(subject: Any, predicate: str, obj: Any, **qualifiers) -> Dict[str, Any]:
    """构造一条结构化事实"""
    return {
        "subject": str(subject),
        "predicate": predicate,
        "object": obj,
        "qualifiers": qualifiers,
    }


def _seeded_sample(pool: List[Any], n: int, seed: int) -> List[Any]:
    """可复现采样：排序后按种子抽样"""
    rng = random.Random(seed)
    pool = list(pool)
    rng.shuffle(pool)
    return pool[: max(0, min(n, len(pool)))]


# ==================== 场景 1：患者故事线 ====================

def _sample_patient_storyline(n: int, seed: int) -> List[Task]:
    cql_pool = """
    MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
    WITH p, count(v) AS visit_count
    WHERE visit_count >= 1
    RETURN p.patient_id AS patient_id, p.medical_record_no AS mrn,
           p.age AS age, visit_count
    ORDER BY p.patient_id
    """
    pool = [dict(r) for r in neo4j_client.run(cql_pool)]
    tasks = []
    for i, row in enumerate(_seeded_sample(pool, n, seed)):
        pid = row["patient_id"]
        # 就诊列表（按入院日期排序，最多取前 2 次，控制事实规模）
        cql_visits = """
        MATCH (p:Patient {patient_id: $pid})-[:HAS_VISIT]->(v:Visit)
        RETURN v.visit_id AS visit_id, v.admission_date AS admission_date,
               v.discharge_date AS discharge_date, v.length_of_stay AS los,
               v.chief_complaint AS chief_complaint
        ORDER BY v.admission_date LIMIT 2
        """
        visits = [dict(r) for r in neo4j_client.run(cql_visits, {"pid": pid})]

        facts: List[Dict[str, Any]] = [
            _fact(pid, "visit_count", int(row["visit_count"]), label="就诊次数"),
        ]
        if row.get("mrn"):
            facts.append(_fact(pid, "medical_record_no", str(row["mrn"]), label="病案号"))
        if row.get("age") is not None:
            facts.append(_fact(pid, "age", row["age"], label="年龄"))
        visits_data = []
        for v in visits:
            vid = v["visit_id"]
            adm_date = str(v.get("admission_date") or "")
            facts.append(_fact(pid, "HAS_VISIT", vid))
            if v.get("admission_date"):
                facts.append(_fact(vid, "admission_date", adm_date, label="入院日期"))
            if v.get("discharge_date"):
                facts.append(_fact(vid, "discharge_date", str(v["discharge_date"]), label="出院日期"))
            if v.get("los") is not None:
                facts.append(_fact(vid, "length_of_stay", v["los"],
                                   label="住院天数", item="住院",
                                   admission_date=adm_date))
            cql_detail = """
            MATCH (v:Visit {visit_id: $vid})
            OPTIONAL MATCH (v)-[rd:DIAGNOSED_WITH]->(d:Disease)
            OPTIONAL MATCH (v)-[rp:PRESCRIBED]->(dr:Drug)
            OPTIONAL MATCH (v)-[ru:UNDERWENT]->(s:Surgery)
            OPTIONAL MATCH (v)-[re:PERFORMED_EXAM]->(e:Exam)
            RETURN
                collect(DISTINCT d.display_name)[..8] AS diseases,
                collect(DISTINCT dr.name)[..8] AS drugs,
                collect(DISTINCT s.name)[..5] AS surgeries,
                collect(DISTINCT e.name)[..5] AS exams
            """
            recs = neo4j_client.run(cql_detail, {"vid": vid})
            detail = dict(recs[0]) if recs else {}
            for name in detail.get("diseases") or []:
                if name:
                    facts.append(_fact(vid, "DIAGNOSED_WITH", name))
            for name in detail.get("drugs") or []:
                if name:
                    facts.append(_fact(vid, "PRESCRIBED", name))
            for name in detail.get("surgeries") or []:
                if name:
                    facts.append(_fact(vid, "UNDERWENT", name))
            for name in detail.get("exams") or []:
                if name:
                    facts.append(_fact(vid, "PERFORMED_EXAM", name))
            # 检验结果：数值事实的上下文放在 qualifiers（项目名/单位/入院日期），
            # 因为叙事只会提及项目名和数值，不会提及内部 visit_id
            cql_labs = """
            MATCH (v:Visit {visit_id: $vid})-[rl:HAS_LAB_RESULT]->(l:LabItem)
            RETURN l.name AS name, rl.value AS value, rl.unit AS unit LIMIT 8
            """
            lab_rows = [dict(r) for r in neo4j_client.run(cql_labs, {"vid": vid})]
            labs_data = []
            for lr in lab_rows:
                if not lr.get("name"):
                    continue
                facts.append(_fact(vid, "HAS_LAB_RESULT", lr["name"]))
                try:
                    lab_val = float(lr["value"])
                except (TypeError, ValueError):
                    lab_val = None
                if lab_val is not None:
                    facts.append(_fact(vid, "lab_value", lab_val,
                                       item=lr["name"], unit=str(lr.get("unit") or ""),
                                       label="检验结果", admission_date=adm_date))
                labs_data.append({"name": lr["name"], "value": lr.get("value"),
                                  "unit": lr.get("unit")})
            visits_data.append({
                "visit_id": vid,
                "admission_date": str(v.get("admission_date") or ""),
                "discharge_date": str(v.get("discharge_date") or ""),
                "length_of_stay": v.get("los"),
                "chief_complaint": v.get("chief_complaint") or "",
                "diseases": detail.get("diseases") or [],
                "drugs": detail.get("drugs") or [],
                "surgeries": detail.get("surgeries") or [],
                "exams": detail.get("exams") or [],
                "labs": labs_data,
            })

        prompt = (
            f"请为患者（病案号 {row.get('mrn') or pid}）撰写一段患者故事线叙事，"
            f"按时间顺序描述其 {row['visit_count']} 次就诊经过，"
            "包括每次入院的主诉、诊断、用药、检查与手术等关键信息，800字以内。"
        )
        tasks.append(Task(
            task_id=f"patient_storyline-{i:03d}",
            scenario="patient_storyline",
            subject=pid,
            prompt=prompt,
            ground_truth_facts=facts,
            data={
                "patient_id": pid,
                "medical_record_no": row.get("mrn"),
                "age": row.get("age"),
                "visit_count": int(row["visit_count"]),
                "visits": visits_data,
            },
        ))
    return tasks


# ==================== 疾病类场景的公共查询 ====================

def _disease_pool(min_visits: int = 10) -> List[Dict[str, Any]]:
    """西医疾病候选池（按就诊人次降序）"""
    cql = """
    MATCH (d:Disease)<-[:DIAGNOSED_WITH]-(v:Visit)
    WHERE d.type = 'western'
    WITH d.display_name AS name, count(DISTINCT v) AS cnt
    WHERE cnt >= $min_visits
    RETURN name, cnt ORDER BY cnt DESC, name
    """
    return [dict(r) for r in neo4j_client.run(cql, {"min_visits": min_visits})]


def _disease_top_items(disease_name: str, rel: str, label: str, limit: int) -> List[Dict[str, Any]]:
    """某疾病就诊中最常关联的实体（药品/检查/手术/检验等）"""
    cql = f"""
    MATCH (d:Disease)
    WHERE d.display_name = $name OR d.name STARTS WITH $name + "::"
    MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:{rel}]->(x:{label})
    RETURN x.name AS name, count(DISTINCT v) AS cnt
    ORDER BY cnt DESC LIMIT $limit
    """
    return [{"name": r["name"], "count": r["cnt"]}
            for r in neo4j_client.run(cql, {"name": disease_name, "limit": limit})]


def _disease_base_stats(disease_name: str) -> Optional[Dict[str, Any]]:
    cql = """
    MATCH (d:Disease)
    WHERE d.display_name = $name OR d.name STARTS WITH $name + "::"
    MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)
    RETURN count(DISTINCT v) AS visit_count, avg(v.length_of_stay) AS avg_stay
    """
    recs = neo4j_client.run(cql, {"name": disease_name})
    if not recs or recs[0]["visit_count"] == 0:
        return None
    return dict(recs[0])


# ==================== 场景 2：诊疗路径 ====================

def _sample_treatment_pathway(n: int, seed: int) -> List[Task]:
    tasks = []
    for i, row in enumerate(_seeded_sample(_disease_pool(), n, seed)):
        name = row["name"]
        stats = _disease_base_stats(name)
        if not stats:
            continue
        top_drugs = _disease_top_items(name, "PRESCRIBED", "Drug", 10)
        top_exams = _disease_top_items(name, "PERFORMED_EXAM", "Exam", 5)
        top_surgeries = _disease_top_items(name, "UNDERWENT", "Surgery", 5)

        facts = [_fact(name, "visit_count", int(stats["visit_count"]), label="就诊人次")]
        if stats.get("avg_stay") is not None:
            facts.append(_fact(name, "avg_stay", round(float(stats["avg_stay"]), 1),
                               label="平均住院天数"))
        for d in top_drugs:
            facts.append(_fact(name, "top_drug", d["name"], count=int(d["count"])))
            facts.append(_fact(name, "drug_count", int(d["count"]),
                               item=d["name"], label="使用例数"))
        for e in top_exams:
            facts.append(_fact(name, "top_exam", e["name"], count=int(e["count"])))
        for s in top_surgeries:
            facts.append(_fact(name, "top_surgery", s["name"], count=int(s["count"])))

        prompt = (
            f"请撰写「{name}」的诊疗路径模式叙事，总结本科室对该疾病的典型诊疗流程、"
            "常用药品、常规检查与手术、住院天数情况，800字以内。"
        )
        tasks.append(Task(
            task_id=f"treatment_pathway-{i:03d}",
            scenario="treatment_pathway",
            subject=name,
            prompt=prompt,
            ground_truth_facts=facts,
            data={
                "disease_name": name,
                "visit_count": int(stats["visit_count"]),
                "avg_stay": round(float(stats["avg_stay"]), 1) if stats.get("avg_stay") is not None else None,
                "top_drugs": top_drugs,
                "top_exams": top_exams,
                "top_surgeries": top_surgeries,
            },
        ))
    return tasks


# ==================== 场景 3：合并症分析 ====================

def _sample_comorbidity(n: int, seed: int) -> List[Task]:
    tasks = []
    for i, row in enumerate(_seeded_sample(_disease_pool(), n, seed)):
        name = row["name"]
        stats = _disease_base_stats(name)
        if not stats:
            continue
        cql = """
        MATCH (d:Disease)
        WHERE d.display_name = $name OR d.name STARTS WITH $name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(d2:Disease)
        WHERE d2 <> d AND d2.type = 'western'
        RETURN d2.display_name AS name, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 15
        """
        comorbs = [{"name": r["name"], "count": r["cnt"]}
                   for r in neo4j_client.run(cql, {"name": name})]
        if not comorbs:
            continue

        total = int(stats["visit_count"])
        facts = [_fact(name, "visit_count", total, label="就诊人次")]
        for c in comorbs:
            facts.append(_fact(name, "cooccurs_with", c["name"], count=int(c["count"])))
            facts.append(_fact(name, "cooccur_count", int(c["count"]),
                               item=c["name"], label="共现例数"))

        prompt = (
            f"请撰写「{name}」的合并症（疾病共现）分析叙事，"
            "说明最常见的合并症及其共现频次与临床意义，800字以内。"
        )
        tasks.append(Task(
            task_id=f"comorbidity-{i:03d}",
            scenario="comorbidity",
            subject=name,
            prompt=prompt,
            ground_truth_facts=facts,
            data={
                "disease_name": name,
                "visit_count": total,
                "comorbidities": comorbs,
            },
        ))
    return tasks


# ==================== 场景 4：用药模式 ====================

def _sample_drug_pattern(n: int, seed: int) -> List[Task]:
    tasks = []
    for i, row in enumerate(_seeded_sample(_disease_pool(), n, seed)):
        name = row["name"]
        stats = _disease_base_stats(name)
        if not stats:
            continue
        top_drugs = _disease_top_items(name, "PRESCRIBED", "Drug", 15)
        if not top_drugs:
            continue
        cql_pairs = """
        MATCH (d:Disease)
        WHERE d.display_name = $name OR d.name STARTS WITH $name + "::"
        MATCH (d)<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(d1:Drug)
        MATCH (v)-[:PRESCRIBED]->(d2:Drug)
        WHERE d1 <> d2 AND d1.name < d2.name
        RETURN d1.name AS name1, d2.name AS name2, count(DISTINCT v) AS cnt
        ORDER BY cnt DESC LIMIT 10
        """
        pairs = [{"drug_a": r["name1"], "drug_b": r["name2"], "count": r["cnt"]}
                 for r in neo4j_client.run(cql_pairs, {"name": name})]

        total = int(stats["visit_count"])
        facts = [_fact(name, "visit_count", total, label="就诊人次")]
        for d in top_drugs:
            facts.append(_fact(name, "top_drug", d["name"], count=int(d["count"])))
            facts.append(_fact(name, "drug_count", int(d["count"]),
                               item=d["name"], label="使用例数"))
        for p in pairs:
            facts.append(_fact(p["drug_a"], "co_prescribed_with", p["drug_b"],
                               count=int(p["count"]), disease=name))
            facts.append(_fact(f"{p['drug_a']}+{p['drug_b']}", "pair_count",
                               int(p["count"]), drug_a=p["drug_a"], drug_b=p["drug_b"],
                               label="联合用药例数", disease=name))

        prompt = (
            f"请撰写「{name}」的用药模式分析叙事，"
            "说明最常用药品、常见药品组合及潜在用药问题，800字以内。"
        )
        tasks.append(Task(
            task_id=f"drug_pattern-{i:03d}",
            scenario="drug_pattern",
            subject=name,
            prompt=prompt,
            ground_truth_facts=facts,
            data={
                "disease_name": name,
                "visit_count": total,
                "top_drugs": top_drugs,
                "drug_pairs": pairs,
            },
        ))
    return tasks


# ==================== 场景 5：晨会简报 ====================

def _sample_morning_briefing(n: int, seed: int) -> List[Task]:
    cql_dates = """
    MATCH (v:Visit)
    WHERE v.admission_date IS NOT NULL
    RETURN v.admission_date AS d, count(*) AS cnt
    ORDER BY cnt DESC, d
    """
    pool = [{"date": str(r["d"]), "count": r["cnt"]} for r in neo4j_client.run(cql_dates)]
    tasks = []
    for i, row in enumerate(_seeded_sample(pool, n, seed)):
        day = row["date"]
        # 当日新入院患者
        cql_adm = """
        MATCH (p:Patient)-[:HAS_VISIT]->(v:Visit)
        WHERE date(v.admission_date) = date($day)
        RETURN p.patient_id AS patient_id, p.age AS age,
               v.chief_complaint AS chief_complaint
        LIMIT 15
        """
        admissions = [dict(r) for r in neo4j_client.run(cql_adm, {"day": day})]
        # 当日手术
        cql_surg = """
        MATCH (v:Visit)-[r:UNDERWENT]->(s:Surgery)
        WHERE date(r.start_date) = date($day)
        RETURN count(r) AS cnt
        """
        surg_recs = neo4j_client.run(cql_surg, {"day": day})
        surg_count = int(surg_recs[0]["cnt"]) if surg_recs else 0

        facts = [
            _fact(day, "new_admissions", int(row["count"]), label="新入院人数"),
            _fact(day, "surgeries", surg_count, label="手术台数"),
        ]
        for a in admissions:
            facts.append(_fact(a["patient_id"], "admitted_on", day, label="入院日期"))

        prompt = (
            f"请撰写 {day} 的科室晨会简报叙事，"
            "包括当日新入院人数、手术安排与重点关注事项，500字以内。"
        )
        tasks.append(Task(
            task_id=f"morning_briefing-{i:03d}",
            scenario="morning_briefing",
            subject=day,
            prompt=prompt,
            ground_truth_facts=facts,
            data={
                "date": day,
                "new_admissions": int(row["count"]),
                "surgeries": surg_count,
                "admissions": [
                    {"patient_id": a["patient_id"], "age": a.get("age"),
                     "chief_complaint": a.get("chief_complaint") or ""}
                    for a in admissions
                ],
            },
        ))
    return tasks


# ==================== 采样入口 ====================

SAMPLERS = {
    "patient_storyline": _sample_patient_storyline,
    "treatment_pathway": _sample_treatment_pathway,
    "comorbidity": _sample_comorbidity,
    "drug_pattern": _sample_drug_pattern,
    "morning_briefing": _sample_morning_briefing,
}


def sample_tasks(
    scenarios: Optional[List[str]] = None,
    per_scenario: int = exp_config.DEFAULT_SAMPLES_PER_SCENARIO,
    seed: int = exp_config.DEFAULT_SEED,
    limit: Optional[int] = None,
) -> List[Task]:
    """按场景采样实验任务。

    scenarios: 为空则采样全部 5 类场景
    per_scenario: 每类场景采样数
    seed: 随机种子（每个场景使用 seed 派生的独立种子，互不影响）
    limit: 全局任务数上限（小样本试跑用）
    """
    scenarios = scenarios or list(exp_config.SCENARIOS)
    tasks: List[Task] = []
    for idx, sc in enumerate(scenarios):
        if sc not in SAMPLERS:
            raise ValueError(f"未知场景: {sc}，可选: {list(SAMPLERS)}")
        tasks.extend(SAMPLERS[sc](per_scenario, seed + idx))
    if limit is not None:
        tasks = tasks[:limit]
    return tasks
