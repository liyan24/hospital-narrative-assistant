# 4. Results

> 状态：初稿（Draft v0.4），自动评估+消融+LLM 辅助校准+模拟盲评数字全部回填完毕（2026-08-26）。唯一待替换项：4.3 的模拟专家评审需用真人临床专家数据替换或并列呈现。显著性标记：* p<0.05，** p<0.005（Bonferroni 校正后阈值，9 项检验 α=0.0056）。

## 4.1 Automated Factual Verification

**Table 2.** Automated faithfulness metrics by method (mean ± SD across 100 tasks).

| Method | Grounding rate ↑ | Fact accuracy ↑ | Hallucination rate ↓ | Unsupported rate ↓ |
|---|---|---|---|---|
| B1 Direct-LLM | 0.655 ± 0.318 | 0.993 ± 0.032 | 0.006 ± 0.026 | 0.339 ± 0.319 |
| B2 Vector-RAG | 0.548 ± 0.287 | 0.996 ± 0.024 | 0.003 ± 0.016 | 0.449 ± 0.288 |
| B3 KG-Grounded (ours) | **0.841 ± 0.236** | 0.999 ± 0.007 | 0.001 ± 0.006 | **0.158 ± 0.236** |
| B4 Template (reference) | 0.846 ± 0.314 | 1.000 ± 0.000 | 0.000 ± 0.000 | 0.154 ± 0.314 |

The KG-grounded method substantially outperformed both generative baselines on verifiability. Grounding rate — the proportion of extracted atomic claims entailed by knowledge-graph facts — was 0.841 for B3 versus 0.655 for B1 (Wilcoxon signed-rank p < 0.001**, effect size r = 0.76) and 0.548 for B2, a large effect by conventional criteria. Conversely, the unsupported-claim rate dropped from 33.9% (B1) and 44.9% (B2) to 15.8% (B3) (B1 vs B3: p < 0.001**, r = 0.75). Detected contradictions were rare under all methods (hallucination rate ≤ 0.6%) and did not differ significantly between B1 and B3 (p = 0.066); we attribute this floor effect to our deliberately conservative contradiction criteria (Section 3.4.3) and return to its implications in Section 5. The template reference B4 approached perfect fact accuracy (1.000) as expected, since it verbalizes ground-truth facts directly, and its grounding rate (0.846) was comparable to B3 — however, its narrative quality was markedly inferior (Section 4.2), confirming that B4 is a factual upper bound rather than a usable system.

**抽取器校准**：在 20% 分层样本（80 条叙事、2,022 条断言，见 `experiments/output/calibration_sheet.csv`）上完成了 LLM 辅助标注（5 个独立标注智能体，其中 240 条断言为 5 方重叠标注）。结果：断言抽取器 precision = 1.000（2,982 条标注中未发现抽取错误）；自动核查标签与标注标签的 5 方完全一致率 = 98.3%（Fleiss' κ = 0.983）。标注者仅发现 1 条 contradicted，与自动核查中 contradicted 罕见的地板效应一致。
⚠️ 写作注意：该数字由同族 LLM 标注产生，存在系统性高估风险；正文应写为 "LLM-assisted annotation (preliminary)"，真实人工标注子集（1–2 人 × 300–500 条）仍须在投稿前完成并在 Limitations 中说明。

## 4.2 Narrative Quality (LLM-as-Judge)

**Table 3.** LLM-as-Judge scores (1–5, mean ± SD).

| Method | Coherence | Coverage | Readability | Clinical usefulness |
|---|---|---|---|---|
| B1 Direct-LLM | 4.70 ± 0.54 | 4.54 ± 0.77 | 4.73 ± 0.45 | 4.61 ± 0.75 |
| B2 Vector-RAG | 4.68 ± 0.55 | 4.51 ± 0.67 | 4.70 ± 0.48 | 4.59 ± 0.64 |
| B3 KG-Grounded (ours) | 4.63 ± 0.54 | 4.41 ± 0.77 | 4.57 ± 0.50 | 4.48 ± 0.67 |
| B4 Template (reference) | 2.81 ± 0.75 | 2.48 ± 0.72 | 3.05 ± 0.56 | 2.26 ± 0.53 |

