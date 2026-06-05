"""
数据分析引擎：从Excel文件中提取所有统计指标，生成结构化JSON数据。
"""
import pandas as pd
import numpy as np
import json
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

DATA_DIR = Path("./data")
JSON_STORE_DIR = Path("./data/json_store")
CACHE_DIR = Path("./data/cache")
JSON_STORE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_or_cache(name: str, loader):
    cache_path = CACHE_DIR / f"{name}.pkl"
    if cache_path.exists():
        return pd.read_pickle(cache_path)
    df = loader()
    df.to_pickle(cache_path)
    return df


def load_admission_data():
    """加载入院信息表"""
    def _load():
        df = pd.read_excel(DATA_DIR / "入院信息表_肿瘤血液科.xlsx")
        df["入院日期"] = pd.to_datetime(df["入院日期"], errors="coerce")
        # 年龄字段单位为"天"，转换为"岁"
        df["年龄"] = pd.to_numeric(df["年龄"], errors="coerce") / 365.25
        return df
    return _load_or_cache("admission", _load)


def load_discharge_data():
    """加载出院信息表"""
    def _load():
        df = pd.read_excel(DATA_DIR / "出院信息表_肿瘤血液科.xlsx")
        df["入院日期"] = pd.to_datetime(df["入院日期"], errors="coerce")
        df["出院日期"] = pd.to_datetime(df["出院日期"], errors="coerce")
        df["住院天数"] = pd.to_numeric(df["住院天数"], errors="coerce")
        return df
    return _load_or_cache("discharge", _load)


def load_exam_data():
    """加载检查数据"""
    def _load():
        df = pd.read_excel(DATA_DIR / "入出院交检查_肿瘤血液科.xlsx")
        df["检查日期"] = pd.to_datetime(df["检查日期"], errors="coerce")
        df["报告日期"] = pd.to_datetime(df["报告日期"], errors="coerce")
        return df
    return _load_or_cache("exam", _load)


def load_lab_data():
    """加载检验数据"""
    def _load():
        df = pd.read_excel(DATA_DIR / "入出院交检验_肿瘤血液科.xlsx")
        df["送检时间"] = pd.to_datetime(df["送检时间"], errors="coerce")
        df["检验时间"] = pd.to_datetime(df["检验时间"], errors="coerce")
        df["报告时间"] = pd.to_datetime(df["报告时间"], errors="coerce")
        df["结果定量化"] = pd.to_numeric(df["结果定量化"], errors="coerce")
        return df
    return _load_or_cache("lab", _load)


def load_surgery_data():
    """加载手术数据"""
    def _load():
        df = pd.read_excel(DATA_DIR / "入出院交手术_肿瘤血液科.xlsx")
        df["手术开始时间"] = pd.to_datetime(df["手术开始时间"], errors="coerce")
        return df
    return _load_or_cache("surgery", _load)


