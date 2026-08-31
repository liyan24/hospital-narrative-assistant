"""论文写作类算子（LLM 驱动）：选题建议、文献检索、提纲、正文、参考文献格式化、自评审。"""
import json
import xml.etree.ElementTree as ET

from services.llm_service import llm_service
from services.research.dataset_service import dataset_service
from services.research.skills.base import BaseSkill, SkillMeta, make_result

PUBMED_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

SYSTEM_PROMPT = (
    "你是一位资深的临床科研方法学顾问与医学论文写作专家，"
    "熟悉肿瘤与血液病领域、真实世界研究方法和中文医学论文规范（GB/T 7714）。"
    "回答使用中文，内容严谨、专业、可落地；涉及统计结果时不得编造数据，"
    "只能基于用户提供的事实数据展开。"
)


def _chat(messages: list[dict], skill_id: str, max_tokens: int = 2000,
          temperature: float = 0.4) -> str:
    """LLM 调用（失败返回 '[LLM调用失败] ...' 字符串，不抛异常）"""
    return llm_service.chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        cache_namespace=f"research:{skill_id}",
    )


def _llm_failed(text: str) -> bool:
    return not text or text.startswith("[LLM调用失败]")


class TopicSuggestionSkill(BaseSkill):
    meta = SkillMeta(
        id="topic_suggestion",
        name="科研选题建议",
        category="论文写作",
        description="基于数据资产摘要与已有分析结果，LLM 生成 3-5 个候选选题与研究假设",
        params_schema=[
            {"name": "focus", "label": "关注方向", "type": "string",
             "default": "", "description": "可选，如'再入院'、'合并症'、'用药规律'"},
            {"name": "facts", "label": "已有分析结果(JSON)", "type": "string",
             "default": "", "description": "可选，粘贴其他算子结果中的 facts 内容"},
        ],
        data_requirements="数据资产清单（无需完整数据）",
    )

    def run(self, params: dict) -> dict:
        focus = str(self.get_param(params, "focus") or "").strip()
        facts_text = str(self.get_param(params, "facts") or "").strip()

        assets = dataset_service.detect_data_assets()
        assets_brief = json.dumps({
            "tables": [{k: t[k] for k in ("name", "rows", "cols", "coverage_note")}
                       for t in assets["tables"]],
            "graph_available": assets["graph"].get("available", False),
            "text_data": assets["text_data"],
        }, ensure_ascii=False, indent=1)

        prompt = (
            "以下是某医院肿瘤血液科的真实世界数据资产概况：\n"
            f"{assets_brief}\n\n"
            + (f"已完成的初步分析结果：\n{facts_text}\n\n" if facts_text else "")
            + (f"研究者关注方向：{focus}\n\n" if focus else "")
            + "请基于以上数据条件，提出 3-5 个可落地的回顾性科研选题。"
            "每个选题包含：1) 题目；2) 研究背景一句话；3) 研究假设（必须明确标注为'候选假设'）；"
            "4) 可用的数据字段与分析方法建议；5) 主要局限性。"
            "选题必须与数据实际字段匹配，不要提出数据无法支持的方案。"
        )
        content = _chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": prompt}],
            self.meta.id, max_tokens=3000, temperature=0.5,
        )
        if _llm_failed(content):
            return make_result(
                f"选题建议生成失败：{content}。可稍后在 LLM 可用时重试，"
                "或先运行'数据集画像'算子了解数据概况后人工拟定选题。"
            )

        return make_result(
            summary=content,
            facts={"focus": focus, "suggestions_text": content},
        )


