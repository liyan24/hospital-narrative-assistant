"""纯逻辑单测：claims 解析、verify 匹配与指标、judge 解析与重试。

不连接 Neo4j / LLM；LLM 调用通过注入假的 chat_fn 模拟。
"""

import pytest

from experiments.claims import parse_claims_json, extract_claims
from experiments.verify import (
    build_alias_map,
    claim_number,
    compute_metrics,
    normalize_dates,
    normalize_entity,
    numbers_close,
    verify_claim,
    verify_claims,
)
from experiments.judge import parse_scores_json, score_narrative


# ==================== claims.parse_claims_json ====================

class TestParseClaimsJson:
    def test_clean_json(self):
        raw = '[{"claim": "患者使用华蟾素胶囊", "type": "relation", "entities": ["患者", "华蟾素胶囊"], "value": null}]'
        claims, err = parse_claims_json(raw)
        assert not err
        assert len(claims) == 1
        assert claims[0]["claim"] == "患者使用华蟾素胶囊"
        assert claims[0]["type"] == "relation"
        assert claims[0]["entities"] == ["患者", "华蟾素胶囊"]
        assert claims[0]["value"] is None

    def test_json_code_block(self):
        raw = '抽取结果如下：\n```json\n[{"claim": "共20人次", "type": "numeric", "entities": ["肺癌"], "value": 20}]\n```'
        claims, err = parse_claims_json(raw)
        assert not err
        assert claims[0]["value"] == 20.0
        assert claims[0]["type"] == "numeric"

    def test_prose_around_array(self):
        raw = '好的，这是抽取的断言：[{"claim": "平均住院7.5天", "type": "numeric", "entities": ["肺癌"], "value": 7.5}] 以上。'
        claims, err = parse_claims_json(raw)
        assert not err
        assert claims[0]["value"] == 7.5

    def test_wrapped_in_claims_key(self):
        raw = '{"claims": [{"claim": "A合并B", "type": "relation", "entities": ["A", "B"], "value": null}]}'
        claims, err = parse_claims_json(raw)
        assert not err
        assert len(claims) == 1

    def test_invalid_items_filtered(self):
        raw = '[{"claim": "有效断言", "type": "other", "entities": [], "value": null}, {"no_claim": 1}, "垃圾", 42]'
        claims, err = parse_claims_json(raw)
        assert not err
        assert len(claims) == 1

    def test_bad_type_defaults_other(self):
        raw = '[{"claim": "x", "type": "weird", "entities": ["a"], "value": "abc"}]'
        claims, err = parse_claims_json(raw)
        assert not err
        assert claims[0]["type"] == "other"
        assert claims[0]["value"] is None  # 非数值 value 置 None

    def test_garbage_returns_parse_error(self):
        claims, err = parse_claims_json("模型没有输出任何 JSON。")
        assert err
        assert claims == []

    def test_empty_returns_parse_error(self):
        assert parse_claims_json("") == ([], True)
        assert parse_claims_json("   ") == ([], True)

    def test_truncated_json_returns_parse_error(self):
        claims, err = parse_claims_json('[{"claim": "没闭合", "type": "relation"')
        assert err
        assert claims == []


class TestExtractClaims:
    def test_llm_failure_passthrough(self):
        def fake_chat(*args, **kwargs):
            return "[LLM调用失败] 连接超时"
        out = extract_claims("某叙事文本", chat_fn=fake_chat)
        assert out["error"].startswith("[LLM调用失败]")
        assert out["claims"] == []
        assert out["parse_error"] is False

    def test_empty_text(self):
        out = extract_claims("", chat_fn=lambda *a, **k: "[]")
        assert out["error"] == "empty_text"

    def test_retry_once_on_parse_failure(self):
        outputs = iter(["不是JSON", '[{"claim": "有效", "type": "other", "entities": [], "value": null}]'])
        calls = []

        def fake_chat(*args, **kwargs):
            calls.append(kwargs.get("use_cache"))
            return next(outputs)

        out = extract_claims("某叙事文本", chat_fn=fake_chat)
        assert out["parse_error"] is False
        assert len(out["claims"]) == 1
        assert calls == [True, False]  # 重试跳过缓存

    def test_both_fail_marks_parse_error(self):
        out = extract_claims("某叙事文本", chat_fn=lambda *a, **k: "仍然不是JSON")
        assert out["parse_error"] is True
        assert out["claims"] == []