class DataAnalysisService:
    """数据分析服务，生成报告所需的全部统计指标"""

    def __init__(self):
        self.admission = None
        self.discharge = None
        self.exam = None
        self.lab = None
        self.surgery = None

    def load_all(self):
        self.admission = load_admission_data()
        self.discharge = load_discharge_data()
        self.exam = load_exam_data()
        self.lab = load_lab_data()
        self.surgery = load_surgery_data()

    def analyze_basic(self) -> dict:
        """一、基本统计"""
        df = self.admission
        dept_counts = df["入院记录"].value_counts().to_dict()
        total = len(df)
        return {
            "total_records": total,
            "department_distribution": {
                "categories": list(dept_counts.keys()),
                "values": list(dept_counts.values()),
                "percentages": [round(v / total * 100, 2) for v in dept_counts.values()],
            },
            "date_range": {
                "start": df["入院日期"].min().strftime("%Y-%m-%d"),
                "end": df["入院日期"].max().strftime("%Y-%m-%d"),
                "days": (df["入院日期"].max() - df["入院日期"].min()).days,
            },
        }

    def analyze_admission_trend(self) -> dict:
        """二、入院趋势分析"""
        df = self.admission
        df["year"] = df["入院日期"].dt.year
        df["month"] = df["入院日期"].dt.month
        df["quarter"] = df["入院日期"].dt.quarter

        # 年度
        year_counts = df["year"].value_counts().sort_index()
        year_growth = []
        for i in range(1, len(year_counts)):
            prev = year_counts.iloc[i - 1]
            curr = year_counts.iloc[i]
            growth = round((curr - prev) / prev * 100, 1) if prev > 0 else 0
            year_growth.append(growth)

        # 月度
        month_counts = df["month"].value_counts().sort_index()

        # 季度
        quarter_counts = df["quarter"].value_counts().sort_index()
        q_percentages = [round(v / len(df) * 100, 1) for v in quarter_counts.values]

        return {
            "annual": {
                "years": [int(y) for y in year_counts.index.tolist()],
                "counts": year_counts.values.tolist(),
                "growth_rates": year_growth,
            },
            "monthly": {
                "months": [int(m) for m in month_counts.index.tolist()],
                "counts": month_counts.values.tolist(),
            },
            "quarterly": {
                "quarters": [f"Q{int(i)}" for i in quarter_counts.index.tolist()],
                "counts": quarter_counts.values.tolist(),
                "percentages": q_percentages,
            },
        }

    def analyze_patient_features(self) -> dict:
        """三、患者特征分析"""
        df = self.admission
        total = len(df)

        # 年龄
        age_bins = [0, 18, 30, 40, 50, 60, 70, 80, 100]
        age_labels = ["<18", "18-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]
        df["age_group"] = pd.cut(df["年龄"], bins=age_bins, labels=age_labels, right=False)
        age_counts = df["age_group"].value_counts().sort_index()

        # 婚姻
        marriage_counts = df["婚姻"].fillna("未知").value_counts()

        # 职业
        occupation_counts = df["职业"].fillna("无").value_counts().head(10)

        # 入院次数
        admission_times = df["入院次数"].value_counts().sort_index()
        admission_times_categorized = {
            "1次": int((df["入院次数"] == 1).sum()),
            "2-5次": int(((df["入院次数"] >= 2) & (df["入院次数"] <= 5)).sum()),
            "6-10次": int(((df["入院次数"] >= 6) & (df["入院次数"] <= 10)).sum()),
            ">10次": int((df["入院次数"] > 10).sum()),
        }

        return {
            "age": {
                "groups": age_counts.index.tolist(),
                "counts": age_counts.values.tolist(),
                "percentages": [round(v / total * 100, 1) for v in age_counts.values],
                "mean": round(df["年龄"].mean(), 1),
                "median": round(df["年龄"].median(), 1),
                "min": round(df["年龄"].min(), 1),
                "max": round(df["年龄"].max(), 1),
                "std": round(df["年龄"].std(), 1),
            },
            "marriage": {
                "categories": marriage_counts.index.tolist(),
                "counts": marriage_counts.values.tolist(),
                "percentages": [round(v / total * 100, 1) for v in marriage_counts.values],
            },
            "occupation": {
                "categories": occupation_counts.index.tolist(),
                "counts": occupation_counts.values.tolist(),
                "percentages": [round(v / total * 100, 2) for v in occupation_counts.values],
            },
            "admission_times": {
                "categories": list(admission_times_categorized.keys()),
                "counts": list(admission_times_categorized.values()),
                "percentages": [round(v / total * 100, 1) for v in admission_times_categorized.values()],
                "max_times": int(df["入院次数"].max()),
            },
        }

    def analyze_hospitalization_days(self) -> dict:
        """四、住院天数分析"""
        df = self.discharge.dropna(subset=["住院天数"])
        days = df["住院天数"]
        total = len(days)

        bins = [0, 2, 4, 8, 15, 30, 1000]
        labels = ["<2天", "2-3天", "4-7天", "8-14天", "15-30天", ">30天"]
        day_groups = pd.cut(days, bins=bins, labels=labels, right=False)
        day_counts = day_groups.value_counts().sort_index()

        long_stay = df[df["住院天数"] > 30]
        short_stay = df[df["住院天数"] < 2]

        return {
            "basic_stats": {
                "mean": round(days.mean(), 1),
                "median": round(days.median(), 1),
                "min": int(days.min()),
                "max": int(days.max()),
                "std": round(days.std(), 1),
            },
            "distribution": {
                "groups": day_counts.index.tolist(),
                "counts": day_counts.values.tolist(),
                "percentages": [round(v / total * 100, 1) for v in day_counts.values],
            },
            "long_stay": {
                "count": len(long_stay),
                "percentage": round(len(long_stay) / total * 100, 1),
                "mean_days": round(long_stay["住院天数"].mean(), 1),
                "max_days": int(long_stay["住院天数"].max()),
            },
            "short_stay": {
                "count": len(short_stay),
                "percentage": round(len(short_stay) / total * 100, 1),
            },
        }

    def analyze_disease_types(self) -> dict:
        """五、疾病类型提取分析"""
        df = self.admission
        total = len(df)

        # 从主诉和现病史中提取疾病关键词
        text_fields = ["主诉", "现病史"]
        disease_keywords = {
            "肺癌": ["肺癌", "肺腺癌", "肺鳞癌", "小细胞肺癌", "非小细胞肺癌", "肺部占位"],
            "肺腺癌": ["肺腺癌"],
            "肺鳞癌": ["肺鳞癌"],
            "乳腺癌": ["乳腺癌", "乳腺占位", "乳腺Ca"],
            "肝癌": ["肝癌", "肝占位", "肝Ca", "肝细胞癌"],
            "白血病": ["白血病", "急性白血病", "慢性白血病", "髓系白血病", "淋系白血病"],
            "胃癌": ["胃癌", "胃占位", "胃Ca"],
            "结直肠癌": ["肠癌", "结肠癌", "直肠癌", "结直肠癌", "直肠Ca", "结肠Ca"],
            "食管癌": ["食管癌", "食管Ca", "食道Ca"],
            "宫颈癌": ["宫颈癌", "宫颈Ca", "宫颈占位"],
            "卵巢癌": ["卵巢癌", "卵巢Ca", "卵巢占位"],
            "前列腺癌": ["前列腺癌", "前列腺Ca"],
            "淋巴瘤": ["淋巴瘤", "霍奇金", "非霍奇金"],
            "骨髓瘤": ["骨髓瘤", "多发性骨髓瘤"],
            "鼻咽癌": ["鼻咽癌", "鼻咽Ca"],
        }

        disease_counts = {}
        for disease, keywords in disease_keywords.items():
            count = 0
            for field in text_fields:
                if field in df.columns:
                    for kw in keywords:
                        count += df[field].fillna("").str.contains(kw, case=False, regex=False).sum()
            disease_counts[disease] = count

        # 去重：肺癌总次数应减去肺腺癌和肺鳞癌（避免重复计数）
        disease_counts["肺癌"] = max(0, disease_counts["肺癌"] - disease_counts["肺腺癌"] - disease_counts["肺鳞癌"])

        # 排序取Top15
        sorted_diseases = sorted(disease_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        # 季节性分布
        df_season = df.copy()
        df_season["quarter"] = df_season["入院日期"].dt.quarter
        seasonal_data = {}
        for disease, _ in sorted_diseases[:10]:
            keywords = disease_keywords[disease]
            mask = pd.Series(False, index=df_season.index)
            for field in text_fields:
                if field in df_season.columns:
                    for kw in keywords:
                        mask |= df_season[field].fillna("").str.contains(kw, case=False, regex=False)
            q_counts = df_season[mask]["quarter"].value_counts().sort_index()
            q_total = q_counts.sum()
            seasonal_data[disease] = {
                "quarters": [1, 2, 3, 4],
                "counts": [int(q_counts.get(i, 0)) for i in [1, 2, 3, 4]],
                "percentages": [round(q_counts.get(i, 0) / q_total * 100, 1) if q_total > 0 else 0 for i in [1, 2, 3, 4]],
            }

        return {
            "top15": {
                "diseases": [d[0] for d in sorted_diseases],
                "counts": [d[1] for d in sorted_diseases],
                "percentages": [round(d[1] / total * 100, 2) for d in sorted_diseases],
            },
            "seasonal": seasonal_data,
        }

    def analyze_readmission(self) -> dict:
        """六、再入院分析"""
        df = self.discharge.sort_values(["患者ID", "入院日期"])
        total = len(df)

        # 再入院率
        multi_admission = df[df.duplicated(subset=["患者ID"], keep=False)]
        readmission_rate = round(len(multi_admission) / total * 100, 1)

        # 再入院间隔
        intervals = []
        for pid, group in df.groupby("患者ID"):
            dates = group["入院日期"].dropna().sort_values()
            for i in range(1, len(dates)):
                delta = (dates.iloc[i] - dates.iloc[i - 1]).days
                if delta > 0:
                    intervals.append(delta)

        intervals_series = pd.Series(intervals)
        interval_bins = [0, 7, 14, 30, 60, 90, 180, 365, 10000]
        interval_labels = ["≤7天", "8-14天", "15-30天", "31-60天", "61-90天", "91-180天", "181-365天", ">365天"]
        interval_groups = pd.cut(intervals_series, bins=interval_bins, labels=interval_labels, right=True)
        interval_counts = interval_groups.value_counts().sort_index()

        # 高频患者
        high_freq = df["患者ID"].value_counts()
        high_freq_patients = high_freq[high_freq >= 10]
        high_freq_admission = self.admission[self.admission["患者ID"].isin(high_freq_patients.index)]

        return {
            "readmission_rate": readmission_rate,
            "interval_distribution": {
                "groups": interval_counts.index.tolist(),
                "counts": interval_counts.values.tolist(),
                "percentages": [round(v / len(intervals) * 100, 1) for v in interval_counts.values],
            },
            "interval_stats": {
                "mean": round(intervals_series.mean(), 1),
                "median": round(intervals_series.median(), 1),
                "total_intervals": len(intervals),
            },
            "high_freq_patients": {
                "count": len(high_freq_patients),
                "mean_age": round(high_freq_admission["年龄"].mean(), 1) if len(high_freq_admission) > 0 else None,
            },
        }

    def analyze_discharge(self) -> dict:
        """七、出院情况分析"""
        df = self.discharge
        total = len(df)

        # 出院时间分布
        df["出院年份"] = df["出院日期"].dt.year
        df["出院月份"] = df["出院日期"].dt.month
        year_counts = df["出院年份"].value_counts().sort_index()
        month_counts = df["出院月份"].value_counts().sort_index()

        # 病种与住院天数关系
        disease_keywords = {
            "肺癌": ["肺癌", "肺腺癌", "肺鳞癌", "小细胞肺癌", "非小细胞肺癌", "肺部占位"],
            "乳腺癌": ["乳腺癌", "乳腺占位", "乳腺Ca"],
            "肝癌": ["肝癌", "肝占位", "肝Ca", "肝细胞癌"],
            "白血病": ["白血病", "急性白血病", "慢性白血病"],
            "胃癌": ["胃癌", "胃占位", "胃Ca"],
            "结直肠癌": ["肠癌", "结肠癌", "直肠癌", "结直肠癌"],
            "食管癌": ["食管癌", "食管Ca", "食道Ca"],
            "宫颈癌": ["宫颈癌", "宫颈Ca", "宫颈占位"],
            "淋巴瘤": ["淋巴瘤", "霍奇金", "非霍奇金"],
            "卵巢癌": ["卵巢癌", "卵巢Ca", "卵巢占位"],
        }

        disease_stay = {}
        for disease, keywords in disease_keywords.items():
            mask = pd.Series(False, index=df.index)
            for col in ["入院情况", "病情描述", "出院西医主要诊断1"]:
                if col in df.columns:
                    for kw in keywords:
                        mask |= df[col].fillna("").str.contains(kw, case=False, regex=False)
            subset = df[mask]
            if len(subset) > 5:
                disease_stay[disease] = {
                    "mean_days": round(subset["住院天数"].mean(), 1),
                    "median_days": round(subset["住院天数"].median(), 1),
                    "count": len(subset),
                }

        # 出院结局
        outcome_counts = df["出院结局"].fillna("未记录").value_counts()

        return {
            "annual_discharge": {
                "years": year_counts.index.tolist(),
                "counts": year_counts.values.tolist(),
            },
            "monthly_discharge": {
                "months": month_counts.index.tolist(),
                "counts": month_counts.values.tolist(),
            },
            "disease_stay": disease_stay,
            "outcome": {
                "categories": outcome_counts.index.tolist(),
                "counts": outcome_counts.values.tolist(),
                "percentages": [round(v / total * 100, 2) for v in outcome_counts.values],
            },
        }

    def analyze_exam(self) -> dict:
        """检查数据分析"""
        df = self.exam
        total = len(df)
        unique_patients = df["患者ID"].nunique()
        unique_visits = df["就诊流水号"].nunique()

        # 检查类型
        exam_type_counts = df["标准化项目名称（匹配结果）"].fillna("未知").value_counts().head(20)

        # 时间趋势
        df["year"] = df["检查日期"].dt.year
        year_counts = df["year"].value_counts().sort_index()

        # 诊断关键词
        diag_keywords = ["Ca", "癌", "转移", "占位", "恶性"]
        positive_count = 0
        for col in ["诊断"] + [f"诊断{i}" for i in range(1, 28)]:
            if col in df.columns:
                for kw in diag_keywords:
                    positive_count += df[col].fillna("").str.contains(kw, case=False, regex=False).sum()

        # 各检查类型阳性率
        type_positive = {}
        top_types = exam_type_counts.head(10).index.tolist()
        for etype in top_types:
            subset = df[df["标准化项目名称（匹配结果）"] == etype]
            pos = 0
            total_text = 0
            for col in ["诊断"] + [f"诊断{i}" for i in range(1, 28)]:
                if col in subset.columns:
                    col_str = subset[col].astype(str).replace("nan", "")
                    has_text = col_str.str.len() > 0
                    total_text += has_text.sum()
                    for kw in diag_keywords:
                        pos += col_str.str.contains(kw, case=False, regex=False).sum()
            if total_text > 0:
                type_positive[etype] = {
                    "positive": int(pos),
                    "total": int(total_text),
                    "rate": round(pos / total_text * 100, 2),
                }

        # 报告间隔
        df["report_interval"] = (df["报告日期"] - df["检查日期"]).dt.total_seconds() / 3600
        interval_by_type = df.groupby("标准化项目名称（匹配结果）")["report_interval"].agg(["mean", "median"]).dropna()
        interval_by_type = interval_by_type[interval_by_type["mean"] >= 0].head(10)

        return {
            "basic": {
                "total_exams": total,
                "unique_patients": unique_patients,
                "unique_visits": unique_visits,
                "avg_per_patient": round(total / unique_patients, 1) if unique_patients > 0 else 0,
            },
            "exam_types": {
                "types": exam_type_counts.index.tolist(),
                "counts": exam_type_counts.values.tolist(),
            },
            "yearly_trend": {
                "years": year_counts.index.tolist(),
                "counts": year_counts.values.tolist(),
            },
            "positive": {
                "total_positive": int(positive_count),
                "total_exams": total,
                "rate": round(positive_count / total * 100, 2),
                "by_type": type_positive,
            },
            "report_interval": {
                "types": interval_by_type.index.tolist(),
                "mean_hours": [round(v, 2) for v in interval_by_type["mean"].values],
                "median_hours": [round(v, 2) for v in interval_by_type["median"].values],
            },
        }

    def analyze_lab(self) -> dict:
        """检验数据分析"""
        df = self.lab
        total = len(df)
        unique_patients = df["患者ID"].nunique()
        unique_visits = df["就诊流水号"].nunique()
        unique_items = df["标准项目名称"].nunique()

        # 样本种类
        sample_counts = df["样本种类"].fillna("未知").value_counts()

        # 检验类型（按标准项目名称分组）
        item_counts = df["标准项目名称"].fillna("未知").value_counts().head(20)

        # 时间趋势
        df["year"] = df["送检时间"].dt.year
        year_counts = df["year"].value_counts().sort_index()

        # 异常指标分析
        def parse_ref(ref):
            """解析参考范围"""
            if pd.isna(ref):
                return None, None
            # 统一各种分隔符为半角减号
            ref = str(ref).replace("，", ",").replace("~", "-").replace("—", "-").replace("～", "-").replace("–", "-")
            # 匹配数字-数字
            match = re.search(r"([\d.]+)\s*-\s*([\d.]+)", ref)
            if match:
                return float(match.group(1)), float(match.group(2))
            # 匹配 <数字 或 <=数字
            match = re.search(r"<[=]?\s*([\d.]+)", ref)
            if match:
                return None, float(match.group(1))
            # 匹配 >数字 或 >=数字
            match = re.search(r">[=]?\s*([\d.]+)", ref)
            if match:
                return float(match.group(1)), None
            return None, None

        abnormal_count = 0
        normal_count = 0
        unknown_count = 0
        item_abnormal = {}

        # 批量处理以提高性能
        for item_name, group in df.groupby("标准项目名称"):
            for idx, row in group.iterrows():
                val = row["结果定量化"]
                ref = row["参考范围"]
                low, high = parse_ref(ref)

                if pd.isna(val) or (low is None and high is None):
                    unknown_count += 1
                    continue

                is_abnormal = False
                if low is not None and val < low:
                    is_abnormal = True
                if high is not None and val > high:
                    is_abnormal = True

                if item_name not in item_abnormal:
                    item_abnormal[item_name] = {"high": 0, "low": 0, "total": 0}
                item_abnormal[item_name]["total"] += 1

                if is_abnormal:
                    abnormal_count += 1
                    if low is not None and val < low:
                        item_abnormal[item_name]["low"] += 1
                    elif high is not None and val > high:
                        item_abnormal[item_name]["high"] += 1
                else:
                    normal_count += 1

        # 异常率Top20
        item_abnormal_list = []
        for item, stats in item_abnormal.items():
            if stats["total"] >= 10:
                rate = round((stats["high"] + stats["low"]) / stats["total"] * 100, 1)
                item_abnormal_list.append({
                    "item": item,
                    "total": stats["total"],
                    "abnormal": stats["high"] + stats["low"],
                    "high": stats["high"],
                    "low": stats["low"],
                    "rate": rate,
                })
        item_abnormal_list.sort(key=lambda x: x["rate"], reverse=True)

        # 肿瘤标志物
        tumor_markers = ["甲胎蛋白", "癌胚抗原", "CA125", "CA199", "CA153", "CA724", "CA242", "CA50", "NSE", "SCC", "CYFRA211", "PSA", "FPSA"]
        tumor_data = df[df["标准项目名称"].fillna("").str.contains("|".join(tumor_markers), case=False, regex=True, na=False)]
        tumor_abnormal = 0
        for idx, row in tumor_data.iterrows():
            val = row["结果定量化"]
            ref = row["参考范围"]
            low, high = parse_ref(ref)
            if pd.isna(val) or (low is None and high is None):
                continue
            if high is not None and val > high:
                tumor_abnormal += 1
            if low is not None and val < low:
                tumor_abnormal += 1

        return {
            "basic": {
                "total_items": total,
                "unique_patients": unique_patients,
                "unique_visits": unique_visits,
                "unique_items": unique_items,
                "avg_per_patient": round(total / unique_patients, 1) if unique_patients > 0 else 0,
            },
            "sample_types": {
                "types": sample_counts.index.tolist(),
                "counts": sample_counts.values.tolist(),
            },
            "item_types": {
                "items": item_counts.index.tolist(),
                "counts": item_counts.values.tolist(),
            },
            "yearly_trend": {
                "years": year_counts.index.tolist(),
                "counts": year_counts.values.tolist(),
            },
            "abnormal": {
                "abnormal": abnormal_count,
                "normal": normal_count,
                "unknown": unknown_count,
                "total": abnormal_count + normal_count + unknown_count,
                "abnormal_rate": round(abnormal_count / (abnormal_count + normal_count) * 100, 1) if (abnormal_count + normal_count) > 0 else 0,
            },
            "top_abnormal": item_abnormal_list[:20],
            "tumor_markers": {
                "total_tests": len(tumor_data),
                "unique_patients": tumor_data["患者ID"].nunique(),
                "abnormal": tumor_abnormal,
                "abnormal_rate": round(tumor_abnormal / len(tumor_data) * 100, 1) if len(tumor_data) > 0 else 0,
            },
        }

    def run_full_analysis(self) -> dict:
        """运行全部分析并返回结果"""
        self.load_all()
        result = {
            "report_title": "肿瘤血液科数据分析报告",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_sources": {
                "admission": {"file": "入院信息表_肿瘤血液科.xlsx", "records": len(self.admission)},
                "discharge": {"file": "出院信息表_肿瘤血液科.xlsx", "records": len(self.discharge)},
                "exam": {"file": "入出院交检查_肿瘤血液科.xlsx", "records": len(self.exam)},
                "lab": {"file": "入出院交检验_肿瘤血液科.xlsx", "records": len(self.lab)},
                "surgery": {"file": "入出院交手术_肿瘤血液科.xlsx", "records": len(self.surgery)},
            },
            "basic_stats": self.analyze_basic(),
            "admission_trend": self.analyze_admission_trend(),
            "patient_features": self.analyze_patient_features(),
            "hospitalization_days": self.analyze_hospitalization_days(),
            "disease_types": self.analyze_disease_types(),
            "readmission": self.analyze_readmission(),
            "discharge": self.analyze_discharge(),
            "exam": self.analyze_exam(),
            "lab": self.analyze_lab(),
        }
        return result

    def _convert_to_json_serializable(self, obj):
        """将numpy类型转换为Python原生类型"""
        if isinstance(obj, dict):
            return {k: self._convert_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_json_serializable(v) for v in obj]
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        else:
            return obj

    def save_analysis(self, analysis_id: str = "latest") -> str:
        """保存分析结果到JSON文件"""
        result = self.run_full_analysis()
        result = self._convert_to_json_serializable(result)
        filepath = JSON_STORE_DIR / f"analysis_{analysis_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return str(filepath)

    def load_analysis(self, analysis_id: str = "latest") -> dict:
        """从JSON文件加载分析结果"""
        filepath = JSON_STORE_DIR / f"analysis_{analysis_id}.json"
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)


# 全局单例
data_analysis_service = DataAnalysisService()
