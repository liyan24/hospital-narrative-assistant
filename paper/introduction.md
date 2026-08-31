# 1. Introduction

> 状态：初稿（Draft v0.1）。[n] 为待补引文编号；具体数字待全量实验后回填。对应提纲 `paper/outline.md` 第 1 节。

## Draft

Clinical departments are data-rich but insight-poor. A single oncology–hematology ward accumulates millions of structured records per year — admission and discharge registrations, medication orders, laboratory results, examinations, and surgical records — yet the daily work of understanding these data still relies on manual compilation: clinicians assemble morning handover briefings by reading through disconnected systems, department managers prepare operational reports by copying numbers into slide templates, and quality-control officers hunt for anomalies record by record [n1, n2]. The gap between the volume of available data and the human capacity to digest it is now widely recognized as a bottleneck of data-driven clinical management [n3].

Data storytelling — the automated transformation of data into coherent narrative combining text, numbers, and visualizations — has emerged as a promising bridge across this gap, and has been listed among the core capabilities of modern analytics platforms [n4]. The rise of large language models (LLMs) has sharply lowered the cost of generating fluent narrative from data, and recent frameworks such as DataNarrative [n5] and multi-agent data-video systems [n6] demonstrate that end-to-end automated storytelling is technically feasible for general tabular data.

Healthcare, however, is an unforgiving domain for generative models. When an LLM is asked to narrate structured clinical data directly, it may fabricate laboratory values, confuse medications across admissions, or invent comorbidities that no patient ever had [n7, n8]. Such hallucinations are tolerable in consumer analytics demos; in a morning handover briefing they are patient-safety hazards. Existing retrieval-augmented generation (RAG) approaches mitigate hallucination by grounding generation in retrieved text chunks [n9], but clinical facts in departmental data are predominantly *relational* — which drug co-occurs with which diagnosis within which admission, how a treatment pathway unfolds across visits — and chunk-level retrieval over serialized records does not preserve these relations faithfully [n10, n11].

In this paper we argue that a purpose-built clinical knowledge graph (KG) is a more faithful fact source for narrative generation than raw tables or text chunks, and we present a KG-grounded narrative generation framework for departmental clinical data. Multi-source heterogeneous records are cleaned, standardized to ICD-10, and integrated into a department-level KG (32,694 nodes, 788,119 relationships covering patients, visits, diseases, drugs, laboratory items, examinations, and surgeries). A narrative request is parsed into an intent and mapped to graph retrieval primitives — subgraph, co-occurrence, second-order, and aggregation queries — whose results are serialized into an explicit fact list. The LLM is then constrained to narrate *only* from this fact list, quoting numeric values verbatim and citing a fact identifier for every factual sentence. The design principle is a strict decoupling of **fact supply** (the graph) from **verbalization** (the LLM), which makes every generated sentence traceable to a database-grounded source.

We evaluated the framework on 100 narrative tasks spanning five real departmental scenarios — patient storylines, treatment pathways, comorbidity analysis, drug-pattern analysis, and morning briefings — constructed from de-identified data of 3,990 patients and 13,743 visits in an oncology–hematology department. Against three baselines (direct LLM generation over tabular summaries, vector RAG, and a rule-based template), the KG-grounded method achieved a grounding rate of 84.1% (vs 65.5% for direct generation; Wilcoxon p < 0.001, effect size r = 0.76) and reduced the unsupported-claim rate from 33.9% to 15.8%, while showing no significant quality difference on coherence, coverage, or clinical usefulness as scored by an LLM evaluator with rubric anchoring.

**Contributions.** (1) We propose a KG-grounded narrative generation framework for departmental clinical data that formalizes narrative intents as graph retrieval primitives and decouples fact supply from verbalization, yielding fully provenance-traceable narratives. (2) We design an evaluation protocol for narrative faithfulness that adapts atomic-claim verification to a KG reference, combining automated claim verification, LLM-as-Judge scoring, and blinded expert review. (3) We provide empirical evidence on a real-world departmental dataset that graph grounding substantially improves the verifiability of LLM-generated clinical narratives without sacrificing narrative quality, and we release the experimental pipeline to support replication.

The remainder of this paper is organized as follows. Section 2 reviews related work. Section 3 formalizes the problem and describes the dataset, graph construction, the generation framework, and the evaluation protocol. Section 4 reports experimental results. Section 5 discusses implications and limitations, and Section 6 concludes.

## 写作备注（不进入正文）

1. 引文需求清单（共 11 处）：
   - n1–n3：医疗数据增长/临床管理数据利用困难（可从开题报告 1.1 节 + 医疗信息化综述选取）；
   - n4：Gartner ABI 魔力象限数据叙事；
   - n5：DataNarrative (EMNLP 2024)；n6：Data Director；
   - n7–n8：医疗 NLG 幻觉/事实性研究（需补 1–2 篇，如 radiology report factuality）；
   - n9：RAG (Lewis 2020)；n10：KG×LLM roadmap (Pan 2024)；n11：GraphRAG 类。
2. 结果句中的 [xx] 与检验值待全量实验后回填；若 grounding rate 差异显著而 hallucination rate 差异不显著，按现状如实表述（主指标为 grounding/unsupported）。
3. 投稿前按目标期刊调整第一段钩子：JMIR 系偏好更直白的实践导向开场；JBI 接受当前学术化开场。
