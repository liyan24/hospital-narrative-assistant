"""skill_packs 适配层单元测试：数字一致性校验、GB/T 7714 格式化、规范块降级路径。"""
from services.research.skill_packs import guidance, quality, references
from services.research.skill_packs.paths import skill_dir, skill_file


# ---------- 数字一致性校验 ----------

def test_number_match_exact_and_percent():
    facts = {"rate": 0.234, "n": 3990, "mean_age": 58.6}
    sections = {"结果": "共纳入 3990 名患者，再入院率为 23.4%，平均年龄 58.6 岁。"}
    report = quality.check_number_consistency(sections, facts)
    assert report["suspicious_numbers"] == []
    assert report["facts_number_count"] >= 3


def test_number_suspicious_detected():
    facts = {"rate": 0.234, "n": 3990}
    sections = {"结果": "再入院率为 31.2%，p=0.03。"}
    report = quality.check_number_consistency(sections, facts)
    values = [s["value"] for s in report["suspicious_numbers"]]
    assert "31.2" in values and "0.03" in values
    assert all(s["section"] == "结果" for s in report["suspicious_numbers"])


def test_number_filters_years_and_small_ints():
    sections = {"前言": "2023 年发布的指南提出 3 类分型。"}
    report = quality.check_number_consistency(sections, {"n": 100})
    assert report["suspicious_numbers"] == []


def test_number_facts_from_strings():
    # facts 中字符串化的数字也应参与比对
    facts = {"desc": "再入院率 18.5%"}
    sections = {"结果": "再入院率为 18.5%。"}
    report = quality.check_number_consistency(sections, facts)
    assert report["suspicious_numbers"] == []


def test_number_thousand_separator():
    # 千分位空格不应被拆成碎片误报
    facts = {"patients": 3990, "visits": 13743}
    sections = {"结果": "共纳入 3 990 例患者、13 743 次就诊记录。"}
    report = quality.check_number_consistency(sections, facts)
    assert report["suspicious_numbers"] == []


def test_number_scientific_notation():
    # p 值科学计数法整体比对，不拆出 10/8 等碎片
    facts = {"p_age": 2.3e-08, "n": 100}
    sections = {"结果": "年龄组间差异显著（p=2.30×10⁻⁸），共 100 例。"}
    report = quality.check_number_consistency(sections, facts)
    assert report["suspicious_numbers"] == []


def test_number_sci_in_facts_string():
    # facts 字符串中的 "2.30e-08" 不应被拆成 2.30 和 08，正文 p=2.30×10⁻⁸ 应匹配
    facts = {"numeric_tests": [{"var": "age", "p": "2.30e-08"}]}
    sections = {"结果": "年龄差异显著（p=2.30×10⁻⁸）。"}
    report = quality.check_number_consistency(sections, facts)
    assert report["suspicious_numbers"] == []


def test_number_ascii_sci_in_text():
    # 正文写 p=5.19e-06（e 记法），facts 字符串含 "5.19e-06"，应匹配不误报
    facts = {"numeric_tests": [{"var": "los", "p": "5.19e-06"}]}
    sections = {"结果": "住院天数差异显著（P=5.19e-06）。"}
    report = quality.check_number_consistency(sections, facts)
    assert report["suspicious_numbers"] == []


def test_number_dedup_and_sentence_context():
    facts = {"n": 100}
    sections = {"结果": "有效率为 55.5%。另一项指标也为 55.5%。"}
    report = quality.check_number_consistency(sections, facts)
    assert len(report["suspicious_numbers"]) == 1
    ctx = report["suspicious_numbers"][0]["context"]
    assert "……" not in ctx and "55.5%" in ctx


def test_number_skips_section_numbers_and_thresholds():
    facts = {"n": 100}
    sections = {"结果": "#### 3.1 患者特征\n2.4 统计方法\n纳入年龄≥65 岁的患者，有效率 55.5%。"}
    report = quality.check_number_consistency(sections, facts)
    values = [s["value"] for s in report["suspicious_numbers"]]
    assert "3.1" not in values and "2.4" not in values and "65" not in values
    assert "55.5" in values


# ---------- lint 过滤与中文映射 ----------

def test_lint_skip_and_cn_mapping():
    assert quality._is_lint_skipped("CONFIDENTIALITY_GATE_NOT_CHECKED")
    assert quality._is_lint_skipped("MANIFEST_MISSING")
    assert quality._is_lint_skipped("")
    assert not quality._is_lint_skipped("PLACEHOLDER_TODO")
    assert "占位符" in quality._lint_message_cn("PLACEHOLDER_TODO", "")
    assert "因果" in quality._lint_message_cn("CAUSAL_LANGUAGE", "")
    # 未知名：返回原码，不输出英文长句
    assert quality._lint_message_cn("SOME_NEW_RULE", "english message") == "SOME_NEW_RULE"


# ---------- GB/T 7714 格式化 ----------

def test_gbt7714_full_entry():
    articles = [{
        "title": "A test study.", "authors": ["Zhang S", "Li M", "Wang J", "Liu X"],
        "journal": "Lancet Oncology", "year": "2023",
        "volume": "24", "issue": "3", "pages": "100-108", "doi": "10.1/abc",
    }]
    text = references.format_gbt7714(articles)
    assert text.startswith("[1] Zhang S, Li M, Wang J, et al. A test study[J].")
    assert "Lancet Oncology, 2023, 24(3): 100-108." in text
    assert "DOI: 10.1/abc." in text


def test_gbt7714_missing_fields_fallback_pmid():
    articles = [{"title": "Study", "authors": ["Zhang S"], "journal": "", "year": "2022",
                 "pmid": "12345"}]
    text = references.format_gbt7714(articles)
    assert "[1] Zhang S. Study[J]. 2022. PMID: 12345." == text


def test_gbt7714_empty():
    assert references.format_gbt7714([]) == ""


# ---------- 规范块与路径降级 ----------

def test_guidance_blocks_nonempty():
    assert "证据绑定" in guidance.writing_rules()
    assert "混杂" in guidance.critical_checklist()
    assert "创新性" in guidance.review_dimensions()


def test_paths_skill_dir_resolution():
    # .agents/skills 存在时应能定位；不存在时返回 None 而不抛异常
    d = skill_dir("scientific-writing")
    if d is not None:
        assert d.is_dir()
    assert skill_dir("nonexistent-skill-xyz") is None
    assert skill_file("nonexistent-skill-xyz", "scripts", "a.py") is None


def test_enrich_articles_offline_graceful(monkeypatch):
    # 网络异常时原样返回，不抛异常
    import requests

    def boom(*a, **k):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(references.requests, "get", boom)
    articles = [{"pmid": "1", "title": "T"}]
    assert references.enrich_articles(articles) == articles
