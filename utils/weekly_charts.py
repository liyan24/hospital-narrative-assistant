"""
周简报数据可视化辅助函数
将 weekly report 中的各模块数据渲染为 ECharts 图表
"""
import streamlit as st
from streamlit_echarts import st_echarts


def _bar_chart(title, x_data, y_data, color="#5470c6", y_name="数量"):
    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "category", "data": x_data, "axisLabel": {"rotate": 30, "fontSize": 10}},
        "yAxis": {"type": "value", "name": y_name, "nameTextStyle": {"fontSize": 10}},
        "series": [
            {
                "data": y_data,
                "type": "bar",
                "itemStyle": {"color": color},
                "label": {"show": True, "position": "top", "fontSize": 10},
            }
        ],
    }


def _line_chart(title, x_data, y_data, color="#91cc75", y_name="数量"):
    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "category", "data": x_data, "boundaryGap": False},
        "yAxis": {"type": "value", "name": y_name, "nameTextStyle": {"fontSize": 10}},
        "series": [
            {
                "data": y_data,
                "type": "line",
                "smooth": True,
                "itemStyle": {"color": color},
                "areaStyle": {"opacity": 0.2},
                "label": {"show": True, "fontSize": 10},
            }
        ],
    }


def _pie_chart(title, data, color_list=None):
    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "series": [
            {
                "type": "pie",
                "radius": ["40%", "70%"],
                "avoidLabelOverlap": False,
                "itemStyle": {"borderRadius": 5, "borderColor": "#fff", "borderWidth": 1},
                "label": {"show": True, "fontSize": 10},
                "data": data,
                "color": color_list,
            }
        ],
    }


def _horizontal_bar_chart(title, y_data, x_data, color="#ee6666"):
    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": "3%", "right": "8%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "value", "name": "数量"},
        "yAxis": {"type": "category", "data": y_data, "axisLabel": {"fontSize": 10}},
        "series": [
            {
                "data": x_data,
                "type": "bar",
                "itemStyle": {"color": color},
                "label": {"show": True, "position": "right", "fontSize": 10},
            }
        ],
    }


def render_weekly_charts(section_key, section_data):
    """根据 section_key 渲染对应的图表"""
    if section_key == "operation":
        daily = section_data.get("daily_admission", {})
        if daily:
            days = list(daily.keys())
            counts = list(daily.values())
            st_echarts(
                options=_line_chart("每日入院分布", days, counts, color="#5470c6"),
                height="280px",
                key=f"wk_op_line_{days}",
            )

        # 关键指标卡片
        cols = st.columns(4)
        metrics = [
            ("入院人次", section_data.get("admission_count", 0)),
            ("出院人次", section_data.get("discharge_count", 0)),
            ("平均在院", section_data.get("avg_in_hospital", 0)),
            ("床位使用率", f"{section_data.get('bed_usage_rate', 0)}%"),
        ]
        for col, (label, value) in zip(cols, metrics):
            with col:
                st.metric(label, value)

    elif section_key == "diseases":
        top5 = section_data.get("top5", [])
        if top5:
            diseases = [item["disease"] for item in top5]
            counts = [item["count"] for item in top5]
            pie_data = [{"value": item["count"], "name": item["disease"]} for item in top5]

            c1, c2 = st.columns(2)
            with c1:
                st_echarts(
                    options=_bar_chart("Top5 病种入院人次", diseases, counts, color="#fac858"),
                    height="300px",
                    key="wk_dis_bar",
                )
            with c2:
                st_echarts(
                    options=_pie_chart("Top5 病种占比", pie_data),
                    height="300px",
                    key="wk_dis_pie",
                )

        new_trends = section_data.get("new_trends", [])
        if new_trends:
            st.caption("本周新增病种趋势")
            st.dataframe(new_trends, use_container_width=True)

    elif section_key == "exam_lab":
        exam_types = section_data.get("exam_types", [])
        if exam_types:
            labels = [item["type"] for item in exam_types]
            counts = [item["count"] for item in exam_types]
            positive_rates = [item.get("positive_rate", 0) for item in exam_types]

            option = {
                "title": {"text": "检查类型及阳性率", "left": "center", "textStyle": {"fontSize": 14}},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
                "legend": {"data": ["检查量", "阳性率(%)"], "bottom": 0},
                "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 30, "fontSize": 10}},
                "yAxis": [
                    {"type": "value", "name": "检查量", "position": "left"},
                    {"type": "value", "name": "阳性率(%)", "position": "right", "max": 100},
                ],
                "series": [
                    {"name": "检查量", "type": "bar", "data": counts, "itemStyle": {"color": "#73c0de"}},
                    {"name": "阳性率(%)", "type": "line", "yAxisIndex": 1, "data": positive_rates, "itemStyle": {"color": "#ee6666"}},
                ],
            }
            st_echarts(options=option, height="300px", key="wk_exam_chart")

        lab_types = section_data.get("lab_types", [])
        if lab_types:
            labels = [item["type"] for item in lab_types]
            counts = [item["count"] for item in lab_types]
            abnormal_rates = [item.get("abnormal_rate", 0) for item in lab_types]

            option = {
                "title": {"text": "检验类型及异常率", "left": "center", "textStyle": {"fontSize": 14}},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
                "legend": {"data": ["检验量", "异常率(%)"], "bottom": 0},
                "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
                "xAxis": {"type": "category", "data": labels, "axisLabel": {"rotate": 30, "fontSize": 10}},
                "yAxis": [
                    {"type": "value", "name": "检验量", "position": "left"},
                    {"type": "value", "name": "异常率(%)", "position": "right", "max": 100},
                ],
                "series": [
                    {"name": "检验量", "type": "bar", "data": counts, "itemStyle": {"color": "#3ba272"}},
                    {"name": "异常率(%)", "type": "line", "yAxisIndex": 1, "data": abnormal_rates, "itemStyle": {"color": "#fc8452"}},
                ],
            }
            st_echarts(options=option, height="300px", key="wk_lab_chart")

        ct_top5 = section_data.get("ct_top5", [])
        if ct_top5:
            st.caption("CT 阳性发现 Top5")
            st.dataframe(ct_top5, use_container_width=True)

    elif section_key == "treatment":
        adverse = section_data.get("adverse_events", [])
        if adverse:
            events = [item["event"] for item in adverse]
            counts = [item["count"] for item in adverse]
            st_echarts(
                options=_horizontal_bar_chart("不良反应统计", events, counts),
                height="260px",
                key="wk_adv_bar",
            )

        surgeries = section_data.get("surgeries", [])
        if surgeries:
            st.caption(f"本周手术 {section_data.get('surgery_count', 0)} 例")
            st.dataframe(surgeries, use_container_width=True)

    elif section_key == "quality":
        cols = st.columns(3)
        with cols[0]:
            st.metric("平均住院天数", section_data.get("avg_days", 0))
        with cols[1]:
            st.metric("30天再入院率", f"{section_data.get('readmit_30_rate', 0)}%")
        with cols[2]:
            st.metric("24h检查完善率", f"{section_data.get('exam_within_24h_rate', 0)}%")

    elif section_key == "focus_patients":
        elderly = section_data.get("elderly", [])
        long_stay = section_data.get("long_stay", [])
        cols = st.columns(2)
        with cols[0]:
            st.metric("高龄患者(≥80岁)", section_data.get("elderly_count", 0))
            if elderly:
                st.dataframe(elderly, use_container_width=True)
        with cols[1]:
            st.metric("超长住院(>30天)", section_data.get("long_stay_count", 0))
            if long_stay:
                st.dataframe(long_stay, use_container_width=True)
