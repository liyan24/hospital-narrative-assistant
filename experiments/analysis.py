"""结果汇总分析：按方法输出指标均值表，并对 B1 vs B3 做 Wilcoxon 符号秩检验。

输入：experiments/output/ 下的 verdicts.jsonl / scores.jsonl / generations.jsonl
输出：results_summary.csv（各方法均值表）、wilcoxon_B1_vs_B3.csv（配对检验结果），
并在终端打印表格。

用法（项目根目录）：
    .venv/Scripts/python.exe -m experiments.analysis
"""

import csv
import math
from typing import Any, Dict, List, Optional, Tuple

import experiments  # noqa: F401  确保 sys.path 就绪
from experiments import exp_config
from experiments.pipeline import read_jsonl

# 汇总指标列
METRIC_KEYS = ["grounding_rate", "fact_accuracy", "hallucination_rate", "unsupported_rate"]
LATENCY_KEY = "latency_s"

try:
    from scipy.stats import wilcoxon as _scipy_wilcoxon
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ==================== Wilcoxon 符号秩检验 ====================

def _average_ranks(values: List[float]) -> List[float]:
    """平均秩（处理并列），values 应已按正数输入"""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _wilcoxon_fallback(x: List[float], y: List[float]) -> Tuple[Optional[float], Optional[float]]:
    """纯 Python 兜底：正态近似 Wilcoxon 符号秩检验（含并列校正的方差）。

    返回 (p 值, 效应量 r)。非零差值对数 < 5 时返回 (None, None)。
    """
    diffs = [(a - b) for a, b in zip(x, y)]
    nonzero = [d for d in diffs if d != 0]
    n = len(nonzero)
    if n < 5:
        return None, None
    abs_d = [abs(d) for d in nonzero]
    ranks = _average_ranks(abs_d)
    w_plus = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    w_minus = sum(r for r, d in zip(ranks, nonzero) if d < 0)
    w = min(w_plus, w_minus)

    mean_w = n * (n + 1) / 4.0
    # 并列校正：var = n(n+1)(2n+1)/24 - Σ(t^3-t)/48
    tie_counts: Dict[float, int] = {}
    for v in abs_d:
        tie_counts[v] = tie_counts.get(v, 0) + 1
    tie_term = sum(t ** 3 - t for t in tie_counts.values() if t > 1) / 48.0
    var_w = n * (n + 1) * (2 * n + 1) / 24.0 - tie_term
    if var_w <= 0:
        return None, None
    z = (w - mean_w) / math.sqrt(var_w)
    # 双侧 p（标准正态近似）
    p = math.erfc(abs(z) / math.sqrt(2))
    r = abs(z) / math.sqrt(len(diffs))
    return p, r


def wilcoxon_test(x: List[float], y: List[float]) -> Tuple[Optional[float], Optional[float]]:
    """Wilcoxon 符号秩检验：返回 (p, 效应量 r=|z|/√N)。优先 scipy，否则纯 Python 兜底。"""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 5:
        return None, None
    xs = [a for a, _ in pairs]
    ys = [b for _, b in pairs]
    if _HAS_SCIPY:
        try:
            if all(a == b for a, b in pairs):
                return 1.0, 0.0
            res = _scipy_wilcoxon(xs, ys)
            # 由 W 统计量换算 z，再算效应量 r
            nonzero = [a - b for a, b in pairs if a != b]
            n = len(nonzero)
            mean_w = n * (n + 1) / 4.0
            var_w = n * (n + 1) * (2 * n + 1) / 24.0
            z = (float(res.statistic) - mean_w) / math.sqrt(var_w) if var_w > 0 else 0.0
            r = abs(z) / math.sqrt(len(pairs))
            return float(res.pvalue), r
        except Exception:
            return _wilcoxon_fallback(xs, ys)
    return _wilcoxon_fallback(xs, ys)


# ==================== 汇总 ====================

def collect_rows() -> Dict[Tuple[str, str], Dict[str, Any]]:
    """汇总各阶段落盘结果为 {(task_id, method): {指标...}} 的行"""
    rows: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def _row(task_id: str, method: str, scenario: str) -> Dict[str, Any]:
        key = (task_id, method)
        if key not in rows:
            rows[key] = {"task_id": task_id, "method": method, "scenario": scenario}
        return rows[key]

    for r in read_jsonl(exp_config.output_path(exp_config.FILE_GENERATIONS)):
        row = _row(r["task_id"], r["method"], r["scenario"])
        row[LATENCY_KEY] = r.get("latency_s")

    for r in read_jsonl(exp_config.output_path(exp_config.FILE_VERDICTS)):
        row = _row(r["task_id"], r["method"], r["scenario"])
        for k in METRIC_KEYS:
            row[k] = (r.get("metrics") or {}).get(k)

    for r in read_jsonl(exp_config.output_path(exp_config.FILE_SCORES)):
        row = _row(r["task_id"], r["method"], r["scenario"])
        scores = r.get("scores") or {}
        for dim in exp_config.JUDGE_DIMENSIONS:
            entry = scores.get(dim) or {}
            row[dim] = entry.get("score")

    return rows


