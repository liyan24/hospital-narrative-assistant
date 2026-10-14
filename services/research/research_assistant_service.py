"""
科研助手编排服务：算子执行 + LLM 解读 + 分析路径推荐 + IMRaD 论文生成（docx）。
"""
import io
import re
import uuid
from datetime import datetime
from pathlib import Path

from database.json_store import json_store
from services.llm_service import llm_service
from services.research.dataset_service import dataset_service
from services.research.skill_packs import figure_style, guidance, quality, references as ref_pack
from services.research.skills.base import convert
from services.research.skills.registry import get_skill, list_skills_by_category

OUTPUT_DIR = Path("./data/outputs")

SYSTEM_PROMPT = (
    "你是一位资深的临床科研方法学顾问与医学论文写作专家，"
    "熟悉肿瘤与血液病领域、真实世界研究方法和中文医学论文规范（GB/T 7714）。"
    "回答使用中文，严谨专业；只能基于提供的事实数据展开，不得编造数字。"
)


class ResearchAssistantService:
    """科研助手编排服务"""

    def __init__(self):
        self.llm = llm_service

    # ========== 算子执行 + LLM 解读 ==========

    def run_skill(self, skill_id: str, params: dict) -> dict:
        """执行算子，附加 LLM 中文解读，结果存 json_store"""
        skill = get_skill(skill_id)
        if skill is None:
            raise ValueError(f"未知算子: {skill_id}")

        result = skill.run(params or {})

        interpretation = self._interpret(skill.meta, params, result)

        result_id = f"research_result_{uuid.uuid4().hex[:8]}"
        record = {
            "result_id": result_id,
            "skill_id": skill_id,
            "skill_name": skill.meta.name,
            "category": skill.meta.category,
            "params": params or {},
            "result": result,
            "interpretation": interpretation,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        json_store.save(result_id, convert(record))
        return convert(record)

    def _interpret(self, meta, params: dict, result: dict) -> str:
        """LLM 对算子结果生成中文解读（失败返回错误字符串，不中断流程）"""
        # 摘要 + 关键事实 + 首个表格前几行，控制 prompt 规模
        brief_tables = []
        for t in result.get("tables", [])[:2]:
            brief_tables.append({
                "title": t.get("title"),
                "columns": t.get("columns"),
                "rows": t.get("rows", [])[:8],
            })
        import json
        context = json.dumps({
            "summary": result.get("summary", ""),
            "facts": result.get("facts", {}),
            "tables_preview": brief_tables,
        }, ensure_ascii=False, default=str)[:5000]

        return self.llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              f"以下是科研算子「{meta.name}」（{meta.category}）的执行结果，参数：{params}。\n\n"
              f"{context}\n\n"
              "请用中文给出 200-400 字的专业解读：1) 核心发现；2) 临床/科研意义；"
              "3) 结果解读时的注意事项（混杂、偏倚、多重比较等）；4) 建议的下一步分析。"}],
            temperature=0.4,
            max_tokens=1500,
            cache_namespace="research:interpret",
        )

    def get_result(self, result_id: str) -> dict | None:
        return json_store.load(result_id)

    # ========== 分析路径推荐 ==========

    def recommend_path(self, question: str) -> dict:
        """LLM 根据数据资产 + 算子目录推荐分析路径"""
        assets = dataset_service.detect_data_assets()
        assets_brief = [{
            "name": t["name"], "rows": t["rows"], "coverage_note": t["coverage_note"]
        } for t in assets["tables"]]

        catalog = []
        for category, skills in list_skills_by_category().items():
            for s in skills:
                catalog.append({"id": s["id"], "name": s["name"], "category": category,
                                "description": s["description"]})

        import json
        content = self.llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              f"研究问题：{question}\n\n"
              f"数据资产：{json.dumps(assets_brief, ensure_ascii=False)}\n"
              f"图谱可用：{assets['graph'].get('available', False)}\n\n"
              f"可用分析算子：\n{json.dumps(catalog, ensure_ascii=False, indent=1)}\n\n"
              "请推荐一条可落地的分析路径：1) 总体思路一段话；"
              "2) 按顺序列出建议执行的算子（使用算子 id），并说明每一步的目的。"
              "只推荐与数据条件匹配的算子（图谱不可用时不要推荐图谱算子）。"}],
            temperature=0.4,
            max_tokens=2000,
            cache_namespace="research:recommend",
        )

        # 从回复中识别提到的算子 id
        suggested = [sid for sid in
                     [s["id"] for skills in list_skills_by_category().values() for s in skills]
                     if sid in content]
        return {
            "recommendation": content,
            "suggested_skills": suggested,
        }

    # ========== 论文生成（多阶段流水线：大纲→分章写作→引用回填→质检→评审修订→导出） ==========

    PAPER_SECTIONS = ["摘要", "前言", "文献综述", "资料与方法", "结果", "讨论", "结论"]

    # 参考文献规模上限（上下文摘要与 GB/T 7714 格式化共用）
    MAX_REFERENCES = 18

    def _prepare_context(self, question: str, result_ids: list[str],
                         articles: list[dict], title: str | None = None) -> dict:
        """汇总选定结果与文献，构建写作上下文（供论文生成与大纲预览共用）"""
        import json

        # 汇总选定分析结果
        selected = []
        all_charts = []
        all_tables = []
        for rid in result_ids:
            record = json_store.load(rid)
            if not record:
                continue
            selected.append({
                "skill": record.get("skill_name"),
                "summary": record.get("result", {}).get("summary", ""),
                "facts": record.get("result", {}).get("facts", {}),
            })
            for ch in record.get("result", {}).get("charts", [])[:3]:
                all_charts.append({"title": ch.get("title", ""), "option": ch.get("option", {})})
            for tb in record.get("result", {}).get("tables", [])[:3]:
                if tb.get("columns") and tb.get("rows"):
                    all_tables.append({
                        "title": tb.get("title", ""),
                        "columns": tb.get("columns"),
                        "rows": tb.get("rows"),
                    })

        if not selected:
            raise ValueError("未找到任何有效的分析结果，请先运行算子并选择至少一个结果")

        facts_brief = json.dumps(selected, ensure_ascii=False, default=str)[:8000]
        articles_brief = ""
        if articles:
            articles_brief = "\n".join(
                f"[{i+1}] {a.get('title', '')}（{a.get('journal', '')}, {a.get('year', '')}）"
                f"：{(a.get('abstract') or '')[:300]}"
                for i, a in enumerate(articles[:self.MAX_REFERENCES])
            )

        # 生成题目
        if not title:
            title = self.llm.chat(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content":
                  f"研究问题：{question}\n分析结果：\n{facts_brief[:2000]}\n\n"
                  "请为该研究拟定一个规范的中文医学论文题目（一句话，只输出题目本身）。"}],
                temperature=0.4, max_tokens=800,
                cache_namespace="research:paper_title",
            ).strip().strip("《》\"'")

        context = (
            f"论文题目：{title}\n研究问题：{question}\n\n"
            f"分析结果事实（引用数据必须来自此处，不得编造）：\n{facts_brief}\n\n"
            + (f"参考文献：\n{articles_brief}\n\n" if articles_brief else "")
            + "研究背景：某县级医院肿瘤血液科真实世界回顾性数据"
            "（约1.37万就诊、3990名患者，含诊断/医嘱/检验/检查，无性别字段）。"
        )
        return {
            "selected": selected, "all_charts": all_charts, "all_tables": all_tables,
            "facts_brief": facts_brief, "context": context, "title": title,
        }

    def propose_outline(self, question: str, result_ids: list[str],
                        title: str | None = None) -> dict:
        """为给定素材生成大纲候选（供人在环确认/编辑，智能模式流水线暂停点使用）"""
        prepared = self._prepare_context(question, result_ids, [], title)
        return {"title": prepared["title"],
                "outline": self._gen_outline(prepared["context"])}

    def generate_paper(self, question: str, result_ids: list[str],
                       articles: list[dict], title: str | None = None,
                       outline: str | None = None) -> dict:
        """汇总选定结果与文献，多阶段生成 IMRaD 论文并导出 docx

        各阶段（大纲/回填/质检/评审）失败均降级为现有行为，不中断主流程。
        outline 不为 None 时跳过 Stage 0（用于人在环确认后直接采用用户大纲）。
        返回 dict 在原有 paper/filename/download_url 基础上增加
        quality_report 与 review 字段。
        """
        import json

        prepared = self._prepare_context(question, result_ids, articles, title)
        selected = prepared["selected"]
        all_charts = prepared["all_charts"]
        all_tables = prepared["all_tables"]
        context = prepared["context"]
        title = prepared["title"]

        # Stage 0：大纲先行（锦标赛择优；失败回落空大纲，按固定章节写作）
        if outline is None:
            outline = self._gen_outline(context)

        # Stage 1：分章写作（携带大纲与前一章摘要，注入章节专属规范）
        sections = self._write_sections(context, outline, has_articles=bool(articles))

        # Stage 2：文献元数据增强 + GB/T 7714 确定性格式化 + 引用编号回填 + 引用核验
        references = ""
        enriched = []
        if articles:
            enriched = ref_pack.enrich_articles(articles[:self.MAX_REFERENCES])
            references = ref_pack.format_gbt7714(enriched)
            if not references:  # 确定性格式化异常时回落 LLM 格式化
                references = self.llm.chat(
                    [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content":
                      "请将以下文献格式化为 GB/T 7714-2015 顺序编码制格式"
                      f"（卷期页缺失可省略，末尾保留 PMID）：\n{json.dumps(articles[:self.MAX_REFERENCES], ensure_ascii=False)[:8000]}\n"
                      "只输出编号文献列表。"}],
                    temperature=0.2, max_tokens=3000,
                    cache_namespace="research:reference_format",
                )
            sections = self._backfill_citations(sections, references)
            sections = self._verify_citations(sections, enriched or articles[:self.MAX_REFERENCES])

        # Stage 3a：第一轮数字质检（为修订提供可疑数字清单，确定性、开销极小）
        facts_pool = list(selected) + [{
            "skill": "研究背景",
            "facts": {"就诊记录数": 13743, "患者数": 3990,
                      "检验覆盖患者数": 826, "手术记录数": 85},
        }]
        for tb in all_tables:
            facts_pool.append({"skill": f"数据表:{tb.get('title', '')}",
                               "facts": {"columns": tb.get("columns"), "rows": tb.get("rows")}})
        suspicious = []
        try:
            suspicious = quality.check_number_consistency(sections, facts_pool).get(
                "suspicious_numbers", [])
        except Exception:
            pass

        # Stage 4：结构化自评审 + 定向修订（评审意见与可疑数字清单闭环处理，失败保留原稿）
        review = self._review_paper(title, sections)
        if review or suspicious:
            sections = self._revise_sections(context, sections, review, suspicious)

        # Stage 3b：终稿质检（对修订后正文出具最终报告：数字一致性 + skills lint）
        quality_report = {"numbers": {}, "lints": {}}
        try:
            quality_report["numbers"] = quality.check_number_consistency(sections, facts_pool)
            quality_report["lints"] = quality.run_skill_lints(sections, references)
        except Exception:
            pass

        # Stage 5：生成论文 docx（正文，不含质检附录）；质检与评审报告独立成文
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"科研论文_{ts}.docx"
        filepath = self._build_docx(OUTPUT_DIR / filename, title, sections, references,
                                    all_charts[:6], tables=all_tables[:6])
        report_filename = f"质检与评审报告_{ts}.docx"
        self._build_report_docx(OUTPUT_DIR / report_filename, title, quality_report, review)

        project_id = f"research_project_{uuid.uuid4().hex[:8]}"
        json_store.save(project_id, convert({
            "project_id": project_id,
            "question": question,
            "title": title,
            "result_ids": result_ids,
            "outline": outline,
            "sections": sections,
            "references": references,
            "quality_report": quality_report,
            "review": review,
            "filename": filename,
            "report_filename": report_filename,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }))

        return convert({
            "paper": {"title": title, "sections": sections, "references": references},
            "quality_report": quality_report,
            "review": review,
            "filename": filename,
            "download_url": f"/api/research/paper/download/{filename}",
            "report_filename": report_filename,
            "report_download_url": f"/api/research/paper/download/{report_filename}",
        })

    # ---------- Stage 0：大纲（锦标赛择优，借鉴 Co-Scientist 生成-批判-排序） ----------

    def _outline_prompt(self, context: str) -> str:
        return (
            f"{context}\n\n{guidance.writing_rules()}\n\n"
            "请先为全文拟定详细大纲：各章节的要点与逻辑主线，结果章节按小节列出"
            "拟呈现的分析结果（对应到上述事实），讨论章节列出主要发现/文献比较/局限性要点。"
            "只输出大纲本身，供后续分章写作使用。")

    def _gen_outline(self, context: str) -> str:
        """生成两个候选大纲，由评审调用择优/融合（锦标赛机制）；失败逐级降级"""
        prompt = self._outline_prompt(context)
        candidates = []
        for temp in (0.3, 0.7):
            o = self.llm.chat(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content": prompt}],
                temperature=temp, max_tokens=2000,
                cache_namespace="research:paper_outline_auto",
            )
            if o and not o.startswith("[LLM调用失败]"):
                candidates.append(o)
        if not candidates:
            return ""
        if len(candidates) == 1 or candidates[0] == candidates[1]:
            return candidates[0]

        judged = self.llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              f"{context}\n\n以下是同一篇论文的两版大纲：\n\n【大纲A】\n{candidates[0]}\n\n"
              f"【大纲B】\n{candidates[1]}\n\n"
              "请从与研究问题的契合度、数字与事实的对应准确性、章节逻辑完整性三方面批判性评估两版大纲，"
              "输出更优的一版（可吸收另一版的优点做修订）。只输出最终大纲，不要评价过程。"}],
            temperature=0.2, max_tokens=2000,
            cache_namespace="research:outline_judge",
        )
        if judged and not judged.startswith("[LLM调用失败]") and len(judged) > 100:
            return judged
        return candidates[0]

    # ---------- Stage 1：分章写作 ----------

    # 章节专属写作要求（在通用要求之上叠加）
    SECTION_GUIDES = {
        "摘要": "（含3-5个关键词，300字左右，按背景/方法/结果/结论组织）",
        "前言": "（500-800字，学术语言；引用文献处留待后续统一编号，先以'有研究表明'等表述行文）",
        "文献综述": "（600-900字，学术综述语言：按主题归纳所附参考文献的研究进展与共识，"
                   "每个主题句后用[n]标注对应参考文献编号（编号与上文'参考文献'列表一致）；"
                   "指出现有研究的空白与不足，自然引出本研究问题；不得引用列表之外的文献）",
        "资料与方法": "（500-800字，写清数据来源/纳入排除/变量定义/统计方法；不得虚构伦理批件号）",
        "结果": "（按小节组织，逐一引用分析结果事实中的具体数字；表格与图在文中需要位置单独成行"
               "标注占位，格式：【表N 表题（占位）】、【图N 图题（占位）】；"
               "只做客观描述，禁止'导致''证明'等因果表述，不写任何 facts 之外的数字）",
        "讨论": "（500-800字：主要发现/与文献比较/机制解释/局限性）",
        "结论": "（200-400字，仅总结有数据支持的发现，关联不得写成因果）",
    }

    # 关键章节双稿择优（借鉴 AI Scientist v2 树搜索的退化版 best-of-2）
    TOURNAMENT_SECTIONS = {"摘要", "文献综述", "讨论"}

    def _write_sections(self, context: str, outline: str, has_articles: bool = False) -> dict:
        """分章写作：每章携带大纲与已完成前一章的摘要，保证章节间衔接；
        关键章节生成双稿并由评审调用择优；无文献时综述章节给占位提示"""
        sections = {}
        prev_brief = ""
        for sec in self.PAPER_SECTIONS:
            if sec == "文献综述" and not has_articles:
                sections[sec] = ("（本次生成未附参考文献，文献综述从略。"
                               "建议先运行'文献检索'算子并勾选文献后重新生成。）")
                continue
            extra = self.SECTION_GUIDES.get(sec, "（500-800字，学术语言）")
            rules = guidance.writing_rules()
            if sec == "讨论":
                rules += "\n\n" + guidance.critical_checklist()
            prompt = f"{context}\n\n"
            if outline:
                prompt += f"全文大纲：\n{outline}\n\n"
            if prev_brief:
                prompt += f"已完成的前序章节要点（保持衔接，不要重复）：\n{prev_brief}\n\n"
            prompt += f"{rules}\n\n请撰写论文「{sec}」部分{extra}。只输出该章节正文。"
            content = self.llm.chat(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content": prompt}],
                temperature=0.4, max_tokens=2500,
                cache_namespace="research:paper_writing",
            )
            if sec in self.TOURNAMENT_SECTIONS \
                    and content and not content.startswith("[LLM调用失败]"):
                content = self._best_of_two(context, sec, prompt, content)
            sections[sec] = content
            if content and not content.startswith("[LLM调用失败]"):
                prev_brief += f"【{sec}】{content[:200]}\n"
        return sections

    def _best_of_two(self, context: str, sec: str, prompt: str, draft_a: str) -> str:
        """关键章节 best-of-2：再生成一稿，评审择优/融合；任何失败回落第一稿"""
        draft_b = self.llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=2500,
            cache_namespace="research:paper_writing",
        )
        if not draft_b or draft_b.startswith("[LLM调用失败]") or draft_b == draft_a:
            return draft_a

        judged = self.llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              f"{context}\n\n以下是论文「{sec}」的两个版本：\n\n【版本A】\n{draft_a}\n\n"
              f"【版本B】\n{draft_b}\n\n"
              "请从数字与事实的一致性、学术表达质量、逻辑连贯性三方面批判性评估两版，"
              "输出更优的一版（可吸收另一版优点修订；引用数字必须出自分析结果事实）。"
              "只输出最终章节正文，不要评价过程。"}],
            temperature=0.2, max_tokens=2500,
            cache_namespace="research:section_judge",
        )
        if judged and not judged.startswith("[LLM调用失败]") and len(judged) > 50:
            return judged
        return draft_a

    # ---------- Stage 2：引用编号回填 ----------

    # 参与引用编号回填与引用-断言核验的章节
    CITATION_SECTIONS = ("前言", "文献综述", "讨论")

    def _backfill_citations(self, sections: dict, references: str) -> dict:
        """在引用章节中回填 [n] 引用编号（限定编号范围，失败保留原文）"""
        if not references or references.startswith("[LLM调用失败]"):
            return sections
        for sec in self.CITATION_SECTIONS:
            content = sections.get(sec, "")
            if not content or content.startswith("[LLM调用失败]"):
                continue
            revised = self.llm.chat(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content":
                  f"参考文献列表：\n{references}\n\n"
                  f"论文章节「{sec}」原文：\n{content}\n\n"
                  "请在该章节中引用他人研究观点/数据的位置插入顺序编码引用标记[n]，"
                  "编号只能使用上面参考文献列表中存在的编号；不引用文献的内容不要加标记。"
                  "除插入引用标记外不得改动原文任何文字与数字。只输出修订后的章节正文。"}],
                temperature=0.2, max_tokens=2500,
                cache_namespace="research:citation_backfill",
            )
            if revised and not revised.startswith("[LLM调用失败]"):
                sections[sec] = revised
        return sections

    # ---------- Stage 2b：引用-断言核验 ----------

    _CITATION_RE = re.compile(r"\[(\d{1,2})\]")

    @classmethod
    def _extract_citation_items(cls, sections: dict, articles: list[dict],
                                max_items: int = 20) -> list[dict]:
        """提取引用章节中的 [n] 引用标记及其所在句子，配对被引文献元数据"""
        items = []
        seen = set()
        for sec in cls.CITATION_SECTIONS:
            content = sections.get(sec, "")
            if not isinstance(content, str):
                continue
            for m in cls._CITATION_RE.finditer(content):
                n = int(m.group(1))
                if not (1 <= n <= len(articles)):
                    continue
                # 取标记所在完整句子
                left = max(content.rfind(c, 0, m.start()) for c in "。；;！？!?\n") + 1
                rights = [content.find(c, m.end()) for c in "。；;！？!?\n"]
                rights = [r for r in rights if r >= 0]
                right = min(rights) + 1 if rights else len(content)
                sentence = re.sub(r"\s+", " ", content[left:right]).strip()[:300]
                key = (sec, n, sentence)
                if key in seen:
                    continue
                seen.add(key)
                art = articles[n - 1]
                items.append({
                    "section": sec, "ref_no": n, "sentence": sentence,
                    "ref_title": str(art.get("title", "")),
                    "ref_abstract": str(art.get("abstract") or "")[:400],
                })
                if len(items) >= max_items:
                    return items
        return items

    @staticmethod
    def _remove_citation_marker(content: str, sentence: str, ref_no: int) -> str:
        """在指定句子中移除一个 [n] 引用标记（句子定位失败则不改动）"""
        idx = content.find(sentence[:40])
        if idx < 0:
            return content
        seg_end = idx + len(sentence) + 20
        seg = content[idx:seg_end]
        seg_new = seg.replace(f"[{ref_no}]", "", 1)
        return content[:idx] + seg_new + content[seg_end:]

    def _verify_citations(self, sections: dict, articles: list[dict]) -> dict:
        """引用-断言核验（借鉴 OpenScholar 自反馈环）：LLM 判断被引文献摘要是否支持
        所在句子的论断，不支持的移除该引用标记；核验失败保守保留原文"""
        items = self._extract_citation_items(sections, articles)
        if not items:
            return sections

        payload = "\n\n".join(
            f"[item {i}] 章节「{it['section']}」句子：{it['sentence']}\n"
            f"被引文献[{it['ref_no']}]：{it['ref_title']}。摘要：{it['ref_abstract']}"
            for i, it in enumerate(items))
        verdict = self.llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              "以下每一对是论文中的一个引用句与其标注引用的文献摘要。"
              "请逐条判断：该文献的标题/摘要是否能支持句子中引用位置处的论断"
              "（主题相关、不矛盾即可视为支持；主题明显无关或论断与文献内容冲突视为不支持）。\n\n"
              f"{payload}\n\n"
              '只输出 JSON：{"unsupported": [不支持的 item 编号数组]}，全部支持则输出空数组。'}],
            temperature=0.1, max_tokens=500,
            cache_namespace="research:citation_verify",
        )
        if not verdict or verdict.startswith("[LLM调用失败]"):
            return sections

        try:
            import json as _json
            m = re.search(r"\{.*\}", verdict, re.S)
            unsupported = set(_json.loads(m.group())["unsupported"]) if m else set()
        except Exception:
            return sections

        for i, it in enumerate(items):
            if i in unsupported:
                sec = it["section"]
                sections[sec] = self._remove_citation_marker(
                    sections[sec], it["sentence"], it["ref_no"])
        return sections

    # ---------- Stage 4：自评审与修订 ----------

    @staticmethod
    def _is_degenerate(text: str) -> bool:
        """检测 LLM 退化输出（短片段死循环重复或字符多样性极低）"""
        if not text:
            return True
        compact = re.sub(r"\s+", "", text)
        # 任意 2-12 字符片段连续重复 5 次以上 → 死循环
        if re.search(r"(.{2,12}?)\1{5,}", compact):
            return True
        # 长文本但字符种类极少 → 无信息量
        if len(compact) > 100 and len(set(compact)) / len(compact) < 0.08:
            return True
        return False

    def _review_paper(self, title: str, sections: dict) -> str:
        """按评审维度对全稿做结构化自评审，失败或输出退化时返回空串"""
        draft = "\n\n".join(
            f"【{sec}】{(content or '')[:1500]}" for sec, content in sections.items()
        )
        review = self.llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              f"论文题目：{title}\n\n{guidance.review_dimensions()}\n\n"
              "请以审稿人视角按上述维度评审以下草稿。要求：直接输出评审内容，"
              "不要复述任务指令、不要寒暄；每个维度按'维度名：分数/10——具体问题'的格式输出；"
              "总长度控制在 600 字以内，禁止重复词句。"
              "注：正文中的【表N/图N（占位）】标记会在导出时替换为真实表格与图片，"
              "不要将占位标记本身作为问题评价。\n\n"
              f"论文草稿：\n{draft[:9000]}"}],
            temperature=0.3, max_tokens=2500,
            cache_namespace="research:paper_review_auto",
        )
        if not review or review.startswith("[LLM调用失败]") or self._is_degenerate(review):
            return ""
        return review

    def _revise_sections(self, context: str, sections: dict, review: str,
                         suspicious: list | None = None) -> dict:
        """依据评审意见与数字质检清单对每章做一轮定向修订（单章失败保留原文）

        suspicious：check_number_consistency 检出的可疑数字，按章节过滤后随修订
        prompt 一并下发，要求逐条修正或删除——形成"质检→修订"闭环。
        """
        suspicious = suspicious or []
        review_block = (
            f"审稿意见（全文）：\n{review[:3000]}\n\n" if review else "")
        instruction = (
            "请依据审稿意见中与本章相关的问题修订该章节：修正数据/表述问题、"
            "补充缺失的局限性或方法细节、删除无数据支持的断言。"
            if review else "请修订该章节：")
        for sec in self.PAPER_SECTIONS:
            content = sections.get(sec, "")
            if not content or content.startswith("[LLM调用失败]"):
                continue
            sec_suspicious = [s for s in suspicious if s.get("section") == sec]
            number_block = ""
            if sec_suspicious:
                listed = "\n".join(
                    f"· 数值 {s['value']}：{s['context']}" for s in sec_suspicious[:10])
                number_block = (
                    "自动质检发现本章以下数字未在分析结果事实中找到（可能为幻觉或"
                    "二次派生计算），请逐条处理：能用分析结果事实中的数字修正的修正，"
                    "无法核实的删除或改写为无数字表述：\n"
                    f"{listed}\n\n")
            revised = self.llm.chat(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content":
                  f"{context}\n\n{guidance.writing_rules()}\n\n"
                  f"{review_block}{number_block}"
                  f"章节「{sec}」原文：\n{content}\n\n"
                  f"{instruction}"
                  "凡引用数字仍必须出自分析结果事实。只输出修订后的章节正文。"}],
                temperature=0.3, max_tokens=2500,
                cache_namespace="research:paper_revise",
            )
            if revised and not revised.startswith("[LLM调用失败]"):
                sections[sec] = revised
        return sections

    # ========== docx 生成（参照 document_service 的排版与 _chart_to_image 模式） ==========

    def _build_docx(self, filepath: Path, title: str, sections: dict,
                    references: str, charts: list,
                    tables: list | None = None) -> str:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.shared import Pt

        filepath.parent.mkdir(parents=True, exist_ok=True)
        doc = Document()

        # 算子产出的真实数据表，按顺序替换结果章节中的【表N …（占位）】
        table_queue = [t for t in (tables or []) if t.get("columns") and t.get("rows")]

        def set_font(run, cn_font: str, size: int, bold: bool = False):
            run.font.name = "Times New Roman"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), cn_font)
            run.font.size = Pt(size)
            run.font.bold = bold

        # 标题（黑体二号居中）
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run(title), "黑体", 16, bold=True)

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（AI 辅助起草，需人工审校）"),
                 "宋体", 9)

        def add_runs(para, text: str, size: int = 12, base_bold: bool = False):
            """按 ** 切分渲染行内加粗，去除 markdown 标记"""
            for idx, seg in enumerate(str(text).split("**")):
                if not seg:
                    continue
                set_font(para.add_run(seg), "宋体", size, bold=base_bold or idx % 2 == 1)

        def add_para(text: str, size: int = 12, bold: bool = False, indent: bool = True):
            para = doc.add_paragraph()
            if indent:
                para.paragraph_format.first_line_indent = Pt(24)
            para.paragraph_format.line_spacing = 1.5
            add_runs(para, text, size, base_bold=bold)

        def _fill_grid(grid, rows: list[list], header_bold: bool = True):
            for i, row in enumerate(rows):
                for j, val in enumerate(row):
                    cell = grid.rows[i].cells[j]
                    cell.text = ""
                    set_font(cell.paragraphs[0].add_run(str(val)),
                             "黑体" if i == 0 and header_bold else "宋体", 9,
                             bold=i == 0 and header_bold)

        def add_data_table(caption: str, columns: list, rows: list):
            """算子数据表 → Word 表格（最多 20 行）"""
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            set_font(cap.add_run(caption), "黑体", 10)
            cols = [str(c) for c in columns]
            body = [([str(v) for v in r][:len(cols)]
                     + [""] * (len(cols) - len(r))) for r in rows[:20]]
            grid = doc.add_table(rows=len(body) + 1, cols=len(cols))
            grid.style = "Table Grid"
            _fill_grid(grid, [cols] + body)

        def add_md_table(tbl_lines: list[str]):
            """markdown 表格块 → Word 表格"""
            rows = []
            for ln in tbl_lines:
                cells = [c.strip().replace("**", "") for c in ln.strip().strip("|").split("|")]
                if cells and all(set(c) <= set("-: ") for c in cells):
                    continue  # 分隔行
                rows.append(cells)
            if not rows:
                return
            ncol = max(len(r) for r in rows)
            rows = [r + [""] * (ncol - len(r)) for r in rows]
            grid = doc.add_table(rows=len(rows), cols=ncol)
            grid.style = "Table Grid"
            _fill_grid(grid, rows)

        # 表/图占位行，如【表1 xxx（占位）】、表2 xxx（占位）
        placeholder_re = re.compile(r"^[【\[]?\s*([表图])\s*\w*\s*(.*?)[（(]占位[)）]\s*[】\]]?\s*$")

        def add_section(sec_title: str, content: str, insert_tables: bool = False):
            h = doc.add_paragraph()
            set_font(h.add_run(sec_title), "黑体", 14, bold=True)
            lines = content.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                i += 1
                if not line:
                    continue
                # 与章节标题完全相同的裸行跳过（避免"文献综述/文献综述"重复标题）
                if line.lstrip("#* ").strip() == sec_title:
                    continue
                # markdown 表格块
                if line.startswith("|"):
                    tbl = [line]
                    while i < len(lines) and lines[i].strip().startswith("|"):
                        tbl.append(lines[i].strip())
                        i += 1
                    add_md_table(tbl)
                    continue
                # 表/图占位行：表→替换为真实数据表；图→由后续统一嵌入，此处跳过
                m_ph = placeholder_re.match(line)
                if m_ph:
                    if m_ph.group(1) == "表" and insert_tables and table_queue:
                        tb = table_queue.pop(0)
                        caption = m_ph.group(2).strip(" 】]") or tb.get("title") or "数据表"
                        add_data_table(caption, tb["columns"], tb["rows"])
                    continue
                # markdown 标题行（# 开头）
                m_h = re.match(r"^#{1,4}\s*(.+?)\s*$", line)
                if m_h:
                    add_para(m_h.group(1).replace("**", ""), bold=True, indent=False)
                    continue
                # 整行加粗（**小节标题**）；与章节标题重复则跳过
                m_b = re.match(r"^\*\*(.+?)\*\*\s*$", line)
                if m_b:
                    sub = m_b.group(1).strip()
                    if sub != sec_title:
                        add_para(sub, bold=True, indent=False)
                    continue
                add_para(line)

        for sec in self.PAPER_SECTIONS:
            content = sections.get(sec, "")
            if not content or content.startswith("[LLM调用失败]"):
                content = f"（本章节生成失败：{content or '空'}，请补充。）"
            add_section(sec, content, insert_tables=(sec == "结果"))
            # 结果章节：未被占位消耗的剩余数据表 + 图表
            if sec == "结果":
                while table_queue:
                    tb = table_queue.pop(0)
                    add_data_table(tb.get("title") or "数据表", tb["columns"], tb["rows"])
                for ch in charts:
                    img = self._chart_to_image(ch.get("option", {}))
                    if img:
                        doc.add_picture(io.BytesIO(img), width=Pt(400))
                        cap = doc.add_paragraph()
                        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        set_font(cap.add_run(ch.get("title", "图")), "黑体", 10)

        if references:
            add_section("参考文献", references)

        doc.save(str(filepath))
        return str(filepath)

    def _build_report_docx(self, filepath: Path, title: str,
                           quality_report: dict | None, review: str) -> str:
        """质检与自评审报告独立成文（与论文正文分开输出）"""
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
        from docx.shared import Pt

        filepath.parent.mkdir(parents=True, exist_ok=True)
        doc = Document()

        def set_font(run, cn_font: str, size: int, bold: bool = False):
            run.font.name = "Times New Roman"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), cn_font)
            run.font.size = Pt(size)
            run.font.bold = bold

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run("AI 质检与自评审报告"), "黑体", 16, bold=True)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run(f"对应论文：{title}"), "宋体", 10)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_font(p.add_run(
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（AI 生成，仅供人工核对参考）"),
            "宋体", 9)

        for line in self._format_appendix(quality_report, review).split("\n"):
            line = line.strip()
            if not line:
                continue
            is_head = bool(re.match(r"^[一二三四五六七八九十]+、", line))
            para = doc.add_paragraph()
            para.paragraph_format.line_spacing = 1.5
            set_font(para.add_run(line), "黑体" if is_head else "宋体",
                     12 if is_head else 10, bold=is_head)

        doc.save(str(filepath))
        return str(filepath)

    @staticmethod
    def _format_appendix(quality_report: dict | None, review: str) -> str:
        """将质检报告与自评审整理为 docx 附录文本"""
        parts = []
        numbers = (quality_report or {}).get("numbers") or {}
        suspicious = numbers.get("suspicious_numbers") or []
        if suspicious:
            lines = ["一、数字一致性校验（正文数字与算子 facts 自动比对，仅作提示）："]
            for s in suspicious[:15]:
                lines.append(f"· [{s.get('section')}] 数值 {s.get('value')} 未在分析结果中找到：{s.get('context')}")
            parts.append("\n".join(lines))
        else:
            parts.append("一、数字一致性校验：未发现正文数字与分析结果明显不符（自动比对，仅供参"
                         "考）。")
        lints = ((quality_report or {}).get("lints") or {}).get("lints") or []
        if lints:
            lines = ["二、写作规范 lint 警告："]
            for it in lints[:15]:
                lines.append(f"· [{it.get('tool') or it.get('skill')}] {it.get('code')} "
                             f"{it.get('message') or it.get('location')}")
            parts.append("\n".join(lines))
        if review:
            parts.append(f"三、结构化自评审：\n{review}")
        return "\n\n".join(parts)

    def _chart_to_image(self, option: dict, width: int = 8, height: int = 5) -> bytes:
        """将 ECharts option 用 matplotlib 渲染为 PNG 字节（参照 document_service._chart_to_image）"""
        import matplotlib
        matplotlib.use("Agg")
        matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False
        import matplotlib.pyplot as plt

        # 应用 scientific-visualization 的色盲友好调色板与出版级版式（保留中文字体）
        try:
            figure_style.apply_style()
            matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
        except Exception:
            pass

        series = option.get("series", [])
        if not series:
            return b""

        title = option.get("title", {}).get("text", "")
        x_data = option.get("xAxis", {}).get("data", [])
        s0 = series[0]
        s_type = s0.get("type", "bar")

        fig, ax = plt.subplots(figsize=(width, height))
        try:
            if s_type == "pie":
                data = s0.get("data", [])
                ax.pie([d["value"] for d in data], labels=[d["name"] for d in data],
                       autopct="%1.1f%%")
                ax.set_title(title)
            elif s_type == "scatter":
                for s in series:
                    data = s.get("data", [])
                    if not data:
                        continue
                    xs = [p[0] for p in data]
                    ys = [p[1] for p in data]
                    ax.scatter(xs, ys, s=8, alpha=0.5, label=s.get("name", ""))
                ax.set_title(title)
                ax.set_xlabel(option.get("xAxis", {}).get("name", ""))
                ax.set_ylabel(option.get("yAxis", {}).get("name", ""))
                if any(s.get("name") for s in series):
                    ax.legend()
            elif s_type == "heatmap":
                data = s0.get("data", [])
                x_labels = option.get("xAxis", {}).get("data", [])
                y_labels = option.get("yAxis", {}).get("data", [])
                import numpy as np
                mat = np.zeros((len(y_labels), len(x_labels)))
                for xi, yi, v in data:
                    mat[yi][xi] = v
                im = ax.imshow(mat, cmap="RdBu_r", vmin=-1, vmax=1)
                ax.set_xticks(range(len(x_labels)), x_labels, rotation=45, ha="right")
                ax.set_yticks(range(len(y_labels)), y_labels)
                fig.colorbar(im, ax=ax)
                ax.set_title(title)
            elif s_type == "graph":
                # 网络图不适合静态渲染，跳过
                plt.close()
                return b""
            elif s_type == "bar" and option.get("xAxis", {}).get("type") == "value":
                y_data = option.get("yAxis", {}).get("data", [])
                ax.barh([str(y) for y in y_data], s0.get("data", []))
                ax.set_title(title)
            else:
                for s in series:
                    data = s.get("data", [])
                    if s.get("type") == "line":
                        ax.plot(x_data, data, label=s.get("name", ""), marker="o")
                    else:
                        ax.bar([str(x) for x in x_data], data, label=s.get("name", ""))
                ax.set_title(title)
                ax.set_xlabel(option.get("xAxis", {}).get("name", ""))
                ax.set_ylabel(option.get("yAxis", {}).get("name", ""))
                if len(series) > 1 or any(s.get("name") for s in series):
                    ax.legend()
                plt.xticks(rotation=30, ha="right")

            plt.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150)
            plt.close()
            buf.seek(0)
            return buf.read()
        except Exception:
            plt.close()
            return b""


# 全局单例
research_assistant_service = ResearchAssistantService()