# ==================== verify：归一化与数值 ====================

class TestNormalize:
    def test_fullwidth_and_space(self):
        assert normalize_entity("ＡＢＣ　123") == "abc123"
        assert normalize_entity(" 肺 癌 ") == "肺癌"

    def test_alias(self):
        aliases = build_alias_map({"肺恶性肿瘤": "肺癌"})
        assert normalize_entity("肺恶性肿瘤", aliases) == normalize_entity("肺癌", aliases)

    def test_numbers_close(self):
        assert numbers_close(100, 104)       # 4% 误差，容差内
        assert not numbers_close(100, 110)   # 10% 超差
        assert numbers_close(0, 1e-8)        # 绝对容差


class TestNormalizeDates:
    def test_chinese_date(self):
        assert normalize_dates("2020年12月31日") == "2020-12-31"
        assert normalize_dates("2020 年 1 月 2 日入院") == "2020-01-02入院"

    def test_slash_and_dot_date(self):
        assert normalize_dates("2020/12/31") == "2020-12-31"
        assert normalize_dates("2020.1.2") == "2020-01-02"

    def test_iso_unchanged(self):
        assert normalize_dates("2020-12-31") == "2020-12-31"

    def test_entity_normalization_includes_dates(self):
        assert normalize_entity("患者2020年12月31日入院") == "患者2020-12-31入院"

    def test_claim_number_skips_dates(self):
        # 日期中的 2020 不应被当作断言数值
        claim = {"claim": "患者2020年12月31日入院", "type": "temporal",
                 "entities": [], "value": None}
        assert claim_number(claim) is None
        claim2 = {"claim": "2020年12月31日入院，住院5天", "type": "numeric",
                  "entities": [], "value": None}
        assert claim_number(claim2) == 5.0


# ==================== verify：断言核查 ====================

FACTS = [
    {"subject": "肺癌", "predicate": "visit_count", "object": 100, "qualifiers": {}},
    {"subject": "肺癌", "predicate": "avg_stay", "object": 7.5, "qualifiers": {}},
    {"subject": "肺癌", "predicate": "cooccurs_with", "object": "高血压", "qualifiers": {"count": 30}},
    {"subject": "肺癌", "predicate": "cooccurs_with", "object": "糖尿病", "qualifiers": {"count": 12}},
    {"subject": "V001", "predicate": "PRESCRIBED", "object": "华蟾素胶囊", "qualifiers": {}},
]