class LiteratureSearchSkill(BaseSkill):
    meta = SkillMeta(
        id="literature_search",
        name="文献检索（PubMed）",
        category="论文写作",
        description="PubMed E-utilities 检索文献并生成中文要点总结；网络失败时给出离线建议",
        params_schema=[
            {"name": "query", "label": "检索式", "type": "string",
             "default": "", "description": "PubMed 检索词，如 'lymphoma readmission'"},
            {"name": "max_results", "label": "返回条数", "type": "number",
             "default": 5, "min": 1, "max": 20},
        ],
        data_requirements="互联网访问（PubMed E-utilities）",
    )

    def _esearch(self, query: str, max_results: int) -> list[str]:
        import requests
        resp = requests.get(
            f"{PUBMED_EUTILS}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": max_results,
                    "retmode": "json", "sort": "relevance"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("esearchresult", {}).get("idlist", [])

    def _efetch(self, pmids: list[str]) -> list[dict]:
        import requests
        resp = requests.get(
            f"{PUBMED_EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
            timeout=30,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        articles = []
        for art in root.findall(".//PubmedArticle"):
            med = art.find("MedlineCitation")
            if med is None:
                continue
            pmid = (med.findtext("PMID") or "").strip()
            article = med.find("Article")
            if article is None:
                continue
            title = "".join(article.find("ArticleTitle").itertext()) \
                if article.find("ArticleTitle") is not None else ""

            authors = []
            for a in article.findall(".//Author"):
                last, init = a.findtext("LastName"), a.findtext("Initials")
                if last:
                    authors.append(f"{last} {init}" if init else last)

            journal = article.findtext(".//Journal/Title") or ""
            year = (article.findtext(".//JournalIssue/PubDate/Year")
                    or article.findtext(".//JournalIssue/PubDate/MedlineDate") or "")[:4]

            abstract_parts = [
                "".join(ab.itertext()) for ab in article.findall(".//Abstract/AbstractText")
            ]
            articles.append({
                "pmid": pmid,
                "title": title.strip(),
                "authors": authors[:6],
                "journal": journal.strip(),
                "year": year,
                "abstract": " ".join(abstract_parts).strip(),
            })
        return articles

    def run(self, params: dict) -> dict:
        query = str(self.get_param(params, "query") or "").strip()
        max_results = int(self.get_param(params, "max_results"))
        if not query:
            return make_result("请先填写 PubMed 检索式。")

        try:
            pmids = self._esearch(query, max_results)
            articles = self._efetch(pmids) if pmids else []
        except Exception as e:
            return make_result(
                f"文献检索不可用：PubMed 接口访问失败（{e}）。"
                "离线建议：1) 可在中国知网/万方/维普以相同关键词手工检索；"
                "2) 检索词建议采用'疾病名 + 研究设计（retrospective/cohort）'组合；"
                "3) 网络恢复后可重试本算子。"
            )

        if not articles:
            return make_result(f"检索式「{query}」未命中任何文献，建议调整检索词后重试。")

        tables = [{
            "title": f"PubMed 检索结果（{len(articles)} 篇）",
            "columns": ["PMID", "标题", "第一作者", "期刊", "年份"],
            "rows": [[a["pmid"], a["title"], a["authors"][0] if a["authors"] else "",
                      a["journal"], a["year"]] for a in articles],
        }]

        # LLM 中文要点总结
        brief = "\n\n".join(
            f"[{i+1}] {a['title']}（{a['journal']}, {a['year']}）\n摘要：{a['abstract'][:800]}"
            for i, a in enumerate(articles)
        )
        digest = _chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              f"以下是检索式「{query}」命中的 {len(articles)} 篇文献标题与摘要：\n\n{brief}\n\n"
              "请用中文逐篇提炼 2-3 句要点（研究设计、样本量、核心结论），"
              "最后给出一段'对本研究的启示'。"}],
            self.meta.id, max_tokens=3000, temperature=0.3,
        )
        if _llm_failed(digest):
            digest = f"（LLM 要点总结暂不可用：{digest}。以下为文献原始信息，可人工阅读摘要。）"

        summary = f"检索式「{query}」命中 {len(articles)} 篇文献。\n\n{digest}"
        return make_result(summary, tables, facts={"query": query, "articles": articles})


