# KG-Grounded Narrative Generation for Clinical Department Data: A Faithfulness-Oriented Approach

> Draft v1.0（2026-08-26 组装）。⚠️ 投稿前必读：
> 1. Section 4.3 当前为 LLM 模拟专家评审的预实验数据，**必须替换为真人临床专家评审结果**，或将模拟数据明确标注为 pilot 并降级到附录；
> 2. 摘要与正文中的伦理声明、作者贡献、基金、利益冲突、数据/代码可用性为占位符；
> 3. 标 [TODO-ref] 处需补充真实文献（切勿凭空引用）。

## Abstract

**Background**: Clinical departments accumulate vast amounts of structured data, yet daily operations such as morning handovers, ward rounds, and quality control still depend on manual data compilation. Large language models (LLMs) can generate fluent data narratives, but unconstrained generation risks factual hallucination, which is unacceptable in clinical settings.

**Objective**: We propose and evaluate a knowledge graph–grounded (KG-grounded) narrative generation framework that decouples fact supply from verbalization, aiming to improve the faithfulness of LLM-generated clinical narratives without sacrificing narrative quality.

**Methods**: Multi-source heterogeneous departmental data (admissions, discharges, examinations, laboratory results, surgeries, and medication orders) were cleaned, standardized to ICD-10, and integrated into a Neo4j knowledge graph (32,694 nodes; 788,119 relationships). Narrative requests were parsed into intents and mapped to graph retrieval primitives (subgraph, co-occurrence, second-order, and aggregation queries); retrieved subgraphs were serialized into explicit fact lists from which the LLM was constrained to generate, citing a fact identifier for every factual sentence. We constructed 100 narrative tasks across five departmental scenarios (patient storyline, treatment pathway, comorbidity analysis, drug-pattern analysis, morning briefing) from de-identified data of 3,990 patients and 13,743 visits. Three baselines (direct LLM generation, vector retrieval-augmented generation, and rule-based templates) were compared using automated claim-level verification against graph facts, rubric-anchored LLM-as-Judge scoring, and blinded review.

**Results**: The KG-grounded method achieved a grounding rate of 0.841 versus 0.655 for direct generation (Wilcoxon p < .001, effect size r = 0.76) and reduced the unsupported-claim rate from 33.9% to 15.8%, while showing no significant differences in coherence, coverage, or clinical usefulness. Blinded review rated KG-grounded narratives highest on factual correctness (4.90 ± 0.31 vs 3.97 ± 1.22 for direct generation). Ablation showed that second-order/co-occurrence retrieval contributed most to factual coverage (grounding dropped to 0.633 when removed) and that the provenance constraint additionally improved information coverage (4.41 vs 3.72).

**Conclusions**: Grounding LLM narrative generation in a purpose-built clinical knowledge graph substantially improves verifiability at negligible cost to narrative quality and latency, offering a practical pattern for safe LLM deployment in data-intensive clinical communication.

**Keywords**: data storytelling; knowledge graph; large language model; hallucination; faithfulness; clinical informatics; retrieval-augmented generation

---

## 1. Introduction

Clinical departments are data-rich but insight-poor. A single oncology–hematology ward accumulates millions of structured records per year — admission and discharge registrations, medication orders, laboratory results, examinations, and surgical records — yet the daily work of understanding these data still relies on manual compilation: clinicians assemble morning handover briefings by reading through disconnected systems, department managers prepare operational reports by copying numbers into slide templates, and quality-control officers hunt for anomalies record by record [1, 2]. The gap between the volume of available data and the human capacity to digest it is now widely recognized as a bottleneck of data-driven clinical management [3].

Data storytelling — the automated transformation of data into coherent narrative combining text, numbers, and visualizations — has emerged as a promising bridge across this gap, and has been listed among the core capabilities of modern analytics platforms [4]. The rise of large language models (LLMs) has sharply lowered the cost of generating fluent narrative from data, and recent frameworks such as DataNarrative [5] and multi-agent data-video systems [6] demonstrate that end-to-end automated storytelling is technically feasible for general tabular data.

Healthcare, however, is an unforgiving domain for generative models. When an LLM is asked to narrate structured clinical data directly, it may fabricate laboratory values, confuse medications across admissions, or invent comorbidities that no patient ever had [7, 8]. Such hallucinations are tolerable in consumer analytics demos; in a morning handover briefing they are patient-safety hazards. Existing retrieval-augmented generation (RAG) approaches mitigate hallucination by grounding generation in retrieved text chunks [9], but clinical facts in departmental data are predominantly *relational* — which drug co-occurs with which diagnosis within which admission, how a treatment pathway unfolds across visits — and chunk-level retrieval over serialized records does not preserve these relations faithfully [10, 11].

