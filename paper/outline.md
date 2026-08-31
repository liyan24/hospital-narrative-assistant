# 论文详细提纲

**工作标题**：KG-Grounded Narrative Generation for Clinical Department Data: A Faithfulness-Oriented Approach
（知识图谱增强大语言模型的临床科室数据叙事生成方法：一种面向事实保真的方法）

**目标期刊（医学信息学 SCI，按优先级）**：
1. *Journal of Biomedical Informatics* (JBI, IF≈4, 方法+实验均衡，最契合)
2. *JMIR Medical Informatics* 或 *Journal of Medical Internet Research* (JMIR, 偏应用与系统评估)
3. *BMC Medical Informatics and Decision Making*（接受度高、周期快，保底）
4. *Artificial Intelligence in Medicine*（方法权重更高，可冲）

**全文预算**：正文 6000–8000 词（不含参考文献），图表 6–8 个，参考文献 40–60 篇。
**写作语言**：英文投稿，先用中文打草稿各节论点再翻译，或直接英文写作。

---

## Title / Abstract / Keywords

### Abstract（结构式，250–300 词，按 JMIR/JBI 模板）

- **Background**：医疗机构数据量激增，但科室级数据洞察仍依赖人工整理；LLM 直接生成数据叙事存在事实性幻觉，在医疗场景不可接受。
- **Objective**：提出并验证一种知识图谱约束（KG-grounded）的临床数据叙事生成框架，在不损害叙事质量的前提下提升事实保真度。
- **Methods**：多源异构科室数据（入院/出院/检查/检验/手术/医嘱）经清洗与 ICD-10 标准化后构建知识图谱；叙事请求经意图解析映射为图检索原语，检索子图序列化为事实清单，约束 LLM 生成并标注来源。在真实脱敏数据集（3,990 患者、13,743 次就诊）上构建 100 个叙事任务（5 类场景），与 3 个基线对比；采用自动事实核查（断言抽取+图谱比对）、LLM-as-Judge 多维评分与临床专家盲评三重评估。
- **Results**：（待实验填入：B3 vs B1 的事实准确率提升、幻觉率下降、叙事质量无显著差异、效率开销）。
- **Conclusions**：图谱约束以较小的效率代价显著提升医疗数据叙事的事实保真度，为 LLM 在高风险医疗场景的文本生成提供了可行范式。
- **Keywords**：data storytelling; knowledge graph; large language model; hallucination; faithfulness; clinical informatics; retrieval-augmented generation

---

## 1. Introduction（约 1000–1200 词）

### 1.1 背景与动机（3 段）
- 段 1：医疗数据爆炸与"数据丰富、洞察贫乏"悖论；科室日常场景（晨会交班、查房、质控、运营汇报）依赖人工从多系统拼凑数据，耗时且易错（引用医疗信息化与数据叙事文献）。
- 段 2：数据叙事（data storytelling）在 BI 领域已被 Gartner 等列为核心能力；LLM 使自动化数据叙事成为可能（引 DataNarrative、GPT-4 data storytelling 等）。
- 段 3：**问题**：LLM 直接生成在数值、实体关系上产生幻觉；医疗场景对事实错误零容忍；现有 RAG 多面向非结构化文本，对结构化/关系型医疗数据的"关系事实"（共现、路径、时序）支撑不足。

### 1.2 本文方法概览（1 段 + Figure 1 指引）
提出 KG-grounded 叙事生成框架：数据层（清洗+ICD-10 标准化）→ 图谱层（9 类节点本体）→ 检索层（意图→图检索原语）→ 生成层（事实清单约束 + 来源标注）。核心思想：**事实由图谱供给，LLM 只负责组织与表达**，生成内容与来源可追溯。

### 1.3 贡献（bullet，3–4 条）
1. 提出面向临床科室数据的 KG-grounded 叙事生成框架，将叙事意图形式化为图检索原语，实现"事实供给—语言表达"解耦；
2. 设计覆盖 5 类科室叙事场景的任务构建方法，以及"断言抽取—图谱核查"的自动事实性评估协议；
3. 在真实脱敏科室数据（3,990 患者/13,743 就诊/约 114 万医嘱）上完成系统实验：与直接生成、向量 RAG、模板法对比，自动评估 + LLM 评审 + 临床专家盲评三重验证；
4. （可选）开源实验管线与评测协议。

### 1.4 论文结构（1 小段）

---

## 2. Related Work（约 1200–1500 词）

### 2.1 Data Storytelling and Automated Narrative Generation
- 叙事可视化经典（Segel & Heer 2010；Kosara & Mackinlay 2013）→ 自动化工具（DataShot、AutoClips）→ LLM 驱动（DataNarrative、Data Director、MDSF）。
- **缺口**：大多面向通用表格/BI 场景，缺少医疗领域的事实性保障机制。

