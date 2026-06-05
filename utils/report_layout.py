"""
报告布局工具：将文本和图表按小节穿插排列。
"""
import re

# 定义每个章节中，关键词到图表的映射
# 顺序很重要：先匹配的关键词对应的图表会先插入
SECTION_CHART_MAP = {
    "basic": [
        ("科室", "department_pie"),
    ],
    "admission_trend": [
        ("年度", "admission_trend_line"),
        ("月度", "monthly_admission_bar"),
        ("季度", "quarterly_admission_pie"),
    ],
    "patient_features": [
        ("年龄", "age_distribution_bar"),
        ("婚姻", "marriage_pie"),
        ("职业", None),  # 职业数据质量太差，不生成图表
        ("入院次数", "admission_times_pie"),
    ],
    "hospitalization_days": [
        ("分段", "hospitalization_days_bar"),
        ("分布", "hospitalization_days_bar"),
    ],
    "disease_types": [
        ("Top15", "disease_top15_bar"),
        ("季节", "seasonal_disease_stacked"),
        ("病种", "disease_top15_bar"),
    ],
    "readmission": [
        ("间隔", "readmission_interval_bar"),
        ("时间", "readmission_interval_bar"),
    ],
    "discharge": [
        ("年度", "discharge_trend_line"),
        ("月度", "discharge_trend_line"),
        ("时间", "discharge_trend_line"),
        ("病种.*住院", "disease_stay_bar"),
        ("天数", "disease_stay_bar"),
    ],
    "exam": [
        ("类型", "exam_types_bar"),
        ("Top5", "exam_types_bar"),
        ("时间", "exam_trend_line"),
        ("趋势", "exam_trend_line"),
        ("阳性", "exam_positive_bar"),
    ],
    "lab": [
        ("样本", "lab_sample_pie"),
        ("种类", "lab_sample_pie"),
        ("项目", "lab_items_bar"),
        ("类型", "lab_items_bar"),
        ("时间", "lab_trend_line"),
        ("趋势", "lab_trend_line"),
        ("异常", "lab_abnormal_bar"),
    ],
    "summary": [],
}


def interleave_text_with_charts(section_key: str, text: str, charts: dict) -> list:
    """
    将章节文本与对应图表按小节穿插排列。
    返回列表，元素为 {"type": "text", "content": str} 或 {"type": "chart", "chart_id": str}
    """
    if not text:
        return []

    mappings = SECTION_CHART_MAP.get(section_key, [])
    if not mappings:
        # 无图表映射，直接返回纯文本
        return [{"type": "text", "content": text}]

    # 按行分割，保留换行符结构
    lines = text.split("\n")
    result = []
    inserted_charts = set()

    # 用于记录当前正在累积的文本缓冲区
    text_buffer = []

    def flush_text():
        nonlocal text_buffer
        if text_buffer:
            content = "\n".join(text_buffer)
            if content.strip():
                result.append({"type": "text", "content": content})
            text_buffer = []

    for line in lines:
        text_buffer.append(line)

        # 检查当前行是否触发图表插入
        for keyword, chart_id in mappings:
            if chart_id is None:
                continue
            if chart_id in inserted_charts:
                continue
            if chart_id not in charts:
                continue
            # 支持正则表达式关键词
            if re.search(keyword, line):
                flush_text()
                result.append({"type": "chart", "chart_id": chart_id})
                inserted_charts.add(chart_id)
                break  # 一行只触发一个图表

    flush_text()

    # 如果还有未插入的图表，在章节末尾追加
    for keyword, chart_id in mappings:
        if chart_id and chart_id not in inserted_charts and chart_id in charts:
            result.append({"type": "chart", "chart_id": chart_id})
            inserted_charts.add(chart_id)

    return result