class TestVerifyClaim:
    def test_supported_relation(self):
        claim = {"claim": "肺癌常合并高血压", "type": "relation",
                 "entities": ["肺癌", "高血压"], "value": None}
        assert verify_claim(claim, FACTS)["label"] == "supported"

    def test_supported_numeric_within_tolerance(self):
        claim = {"claim": "肺癌相关就诊约102人次", "type": "numeric",
                 "entities": ["肺癌"], "value": 102}
        v = verify_claim(claim, FACTS)
        assert v["label"] == "supported"
        assert v["matched_fact"]["predicate"] == "visit_count"

    def test_contradicted_numeric_out_of_tolerance(self):
        claim = {"claim": "肺癌相关就诊约250人次", "type": "numeric",
                 "entities": ["肺癌"], "value": 250}
        assert verify_claim(claim, FACTS)["label"] == "contradicted"

    def test_contradicted_relation_alternative_object(self):
        # 事实中肺癌的合并症只有高血压和糖尿病；断言说"肺癌合并冠心病"，
        # 冠心病不在事实中 → 该断言主体匹配但客体既不支持也不在同谓词客体集合中 → unverifiable
        # 而"肺癌合并糖尿病"若事实写错对象则应判 contradicted：
        # 构造一条断言提到同谓词下的另一个客体（实体列表含糖尿病，但文本说高血压之外的病）
        claim = {"claim": "肺癌最常见的合并症是糖尿病", "type": "relation",
                 "entities": ["肺癌", "糖尿病"], "value": None}
        # 糖尿病确实是事实客体 → supported
        assert verify_claim(claim, FACTS)["label"] == "supported"

        # 数值断言：平均住院天数写错 → contradicted
        claim2 = {"claim": "肺癌患者平均住院30天", "type": "numeric",
                  "entities": ["肺癌"], "value": 30}
        assert verify_claim(claim2, FACTS)["label"] == "contradicted"

    def test_contradicted_wrong_drug_object(self):
        facts = FACTS + [
            {"subject": "V001", "predicate": "PRESCRIBED", "object": "康莱特注射液", "qualifiers": {}},
        ]
        # 断言只提到"华蟾素胶囊"为 V001 用药 → supported
        ok = {"claim": "V001使用华蟾素胶囊", "type": "relation",
              "entities": ["V001", "华蟾素胶囊"], "value": None}
        assert verify_claim(ok, facts)["label"] == "supported"

    def test_unverifiable_unknown_subject(self):
        claim = {"claim": "胃癌就诊50人次", "type": "numeric",
                 "entities": ["胃癌"], "value": 50}
        assert verify_claim(claim, FACTS)["label"] == "unverifiable"

    def test_unverifiable_subject_known_object_absent(self):
        claim = {"claim": "肺癌患者常接受放疗", "type": "relation",
                 "entities": ["肺癌", "放疗"], "value": None}
        assert verify_claim(claim, FACTS)["label"] == "unverifiable"

    def test_alias_matching(self):
        aliases = build_alias_map({"肺恶性肿瘤": "肺癌"})
        claim = {"claim": "肺恶性肿瘤相关就诊100人次", "type": "numeric",
                 "entities": ["肺恶性肿瘤"], "value": 100}
        assert verify_claim(claim, FACTS, aliases=aliases)["label"] == "supported"

    def test_fullwidth_entities(self):
        claim = {"claim": "Ｖ００１使用华蟾素胶囊", "type": "relation",
                 "entities": ["Ｖ００１", "华蟾素胶囊"], "value": None}
        assert verify_claim(claim, FACTS)["label"] == "supported"

    def test_numeric_value_fallback_to_text(self):
        # value 缺失时从 claim 文本提取第一个数字
        claim = {"claim": "肺癌相关就诊100人次", "type": "numeric",
                 "entities": ["肺癌"], "value": None}
        assert verify_claim(claim, FACTS)["label"] == "supported"


