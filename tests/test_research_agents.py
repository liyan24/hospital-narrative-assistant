"""P1/P2 优化单元测试：锦标赛择优、文献多查询扩展与重排、人在环大纲确认。"""
import json
import pytest

from services.research import auto_research_service as ars_mod
from services.research.auto_research_service import AutoResearchService
from services.research.research_assistant_service import ResearchAssistantService
from services.research.skills.writing import LiteratureSearchSkill


class FakeLLM:
    """按命名空间/关键字返回预设内容，并记录 prompt"""
    def __init__(self, replies: dict[str, str], default: str = "默认文本"):
        self.replies = replies
        self.default = default
        self.calls = []

    def chat(self, messages, **kw):
        ns = kw.get("cache_namespace", "")
        self.calls.append((ns, messages[-1]["content"]))
        for key, val in self.replies.items():
            if key in ns:
                return val
        return self.default


def make_svc(llm):
    svc = ResearchAssistantService.__new__(ResearchAssistantService)
    svc.llm = llm
    return svc


# ---------- 大纲锦标赛 ----------

def test_outline_tournament_judges_two_candidates():
    class VaryingLLM(FakeLLM):
        def __init__(self):
            super().__init__({"outline_judge": "融合后的最终大纲" + "x" * 200})
            self.n = 0

        def chat(self, messages, **kw):
            ns = kw.get("cache_namespace", "")
            self.calls.append((ns, messages[-1]["content"]))
            if "outline_judge" in ns:
                return self.replies["outline_judge"]
            self.n += 1
            return f"大纲候选{self.n}"  # 两个不同候选才会触发评审

    llm = VaryingLLM()
    svc = make_svc(llm)
    out = svc._gen_outline("上下文")
    nss = [ns for ns, _ in llm.calls]
    assert nss.count("research:paper_outline_auto") == 2  # 两个候选
    assert "research:outline_judge" in nss                # 评审择优
    assert out.startswith("融合后的最终大纲")


def test_outline_tournament_fallback_single_candidate():
    # 第二次生成失败 → 直接用唯一候选；评审失败 → 回落第一候选
    llm = FakeLLM({"paper_outline_auto": "[LLM调用失败] x"})
    svc = make_svc(llm)
    assert svc._gen_outline("上下文") == ""

    class OneShotLLM(FakeLLM):
        def __init__(self):
            super().__init__({})
            self.n = 0

        def chat(self, messages, **kw):
            ns = kw.get("cache_namespace", "")
            if ns == "research:paper_outline_auto":
                self.n += 1
                return "大纲甲" if self.n == 1 else "[LLM调用失败] y"
            return self.default

    svc2 = make_svc(OneShotLLM())
    assert svc2._gen_outline("上下文") == "大纲甲"


# ---------- 议题锦标赛排序 ----------

def test_rank_topics_reorders():
    svc = AutoResearchService.__new__(AutoResearchService)
    svc.llm = FakeLLM({"topic_rank": '["t2","t1"]'})
    topics = [{"id": "t1", "title": "甲"}, {"id": "t2", "title": "乙"}, {"id": "t3", "title": "丙"}]
    ranked = svc._rank_topics(topics, {"facts": {}})
    assert [t["id"] for t in ranked] == ["t2", "t1", "t3"]  # 未提及的追加在后


def test_rank_topics_fallback_on_garbage():
    svc = AutoResearchService.__new__(AutoResearchService)
    svc.llm = FakeLLM({"topic_rank": "无法解析的回复"})
    topics = [{"id": "t1"}, {"id": "t2"}]
    assert svc._rank_topics(topics, {"facts": {}}) == topics


# ---------- 文献多查询扩展与重排 ----------

def test_expand_queries_fallback_on_llm_failure(monkeypatch):
    skill = LiteratureSearchSkill()
    monkeypatch.setattr("services.research.skills.writing._chat",
                        lambda *a, **k: "[LLM调用失败] x")
    assert skill._expand_queries("lymphoma") == ["lymphoma"]


def test_expand_queries_parses_lines(monkeypatch):
    skill = LiteratureSearchSkill()
    monkeypatch.setattr("services.research.skills.writing._chat",
                        lambda *a, **k: "1. lymphoma prognosis\n2. blood cancer outcomes\nlymphoma")
    qs = skill._expand_queries("lymphoma")
    assert qs == ["lymphoma", "lymphoma prognosis", "blood cancer outcomes"]