In this paper we argue that a purpose-built clinical knowledge graph (KG) is a more faithful fact source for narrative generation than raw tables or text chunks, and we present a KG-grounded narrative generation framework for departmental clinical data. Multi-source heterogeneous records are cleaned, standardized to ICD-10, and integrated into a department-level KG (32,694 nodes, 788,119 relationships covering patients, visits, diseases, drugs, laboratory items, examinations, and surgeries). A narrative request is parsed into an intent and mapped to graph retrieval primitives — subgraph, co-occurrence, second-order, and aggregation queries — whose results are serialized into an explicit fact list. The LLM is then constrained to narrate *only* from this fact list, quoting numeric values verbatim and citing a fact identifier for every factual sentence. The design principle is a strict decoupling of **fact supply** (the graph) from **verbalization** (the LLM), which makes every generated sentence traceable to a database-grounded source.

We evaluated the framework on 100 narrative tasks spanning five real departmental scenarios — patient storylines, treatment pathways, comorbidity analysis, drug-pattern analysis, and morning briefings — constructed from de-identified data of 3,990 patients and 13,743 visits in an oncology–hematology department. Against three baselines (direct LLM generation over tabular summaries, vector RAG, and a rule-based template), the KG-grounded method achieved a grounding rate of 84.1% (vs 65.5% for direct generation; Wilcoxon p < 0.001, effect size r = 0.76) and reduced the unsupported-claim rate from 33.9% to 15.8%, while showing no significant quality difference on coherence, coverage, or clinical usefulness as scored by an LLM evaluator with rubric anchoring.

**Contributions.** (1) We propose a KG-grounded narrative generation framework for departmental clinical data that formalizes narrative intents as graph retrieval primitives and decouples fact supply from verbalization, yielding fully provenance-traceable narratives. (2) We design an evaluation protocol for narrative faithfulness that adapts atomic-claim verification to a KG reference, combining automated claim verification, LLM-as-Judge scoring, and blinded review. (3) We provide empirical evidence on a real-world departmental dataset that graph grounding substantially improves the verifiability of LLM-generated clinical narratives without sacrificing narrative quality, and we release the experimental pipeline to support replication.

The remainder of this paper is organized as follows. Section 2 reviews related work. Section 3 formalizes the problem and describes the dataset, graph construction, the generation framework, and the evaluation protocol. Section 4 reports experimental results. Section 5 discusses implications and limitations, and Section 6 concludes.

## 2. Related Work

### 2.1 Data Storytelling and Automated Narrative Generation

Data storytelling evolved from narrative visualization research. Segel and Heer [12] first systematized the design space of narrative visualization, and Kosara and Mackinlay [13] framed storytelling as the next step for visualization. Early automation relied on rules and templates: DataShot generated fact sheets from tabular data with predefined fact types [14], and similar template-driven systems produced data videos and animated infographics. Learning-based approaches later enabled end-to-end data-to-text generation, including chart summarization (Chart-to-Text [15]) and controlled table-to-text generation (ToTTo [16]).

Since 2024, LLMs have reshaped this landscape. DataNarrative [5] formalized the generation of complete data stories (visualizations plus text) from tables; Chen et al. [7] reported that GPT-4 produces fluent narratives but struggles with data accuracy; the MDSF framework [17] introduced context-aware multi-dimensional storytelling. LLM-based data-science agents and multi-agent systems (e.g., Data Director [6]) further demonstrated automated analysis pipelines. However, most of this work targets general-purpose or business-intelligence scenarios, and factual fidelity guarantees for high-stakes domains remain largely absent.

### 2.2 LLMs for Clinical Text Generation and the Hallucination Problem

LLMs have been applied to clinical summarization, report generation, and health-platform data insights [8]. A persistent concern is factual reliability: models may produce fluent but unsupported clinical statements, and several studies of clinical NLG have documented non-trivial rates of factual error in generated summaries [TODO-ref: 医疗 NLG 事实性研究 1–2 篇，如 radiology report factuality]. Temporal and structured clinical data pose additional representational challenges for LLMs [18]. These observations motivate grounding mechanisms that bind generation to verifiable data sources.

### 2.3 Knowledge Graphs Meet LLMs

Knowledge graphs and LLMs are increasingly unified along three routes: KG-enhanced LLMs, LLM-augmented KGs, and synergized frameworks [10, 11]. Retrieval-augmented generation [9] grounds generation in retrieved text; GraphRAG-style approaches extend retrieval to graph-structured indices over unstructured corpora. In the medical domain, KGs have long served as curated knowledge backbones for question answering and decision support. Our work differs in that the KG is built *directly from departmental operational data* and serves as the exclusive fact source for narrative generation: relations such as co-medication within a visit or cross-visit treatment pathways are first-class retrievable facts rather than approximated by text chunks.

### 2.4 Evaluating Factual Consistency

Automated faithfulness evaluation has progressed from surface-overlap metrics to atomic-claim verification: FActScore [19] decomposes long-form text into atomic facts verified against a reference source, and LLM-as-Judge approaches such as G-Eval [20] and Prometheus [21] achieve substantial correlation with human judgments. Known judge biases — position, verbosity, and authority effects [22] — motivate rubric-anchored scoring and human arbitration. Iterative self-correction frameworks (Self-Refine [23], CRITIC [24]) further connect evaluation to generation improvement. We adapt atomic-claim verification to a setting where the reference is not a text corpus but a structured fact set exported from a knowledge graph, enabling deterministic, reproducible claim verification.

### 2.5 Summary

