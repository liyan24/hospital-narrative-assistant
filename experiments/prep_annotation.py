"""准备 LLM 辅助标注与模拟盲评的数据包（一次性脚本）。

产出：
- output/annotation_work/chunk_{1..5}.json  —— 5 个标注分片（8 条共享样本 + 各自独立样本）
- output/blind_review/packet_{1..3}.json   —— 3 份盲评审阅包（每份内方法标签随机置换）
- output/blind_review/key.json             —— 标签→方法 映射密钥（评审者不可见）
"""
import csv, json, random
from collections import defaultdict
from pathlib import Path

OUT = Path("experiments/output")
SEED = 42

# ---------- 读取校准工作表（跳过 # 注释行） ----------
lines = [l for l in open(OUT / "calibration_sheet.csv", encoding="utf-8-sig") if not l.startswith("#")]
sheet = list(csv.DictReader(lines))

tasks = {json.loads(l)["task_id"]: json.loads(l) for l in open(OUT / "tasks.jsonl", encoding="utf-8")}
gens = {(json.loads(l)["task_id"], json.loads(l)["method"]): json.loads(l)
        for l in open(OUT / "generations.jsonl", encoding="utf-8")}

# ---------- 按 sample 分组 ----------
samples = defaultdict(list)
for r in sheet:
    samples[r["sample_id"]].append(r)

sample_items = []
for sid, rows in sorted(samples.items()):
    task_id = rows[0]["task_id"]
    nar_file = rows[0]["narrative_file"]
    nar_path = OUT / "calibration_narratives" / nar_file
    narrative = nar_path.read_text(encoding="utf-8") if nar_path.exists() else ""
    facts = tasks.get(task_id, {}).get("ground_truth_facts", [])
    claims = [{"row_id": f"{sid}#{r['claim_id']}", "claim_text": r["claim_text"],
               "claim_type": r["claim_type"], "claim_value": r["claim_value"]} for r in rows]
    sample_items.append({
        "sample_id": sid, "task_id": task_id, "scenario": rows[0]["scenario"],
        "method": rows[0]["method"], "narrative": narrative,
        "facts": facts, "claims": claims,
    })

rng = random.Random(SEED)
rng.shuffle(sample_items)
shared = sample_items[:8]
rest = sample_items[8:]
# 72 = 15+15+14+14+14
sizes = [15, 15, 14, 14, 14]
work = Path("experiments/output/annotation_work")
work.mkdir(parents=True, exist_ok=True)
idx = 0
for i, sz in enumerate(sizes, 1):
    chunk = shared + rest[idx: idx + sz]
    idx += sz
    n_claims = sum(len(s["claims"]) for s in chunk)
    (work / f"chunk_{i}.json").write_text(json.dumps(
        {"items": chunk}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"chunk_{i}.json: {len(chunk)} samples, {n_claims} claims (含 8 条共享样本)")

# ---------- 盲评审阅包 ----------
METHODS = ["B1_direct", "B2_vector_rag", "B3_kg_grounded", "B4_template"]
LABELS = ["文本甲", "文本乙", "文本丙", "文本丁"]
by_scenario = defaultdict(list)
for t in tasks.values():
    by_scenario[t["scenario"]].append(t)
rng2 = random.Random(SEED)
picked = []
for sc, ts in sorted(by_scenario.items()):
    ts = sorted(ts, key=lambda t: t["task_id"])
    picked.extend(rng2.sample(ts, 2))

br = Path("experiments/output/blind_review")
br.mkdir(parents=True, exist_ok=True)
key = {}
for p in (1, 2, 3):
    rngp = random.Random(SEED + p)
    entries = []
    for t in picked:
        perm = METHODS[:]
        rngp.shuffle(perm)
        texts = []
        for label, m in zip(LABELS, perm):
            g = gens.get((t["task_id"], m))
            texts.append({"label": label, "text": g["text"] if g else ""})
            key.setdefault(str(p), {}).setdefault(t["task_id"], {})[label] = m
        entries.append({
            "task_id": t["task_id"], "scenario": t["scenario"],
            "prompt": t["prompt"], "facts": t["ground_truth_facts"],
            "texts": texts,
        })
    (br / f"packet_{p}.json").write_text(json.dumps(
        {"items": entries}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"packet_{p}.json: {len(entries)} tasks × 4 texts")
(br / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
print("key.json written (评审者不可读)")
