"""数据挖掘类算子：频繁项集、关联规则、相似项、共现网络、异常检测。"""
from collections import Counter

import numpy as np
import pandas as pd

from services.research.dataset_service import dataset_service
from services.research.skills.base import (
    BaseSkill, SkillMeta, make_result, bar_option, scatter_option, graph_option,
)

# 事务集最大项数（限制 one-hot 矩阵规模，保证 apriori 性能）
MAX_ITEMS = 200


def _get_transactions(item_set: str, min_freq: int = 5) -> tuple[list[list[str]], str]:
    """从就诊宽表构建事务集，返回 (事务列表, 项目类型中文名)"""
    visits = dataset_service.build_visit_matrix()
    col = "diagnoses" if item_set == "diagnoses" else "drugs"
    label = "诊断" if item_set == "diagnoses" else "用药"

    counter = Counter(x for items in visits[col] for x in items)
    keep_items = {x for x, c in counter.items() if c >= min_freq}
    keep_items = {x for x, _ in counter.most_common(MAX_ITEMS) if x in keep_items}

    transactions = [
        [x for x in dict.fromkeys(items) if x in keep_items]
        for items in visits[col]
    ]
    transactions = [t for t in transactions if t]
    return transactions, label


def _transactions_to_onehot(transactions: list[list[str]]) -> pd.DataFrame:
    from mlxtend.preprocessing import TransactionEncoder
    te = TransactionEncoder()
    arr = te.fit(transactions).transform(transactions)
    return pd.DataFrame(arr, columns=te.columns_)


class FrequentItemsetsSkill(BaseSkill):
    meta = SkillMeta(
        id="frequent_itemsets",
        name="频繁项集挖掘",
        category="数据挖掘",
        description="基于 Apriori 算法挖掘诊断或用药的频繁共现组合",
        params_schema=[
            {"name": "item_set", "label": "事务集", "type": "select",
             "default": "diagnoses", "options": ["diagnoses", "drugs"],
             "description": "以同一就诊的诊断集合或用药集合作为事务"},
            {"name": "min_support", "label": "最小支持度", "type": "number",
             "default": 0.05, "min": 0.001, "max": 1,
             "description": "项集在全部事务中出现的最小比例"},
            {"name": "max_len", "label": "最大项集长度", "type": "number",
             "default": 3, "min": 1, "max": 5},
        ],
        data_requirements="就诊级诊断/用药清单",
    )

    def run(self, params: dict) -> dict:
        item_set = self.get_param(params, "item_set")
        min_support = float(self.get_param(params, "min_support"))
        max_len = int(self.get_param(params, "max_len"))

        transactions, label = _get_transactions(item_set)
        if len(transactions) < 50:
            return make_result(f"含{label}信息的有效就诊事务不足 50 条，无法挖掘频繁项集。")

        from mlxtend.frequent_patterns import apriori
        onehot = _transactions_to_onehot(transactions)
        freq = apriori(onehot, min_support=min_support, use_colnames=True, max_len=max_len, low_memory=True)
        if freq.empty:
            return make_result(
                f"在最小支持度 {min_support} 下未发现任何频繁{label}组合，建议调低最小支持度后重试。"
            )

        freq = freq.sort_values("support", ascending=False)
        freq["itemsets_str"] = freq["itemsets"].apply(lambda s: " + ".join(sorted(s)))
        top = freq.head(20)

        tables = [{
            "title": f"频繁{label}组合 Top{len(top)}",
            "columns": ["项集", "支持度", "出现就诊数"],
            "rows": [[r["itemsets_str"], round(r["support"], 4), int(r["support"] * len(transactions))]
                     for _, r in top.iterrows()],
        }]
        charts = [{"title": f"频繁{label}组合支持度", "option": bar_option(
            f"频繁{label}组合 Top{len(top)}（支持度）",
            top["itemsets_str"].tolist(), [round(v, 4) for v in top["support"]], "", "支持度")}]

        summary = (
            f"在 {len(transactions)} 条有效就诊事务中，以最小支持度 {min_support} 挖掘出 "
            f"{len(freq)} 个频繁{label}组合；支持度最高的是「{top.iloc[0]['itemsets_str']}」"
            f"（支持度 {top.iloc[0]['support']:.2%}）。"
        )
        facts = {
            "transaction_count": len(transactions),
            "itemset_count": len(freq),
            "min_support": min_support,
            "top_itemsets": top[["itemsets_str", "support"]].head(10).to_dict("records"),
        }
        return make_result(summary, tables, charts, facts)