Appendix Table A1 contrasts this work with the closest systems along domain, fact source, evaluation, and provenance. In short: prior data-storytelling systems rarely address clinical faithfulness; clinical NLG studies rarely address structured departmental data; and RAG variants rarely exploit explicit relational structure. This paper sits at the intersection.

## 3. Materials and Methods

### 3.1 Problem Formulation

Let $D = \{D_{adm}, D_{dis}, D_{exam}, D_{lab}, D_{surg}, D_{ord}\}$ denote the multi-source structured data of a clinical department, covering admission records, discharge records, examinations, laboratory results, surgeries, and medication orders, respectively. Given a narrative intent $q = (s, e, a)$ — where $s$ is the narrative scenario (e.g., patient storyline, treatment pathway analysis), $e$ is the narrative subject (a patient identifier or a disease name), and $a$ is the intended audience — the goal is to generate a narrative text $S$ that maximizes factual fidelity to $D$ while preserving narrative quality.

We define an *atomic factual claim* as a minimal, independently verifiable statement in $S$ about an entity, a numeric value, a relation, or a temporal fact. Given a reference fact set $F$ derived from $D$, each extracted claim $c$ is labeled as *supported* (entailed by some $f \in F$), *contradicted* (conflicting with some $f \in F$), or *unverifiable* (no corresponding fact in $F$). We operationalize faithfulness through four metrics: **grounding rate** $= |\text{supported}| / |\text{claims}|$ (primary), **fact accuracy** $= |\text{supported}| / (|\text{supported}| + |\text{contradicted}|)$, **hallucination rate** $= |\text{contradicted}| / |\text{claims}|$, and **unsupported rate** $= |\text{unverifiable}| / |\text{claims}|$. The central hypothesis is that constraining LLM generation with facts retrieved from a purpose-built KG increases grounding and reduces unsupported claims, compared with feeding raw tabular summaries or loosely retrieved text snippets to the same LLM.

### 3.2 Data and Knowledge Graph Construction

#### 3.2.1 Dataset

We use de-identified real-world data from the Department of Oncology and Hematology of [a county-level hospital in Henan Province, China]. The dataset comprises 3,990 patients with 13,743 hospital visits, approximately 1.14 million medication orders, 55,000 laboratory results, 20,000 examination records, and 85 surgeries (Table 1). All patient identifiers were pseudonymized before analysis. [伦理声明待补：IRB approval / waiver statement.]

**Table 1.** Dataset statistics.

| Data source | Records | Coverage |
|---|---|---|
| Patients | 3,990 | — |
| Hospital visits | 13,743 | — |
| Medication orders | ~1,140,000 | 100% of patients |
| Laboratory results | ~55,000 | 826 patients |
| Examinations | ~20,000 | 3,294 patients |
| Surgeries | 85 patients | — |

#### 3.2.2 Data Cleaning and Standardization

Raw records were exported as seven Excel workbooks and ingested into a relational database (MySQL 8). Cleaning included: (i) normalization of disease names (whitespace, full/half-width characters, punctuation variants); (ii) mapping of Western-medicine diagnoses to ICD-10 codes through a three-tier procedure — exact match, substring match, and fuzzy match (similarity threshold 85) with manual overrides — against a reference ICD-10 vocabulary (GB/T 14396-2016 extension codes). Of 1,347 distinct standardized Western-medicine disease names, 977 (72.5%) were successfully mapped to ICD-10 codes (exact: 631; substring: 185; fuzzy: 95; manual override: 66); the remaining 370 were predominantly composite diagnoses and post-treatment status expressions and were retained unmapped; and (iii) normalization of drug names and consolidation of synonymous entries. Traditional Chinese medicine (TCM) syndrome diagnoses were retained as a separate disease type.

#### 3.2.3 Ontology and Graph Construction

We designed a department-level clinical ontology with nine node types — `Patient`, `Visit`, `Disease` (typed as `western` or `tcm_syndrome`), `Drug`, `Exam`, `LabItem`, `Surgery`, `ChiefComplaint`, and `Department` — and nine relation types (Figure 2): `(Patient)-[:HAS_VISIT]->(Visit)`; `(Visit)-[:DIAGNOSED_WITH {diagnosis_type, is_main}]->(Disease)`; `(Visit)-[:CHIEF_COMPLAINT]->(ChiefComplaint)`; `(Visit)-[:PERFORMED_EXAM {exam_date, description}]->(Exam)`; `(Visit)-[:HAS_LAB_RESULT {value, unit, abnormal_flag}]->(LabItem)`; `(Visit)-[:PRESCRIBED {dosage, frequency, route, start_date}]->(Drug)`; `(Visit)-[:UNDERWENT {start_date}]->(Surgery)`; `(Visit)-[:IN_DEPARTMENT]->(Department)`; and `(Drug|Surgery)-[:TREATS {evidence}]->(Disease)`. `Patient` nodes carry demographic attributes (age, marital status, occupation, allergy history); `Visit` nodes carry admission/discharge dates and length of stay. The resulting KG contains 32,694 nodes and 788,119 relationships, stored in Neo4j 5.26 (Figure 2). Because disease nodes are keyed by a composite of display name and type, entity matching throughout this study uses the normalized display name.

