# System One 模型（Jev 类）嵌入优化方案

> 版本：v1.0　　适用系统：医院叙事生成助手（HNA）　　日期：2026-09-29
> 性质：架构优化提案（未实施），供评审与排期参考

## 1. 背景：什么是 System One 模型

2026 年 9 月 TypeSafe AI 发布的 Jev 提出了一个新模型类别——**System One 模型**。名称借自卡尼曼《思考，快与慢》：System 1 是快速、直觉、低成本的判断；System 2 是缓慢、审慎的分析。

Jev 类模型与传统 LLM 的本质区别：

| | System One 模型（Jev 类） | System Two（DeepSeek/GPT 等 LLM） |
|---|---|---|
| 工作方式 | 非自回归：一次前向传播对**预定义的固定输出空间**打分 | 自回归：逐 token 生成自由文本 |
| 输出 | 结构化决策 + 置信度（分类/选择/评分） | 任意文本（叙事、论文、解读） |
| 速度/成本 | 毫秒级、极低成本 | 秒~分钟级、按 token 计费 |
| 典型角色 | 路由、分类、判定、打分 | 生成、解释、写作、推理 |

**适用边界很重要**：Jev 类模型不能写文章、不能做解释——它只回答「选项有限的判断题」。凡输出需要给人阅读的文字，仍需 LLM。

> 提示：Jev 发布初期网络上的性能数据（如"193 倍快""444 倍便宜"）多来自低权威站点的相互转载，可信度存疑。本方案不引用这些数字，只基于「固定输出空间单次打分」这一已确认的机制做架构推演。另外「从不幻觉」的说法应理解为「不生成自由文本所以无文本幻觉」，其**判断本身仍可能出错**，医疗场景必须保留置信度阈值与人工兜底。

## 2. 我们系统的现状与痛点

本系统所有 AI 能力都走单一 LLM 通道（`services/llm_service.py` → DeepSeek）。实际运行中暴露的痛点：

1. **决策型调用也在用生成模型**：文献相关性重排只要输出 `[2,0,5]`，议题可行性只要输出「高/中/低」，引用核验只要输出不支持编号——却都要走完整的文本生成，慢且贵
2. **思考模式引发的故障**：思维链消耗 max_tokens 导致空内容、长推理导致 `Request timed out`（再入院分析案例）——这些恰恰都是决策型调用，本不需要长推理
3. **规则硬编码的隐性决策点**：诊断归一化（同义词映射表）、药品/非药品关键词过滤、检验异常标记（按"高/低/↑"字符串匹配）——规则覆盖不全时静默出错
4. **失败缓存放大抖动**：一次超时结果被缓存，用户长时间看到旧错误（已修复为短 TTL，但根因是决策调用不该走到超时）

## 3. 嵌入方案：三层认知架构

```
┌─────────────────────────────────────────────────────┐
│  System 0：缓存与规则层（已有）                        │
│  llm_cache / result_cache / 归一化规则表              │
│  命中即返回，零模型调用                                 │
├─────────────────────────────────────────────────────┤
│  System 1：决策层（新增，Jev 类模型）                  │
│  固定输出空间的快速判断：分类、路由、相关性打分、         │
│  置信度评估。毫秒级返回，失败时回退规则                  │
├─────────────────────────────────────────────────────┤
│  System 2：生成层（现有 DeepSeek）                     │
│  只承担真正需要生成文本的任务：叙事、解读、论文           │
└─────────────────────────────────────────────────────┘
```

原则：**能用规则的不调模型（System 0），能打判断题的不写小作文（System 1），必须生成文字的才用 LLM（System 2）**。

## 4. 具体嵌入点（按优先级）

### P0 — 决策型 LLM 调用替换（收益最直接）

| 现有调用点 | 位置 | 当前方式 | System 1 改造 |
|---|---|---|---|
| 文献相关性重排 | `skills/writing.py` `_rerank` | LLM 生成编号 JSON | 对每篇文献打分（相关度 0-1 + 置信度），取 Top N |
| 引用-论断核验 | `research_assistant_service.py` citation_verify | LLM 逐条判断输出 JSON | 逐对（句子, 文献）做二分类：支持/不支持 + 置信度 |
| 自定义议题可行性 | `auto_research_service.py` evaluate_custom_topic | LLM 生成长文评估 | 拆成两步：S1 判定「高/中/低 + 缺什么数据类别」，S2 仅在需要时生成解释文字 |
| PubMed 检索式改写选择 | `skills/writing.py` `_expand` | LLM 生成改写 | S1 在候选检索式模板中选择，消除生成失败分支 |
| 意图路由（RAG） | `kg_rag_service.py` | 固定流程 | S1 路由：走图谱查询 / 向量检索 / 直接回答 |

### P1 — 规则硬编码点升级为模型判定

