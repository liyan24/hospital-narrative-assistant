"""论文图表样式：采用 scientific-visualization skill 的 Okabe-Ito 色盲友好调色板
与出版级版式（去顶/右边框、轴下绘制、细刻度线）。

优先从 .agents/skills/scientific-visualization/assets/color_palettes.py 动态加载；
缺失时使用内置常量。保留项目原有中文字体设置，仅增强配色与版式。
"""
import importlib.util

from services.research.skill_packs.paths import skill_file

# 内置兜底：Okabe-Ito 白底五色系（对比度 ≥ 3:1，Wong 2011, Nature Methods）
_FALLBACK_PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#000000"]


def _load_palette() -> list[str]:
    f = skill_file("scientific-visualization", "assets", "color_palettes.py")
    if f is not None:
        try:
            spec = importlib.util.spec_from_file_location("sv_color_palettes", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            palette = getattr(mod, "OKABE_ITO_ON_WHITE", None)
            if palette:
                return list(palette)
        except Exception:
            pass
    return list(_FALLBACK_PALETTE)


PALETTE = _load_palette()


def apply_style() -> None:
    """应用出版级图表样式（在 matplotlib 导入后、绘图前调用）"""
    import matplotlib
    from cycler import cycler

    matplotlib.rcParams.update({
        "axes.prop_cycle": cycler(color=PALETTE),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.axisbelow": True,
        "axes.linewidth": 0.8,
        "lines.linewidth": 1.5,
        "lines.markersize": 5,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.frameon": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


def color(index: int) -> str:
    """取调色板中第 index 个颜色（循环）"""
    return PALETTE[index % len(PALETTE)]