### 2.2 LLMs for Clinical Text Generation
- 医疗 LLM 应用综述（LLM in DHP、临床摘要生成、discharge summary 生成等）；
- 医疗幻觉问题研究（factuality in clinical NLG，引 2–3 篇放射报告/病历摘要事实性评估工作）。
- **缺口**：医疗文本生成评估多针对自由文本（病历），缺少针对"结构化数据→叙事"的事实性评测。

### 2.3 Knowledge Graphs + LLMs / Retrieval-Augmented Generation
- KG×LLM 路线（Pan et al. 2024 roadmap；Ji et al. 2022）；GraphRAG 类工作；医疗 KG（如 UMLS、中文医疗图谱）及其在问答中的应用。
- **缺口**：GraphRAG 主要面向非结构化语料的图索引；将业务关系型数据整体图谱化并作为叙事事实源的研究少。

### 2.4 Evaluation of Factual Consistency
- 自动评估：断言抽取+验证（QAG/FActScore 思路）、G-Eval/Prometheus 等 LLM-as-Judge；医疗领域人工评估惯例。
- **定位**：本文将 FActScore 式原子断言验证移植到"结构化事实库（KG）作为参照"的场景。

### 2.5 Summary（表格或一段）：本文与最接近工作的差异矩阵（领域、事实源类型、评估方式、是否溯源）。

---

## 3. Materials and Methods（约 2000–2500 词，核心章）

### 3.1 Problem Formulation
- 形式化：给定多源科室数据集合 D = {入院, 出院, 检查, 检验, 手术, 医嘱} 与叙事意图 q（场景、对象、受众），生成叙事文本 S；目标：最大化 factuality(S, D) 同时保持质量指标 quality(S)。
- 定义事实断言（atomic factual claim）、幻觉（contradicted claim）、不可考断言（unverifiable claim）。

### 3.2 Data and Knowledge Graph Construction
- 3.2.1 数据集：郸城某医院肿瘤血液科脱敏数据，规模统计表（**Table 1**：患者 3,990、就诊 13,743、医嘱约 114 万、检验约 5.5 万、检查约 2 万、手术 85）；脱敏与伦理声明。
- 3.2.2 数据清洗与标准化：疾病名标准化、ICD-10 三级映射（精确→子串→模糊匹配），药品名归一；报告映射覆盖率统计。
- 3.2.3 图谱本体与构建：9 类节点（Patient/Visit/Disease/Drug/Exam/LabItem/Surgery/ChiefComplaint/Department）+ 关系（就诊-诊断、就诊-用药、就诊-检查等）；构建流程（MySQL→清洗→批量 MERGE）；规模 32,694 节点 / 788,119 关系（**Figure 2**：本体 schema 图）。

### 3.3 KG-Grounded Narrative Generation Framework（**Figure 1**：总体框架图）
- 3.3.1 意图解析：场景分类（patient / disease / drug / comorbidity / pathway / briefing）+ 实体抽取。
- 3.3.2 图检索原语：子图检索（患者全量时间线）、共现检索（药品/疾病共现计数）、二阶关系（合并症对）、相似度检索（Jaccard 共同邻居）；每类原语对应 Cypher 模式（附示例）。
- 3.3.3 子图序列化：检索结果→结构化事实清单（每条事实带唯一 fact_id）。
- 3.3.4 受约束生成：prompt 模板要求"仅使用给定事实、数值逐字引用、句末标注 [fact_id]"；输出叙事 + 来源标注。

### 3.4 Experimental Design
- 3.4.1 任务集构建：5 场景 × 20 任务 = 100 任务；采样规则（患者故事线按就诊次数分层抽样、合并症按高频疾病抽样等）；每任务从图谱导出 ground-truth 事实集。
- 3.4.2 对比方法：
  - B1 Direct-LLM：表格化数据摘要直接进 prompt；
  - B2 Vector-RAG：向量检索片段 + LLM；
  - B3 KG-Grounded（本文）；
  - B4 Template：规则模板（下界参照）。
  - 消融：A1 去 ICD-10 标准化；A2 仅一度邻居（无二阶/共现检索）；A3 去来源标注约束。
- 3.4.3 评估协议（**Figure 3**：评测流程图）：
  - 自动事实性：LLM 断言抽取器 → 与 ground-truth 事实集比对 → fact accuracy / hallucination rate / unsupported rate；抽取器自身在 20% 样本人工校准（报告一致率）；
  - LLM-as-Judge：连贯性、覆盖度、可读性、临床有用性 4 维 1–5 分；报告与人工评分的 Spearman 相关；
  - 人工盲评：3–5 名评估者（临床医生+医学研究生），随机打乱方法来源，维度：事实正确性、临床有用性、可读性；报告 Fleiss' κ；
  - 效率：端到端延迟、token 消耗、缓存命中率。
- 3.4.4 统计分析：配对 Wilcoxon 符号秩检验（B1 vs B3，按任务配对），效应量 r；Bonferroni 校正多重比较；显著性阈值 0.05。
- 3.4.5 实现细节：模型（DeepSeek/GPT 版本与温度）、Neo4j 版本、硬件、代码可用性声明。

