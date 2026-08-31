"""统计分析类算子：描述性统计、组间比较、相关分析。"""
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from services.research.dataset_service import dataset_service
from services.research.skills.base import (
    BaseSkill, SkillMeta, make_result, bar_option, heatmap_option,
)

NUMERIC_BASE_COLS = ["age_years", "length_of_stay"]


def _numeric_columns(visits: pd.DataFrame) -> list[str]:
    """可用于统计的数值列：年龄/住院天数 + 覆盖率达标的检验特征"""
    cols = list(NUMERIC_BASE_COLS)
    for c in visits.columns:
        if c.startswith("lab_") and visits[c].notna().mean() >= 0.05:
            cols.append(c)
    return [c for c in cols if visits[c].notna().sum() > 30]


class DescriptiveStatsSkill(BaseSkill):
    meta = SkillMeta(
        id="descriptive_stats",
        name="描述性统计",
        category="统计分析",
        description="数值列的均值/中位数/标准差/分位数统计表 + 分布直方图",
        params_schema=[],
        data_requirements="就诊级宽表（年龄/住院天数/检验特征）",
    )

    def run(self, params: dict) -> dict:
        visits = dataset_service.build_visit_matrix()
        cols = _numeric_columns(visits)
        if not cols:
            return make_result("可用的数值列不足，无法进行描述性统计。")

        rows = []
        for c in cols:
            s = visits[c].dropna()
            rows.append([
                c, len(s), round(s.mean(), 2), round(s.median(), 2),
                round(s.std(), 2), round(s.quantile(0.25), 2), round(s.quantile(0.75), 2),
                round(s.min(), 2), round(s.max(), 2),
            ])

        tables = [{
            "title": "数值列描述性统计",
            "columns": ["变量", "N", "均值", "中位数", "标准差", "P25", "P75", "最小值", "最大值"],
            "rows": rows,
        }]

        charts = []
        for c in ["age_years", "length_of_stay"]:
            if c in cols:
                s = visits[c].dropna()
                counts, edges = np.histogram(s, bins=20)
                x_labels = [f"{edges[i]:.0f}-{edges[i+1]:.0f}" for i in range(len(counts))]
                label = "年龄（岁）" if c == "age_years" else "住院天数（天）"
                charts.append({"title": f"{label}分布", "option": bar_option(
                    f"{label}分布直方图", x_labels, counts.tolist(), label, "人次")})

        los = visits["length_of_stay"].dropna()
        summary = (
            f"共统计 {len(cols)} 个数值变量；年龄均值 {visits['age_years'].mean():.1f} 岁，"
            f"住院天数均值 {los.mean():.1f} 天（中位数 {los.median():.0f} 天，"
            f"P25-P75：{los.quantile(0.25):.0f}-{los.quantile(0.75):.0f} 天），"
            "分布右偏明显，报告中位数比均值更有代表性。"
        )
        facts = {
            "numeric_columns": cols,
            "age_mean": float(visits["age_years"].mean()),
            "los_mean": float(los.mean()),
            "los_median": float(los.median()),
            "los_iqr": [float(los.quantile(0.25)), float(los.quantile(0.75))],
        }
        return make_result(summary, tables, charts, facts)


