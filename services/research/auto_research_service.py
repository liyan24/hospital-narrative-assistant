"""
智能自动科研流水线：LLM 议题推荐 + 后台线程自动执行（算子链 + 论文生成）。
面向不懂 ML 的医生：只选一个议题，系统自动跑完分析并产出论文 docx。
"""
import json
import threading
import uuid
from datetime import datetime

from database.json_store import json_store
from services.llm_service import llm_service
from services.research.dataset_service import dataset_service
from services.research.research_assistant_service import (
    SYSTEM_PROMPT, research_assistant_service,
)
from services.research.skills.registry import get_skill, list_skills_by_category


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# 流水线任务状态（内存为主，完成后落 json_store 供重启后查询）
_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()


class AutoResearchService:
    """自动科研流水线服务：议题推荐 + 一键流水线"""

    def __init__(self):
        self.llm = llm_service

    # ========== 议题推荐 ==========

    def propose_topics(self, refresh: bool = False,
                       exclude_titles: list[str] | None = None) -> list[dict]:
        """基于数据画像与算子目录，LLM 推荐 3-5 个数据可支撑的研究议题。
        refresh=True 时跳过 LLM 缓存，并在 prompt 中排除已推荐过的议题标题。"""
        try:
            return self._propose_topics_llm(refresh=refresh, exclude_titles=exclude_titles)
        except Exception:
            return self._fallback_topics()

    def _propose_topics_llm(self, refresh: bool = False,
                            exclude_titles: list[str] | None = None) -> list[dict]:
        # 上下文：数据资产 + 数据画像 facts + 算子目录
        assets = dataset_service.detect_data_assets()
        assets_brief = [{
            "name": t["name"], "label": t["label"], "rows": t["rows"],
            "key_columns": t["key_columns"], "coverage_note": t["coverage_note"],
        } for t in assets["tables"]]

        profile = get_skill("dataset_profile").run({})
        profile_brief = {
            "summary": profile.get("summary", ""),
            "facts": profile.get("facts", {}),
        }

        catalog = [
            {"id": s["id"], "name": s["name"], "description": s["description"]}
            for skills in list_skills_by_category().values() for s in skills
        ]

        exclude_block = ""
        # 已推荐过（前端传入）+ 历史研究记录中出现过的议题都不再重复推荐
        history_titles = [j["topic_title"] for j in self.list_history()
                          if j.get("topic_title")]
        all_excluded = list(dict.fromkeys(
            [str(t) for t in (exclude_titles or []) if str(t).strip()] + history_titles))
        if all_excluded:
            listed = "\n".join(f"- {t}" for t in all_excluded)
            exclude_block = (
                "以下议题已经推荐过或已经研究过，请提出与它们研究方向不同的新议题：\n"
                f"{listed}\n\n")

        content = self.llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              f"数据资产清单：\n{json.dumps(assets_brief, ensure_ascii=False)}\n\n"
              f"数据集真实画像：\n{json.dumps(profile_brief, ensure_ascii=False, default=str)}\n\n"
              f"可用分析算子目录：\n{json.dumps(catalog, ensure_ascii=False, indent=1)}\n\n"
              f"{exclude_block}"
              "请基于上述数据的真实规模、覆盖率和字段，提出 3-5 个【数据可支撑】的临床科研议题。\n"
              "要求：\n"
              "1. 每个议题的 skills 只能从上述算子目录中选取 2-4 个，按合理分析顺序排列；\n"
              "2. 每个议题至少包含一个数据挖掘或机器学习算子；\n"
              "3. 优先样本量充足的议题：检验数据仅约 826 名患者有（覆盖约两成）、"
              "手术记录仅约 85 例，避免提出依赖这些稀缺数据的议题；\n"
              "4. 严格输出 JSON 数组，不要输出 markdown 代码块以外的任何文字。\n\n"
              '每项格式：{"id":"topic_1","title":"论文级中文标题","question":"研究问题一句话",'
              '"rationale":"为什么这个议题适合该数据（引用真实数字）","feasibility":"高|中|低",'
              '"skills":[{"id":"算子id","purpose":"该算子在本议题中回答什么"}]}'}],
            temperature=0.5,
            max_tokens=3000,
            cache_namespace="research:auto_topics",
            use_cache=not refresh,
        )

        topics = self._parse_topics(content)
        if not topics:
            raise ValueError(f"议题解析失败: {content[:200]}")
        return topics

    def _parse_topics(self, content: str) -> list[dict]:
        """从 LLM 回复中提取 JSON 数组并校验算子 id，补上算子中文名"""
        start = content.find("[")
        end = content.rfind("]")
        if start < 0 or end <= start:
            return []
        raw = json.loads(content[start:end + 1])
        if not isinstance(raw, list):
            return []

        topics = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            # LLM 偶发使用非约定键名，做别名容错
            raw_skills = item.get("skills") or item.get("methods") or item.get("算子") or []
            skills = []
            for s in raw_skills:
                if not isinstance(s, dict):
                    continue
                skill = get_skill(str(s.get("id", "")))
                if skill is None:
                    continue
                skills.append({
                    "id": skill.meta.id,
                    "name": skill.meta.name,
                    "purpose": str(s.get("purpose", "")),
                })
            if not skills:
                continue
            title = str(
                item.get("title") or item.get("topic_title") or item.get("name")
                or item.get("标题") or ""
            ).strip()
            if not title:
                # 标题缺失时用研究问题截断兜底，避免前端出现"未命名议题"
                title = (str(item.get("question", "")).strip() or f"研究议题 {i + 1}")[:40]
            topics.append({
                "id": str(item.get("id") or f"topic_{i + 1}"),
                "title": title,
                "question": str(item.get("question", "")),
                "rationale": str(item.get("rationale", "")),
                "feasibility": str(item.get("feasibility", "中")),
                "skills": skills,
            })
        return topics

    @staticmethod
    def _fallback_topics() -> list[dict]:
        """LLM 失败/解析失败时的内置兜底议题（均为数据可支撑的常见方向）"""
        def skill(sid: str, purpose: str) -> dict:
            meta = get_skill(sid)
            return {"id": sid, "name": meta.meta.name if meta else sid, "purpose": purpose}

        return [
            {
                "id": "topic_1",
                "title": "基于关联规则的肿瘤血液科住院患者合并症共现模式研究",
                "question": "住院患者的出院诊断之间存在哪些高频共现（合并症）关联模式？",
                "rationale": "诊断字段全量覆盖（万余次就诊），样本量充足，"
                            "适合用频繁项集与关联规则挖掘合并症共现结构。",
                "feasibility": "高",
                "skills": [
                    skill("frequent_itemsets", "找出高频共现的诊断组合（合并症模式）"),
                    skill("association_rules", "量化诊断间的关联强度（支持度/置信度/提升度）"),
                    skill("cooccurrence_network", "以网络图展示合并症共现的整体结构"),
                ],
            },
            {
                "id": "topic_2",
                "title": "肿瘤血液科患者再入院的影响因素分析及预测模型构建",
                "question": "哪些临床特征与患者再入院相关，能否构建可用的再入院预测模型？",
                "rationale": "多次就诊患者占比可观，再入院标签与年龄、住院天数、诊断、"
                            "检验等特征均在就诊级宽表中可得，样本量支撑分类建模。",
                "feasibility": "高",
                "skills": [
                    skill("group_comparison", "比较再入院与非再入院患者的特征差异"),
                    skill("classification", "构建再入院预测分类模型并评估性能"),
                    skill("feature_importance", "识别对再入院预测最重要的影响因素"),
                ],
            },
            {
                "id": "topic_3",
                "title": "基于聚类的肿瘤血液科住院患者分群与临床画像研究",
                "question": "住院患者能否按临床特征聚为若干亚群，各亚群有何画像特征？",
                "rationale": "就诊级宽表含年龄、住院天数、检验指标、诊断/用药等连续与"
                            "离散特征，万余次就诊样本充足，适合无监督聚类分群。",
                "feasibility": "高",
                "skills": [
                    skill("clustering", "对患者按临床特征进行无监督聚类分群"),
                    skill("dimensionality_reduction", "降维可视化各亚群的分布与分离度"),
                    skill("descriptive_stats", "描述各亚群的关键特征画像"),
                ],
            },
        ]

    # ========== 历史论文列表 ==========

    def list_history(self) -> list[dict]:
        """列出全部自动流水线任务（json_store 持久化记录 + 内存中尚未落盘的 running job），
        按 created_at 倒序，损坏的记录跳过。"""
        jobs: list[dict] = []
        seen: set[str] = set()

        for doc_id in json_store.list_all():
            if not doc_id.startswith("autojob_"):
                continue
            try:
                job = json_store.load(doc_id)
                if not isinstance(job, dict):
                    continue
                jobs.append(self._history_entry(job))
                seen.add(doc_id)
            except Exception:
                continue

        # 内存中尚未持久化的 running job（终态才落盘）
        with _JOBS_LOCK:
            running = [job for jid, job in _JOBS.items()
                       if jid not in seen and job.get("state") == "running"]
        for job in running:
            jobs.append(self._history_entry(job))

        jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        # 同一议题标题只保留创建时间最晚的一条（此时已按时间倒序）
        seen_titles: set[str] = set()
        deduped: list[dict] = []
        for j in jobs:
            title = j.get("topic_title")
            if title and title in seen_titles:
                continue
            if title:
                seen_titles.add(title)
            deduped.append(j)
        return deduped

    @staticmethod
    def _history_entry(job: dict) -> dict:
        return {
            "job_id": job.get("job_id"),
            "state": job.get("state"),
            "topic_title": (job.get("topic") or {}).get("title"),
            "paper_title": (job.get("paper") or {}).get("title"),
            "filename": job.get("filename"),
            "download_url": job.get("download_url"),
            "created_at": job.get("created_at"),
            "finished_at": job.get("finished_at"),
        }

    # ========== 自定义议题评估 ==========

    def evaluate_custom_topic(self, idea: str) -> dict:
        """LLM（临床科研方法学专家）评估用户自定义研究设想的数据可支撑性，
        返回 {"topic": {...}, "supported": bool}；失败时回落为不支持。"""
        try:
            return self._evaluate_custom_topic_llm(idea)
        except Exception:
            return {
                "topic": {
                    "id": "custom",
                    "title": idea.strip() or "自定义议题",
                    "question": "",
                    "rationale": "议题评估失败，可重试或从推荐议题中选择",
                    "feasibility": "低",
                    "skills": [],
                },
                "supported": False,
            }

    def _evaluate_custom_topic_llm(self, idea: str) -> dict:
        assets = dataset_service.detect_data_assets()
        assets_brief = [{
            "name": t["name"], "label": t["label"], "rows": t["rows"],
            "key_columns": t["key_columns"], "coverage_note": t["coverage_note"],
        } for t in assets["tables"]]

        profile = get_skill("dataset_profile").run({})
        profile_brief = {
            "summary": profile.get("summary", ""),
            "facts": profile.get("facts", {}),
        }

        catalog = [
            {"id": s["id"], "name": s["name"], "description": s["description"]}
            for skills in list_skills_by_category().values() for s in skills
        ]

        content = self.llm.chat(
            [{"role": "system", "content":
              "你是一位临床科研方法学专家，擅长评估基于真实世界数据的临床科研设想的可行性，"
              "并为其设计切实可行的分析路径。"},
             {"role": "user", "content":
              f"数据资产清单：\n{json.dumps(assets_brief, ensure_ascii=False)}\n\n"
              f"数据集真实画像：\n{json.dumps(profile_brief, ensure_ascii=False, default=str)}\n\n"
              f"可用分析算子目录：\n{json.dumps(catalog, ensure_ascii=False, indent=1)}\n\n"
              f"医生提出的研究设想：\n{idea}\n\n"
              "请评估该研究设想是否被上述数据支撑，并将其细化为可执行的研究议题。\n"
              "要求：\n"
              "1. rationale 必须引用数据画像中的真实数字说明数据是否支撑及原因；"
              "若数据不支撑，说明缺什么数据，并给出当前数据可支撑的修改建议；\n"
              "2. skills 只能从上述算子目录中选取 2-4 个，按合理分析顺序排列；\n"
              "3. 若数据明显不支撑，feasibility 必须为「低」，且 skills 给出当前数据下"
              "最接近的可行替代分析路径；\n"
              "4. 严格输出一个 JSON 对象，不要输出 markdown 代码块以外的任何文字。\n\n"
              '格式：{"title":"refined 论文级中文标题","question":"研究问题一句话",'
              '"rationale":"数据是否支撑及原因（引用真实数字）","feasibility":"高|中|低",'
              '"skills":[{"id":"算子id","purpose":"该算子在本议题中回答什么"}]}'}],
            temperature=0.3,
            max_tokens=2000,
            cache_namespace="research:custom_topic",
        )

        topic = self._parse_custom_topic(content)
        if topic is None:
            raise ValueError(f"议题评估解析失败: {content[:200]}")
        return {
            "topic": topic,
            "supported": topic["feasibility"] in ("高", "中"),
        }

    def _parse_custom_topic(self, content: str) -> dict | None:
        """从 LLM 回复中提取 JSON 对象，校验算子 id（不存在的换成语义最近的），补上算子中文名"""
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            return None
        item = json.loads(content[start:end + 1])
        if not isinstance(item, dict):
            return None

        skills = []
        for s in item.get("skills", []):
            if not isinstance(s, dict):
                continue
            skill = get_skill(str(s.get("id", "")))
            if skill is None:
                skill = self._nearest_skill(str(s.get("id", "")))
            if skill is None:
                continue
            skills.append({
                "id": skill.meta.id,
                "name": skill.meta.name,
                "purpose": str(s.get("purpose", "")),
            })

        return {
            "id": "custom",
            "title": str(item.get("title", "自定义议题")),
            "question": str(item.get("question", "")),
            "rationale": str(item.get("rationale", "")),
            "feasibility": str(item.get("feasibility", "低")),
            "skills": skills,
        }

    @staticmethod
    def _nearest_skill(bad_id: str) -> object | None:
        """为不存在的算子 id 找语义最近的目录内算子（先子串匹配，再 difflib 模糊匹配）"""
        catalog = [s for skills in list_skills_by_category().values() for s in skills]
        low = bad_id.strip().lower()
        if not low:
            return None
        for s in catalog:
            sid = str(s.get("id", "")).lower()
            if low in sid or sid in low:
                return get_skill(s["id"])
        import difflib
        ids = [str(s.get("id", "")) for s in catalog]
        matches = difflib.get_close_matches(low, ids, n=1, cutoff=0.4)
        return get_skill(matches[0]) if matches else None

    # ========== 自动流水线 ==========

    def start_pipeline(self, topic: dict) -> str:
        """创建流水线任务并后台执行，返回 job_id"""
        job_id = f"autojob_{uuid.uuid4().hex[:8]}"
        steps = [{"key": "profile", "label": "数据画像", "state": "pending",
                  "detail": "", "result_id": None}]
        for s in topic.get("skills", []):
            steps.append({
                "key": f"skill:{s.get('id', '')}",
                "label": f"算子：{s.get('name', s.get('id', ''))}",
                "state": "pending", "detail": "", "result_id": None,
            })
        steps.append({"key": "paper", "label": "论文生成", "state": "pending",
                      "detail": "", "result_id": None})

        job = {
            "job_id": job_id,
            "state": "running",
            "topic": topic,
            "steps": steps,
            "result_ids": [],
            "paper": None,
            "filename": None,
            "download_url": None,
            "error": None,
            "created_at": _now(),
            "finished_at": None,
        }
        with _JOBS_LOCK:
            _JOBS[job_id] = job

        threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        """先查内存，miss 查 json_store"""
        with _JOBS_LOCK:
            job = _JOBS.get(job_id)
        if job is not None:
            return job
        return json_store.load(job_id)

    def _update_step(self, job: dict, idx: int, state: str,
                     detail: str = "", result_id: str | None = None):
        with _JOBS_LOCK:
            step = job["steps"][idx]
            step["state"] = state
            if detail:
                step["detail"] = detail
            if result_id is not None:
                step["result_id"] = result_id

    def _run(self, job_id: str):
        """流水线主流程（后台线程）：数据画像 → 各算子 → 论文生成。
        捕所有异常，绝不让 job 永远停在 running。"""
        job = self.get_job(job_id)
        if job is None:
            return
        topic = job.get("topic", {})
        try:
            # 1) 数据画像（仅作上下文留痕，不纳入论文 result_ids）
            idx = 0
            self._update_step(job, idx, "running")
            try:
                profile = get_skill("dataset_profile").run({})
                facts = profile.get("facts", {})
                self._update_step(
                    job, idx, "done",
                    f"共 {facts.get('visit_count', '?')} 次就诊、"
                    f"{facts.get('patient_count', '?')} 名患者")
            except Exception as e:
                self._update_step(job, idx, "failed", f"数据画像失败：{e}")

            # 2) 顺序执行议题算子（默认参数，失败不中断后续）
            for i, s in enumerate(topic.get("skills", []), start=1):
                sid = s.get("id", "")
                self._update_step(job, i, "running")
                try:
                    record = research_assistant_service.run_skill(sid, {})
                    rid = record.get("result_id")
                    with _JOBS_LOCK:
                        job["result_ids"].append(rid)
                    summary = (record.get("result", {}).get("summary") or "").strip()
                    detail = summary.split("\n")[0][:80] if summary else "执行完成"
                    self._update_step(job, i, "done", detail, result_id=rid)
                except Exception as e:
                    self._update_step(job, i, "failed", f"算子执行失败：{e}")

            # 3) 论文生成（要求至少 1 个成功 result_id）
            paper_idx = len(job["steps"]) - 1
            self._update_step(job, paper_idx, "running")
            with _JOBS_LOCK:
                result_ids = list(job["result_ids"])
            if not result_ids:
                raise RuntimeError("所有算子均执行失败，无法生成论文")
            paper = research_assistant_service.generate_paper(
                question=topic.get("question", ""),
                result_ids=result_ids,
                articles=[],
                title=topic.get("title") or None,
            )
            with _JOBS_LOCK:
                job["paper"] = paper.get("paper")
                job["filename"] = paper.get("filename")
                job["download_url"] = paper.get("download_url")
            title = (job.get("paper") or {}).get("title", "")
            self._update_step(job, paper_idx, "done", f"论文已生成：{title}")

            with _JOBS_LOCK:
                job["state"] = "done"
                job["finished_at"] = _now()
        except Exception as e:
            with _JOBS_LOCK:
                job["state"] = "failed"
                job["error"] = str(e)
                job["finished_at"] = _now()
            # 将仍处于 running/pending 的步骤标记为 failed，避免前端轮询悬挂
            for i, step in enumerate(job["steps"]):
                if step["state"] in ("running", "pending"):
                    self._update_step(job, i, "failed", "流水线中断")
        finally:
            # 终态落盘（内存对象即最终状态，整体序列化）
            try:
                json_store.save(job_id, json.loads(json.dumps(job, default=str)))
            except Exception:
                pass


# 全局单例
auto_research_service = AutoResearchService()
