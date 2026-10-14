"""文献元数据增强与 GB/T 7714 确定性格式化。

- enrich_articles：用 OpenAlex 免费 API（无需 key）按 PMID/标题补全卷期页与 DOI；
  联网失败时原样返回，不抛异常。
- format_gbt7714：确定性模板生成 GB/T 7714-2015 顺序编码制条目，
  替代纯 LLM 格式化，避免编造卷期页。
"""
import re

import requests

OPENALEX_WORKS = "https://api.openalex.org/works"


def _lookup_openalex(article: dict, timeout: int = 10) -> dict | None:
    """按 PMID（优先）或标题查询 OpenAlex，返回 work 对象；失败返回 None"""
    pmid = str(article.get("pmid") or "").strip()
    try:
        if pmid:
            resp = requests.get(f"{OPENALEX_WORKS}/pmid:{pmid}", timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            return None
        title = str(article.get("title") or "").strip()
        if title:
            resp = requests.get(
                OPENALEX_WORKS,
                params={"search": title, "per-page": 1},
                timeout=timeout,
            )
            if resp.status_code == 200:
                results = resp.json().get("results") or []
                return results[0] if results else None
    except Exception:
        return None
    return None


def enrich_articles(articles: list[dict]) -> list[dict]:
    """补全每篇文献的 volume/issue/pages/doi；任一失败则保留原样"""
    enriched = []
    for a in articles or []:
        item = dict(a)
        work = _lookup_openalex(a)
        if work:
            biblio = work.get("biblio") or {}
            item.setdefault("volume", biblio.get("volume") or "")
            item.setdefault("issue", biblio.get("issue") or "")
            first, last = biblio.get("first_page"), biblio.get("last_page")
            if first and not item.get("pages"):
                item["pages"] = f"{first}-{last}" if last and last != first else str(first)
            doi = (work.get("doi") or "").replace("https://doi.org/", "")
            if doi and not item.get("doi"):
                item["doi"] = doi
            if not item.get("year") and work.get("publication_year"):
                item["year"] = str(work["publication_year"])
        enriched.append(item)
    return enriched


def _format_authors(authors: list[str]) -> str:
    """GB/T 7714：3 名以上作者取前 3 加 et al（西文）"""
    authors = [str(a).strip() for a in (authors or []) if str(a).strip()]
    if not authors:
        return "佚名"
    if len(authors) > 3:
        return ", ".join(authors[:3]) + ", et al"
    return ", ".join(authors)


def _is_cjk(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text or ""))


def format_gbt7714(articles: list[dict]) -> str:
    """确定性生成 GB/T 7714-2015 顺序编码制期刊文献条目"""
    lines = []
    for i, a in enumerate(articles or [], 1):
        authors = _format_authors(a.get("authors"))
        title = str(a.get("title") or "").strip().rstrip(".")
        journal = str(a.get("journal") or "").strip()
        year = str(a.get("year") or "").strip()
        volume = str(a.get("volume") or "").strip()
        issue = str(a.get("issue") or "").strip()
        pages = str(a.get("pages") or "").strip()
        doi = str(a.get("doi") or "").strip()
        pmid = str(a.get("pmid") or "").strip()

        # [序号] 作者. 题名[J]. 刊名, 年, 卷(期): 起止页.
        entry = f"[{i}] {authors}. {title}[J]."
        if journal:
            entry += f" {journal}"
            if year:
                entry += f", {year}"
            if volume:
                entry += f", {volume}"
                if issue:
                    entry += f"({issue})"
            if pages:
                entry += f": {pages}"
            entry += "."
        elif year:
            entry += f" {year}."
        if doi:
            entry += f" DOI: {doi}."
        elif pmid:
            entry += f" PMID: {pmid}."
        lines.append(entry)
    return "\n".join(lines)