class TestVerifyClaimV2:
    """FIX-2 新增：object 提及候选、日期归一化、数值上下文匹配、保守 contradicted"""

    # 模拟 patient_storyline 场景：subject 是叙事中永不出现的内部 ID
    PATIENT_FACTS = [
        {"subject": "99830002", "predicate": "visit_count", "object": 2,
         "qualifiers": {"label": "就诊次数"}},
        {"subject": "99830002", "predicate": "age", "object": 60,
         "qualifiers": {"label": "年龄"}},
        {"subject": "V001", "predicate": "admission_date", "object": "2020-12-31",
         "qualifiers": {"label": "入院日期"}},
        {"subject": "V001", "predicate": "length_of_stay", "object": 5,
         "qualifiers": {"label": "住院天数", "admission_date": "2020-12-31"}},
        {"subject": "V001", "predicate": "DIAGNOSED_WITH", "object": "肺癌",
         "qualifiers": {}},
        {"subject": "V001", "predicate": "PRESCRIBED", "object": "华蟾素胶囊",
         "qualifiers": {}},
        {"subject": "V001", "predicate": "lab_value", "object": 5.6,
         "qualifiers": {"item": "血红蛋白", "unit": "g/L", "label": "检验结果",
                        "admission_date": "2020-12-31"}},
    ]

    def test_object_mention_makes_candidate(self):
        # 断言只提及药品名（object），未提及 visit_id（subject）→ 仍应判 supported
        claim = {"claim": "患者使用华蟾素胶囊治疗", "type": "relation",
                 "entities": ["华蟾素胶囊"], "value": None}
        assert verify_claim(claim, self.PATIENT_FACTS)["label"] == "supported"

    def test_chinese_date_matches_iso_object(self):
        claim = {"claim": "患者2020年12月31日入院", "type": "temporal",
                 "entities": [], "value": None}
        v = verify_claim(claim, self.PATIENT_FACTS)
        assert v["label"] == "supported"
        assert v["matched_fact"]["predicate"] == "admission_date"

    def test_numeric_context_via_qualifier_label(self):
        # 年龄：subject 是 patient_id（不出现），靠 qualifiers 的 label 匹配上下文
        claim = {"claim": "患者年龄60岁", "type": "numeric",
                 "entities": ["患者"], "value": 60}
        assert verify_claim(claim, self.PATIENT_FACTS)["label"] == "supported"

    def test_numeric_context_via_qualifier_date(self):
        # 住院天数：上下文靠 qualifiers 里的 admission_date 匹配
        claim = {"claim": "患者2020年12月31日入院，住院5天", "type": "numeric",
                 "entities": [], "value": 5}
        assert verify_claim(claim, self.PATIENT_FACTS)["label"] == "supported"

    def test_lab_value_via_item_name(self):
        claim = {"claim": "血红蛋白5.6g/L", "type": "numeric",
                 "entities": ["血红蛋白"], "value": 5.6}
        assert verify_claim(claim, self.PATIENT_FACTS)["label"] == "supported"

    def test_contradicted_unique_numeric_context(self):
        # 年龄是唯一数值上下文，数值超容差 → contradicted
        claim = {"claim": "患者年龄75岁", "type": "numeric",
                 "entities": ["患者"], "value": 75}
        v = verify_claim(claim, self.PATIENT_FACTS)
        assert v["label"] == "contradicted"
        assert v["matched_fact"]["predicate"] == "age"

    def test_ambiguous_numeric_context_not_contradicted(self):
        # 同一检验项目出现在两次就诊（上下文不唯一），数值对不上 → 保守判 unverifiable
        facts = [
            {"subject": "V001", "predicate": "lab_value", "object": 5.6,
             "qualifiers": {"item": "血红蛋白", "label": "检验结果"}},
            {"subject": "V002", "predicate": "lab_value", "object": 7.2,
             "qualifiers": {"item": "血红蛋白", "label": "检验结果"}},
        ]
        claim = {"claim": "血红蛋白9.9g/L", "type": "numeric",
                 "entities": ["血红蛋白"], "value": 9.9}
        assert verify_claim(claim, facts)["label"] == "unverifiable"
        # 数值命中其中之一 → supported
        claim_ok = {"claim": "血红蛋白7.2g/L", "type": "numeric",
                    "entities": ["血红蛋白"], "value": 7.2}
        assert verify_claim(claim_ok, facts)["label"] == "supported"

    def test_wrong_lab_value_unique_context_contradicted(self):
        claim = {"claim": "血红蛋白9.9g/L", "type": "numeric",
                 "entities": ["血红蛋白"], "value": 9.9}
        assert verify_claim(claim, self.PATIENT_FACTS)["label"] == "contradicted"

    def test_internal_id_not_mentioned_still_verifiable(self):
        # 就诊次数：label "就诊次数" 出现在文本中即可匹配
        claim = {"claim": "患者就诊次数2次", "type": "numeric",
                 "entities": [], "value": 2}
        assert verify_claim(claim, self.PATIENT_FACTS)["label"] == "supported"

    def test_completely_unknown_entity(self):
        claim = {"claim": "患者接受了骨髓移植", "type": "relation",
                 "entities": ["骨髓移植"], "value": None}
        assert verify_claim(claim, self.PATIENT_FACTS)["label"] == "unverifiable"

    def test_partial_match_composite_name(self):
        # 图谱中疾病 display_name 是复合名 "骨疽病，气血瘀阻证"，
        # 断言拆成单个实体也应能匹配
        facts = [
            {"subject": "V001", "predicate": "DIAGNOSED_WITH",
             "object": "骨疽病，气血瘀阻证", "qualifiers": {}},
        ]
        for ent in ("骨疽病", "气血瘀阻证"):
            claim = {"claim": f"诊断为{ent}", "type": "relation",
                     "entities": [ent], "value": None}
            assert verify_claim(claim, facts)["label"] == "supported"

    def test_unit_alone_not_context(self):
        # 仅单位（g/L）命中不足以建立数值上下文 → unverifiable 而非 contradicted
        facts = [
            {"subject": "V001", "predicate": "lab_value", "object": 107.0,
             "qualifiers": {"item": "血红蛋白测定", "unit": "g/L", "label": "检验结果"}},
        ]
        claim = {"claim": "血常规示78g/L", "type": "numeric",
                 "entities": [], "value": 78}
        assert verify_claim(claim, facts)["label"] == "unverifiable"
        # 但断言实体是检验项目的子串（部分匹配）时可以建立上下文
        claim2 = {"claim": "血红蛋白78g/L", "type": "numeric",
                  "entities": ["血红蛋白"], "value": 78}
        assert verify_claim(claim2, facts)["label"] == "contradicted"

    def test_generic_item_alias_for_los(self):
        # 住院天数事实带通用 item 别名 "住院"：多次就诊数值命中其一即 supported
        facts = [
            {"subject": "V001", "predicate": "length_of_stay", "object": 12,
             "qualifiers": {"label": "住院天数", "item": "住院"}},
            {"subject": "V002", "predicate": "length_of_stay", "object": 29,
             "qualifiers": {"label": "住院天数", "item": "住院"}},
        ]
        ok = {"claim": "第1次住院12天", "type": "numeric",
              "entities": ["第1次"], "value": 12}
        assert verify_claim(ok, facts)["label"] == "supported"
        # 上下文不唯一，数值对不上 → 保守判 unverifiable
        bad = {"claim": "第1次住院99天", "type": "numeric",
               "entities": ["第1次"], "value": 99}
        assert verify_claim(bad, facts)["label"] == "unverifiable"

    def test_weak_context_not_contradicted(self):
        # 通用短别名（"住院"）建立的弱上下文不能用于判 contradicted：
        # "住院期间共完成1次诊疗" 的数字 1 不应误伤住院天数事实（真实冒烟中出现过）
        facts = [
            {"subject": "V001", "predicate": "length_of_stay", "object": 78,
             "qualifiers": {"label": "住院天数", "item": "住院",
                            "admission_date": "2020-12-31"}},
        ]
        claim = {"claim": "住院期间共完成1次完整诊疗过程", "type": "numeric",
                 "entities": ["患者"], "value": 1}
        assert verify_claim(claim, facts)["label"] == "unverifiable"
        # 但 label 被直接提及（强上下文）且数值超容差 → contradicted
        strong = {"claim": "住院天数为30天", "type": "numeric",
                  "entities": [], "value": 30}
        assert verify_claim(strong, facts)["label"] == "contradicted"