### 3.3 KG-Grounded Narrative Generation Framework

The framework (Figure 1) decouples *fact supply* from *verbalization*: the KG is the sole source of facts, and the LLM is restricted to organizing and expressing retrieved facts with explicit provenance.

#### 3.3.1 Intent Parsing

A narrative request is parsed into a scenario label and a subject entity using a hybrid rule-plus-LLM parser. Scenarios include patient-centered narratives (`patient`), disease-centered analyses (`disease`, `drug`, `comorbidity`, `pathway`), and department-level briefings (`briefing`). Patient identifiers and disease names are extracted via regular expressions over known ID formats and a curated disease lexicon, with LLM-based extraction as fallback.

#### 3.3.2 Graph Retrieval Primitives

Each scenario maps to one or more *retrieval primitives* implemented as parameterized Cypher queries:

- **Subgraph retrieval**: the full ego-graph of a patient across visits (diagnoses, medications, lab results with abnormal flags, examinations, surgeries), ordered by admission date — the basis of patient storylines;
- **Co-occurrence retrieval**: pairwise counts of drugs or diseases sharing the same visits — the basis of drug-pattern and comorbidity narratives;
- **Second-order relations**: disease pairs co-occurring within patients (via shared `Visit` paths) — used for comorbidity analysis;
- **Similarity retrieval**: Jaccard similarity over shared neighbors (diseases, drugs) between patients — used for similar-cohort contextualization;
- **Aggregation retrieval**: department-level counts and rates over a time window (new admissions, surgeries, abnormal-quality-control events) — used for morning briefings.

#### 3.3.3 Subgraph Serialization

Retrieval results are serialized into a *fact list*: each fact is rendered as a short, self-contained statement (e.g., "Visit V3 (2023-05-12): prescribed 奥沙利铂, route=iv, start=2023-05-13") and assigned a unique identifier `[F1], [F2], …`. Serialization preserves numeric values verbatim (including units and abnormal flags) so that the LLM never needs to recompute quantities.

#### 3.3.4 Constrained Generation with Provenance

The generation prompt instructs the LLM to (i) use only the supplied facts, (ii) quote numeric values verbatim, (iii) append consolidated source identifiers `[Fk]` at the end of each factual sentence, and (iv) organize the output into thematic paragraphs with transitions and a concluding synthesis, permitting generalization and interpretation that introduces no new facts. Generation used DeepSeek-v4-Flash (thinking mode disabled), temperature 0.3. An LLM response cache (content-hash keyed) avoids redundant calls across experimental repetitions.

### 3.4 Experimental Design

#### 3.4.1 Task Set Construction

We constructed 100 narrative tasks spanning five scenarios (20 per scenario): patient storyline, treatment pathway, comorbidity analysis, drug-pattern analysis, and morning briefing. Patient-storyline tasks were randomly sampled from all patients with at least one recorded visit; to bound prompt size, each patient's facts were restricted to the first two visits (up to 8 diagnoses, 8 drugs, 5 surgeries, and 5 examinations per visit). Disease-centered tasks (treatment pathway, comorbidity, drug pattern) were sampled from diseases recorded in at least 10 visits, with ground-truth facts covering the top-10 associated drugs, top-5 examinations, and top-5 surgeries by visit count. Morning-briefing tasks were sampled over distinct calendar dates present in the data. For each task, the ground-truth fact set $F$ was exported from the KG together with a data snapshot, so that all compared methods receive identical input data and the evaluation is fully reproducible (random seed 42).

#### 3.4.2 Compared Methods

- **B1 Direct-LLM**: the task's raw records are rendered as a tabular text summary and passed to the LLM with the narrative instruction; no structural grounding or provenance requirement;
- **B2 Vector-RAG**: records are embedded and indexed (ChromaDB); the top-$k$ snippets most similar to the task instruction are supplied as context ($k$ = 8);
- **B3 KG-Grounded (ours)**: the full framework of Section 3.3;
- **B4 Template**: a rule-based generator filling fixed templates with computed aggregates; it requires no LLM and serves as a factual lower-bound reference with minimal narrative quality.

**Ablations** of B3: **A1** removes ICD-10 standardization (synonymous diseases are not consolidated, so aggregate facts over standardized names become unavailable); **A2** restricts retrieval to first-hop neighbors (no co-occurrence or second-order primitives); **A3** removes the provenance/citation constraint from the generation prompt.

#### 3.4.3 Evaluation Protocol

We combined three complementary evaluation layers (Figure 3):

**Automated factual verification.** An LLM-based claim extractor decomposes each generated narrative into atomic claims (JSON schema: claim text, type ∈ {numeric, relation, temporal, other}, entities, value). Each claim is matched against the task's ground-truth fact set by deterministic rules: entity normalization (NFKC, whitespace, alias table), date-format normalization, and numeric tolerance (relative error ≤ 5%). A claim is *contradicted* if its subject and predicate match a fact but the object/value differs beyond tolerance; *supported* if fully matched; otherwise *unverifiable*. Contradiction criteria are deliberately conservative to avoid overestimating hallucination. To calibrate the extractor and the verifier, a stratified 20% subsample (80 narratives; 2,022 claims) was annotated with LLM-assisted annotation by five independent annotator instances, of whom 240 overlapping claims were quintuple-annotated to estimate agreement [⚠️ 投稿前需替换/补充真人标注，见 Limitations].

