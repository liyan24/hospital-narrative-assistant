"""
图表配置生成服务：将统计数据转换为ECharts JSON配置。
"""


class ChartService:
    """生成ECharts图表配置"""

    def _bar_option(self, title: str, x_data: list, y_data: list, x_label: str = "", y_label: str = "") -> dict:
        return {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": x_data, "name": x_label, "axisLabel": {"rotate": 30}},
            "yAxis": {"type": "value", "name": y_label},
            "series": [{"data": y_data, "type": "bar", "itemStyle": {"color": "#5470c6"}}],
            "grid": {"left": "10%", "right": "10%", "bottom": "15%"},
        }

    def _line_option(self, title: str, x_data: list, y_data: list, x_label: str = "", y_label: str = "") -> dict:
        return {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": x_data, "name": x_label},
            "yAxis": {"type": "value", "name": y_label},
            "series": [{"data": y_data, "type": "line", "smooth": True, "itemStyle": {"color": "#91cc75"}, "areaStyle": {}}],
            "grid": {"left": "10%", "right": "10%", "bottom": "10%"},
        }

    def _pie_option(self, title: str, data: list) -> dict:
        """data: [{"name": "...", "value": N}, ...]"""
        return {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"orient": "vertical", "left": "left", "type": "scroll"},
            "series": [{
                "type": "pie",
                "radius": "50%",
                "data": data,
                "emphasis": {
                    "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}
                },
            }],
        }

    def _horizontal_bar_option(self, title: str, y_data: list, x_data: list, x_label: str = "") -> dict:
        return {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "value", "name": x_label},
            "yAxis": {"type": "category", "data": y_data, "axisLabel": {"width": 120, "overflow": "truncate"}},
            "series": [{"data": x_data, "type": "bar", "itemStyle": {"color": "#fac858"}}],
            "grid": {"left": "20%", "right": "10%", "bottom": "10%"},
        }

    def _stacked_bar_option(self, title: str, x_data: list, series_list: list) -> dict:
        """series_list: [{"name": "...", "data": [...], "stack": "total"}, ...]"""
        return {
            "title": {"text": title, "left": "center"},
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"top": "bottom"},
            "xAxis": {"type": "category", "data": x_data},
            "yAxis": {"type": "value", "name": "人次"},
            "series": series_list,
            "grid": {"left": "10%", "right": "10%", "bottom": "15%"},
        }

    def generate_all_charts(self, data: dict) -> dict:
        """基于分析数据生成全部图表配置"""
        charts = {}

        # 1. 科室分布饼图
        dept = data["basic_stats"]["department_distribution"]
        charts["department_pie"] = self._pie_option(
            "科室分布",
            [{"name": dept["categories"][i], "value": dept["values"][i]} for i in range(len(dept["categories"]))]
        )

        # 2. 年度入院趋势
        trend = data["admission_trend"]["annual"]
        charts["admission_trend_line"] = self._line_option(
            "年度入院趋势", [str(y) for y in trend["years"]], trend["counts"], "年份", "入院人次"
        )

        # 3. 月度入院分布
        monthly = data["admission_trend"]["monthly"]
        charts["monthly_admission_bar"] = self._bar_option(
            "月度入院分布", [f"{m}月" for m in monthly["months"]], monthly["counts"], "月份", "入院人次"
        )

        # 4. 季度入院分布
        quarterly = data["admission_trend"]["quarterly"]
        charts["quarterly_admission_pie"] = self._pie_option(
            "季度入院分布",
            [{"name": quarterly["quarters"][i], "value": quarterly["counts"][i]} for i in range(len(quarterly["quarters"]))]
        )

        # 5. 年龄分布
        age = data["patient_features"]["age"]
        charts["age_distribution_bar"] = self._bar_option(
            "患者年龄分布", age["groups"], age["counts"], "年龄段", "人数"
        )

        # 6. 婚姻状况分布
        marriage = data["patient_features"]["marriage"]
        charts["marriage_pie"] = self._pie_option(
            "婚姻状况分布",
            [{"name": marriage["categories"][i], "value": marriage["counts"][i]} for i in range(len(marriage["categories"]))]
        )

        # 7. 入院次数分布
        adm_times = data["patient_features"]["admission_times"]
        charts["admission_times_pie"] = self._pie_option(
            "入院次数分布",
            [{"name": adm_times["categories"][i], "value": adm_times["counts"][i]} for i in range(len(adm_times["categories"]))]
        )

        # 8. 住院天数分布
        days = data["hospitalization_days"]["distribution"]
        charts["hospitalization_days_bar"] = self._bar_option(
            "住院天数分布", days["groups"], days["counts"], "天数区间", "人数"
        )

        # 9. 疾病类型Top15
        disease = data["disease_types"]["top15"]
        charts["disease_top15_bar"] = self._horizontal_bar_option(
            "疾病类型Top15", disease["diseases"][::-1], disease["counts"][::-1], "病例数"
        )

        # 10. 病种季节性分布（堆叠柱状图）
        seasonal = data["disease_types"]["seasonal"]
        if seasonal:
            diseases = list(seasonal.keys())[:8]
            quarters = ["Q1", "Q2", "Q3", "Q4"]
            series_list = []
            for d in diseases:
                series_list.append({
                    "name": d,
                    "type": "bar",
                    "stack": "total",
                    "data": seasonal[d]["counts"] if d in seasonal else [0, 0, 0, 0],
                })
            charts["seasonal_disease_stacked"] = self._stacked_bar_option(
                "主要病种季节性分布", quarters, series_list
            )

        # 11. 再入院间隔分布
        interval = data["readmission"]["interval_distribution"]
        charts["readmission_interval_bar"] = self._bar_option(
            "再入院间隔分布", interval["groups"], interval["counts"], "间隔时间", "人次"
        )

        # 12. 年度出院趋势
        discharge = data["discharge"]["annual_discharge"]
        charts["discharge_trend_line"] = self._line_option(
            "年度出院趋势", [str(y) for y in discharge["years"]], discharge["counts"], "年份", "出院人次"
        )

        # 13. 病种住院天数对比
        disease_stay = data["discharge"]["disease_stay"]
        if disease_stay:
            diseases = list(disease_stay.keys())
            means = [disease_stay[d]["mean_days"] for d in diseases]
            medians = [disease_stay[d]["median_days"] for d in diseases]
            charts["disease_stay_bar"] = {
                "title": {"text": "病种平均住院天数对比", "left": "center"},
                "tooltip": {"trigger": "axis"},
                "legend": {"top": "bottom"},
                "xAxis": {"type": "category", "data": diseases, "axisLabel": {"rotate": 30}},
                "yAxis": {"type": "value", "name": "天数"},
                "series": [
                    {"name": "平均天数", "type": "bar", "data": means, "itemStyle": {"color": "#5470c6"}},
                    {"name": "中位数", "type": "bar", "data": medians, "itemStyle": {"color": "#91cc75"}},
                ],
                "grid": {"left": "10%", "right": "10%", "bottom": "15%"},
            }

        # 14. 检查类型Top10
        exam_types = data["exam"]["exam_types"]
        charts["exam_types_bar"] = self._horizontal_bar_option(
            "检查类型Top10",
            exam_types["types"][:10][::-1],
            exam_types["counts"][:10][::-1],
            "检查次数"
        )

        # 15. 检查时间趋势
        exam_trend = data["exam"]["yearly_trend"]
        charts["exam_trend_line"] = self._line_option(
            "检查量年度趋势", [str(y) for y in exam_trend["years"]], exam_trend["counts"], "年份", "检查次数"
        )

        # 16. 检查阳性率
        positive = data["exam"]["positive"]["by_type"]
        if positive:
            types = list(positive.keys())[:10]
            rates = [positive[t]["rate"] for t in types]
            charts["exam_positive_bar"] = self._bar_option(
                "各检查类型阳性率", types, rates, "检查类型", "阳性率(%)"
            )

        # 17. 检验样本种类
        sample = data["lab"]["sample_types"]
        charts["lab_sample_pie"] = self._pie_option(
            "检验样本种类分布",
            [{"name": sample["types"][i], "value": sample["counts"][i]} for i in range(len(sample["types"]))]
        )

        # 18. 检验类型Top10
        lab_items = data["lab"]["item_types"]
        charts["lab_items_bar"] = self._horizontal_bar_option(
            "检验项目Top10",
            lab_items["items"][:10][::-1],
            lab_items["counts"][:10][::-1],
            "检验次数"
        )

        # 19. 检验时间趋势
        lab_trend = data["lab"]["yearly_trend"]
        charts["lab_trend_line"] = self._line_option(
            "检验量年度趋势", [str(y) for y in lab_trend["years"]], lab_trend["counts"], "年份", "检验次数"
        )

        # 20. 异常指标Top20
        top_abnormal = data["lab"]["top_abnormal"]
        if top_abnormal:
            items = [a["item"] for a in top_abnormal[:15]][::-1]
            rates = [a["rate"] for a in top_abnormal[:15]][::-1]
            charts["lab_abnormal_bar"] = self._horizontal_bar_option(
                "异常指标Top15", items, rates, "异常率(%)"
            )

        return charts


# 全局单例
chart_service = ChartService()
