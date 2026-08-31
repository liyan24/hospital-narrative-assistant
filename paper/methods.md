# 3. Materials and Methods

> 状态：初稿（Draft v0.1）。方括号 […] 为待实验后填入的数字或待确认的引用。对应提纲 `paper/outline.md` 第 3 节。

## 3.1 Problem Formulation

Let $D = \{D_{adm}, D_{dis}, D_{exam}, D_{lab}, D_{surg}, D_{ord}\}$ denote the multi-source structured data of a clinical department, covering admission records, discharge records, examinations, laboratory results, surgeries, and medication orders, respectively. Given a narrative intent $q = (s, e, a)$ — where $s$ is the narrative scenario (e.g., patient storyline, treatment pathway analysis), $e$ is the narrative subject (a patient identifier or a disease name), and $a$ is the intended audience — the goal is to generate a narrative text $S$ that maximizes factual fidelity to $D$ while preserving narrative quality.

We define an *atomic factual claim* as a minimal, independently verifiable statement in $S$ about an entity, a numeric value, a relation, or a temporal fact. Given a reference fact set $F$ derived from $D$, each extracted claim $c$ is labeled as *supported* (entailed by some $f \in F$), *contradicted* (conflicting with some $f \in F$), or *unverifiable* (no corresponding fact in $F$). We operationalize faithfulness through three metrics: **fact accuracy** $= |\text{supported}| / (|\text{supported}| + |\text{contradicted}|)$, **hallucination rate** $= |\text{contradicted}| / |\text{claims}|$, and **unsupported rate** $= |\text{unverifiable}| / |\text{claims}|$. The central hypothesis of this study is that constraining LLM generation with facts retrieved from a purpose-built knowledge graph (KG) increases fact accuracy and reduces hallucination, compared with feeding raw tabular summaries or loosely retrieved text snippets to the same LLM.

## 3.2 Data and Knowledge Graph Construction

### 3.2.1 Dataset

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

### 3.2.2 Data Cleaning and Standardization

Raw records were exported as seven Excel workbooks and ingested into a relational database (MySQL 8). Cleaning included: (i) normalization of disease names (whitespace, full/half-width characters, punctuation variants); (ii) mapping of Western-medicine diagnoses to ICD-10 codes through a three-tier procedure — exact match, substring match, and fuzzy match (similarity threshold 85) with manual overrides — against a reference ICD-10 vocabulary (GB/T 14396-2016 extension codes). Of 1,347 distinct standardized Western-medicine disease names, 977 (72.5%) were successfully mapped to ICD-10 codes (exact: 631; substring: 185; fuzzy: 95; manual override: 66); the remaining 370 were predominantly composite diagnoses and post-treatment status expressions and were retained unmapped; and (iii) normalization of drug names and consolidation of synonymous entries. Traditional Chinese medicine (TCM) syndrome diagnoses were retained as a separate disease type.

### 3.2.3 Ontology and Graph Construction

We designed a department-level clinical ontology with nine node types — `Patient`, `Visit`, `Disease` (typed as `western` or `tcm_syndrome`), `Drug`, `Exam`, `LabItem`, `Surgery`, `ChiefComplaint`, and `Department` — and nine relation types (Figure 2): `(Patient)-[:HAS_VISIT]->(Visit)`; `(Visit)-[:DIAGNOSED_WITH {diagnosis_type, is_main}]->(Disease)`; `(Visit)-[:CHIEF_COMPLAINT]->(ChiefComplaint)`; `(Visit)-[:PERFORMED_EXAM {exam_date, description}]->(Exam)`; `(Visit)-[:HAS_LAB_RESULT {value, unit, abnormal_flag}]->(LabItem)`; `(Visit)-[:PRESCRIBED {dosage, frequency, route, start_date}]->(Drug)`; `(Visit)-[:UNDERWENT {start_date}]->(Surgery)`; `(Visit)-[:IN_DEPARTMENT]->(Department)`; and `(Drug|Surgery)-[:TREATS {evidence}]->(Disease)`. `Patient` nodes carry demographic attributes (age, marital status, occupation, allergy history); `Visit` nodes carry admission/discharge dates and length of stay. The resulting KG contains 32,694 nodes and 788,119 relationships, stored in Neo4j 5.26 (Figure 2). Because disease nodes are keyed by a composite of display name and type, entity matching throughout this study uses the normalized display name.

