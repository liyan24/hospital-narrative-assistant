"""实验管线 CLI 编排：sample → generate → extract → verify → judge → all。

用法（项目根目录）：
    .venv/Scripts/python.exe -m experiments.pipeline all --limit 5
    .venv/Scripts/python.exe -m experiments.pipeline sample --per-scenario 20 --seed 42

中间结果落盘 JSONL 到 experiments/output/，支持断点续跑：
已存在的 task_id（+method）组合自动跳过。
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import experiments  # noqa: F401  确保 sys.path 就绪
from experiments import exp_config
from experiments.tasks import Task, sample_tasks

try:  # Windows GBK 控制台中文乱码兜底
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ==================== JSONL 读写 ====================

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]):
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _print(msg: str):
    print(msg, flush=True)


# ==================== 服务可用性检查 ====================

def _check_neo4j():
    """Neo4j 不可用时清晰报错并以非零码退出"""
    try:
        from database.neo4j_client import neo4j_client
        if not neo4j_client.test_connection():
            raise RuntimeError("test_connection 返回 False")
    except Exception as e:
        _print(f"[错误] Neo4j 不可用：{e}\n"
               "请确认 Neo4j 已启动且 .env 中 neo4j_uri/neo4j_user/neo4j_password 配置正确。")
        sys.exit(2)


def _check_llm():
    """LLM 配置缺失时清晰报错并以非零码退出（不实际调用，避免消耗额度）"""
    from config import settings
    if not settings.openai_api_key:
        _print("[错误] 未配置 LLM：.env 中 openai_api_key 为空，"
               "无法执行 generate/extract/judge 阶段。")
        sys.exit(3)


# ==================== 各阶段 ====================

def stage_sample(args) -> List[Dict[str, Any]]:
    """采样任务并写入 tasks.jsonl（重跑会覆盖重来）"""
    _check_neo4j()
    scenarios = args.scenarios.split(",") if args.scenarios else None
    tasks = sample_tasks(
        scenarios=scenarios,
        per_scenario=args.per_scenario,
        seed=args.seed,
        limit=args.limit,
    )
    path = exp_config.output_path(exp_config.FILE_TASKS)
    # sample 是后续阶段的输入源，重跑时整体重写
    with open(path, "w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")
    _print(f"[sample] 采样 {len(tasks)} 个任务 -> {path}")
    return [t.to_dict() for t in tasks]


def _load_tasks() -> List[Task]:
    path = exp_config.output_path(exp_config.FILE_TASKS)
    rows = read_jsonl(path)
    if not rows:
        _print(f"[错误] 未找到任务文件 {path}，请先运行 sample 阶段。")
        sys.exit(4)
    return [Task.from_dict(r) for r in rows]


def _allowed_task_ids(args) -> Optional[set]:
    """limit 的统一语义：tasks.jsonl 中前 N 个任务的 task_id 集合；None 表示不限制。

    generate/extract/judge 三个阶段共用这一语义，避免把 limit 误当成结果行数。
    """
    if not args.limit:
        return None
    rows = read_jsonl(exp_config.output_path(exp_config.FILE_TASKS))
    return {r["task_id"] for r in rows[: args.limit]}


def stage_generate(args):
    """遍历 任务×方法 生成叙事，断点续跑（跳过已有的 task_id+method）"""
    _check_llm()
    from experiments.baselines import build_methods

    tasks = _load_tasks()
    if args.limit:
        tasks = tasks[: args.limit]
    methods = build_methods(args.methods.split(",") if args.methods else None)

    path = exp_config.output_path(exp_config.FILE_GENERATIONS)
    done = {(r["task_id"], r["method"]) for r in read_jsonl(path)}

    total, skipped, failed = 0, 0, 0
    for task in tasks:
        for m in methods:
            total += 1
            if (task.task_id, m.name) in done:
                skipped += 1
                continue
            result = m.generate(task)
            append_jsonl(path, [result])
            if result.get("error"):
                failed += 1
                _print(f"[generate] {task.task_id} × {m.name} 失败: {result['error']}")
            else:
                _print(f"[generate] {task.task_id} × {m.name} 完成 "
                       f"({result['latency_s']}s, {len(result['text'])}字)")
    _print(f"[generate] 共 {total} 组合，跳过 {skipped}，失败 {failed}")


def stage_extract(args):
    """对 generations.jsonl 中的叙事抽取断言，断点续跑"""
    _check_llm()
    from experiments.claims import extract_claims

    generations = read_jsonl(exp_config.output_path(exp_config.FILE_GENERATIONS))
    allowed = _allowed_task_ids(args)
    if allowed is not None:
        generations = [g for g in generations if g["task_id"] in allowed]
    path = exp_config.output_path(exp_config.FILE_CLAIMS)
    done = {(r["task_id"], r["method"]) for r in read_jsonl(path)}

    n_new, n_parse_err = 0, 0
    for g in generations:
        key = (g["task_id"], g["method"])
        if key in done:
            continue
        ns = exp_config.cache_namespace("claims", g["scenario"])
        out = extract_claims(g.get("text", ""), cache_namespace=ns)
        append_jsonl(path, [{"task_id": g["task_id"], "scenario": g["scenario"],
                             "method": g["method"], **out}])
        n_new += 1
        if out.get("parse_error"):
            n_parse_err += 1
    _print(f"[extract] 新增 {n_new} 条，其中解析失败 {n_parse_err} 条")


def stage_verify(args):
    """断言核查（纯本地计算，不依赖 LLM），断点续跑"""
    from experiments.verify import compute_metrics, verify_claims

    tasks = {t.task_id: t for t in _load_tasks()}
    # verify 是纯本地计算，不消耗 LLM，处理全部 claims 行（不做 limit 过滤）
    claims_rows = read_jsonl(exp_config.output_path(exp_config.FILE_CLAIMS))
    path = exp_config.output_path(exp_config.FILE_VERDICTS)
    done = {(r["task_id"], r["method"]) for r in read_jsonl(path)}

    n_new = 0
    for row in claims_rows:
        key = (row["task_id"], row["method"])
        if key in done:
            continue
        task = tasks.get(row["task_id"])
        if task is None:
            _print(f"[verify] 警告：找不到任务 {row['task_id']}，跳过")
            continue
        verdicts = verify_claims(row.get("claims", []), task.ground_truth_facts)
        metrics = compute_metrics(verdicts)
        append_jsonl(path, [{"task_id": row["task_id"], "scenario": row["scenario"],
                             "method": row["method"], "metrics": metrics,
                             "verdicts": verdicts}])
        n_new += 1
    _print(f"[verify] 新增 {n_new} 条")


def stage_judge(args):
    """LLM-as-Judge 打分，断点续跑"""
    _check_llm()
    from experiments.judge import score_narrative

    tasks = {t.task_id: t for t in _load_tasks()}
    generations = read_jsonl(exp_config.output_path(exp_config.FILE_GENERATIONS))
    allowed = _allowed_task_ids(args)
    if allowed is not None:
        generations = [g for g in generations if g["task_id"] in allowed]
    path = exp_config.output_path(exp_config.FILE_SCORES)
    done = {(r["task_id"], r["method"]) for r in read_jsonl(path)}

    n_new, n_none = 0, 0
    for g in generations:
        key = (g["task_id"], g["method"])
        if key in done:
            continue
        task = tasks.get(g["task_id"])
        task_prompt = task.prompt if task else ""
        ns = exp_config.cache_namespace("judge", g["scenario"])
        scores = score_narrative(g.get("text", ""), task_prompt, cache_namespace=ns)
        append_jsonl(path, [{"task_id": g["task_id"], "scenario": g["scenario"],
                             "method": g["method"], "scores": scores}])
        n_new += 1
        if scores is None:
            n_none += 1
    _print(f"[judge] 新增 {n_new} 条，其中打分失败（None）{n_none} 条")


# ==================== CLI ====================

def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(
        prog="experiments.pipeline",
        description="论文实验评测管线：sample → generate → extract → verify → judge",
    )
    parser.add_argument("stage",
                        choices=["sample", "generate", "extract", "verify", "judge", "all"],
                        help="执行哪个阶段；all = 依次执行全部阶段")
    parser.add_argument("--per-scenario", type=int,
                        default=exp_config.DEFAULT_SAMPLES_PER_SCENARIO,
                        help="每类场景采样数（默认 20）")
    parser.add_argument("--seed", type=int, default=exp_config.DEFAULT_SEED,
                        help="随机种子（默认 42）")
    parser.add_argument("--limit", type=int, default=None,
                        help="小样本试跑：限制处理的任务/记录数")
    parser.add_argument("--scenarios", type=str, default=None,
                        help="只跑指定场景，逗号分隔，如 patient_storyline,comorbidity")
    parser.add_argument("--methods", type=str, default=None,
                        help="只跑指定方法，逗号分隔，如 B1_direct,B3_kg_grounded")
    args = parser.parse_args(argv)

    stages = {
        "sample": stage_sample,
        "generate": stage_generate,
        "extract": stage_extract,
        "verify": stage_verify,
        "judge": stage_judge,
    }

    if args.stage == "all":
        for name in ["sample", "generate", "extract", "verify", "judge"]:
            _print(f"===== 阶段: {name} =====")
            stages[name](args)
        _print("===== 全部阶段完成，可运行 experiments/analysis.py 汇总结果 =====")
    else:
        stages[args.stage](args)


if __name__ == "__main__":
    main()