def summarize(rows: Dict[Tuple[str, str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按方法聚合均值"""
    metric_cols = METRIC_KEYS + exp_config.JUDGE_DIMENSIONS + [LATENCY_KEY]
    by_method: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows.values():
        by_method.setdefault(row["method"], []).append(row)

    summary = []
    for method in exp_config.METHODS:
        group = by_method.get(method, [])
        rec: Dict[str, Any] = {"method": method, "n_tasks": len({r['task_id'] for r in group})}
        for col in metric_cols:
            vals = [r[col] for r in group if isinstance(r.get(col), (int, float))]
            rec[col] = round(sum(vals) / len(vals), 4) if vals else None
        summary.append(rec)
    return summary


def compare_b1_b3(rows: Dict[Tuple[str, str], Dict[str, Any]]) -> List[Dict[str, Any]]:
    """B1 vs B3 按任务配对的 Wilcoxon 检验（覆盖全部指标）"""
    metric_cols = METRIC_KEYS + exp_config.JUDGE_DIMENSIONS + [LATENCY_KEY]
    # task_id -> {method: row}
    by_task: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for (task_id, method), row in rows.items():
        by_task.setdefault(task_id, {})[method] = row

    results = []
    for col in metric_cols:
        x, y = [], []
        for task_rows in by_task.values():
            b1, b3 = task_rows.get("B1_direct"), task_rows.get("B3_kg_grounded")
            if not b1 or not b3:
                continue
            v1, v3 = b1.get(col), b3.get(col)
            if isinstance(v1, (int, float)) and isinstance(v3, (int, float)):
                x.append(float(v1))
                y.append(float(v3))
        p, r = wilcoxon_test(x, y)
        results.append({
            "metric": col, "n_pairs": len(x),
            "B1_mean": round(sum(x) / len(x), 4) if x else None,
            "B3_mean": round(sum(y) / len(y), 4) if y else None,
            "wilcoxon_p": round(p, 6) if p is not None else None,
            "effect_size_r": round(r, 4) if r is not None else None,
        })
    return results


def _print_table(records: List[Dict[str, Any]], columns: List[str]):
    """简单终端表格打印"""
    headers = columns
    str_rows = [[("" if rec.get(c) is None else str(rec.get(c))) for c in columns]
                for rec in records]
    widths = [max(len(h), *(len(r[i]) for r in str_rows)) if str_rows else len(h)
              for i, h in enumerate(headers)]
    line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-+-".join("-" * widths[i] for i in range(len(headers))))
    for r in str_rows:
        print(" | ".join(r[i].ljust(widths[i]) for i in range(len(headers))))


def _write_csv(path, records: List[Dict[str, Any]], columns: List[str]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for rec in records:
            writer.writerow({c: rec.get(c) for c in columns})


def main():
    if not _HAS_SCIPY:
        print("[提示] 未安装 scipy，Wilcoxon 检验使用纯 Python 正态近似兜底实现。")

    rows = collect_rows()
    if not rows:
        print("[错误] 未找到任何实验结果，请先运行 experiments/pipeline.py。")
        raise SystemExit(4)

    summary = summarize(rows)
    summary_cols = ["method", "n_tasks"] + METRIC_KEYS + exp_config.JUDGE_DIMENSIONS + [LATENCY_KEY]
    print("\n===== 各方法指标均值 =====")
    _print_table(summary, summary_cols)
    csv_path = exp_config.output_path(exp_config.FILE_RESULTS_CSV)
    _write_csv(csv_path, summary, summary_cols)
    print(f"\n均值表已导出: {csv_path}")

    cmp_results = compare_b1_b3(rows)
    cmp_cols = ["metric", "n_pairs", "B1_mean", "B3_mean", "wilcoxon_p", "effect_size_r"]
    print("\n===== B1_direct vs B3_kg_grounded Wilcoxon 符号秩检验（按任务配对）=====")
    _print_table(cmp_results, cmp_cols)
    cmp_path = exp_config.output_path(exp_config.FILE_WILCOXON_CSV)
    _write_csv(cmp_path, cmp_results, cmp_cols)
    print(f"\n检验结果已导出: {cmp_path}")


if __name__ == "__main__":
    main()