class AssociationRulesSkill(BaseSkill):
    meta = SkillMeta(
        id="association_rules",
        name="关联规则挖掘",
        category="数据挖掘",
        description="挖掘合并症/用药关联规则，按支持度/置信度/提升度排序（默认场景：合并症关联）",
        params_schema=[
            {"name": "item_set", "label": "事务集", "type": "select",
             "default": "diagnoses", "options": ["diagnoses", "drugs"],
             "description": "diagnoses=合并症关联（同一就诊的诊断集合），drugs=联合用药关联"},
            {"name": "min_support", "label": "最小支持度", "type": "number",
             "default": 0.02, "min": 0.001, "max": 1},
            {"name": "min_confidence", "label": "最小置信度", "type": "number",
             "default": 0.5, "min": 0.05, "max": 1},
            {"name": "top_n", "label": "输出条数", "type": "number",
             "default": 20, "min": 5, "max": 100},
        ],
        data_requirements="就诊级诊断/用药清单",
    )

    def run(self, params: dict) -> dict:
        item_set = self.get_param(params, "item_set")
        min_support = float(self.get_param(params, "min_support"))
        min_confidence = float(self.get_param(params, "min_confidence"))
        top_n = int(self.get_param(params, "top_n"))

        transactions, label = _get_transactions(item_set)
        if len(transactions) < 50:
            return make_result(f"含{label}信息的有效就诊事务不足 50 条，无法挖掘关联规则。")

        from mlxtend.frequent_patterns import apriori, association_rules
        onehot = _transactions_to_onehot(transactions)
        freq = apriori(onehot, min_support=min_support, use_colnames=True, max_len=3, low_memory=True)
        if freq.empty or len(freq) < 2:
            return make_result(
                f"在最小支持度 {min_support} 下频繁项集过少，无法生成关联规则，建议调低最小支持度。"
            )

        rules = association_rules(freq, metric="confidence", min_threshold=min_confidence)
        if rules.empty:
            return make_result(
                f"在最小置信度 {min_confidence} 下未发现满足条件的{label}关联规则，建议调低阈值。"
            )

        rules = rules.sort_values("lift", ascending=False).head(top_n)
        rows = []
        for _, r in rules.iterrows():
            rows.append([
                " + ".join(sorted(r["antecedents"])),
                " + ".join(sorted(r["consequents"])),
                round(r["support"], 4),
                round(r["confidence"], 3),
                round(r["lift"], 2),
            ])

        tables = [{
            "title": f"{label}关联规则 Top{len(rows)}（按提升度排序）",
            "columns": ["前项", "后项", "支持度", "置信度", "提升度"],
            "rows": rows,
        }]
        charts = [{"title": "关联规则提升度", "option": bar_option(
            f"{label}关联规则提升度 Top{len(rows)}",
            [f"{r[0]}→{r[1]}" for r in rows], [r[4] for r in rows], "", "提升度")}]

        best = rules.iloc[0]
        summary = (
            f"基于 {len(transactions)} 条就诊事务挖掘出 {len(rules)} 条{label}关联规则"
            f"（支持度≥{min_support}，置信度≥{min_confidence}）。"
            f"提升度最高的规则为「{' + '.join(sorted(best['antecedents']))} → "
            f"{' + '.join(sorted(best['consequents']))}」，置信度 {best['confidence']:.1%}，"
            f"提升度 {best['lift']:.2f}，提示两者存在显著共现关联（统计关联，非因果关系）。"
        )
        facts = {
            "rule_count": len(rules),
            "top_rules": [
                {"antecedents": r[0], "consequents": r[1], "support": r[2],
                 "confidence": r[3], "lift": r[4]}
                for r in rows[:10]
            ],
        }
        return make_result(summary, tables, charts, facts)


