"""
统一 UI 样式配置
提供 Streamlit 页面共享的 CSS、颜色主题、卡片组件等
"""

import streamlit as st

# 医疗主题色
PRIMARY_COLOR = "#2563EB"        # 主蓝色
PRIMARY_LIGHT = "#EFF6FF"        # 浅蓝背景
SUCCESS_COLOR = "#10B981"        # 成功绿
WARNING_COLOR = "#F59E0B"        # 警告橙
DANGER_COLOR = "#EF4444"         # 危险红
TEXT_PRIMARY = "#1F2937"         # 主文字
TEXT_SECONDARY = "#6B7280"       # 次要文字
BORDER_COLOR = "#E5E7EB"         # 边框
BG_COLOR = "#F9FAFB"             # 页面背景
CARD_BG = "#FFFFFF"              # 卡片背景


def apply_global_style():
    """注入全局 CSS 样式"""
    st.markdown(f"""
    <style>
        /* 全局字体与背景 */
        .stApp {{
            background-color: {BG_COLOR};
            font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
        }}

        /* 标题样式 */
        h1, h2, h3, h4, h5, h6 {{
            color: {TEXT_PRIMARY};
            font-weight: 600;
        }}

        /* 卡片通用样式 */
        .medical-card {{
            background-color: {CARD_BG};
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            margin-bottom: 16px;
        }}

        .medical-card-title {{
            font-size: 16px;
            font-weight: 600;
            color: {TEXT_PRIMARY};
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .medical-card-subtitle {{
            font-size: 13px;
            color: {TEXT_SECONDARY};
            margin-bottom: 16px;
        }}

        /* 指标卡片 */
        .metric-card {{
            background-color: {CARD_BG};
            border: 1px solid {BORDER_COLOR};
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }}

        .metric-value {{
            font-size: 28px;
            font-weight: 700;
            color: {PRIMARY_COLOR};
            margin: 8px 0;
        }}

        .metric-label {{
            font-size: 13px;
            color: {TEXT_SECONDARY};
        }}

        /* 状态标签 */
        .status-badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }}

        .status-normal {{
            background-color: #D1FAE5;
            color: #065F46;
        }}

        .status-warning {{
            background-color: #FEF3C7;
            color: #92400E;
        }}

        .status-danger {{
            background-color: #FEE2E2;
            color: #991B1B;
        }}

        /* 时间线 */
        .timeline-item {{
            border-left: 3px solid {PRIMARY_COLOR};
            padding-left: 16px;
            padding-bottom: 20px;
            position: relative;
        }}

        .timeline-item::before {{
            content: "";
            position: absolute;
            left: -6px;
            top: 4px;
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background-color: {PRIMARY_COLOR};
        }}

        .timeline-date {{
            font-size: 12px;
            color: {TEXT_SECONDARY};
            margin-bottom: 4px;
        }}

        .timeline-title {{
            font-size: 14px;
            font-weight: 600;
            color: {TEXT_PRIMARY};
            margin-bottom: 4px;
        }}

        .timeline-desc {{
            font-size: 13px;
            color: {TEXT_SECONDARY};
            line-height: 1.5;
        }}

        /* 按钮样式 */
        .stButton>button {{
            border-radius: 8px;
            font-weight: 500;
        }}

        /* 隐藏默认展开边框 */
        .streamlit-expanderHeader {{
            font-weight: 600;
            color: {TEXT_PRIMARY};
        }}

        /* 表格样式 */
        .dataframe {{
            font-size: 13px;
        }}

        /* 侧边栏 */
        .css-1d391kg {{
            background-color: {CARD_BG};
        }}
    </style>
    """, unsafe_allow_html=True)


def render_card(title: str, content: str, icon: str = ""):
    """渲染一个标准信息卡片"""
    st.markdown(f"""
    <div class="medical-card">
        <div class="medical-card-title">{icon} {title}</div>
        <div style="color: {TEXT_SECONDARY}; font-size: 14px; line-height: 1.6;">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def render_metric_card(label: str, value: str, delta: str = "", color: str = PRIMARY_COLOR):
    """渲染指标卡片"""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color: {color};">{value}</div>
        {f'<div style="font-size: 12px; color: {TEXT_SECONDARY};">{delta}</div>' if delta else ''}
    </div>
    """, unsafe_allow_html=True)


def render_status_badge(text: str, level: str = "normal"):
    """渲染状态标签"""
    cls = f"status-{level}"
    st.markdown(f'<span class="status-badge {cls}">{text}</span>', unsafe_allow_html=True)


def render_section_header(title: str, subtitle: str = ""):
    """渲染区块标题"""
    st.markdown(f"""
    <div style="margin: 24px 0 16px 0;">
        <h3 style="margin: 0; color: {TEXT_PRIMARY};">{title}</h3>
        {f'<p style="margin: 4px 0 0 0; color: {TEXT_SECONDARY}; font-size: 14px;">{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)
