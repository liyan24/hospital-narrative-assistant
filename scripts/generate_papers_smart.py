"""通过智能模式（自动流水线）批量生成论文并复制到 output/ 文件夹。

用法：python scripts/generate_papers_smart.py [篇数，默认3]
流程：propose_topics → 逐议题 start_pipeline → 轮询 job 完成 → 复制 docx 到 output/
"""
import io
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from services.research.auto_research_service import auto_research_service

OUTPUT_DIR = Path("./output")
DATA_OUTPUTS = Path("./data/outputs")
POLL_INTERVAL = 15
JOB_TIMEOUT = 90 * 60  # 单个流水线最长等待 90 分钟


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main(n: int = 3):
    log("正在推荐研究议题（含数据画像，首次较慢）……")
    topics = auto_research_service.propose_topics(refresh=True)
    log(f"获得 {len(topics)} 个候选议题")
    for i, t in enumerate(topics):
        log(f"  {i+1}. {t.get('title')}（可行性：{t.get('feasibility')}，"
            f"算子：{[s.get('id') for s in t.get('skills', [])]}）")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    done_files = []
    for i, topic in enumerate(topics[:n], 1):
        title = topic.get("title", "")
        log(f"===== [{i}/{n}] 启动流水线：{title} =====")
        job_id = auto_research_service.start_pipeline(topic)
        log(f"job_id = {job_id}")
        start = time.time()
        last_states = ""
        while True:
            job = auto_research_service.get_job(job_id)
            states = "|".join(f"{s['label']}:{s['state']}" for s in job.get("steps", []))
            if states != last_states:
                log(f"  进度：{states}")
                last_states = states
            # 批量模式：大纲检查点自动确认（采用 AI 生成的大纲）
            if job.get("state") == "awaiting_outline":
                log("  大纲检查点：批量模式自动确认")
                auto_research_service.confirm_outline(job_id, job.get("outline") or "")
                continue
            if job.get("state") in ("done", "failed"):
                break
            if time.time() - start > JOB_TIMEOUT:
                log("  超时，放弃该议题")
                break
            time.sleep(POLL_INTERVAL)

        if job.get("state") == "done" and job.get("filename"):
            src = DATA_OUTPUTS / job["filename"]
            dst = OUTPUT_DIR / job["filename"]
            if src.exists():
                shutil.copy2(src, dst)
                done_files.append(str(dst))
                log(f"  完成，已复制到 {dst}")
            else:
                log(f"  警告：找不到生成文件 {src}")
        else:
            log(f"  失败：{job.get('error')}")

    log(f"===== 全部结束，成功 {len(done_files)}/{n} 篇 =====")
    for f in done_files:
        log(f"  {f}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