---

## 4. Results（约 1200–1500 词）

### 4.1 自动事实性评估（**Table 2**）
- 各方法 fact accuracy / hallucination rate / unsupported rate 均值±标准差；B3 vs B1 的检验结果。
- 断言抽取器校准结果（抽取准确率/一致率）。
- 预期叙述：B3 幻觉率显著低于 B1/B2；B4 事实性最高但叙事质量差（下界参照的作用）。

### 4.2 叙事质量评估（**Table 3**）
- LLM-as-Judge 4 维评分；B3 与 B1 在连贯性/可读性上无显著差异（说明图谱约束不损质量），覆盖度 B3 更优。
- LLM-Judge 与人评的 Spearman 相关（支持自动评测可信度）。

### 4.3 人工盲评（**Table 4**）
- 三维评分 + Fleiss' κ；与自动指标方向一致。

### 4.4 消融实验（**Table 5**）
- A1/A2/A3 对幻觉率与覆盖度的影响，逐项论证各组件贡献（预期：A1 影响实体匹配、A2 影响关系事实覆盖、A3 影响可核查性）。

### 4.5 效率分析（**Table 6** 或并入 4.4）
- 延迟、token、缓存命中率；B3 额外开销量化。

### 4.6 案例研究（**Figure 4**）
- 1–2 个典型任务：并排展示 B1 与 B3 输出片段，标注 B1 的幻觉实例（编造的检验值、张冠李戴的用药）与 B3 的 [fact_id] 溯源。

---

## 5. Discussion（约 800–1000 词）

### 5.1 Principal Findings
- 3–4 条要点式总结：图谱约束显著降幻觉；质量不降；二阶关系检索对合并症/路径类场景贡献最大；效率代价可接受。

### 5.2 Comparison with Prior Work
- 与 DataNarrative / GraphRAG / 医疗 NLG 事实性工作的对比定位。

### 5.3 Implications for Clinical Practice
- 对晨会、质控、查房场景的落地意义；人机协同定位（辅助而非替代）；溯源机制对临床信任的价值。

### 5.4 Limitations
- 单中心、单科室；图谱覆盖度决定 unverifiable 比例；断言抽取器依赖 LLM；中文场景为主；未做患者结局相关性验证。

### 5.5 Future Work
- 多中心扩展；将自动评测嵌入生成过程形成"生成—评测—反馈—优化"闭环（衔接博士论文研究内容四）；多模态叙事（图表+文本协同）。

---

## 6. Conclusions（约 150–200 词）
一段式：重申问题、方法、核心结果数字、意义。

---

## 附录与补充材料
- Appendix A：各场景 prompt 模板与检索原语 Cypher 示例；
- Appendix B：评估 rubric（LLM-as-Judge 评分细则、人工评估表）；
- Appendix C：消融与效率的完整统计表；
- Data Availability / Code Availability / Ethics / Author Contributions / Funding / Conflicts of Interest（按期刊模板）。

---

## 图表清单（汇总）

| 编号 | 内容 | 所在节 |
|---|---|---|
| Figure 1 | KG-grounded 叙事生成总体框架图（四层） | 3.3 |
| Figure 2 | 图谱本体 schema 图（9 类节点+关系） | 3.2.3 |
| Figure 3 | 三重评估协议流程图 | 3.4.3 |
| Figure 4 | 案例研究：B1 vs B3 输出对比标注 | 4.6 |
| Table 1 | 数据集统计 | 3.2.1 |
| Table 2 | 自动事实性指标主表 | 4.1 |
| Table 3 | LLM-as-Judge 质量评分 | 4.2 |
| Table 4 | 人工盲评结果 + κ | 4.3 |
| Table 5 | 消融实验 | 4.4 |
| Table 6 | 效率对比（延迟/token/缓存命中率） | 4.5 |

## 实验与正文的对应关系（experiments/ 管线产出 → 论文素材）

| 管线输出 | 论文位置 |
|---|---|
| `output/tasks.jsonl` | 3.4.1 任务集描述 |
| `output/generations.jsonl` | 4.6 案例研究素材 |
| `output/verdicts.jsonl` + `results_summary.csv` | Table 2（自动事实性） |
| `output/scores.jsonl` + `results_summary.csv` | Table 3（LLM-as-Judge） |
| `analysis.py` 的 Wilcoxon 输出 | 4.1–4.4 统计检验段落 |
| 消融运行（改配置生成 A1/A2/A3） | Table 5 |
| 生成日志中的 latency/token | Table 6 |

## 写作顺序建议

1. 先跑通实验拿到 Table 2/3 的数字（方法有效性的前提）；
2. 写 Methods（3.x）——管线代码即文档，照着写；
3. 写 Results——数字驱动；
4. 写 Introduction/Discussion——最后打磨故事线；
5. Related Work 可复用开题报告第二章文献，但需补充医疗 NLG 事实性评估方向的 5–8 篇新文献（开题报告里这块偏弱）。
