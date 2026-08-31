"""科研算子基类与统一返回结构工具。"""
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class SkillMeta:
    """算子元信息：前端按 params_schema 渲染参数表单"""
    id: str
    name: str
    category: str
    description: str
    params_schema: list[dict] = field(default_factory=list)
    data_requirements: str = ""


class BaseSkill:
    """科研算子抽象基类"""

    meta: SkillMeta

    def run(self, params: dict) -> dict:
        """执行算子，返回统一结构，子类必须实现"""
        raise NotImplementedError

    def get_param(self, params: dict, name: str):
        """取参数值，缺省回落到 params_schema 中的 default"""
        if name in params and params[name] is not None:
            return params[name]
        for p in self.meta.params_schema:
            if p["name"] == name:
                return p.get("default")
        return None


def make_result(summary: str, tables: list | None = None,
                charts: list | None = None, facts: dict | None = None) -> dict:
    """构造统一返回结构并转换数值为 python 原生类型"""
    return convert({
        "summary": summary,
        "tables": tables or [],
        "charts": charts or [],
        "facts": facts or {},
    })


def convert(obj: Any) -> Any:
    """numpy/pandas 类型转 python 原生类型（参照 weekly_analysis_service 写法）"""
    if isinstance(obj, dict):
        return {k: convert(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert(v) for v in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    elif isinstance(obj, float) and pd.isna(obj):
        return None
    elif isinstance(obj, pd.Series):
        return convert(obj.tolist())
    return obj


# ========== ECharts option 构造（参照 chart_service 风格） ==========

def bar_option(title: str, x_data: list, y_data: list, x_label: str = "", y_label: str = "") -> dict:
    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": x_data, "name": x_label, "axisLabel": {"rotate": 30}},
        "yAxis": {"type": "value", "name": y_label},
        "series": [{"data": y_data, "type": "bar", "itemStyle": {"color": "#5470c6"}}],
        "grid": {"left": "10%", "right": "10%", "bottom": "15%"},
    }


def horizontal_bar_option(title: str, y_data: list, x_data: list, x_label: str = "") -> dict:
    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "value", "name": x_label},
        "yAxis": {"type": "category", "data": y_data, "axisLabel": {"width": 140, "overflow": "truncate"}},
        "series": [{"data": x_data, "type": "bar", "itemStyle": {"color": "#fac858"}}],
        "grid": {"left": "22%", "right": "10%", "bottom": "10%"},
    }


def line_option(title: str, x_data: list, y_data: list, x_label: str = "", y_label: str = "") -> dict:
    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": x_data, "name": x_label},
        "yAxis": {"type": "value", "name": y_label},
        "series": [{"data": y_data, "type": "line", "smooth": True, "itemStyle": {"color": "#91cc75"}, "areaStyle": {}}],
        "grid": {"left": "10%", "right": "10%", "bottom": "10%"},
    }


def pie_option(title: str, data: list) -> dict:
    """data: [{"name": "...", "value": N}, ...]"""
    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"orient": "vertical", "left": "left", "type": "scroll"},
        "series": [{
            "type": "pie",
            "radius": "50%",
            "data": data,
            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}},
        }],
    }


def scatter_option(title: str, points: list, x_label: str = "", y_label: str = "",
                   series_name: str = "样本") -> dict:
    """points: [[x, y], ...] 或多系列时由调用方自行组装 series"""
    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "value", "name": x_label},
        "yAxis": {"type": "value", "name": y_label},
        "series": [{"data": points, "type": "scatter", "name": series_name,
                    "symbolSize": 6, "itemStyle": {"opacity": 0.6}}],
        "grid": {"left": "10%", "right": "10%", "bottom": "12%"},
    }


def heatmap_option(title: str, x_labels: list, y_labels: list, data: list,
                   vmin: float = -1, vmax: float = 1) -> dict:
    """data: [[x_idx, y_idx, value], ...]"""
    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "category", "data": x_labels, "axisLabel": {"rotate": 30}},
        "yAxis": {"type": "category", "data": y_labels},
        "visualMap": {
            "min": vmin, "max": vmax, "calculable": True, "orient": "horizontal",
            "left": "center", "bottom": "2%",
            "inRange": {"color": ["#5470c6", "#ffffff", "#ee6666"]},
        },
        "series": [{"type": "heatmap", "data": data, "label": {"show": False}}],
        "grid": {"left": "15%", "right": "10%", "bottom": "25%"},
    }


def graph_option(title: str, nodes: list, links: list) -> dict:
    """nodes: [{"name", "value", "symbolSize"}], links: [{"source", "target", "value"}]"""
    return {
        "title": {"text": title, "left": "center"},
        "tooltip": {"trigger": "item"},
        "series": [{
            "type": "graph",
            "layout": "force",
            "roam": True,
            "data": nodes,
            "links": links,
            "force": {"repulsion": 200, "edgeLength": 80},
            "label": {"show": True, "fontSize": 10},
            "lineStyle": {"color": "source", "curveness": 0.1, "opacity": 0.5},
            "emphasis": {"focus": "adjacency"},
        }],
    }
