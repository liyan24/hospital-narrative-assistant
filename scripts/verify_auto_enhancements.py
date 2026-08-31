# -*- coding: utf-8 -*-
"""三项后端增强的验证脚本：真实 LLM 调用，不启动 uvicorn。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.json_store import json_store
from services.research.auto_research_service import auto_research_service
from services.research.skills.registry import get_skill

print("=" * 70)
print("验证①：propose_topics 基线（写缓存）→ 再走缓存 → refresh 出新议题")
print("=" * 70)

baseline = auto_research_service.propose_topics()
baseline_titles = [t["title"] for t in baseline]
print("\n[基线议题]")
for t in baseline_titles:
    print(" -", t)

# 第二次相同调用应命中缓存（证明第一次走了缓存写入）
cached = auto_research_service.propose_topics()
cached_titles = [t["title"] for t in cached]
assert cached_titles == baseline_titles, "第二次非 refresh 调用未命中缓存！"
print("\n[缓存确认] 第二次非 refresh 调用标题与基线完全一致 → 第一次已写入缓存 ✓")

refreshed = auto_research_service.propose_topics(refresh=True, exclude_titles=baseline_titles)
refreshed_titles = [t["title"] for t in refreshed]
print("\n[refresh 新议题]")
for t in refreshed_titles:
    print(" -", t)

intersection = set(baseline_titles) & set(refreshed_titles)
assert not intersection, f"refresh 后标题与基线有交集: {intersection}"
print("\n[断言通过] 两批标题交集为空 ✓")

print("\n" + "=" * 70)
print("验证②：list_history 列出 json_store 中的 autojob 记录")
print("=" * 70)

all_docs = json_store.list_all()
autojob_docs = [d for d in all_docs if d.startswith("autojob_")]
print(f"\njson_store 中 autojob_* 记录数: {len(autojob_docs)} -> {autojob_docs}")
assert len(autojob_docs) >= 1, "json_store 中没有 autojob 记录！"

history = auto_research_service.list_history()
print(f"\nlist_history() 返回 {len(history)} 条：")
required_fields = {"job_id", "state", "topic_title", "paper_title",
                   "filename", "download_url", "created_at", "finished_at"}
for j in history:
    missing = required_fields - set(j.keys())
    assert not missing, f"{j.get('job_id')} 缺字段: {missing}"
    print(json.dumps(j, ensure_ascii=False))
# 倒序校验
created = [j["created_at"] or "" for j in history]
assert created == sorted(created, reverse=True), "未按 created_at 倒序！"
print("\n[断言通过] 至少 1 条记录、字段齐全、created_at 倒序 ✓")

print("\n" + "=" * 70)
print("验证③：evaluate_custom_topic")
print("=" * 70)

idea1 = "我想研究化疗后骨髓抑制的发生规律"
print(f"\n[idea 1] {idea1}")
res1 = auto_research_service.evaluate_custom_topic(idea1)
print(json.dumps(res1, ensure_ascii=False, indent=2))
assert res1["topic"]["id"] == "custom"
assert res1["topic"]["skills"], "合法议题 skills 不应为空"
for s in res1["topic"]["skills"]:
    assert get_skill(s["id"]) is not None, f"skill id 不在 registry: {s['id']}"
print("[断言通过] skills 的 id 全部在 registry ✓ supported =", res1["supported"])

idea2 = "基因突变与预后"
print(f"\n[idea 2] {idea2}")
res2 = auto_research_service.evaluate_custom_topic(idea2)
print(json.dumps(res2, ensure_ascii=False, indent=2))
assert res2["topic"]["feasibility"] == "低", f"feasibility 应为低，实际 {res2['topic']['feasibility']}"
assert res2["supported"] is False, "supported 应为 False"
for s in res2["topic"]["skills"]:
    assert get_skill(s["id"]) is not None, f"skill id 不在 registry: {s['id']}"
print("[断言通过] feasibility=低 且 supported=False ✓")

print("\n全部验证通过 ✓")
