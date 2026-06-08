"""
中医特色叙事增强服务
分析中医证型-用药关联、中西医结合对比、证型分布趋势等
"""
import re
from typing import Optional

from database.neo4j_client import neo4j_client
from services.llm_service import llm_service


class TCMNarrativeService:
    """中医特色叙事服务"""

    # 中药/中成药识别关键词
    TCM_DRUG_KEYWORDS = [
        "颗粒", "汤", "丸", "胶囊", "口服液", "注射液", "散", "膏", "丹", "片",
        "复方", "华蟾素", "艾愈", "地奥心血康", "云南白药", "肝爽", "麻仁",
        "稳心", "六味地黄", "金水宝", "百令", "黄芪", "人参", "当归", "党参",
        "白术", "茯苓", "甘草", "丹参", "川芎", "红花", "三七", "半夏", "陈皮",
        "柴胡", "黄芩", "黄连", "连翘", "金银花", "板蓝根", "蒲公英", "鱼腥草",
        "苦参", "薏苡仁", "枸杞子", "麦冬", "五味子", "附子", "肉桂", "熟地黄",
        "山茱萸", "山药", "泽泻", "牡丹皮", "知母", "黄柏", "鳖甲", "龟甲",
        "阿胶", "鹿角", "冬虫夏草", "灵芝", "刺五加", "绞股蓝", "银杏叶",
    ]

    # 西药识别（通过排除中药）
    def _is_tcm_drug(self, drug_name: str) -> bool:
        return any(kw in drug_name for kw in self.TCM_DRUG_KEYWORDS)

    def generate_syndrome_drug_narrative(self, syndrome_name: Optional[str] = None,
                                          western_disease: Optional[str] = None) -> dict:
        """
        证型-用药关联叙事
        输入：中医证型名 或 西医疾病名
        返回：该证型/疾病下的用药模式叙事
        """
        if syndrome_name:
            return self._narrative_for_syndrome(syndrome_name)
        if western_disease:
            return self._narrative_for_disease_syndromes(western_disease)
        return self._narrative_global_tcm_patterns()

    def _normalize_syndrome_name(self, name: str) -> str:
        """规范化证型名，尝试匹配图谱中的名称"""
        name = name.strip()
        # 如果用户输入没有::tcm后缀，加上
        if "::" not in name:
            # 尝试精确匹配
            recs = neo4j_client.run(
                "MATCH (d:Disease) WHERE d.name = $name + '::tcm' RETURN d.name AS name LIMIT 1",
                {"name": name}
            )
            if recs:
                return recs[0]["name"]
            # 尝试模糊匹配
            recs = neo4j_client.run(
                "MATCH (d:Disease) WHERE d.type IN ['tcm', 'tcm_syndrome'] AND d.name CONTAINS $name RETURN d.name AS name LIMIT 1",
                {"name": name}
            )
            if recs:
                return recs[0]["name"]
        return name

    def _normalize_western_disease(self, name: str) -> str:
        """规范化西医疾病名"""
        name = name.strip()
        if "::" not in name:
            recs = neo4j_client.run(
                "MATCH (d:Disease) WHERE d.name = $name + '::western' RETURN d.name AS name LIMIT 1",
                {"name": name}
            )
            if recs:
                return recs[0]["name"]
            recs = neo4j_client.run(
                "MATCH (d:Disease) WHERE d.type = 'western' AND d.name CONTAINS $name RETURN d.name AS name LIMIT 1",
                {"name": name}
            )
            if recs:
                return recs[0]["name"]
        return name

    def _narrative_for_syndrome(self, syndrome_name: str) -> dict:
        """分析特定证型的用药模式"""
        syndrome_name = self._normalize_syndrome_name(syndrome_name)

        # 基本统计
        stat_recs = neo4j_client.run("""
            MATCH (s:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)
            RETURN count(DISTINCT v) AS visit_count,
                   avg(v.length_of_stay) AS avg_los,
                   percentileCont(v.length_of_stay, 0.5) AS median_los
        """, {"name": syndrome_name})
        stats = dict(stat_recs[0]) if stat_recs else {}

        # Top 药品（全部）
        drug_recs = neo4j_client.run("""
            MATCH (s:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
            RETURN dr.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 20
        """, {"name": syndrome_name})
        top_drugs = [{"name": r["name"], "count": r["cnt"], "is_tcm": self._is_tcm_drug(r["name"])} for r in drug_recs]

        # Top 中药/中成药
        tcm_drugs = [d for d in top_drugs if d["is_tcm"]]
        wm_drugs = [d for d in top_drugs if not d["is_tcm"]]

        # 常见合并证型
        co_syndrome_recs = neo4j_client.run("""
            MATCH (s:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(co:Disease)
            WHERE co.name <> s.name AND (co.type = 'tcm' OR co.type = 'tcm_syndrome')
            RETURN co.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, {"name": syndrome_name})
        co_syndromes = [{"name": r["name"], "count": r["cnt"]} for r in co_syndrome_recs]

        # 常见西医疾病共现
        co_western_recs = neo4j_client.run("""
            MATCH (s:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(co:Disease)
            WHERE co.type = 'western'
            RETURN co.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 10
        """, {"name": syndrome_name})
        co_western = [{"name": r["name"], "count": r["cnt"]} for r in co_western_recs]

        # 药品组合对
        pair_recs = neo4j_client.run("""
            MATCH (s:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)-[:PRESCRIBED]->(dr:Drug)
            WITH v, collect(dr.name) AS drugs
            UNWIND drugs AS d1
            UNWIND drugs AS d2
            WITH d1, d2, count(*) AS pair_count WHERE d1 < d2
            RETURN d1, d2, pair_count ORDER BY pair_count DESC LIMIT 15
        """, {"name": syndrome_name})
        pairs = [{"drug1": r["d1"], "drug2": r["d2"], "count": r["pair_count"]} for r in pair_recs]

        data = {
            "type": "syndrome_drug",
            "syndrome_name": syndrome_name,
            "visit_count": stats.get("visit_count", 0),
            "avg_los": round(stats.get("avg_los", 0) or 0, 1),
            "median_los": round(stats.get("median_los", 0) or 0, 1),
            "top_drugs": top_drugs,
            "tcm_drugs": tcm_drugs,
            "western_drugs": wm_drugs,
            "co_syndromes": co_syndromes,
            "co_western_diseases": co_western,
            "common_pairs": pairs,
        }

        narrative = self._llm_generate_syndrome_narrative(data)
        return {**data, "narrative": narrative}

    def _narrative_for_disease_syndromes(self, western_disease: str) -> dict:
        """分析某西医疾病的中医证型分布和用药"""
        western_disease = self._normalize_western_disease(western_disease)

        # 证型分布
        syndrome_recs = neo4j_client.run("""
            MATCH (wd:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(s:Disease)
            WHERE s.type IN ['tcm', 'tcm_syndrome']
            RETURN s.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 15
        """, {"name": western_disease})
        syndromes = [{"name": r["name"], "count": r["cnt"]} for r in syndrome_recs]

        # 总就诊数
        total_recs = neo4j_client.run("""
            MATCH (wd:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)
            RETURN count(DISTINCT v) AS total
        """, {"name": western_disease})
        total_visits = dict(total_recs[0])["total"] if total_recs else 0

        # 中西医结合比例
        integrated_recs = neo4j_client.run("""
            MATCH (wd:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(s:Disease) WHERE s.type IN ['tcm', 'tcm_syndrome']
            WITH v, count(s) AS has_tcm
            RETURN sum(CASE WHEN has_tcm > 0 THEN 1 ELSE 0 END) AS integrated,
                   count(v) AS total
        """, {"name": western_disease})
        integrated = dict(integrated_recs[0]) if integrated_recs else {"integrated": 0, "total": 0}
        integrated_pct = round(integrated["integrated"] / integrated["total"] * 100, 1) if integrated["total"] else 0

        # 各证型常用中药
        syndrome_tcm_drugs = {}
        for syn in syndromes[:5]:
            syn_name = syn["name"]
            drug_recs = neo4j_client.run("""
                MATCH (wd:Disease {name: $disease})<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(s:Disease {name: $syndrome})
                MATCH (v)-[:PRESCRIBED]->(dr:Drug)
                RETURN dr.name AS name, count(DISTINCT v) AS cnt
                ORDER BY cnt DESC LIMIT 10
            """, {"disease": western_disease, "syndrome": syn_name})
            all_drugs = [{"name": r["name"], "count": r["cnt"], "is_tcm": self._is_tcm_drug(r["name"])} for r in drug_recs]
            tcm_only = [d for d in all_drugs if d["is_tcm"]]
            syndrome_tcm_drugs[syn_name] = tcm_only[:5]

        data = {
            "type": "disease_syndrome",
            "western_disease": western_disease,
            "total_visits": total_visits,
            "integrated_count": integrated["integrated"],
            "integrated_percentage": integrated_pct,
            "syndromes": syndromes,
            "syndrome_tcm_drugs": syndrome_tcm_drugs,
        }

        narrative = self._llm_generate_disease_syndrome_narrative(data)
        return {**data, "narrative": narrative}

    def _narrative_global_tcm_patterns(self) -> dict:
        """全局中医特色概览"""
        # Top 中医证型
        syndrome_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:DIAGNOSED_WITH]->(s:Disease)
            WHERE s.type IN ['tcm', 'tcm_syndrome']
            RETURN s.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 20
        """)
        top_syndromes = [{"name": r["name"], "count": r["cnt"]} for r in syndrome_recs]

        # Top 中药/中成药
        drug_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:PRESCRIBED]->(dr:Drug)
            RETURN dr.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 200
        """)
        tcm_drugs = []
        for r in drug_recs:
            if self._is_tcm_drug(r["name"]):
                tcm_drugs.append({"name": r["name"], "count": r["cnt"]})
            if len(tcm_drugs) >= 20:
                break

        # 中西医结合比例
        integrated_recs = neo4j_client.run("""
            MATCH (v:Visit)
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(w:Disease) WHERE w.type = 'western'
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(t:Disease) WHERE t.type IN ['tcm', 'tcm_syndrome']
            WITH v, count(w) AS has_w, count(t) AS has_t
            RETURN sum(CASE WHEN has_w > 0 AND has_t > 0 THEN 1 ELSE 0 END) AS integrated,
                   sum(CASE WHEN has_w > 0 THEN 1 ELSE 0 END) AS western_only,
                   sum(CASE WHEN has_t > 0 THEN 1 ELSE 0 END) AS tcm_only,
                   count(v) AS total
        """)
        integrated = dict(integrated_recs[0]) if integrated_recs else {}

        # 证型分布趋势（按年）
        trend_recs = neo4j_client.run("""
            MATCH (v:Visit)-[:DIAGNOSED_WITH]->(s:Disease)
            WHERE s.type IN ['tcm', 'tcm_syndrome']
            RETURN substring(v.admission_date, 0, 4) AS year, count(DISTINCT v) AS cnt
            ORDER BY year
        """)
        trend = [{"year": r["year"], "count": r["cnt"]} for r in trend_recs if r["year"]]

        data = {
            "type": "global_tcm",
            "top_syndromes": top_syndromes,
            "top_tcm_drugs": tcm_drugs,
            "integrated": integrated,
            "trend": trend,
        }

        narrative = self._llm_generate_global_tcm_narrative(data)
        return {**data, "narrative": narrative}

    def generate_integrated_comparison_narrative(self, western_disease: Optional[str] = None) -> dict:
        """
        中西医结合对比叙事
        对比：纯西医治疗 vs 西医+中医治疗的疗效指标
        """
        if western_disease:
            western_disease = self._normalize_western_disease(western_disease)

        # 构建基础match
        if western_disease:
            match_clause = "MATCH (wd:Disease {name: $disease})<-[:DIAGNOSED_WITH]-(v:Visit)"
            params = {"disease": western_disease}
        else:
            match_clause = "MATCH (v:Visit)"
            params = {}

        # 判断是否有中医参与
        query = f"""
            {match_clause}
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(t:Disease) WHERE t.type IN ['tcm', 'tcm_syndrome']
            OPTIONAL MATCH (v)-[:PRESCRIBED]->(dr:Drug)
            WITH v, count(DISTINCT t) AS tcm_count, collect(DISTINCT dr.name) AS drugs
            WITH v,
                 (tcm_count > 0) AS has_tcm_diagnosis,
                 any(d IN drugs WHERE {' OR '.join([f'd CONTAINS "{kw}"' for kw in self.TCM_DRUG_KEYWORDS[:10]])}) AS has_tcm_drug
            WITH v, (has_tcm_diagnosis OR has_tcm_drug) AS has_tcm
            RETURN has_tcm,
                   count(v) AS visit_count,
                   avg(v.length_of_stay) AS avg_los,
                   percentileCont(v.length_of_stay, 0.5) AS median_los,
                   avg(size([(v)-[:PRESCRIBED]->() | 1])) AS avg_drug_count
            ORDER BY has_tcm
        """
        # 简化：主要用中医诊断判断
        query = f"""
            {match_clause}
            OPTIONAL MATCH (v)-[:DIAGNOSED_WITH]->(t:Disease) WHERE t.type IN ['tcm', 'tcm_syndrome']
            WITH v, count(DISTINCT t) AS tcm_count
            WITH v, (tcm_count > 0) AS has_tcm
            RETURN has_tcm,
                   count(v) AS visit_count,
                   avg(v.length_of_stay) AS avg_los,
                   percentileCont(v.length_of_stay, 0.5) AS median_los
        """

        recs = neo4j_client.run(query, params)

        comparison = {}
        for r in recs:
            key = "integrated" if r["has_tcm"] else "western_only"
            comparison[key] = {
                "visit_count": r["visit_count"],
                "avg_los": round(r["avg_los"] or 0, 1),
                "median_los": round(r["median_los"] or 0, 1),
            }

        # 中药使用情况
        tcm_drug_query = f"""
            {match_clause}
            MATCH (v)-[:DIAGNOSED_WITH]->(t:Disease) WHERE t.type IN ['tcm', 'tcm_syndrome']
            MATCH (v)-[:PRESCRIBED]->(dr:Drug)
            RETURN dr.name AS name, count(DISTINCT v) AS cnt
            ORDER BY cnt DESC LIMIT 15
        """
        tcm_drug_recs = neo4j_client.run(tcm_drug_query, params)
        integrated_drugs = [{"name": r["name"], "count": r["cnt"], "is_tcm": self._is_tcm_drug(r["name"])} for r in tcm_drug_recs]

        data = {
            "type": "integrated_comparison",
            "western_disease": western_disease,
            "comparison": comparison,
            "integrated_drugs": integrated_drugs,
        }

        narrative = self._llm_generate_comparison_narrative(data)
        return {**data, "narrative": narrative}

    def generate_syndrome_trend_narrative(self, syndrome_name: Optional[str] = None,
                                           western_disease: Optional[str] = None) -> dict:
        """
        证型分布趋势叙事
        分析证型或疾病的年度/月度分布变化
        """
        params = {}
        if syndrome_name:
            syndrome_name = self._normalize_syndrome_name(syndrome_name)
            match_clause = "MATCH (s:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)"
            params["name"] = syndrome_name
            title_key = syndrome_name
        elif western_disease:
            western_disease = self._normalize_western_disease(western_disease)
            match_clause = "MATCH (wd:Disease {name: $name})<-[:DIAGNOSED_WITH]-(v:Visit)-[:DIAGNOSED_WITH]->(s:Disease) WHERE s.type IN ['tcm', 'tcm_syndrome']"
            params["name"] = western_disease
            title_key = western_disease
        else:
            match_clause = "MATCH (v:Visit)-[:DIAGNOSED_WITH]->(s:Disease) WHERE s.type IN ['tcm', 'tcm_syndrome']"
            title_key = "全局"

        # 年度趋势
        year_query = f"""
            {match_clause}
            RETURN substring(v.admission_date, 0, 4) AS year, s.name AS syndrome, count(DISTINCT v) AS cnt
            ORDER BY year, cnt DESC
        """
        # 如果全局或无特定证型，需要group by syndrome
        if syndrome_name:
            year_query = f"""
                {match_clause}
                RETURN substring(v.admission_date, 0, 4) AS year, count(DISTINCT v) AS cnt
                ORDER BY year
            """
            year_recs = neo4j_client.run(year_query, params)
            year_trend = [{"year": r["year"], "count": r["cnt"]} for r in year_recs if r["year"]]
            syndrome_trend = {}
        else:
            year_recs = neo4j_client.run(year_query, params)
            year_trend = []
            syndrome_trend = {}
            current_year = None
            year_count = 0
            for r in year_recs:
                if not r["year"]:
                    continue
                if r["year"] != current_year:
                    if current_year:
                        year_trend.append({"year": current_year, "count": year_count})
                    current_year = r["year"]
                    year_count = 0
                year_count += r["cnt"]
                syn = r["syndrome"]
                if syn:
                    syndrome_trend.setdefault(r["year"], []).append({"syndrome": syn, "count": r["cnt"]})
            if current_year:
                year_trend.append({"year": current_year, "count": year_count})

        # 季度趋势
        quarter_query = f"""
            {match_clause}
            RETURN substring(v.admission_date, 0, 4) + '-Q' + CASE WHEN substring(v.admission_date, 5, 2) IN ['01','02','03'] THEN '1' WHEN substring(v.admission_date, 5, 2) IN ['04','05','06'] THEN '2' WHEN substring(v.admission_date, 5, 2) IN ['07','08','09'] THEN '3' ELSE '4' END AS quarter,
                   count(DISTINCT v) AS cnt
            ORDER BY quarter
        """
        if not syndrome_name:
            quarter_query = f"""
                {match_clause}
                RETURN substring(v.admission_date, 0, 4) + '-Q' + CASE WHEN substring(v.admission_date, 5, 2) IN ['01','02','03'] THEN '1' WHEN substring(v.admission_date, 5, 2) IN ['04','05','06'] THEN '2' WHEN substring(v.admission_date, 5, 2) IN ['07','08','09'] THEN '3' ELSE '4' END AS quarter,
                       count(DISTINCT v) AS cnt
                ORDER BY quarter
            """
        quarter_recs = neo4j_client.run(quarter_query, params)
        quarter_trend = [{"quarter": r["quarter"], "count": r["cnt"]} for r in quarter_recs if r["quarter"]]

        data = {
            "type": "syndrome_trend",
            "title_key": title_key,
            "year_trend": year_trend,
            "quarter_trend": quarter_trend,
            "syndrome_trend": syndrome_trend,
        }

        narrative = self._llm_generate_trend_narrative(data)
        return {**data, "narrative": narrative}

    # ========== LLM 叙事生成 ==========

    def _call_llm(self, system: str, user: str, cache_namespace: str = "tcm:general") -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return llm_service.chat(messages, temperature=0.4, max_tokens=2500, cache_namespace=cache_namespace)

    def _llm_generate_syndrome_narrative(self, data: dict) -> str:
        system = (
            "你是一位资深的中医临床数据分析专家。请基于提供的中医证型-用药统计数据，"
            "生成结构化、专业的中医特色叙事分析。要求：1) 区分中药/中成药与西药；"
            "2) 分析用药组合的中医治则治法意义；3) 指出中西医结合特点；"
            "4) 语言专业、简洁，中文输出。"
        )
        user = self._format_data_for_prompt(data)
        return self._call_llm(system, user, cache_namespace=f"tcm:syndrome:{data.get('syndrome_name', 'unknown')}")

    def _llm_generate_disease_syndrome_narrative(self, data: dict) -> str:
        system = (
            "你是一位中西医结合临床专家。请基于某西医疾病的中医证型分布数据，"
            "分析该疾病在中医辨证分型上的特点、各证型的用药规律，以及中西医结合治疗比例。"
            "中文输出，专业简洁。"
        )
        user = self._format_data_for_prompt(data)
        return self._call_llm(system, user, cache_namespace=f"tcm:disease_syndrome:{data.get('western_disease', 'unknown')}")

    def _llm_generate_global_tcm_narrative(self, data: dict) -> str:
        system = (
            "你是一位医院中医药管理专家。请基于全局中医特色统计数据，"
            "生成本科室中医药应用概况叙事，包括：常见证型、常用中药/中成药、"
            "中西医结合比例、证型就诊趋势等。中文输出。"
        )
        user = self._format_data_for_prompt(data)
        return self._call_llm(system, user, cache_namespace="tcm:global")

    def _llm_generate_comparison_narrative(self, data: dict) -> str:
        system = (
            "你是一位循证医学与中医药结合研究专家。请基于中西医结合对比数据，"
            "客观分析中西医结合治疗与纯西医治疗在住院天数等指标上的差异。"
            "注意：不要做出没有数据支持的疗效判断，仅描述观察到的统计差异。"
            "中文输出。"
        )
        user = self._format_data_for_prompt(data)
        return self._call_llm(system, user, cache_namespace="tcm:comparison")

    def _llm_generate_trend_narrative(self, data: dict) -> str:
        system = (
            "你是一位中医流行病学分析专家。请基于证型分布的时间序列数据，"
            "分析证型就诊的季节性、年度变化趋势，并给出合理的临床解释。"
            "中文输出。"
        )
        user = self._format_data_for_prompt(data)
        return self._call_llm(system, user, cache_namespace=f"tcm:trend:{data.get('title_key', 'unknown')}")

    def _format_data_for_prompt(self, data: dict) -> str:
        lines = [f"分析类型: {data.get('type')}"]

        if "syndrome_name" in data:
            lines.append(f"证型: {data['syndrome_name']}")
        if "western_disease" in data:
            lines.append(f"西医疾病: {data['western_disease']}")
        if "title_key" in data:
            lines.append(f"分析对象: {data['title_key']}")

        if "visit_count" in data:
            lines.append(f"相关就诊次数: {data['visit_count']}")
        if "avg_los" in data and data["avg_los"]:
            lines.append(f"平均住院天数: {data['avg_los']}")
        if "median_los" in data and data["median_los"]:
            lines.append(f"中位住院天数: {data['median_los']}")

        if data.get("top_drugs"):
            lines.append("\nTop 药品:")
            for d in data["top_drugs"][:15]:
                tag = "[中药]" if d["is_tcm"] else "[西药]"
                lines.append(f"  - {d['name']} {tag}: {d['count']}次")

        if data.get("tcm_drugs"):
            lines.append("\n常用中药/中成药:")
            for d in data["tcm_drugs"][:10]:
                lines.append(f"  - {d['name']}: {d['count']}次")

        if data.get("western_drugs"):
            lines.append("\n常用西药:")
            for d in data["western_drugs"][:10]:
                lines.append(f"  - {d['name']}: {d['count']}次")

        if data.get("syndromes"):
            lines.append("\n中医证型分布:")
            for s in data["syndromes"][:10]:
                pct = round(s["count"] / data.get("total_visits", 1) * 100, 1) if data.get("total_visits") else 0
                lines.append(f"  - {s['name']}: {s['count']}次 ({pct}%)")

        if data.get("syndrome_tcm_drugs"):
            lines.append("\n各证型常用中药:")
            for syn, drugs in data["syndrome_tcm_drugs"].items():
                drug_str = ", ".join([f"{d['name']}({d['count']}次)" for d in drugs])
                lines.append(f"  - {syn}: {drug_str}")

        if data.get("common_pairs"):
            lines.append("\n常见药品组合:")
            for p in data["common_pairs"][:10]:
                lines.append(f"  - {p['drug1']} + {p['drug2']}: {p['count']}次")

        if data.get("co_syndromes"):
            lines.append("\n常见合并证型:")
            for s in data["co_syndromes"][:8]:
                lines.append(f"  - {s['name']}: {s['count']}次")

        if data.get("co_western_diseases"):
            lines.append("\n常见共现西医疾病:")
            for d in data["co_western_diseases"][:8]:
                lines.append(f"  - {d['name']}: {d['count']}次")

        if data.get("comparison"):
            lines.append("\n中西医结合对比:")
            for key, val in data["comparison"].items():
                label = "中西医结合组" if key == "integrated" else "纯西医组"
                lines.append(f"  - {label}: {val['visit_count']}例, 平均住院{val['avg_los']}天, 中位住院{val['median_los']}天")

        if data.get("integrated"):
            lines.append("\n全局中西医结合统计:")
            ig = data["integrated"]
            total = ig.get("total", 0)
            lines.append(f"  - 总就诊: {total}")
            lines.append(f"  - 中西医结合: {ig.get('integrated', 0)}")
            lines.append(f"  - 纯西医: {ig.get('western_only', 0)}")
            lines.append(f"  - 纯中医: {ig.get('tcm_only', 0)}")

        if data.get("year_trend"):
            lines.append("\n年度趋势:")
            for y in data["year_trend"]:
                lines.append(f"  - {y['year']}: {y['count']}次")

        if data.get("quarter_trend"):
            lines.append("\n季度趋势:")
            for q in data["quarter_trend"]:
                lines.append(f"  - {q['quarter']}: {q['count']}次")

        return "\n".join(lines)


# 全局单例
tcm_narrative_service = TCMNarrativeService()