# ==================== verify：任务级指标 ====================

class TestComputeMetrics:
    def test_metrics(self):
        claims = [
            {"claim": "肺癌就诊100人次", "type": "numeric", "entities": ["肺癌"], "value": 100},   # supported
            {"claim": "肺癌合并高血压", "type": "relation", "entities": ["肺癌", "高血压"], "value": None},  # supported
            {"claim": "肺癌就诊500人次", "type": "numeric", "entities": ["肺癌"], "value": 500},   # contradicted
            {"claim": "肺癌患者普遍年轻", "type": "other", "entities": ["肺癌"], "value": None},   # unverifiable
        ]
        verdicts = verify_claims(claims, FACTS)
        labels = [v["label"] for v in verdicts]
        assert labels == ["supported", "supported", "contradicted", "unverifiable"]

        m = compute_metrics(verdicts)
        assert m["total"] == 4
        assert m["supported"] == 2
        assert m["contradicted"] == 1
        assert m["unverifiable"] == 1
        assert m["grounding_rate"] == pytest.approx(2 / 4)
        assert m["fact_accuracy"] == pytest.approx(2 / 3)
        assert m["hallucination_rate"] == pytest.approx(1 / 4)
        assert m["unsupported_rate"] == pytest.approx(1 / 4)

    def test_empty_verdicts(self):
        m = compute_metrics([])
        assert m["total"] == 0
        assert m["grounding_rate"] is None
        assert m["fact_accuracy"] is None
        assert m["hallucination_rate"] is None

    def test_no_supported_or_contradicted(self):
        m = compute_metrics([{"label": "unverifiable"}])
        assert m["fact_accuracy"] is None
        assert m["unsupported_rate"] == 1.0