class PaperOutlineSkill(BaseSkill):
    meta = SkillMeta(
        id="paper_outline",
        name="论文提纲生成",
        category="论文写作",
        description="按 IMRaD 结构生成中文论文提纲",
        params_schema=[
            {"name": "topic", "label": "论文选题", "type": "string", "default": ""},
            {"name": "facts", "label": "已有分析结果(JSON)", "type": "string",
             "default": "", "description": "可选，粘贴算子结果 facts"},
        ],
        data_requirements="无（纯 LLM 生成）",
    )

    def run(self, params: dict) -> dict:
        topic = str(self.get_param(params, "topic") or "").strip()
        facts_text = str(self.get_param(params, "facts") or "").strip()
        if not topic:
            return make_result("请先填写论文选题。")

        prompt = (
            f"论文选题：{topic}\n\n"
            + (f"已完成的分析结果事实：\n{facts_text}\n\n" if facts_text else "")
            + "研究背景：某县级医院肿瘤血液科真实世界回顾性数据（约1.37万就诊、3990名患者，"
            "含诊断/医嘱/检验/检查，检验覆盖约两成患者，无性别字段）。\n\n"
            "请按 IMRaD 结构生成详细论文提纲：摘要要点、前言（3段要点）、"
            "资料与方法（数据来源/纳入排除/变量定义/统计方法）、结果（按小节列出拟呈现的表和图）、"
            "讨论（主要发现/与文献比较/局限性）、结论。提纲要贴合上述数据条件。"
        )
        content = _chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": prompt}],
            self.meta.id, max_tokens=3000, temperature=0.4,
        )
        if _llm_failed(content):
            return make_result(f"提纲生成失败：{content}。可在 LLM 可用时重试。")

        return make_result(summary=content, facts={"topic": topic, "outline_text": content})


class PaperWritingSkill(BaseSkill):
    meta = SkillMeta(
        id="paper_writing",
        name="论文正文起草",
        category="论文写作",
        description="输入选题+事实数据+文献要点，分章节生成中文论文正文（IMRaD）",
        params_schema=[
            {"name": "topic", "label": "论文选题", "type": "string", "default": ""},
            {"name": "facts", "label": "分析结果事实(JSON)", "type": "string",
             "default": "", "description": "粘贴一个或多个算子结果的 facts"},
            {"name": "references", "label": "文献要点", "type": "string",
             "default": "", "description": "可选，文献检索算子的总结文本"},
        ],
        data_requirements="无（纯 LLM 生成）",
    )

    SECTIONS = ["摘要", "前言", "资料与方法", "结果", "讨论", "结论"]

    def run(self, params: dict) -> dict:
        topic = str(self.get_param(params, "topic") or "").strip()
        facts_text = str(self.get_param(params, "facts") or "").strip()
        references = str(self.get_param(params, "references") or "").strip()
        if not topic:
            return make_result("请先填写论文选题。")

        context = (
            f"论文选题：{topic}\n\n"
            f"分析结果事实（论文中引用数据必须来自此处，不得编造）：\n{facts_text or '（未提供，仅按方法学描述展开）'}\n\n"
            + (f"参考文献要点：\n{references}\n\n" if references else "")
            + "研究背景：某县级医院肿瘤血液科真实世界回顾性数据。"
        )

        sections = {}
        failed = []
        for sec in self.SECTIONS:
            content = _chat(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content":
                  f"{context}\n请撰写论文「{sec}」部分"
                  + ("（含3-5个关键词，300字左右）" if sec == "摘要"
                     else "（500-800字，学术语言，分小节可加小标题）")
                  + "。只输出该章节正文，不要输出其他内容。"}],
                self.meta.id, max_tokens=2500, temperature=0.4,
            )
            if _llm_failed(content):
                failed.append(sec)
            else:
                sections[sec] = content

        if not sections:
            return make_result(
                f"论文起草失败：LLM 全部章节调用不可用（{failed[0] if failed else '未知原因'}）。"
                "可在 LLM 可用时重试。"
            )

        summary = "；".join(f"【{k}】已完成" for k in sections)
        if failed:
            summary += f"；【{'、'.join(failed)}】生成失败，可重试"
        tables = [{
            "title": "论文章节预览（前200字）",
            "columns": ["章节", "内容预览"],
            "rows": [[k, v[:200] + "……"] for k, v in sections.items()],
        }]
        return make_result(summary, tables, facts={"topic": topic, "sections": sections})