class SimilarItemsSkill(BaseSkill):
    meta = SkillMeta(
        id="similar_items",
        name="相似患者/共现疾病检索",
        category="数据挖掘",
        description="基于 Jaccard 相似度，输入患者ID找相似患者，或输入疾病名找共现疾病 Top10",
        params_schema=[
            {"name": "target_type", "label": "目标类型", "type": "select",
             "default": "patient", "options": ["patient", "disease"]},
            {"name": "target", "label": "目标值", "type": "string",
             "default": "", "description": "患者ID 或疾病名称"},
            {"name": "top_n", "label": "返回数量", "type": "number",
             "default": 10, "min": 3, "max": 50},
        ],
        data_requirements="就诊级诊断清单",
    )

    def run(self, params: dict) -> dict:
        target_type = self.get_param(params, "target_type")
        target = str(self.get_param(params, "target") or "").strip()
        top_n = int(self.get_param(params, "top_n"))
        if not target:
            return make_result("请先填写目标值（患者ID 或疾病名称）。")

        visits = dataset_service.build_visit_matrix()

        # 患者 -> 诊断集合（跨就诊聚合）
        patient_diags = visits.groupby("patient_id")["diagnoses"].apply(
            lambda ds: set(x for d in ds for x in d)
        )

        if target_type == "patient":
            if target not in patient_diags.index:
                return make_result(f"未找到患者 {target} 的诊断记录，请确认患者ID是否正确。")
            target_set = patient_diags[target]
            if not target_set:
                return make_result(f"患者 {target} 无有效出院诊断，无法计算相似患者。")

            sims = []
            for pid, dset in patient_diags.items():
                if pid == target or not dset:
                    continue
                union = target_set | dset
                sim = len(target_set & dset) / len(union) if union else 0
                if sim > 0:
                    sims.append((pid, sim, sorted(target_set & dset)))
            sims.sort(key=lambda x: x[1], reverse=True)
            top = sims[:top_n]
            if not top:
                return make_result(f"未找到与患者 {target} 有共同诊断的其他患者。")

            tables = [{
                "title": f"与患者 {target} 最相似的患者 Top{len(top)}",
                "columns": ["患者ID", "Jaccard相似度", "共同诊断"],
                "rows": [[pid, round(sim, 3), "、".join(common[:5])] for pid, sim, common in top],
            }]
            charts = [{"title": "相似患者相似度", "option": bar_option(
                f"与 {target} 的 Jaccard 相似度",
                [pid for pid, _, _ in top], [round(s, 3) for _, s, _ in top], "", "相似度")}]
            summary = (
                f"患者 {target} 的诊断集合包含 {len(target_set)} 种疾病；"
                f"最相似的患者为 {top[0][0]}（Jaccard 相似度 {top[0][1]:.2f}，"
                f"共同诊断：{'、'.join(top[0][2][:3])}）。"
            )
            facts = {"target_patient": target, "target_diagnoses": sorted(target_set),
                     "similar": [{"patient_id": p, "similarity": s} for p, s, _ in top]}
            return make_result(summary, tables, charts, facts)

        # disease：疾病间 Jaccard（以就诊为共现单位）
        disease_visits: dict[str, set] = {}
        for visit_no, diags in zip(visits["visit_no"], visits["diagnoses"]):
            for d in diags:
                disease_visits.setdefault(d, set()).add(visit_no)

        if target not in disease_visits:
            close = [d for d in disease_visits if target in d][:5]
            hint = f"，您是否指：{'、'.join(close)}" if close else ""
            return make_result(f"未找到疾病「{target}」的记录{hint}。")

        target_set = disease_visits[target]
        sims = []
        for d, vset in disease_visits.items():
            if d == target:
                continue
            union = target_set | vset
            sim = len(target_set & vset) / len(union) if union else 0
            if sim > 0:
                sims.append((d, sim, len(target_set & vset)))
        sims.sort(key=lambda x: x[1], reverse=True)
        top = sims[:top_n]
        if not top:
            return make_result(f"疾病「{target}」未发现显著共现疾病。")

        tables = [{
            "title": f"与「{target}」共现最强的疾病 Top{len(top)}",
            "columns": ["疾病", "Jaccard相似度", "共现就诊数"],
            "rows": [[d, round(s, 3), c] for d, s, c in top],
        }]
        charts = [{"title": "共现疾病相似度", "option": bar_option(
            f"与「{target}」的共现 Jaccard 相似度",
            [d for d, _, _ in top], [round(s, 3) for _, s, _ in top], "", "相似度")}]
        summary = (
            f"疾病「{target}」出现在 {len(target_set)} 次就诊中；"
            f"共现最强的疾病为「{top[0][0]}」（Jaccard {top[0][1]:.2f}，共现 {top[0][2]} 次就诊）。"
        )
        facts = {"target_disease": target, "visit_count": len(target_set),
                 "cooccurring": [{"disease": d, "similarity": s, "co_visits": c} for d, s, c in top]}
        return make_result(summary, tables, charts, facts)


