"""论文流水线 P0 优化单元测试：引用-断言核验、质检→修订闭环。"""
from services.research.research_assistant_service import ResearchAssistantService

SVC = ResearchAssistantService.__new__(ResearchAssistantService)  # 不触发单例依赖

ARTICLES = [
    {"title": "Readmission risk in heart failure", "abstract": "We studied 1000 HF patients and found age predicts readmission."},
    {"title": "Deep learning for images", "abstract": "A survey of CNN architectures for image classification."},
]


class FakeLLM:
    """记录 prompt 并按预设返回"""
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def chat(self, messages, **kw):
        self.prompts.append(messages[-1]["content"])
        return self.reply


# ---------- 引用标记提取 ----------

def test_extract_citation_items():
    sections = {
        "前言": "再入院是重要负性指标[1]。本研究旨在分析。",
        "讨论": "这与影像研究结论一致[2]。无标记句子。编号超范围[9]忽略。",
        "结果": "结果章节不提取[1]。",
    }
    items = SVC._extract_citation_items(sections, ARTICLES)
    assert len(items) == 2
    assert items[0]["ref_no"] == 1 and "再入院是重要负性指标" in items[0]["sentence"]
    assert items[1]["ref_no"] == 2
    assert items[0]["ref_title"] == ARTICLES[0]["title"]


def test_remove_citation_marker_only_in_sentence():
    content = "首句引用[1]。这与影像研究一致[2]，但不支持。尾句也提[2]。"
    sentence = "这与影像研究一致[2]，但不支持。"
    out = SVC._remove_citation_marker(content, sentence, 2)
    assert out == "首句引用[1]。这与影像研究一致，但不支持。尾句也提[2]。"


def test_remove_citation_marker_sentence_not_found():
    content = "句子引用[3]。"
    assert SVC._remove_citation_marker(content, "不存在的句子", 3) == content


# ---------- 引用核验（mock LLM） ----------

def test_verify_citations_removes_unsupported(monkeypatch):
    svc = SVC
    fake = FakeLLM('{"unsupported": [1]}')
    monkeypatch.setattr(svc, "llm", fake, raising=False)
    sections = {
        "前言": "再入院是重要负性指标[1]。",
        "讨论": "这与影像研究结论一致[2]。",
    }
    out = svc._verify_citations(sections, ARTICLES)
    assert "[1]" in out["前言"]          # item 0 被判支持，保留
    assert "[2]" not in out["讨论"]      # item 1 不支持，移除


def test_verify_citations_llm_failure_keeps_text(monkeypatch):
    svc = SVC
    monkeypatch.setattr(svc, "llm", FakeLLM("[LLM调用失败] timeout"), raising=False)
    sections = {"前言": "再入院是重要负性指标[1]。"}
    out = svc._verify_citations(sections, ARTICLES)
    assert out["前言"] == sections["前言"]


def test_verify_citations_bad_json_keeps_text(monkeypatch):
    svc = SVC
    monkeypatch.setattr(svc, "llm", FakeLLM("都不是不支持的"), raising=False)
    sections = {"前言": "再入院是重要负性指标[1]。"}
    assert svc._verify_citations(sections, ARTICLES) == sections


# ---------- 质检 → 修订闭环 ----------

def test_revise_sections_carries_suspicious_numbers(monkeypatch):
    svc = SVC
    fake = FakeLLM("修订后正文")
    monkeypatch.setattr(svc, "llm", fake, raising=False)
    sections = {sec: f"{sec}正文" for sec in svc.PAPER_SECTIONS}
    suspicious = [{"section": "结果", "value": "99.9",
                   "context": "再入院率为 99.9%。"}]
    svc._revise_sections("上下文", sections, "评审意见", suspicious)
    # 每个章节都被修订；只有「结果」章的 prompt 含可疑数字清单
    assert len(fake.prompts) == len(svc.PAPER_SECTIONS)
    result_prompt = fake.prompts[svc.PAPER_SECTIONS.index("结果")]
    assert "99.9" in result_prompt and "逐条处理" in result_prompt
    abstract_prompt = fake.prompts[0]
    assert "99.9" not in abstract_prompt


def test_revise_sections_without_review(monkeypatch):
    # 评审为空但有可疑数字时也应修订，且 prompt 不含审稿意见块
    svc = SVC
    fake = FakeLLM("修订后正文")
    monkeypatch.setattr(svc, "llm", fake, raising=False)
    sections = {sec: f"{sec}正文" for sec in svc.PAPER_SECTIONS}
    svc._revise_sections("上下文", sections, "", [{"section": "摘要", "value": "1.5", "context": "占比1.5%"}])
    assert "审稿意见" not in fake.prompts[0]
    assert "1.5" in fake.prompts[0]