class ReferenceFormatSkill(BaseSkill):
    meta = SkillMeta(
        id="reference_format",
        name="参考文献格式化（GB/T 7714）",
        category="论文写作",
        description="将文献列表（PMID检索结果）格式化为 GB/T 7714 中文参考文献格式",
        params_schema=[
            {"name": "articles", "label": "文献列表(JSON)", "type": "string",
             "default": "", "description": "文献检索算子 facts 中的 articles 数组（JSON 文本）"},
        ],
        data_requirements="文献检索算子的输出",
    )

    def run(self, params: dict) -> dict:
        raw = str(self.get_param(params, "articles") or "").strip()
        if not raw:
            return make_result("请先粘贴文献列表 JSON（可从文献检索算子的 facts.articles 复制）。")

        try:
            articles = json.loads(raw)
            assert isinstance(articles, list) and articles
        except (json.JSONDecodeError, AssertionError):
            return make_result("文献列表 JSON 解析失败，请确认粘贴的是 articles 数组文本。")

        brief = json.dumps(articles, ensure_ascii=False)[:6000]
        content = _chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              f"请将以下文献信息格式化为 GB/T 7714-2015 顺序编码制期刊文献格式"
              f"（[序号] 作者. 题名[J]. 刊名, 年, 卷(期): 起止页. 卷期页缺失时可省略，"
              f"保留 DOI 或 PMID 于末尾）：\n{brief}\n\n"
              "只输出编号文献列表，不要其他内容。"}],
            self.meta.id, max_tokens=2000, temperature=0.2,
        )
        if _llm_failed(content):
            return make_result(f"参考文献格式化失败：{content}。可在 LLM 可用时重试。")

        rows = [[line.strip()] for line in content.split("\n") if line.strip()]
        return make_result(
            summary=f"已将 {len(articles)} 篇文献格式化为 GB/T 7714 格式：\n\n{content}",
            tables=[{"title": "GB/T 7714 参考文献", "columns": ["条目"], "rows": rows}],
            facts={"formatted_references": content},
        )


class PaperReviewSkill(BaseSkill):
    meta = SkillMeta(
        id="paper_review",
        name="论文自评审",
        category="论文写作",
        description="LLM 对论文草稿做结构化自评审：创新性/方法/结果/写作四维度 + 修改建议",
        params_schema=[
            {"name": "draft", "label": "论文草稿", "type": "string",
             "default": "", "description": "粘贴论文草稿全文或主要章节"},
        ],
        data_requirements="无（纯 LLM 评审）",
    )

    def run(self, params: dict) -> dict:
        draft = str(self.get_param(params, "draft") or "").strip()
        if not draft:
            return make_result("请先粘贴论文草稿。")

        content = _chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content":
              "请以审稿人视角对以下中文医学论文草稿做结构化自评审，"
              "从四个维度分别打分（1-10）并指出问题：1) 创新性；2) 方法学严谨性"
              "（纳入排除/变量定义/统计方法）；3) 结果呈现（数据一致性/图表规范）；"
              "4) 写作质量（结构/语言/逻辑）。最后给出按优先级排序的具体修改建议清单。\n\n"
              f"论文草稿：\n{draft[:8000]}"}],
            self.meta.id, max_tokens=3000, temperature=0.3,
        )
        if _llm_failed(content):
            return make_result(f"自评审失败：{content}。可在 LLM 可用时重试。")

        return make_result(summary=content, facts={"review_text": content})


topic_suggestion_skill = TopicSuggestionSkill()
literature_search_skill = LiteratureSearchSkill()
paper_outline_skill = PaperOutlineSkill()
paper_writing_skill = PaperWritingSkill()
reference_format_skill = ReferenceFormatSkill()
paper_review_skill = PaperReviewSkill()