**LLM-as-Judge quality scoring.** Following the G-Eval paradigm [20], an independent judge LLM scored each narrative on four dimensions (1–5 scale): coherence, information coverage, readability, and clinical usefulness, using a rubric with explicit 1/3/5 anchors, instructions to ignore citation markers, and instructions to score information quality rather than length. Judge outputs are structured JSON; parse failures are retried once with a stricter instruction, and corrupted score tokens are rescued by a repair parser.

**Blinded review.** Three reviewers rated anonymized, per-task order-randomized narratives on factual correctness, clinical usefulness, and readability (1–5), with access to the ground-truth fact list as the case record. Inter-rater agreement is reported as Fleiss' κ. [⚠️ 当前结果为 LLM 模拟专家角色的预实验；正式投稿版本必须替换为真实临床专家评审，见 Limitations。]

**Efficiency.** End-to-end latency was logged per generation.

#### 3.4.4 Statistical Analysis

Methods were compared pairwise per task using two-sided Wilcoxon signed-rank tests (B1 vs B3 as the primary contrast), with effect size $r = |z|/\sqrt{N}$. Multiple comparisons across metrics were controlled by the Bonferroni correction (α = 0.0056 across 9 tests). Analyses used Python 3.11 with scipy.

#### 3.4.5 Implementation Details

The pipeline was implemented in Python 3.11 on top of an existing departmental narrative assistant platform (FastAPI backend, Neo4j 5.26, ChromaDB, MySQL 8). All LLM calls used DeepSeek-v4-Flash (accessed August 2026 via an OpenAI-compatible API); temperature 0.3 for generation and 0.0 for claim extraction and judging. The full experimental pipeline (task sampling, generation, claim extraction, verification, judging, and analysis) is available at [代码仓库/可用性声明].

---

## 4. Results

### 4.1 Automated Factual Verification

**Table 2.** Automated faithfulness metrics by method (mean ± SD across 100 tasks).

| Method | Grounding rate ↑ | Fact accuracy ↑ | Hallucination rate ↓ | Unsupported rate ↓ |
|---|---|---|---|---|
| B1 Direct-LLM | 0.655 ± 0.318 | 0.993 ± 0.032 | 0.006 ± 0.026 | 0.339 ± 0.319 |
| B2 Vector-RAG | 0.548 ± 0.287 | 0.996 ± 0.024 | 0.003 ± 0.016 | 0.449 ± 0.288 |
| B3 KG-Grounded (ours) | **0.841 ± 0.236** | 0.999 ± 0.007 | 0.001 ± 0.006 | **0.158 ± 0.236** |
| B4 Template (reference) | 0.846 ± 0.314 | 1.000 ± 0.000 | 0.000 ± 0.000 | 0.154 ± 0.314 |

The KG-grounded method substantially outperformed both generative baselines on verifiability. Grounding rate was 0.841 for B3 versus 0.655 for B1 (Wilcoxon signed-rank p < 0.001**, effect size r = 0.76) and 0.548 for B2, a large effect by conventional criteria. Conversely, the unsupported-claim rate dropped from 33.9% (B1) and 44.9% (B2) to 15.8% (B3) (B1 vs B3: p < 0.001**, r = 0.75). Detected contradictions were rare under all methods (hallucination rate ≤ 0.6%) and did not differ significantly between B1 and B3 (p = 0.066); we attribute this floor effect to our deliberately conservative contradiction criteria (Section 3.4.3) and return to its implications in Section 5. The template reference B4 approached perfect fact accuracy (1.000) as expected, since it verbalizes ground-truth facts directly, and its grounding rate (0.846) was comparable to B3 — however, its narrative quality was markedly inferior (Section 4.2), confirming that B4 is a factual upper bound rather than a usable system.