class CooccurrenceNetworkSkill(BaseSkill):
    meta = SkillMeta(
        id="cooccurrence_network",
        name="疾病共现网络",
        category="数据挖掘",
        description="构建疾病共现网络，取共现强度 Top50 边绘制关系图",
        params_schema=[
            {"name": "top_edges", "label": "边数量", "type": "number",
             "default": 50, "min": 10, "max": 200},
        ],
        data_requirements="就诊级诊断清单",
    )

    def run(self, params: dict) -> dict:
        top_edges = int(self.get_param(params, "top_edges"))
        visits = dataset_service.build_visit_matrix()

        pair_counter: Counter = Counter()
        node_counter: Counter = Counter()
        for diags in visits["diagnoses"]:
            uniq = sorted(set(diags))
            node_counter.update(uniq)
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    pair_counter[(uniq[i], uniq[j])] += 1

        if not pair_counter:
            return make_result("诊断数据不足，无法构建共现网络。")

        edges = pair_counter.most_common(top_edges)
        used_nodes = {n for e, _ in edges for n in e}
        nodes = [
            {"name": n, "value": node_counter[n],
             "symbolSize": max(10, min(50, np.sqrt(node_counter[n]) * 2))}
            for n in used_nodes
        ]
        links = [{"source": a, "target": b, "value": c} for (a, b), c in edges]

        charts = [{"title": "疾病共现网络", "option": graph_option(
            f"疾病共现网络（Top{len(edges)} 条边）", nodes, links)}]

        tables = [{
            "title": "共现强度最高的疾病对",
            "columns": ["疾病A", "疾病B", "共现就诊数"],
            "rows": [[a, b, c] for (a, b), c in edges[:20]],
        }]

        strongest = edges[0]
        summary = (
            f"共现网络包含 {len(used_nodes)} 种疾病、{len(edges)} 条共现边；"
            f"共现最强的疾病对为「{strongest[0][0]} — {strongest[0][1]}」，"
            f"共同出现在 {strongest[1]} 次就诊中。"
        )
        facts = {
            "node_count": len(used_nodes),
            "edge_count": len(edges),
            "top_pairs": [{"a": a, "b": b, "co_visits": c} for (a, b), c in edges[:10]],
        }
        return make_result(summary, tables, charts, facts)


