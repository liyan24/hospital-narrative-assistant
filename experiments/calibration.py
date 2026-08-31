"""断言抽取器人工校准样本导出。

从 claims.jsonl 中按 方法×场景 分层随机抽取 20% 的叙事，导出一个供人工标注的
CSV 工作表：每行一条机器抽取的断言，标注者判断该断言是否被原文叙事真实表达
（校准抽取器的 precision），并核对自动核查标签是否正确（supported/contradicted/
unverifiable 的人工复核，校准 verify 环节）。

用法（项目根目录，需在 extract/verify 阶段完成后运行）：
    .venv/Scripts/python.exe -m experiments.calibration [--ratio 0.2] [--seed 42]

输出：
    experiments/output/calibration_sheet.csv  —— 人工标注工作表（utf-8-sig，Excel 可直接打开）
    experiments/output/calibration_narratives/ —— 每条叙事的原文 txt，供标注时对照

标注说明（写在 CSV 表头注释行中）：
- human_extract_ok：该断言是否忠实于原文（1=是，0=否/原文没有此意/拆分错误）
- human_label：对照 ground truth 事实，人工判定 supported/contradicted/unverifiable
- 填完后可用于计算：抽取 precision = mean(human_extract_ok)；
  自动核查与人工标签的一致率（accuracy / Cohen's kappa）。
"""

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import experiments  # noqa: F401  确保 sys.path 就绪
from experiments import exp_config
from experiments.pipeline import read_jsonl

CAL_CSV = "calibration_sheet.csv"
CAL_DIR = "calibration_narratives"

HEADER_NOTE = (
    "# 标注说明：human_extract_ok: 该断言是否忠实于原文(1=是,0=否)；"
    "human_label: 人工核查标签(supported/contradicted/unverifiable)；"
    "narrative_file 列为叙事原文文件，请对照阅读后标注。"
)


def export_calibration(ratio: float = 0.2, seed: int = 42) -> Path:
    claims_rows = read_jsonl(exp_config.output_path(exp_config.FILE_CLAIMS))
    if not claims_rows:
        print("[错误] 未找到 claims.jsonl，请先运行 pipeline 的 extract 阶段。")
        sys.exit(4)
    verdicts = {(r["task_id"], r["method"]): r for r in
                read_jsonl(exp_config.output_path(exp_config.FILE_VERDICTS))}
    generations = {(r["task_id"], r["method"]): r for r in
                   read_jsonl(exp_config.output_path(exp_config.FILE_GENERATIONS))}

    # 按 场景×方法 分层抽样
    strata: dict[tuple, list] = defaultdict(list)
    for r in claims_rows:
        strata[(r["scenario"], r["method"])].append(r)
    rng = random.Random(seed)
    sampled = []
    for key, group in sorted(strata.items()):
        k = max(1, round(len(group) * ratio))
        sampled.extend(rng.sample(group, min(k, len(group))))

    # 导出叙事原文供对照
    nar_dir = exp_config.output_path(CAL_DIR)
    nar_dir.mkdir(parents=True, exist_ok=True)

    out_path = exp_config.output_path(CAL_CSV)
    n_rows = 0
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(HEADER_NOTE + "\n")
        writer = csv.DictWriter(f, fieldnames=[
            "sample_id", "task_id", "scenario", "method",
            "claim_id", "claim_text", "claim_type", "claim_value",
            "auto_label", "auto_matched_fact",
            "narrative_file",
            "human_extract_ok", "human_label", "human_note",
        ])
        writer.writeheader()
        for r in sampled:
            key = (r["task_id"], r["method"])
            nar_file = f"{r['task_id']}__{r['method']}.txt"
            gen = generations.get(key)
            if gen:
                (nar_dir / nar_file).write_text(gen.get("text", ""), encoding="utf-8")
            vmap = {}
            vrow = verdicts.get(key)
            if vrow:
                for i, v in enumerate(vrow.get("verdicts", [])):
                    vmap[i] = v
            for i, c in enumerate(r.get("claims", [])):
                v = vmap.get(i, {})
                matched = v.get("matched_fact")
                writer.writerow({
                    "sample_id": f"{r['task_id']}__{r['method']}",
                    "task_id": r["task_id"],
                    "scenario": r["scenario"],
                    "method": r["method"],
                    "claim_id": i,
                    "claim_text": c.get("claim", ""),
                    "claim_type": c.get("type", ""),
                    "claim_value": json.dumps(c.get("value"), ensure_ascii=False),
                    "auto_label": v.get("label", ""),
                    "auto_matched_fact": json.dumps(matched, ensure_ascii=False) if matched else "",
                    "narrative_file": nar_file,
                    "human_extract_ok": "",
                    "human_label": "",
                    "human_note": "",
                })
                n_rows += 1

    print(f"[calibration] 抽样 {len(sampled)} 条叙事（比例 {ratio}），共 {n_rows} 条断言")
    print(f"[calibration] 工作表: {out_path}")
    print(f"[calibration] 叙事原文目录: {nar_dir}")
    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="experiments.calibration",
        description="导出断言抽取器人工校准样本工作表",
    )
    parser.add_argument("--ratio", type=float, default=0.2, help="抽样比例，默认 0.2")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args(argv)
    export_calibration(ratio=args.ratio, seed=args.seed)


if __name__ == "__main__":
    main()