## 3.3 KG-Grounded Narrative Generation Framework

The framework (Figure 1) decouples *fact supply* from *verbalization*: the KG is the sole source of facts, and the LLM is restricted to organizing and expressing retrieved facts with explicit provenance.

### 3.3.1 Intent Parsing

A narrative request is parsed into a scenario label and a subject entity using a hybrid rule-plus-LLM parser. Scenarios include patient-centered narratives (`patient`), disease-centered analyses (`disease`, `drug`, `comorbidity`, `pathway`), and department-level briefings (`briefing`). Patient identifiers and disease names are extracted via regular expressions over known ID formats and a curated disease lexicon, with LLM-based extraction as fallback.

### 3.3.2 Graph Retrieval Primitives

Each scenario maps to one or more *retrieval primitives* implemented as parameterized Cypher queries:

- **Subgraph retrieval**: the full ego-graph of a patient across visits (diagnoses, medications, lab results with abnormal flags, examinations, surgeries), ordered by admission date — the basis of patient storylines;
- **Co-occurrence retrieval**: pairwise counts of drugs or diseases sharing the same visits — the basis of drug-pattern and comorbidity narratives;
- **Second-order relations**: disease pairs co-occurring within patients (via shared `Visit` paths) — used for comorbidity analysis;
- **Similarity retrieval**: Jaccard similarity over shared neighbors (diseases, drugs) between patients — used for similar-cohort contextualization;
- **Aggregation retrieval**: department-level counts and rates over a time window (new admissions, surgeries, abnormal-quality-control events) — used for morning briefings.

### 3.3.3 Subgraph Serialization

Retrieval results are serialized into a *fact list*: each fact is rendered as a short, self-contained statement (e.g., "Visit V3 (2023-05-12): prescribed 奥沙利铂, route=iv, start=2023-05-13") and assigned a unique identifier `[F1], [F2], …`. Serialization preserves numeric values verbatim (including units and abnormal flags) so that the LLM never needs to recompute quantities.

### 3.3.4 Constrained Generation with Provenance

The generation prompt instructs the LLM to (i) use only the supplied facts, (ii) quote numeric values verbatim, and (iii) append the source fact identifier `[Fk]` to every factual sentence. The prompt further specifies audience-appropriate style (professional, concise Chinese clinical register). Generation used DeepSeek-v4-Flash (thinking mode disabled), temperature 0.3. An LLM response cache (content-hash keyed) avoids redundant calls across experimental repetitions and provides the cache hit rate reported in Section 4.5.

## 3.4 Experimental Design

### 3.4.1 Task Set Construction

We constructed 100 narrative tasks spanning five scenarios (20 per scenario): patient storyline, treatment pathway, comorbidity analysis, drug-pattern analysis, and morning briefing. Patient-storyline tasks were randomly sampled from all patients with at least one recorded visit; to bound prompt size, each patient's facts were restricted to the first two visits (up to 8 diagnoses, 8 drugs, 5 surgeries, and 5 examinations per visit). Disease-centered tasks (treatment pathway, comorbidity, drug pattern) were sampled from diseases recorded in at least 10 visits, with ground-truth facts covering the top-10 associated drugs, top-5 examinations, and top-5 surgeries by visit count. Morning-briefing tasks were sampled over distinct calendar dates present in the data. For each task, the ground-truth fact set $F$ was exported from the KG together with a data snapshot, so that all compared methods receive identical input data and the evaluation is fully reproducible (random seed 42).

### 3.4.2 Compared Methods