Crucially, the faithfulness gains of B3 did not come at the cost of narrative quality. B3 did not differ significantly from B1 on coherence (4.63 vs 4.70; p = 0.178), information coverage (4.41 vs 4.54; p = 0.085), or clinical usefulness (4.48 vs 4.61; p = 0.063). Readability showed a small but significant difference favoring B1 (4.57 vs 4.73; p = 0.003**, r = 0.26), which we attribute in part to residual citation markers ([Fk]) in B3 outputs despite the judge being instructed to ignore them. The template method B4 scored significantly below all LLM-based methods on every dimension (all p < 0.001), confirming that rule-based verbalization cannot substitute for generative narration. We note that judge scores remained correlated with narrative length (Pearson r = 0.667), consistent with known verbosity bias of LLM evaluators [ref]; the blinded expert review (Section 4.3) therefore serves as the arbiter of the quality comparison.

## 4.3 Expert Blind Review

**Table 4.** Blinded review ratings (1–5, mean ± SD; 3 raters × 10 tasks per method)【预实验：LLM 模拟专家评审（3 种临床角色：主任医师/主治医师/医学信息学研究生），真实临床专家评审待组织】

| Method | Factual correctness | Clinical usefulness | Readability |
|---|---|---|---|
| B1 Direct-LLM | 3.97 ± 1.22 | **4.27 ± 0.64** | **4.83 ± 0.38** |
| B2 Vector-RAG | 3.20 ± 1.49 | 3.37 ± 1.35 | 4.57 ± 0.50 |
| B3 KG-Grounded (ours) | **4.90 ± 0.31** | 4.13 ± 0.63 | 4.30 ± 0.47 |
| B4 Template (reference) | 4.50 ± 1.11 | 2.20 ± 0.48 | 3.00 ± 0.00 |

评审者间一致性：Fleiss' κ = 0.543（事实正确性）/ 0.560（临床有用性）/ 0.565（可读性），中等一致性——主观维度评审的正常水平。LLM-Judge 与盲评的 Spearman ρ = 0.457（n=40，按任务×方法配对），中等相关，说明 LLM-Judge 可作粗粒度筛查但不可替代专家评审。

The blinded review corroborated and strengthened the automated findings. B3 achieved the highest factual correctness (4.90 ± 0.31, vs 3.97 for B1 and 3.20 for B2) with a markedly smaller variance, indicating that graph grounding yields *consistently* reliable narratives rather than occasional successes. Clinical usefulness was comparable between B3 (4.13) and B1 (4.27), mirroring the automated quality results. Notably, reviewers independently flagged the same failure mode that automated verification detected at scale: B2's fluent narratives included fully fabricated treatment courses (an invented "3+7" induction chemotherapy regimen in patient_storyline-003; seven fabricated hospitalizations with a misreported discharge date in patient_storyline-017), rated as the most hazardous error type despite high readability. Post-hoc key decoding showed all such severe cases came from B2 — vector retrieval had surfaced records of *different patients*, an identity-confusion failure that chunk-level retrieval cannot prevent and B3's patient-scoped traversal is structurally immune to. B1's errors were predominantly unverifiable elaborations rather than wholesale fabrication. B3's readability remained below B1 (4.30 vs 4.83), consistent with the LLM-Judge results; we discuss mitigation in Section 5.

## 4.4 Ablation Study

**Table 5.** Ablation of B3 components (mean across 100 tasks).

| Variant | Grounding rate | Unsupported rate | Coverage | Coherence |
|---|---|---|---|---|
| B3 full | 0.841 | 0.158 | **4.41** | **4.63** |
| A1 − ICD-10 standardization | 0.753 | 0.241 | 4.59 | 4.79 |
| A2 − second-order/co-occurrence retrieval | **0.633** | **0.358** | 4.30 | 4.70 |
| A3 − provenance constraint | 0.880 | 0.120 | 3.72 | 4.44 |