| 现有规则点 | 位置 | 现状问题 | System 1 改造 |
|---|---|---|---|
| 检验异常判定 | `kg_mysql_loader.py` / 检验清洗 | 字符串匹配「高/低/↑/↓」，空 hint 即丢异常标记 | S1 结合（结果值, 参考范围, 单位）判定正常/偏高/偏低/危急 |
| 药品/非药品过滤 | `kg_data_cleaner.py` `is_non_drug` | 关键词表，新剂型漏判 | S1 分类：药品/耗材/诊疗/检查 + 置信度，低置信度进人工队列 |
| 诊断归一化 | `kg_data_cleaner.py` `normalize_disease` | 同义词表维护成本高 | S1 将自由文本映射到 ICD-10 候选（固定输出空间正好是标准诊断集合） |
| 质控异常类型 | `quality_control_service.py` | 规则 + LLM 叙事 | S1 先做异常类型分类，S2 只对命中的异常生成说明 |

### P2 — 体验与成本优化

- **风险预警分级**（`risk_prediction_service.py`）：S1 输出低/中/高风险 + 置信度做初筛，仅高风险患者调 S2 生成详细叙事——把 LLM 调用量降一到两个数量级
- **晨会/周简报的数据选择**：S1 判断哪些指标变化「值得写」，S2 只为值得写的部分生成文字
- **智能体编排前置路由**：科研助手流水线中，S1 先判断「这个问题数据是否足以回答」，不足时直接提示，不启动流水线

## 5. 技术落地设计

### 5.1 调用层改造（最小侵入）

在 `llm_service.py` 旁新增 `services/decision_service.py`，与 LLMService 并列：

```python
decision_service.decide(
    task="lab_abnormal",            # 任务名（对应预定义的输出空间）
    context={...},                  # 结构化输入
    options=["正常", "偏高", "偏低", "危急"],  # 固定选项集合
) -> {"choice": "偏高", "confidence": 0.93}
```

- 底层可插拔：Jev API / 本地小模型（如 fastText/微调分类器）/ 规则兜底，按 `config.py` 配置切换
- 置信度低于阈值（如 0.7）时自动回退现有规则或转 LLM，保证不退化
- 所有 S1 决策记录日志（任务名、输入摘要、输出、置信度），便于审计与阈值调优

### 5.2 与缓存的关系

S1 决策结果同样走 `llm_cache`（决策也是可缓存的确定性映射）；规则层（System 0）保持最高优先级。三层的耗时/成本阶梯：μs → ms → s。

### 5.3 医疗安全边界

- S1 只做**辅助判断**，不做诊断结论；所有面向临床的展示保留人工确认入口
- 每个 S1 任务上线前用历史数据做校准评估（准确率/混淆矩阵），阈值写入配置
- 低置信度样本进入人工审核队列，审核结果回流作为校准数据

## 6. 预期收益

- **延迟**：决策型调用从秒级（思考模式可达分钟级、甚至超时）降到毫秒级，科研助手流水线与 RAG 问答体感明显加快
- **稳定性**：消除「max_tokens 过小」「Request timed out」这类思考模式故障的主要发生面
- **成本**：LLM 调用量预计下降 50% 以上（P0+P1 替换后）
- **数据质量**：归一化/异常判定从「规则覆盖到哪算哪」变为「模型判断 + 低置信度人工兜底」，覆盖率可度量

## 7. 实施路线图建议

| 阶段 | 内容 | 验证方式 |
|---|---|---|
| 第 1 步 | 建 `decision_service` 骨架 + 选 1 个点试点（建议文献重排，影响面小） | 与 LLM 重排结果对比一致率 |
| 第 2 步 | P0 全部替换 + 决策日志 | 流水线耗时对比、故障率 |
| 第 3 步 | P1 规则点改造（检验异常判定优先，有参考范围可自动校验准确率） | 历史数据回测准确率 |
| 第 4 步 | P2 体验优化 + 置信度阈值调优 | 端到端延迟/成本报表 |

## 参考资料

