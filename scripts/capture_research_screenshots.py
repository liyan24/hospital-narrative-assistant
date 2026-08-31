# -*- coding: utf-8 -*-
"""科研助手说明文档用页面截图脚本（一次性工具）。
前置：后端 8005、前端 8501 运行中；auth_tmp.json 存有登录返回（含 access_token 与 user）。
用法：.venv/Scripts/python.exe -X utf8 scripts/capture_research_screenshots.py
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images" / "research"
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:8501"
auth = json.load(open(ROOT / "auth_tmp.json", encoding="utf-8"))
TOKEN = auth["access_token"]
USER = json.dumps(auth["user"], ensure_ascii=False)

INIT_JS = f"""
localStorage.setItem('token', {json.dumps(TOKEN)});
localStorage.setItem('user', {json.dumps(USER)});
"""


def shot(page, name, full=False):
    page.screenshot(path=str(OUT / name), full_page=full)
    print(f"[shot] {name}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1680, "height": 1000},
                                  device_scale_factor=1.5)
        ctx.add_init_script(INIT_JS)
        page = ctx.new_page()

        # ---------- 智能模式：议题推荐页（含历史记录、自定义议题卡）----------
        page.goto(f"{BASE}/portal/research-assistant", wait_until="networkidle")
        page.wait_for_timeout(2500)
        # 触发议题推荐（LLM 调用，等待议题卡片出现）
        btn = page.get_by_role("button", name="分析数据并推荐研究议题")
        if btn.count() > 0:
            btn.first.click()
            page.wait_for_selector("text=开始自动研究", timeout=180000)
            page.wait_for_timeout(1500)
        shot(page, "01_智能模式_议题推荐.png", full=True)

        # ---------- 智能模式：自定义议题评估 ----------
        textarea = page.locator("textarea[placeholder*='化疗后骨髓抑制']")
        if textarea.count() > 0:
            textarea.first.fill("我想研究化疗后骨髓抑制的发生规律和影响因素")
            page.get_by_role("button", name="评估我的议题").first.click()
            page.wait_for_selector("text=数据支", timeout=180000)
            page.wait_for_timeout(1000)
            shot(page, "02_智能模式_自定义议题评估.png")

        # ---------- 智能模式：流水线运行 ----------
        page.evaluate("window.scrollTo(0, 0)")
        page.get_by_role("button", name="开始自动研究").first.click()
        page.wait_for_selector("text=数据画像", timeout=60000)
        # 等待至少 2 步完成，呈现"进行中"的中间态
        for _ in range(90):
            done_cnt = page.locator(".ant-steps-item-finish").count()
            if done_cnt >= 2:
                break
            page.wait_for_timeout(3000)
        page.wait_for_timeout(1500)
        shot(page, "03_智能模式_流水线运行.png", full=True)

        # 等待流水线完成（论文展示阶段）
        try:
            page.wait_for_selector("text=下载 Word 文档", timeout=480000)
            page.wait_for_timeout(2000)
            shot(page, "04_智能模式_论文展示.png", full=True)
        except Exception:
            print("[warn] 流水线超时未完成，改从历史记录截取论文展示")
            page.goto(f"{BASE}/portal/research-assistant", wait_until="networkidle")
            page.wait_for_timeout(2500)
            view = page.get_by_role("button", name="查看")
            if view.count() > 0:
                view.first.click()
                page.wait_for_selector("text=下载 Word 文档", timeout=60000)
                page.wait_for_timeout(1500)
                shot(page, "04_智能模式_论文展示.png", full=True)

        # ---------- 专家模式：数据资产 ----------
        page.goto(f"{BASE}/portal/research-assistant", wait_until="networkidle")
        page.wait_for_timeout(2500)
        page.get_by_role("tab", name="专家模式").click()
        page.wait_for_timeout(3000)
        shot(page, "05_专家模式_数据资产.png", full=True)

        # ---------- 专家模式：Skills 工作台（运行关联规则）----------
        next_btn = page.get_by_role("button", name="下一步")
        next_btn.first.click()
        page.wait_for_timeout(2000)
        menu_item = page.locator(".ant-menu-item", has_text="关联规则挖掘")
        if menu_item.count() > 0:
            menu_item.first.click()
            page.wait_for_timeout(1000)
            run_btn = page.get_by_role("button", name="运行")
            run_btn.first.click()
            page.wait_for_selector("text=AI 解读", timeout=300000)
            page.wait_for_timeout(1500)
        shot(page, "06_专家模式_Skills工作台.png", full=True)

        browser.close()
    print("全部截图完成 ->", OUT)


if __name__ == "__main__":
    main()