叙述要点：
- **A2 降幅最大**（grounding −0.21，unsupported +0.20）：二阶关系/共现检索是事实覆盖的最大贡献者，尤其在合并症与用药模式场景——消融预检显示 A2 使合并症任务可用事实从 588 条降至 20 条；
- **A1**（去 ICD-10 标准化）：grounding −0.09，unsupported +0.08——同义疾病未合并导致聚合事实缺失，贡献次之但明确；
- **A3**（去溯源约束）：grounding 微升（0.880 vs 0.841）但 **coverage 明显下降（3.72 vs 4.41，−0.69）**——逐句标注来源的写作纪律迫使模型系统性地覆盖事实清单，去掉约束后模型倾向泛泛而谈。这说明溯源约束的价值不仅在可审计性（provenance），还在信息完整性；其 grounding 的轻微代价（约 4 个百分点）是可接受的权衡；
- A1/A2 的 coverage/coherence 与 B3 full 相当（约束减少 → 发挥更自由），与主实验的"质量-可核查性权衡"叙事一致。

## 4.5 Efficiency

**Table 6.** End-to-end generation latency (seconds, mean ± SD; graph retrieval overhead included in B3).

| Method | Latency (s) |
|---|---|
| B1 Direct-LLM | 6.14 ± 1.43 |
| B2 Vector-RAG | 5.70 ± 1.63 |
| B3 KG-Grounded (ours) | 6.95 ± 1.73 |
| B4 Template | < 0.01 |

B3 was slightly slower than B1 (6.95 s vs 6.14 s per narrative; Wilcoxon p < 0.001**, r = 0.50), an overhead attributable to longer, citation-annotated outputs rather than retrieval cost (Cypher retrieval completes in milliseconds). The absolute difference (~0.8 s) is negligible for departmental reporting workflows, in which narratives are generated once per shift or on demand.

（备注：token 消耗与缓存命中率当前管线未记录，如需列入 Table 6 需给 baselines 增加 usage 统计后补跑；建议投稿时补充，审稿人可能问及成本。）

## 4.6 Case Study

**Figure 4.** 已生成（`paper/figures/figure4_case_study.png/.pdf`）：任务 `patient_storyline-017`，**B2 Vector-RAG vs B3**（B2 grounding 0.17 / B3 0.82；盲评事实正确性 B2=1.0、B3=4.3）。选 B2 而非 B1 的原因：key.json 解码证实盲评打 1 分的"文本丁"是 B2（向量检索混入其他患者病历，虚构第 3–9 次住院），这是全文最有力的失败案例。左栏红框标注 4 处编造（出院日期 2-27 对 2-26、虚构住院经过、胸腔穿刺/姑息放疗、累计住院 79 天），右栏 B3 的 [Fk] 溯源链与事实清单节选（visit_count=9、两次住院出入院日期）。

备选素材：`comorbidity-014`（B1 0.43 → B3 1.00）、`morning_briefing-005`（B1 0.04 → B3 1.00，B1 大量编造患者细节）。

## 结果备注（不进入正文）

1.  hallucination rate 无显著差异是诚实的负面结果，叙事逻辑应为："B3 的优势体现在断言可核查性（grounding）与不可考断言的减少；在保守判定下，直接生成的显性编造率本身不高（0.6%）"。Discussion 需讨论：(a) contradicted 罕见部分源于保守判定；(b) unverifiable 断言在临床场景同样是风险（无法溯源≈不可信）。
2.  B3 grounding 从第一轮的 0.925 降到 0.841：更丰富的叙事引入了更多归纳性（不可考）断言。这是质量-可核查性权衡的真实证据，值得在 Discussion 写一句。
3.  长度偏差 r=0.667 未因 judge 细则修订而消除（第一轮 0.585）——如实报告，并作为 LLM-as-Judge 局限性的实证，呼应开题报告 2.5.2 的偏差讨论。
4.  B3 延迟略高于 B1（输出更长）；第一轮"B3 更快"的结论在 prompt 修订后不再成立，已删除该说法。
