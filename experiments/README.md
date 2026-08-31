# 论文实验评测管线（experiments/）

针对核心论点"KG-grounded 叙事生成比直接把数据喂给 LLM 事实错误更少"的基线对比实验管线。

## 实验设计

- **5 类叙事场景**：patient_storyline（患者故事线）、treatment_pathway（诊疗路径）、comorbidity（合并症分析）、drug_pattern（用药模式）、morning_briefing（晨会简报），每类默认采样 20 个任务。
- **4 个生成方法**：
  - `B1_direct`：表格化数据摘要直接喂 LLM，无图谱约束；
  - `B2_vector_rag`：向量检索 + LLM（向量库不可用时降级为关键词检索，结果带 `degraded` 标记）；
  - `B3_kg_grounded`：**本文方法**——图谱事实清单约束生成，要求只用给定事实并逐条标注来源；
  - `B4_template`：规则模板填空（下界参照，不调 LLM）。
- **评测**：
  - 事实性：`claims.py` 用 LLM 从叙事中抽取原子断言 → `verify.py` 与图谱 ground truth 比对（实体归一化 / 数值容差 / 关系匹配），标签 ∈ {supported, contradicted, unverifiable}，任务级指标 fact_accuracy / hallucination_rate / unsupported_rate；
  - 质量：`judge.py` LLM-as-Judge 按连贯性、信息覆盖、可读性、临床有用性 4 维打 1-5 分（解析失败重试一次后记 None）；
  - 统计：`analysis.py` 按方法汇总均值，并对 B1 vs B3 做按任务配对的 Wilcoxon 符号秩检验（p 值 + 效应量 r）。

## 前置条件

1. Neo4j 已启动并完成建图（`scripts/build_knowledge_graph.py`），关系 Schema 见 `docs/知识图谱说明文档.md`；
2. 项目根目录 `.env` 已配置 `openai_api_key` / `openai_base_url` / `openai_model` 及 `neo4j_*`；
3. 使用项目虚拟环境 `.venv`（Windows 下解释器为 `.venv/Scripts/python.exe`），测试需 `pytest`，统计需 `scipy`（缺失时 analysis.py 自动用纯 Python 正态近似兜底）。

## 运行顺序

在项目根目录执行：

```bash
# 一键全流程（小样本试跑，建议先 --limit 验证）
.venv/Scripts/python.exe -m experiments.pipeline all --limit 5

# 完整运行（每场景 20 任务 × 4 方法）
.venv/Scripts/python.exe -m experiments.pipeline all

# 分阶段运行（断点续跑：已完成的 task_id+method 组合自动跳过）
.venv/Scripts/python.exe -m experiments.pipeline sample --per-scenario 20 --seed 42
.venv/Scripts/python.exe -m experiments.pipeline generate
.venv/Scripts/python.exe -m experiments.pipeline extract
.venv/Scripts/python.exe -m experiments.pipeline verify
.venv/Scripts/python.exe -m experiments.pipeline judge

# 只跑部分场景/方法
.venv/Scripts/python.exe -m experiments.pipeline generate --scenarios comorbidity --methods B1_direct,B3_kg_grounded

# 结果汇总（均值表 + Wilcoxon 检验）
.venv/Scripts/python.exe -m experiments.analysis
```

## 输出文件（experiments/output/）

| 文件 | 内容 |
| --- | --- |
| `tasks.jsonl` | 采样的任务（prompt + ground truth 事实 + 数据快照） |
| `generations.jsonl` | 各方法生成文本、耗时、错误信息 |
| `claims.jsonl` | LLM 抽取的原子断言（含 parse_error 标记） |
| `verdicts.jsonl` | 每条断言的核查标签与任务级指标 |
| `scores.jsonl` | LLM-as-Judge 四维评分 |
| `results_summary.csv` | 各方法指标均值表 |
| `wilcoxon_B1_vs_B3.csv` | B1 vs B3 配对 Wilcoxon 检验结果 |

## 断点续跑说明

- `sample` 阶段会**整体重写** `tasks.jsonl`（重采样后应删除旧的中间结果再跑后续阶段）；
- `generate` / `extract` / `verify` / `judge` 均以追加方式写入，启动时读取已有文件中的 `task_id+method` 组合并跳过，可安全中断后重跑；
- LLM 调用均带缓存（命名空间 `exp:{method}:{scenario}`），重复请求不会重复消耗额度；
- Neo4j / LLM 不可用时会打印清晰错误并以非零退出码退出（Neo4j=2，LLM 配置缺失=3，缺任务文件=4）。

## 单元测试

只测纯逻辑（JSON 解析、断言匹配与指标、judge 解析与重试），不连 Neo4j/LLM：

```bash
.venv/Scripts/python.exe -m pytest experiments/tests/ -v
```
