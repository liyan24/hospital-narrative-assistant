"""
周数据分析引擎：从Excel数据中提取指定周的统计数据。
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
import json

from services.data_analysis_service import (
    load_admission_data,
    load_discharge_data,
    load_exam_data,
    load_lab_data,
    load_surgery_data,
    JSON_STORE_DIR,
)

JSON_STORE_DIR.mkdir(parents=True, exist_ok=True)


class WeeklyAnalysisService:
    def __init__(self):
        self.admission = None
        self.discharge = None
        self.exam = None
        self.lab = None
        self.surgery = None
        self.week_start = None
        self.week_end = None

    def load_all(self):
        self.admission = load_admission_data()
        self.discharge = load_discharge_data()
        self.exam = load_exam_data()
        self.lab = load_lab_data()
        self.surgery = load_surgery_data()

    def set_week(self, week_start: datetime):
        """设置要分析的一周（周一为起点）"""
        self.week_start = pd.Timestamp(week_start)
        self.week_end = self.week_start + timedelta(days=6)

    def set_week_by_date(self, date: datetime):
        """设置包含指定日期的那一周"""
        date = pd.Timestamp(date)
        # 找到该日期所在周的周一
        weekday = date.weekday()  # 0=Monday
        self.week_start = date - timedelta(days=weekday)
        self.week_end = self.week_start + timedelta(days=6)

    def _filter_week(self, df, date_col):
        """筛选本周数据"""
        if df is None or date_col not in df.columns:
            return df.iloc[0:0]
        mask = (df[date_col] >= self.week_start) & (df[date_col] <= self.week_end + timedelta(days=1))
        return df[mask].copy()

    def _prev_week(self):
        """上一周"""
        return self.week_start - timedelta(days=7), self.week_start - timedelta(days=1)

    def _same_week_last_year(self):
        """去年同期"""
        return self.week_start - timedelta(days=365), self.week_end - timedelta(days=365)

    # ========== 模块1：本周运营概况 ==========

    def analyze_operation(self) -> dict:
        """本周运营概况"""
        adm_week = self._filter_week(self.admission, "入院日期")
        dis_week = self._filter_week(self.discharge, "出院日期")
        dis_all = self.discharge.copy()

        # 在院患者日均 = 本周内每天在院的患者数平均值
        daily_in_hospital = []
        for i in range(7):
            day = self.week_start + timedelta(days=i)
            # 当天在院 = 入院日期 <= day 且 (出院日期 >= day 或 未出院)
            in_hospital = dis_all[
                (dis_all["入院日期"] <= day + timedelta(days=1)) &
                ((dis_all["出院日期"].isna()) | (dis_all["出院日期"] >= day))
            ]
            daily_in_hospital.append(len(in_hospital))
        avg_in_hospital = round(np.mean(daily_in_hospital), 1) if daily_in_hospital else 0

        # 床位使用率（假设总床位80张）
        total_beds = 80
        bed_usage_rate = round(avg_in_hospital / total_beds * 100, 1)

        # 平均住院天数（本周出院患者）
        avg_days = round(dis_week["住院天数"].mean(), 1) if len(dis_week) > 0 else 0

        # 环比和同比
        prev_start, prev_end = self._prev_week()
        adm_prev = self.admission[
            (self.admission["入院日期"] >= prev_start) &
            (self.admission["入院日期"] <= prev_end + timedelta(days=1))
        ]
        dis_prev = self.discharge[
            (self.discharge["出院日期"] >= prev_start) &
            (self.discharge["出院日期"] <= prev_end + timedelta(days=1))
        ]

        same_start, same_end = self._same_week_last_year()
        adm_same = self.admission[
            (self.admission["入院日期"] >= same_start) &
            (self.admission["入院日期"] <= same_end + timedelta(days=1))
        ]
        dis_same = self.discharge[
            (self.discharge["出院日期"] >= same_start) &
            (self.discharge["出院日期"] <= same_end + timedelta(days=1))
        ]

        def calc_ratio(current, previous):
            if len(previous) == 0:
                return None
            return round((len(current) - len(previous)) / len(previous) * 100, 1)

        # 每日入院分布
        adm_week["weekday"] = adm_week["入院日期"].dt.weekday
        weekday_counts = adm_week["weekday"].value_counts().sort_index()
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        daily_admission = {weekday_names[i]: int(weekday_counts.get(i, 0)) for i in range(7)}

        return {
            "week_range": f"{self.week_start.strftime('%Y/%m/%d')}—{self.week_end.strftime('%Y/%m/%d')}",
            "admission_count": len(adm_week),
            "discharge_count": len(dis_week),
            "avg_in_hospital": avg_in_hospital,
            "bed_usage_rate": bed_usage_rate,
            "avg_hospitalization_days": avg_days,
            "admission_vs_prev": calc_ratio(adm_week, adm_prev),
            "discharge_vs_prev": calc_ratio(dis_week, dis_prev),
            "admission_vs_yoy": calc_ratio(adm_week, adm_same),
            "discharge_vs_yoy": calc_ratio(dis_week, dis_same),
            "daily_admission": daily_admission,
        }

    # ========== 模块2：病种分析 ==========

    def analyze_diseases(self) -> dict:
        """本周病种分析"""
        adm_week = self._filter_week(self.admission, "入院日期")
        total = len(adm_week)
        if total == 0:
            return {"top5": [], "new_trends": []}

        disease_keywords = {
            "肺癌": ["肺癌", "肺腺癌", "肺鳞癌", "小细胞肺癌", "非小细胞肺癌", "肺部占位"],
            "乳腺癌": ["乳腺癌", "乳腺占位", "乳腺Ca"],
            "食管癌": ["食管癌", "食管Ca", "食道Ca"],
            "胃癌": ["胃癌", "胃占位", "胃Ca"],
            "肝癌": ["肝癌", "肝占位", "肝Ca", "肝细胞癌"],
            "结直肠癌": ["肠癌", "结肠癌", "直肠癌", "结直肠癌"],
            "宫颈癌": ["宫颈癌", "宫颈Ca", "宫颈占位"],
            "卵巢癌": ["卵巢癌", "卵巢Ca", "卵巢占位"],
            "白血病": ["白血病", "急性白血病", "慢性白血病"],
            "淋巴瘤": ["淋巴瘤", "霍奇金", "非霍奇金"],
            "鼻咽癌": ["鼻咽癌", "鼻咽Ca"],
            "前列腺癌": ["前列腺癌", "前列腺Ca"],
            "骨髓瘤": ["骨髓瘤", "多发性骨髓瘤"],
        }

        # 每个患者只计一次，优先匹配Top5病种
        patient_diseases = {}
        for idx, row in adm_week.iterrows():
            matched = []
            text = ""
            for field in ["主诉", "现病史"]:
                if field in adm_week.columns and pd.notna(row[field]):
                    text += str(row[field])
            for disease, keywords in disease_keywords.items():
                for kw in keywords:
                    if kw.lower() in text.lower():
                        matched.append(disease)
                        break
            if matched:
                # 如果有多个匹配，取第一个（按disease_keywords的顺序）
                patient_diseases[idx] = matched[0]

        disease_counts = {}
        for disease in patient_diseases.values():
            disease_counts[disease] = disease_counts.get(disease, 0) + 1

        sorted_diseases = sorted(disease_counts.items(), key=lambda x: x[1], reverse=True)
        top5 = []
        for disease, count in sorted_diseases[:5]:
            if count > 0:
                top5.append({
                    "disease": disease,
                    "count": int(count),
                    "percentage": round(count / total * 100, 1),
                })

        # 新发病种趋势（本周vs上周新增的病种）
        prev_start, prev_end = self._prev_week()
        adm_prev = self.admission[
            (self.admission["入院日期"] >= prev_start) &
            (self.admission["入院日期"] <= prev_end + timedelta(days=1))
        ]

        prev_diseases = set()
        for disease, keywords in disease_keywords.items():
            for field in ["主诉", "现病史"]:
                if field in adm_prev.columns:
                    for kw in keywords:
                        if adm_prev[field].fillna("").str.contains(kw, case=False, regex=False).any():
                            prev_diseases.add(disease)
                            break

        new_trends = []
        for disease, count in sorted_diseases[:10]:
            if count > 0 and disease not in prev_diseases:
                new_trends.append({"disease": disease, "count": int(count)})

        return {
            "top5": top5,
            "new_trends": new_trends,
        }

    # ========== 模块3：检查检验汇总 ==========

    def analyze_exam_lab(self) -> dict:
        """本周检查检验分析"""
        exam_week = self._filter_week(self.exam, "检查日期")
        lab_week = self._filter_week(self.lab, "送检时间")

        # 检查统计
        exam_type_counts = exam_week["标准化项目名称（匹配结果）"].fillna("未知").value_counts().head(10)
        exam_types = []
        for etype, count in exam_type_counts.items():
            # 阳性率计算
            subset = exam_week[exam_week["标准化项目名称（匹配结果）"] == etype]
            pos = 0
            total_text = 0
            for col in ["诊断"] + [f"诊断{i}" for i in range(1, 28)]:
                if col in subset.columns:
                    has_text = subset[col].astype(str).replace("nan", "").str.len() > 0
                    total_text += has_text.sum()
                    for kw in ["Ca", "癌", "转移", "占位", "恶性"]:
                        pos += subset[col].astype(str).str.contains(kw, case=False, regex=False).sum()
            exam_types.append({
                "type": etype,
                "count": int(count),
                "positive": int(pos),
                "positive_rate": round(pos / total_text * 100, 1) if total_text > 0 else 0,
            })

        # CT阳性Top5
        ct_data = exam_week[exam_week["标准化项目名称（匹配结果）"].fillna("").str.contains("CT", case=False, na=False)]
        ct_findings = {}
        for col in ["诊断"] + [f"诊断{i}" for i in range(1, 28)]:
            if col in ct_data.columns:
                for val in ct_data[col].dropna().astype(str):
                    if len(val) > 3:
                        ct_findings[val] = ct_findings.get(val, 0) + 1
        ct_top5 = sorted(ct_findings.items(), key=lambda x: x[1], reverse=True)[:5]

        # 检验统计
        lab_type_counts = lab_week["标准项目名称"].fillna("未知").value_counts().head(10)
        lab_types = []
        for ltype, count in lab_type_counts.items():
            subset = lab_week[lab_week["标准项目名称"] == ltype]
            # 简化异常率计算
            abnormal = 0
            normal = 0
            for _, row in subset.iterrows():
                val = row["结果定量化"]
                ref = row["参考范围"]
                if pd.isna(val) or pd.isna(ref):
                    continue
                ref_str = str(ref).replace("，", ",").replace("~", "-").replace("—", "-").replace("～", "-").replace("–", "-")
                import re
                match = re.search(r"([\d.]+)\s*-\s*([\d.]+)", ref_str)
                if match:
                    low, high = float(match.group(1)), float(match.group(2))
                    if val < low or val > high:
                        abnormal += 1
                    else:
                        normal += 1
            total_valid = abnormal + normal
            lab_types.append({
                "type": ltype,
                "count": int(count),
                "abnormal": abnormal,
                "abnormal_rate": round(abnormal / total_valid * 100, 1) if total_valid > 0 else 0,
            })

        return {
            "exam_types": exam_types,
            "ct_top5": [{"finding": f[0], "count": f[1]} for f in ct_top5],
            "lab_types": lab_types,
        }

    # ========== 模块4：治疗动态 ==========

    def analyze_treatment(self) -> dict:
        """本周治疗动态"""
        surgery_week = self._filter_week(self.surgery, "手术开始时间")
        dis_week = self._filter_week(self.discharge, "出院日期")

        # 手术统计
        surgeries = []
        for _, row in surgery_week.iterrows():
            surgeries.append({
                "date": row["手术开始时间"].strftime("%m/%d") if pd.notna(row["手术开始时间"]) else "",
                "name": row["手术名称"] if pd.notna(row["手术名称"]) else "",
                "type": row["手术类别"] if pd.notna(row["手术类别"]) else "",
            })

        # 化疗方案统计（从出院信息中提取）
        chemo_records = dis_week[dis_week["出院西医主要诊断1"].fillna("").str.contains("化疗", case=False, na=False)]
        chemo_count = len(chemo_records)

        # 药物不良反应（简化，从出院医嘱中提取关键词）
        adverse_events = []
        for field in ["出院医嘱", "出院用药医嘱", "出院饮食医嘱", "出院其他医嘱"]:
            if field in dis_week.columns:
                for val in dis_week[field].dropna().astype(str):
                    if "吐" in val or "恶心" in val:
                        adverse_events.append("恶心/呕吐")
                    if "骨髓抑制" in val or "白细胞" in val:
                        adverse_events.append("骨髓抑制")
                    if "皮疹" in val:
                        adverse_events.append("皮疹")
        adverse_counter = Counter(adverse_events)

        return {
            "surgery_count": len(surgery_week),
            "surgeries": surgeries,
            "chemo_count": chemo_count,
            "adverse_events": [{"event": k, "count": v} for k, v in adverse_counter.most_common(5)],
        }

    # ========== 模块5：质控指标 ==========

    def analyze_quality(self) -> dict:
        """本周质控指标"""
        dis_week = self._filter_week(self.discharge, "出院日期")

        # 平均住院天数
        avg_days = round(dis_week["住院天数"].mean(), 1) if len(dis_week) > 0 else 0

        # 30天非计划再入院率
        readmit_30 = 0
        for pid, group in dis_week.groupby("患者ID"):
            dis_dates = group["出院日期"].dropna().sort_values()
            for i in range(1, len(dis_dates)):
                delta = (dis_dates.iloc[i] - dis_dates.iloc[i-1]).days
                if 0 < delta <= 30:
                    readmit_30 += 1
        readmit_rate = round(readmit_30 / len(dis_week) * 100, 1) if len(dis_week) > 0 else 0

        # 入院24小时内检查完善率（简化：有检查记录的患者比例）
        adm_week = self._filter_week(self.admission, "入院日期")
        adm_ids = set(adm_week["患者ID"].tolist())
        exam_week = self._filter_week(self.exam, "检查日期")
        exam_ids = set(exam_week["患者ID"].tolist())
        exam_rate = round(len(exam_ids & adm_ids) / len(adm_ids) * 100, 1) if len(adm_ids) > 0 else 0

        return {
            "avg_days": avg_days,
            "readmit_30_rate": readmit_rate,
            "exam_within_24h_rate": exam_rate,
        }

    # ========== 模块6：重点关注患者 ==========

    def analyze_focus_patients(self) -> dict:
        """重点关注患者"""
        adm_week = self._filter_week(self.admission, "入院日期")
        dis_week = self._filter_week(self.discharge, "出院日期")

        # 高龄患者（>=80岁）
        elderly = adm_week[adm_week["年龄"] >= 80]
        elderly_list = []
        for _, row in elderly.iterrows():
            elderly_list.append({
                "name": "患者" + str(row["患者ID"])[-4:],
                "gender_age": f"{'男' if str(row.get('性别', '')) == '男' else '女'}/{int(row['年龄'])}岁",
                "diagnosis": str(row.get("主诉", "") or "")[:30],
            })

        # 超长住院（>30天，截至本周日仍在院或本周出院）
        long_stay = dis_week[dis_week["住院天数"] > 30]
        long_stay_list = []
        for _, row in long_stay.iterrows():
            long_stay_list.append({
                "name": "患者" + str(row["患者ID"])[-4:],
                "diagnosis": str(row.get("出院西医主要诊断1", "") or "")[:30],
                "days": int(row["住院天数"]),
            })

        return {
            "elderly_count": len(elderly),
            "elderly": elderly_list,
            "long_stay_count": len(long_stay),
            "long_stay": long_stay_list,
        }

    # ========== 模块7：下周预警 ==========

    def analyze_next_week_forecast(self) -> dict:
        """下周预警（基于历史同期数据预测）"""
        next_week_start = self.week_start + timedelta(days=7)
        next_week_end = self.week_end + timedelta(days=7)

        # 去年同期下周
        same_next_start = next_week_start - timedelta(days=365)
        same_next_end = next_week_end - timedelta(days=365)

        adm_forecast = self.admission[
            (self.admission["入院日期"] >= same_next_start) &
            (self.admission["入院日期"] <= same_next_end + timedelta(days=1))
        ]

        # 手术预测
        surgery_forecast = self.surgery[
            (self.surgery["手术开始时间"] >= same_next_start) &
            (self.surgery["手术开始时间"] <= same_next_end + timedelta(days=1))
        ]

        return {
            "next_week_range": f"{next_week_start.strftime('%Y/%m/%d')}—{next_week_end.strftime('%Y/%m/%d')}",
            "forecast_admission": len(adm_forecast),
            "forecast_surgeries": len(surgery_forecast),
        }

    def run_weekly_analysis(self, week_start: datetime = None) -> dict:
        """运行完整的周分析"""
        self.load_all()
        if week_start is None:
            # 默认选择数据中最晚一周的周一
            latest = self.admission["入院日期"].max()
            self.set_week_by_date(latest)
        else:
            self.set_week(week_start)

        result = {
            "report_title": f"肿瘤血液科 · 每周临床简报",
            "week_range": f"{self.week_start.strftime('%Y/%m/%d')}—{self.week_end.strftime('%Y/%m/%d')}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operation": self.analyze_operation(),
            "diseases": self.analyze_diseases(),
            "exam_lab": self.analyze_exam_lab(),
            "treatment": self.analyze_treatment(),
            "quality": self.analyze_quality(),
            "focus_patients": self.analyze_focus_patients(),
            "next_week": self.analyze_next_week_forecast(),
        }
        return result

    def save_weekly_analysis(self, analysis_id: str = "latest_weekly") -> str:
        """保存周分析结果到JSON文件"""
        result = self.run_weekly_analysis()
        # 避免重复前缀
        filename = analysis_id if analysis_id.startswith("weekly_") else f"weekly_{analysis_id}"
        filepath = JSON_STORE_DIR / f"{filename}.json"
        # 转换numpy类型
        def convert(obj):
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert(v) for v in obj]
            elif isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif pd.isna(obj):
                return None
            return obj
        result = convert(result)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return str(filepath)

    def load_weekly_analysis(self, analysis_id: str = "latest_weekly") -> dict:
        """从JSON文件加载周分析结果"""
        filename = analysis_id if analysis_id.startswith("weekly_") else f"weekly_{analysis_id}"
        filepath = JSON_STORE_DIR / f"{filename}.json"
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)


# 全局单例
weekly_analysis_service = WeeklyAnalysisService()