class GroupComparisonSkill(BaseSkill):
    meta = SkillMeta(
        id="group_comparison",
        name="组间比较",
        category="统计分析",
        description="按分组变量比较：数值列正态性检验后 t 检验/Mann-Whitney，分类列卡方检验，输出 p 值表",
        params_schema=[
            {"name": "group_col", "label": "分组变量", "type": "select",
             "default": "is_readmission",
             "options": ["is_readmission", "is_long_stay", "had_surgery"]},
        ],
        data_requirements="就诊级宽表",
    )

    def run(self, params: dict) -> dict:
        group_col = self.get_param(params, "group_col")
        visits = dataset_service.build_visit_matrix()
        if group_col not in visits.columns or visits[group_col].nunique() < 2:
            return make_result(f"分组变量 {group_col} 不可用或只有一个分组，无法进行组间比较。")

        groups = sorted(visits[group_col].unique())
        g0 = visits[visits[group_col] == groups[0]]
        g1 = visits[visits[group_col] == groups[1]]
        group_label = {True: "是", False: "否"}

        # 数值列比较
        rows = []
        for c in _numeric_columns(visits):
            s0, s1 = g0[c].dropna(), g1[c].dropna()
            if len(s0) < 30 or len(s1) < 30:
                continue
            # 正态性（大样本用 normaltest 近似判断，抽样 5000 避免 shapiro 限制）
            try:
                normal = all(
                    scipy_stats.normaltest(s.sample(min(5000, len(s)), random_state=42)).pvalue > 0.05
                    for s in (s0, s1)
                )
            except Exception:
                normal = False
            if normal:
                stat, p = scipy_stats.ttest_ind(s0, s1, equal_var=False)
                method = "Welch t 检验"
            else:
                stat, p = scipy_stats.mannwhitneyu(s0, s1, alternative="two-sided")
                method = "Mann-Whitney U"
            rows.append([
                c, method,
                f"{s0.median():.2f} / {s0.mean():.2f}",
                f"{s1.median():.2f} / {s1.mean():.2f}",
                round(float(stat), 2),
                f"{p:.2e}" if p < 0.001 else round(float(p), 4),
                "是" if p < 0.05 else "否",
            ])

        # 分类列比较：出院结局 + Top5 诊断
        cat_rows = []
        outcome_ct = pd.crosstab(visits[group_col], visits["outcome"])
        outcome_ct = outcome_ct.loc[:, outcome_ct.sum() >= 5]
        if outcome_ct.shape[1] >= 2:
            chi2, p, _, _ = scipy_stats.chi2_contingency(outcome_ct)
            cat_rows.append(["出院结局", round(float(chi2), 2),
                             f"{p:.2e}" if p < 0.001 else round(float(p), 4),
                             "是" if p < 0.05 else "否"])

        top_diags = pd.Series([d for ds in visits["diagnoses"] for d in ds]).value_counts().head(5).index
        for d in top_diags:
            flag = visits["diagnoses"].apply(lambda ds: d in ds)
            ct = pd.crosstab(visits[group_col], flag)
            if ct.shape == (2, 2):
                chi2, p, _, _ = scipy_stats.chi2_contingency(ct)
                cat_rows.append([f"诊断:{d}", round(float(chi2), 2),
                                 f"{p:.2e}" if p < 0.001 else round(float(p), 4),
                                 "是" if p < 0.05 else "否"])

        tables = [
            {"title": f"按 {group_col} 分组的数值变量比较",
             "columns": ["变量", "检验方法", f"{group_label.get(groups[0], groups[0])}组(中位数/均值)",
                         f"{group_label.get(groups[1], groups[1])}组(中位数/均值)", "统计量", "p值", "显著(p<0.05)"],
             "rows": rows},
            {"title": "分类变量卡方检验",
             "columns": ["变量", "卡方值", "p值", "显著(p<0.05)"],
             "rows": cat_rows},
        ]

        sig = [r[0] for r in rows if r[-1] == "是"] + [r[0] for r in cat_rows if r[-1] == "是"]
        summary = (
            f"按 {group_col} 分组（{group_label.get(groups[0], groups[0])}组 {len(g0)} 次 / "
            f"{group_label.get(groups[1], groups[1])}组 {len(g1)} 次）比较 {len(rows)} 个数值变量、"
            f"{len(cat_rows)} 个分类变量：{len(sig)} 项差异有统计学意义（p<0.05）"
            f"（{('、'.join(sig[:5])) if sig else '无'}）。"
            "注意：多重比较未校正，探索性结果需谨慎解读。"
        )
        facts = {
            "group_col": group_col,
            "group_sizes": {str(groups[0]): len(g0), str(groups[1]): len(g1)},
            "significant_vars": sig,
            "numeric_tests": [{"var": r[0], "method": r[1], "p": r[5]} for r in rows],
        }
        return make_result(summary, tables, facts=facts)


class CorrelationSkill(BaseSkill):
    meta = SkillMeta(
        id="correlation",
        name="相关性分析",
        category="统计分析",
        description="数值列 Pearson/Spearman 相关矩阵 + ECharts 热力图",
        params_schema=[
            {"name": "method", "label": "相关系数", "type": "select",
             "default": "spearman", "options": ["pearson", "spearman"]},
        ],
        data_requirements="就诊级宽表（年龄/住院天数/检验特征）",
    )

    def run(self, params: dict) -> dict:
        method = self.get_param(params, "method")
        visits = dataset_service.build_visit_matrix()
        cols = _numeric_columns(visits)
        if len(cols) < 2:
            return make_result("可用数值列不足 2 个，无法计算相关矩阵。")

        corr = visits[cols].corr(method=method).round(3)

        heat_data = []
        for i, c1 in enumerate(cols):
            for j, c2 in enumerate(cols):
                heat_data.append([j, i, float(corr.loc[c1, c2])])

        tables = [{
            "title": f"{method.capitalize()} 相关矩阵",
            "columns": ["变量"] + cols,
            "rows": [[c] + [float(corr.loc[c, c2]) for c2 in cols] for c in cols],
        }]
        charts = [{"title": "相关矩阵热力图", "option": heatmap_option(
            f"{method.capitalize()} 相关矩阵", cols, cols, heat_data)}]

        # 最强相关对（排除对角线）
        pairs = []
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                pairs.append((cols[i], cols[j], corr.iloc[i, j]))
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        top = pairs[0] if pairs else None

        summary = (
            f"对 {len(cols)} 个数值变量计算 {method} 相关系数；"
            + (f"相关性最强的一对为「{top[0]} — {top[1]}」（r={top[2]:.2f}）。" if top else "")
            + "相关系数仅反映线性/单调关联，不代表因果关系。"
        )
        facts = {
            "method": method,
            "variables": cols,
            "strongest_pair": {"var1": top[0], "var2": top[1], "r": float(top[2])} if top else None,
        }
        return make_result(summary, tables, charts, facts)


descriptive_stats_skill = DescriptiveStatsSkill()
group_comparison_skill = GroupComparisonSkill()
correlation_skill = CorrelationSkill()