class AnomalyDetectionSkill(BaseSkill):
    meta = SkillMeta(
        id="anomaly_detection",
        name="异常就诊检测",
        category="数据挖掘",
        description="住院天数 IQR 异常 + IsolationForest 多维异常（年龄/住院天数/检验特征），散点图展示",
        params_schema=[
            {"name": "contamination", "label": "异常比例", "type": "number",
             "default": 0.02, "min": 0.005, "max": 0.2,
             "description": "IsolationForest 预期异常样本占比"},
        ],
        data_requirements="就诊级宽表（年龄/住院天数/检验特征）",
    )

    def run(self, params: dict) -> dict:
        contamination = float(self.get_param(params, "contamination"))
        visits = dataset_service.build_visit_matrix()

        # IQR 住院天数异常
        los = visits["length_of_stay"].dropna()
        q1, q3 = los.quantile(0.25), los.quantile(0.75)
        iqr_upper = q3 + 1.5 * (q3 - q1)
        iqr_outliers = visits[visits["length_of_stay"] > iqr_upper]

        # IsolationForest 多维异常
        feature_cols = ["age_years", "length_of_stay"] + \
            [c for c in visits.columns if c.startswith("lab_")]
        feat = visits[["visit_no"] + feature_cols].dropna()
        iso_flags = pd.Series(False, index=visits.index)
        iso_count = 0
        if len(feat) >= 200 and len(feature_cols) >= 2:
            from sklearn.ensemble import IsolationForest
            X = feat[feature_cols].values
            model = IsolationForest(contamination=contamination, random_state=42)
            preds = model.fit_predict(X)
            iso_flags.loc[feat.index[preds == -1]] = True
            iso_count = int((preds == -1).sum())

        visits = visits.copy()
        visits["is_anomaly"] = (visits["length_of_stay"] > iqr_upper) | iso_flags

        # 散点图（抽样避免点过多）
        plot_df = visits.dropna(subset=["age_years", "length_of_stay"])
        if len(plot_df) > 3000:
            plot_df = plot_df.sample(3000, random_state=42)
        normal_pts = plot_df[~plot_df["is_anomaly"]][["age_years", "length_of_stay"]].values.tolist()
        anomaly_pts = plot_df[plot_df["is_anomaly"]][["age_years", "length_of_stay"]].values.tolist()

        option = scatter_option("年龄-住院天数异常检测", [], "年龄（岁）", "住院天数")
        option["series"] = [
            {"name": "正常", "type": "scatter", "data": normal_pts,
             "symbolSize": 5, "itemStyle": {"color": "#5470c6", "opacity": 0.4}},
            {"name": "异常", "type": "scatter", "data": anomaly_pts,
             "symbolSize": 8, "itemStyle": {"color": "#ee6666", "opacity": 0.8}},
        ]
        option["legend"] = {"top": "bottom"}

        top_los = iqr_outliers.nlargest(10, "length_of_stay")
        tables = [{
            "title": "住院天数最长的异常就诊 Top10",
            "columns": ["就诊流水号", "患者ID", "年龄(岁)", "住院天数"],
            "rows": [[r["visit_no"], r["patient_id"], round(r["age_years"], 1), int(r["length_of_stay"])]
                     for _, r in top_los.iterrows()],
        }]

        summary = (
            f"IQR 规则（上界 {iqr_upper:.0f} 天）识别出 {len(iqr_outliers)} 次超长住院就诊；"
            f"IsolationForest（异常比例 {contamination}）在 {len(feat)} 条完整特征样本中标记 {iso_count} 次多维异常；"
            f"合并后异常就诊共 {int(visits['is_anomaly'].sum())} 次，建议结合病历人工复核。"
        )
        facts = {
            "iqr_upper_bound": float(iqr_upper),
            "iqr_outlier_count": len(iqr_outliers),
            "isolation_forest_count": iso_count,
            "total_anomaly_count": int(visits["is_anomaly"].sum()),
        }
        return make_result(summary, tables, charts=[{"title": "异常检测散点图", "option": option}], facts=facts)


frequent_itemsets_skill = FrequentItemsetsSkill()
association_rules_skill = AssociationRulesSkill()
similar_items_skill = SimilarItemsSkill()
cooccurrence_network_skill = CooccurrenceNetworkSkill()
anomaly_detection_skill = AnomalyDetectionSkill()