- **B1 Direct-LLM**: the task's raw records are rendered as a tabular text summary and passed to the LLM with the narrative instruction; no structural grounding or provenance requirement;
- **B2 Vector-RAG**: records are embedded and indexed (ChromaDB); the top-$k$ snippets most similar to the task instruction are supplied as context ($k$ = [8]);
- **B3 KG-Grounded (ours)**: the full framework of Section 3.3;
- **B4 Template**: a rule-based generator filling fixed templates with computed aggregates; it requires no LLM and serves as a factual lower-bound reference with minimal narrative quality.

**Ablations** of B3: **A1** removes ICD-10 standardization (synonymous diseases are not consolidated); **A2** restricts retrieval to first-hop neighbors (no co-occurrence or second-order primitives); **A3** removes the provenance/citation constraint from the generation prompt.

### 3.4.3 Evaluation Protocol

We combined three complementary evaluation layers (Figure 3):

**Automated factual verification.** An LLM-based claim extractor decomposes each generated narrative into atomic claims (JSON schema: claim text, type ∈ {numeric, relation, temporal, other}, entities, value). Each claim is matched against the task's ground-truth fact set by deterministic rules: entity normalization (NFKC, whitespace, alias table), numeric tolerance (relative error ≤ 5%), and relation-triple matching. A claim is *contradicted* if its subject and predicate match a fact but the object/value differs beyond tolerance; *supported* if fully matched; otherwise *unverifiable*. To calibrate the extractor itself, two authors independently annotated a random 20% subsample of narratives; we report extractor precision/recall against these annotations [待填].

**LLM-as-Judge quality scoring.** Following the G-Eval paradigm, an independent judge LLM scored each narrative on four dimensions (1–5 scale): coherence, information coverage, readability, and clinical usefulness, using a detailed rubric (Appendix B). Judge outputs are structured JSON; parse failures are retried once. We report Spearman correlation between judge scores and human ratings on a subsample to validate the judge [待填].

**Expert blind review.** [3–5] evaluators ( clinicians and medical postgraduates) rated anonymized, order-randomized narratives on factual correctness, clinical usefulness, and readability (1–5). Inter-rater agreement is reported as Fleiss' κ.

**Efficiency.** End-to-end latency, token consumption, and cache hit rate were logged per generation.

### 3.4.4 Statistical Analysis

Methods were compared pairwise per task using two-sided Wilcoxon signed-rank tests (B1 vs B3 as the primary contrast), with effect size $r = |z|/\sqrt{N}$. Multiple comparisons across metrics were controlled by the Bonferroni correction. Significance threshold $\alpha = 0.05$. Analyses used Python 3.11 with scipy [版本]; when fewer than 5 non-zero paired differences were available, tests were omitted and reported as NA.

### 3.4.5 Implementation Details

The pipeline was implemented in Python 3.11 on top of the existing departmental narrative assistant platform (FastAPI backend, Neo4j 5.26, ChromaDB, MySQL 8). All LLM calls used DeepSeek-v4-Flash (accessed [月份待填] via an OpenAI-compatible API); temperature 0.3 for generation and 0.0 for claim extraction and judging. The full experimental pipeline (task sampling, generation, claim extraction, verification, judging, and analysis) is available at [代码仓库/可用性声明].

---

## 写作备注（不进入正文）

1. 待实验后回填：ICD-10 映射覆盖率、断言抽取器校准的 precision/recall、judge 与人评的 Spearman ρ、专家人数与 κ。
2. 伦理声明：需要向数据提供方确认是否有 IRB 批件或豁免；JMIR/JBI 均要求明确写出。
3. 模型名称与版本、Neo4j/ChromaDB 版本需在投稿前按实际环境锁定。
4. 3.4.1 中 [N]/[M] 阈值要与 `experiments/tasks.py` 的实际采样参数一致，跑完冒烟后核对。
5. 若评审质疑 B2 的 k 值，可在附录补 k 敏感性分析（k=4/8/16）。