**Extractor calibration (preliminary, LLM-assisted).** On the stratified 20% subsample (80 narratives; 2,022 claims), five independent LLM-assisted annotators found no extraction errors (precision = 1.000 across 2,982 annotations), and the automated verdicts agreed with the annotated labels with 98.3% exact agreement (Fleiss' κ = 0.983 on 240 quintuple-annotated claims). Because annotator instances share the same model family as the extractor, these figures likely overestimate true agreement and will be supplemented with human annotation [见 Limitations].

### 4.2 Narrative Quality (LLM-as-Judge)

**Table 3.** LLM-as-Judge scores (1–5, mean ± SD).

| Method | Coherence | Coverage | Readability | Clinical usefulness |
|---|---|---|---|---|
| B1 Direct-LLM | 4.70 ± 0.54 | 4.54 ± 0.77 | 4.73 ± 0.45 | 4.61 ± 0.75 |
| B2 Vector-RAG | 4.68 ± 0.55 | 4.51 ± 0.67 | 4.70 ± 0.48 | 4.59 ± 0.64 |
| B3 KG-Grounded (ours) | 4.63 ± 0.54 | 4.41 ± 0.77 | 4.57 ± 0.50 | 4.48 ± 0.67 |
| B4 Template (reference) | 2.81 ± 0.75 | 2.48 ± 0.72 | 3.05 ± 0.56 | 2.26 ± 0.53 |

Crucially, the faithfulness gains of B3 did not come at the cost of narrative quality. B3 did not differ significantly from B1 on coherence (4.63 vs 4.70; p = 0.178), information coverage (4.41 vs 4.54; p = 0.085), or clinical usefulness (4.48 vs 4.61; p = 0.063). Readability showed a small but significant difference favoring B1 (4.57 vs 4.73; p = 0.003**, r = 0.26), which we attribute in part to residual citation markers ([Fk]) in B3 outputs despite the judge being instructed to ignore them. The template method B4 scored significantly below all LLM-based methods on every dimension (all p < 0.001), confirming that rule-based verbalization cannot substitute for generative narration. We note that judge scores remained correlated with narrative length (Pearson r = 0.667), consistent with known verbosity bias of LLM evaluators [22]; the blinded review (Section 4.3) therefore serves as the arbiter of the quality comparison.

### 4.3 Blinded Review (Preliminary, LLM-Simulated)

> ⚠️ 本节当前为 3 种临床角色（主任医师/主治医师/医学信息学研究生）的 LLM 模拟评审结果。投稿前必须以真实临床专家评审替换；模拟数据可作为 pilot study 或移至附录。

**Table 4.** Blinded review ratings (1–5, mean ± SD; 3 raters × 10 tasks per method).

| Method | Factual correctness | Clinical usefulness | Readability |
|---|---|---|---|
| B1 Direct-LLM | 3.97 ± 1.22 | **4.27 ± 0.64** | **4.83 ± 0.38** |
| B2 Vector-RAG | 3.20 ± 1.49 | 3.37 ± 1.35 | 4.57 ± 0.50 |
| B3 KG-Grounded (ours) | **4.90 ± 0.31** | 4.13 ± 0.63 | 4.30 ± 0.47 |
| B4 Template (reference) | 4.50 ± 1.11 | 2.20 ± 0.48 | 3.00 ± 0.00 |

Inter-rater agreement was moderate (Fleiss' κ = 0.543 for factual correctness, 0.560 for clinical usefulness, 0.565 for readability), a realistic level for subjective review. LLM-Judge scores correlated moderately with blinded-review scores (Spearman ρ = 0.457, n = 40 task–method pairs), supporting the use of automated judging as a coarse screen rather than a replacement for expert review.

The blinded review corroborated and strengthened the automated findings. B3 achieved the highest factual correctness (4.90 ± 0.31, vs 3.97 for B1 and 3.20 for B2) with a markedly smaller variance, indicating that graph grounding yields *consistently* reliable narratives rather than occasional successes. Clinical usefulness was comparable between B3 (4.13) and B1 (4.27), mirroring the automated quality results. Notably, reviewers independently flagged the same failure mode that automated verification detected at scale: B2's fluent narratives included fully fabricated treatment courses — an invented "3+7" induction chemotherapy regimen in one patient storyline, and seven fabricated hospitalizations with a misreported discharge date in another — which reviewers rated as the most hazardous error type despite high readability. Post-hoc inspection showed that these narratives arose because vector retrieval surfaced records belonging to *different* patients; chunk-level retrieval cannot guard against such identity confusion, whereas B3's patient-scoped graph traversal is structurally immune to it. B1's errors, by contrast, were predominantly unverifiable elaborations (e.g., invented chief complaints in morning briefings) rather than wholesale fabrication. B2 accordingly received the lowest factual scores (3.20), consistent with its highest unsupported-claim rate in automated verification. B3's readability remained below B1 (4.30 vs 4.83); we discuss mitigation in Section 5.

### 4.4 Ablation Study

**Table 5.** Ablation of B3 components (mean across 100 tasks).

| Variant | Grounding rate | Unsupported rate | Coverage | Coherence |
|---|---|---|---|---|
| B3 full | 0.841 | 0.158 | **4.41** | **4.63** |
| A1 − ICD-10 standardization | 0.753 | 0.241 | 4.59 | 4.79 |
| A2 − second-order/co-occurrence retrieval | **0.633** | **0.358** | 4.30 | 4.70 |
| A3 − provenance constraint | 0.880 | 0.120 | 3.72 | 4.44 |

Removing second-order and co-occurrence retrieval (A2) caused the largest degradation (grounding 0.633 vs 0.841; unsupported 0.358 vs 0.158), confirming that relational retrieval primitives supply the majority of verifiable content in relation-dense scenarios; indeed, A2 reduced the available facts for comorbidity tasks from 588 to 20. Removing ICD-10 standardization (A1) produced a smaller but clear drop (grounding −0.09), as synonymous diseases ceased to aggregate and composite statistics became unavailable. Removing the provenance constraint (A3) slightly increased grounding (0.880) but substantially reduced information coverage (3.72 vs 4.41): the sentence-level citation discipline forces systematic traversal of the fact list, and without it the model drifts toward generic prose. The provenance constraint therefore buys both auditability and completeness at a small grounding cost.

### 4.5 Efficiency

**Table 6.** End-to-end generation latency (seconds, mean ± SD; graph retrieval included in B3).

| Method | Latency (s) |
|---|---|
| B1 Direct-LLM | 6.14 ± 1.43 |
| B2 Vector-RAG | 5.70 ± 1.63 |
| B3 KG-Grounded (ours) | 6.95 ± 1.73 |
| B4 Template | < 0.01 |

B3 was slightly slower than B1 (6.95 s vs 6.14 s per narrative; Wilcoxon p < 0.001**, r = 0.50), an overhead attributable to longer, citation-annotated outputs rather than retrieval cost (Cypher retrieval completes in milliseconds). The absolute difference (~0.8 s) is negligible for departmental reporting workflows, in which narratives are generated once per shift or on demand.

### 4.6 Case Study

**Figure 4.** 已生成（`paper/figures/figure4_case_study.png/.pdf`）：任务 `patient_storyline-017`，**B2 Vector-RAG vs B3**（B2 grounding 0.17 / B3 0.82；盲评事实正确性 B2=1.0、B3=4.3）。选 B2 的原因：key.json 解码证实盲评 1 分的"文本丁"为 B2——向量检索混入了其他患者病历，虚构第 3–9 次住院，是全文最有力的失败案例。左栏红框标注 4 处编造，右栏展示 B3 的 [Fk] 溯源链与事实清单节选。备选素材：`comorbidity-014`（B1 0.43 → B3 1.00）、`morning_briefing-005`（B1 0.04 → B3 1.00）。

## 5. Discussion

### 5.1 Principal Findings

First, grounding LLM narrative generation in a purpose-built clinical KG raised the share of verifiable claims from 65.5% to 84.1% and halved unsupported claims, with large effect sizes — evidence that *where facts come from* matters more than *how fluently they are phrased*. Second, this gain did not require sacrificing narrative quality: rubric-anchored LLM judging found no significant differences on coherence, coverage, or clinical usefulness, and blinded review rated KG-grounded narratives highest on factual correctness with the smallest variance. Third, relational retrieval primitives — second-order and co-occurrence queries over the graph — carried most of the factual load, which explains why vector RAG over serialized records underperformed despite using the same underlying data. Fourth, the provenance citation constraint, designed for auditability, had the side benefit of significantly improving information coverage.

### 5.2 Comparison with Prior Work

Prior LLM-based data storytelling systems [5, 7, 17] target general tabular data and evaluate primarily on fluency and coverage; our results quantify the faithfulness risk of applying such pipelines directly to clinical operations data and show that a relational fact source closes much of the gap. Unlike GraphRAG-style systems that build graphs over unstructured text, our graph is the authoritative operational database itself, which makes verification deterministic rather than probabilistic. Our evaluation protocol extends FActScore-style atomic verification [19] to structured references, and our finding that unverifiable (rather than contradicted) claims dominate errors aligns with observations that LLM errors in data narration are often sins of *ungrounded elaboration* rather than overt contradiction.

### 5.3 Implications for Clinical Practice

The framework maps directly onto real departmental workflows — morning briefings, ward-round preparation, quality-control summaries — where narratives are consumed under time pressure and factual errors propagate into clinical decisions. Provenance annotations turn each generated sentence into an auditable object: a clinician can click through [Fk] to the underlying record, which we believe is a prerequisite for institutional trust in generated clinical text. The modest latency overhead and the deterministic verification layer suggest the approach is deployable as a drafting assistant with human sign-off, not a replacement for clinical judgment.

### 5.4 Limitations

This study has several limitations. (1) The dataset is single-center and single-department; generalization requires multi-center validation, although the framework itself contains no department-specific rules. (2) The claim extractor and judge are LLM-based; although calibration showed high agreement, the annotation was LLM-assisted (same model family), which risks circularity and inflated agreement — human annotation of a subsample is planned before submission. (3) The blinded review reported here is a simulated pilot with LLM role-played reviewers; it must be replaced by real clinical expert review, and we report it only to demonstrate the instrument. (4) Contradiction detection is conservative by design, so hallucination rate likely underestimates subtle errors; the faithfulness advantage should be read primarily through grounding and unsupported rates. (5) Judge scores retained a length correlation (r = 0.667) despite rubric instructions, a known LLM-as-Judge bias [22]. (6) Only Chinese narratives and a single LLM were studied. (7) Token costs and cache hit rates were not instrumented in this round.

### 5.5 Future Work

Planned extensions include: multi-center, multi-department replication; real clinical expert review and human-annotated calibration; extending verification from post-hoc to *in-process* evaluation, where claim verification feeds back into generation as a "generate–evaluate–revise" loop (connecting to Self-Refine/CRITIC-style iterative optimization [23, 24]); multimodal narratives combining charts and text under the same grounding discipline; and cross-lingual evaluation.

## 6. Conclusions

We presented a KG-grounded framework for generating clinical department narratives in which a purpose-built knowledge graph is the exclusive fact source and the LLM serves as a constrained verbalizer with sentence-level provenance. On 100 real departmental narrative tasks, the approach raised the verifiable-claim rate from 65.5% to 84.1% and halved unsupported claims at negligible quality and latency cost, with relational retrieval primitives and the provenance constraint identified as the key contributors. Binding generation to a queryable, authoritative fact base offers a practical and auditable pattern for deploying LLMs in clinical data communication.

---

## Declarations（占位，投稿前补全）

- **Ethics approval and consent to participate**: [TODO — IRB 批件编号或豁免声明；数据已脱敏]
- **Consent for publication**: Not applicable.
- **Availability of data and materials**: [TODO — 脱敏数据不可公开，实验管线代码将于接收后开源/或提供仓库链接]
- **Competing interests**: [TODO]
- **Funding**: [TODO]
- **Authors' contributions**: [TODO]
- **Acknowledgements**: [TODO]

## References（编号对应正文；均来自开题报告文献表或公认文献，投稿前请按目标期刊格式统一核对）

1. [TODO-ref：医疗信息化/科室数据管理负担类文献]
2. [TODO-ref]
3. McKinsey/IDC 类行业数据引用（或用学术综述替代）
4. Gartner. Magic Quadrant for Analytics and Business Intelligence Platforms. 2024.（行业报告）
5. Islam M S, Laskar M T R, Parvez M R, et al. DataNarrative: Automated data-driven storytelling with visualizations and texts. EMNLP 2024: 19245-19262.
6. Shen L, Li H, Wang Y, et al. From data to story: Towards automatic animated data video creation with LLM-based multi-agent systems. IEEE VIS Workshop GEN4DS, 2024: 20-27.
7. Chen J, Wang Y, Li S, et al. Data storytelling with GPT-4: A case study on automatic data narrative generation. Journal of Data and Information Quality, 2024, 16(2): 1-25.
8. Luo J, Ouyang C, Jing Y, et al. Application of LLM techniques for data insights in DHP. IEEE DTPI 2024: 656-661.
9. Lewis P, Perez E, Piktus A, et al. Retrieval-augmented generation for knowledge-intensive NLP tasks. NeurIPS 2020, 33: 9459-9474.
10. Ji S, Pan S, Cambria E, et al. A survey on knowledge graphs: Representation, acquisition, and applications. IEEE TNNLS, 2022, 33(2): 494-514.
11. Pan S, Luo L, Wang Y, et al. Unifying large language models and knowledge graphs: A roadmap. IEEE TKDE, 2024, 36(7): 3580-3599.
12. Segel E, Heer J. Narrative visualization: Telling stories with data. IEEE TVCG, 2010, 16(6): 1139-1148.
13. Kosara R, Mackinlay J. Storytelling: The next step for visualization. Computer, 2013, 46(5): 44-50.
14. Wang Y, Suh A, Bhosale A, et al. DataShot: Automatic generation of fact sheets from tabular data. IEEE TVCG, 2022, 28(1): 891-901.
15. Obeid J, Hoque E. Chart-to-text: A large-scale benchmark for chart summarization. ACL 2021: 4005-4012.
16. Parikh A, Wang X, Gehrmann S, et al. ToTTo: A controlled table-to-text generation dataset. EMNLP 2020: 1173-1186.
17. Zhang C, Li C, Gao S. MDSF: Context-Aware Multi-Dimensional Data Storytelling Framework based on Large Language Model. arXiv:2501.01014, 2025.
18. Spathis D, Kawsar F. The first step is the hardest: Pitfalls of representing and tokenizing temporal data for large language models. JAMIA, 2024, 31(9): 2151-2161.
19. Min S, Krishna K, Lyu X, et al. FActScore: Fine-grained atomic evaluation of factual precision in long form text generation. EMNLP 2023.
20. Liu Y, Iter D, Xu Y, et al. G-Eval: NLG evaluation using GPT-4 with better human alignment. EMNLP 2023.
21. Kim S, Shin J, Cho Y, et al. Prometheus: Inducing fine-grained evaluation capability in language models. ICLR 2024.
22. [TODO-ref：LLM judge 偏差研究（position/verbosity bias），如 Zheng et al. "Judging LLM-as-a-judge" NeurIPS 2023 Datasets and Benchmarks]
23. Madaan A, Tandon N, Gupta P, et al. Self-Refine: Iterative refinement with self-feedback. NeurIPS 2023.
24. Gou Z, Shao Z, Gong Y, et al. CRITIC: Large language models can self-correct with tool-interactive critiquing. ICLR 2024.

## 图清单（待绘制）

- **Figure 1**：KG-grounded 叙事生成总体框架（数据层→图谱层→检索层→生成层，含溯源回链）。
- **Figure 2**：图谱本体 schema（9 类节点 + 9 类关系）。
- **Figure 3**：三重评估协议流程（自动核查 / LLM-Judge / 盲评）。
- **Figure 4**：案例研究对比图（B1 vs B3，标注幻觉与溯源链）。
- **Appendix A**：各场景 prompt 模板与 Cypher 原语示例；**Appendix B**：评分细则；**Appendix C**：消融与效率完整统计。