def test_rerank_orders_by_llm(monkeypatch):
    skill = LiteratureSearchSkill()
    monkeypatch.setattr("services.research.skills.writing._chat",
                        lambda *a, **k: "[2, 0]")
    arts = [{"title": f"t{i}"} for i in range(5)]
    out = skill._rerank("q", arts, 3)
    assert [a["title"] for a in out] == ["t2", "t0", "t1"]  # 选中+补齐至 max_results


def test_rerank_fallback_on_failure(monkeypatch):
    skill = LiteratureSearchSkill()
    monkeypatch.setattr("services.research.skills.writing._chat",
                        lambda *a, **k: "[LLM调用失败] x")
    arts = [{"title": f"t{i}"} for i in range(5)]
    assert [a["title"] for a in skill._rerank("q", arts, 2)] == ["t0", "t1"]


# ---------- 关键章节 best-of-2 ----------

def test_best_of_two_judge_wins():
    llm = FakeLLM({"section_judge": "择优后的最终版本" + "x" * 100})
    svc = make_svc(llm)
    out = svc._best_of_two("上下文", "摘要", "prompt", "第一稿")
    assert out.startswith("择优后的最终版本")


def test_best_of_two_fallback_when_second_fails():
    class FailSecond(FakeLLM):
        def chat(self, messages, **kw):
            if kw.get("temperature") == 0.7:
                return "[LLM调用失败] x"
            return "其他"

    svc = make_svc(FailSecond({}))
    assert svc._best_of_two("上下文", "摘要", "prompt", "第一稿") == "第一稿"


# ---------- 人在环大纲确认 ----------

def _make_awaiting_job():
    job = {
        "job_id": "autojob_testhitl", "state": "awaiting_outline",
        "topic": {"title": "测试议题", "question": "q"},
        "steps": [{"key": "outline", "label": "大纲确认", "state": "done",
                   "detail": "", "result_id": None},
                  {"key": "paper", "label": "论文生成", "state": "pending",
                   "detail": "", "result_id": None}],
        "result_ids": ["r1"], "articles": [], "outline": "大纲草稿",
        "paper_params": {"question": "q", "result_ids": ["r1"], "articles": [], "title": "t"},
        "paper": None, "quality_report": None, "review": None,
        "filename": None, "download_url": None, "error": None,
        "created_at": "", "finished_at": None,
    }
    with ars_mod._JOBS_LOCK:
        ars_mod._JOBS[job["job_id"]] = job
    return job


def test_confirm_outline_state_guard():
    svc = AutoResearchService.__new__(AutoResearchService)
    with pytest.raises(ValueError):
        svc.confirm_outline("autojob_nonexistent", "大纲")


def test_run_paper_uses_confirmed_outline(monkeypatch):
    job = _make_awaiting_job()
    captured = {}

    class FakeRAS:
        def generate_paper(self, **kw):
            captured.update(kw)
            return {"paper": {"title": "t", "sections": {}}, "filename": "f.docx",
                    "download_url": "/x", "quality_report": None, "review": ""}

    monkeypatch.setattr(ars_mod, "research_assistant_service", FakeRAS())
    svc = AutoResearchService.__new__(AutoResearchService)
    svc._run_paper(job["job_id"])
    assert captured["outline"] == "大纲草稿"
    assert job["state"] == "done" and job["filename"] == "f.docx"
    with ars_mod._JOBS_LOCK:
        ars_mod._JOBS.pop(job["job_id"], None)


def test_run_paper_empty_outline_falls_back_to_auto(monkeypatch):
    job = _make_awaiting_job()
    job["outline"] = "   "
    captured = {}

    class FakeRAS:
        def generate_paper(self, **kw):
            captured.update(kw)
            return {"paper": {"title": "t", "sections": {}}, "filename": "f.docx",
                    "download_url": "/x", "quality_report": None, "review": ""}

    monkeypatch.setattr(ars_mod, "research_assistant_service", FakeRAS())
    svc = AutoResearchService.__new__(AutoResearchService)
    svc._run_paper(job["job_id"])
    assert captured["outline"] is None  # 留空 → 自动锦标赛生成
    with ars_mod._JOBS_LOCK:
        ars_mod._JOBS.pop(job["job_id"], None)