- [Introducing System One Models & Jev（TypeSafe AI 官方）](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [Jev vs. LLMs: When AI Moves from Generation to Decision-Making（Towards Data Science）](https://towardsdatascience.com/jev-vs-llms-when-ai-moves-from-generation-to-decision-making/)
- [What Is Jev? —— 对其宣传数据可信度的质疑（hackerspot）](https://www.hackerspot.net/p/what-is-jev-typesafe-ais-system-one)
- 卡尼曼《思考，快与慢》：System 1 / System 2 概念出处

---

## 附录：全场景 System 1 适配性盘点（2026-09-29 补充）

对 `services/` 全部 24 个服务 + 科研助手子包逐文件清点：**LLM 调用点共 40 处（生成类 27、决策类 13），另有约 28 处规则硬编码的隐性决策点**。

### A. 可直接用 System 1 替换（输出空间有限可枚举）—— 最高收益区

| 场景 | 位置 | 当前实现 | 决策任务 |
|---|---|---|---|
| RAG 问答意图分类 | `kg_rag_service._parse_intent()` :55 | 正则+4 组关键词 | 用户问题 → 6 类意图（患者/疾病/用药/合并症/再入院/全局） |
| RAG 疾病实体抽取与对齐 | `kg_rag_service._extract_disease()` :106 / `_resolve_disease_names()` :135 | 24 词库 + CONTAINS 模糊匹配 | 自由文本 → 图谱节点集合中的疾病实体 |
| RAG 时序判断 | `kg_rag_service._is_recent_query()` :177 | 8 个关键词 | 是否问"最近一次"（是/否） |
| 检验异常判定（3 处重复） | `data_analysis_service` :557 / `weekly_analysis_service` :266 / `kg_data_cleaner` :557 | 正则解析参考范围 + hint 字符串匹配 | （结果值, 参考范围, 单位）→ 正常/偏高/偏低/危急 |
| 检查报告阳性判定 | `data_analysis_service.analyze_exam()` :441 | "Ca/癌/转移/占位/恶性"关键词 | 报告文本 → 阳性/阴性 |
| 病种多标签分类（2 处重复） | `data_analysis_service` :251 / `weekly_analysis_service` :143 | 15 病种固定关键词表 | 主诉+现病史 → 13~15 个病种的多标签 |
| 中药/西药分类（2 处重复） | `department_operation_service._is_tcm_drug()` :20 / `tcm_narrative_service` :28 | 60+ 关键词表 | 药名 → 中药/西药/中成药 |
| 风险评分卡与分级 | `risk_prediction_service` :58/:206/:242 | 6 因子手工评分卡（2 份重复实现）→ 4 级 | 患者特征 → 极高/高/中/低（可直接训成分类器） |
| 晨会重点患者筛选 | `daily_briefing_service._get_focus_patients()` :185 | 规则阈值 + 处置动作映射 | 患者 → 高/中风险 + 处置建议枚举 |
| 质控规则命中分级 | `quality_control_service` 三规则库 + :594 | 14 条规则 + 加权计数 → 4 级 | 单患者 → 异常类型 × 严重度（有限枚举） |
| 诊断归一化 | `kg_data_cleaner.normalize_disease()` :259 | ~60 条同义词表 | 自由文本诊断 → 标准诊断集合（ICD-10/图谱节点） |
| 药品/非药品过滤 | `kg_data_cleaner.is_non_drug()` :207 | 70+ 关键词 | 医嘱项目 → 药品/非药品 + 置信度 |
| 科研-议题锦标赛排序 | `auto_research_service._rank_topics()` :115 | LLM 生成 id 数组 | 候选议题 → 排序（有限集合排列） |
| 科研-文献相关性重排 | `skills/writing.py _rerank()` :187 | LLM 生成编号数组 | 文献 → 相关度打分 |
| 科研-引用核验 | `research_assistant_service._verify_citations()` :524 | LLM 输出 unsupported JSON | （引用句, 文献）对 → 支持/不支持 |
| 科研-引用编号回填 | `research_assistant_service._backfill_citations()` :449 | LLM 文本改写 | 论断句 → 文献编号 1..N |
| 科研-议题 skills 选择 | `auto_research_service` :78/:324 | LLM 生成 JSON | 议题 → 从 24 算子中选 2-4 个 + 可行性高/中/低 |

### B. S1+S2 混合（S1 做选择/判定，S2 只生成必要文字）

| 场景 | 位置 | 拆分方式 |
|---|---|---|
| 分析路径推荐 | `research_assistant_service.recommend_path()` :106 | S1 选算子序列（替代现有的文本子串抠 id）→ S2 写推荐理由 |
| 议题推荐 | `auto_research_service._propose_topics_llm()` :78 | S1 选 skills + 可行性 → S2 写标题与理由 |
| 大纲/章节择优 | `research_assistant_service` :342/:421 | S1 A/B 二选一 → S2 仅在被选中版本上融合润色 |
| 检索式改写 | `skills/writing.py _expand()` :163 / `auto_research_service._pubmed_query()` :477 | S1 在检索式模板库中选择 → 必要时 S2 微调 |
| 退化输出检测 | `research_assistant_service._is_degenerate()` :555 | 已是正则规则，可升级 S1 文本质量分类 |

### C. 必须保留 System 2（生成类，27 处调用点）

所有面向人阅读的文本生成：患者故事线、再入院叙事、合并症/用药模式/诊疗路径/中医特色/科室运营叙事、报告 10 章节、周简报 8 模块、论文 7 章写作与修订、算子 AI 解读、论文评审意见、选题建议文本、文献要点总结。

### D. 已经是"System 1 风格"，无需改造

科研助手 18 个分析算子（sklearn 分类/聚类/回归/特征重要性、mlxtend 关联规则、IsolationForest 异常检测）、相似患者 Jaccard 打分、数字一致性校验（`skill_packs/quality.py`）、GB/T 7714 确定性格式化——这些是本系统里现成的非生成式模型范式，S1 落地时可参考其接口设计。

### E. 盘点中发现的两个现存缺陷（与本方案无关，建议另行修复）

1. `POST /api/narrative/generate`（`routers/narrative.py:39`）调用了不存在的方法 `generate_department_narrative`，该端点实际不可用
2. `llm_service.generate_narrative()` 无任何调用方，属死代码
