"""数据概览类算子：数据集画像与就诊趋势。"""
import numpy as np
import pandas as pd

from services.research.dataset_service import dataset_service
from services.research.skills.base import (
    BaseSkill, SkillMeta, make_result, bar_option, line_option, pie_option,
)


class DatasetProfileSkill(BaseSkill):
    meta = SkillMeta(
        id="dataset_profile",
        name="数据集画像",
        category="数据概览",
        description="各表规模、关键字段缺失率、年龄/住院天数分布直方图、诊断 Top20 条形图",
        params_schema=[],
        data_requirements="全部 Excel 表",
    )

    def run(self, params: dict) -> dict:
        tables = []
        for name in ["admission", "discharge", "orders", "exam", "lab", "surgery"]:
            try:
                df = dataset_service.load_table(name)
            except FileNotFoundError:
                continue
            # 关键字段缺失率（前 12 列中非空率最低的字段）
            miss = df.isna().mean().sort_values(ascending=False)
            worst = miss.head(5)
            tables.append({
                "title": f"{name}（{len(df)} 行 × {len(df.columns)} 列）缺失率 Top5 字段",
                "columns": ["字段", "缺失率"],
                "rows": [[str(k), f"{v:.1%}"] for k, v in worst.items()],
            })

        visits = dataset_service.build_visit_matrix()

        # 年龄分布直方图
        age = visits["age_years"].dropna()
        age_bins = [0, 18, 40, 60, 70, 80, 120]
        age_labels = ["<18", "18-40", "40-60", "60-70", "70-80", ">80"]
        age_counts = pd.cut(age, bins=age_bins, labels=age_labels, right=False).value_counts().reindex(age_labels).fillna(0)

        # 住院天数分布直方图
        los = visits["length_of_stay"].dropna()
        los_bins = [0, 3, 7, 14, 21, 30, 60, np.inf]
        los_labels = ["<3天", "3-7天", "7-14天", "14-21天", "21-30天", "30-60天", ">60天"]
        los_counts = pd.cut(los, bins=los_bins, labels=los_labels, right=False).value_counts().reindex(los_labels).fillna(0)

        # 诊断 Top20
        diag_counter = pd.Series([d for ds in visits["diagnoses"] for d in ds]).value_counts().head(20)

        charts = [
            {"title": "年龄分布", "option": bar_option("就诊患者年龄分布", [str(x) for x in age_counts.index], age_counts.tolist(), "年龄段", "人次")},
            {"title": "住院天数分布", "option": bar_option("住院天数分布", [str(x) for x in los_counts.index], los_counts.tolist(), "天数区间", "人次")},
            {"title": "出院诊断 Top20", "option": bar_option("出院西医诊断 Top20", diag_counter.index.tolist(), diag_counter.tolist(), "", "人次")},
        ]

        readmission_rate = visits["is_readmission"].mean()
        summary = (
            f"数据集共 {len(visits)} 次就诊、{visits['patient_id'].nunique()} 名患者；"
            f"年龄中位数 {age.median():.1f} 岁，住院天数中位数 {los.median():.0f} 天；"
            f"多次就诊（再入院）患者占比 {readmission_rate:.1%}。"
            f"最常见出院诊断为「{diag_counter.index[0] if len(diag_counter) else '无'}」（{int(diag_counter.iloc[0]) if len(diag_counter) else 0} 人次）。"
            "检验数据仅覆盖约两成患者，手术记录为小样本，使用时需注意偏倚。"
        )

        facts = {
            "visit_count": len(visits),
            "patient_count": visits["patient_id"].nunique(),
            "age_median": float(age.median()),
            "los_median": float(los.median()),
            "readmission_rate": float(readmission_rate),
            "top_diagnoses": diag_counter.head(10).to_dict(),
        }
        return make_result(summary, tables, charts, facts)


class TrendAnalysisSkill(BaseSkill):
    meta = SkillMeta(
        id="trend_analysis",
        name="就诊趋势分析",
        category="数据概览",
        description="按年度/月度统计入院人次趋势与出院科室分布",
        params_schema=[
            {"name": "granularity", "label": "时间粒度", "type": "select",
             "default": "year", "options": ["year", "month"], "description": "按年或按月汇总"},
        ],
        data_requirements="入院信息表（入院日期）",
    )

    def run(self, params: dict) -> dict:
        granularity = self.get_param(params, "granularity")
        admission = dataset_service.load_table("admission")
        date_col = dataset_service._find_col(admission, ["入院日期"])
        if not date_col:
            return make_result("入院信息表中未找到入院日期列，无法进行趋势分析。")

        dates = pd.to_datetime(admission[date_col], errors="coerce").dropna()
        if dates.empty:
            return make_result("入院日期字段无法解析为日期，无法进行趋势分析。")

        if granularity == "month":
            period = dates.dt.to_period("M").astype(str)
        else:
            period = dates.dt.year.astype(str)
        counts = period.value_counts().sort_index()

        charts = [{"title": "入院人次趋势", "option": line_option(
            f"{'月度' if granularity == 'month' else '年度'}入院人次趋势",
            counts.index.tolist(), counts.tolist(), "时间", "人次")}]

        tables = [{
            "title": "各时间段入院人次",
            "columns": ["时间", "入院人次"],
            "rows": [[str(k), int(v)] for k, v in counts.items()],
        }]

        span = f"{dates.min().date()} 至 {dates.max().date()}"
        summary = (
            f"数据时间跨度为 {span}，共 {int(counts.sum())} 人次入院；"
            f"{'月度' if granularity == 'month' else '年度'}峰值为 {counts.idxmax()}（{int(counts.max())} 人次），"
            f"最低为 {counts.idxmin()}（{int(counts.min())} 人次）。"
        )
        facts = {
            "date_range": span,
            "total_admissions": int(counts.sum()),
            "peak_period": str(counts.idxmax()),
            "peak_count": int(counts.max()),
        }
        return make_result(summary, tables, charts, facts)


dataset_profile_skill = DatasetProfileSkill()
trend_analysis_skill = TrendAnalysisSkill()