# ==================== judge：解析与重试 ====================

GOOD_JSON = (
    '{"coherence": {"score": 4, "reason": "连贯"},'
    ' "coverage": {"score": 3, "reason": "一般"},'
    ' "readability": {"score": 5, "reason": "流畅"},'
    ' "clinical_usefulness": {"score": 2, "reason": "有限"}}'
)


class TestParseScoresJson:
    def test_clean_json(self):
        scores = parse_scores_json(GOOD_JSON)
        assert scores is not None
        assert scores["coherence"]["score"] == 4
        assert scores["readability"]["reason"] == "流畅"

    def test_code_block(self):
        scores = parse_scores_json(f"```json\n{GOOD_JSON}\n```")
        assert scores is not None
        assert scores["coverage"]["score"] == 3

    def test_invalid_dim_score_becomes_none(self):
        raw = GOOD_JSON.replace('"score": 4', '"score": 9')  # 超出 1-5
        scores = parse_scores_json(raw)
        assert scores is not None
        assert scores["coherence"]["score"] is None
        assert scores["coverage"]["score"] == 3

    def test_garbage_returns_none(self):
        assert parse_scores_json("无法评分") is None
        assert parse_scores_json("") is None


class TestScoreNarrativeRetry:
    def test_first_try_success(self):
        calls = []

        def fake_chat(*args, **kwargs):
            calls.append(1)
            return GOOD_JSON

        scores = score_narrative("某叙事", "某任务", chat_fn=fake_chat)
        assert scores is not None
        assert len(calls) == 1

    def test_retry_once_on_parse_failure(self):
        outputs = iter(["这不是JSON", GOOD_JSON])
        calls = []

        def fake_chat(*args, **kwargs):
            calls.append(1)
            return next(outputs)

        scores = score_narrative("某叙事", chat_fn=fake_chat)
        assert scores is not None
        assert len(calls) == 2  # 重试一次后成功

    def test_both_fail_returns_none(self):
        def fake_chat(*args, **kwargs):
            return "仍然不是JSON"

        assert score_narrative("某叙事", chat_fn=fake_chat) is None

    def test_llm_failure_no_retry(self):
        calls = []

        def fake_chat(*args, **kwargs):
            calls.append(1)
            return "[LLM调用失败] 服务不可用"

        assert score_narrative("某叙事", chat_fn=fake_chat) is None
        assert len(calls) == 1  # LLM 失败不重试

    def test_empty_text(self):
        assert score_narrative("", chat_fn=lambda *a, **k: GOOD_JSON) is None


class TestParseScoresJsonCorrupted:
    """judge 解析器对乱码 score 值的容错（模型偶发在数字前混入乱码 token）"""

    def test_corrupted_score_value_recovered(self):
        from experiments.judge import parse_scores_json
        raw = ('{"coherence": {"score": 3, "reason": "连贯"},'
               ' "coverage": {"score":һڼ3, "reason": "覆盖部分"},'
               ' "readability": {"score": iatively3, "reason": "可读"},'
               ' "clinical_usefulness": {"score": 3, "reason": "有限"}}')
        scores = parse_scores_json(raw)
        assert scores is not None
        assert scores["coverage"]["score"] == 3
        assert scores["readability"]["score"] == 3
        assert scores["coherence"]["score"] == 3

    def test_total_garbage_still_none(self):
        from experiments.judge import parse_scores_json
        assert parse_scores_json("完全不是 JSON 也没有维度名") is None
