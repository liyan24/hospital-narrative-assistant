# -*- coding: utf-8 -*-
"""
Generate publication-grade figures (1-4) for the KG-grounded clinical
data narrative paper.

Usage (from repo root):
    .venv/Scripts/python.exe paper/figures/make_figures.py

Outputs (PNG 300 dpi + vector PDF) into paper/figures/:
    figure1_framework.png/.pdf
    figure2_ontology.png/.pdf
    figure3_evaluation.png/.pdf
    figure4_case_study.png/.pdf
"""
import json
import os
import re
import unicodedata

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Patch
from matplotlib.lines import Line2D

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["pdf.fonttype"] = 42  # editable text in vector output

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "paper", "figures")
EXP = os.path.join(ROOT, "experiments", "output")

# ---------------------------------------------------------------- palette
C_BLUE = "#5B8DB8"      # patient / visit
C_BLUE_L = "#D6E4F0"
C_GREEN = "#7FA87B"     # western disease
C_GREEN_L = "#E3EFE2"
C_PURPLE = "#9678A8"    # tcm syndrome
C_PURPLE_L = "#EAE3F0"
C_ORANGE = "#D9A05B"    # treatment (drug / surgery)
C_ORANGE_L = "#F6E8D6"
C_GREY = "#9AA0A6"
C_GREY_L = "#ECEDEE"
C_RED = "#C0504D"
C_RED_L = "#F8E3E2"
C_DARK = "#3B3B3B"
C_EDGE = "#4D4D4D"


def box(ax, x, y, w, h, text, fc=C_GREY_L, ec=C_EDGE, fs=10, tc=C_DARK,
        lw=1.2, bold=False, rounding=0.02, zorder=2, align="center"):
    """Rounded rectangle with centred text. Coordinates in axes fraction."""
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0,rounding_size={rounding}",
                       fc=fc, ec=ec, lw=lw, zorder=zorder,
                       transform=ax.transAxes, clip_on=False)
    ax.add_patch(p)
    weight = "bold" if bold else "normal"
    if align == "center":
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fs, color=tc, weight=weight, zorder=zorder + 1,
                transform=ax.transAxes, linespacing=1.45)
    else:
        ax.text(x + 0.012, y + h / 2, text, ha="left", va="center",
                fontsize=fs, color=tc, weight=weight, zorder=zorder + 1,
                transform=ax.transAxes, linespacing=1.45)
    return p


def arrow(ax, x1, y1, x2, y2, style="-|>", color=C_EDGE, lw=1.6, ls="-",
          shrinkA=2, shrinkB=2, zorder=1, connectionstyle="arc3,rad=0"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, color=color,
                        lw=lw, linestyle=ls, shrinkA=shrinkA, shrinkB=shrinkB,
                        zorder=zorder, transform=ax.transAxes,
                        mutation_scale=14, connectionstyle=connectionstyle)
    ax.add_patch(a)
    return a


def new_ax(figsize):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"),
                    dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(f"saved {name}.png/.pdf")


# ================================================================ Figure 1
def figure1():
    fig, ax = new_ax((14, 7))

    cols = [
        (0.015, "① Data Layer", C_BLUE),
        (0.265, "② Knowledge Graph Layer", C_GREEN),
        (0.515, "③ Retrieval Layer", C_ORANGE),
        (0.765, "④ Generation Layer", C_PURPLE),
    ]
    cw = 0.22

    # header bands
    for x, title, c in cols:
        box(ax, x, 0.90, cw, 0.075, title, fc=c, ec=c, fs=12.5,
            tc="white", bold=True, rounding=0.015)

    # --- column 1: data layer
    box(ax, cols[0][0], 0.60, cw, 0.24,
        "7 Excel data sources\n\nadmissions · discharges ·\ndiagnoses · orders · labs ·\nexams · TCM therapies",
        fc=C_BLUE_L, fs=10)
    box(ax, cols[0][0], 0.38, cw, 0.14,
        "Cleaning & integration\n(MySQL relational store)", fc=C_BLUE_L, fs=10)
    box(ax, cols[0][0], 0.20, cw, 0.11,
        "ICD-10 standardization", fc=C_BLUE_L, fs=10)
    arrow(ax, 0.125, 0.60, 0.125, 0.525)
    arrow(ax, 0.125, 0.38, 0.125, 0.315)

    # --- column 2: KG layer
    box(ax, cols[1][0], 0.42, cw, 0.42,
        "Neo4j Knowledge Graph\n\n32,694 nodes\n788,119 relationships",
        fc=C_GREEN_L, fs=11.5, bold=False)
    box(ax, cols[1][0], 0.20, cw, 0.15,
        "9 node types\n9 relation types\n(visit-centred star schema)",
        fc=C_GREEN_L, fs=9.5)
    arrow(ax, 0.375, 0.42, 0.375, 0.355)

    # --- column 3: retrieval layer
    box(ax, cols[2][0], 0.70, cw, 0.12, "Intent parsing\n(task type + entities)",
        fc=C_ORANGE_L, fs=10)
    box(ax, cols[2][0], 0.38, cw, 0.26,
        "Retrieval primitives\n\nSubgraph · Co-occurrence\nSecond-order · Similarity\n(Jaccard) · Aggregation",
        fc=C_ORANGE_L, fs=10)
    box(ax, cols[2][0], 0.20, cw, 0.11,
        "Serialized fact list\n[F1, F2, …, Fn]", fc=C_ORANGE_L, fs=10)
    arrow(ax, 0.625, 0.70, 0.625, 0.645)
    arrow(ax, 0.625, 0.38, 0.625, 0.315)

    # --- column 4: generation layer
    box(ax, cols[3][0], 0.55, cw, 0.27,
        "LLM constrained\ngeneration\n\n(conditioned only on the\nserialized fact list)",
        fc=C_PURPLE_L, fs=10.5)
    box(ax, cols[3][0], 0.20, cw, 0.27,
        "Clinical narrative\n\nsentence-level provenance\ncitation [Fk] after every\ngrounded statement",
        fc=C_PURPLE_L, fs=10.5)
    arrow(ax, 0.875, 0.55, 0.875, 0.475)

    # --- inter-layer arrows
    for y in (0.55,):
        arrow(ax, cols[0][0] + cw + 0.004, y, cols[1][0] - 0.004, y, lw=2.0)
        arrow(ax, cols[1][0] + cw + 0.004, y, cols[2][0] - 0.004, y, lw=2.0)
        arrow(ax, cols[2][0] + cw + 0.004, y, cols[3][0] - 0.004, y, lw=2.0)

    # --- dashed verification & feedback loop
    arrow(ax, 0.985, 0.17, 0.985, 0.08, color=C_RED, ls=(0, (5, 4)), lw=1.8)
    arrow(ax, 0.985, 0.08, 0.125, 0.08, color=C_RED, ls=(0, (5, 4)), lw=1.8)
    arrow(ax, 0.125, 0.08, 0.125, 0.19, color=C_RED, ls=(0, (5, 4)), lw=1.8)
    ax.text(0.55, 0.045, "verification && feedback".replace("&&", "&"),
            fontsize=11, color=C_RED, ha="center", style="italic",
            transform=ax.transAxes,
            bbox=dict(fc="white", ec=C_RED, lw=1.0, boxstyle="round,pad=0.3",
                      linestyle=(0, (5, 4))))

    ax.set_title("Figure 1. Framework of KG-grounded clinical narrative generation",
                 fontsize=14, weight="bold", color=C_DARK, pad=6)
    save(fig, "figure1_framework")


# ================================================================ Figure 2
def figure2():
    fig, ax = new_ax((12.5, 8.5))

    # node positions (centre coords, axes fraction)
    pos = {
        "Visit":       (0.470, 0.52),
        "Patient":     (0.100, 0.52),
        "DiseaseW":    (0.720, 0.82),
        "DiseaseT":    (0.420, 0.86),
        "Drug":        (0.860, 0.60),
        "Surgery":     (0.820, 0.24),
        "Exam":        (0.600, 0.16),
        "LabItem":     (0.330, 0.14),
        "Chief":       (0.130, 0.24),
        "Department":  (0.160, 0.84),
    }
    W, H = 0.155, 0.085

    def centre(name):
        return pos[name]

    def draw_node(name, label, fc, ec, fs=10.5, tc=C_DARK, sub=None):
        x, y = pos[name]
        box(ax, x - W / 2, y - H / 2, W, H, label, fc=fc, ec=ec, fs=fs,
            tc=tc, bold=True, rounding=0.02)
        if sub:
            ax.text(x, y - H / 2 - 0.022, sub, ha="center", va="top",
                    fontsize=8, color=C_GREY, style="italic",
                    transform=ax.transAxes)

    def edge(n1, n2, label, props=None, rad=0.0, lx=None, ly=None, color=C_EDGE):
        x1, y1 = centre(n1)
        x2, y2 = centre(n2)
        arrow(ax, x1, y1, x2, y2, color=color, lw=1.5,
              connectionstyle=f"arc3,rad={rad}", shrinkA=26, shrinkB=26)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if lx is None:
            lx = mx
        if ly is None:
            ly = my + 0.02
        ax.text(lx, ly, label, fontsize=9, color=C_DARK, ha="center",
                va="center", transform=ax.transAxes, weight="bold",
                bbox=dict(fc="white", ec="none", alpha=0.9, pad=1.2))
        if props:
            ax.text(lx, ly - 0.035, props, fontsize=7.5, color=C_GREY,
                    ha="center", va="center", style="italic",
                    transform=ax.transAxes,
                    bbox=dict(fc="white", ec="none", alpha=0.9, pad=1.0))

    # edges from Visit (and Patient) ----------------------------------
    edge("Patient", "Visit", "HAS_VISIT", lx=0.285)
    edge("Visit", "DiseaseW", "DIAGNOSED_WITH", rad=0.12, lx=0.615, ly=0.72)
    edge("Visit", "DiseaseT", "DIAGNOSED_WITH", rad=-0.1, lx=0.415, ly=0.72)
    edge("Visit", "Drug", "PRESCRIBED",
         props="{dosage, frequency, route, start_date}",
         rad=0.10, lx=0.700, ly=0.575)
    edge("Visit", "LabItem", "HAS_LAB_RESULT",
         props="{value, unit, abnormal_flag}",
         rad=-0.12, lx=0.375, ly=0.30)
    edge("Visit", "Exam", "PERFORMED_EXAM", rad=0.05, lx=0.555, ly=0.32)
    edge("Visit", "Surgery", "UNDERWENT", rad=-0.12, lx=0.665, ly=0.36)
    edge("Visit", "Chief", "CHIEF_COMPLAINT", rad=0.10, lx=0.275, ly=0.37)
    edge("Visit", "Department", "IN_DEPARTMENT", rad=-0.12, lx=0.280, ly=0.70)

    # TREATS edges
    edge("Drug", "DiseaseW", "TREATS", rad=-0.25, lx=0.870, ly=0.75,
         color=C_ORANGE)
    edge("Surgery", "DiseaseW", "TREATS", rad=0.60, lx=0.960, ly=0.42,
         color=C_ORANGE)

    # nodes -------------------------------------------------------------
    draw_node("Visit", "Visit", C_BLUE, C_BLUE, tc="white", fs=12)
    draw_node("Patient", "Patient", C_BLUE_L, C_BLUE, fs=11)
    draw_node("DiseaseW", "Disease", C_GREEN_L, C_GREEN, fs=11,
              sub="(western)")
    draw_node("DiseaseT", "Disease", C_PURPLE_L, C_PURPLE, fs=11,
              sub="(tcm_syndrome)")
    draw_node("Drug", "Drug", C_ORANGE_L, C_ORANGE, fs=11)
    draw_node("Surgery", "Surgery", C_ORANGE_L, C_ORANGE, fs=11)
    draw_node("Exam", "Exam", C_GREY_L, C_GREY, fs=11)
    draw_node("LabItem", "LabItem", C_GREY_L, C_GREY, fs=11)
    draw_node("Chief", "ChiefComplaint", C_GREY_L, C_GREY, fs=10)
    draw_node("Department", "Department", C_GREY_L, C_GREY, fs=10)

    # legend ------------------------------------------------------------
    handles = [
        Patch(fc=C_BLUE_L, ec=C_BLUE, label="Patient / Visit"),
        Patch(fc=C_GREEN_L, ec=C_GREEN, label="Disease (western)"),
        Patch(fc=C_PURPLE_L, ec=C_PURPLE, label="Disease (tcm_syndrome)"),
        Patch(fc=C_ORANGE_L, ec=C_ORANGE, label="Treatment (Drug / Surgery)"),
        Patch(fc=C_GREY_L, ec=C_GREY, label="Context (Exam, LabItem,\nChiefComplaint, Department)"),
        Line2D([0], [0], color=C_ORANGE, lw=1.8, label="TREATS relation"),
    ]
    leg = ax.legend(handles=handles, loc="lower right",
                    bbox_to_anchor=(0.995, -0.005), fontsize=9,
                    frameon=True, framealpha=0.95, edgecolor=C_GREY,
                    title="Node categories", title_fontsize=9.5)
    leg.set_zorder(5)

    ax.set_title("Figure 2. Knowledge-graph ontology (visit-centred star schema)",
                 fontsize=14, weight="bold", color=C_DARK, pad=6)
    save(fig, "figure2_ontology")


# ================================================================ Figure 3
def figure3():
    fig, ax = new_ax((14, 8))

    # input
    box(ax, 0.30, 0.885, 0.40, 0.095,
        "Generated narratives\n4 methods × 100 tasks = 400",
        fc=C_BLUE_L, ec=C_BLUE, fs=11.5, bold=True, rounding=0.015)

    colw = 0.29
    xs = [0.025, 0.355, 0.685]

    # headers A / B / C
    box(ax, xs[0], 0.755, colw, 0.075, "A. Automated claim\nverification",
        fc=C_GREEN, ec=C_GREEN, fs=11, tc="white", bold=True, rounding=0.012)
    box(ax, xs[1], 0.755, colw, 0.075, "B. LLM-as-Judge",
        fc=C_ORANGE, ec=C_ORANGE, fs=11, tc="white", bold=True, rounding=0.012)
    box(ax, xs[2], 0.755, colw, 0.075, "C. Blinded expert review",
        fc=C_PURPLE, ec=C_PURPLE, fs=11, tc="white", bold=True, rounding=0.012)

    # column A steps
    box(ax, xs[0], 0.585, colw, 0.105, "LLM claim extraction\n(atomic factual claims)",
        fc=C_GREEN_L, ec=C_GREEN, fs=10)
    box(ax, xs[0], 0.415, colw, 0.105, "Deterministic matching\nvs. KG ground-truth facts",
        fc=C_GREEN_L, ec=C_GREEN, fs=10)
    box(ax, xs[0], 0.245, colw, 0.105, "Verdicts: supported /\ncontradicted / unverifiable",
        fc=C_GREEN_L, ec=C_GREEN, fs=10)
    box(ax, xs[0], 0.075, colw, 0.105,
        "Grounding rate · fact accuracy\nhallucination rate · unsupported rate",
        fc="white", ec=C_GREEN, fs=9.5)
    for y1, y2 in ((0.585, 0.525), (0.415, 0.355), (0.245, 0.185)):
        arrow(ax, xs[0] + colw / 2, y1, xs[0] + colw / 2, y2 + 0.002)

    # column B steps
    box(ax, xs[1], 0.50, colw, 0.19,
        "Rubric-anchored scoring\n\n4 dimensions, 1–5 scale\ncoherence · coverage\nreadability · clinical usefulness",
        fc=C_ORANGE_L, ec=C_ORANGE, fs=10)
    box(ax, xs[1], 0.075, colw, 0.105,
        "Dimension scores per narrative\n(mean over 4 dimensions)",
        fc="white", ec=C_ORANGE, fs=9.5)
    arrow(ax, xs[1] + colw / 2, 0.50, xs[1] + colw / 2, 0.187)

    # column C steps
    box(ax, xs[2], 0.585, colw, 0.105,
        "3 blinded packets\n(shuffled labels 文本甲–丁)",
        fc=C_PURPLE_L, ec=C_PURPLE, fs=10)
    box(ax, xs[2], 0.415, colw, 0.105,
        "Expert ratings, 3 dimensions\n1–5 scale + free comments",
        fc=C_PURPLE_L, ec=C_PURPLE, fs=10)
    box(ax, xs[2], 0.075, colw, 0.105,
        "Inter-rater reliability\nFleiss' κ",
        fc="white", ec=C_PURPLE, fs=9.5)
    for y1, y2 in ((0.585, 0.525), (0.415, 0.185)):
        arrow(ax, xs[2] + colw / 2, y1, xs[2] + colw / 2, y2 + 0.002)

    # input fan-out
    for x in xs:
        arrow(ax, 0.50, 0.883, x + colw / 2, 0.835,
              connectionstyle="arc3,rad=0", lw=1.5)

    # convergence
    box(ax, 0.025, -0.155, 0.46, 0.115,
        "Agreement analyses\nextractor calibration κ = 0.983\n"
        "judge vs. review  Spearman ρ = 0.457",
        fc=C_GREY_L, ec=C_GREY, fs=10)
    box(ax, 0.515, -0.155, 0.46, 0.115,
        "Statistical testing\nWilcoxon signed-rank tests\nBonferroni correction",
        fc=C_GREY_L, ec=C_GREY, fs=10)

    for x in xs:
        arrow(ax, x + colw / 2, 0.072, 0.255 if x < 0.5 else 0.745, -0.035,
              lw=1.4, connectionstyle="arc3,rad=0")

    ax.set_ylim(-0.20, 1.02)
    ax.set_title("Figure 3. Three-track evaluation protocol",
                 fontsize=14, weight="bold", color=C_DARK, pad=6)
    save(fig, "figure3_evaluation")


# ================================================================ Figure 4
CJK_RE = re.compile(r"[一-鿿　-〿＀-￯“”‘’—…，。；：、（）《》]")


def char_units(s):
    """Display width in CJK-character units (CJK = 1, ASCII ≈ 0.56)."""
    u = 0.0
    for ch in s:
        u += 1.0 if CJK_RE.match(ch) else 0.56
    return u


def wrap_cjk(text, max_units):
    lines, cur, w = [], "", 0.0
    for ch in text:
        u = 1.0 if CJK_RE.match(ch) else 0.56
        if ch == "\n":
            lines.append(cur)
            cur, w = "", 0.0
            continue
        if w + u > max_units and cur:
            lines.append(cur)
            cur, w = ch, u
        else:
            cur += ch
            w += u
    if cur:
        lines.append(cur)
    return lines


CIT_RE = re.compile(r"(\[F[\d,\s]*\])")


def draw_rich_paragraph(ax, x, y, text, max_units, unit_w, line_h, fs,
                        base_color=C_DARK, cit_color=C_GREEN):
    """Draw wrapped paragraph; [Fk] citations rendered in green."""
    # split into tokens, wrap on units
    tokens = CIT_RE.split(text)
    # build wrapped lines as lists of (segment, is_citation)
    lines = []
    cur, w = [], 0.0
    for tok in tokens:
        if not tok:
            continue
        is_cit = bool(CIT_RE.fullmatch(tok))
        for ch in tok:
            u = 1.0 if CJK_RE.match(ch) else 0.56
            if ch == "\n":
                lines.append(cur)
                cur, w = [], 0.0
                continue
            if w + u > max_units and cur:
                lines.append(cur)
                cur, w = [], 0.0
            if cur and cur[-1][1] == is_cit:
                cur[-1][0] += ch
            else:
                cur.append([ch, is_cit])
            w += u
    if cur:
        lines.append(cur)

    for line in lines:
        cx = x
        for seg, is_cit in line:
            ax.text(cx, y, seg, fontsize=fs, ha="left", va="top",
                    color=cit_color if is_cit else base_color,
                    weight="bold" if is_cit else "normal",
                    transform=ax.transAxes)
            cx += char_units(seg) * unit_w
        y -= line_h
    return y


def load_case(task_id="patient_storyline-017"):
    """Load generation texts, verdict metrics and blind-review mapping."""
    gens, vers = {}, {}
    with open(os.path.join(EXP, "generations.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["task_id"] == task_id:
                gens[d["method"]] = d["text"]
    with open(os.path.join(EXP, "verdicts.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["task_id"] == task_id:
                vers[d["method"]] = d["metrics"]

    key = json.load(open(os.path.join(EXP, "blind_review", "key.json"),
                         encoding="utf-8"))
    # method -> label -> list of factual_correctness scores across packets
    scores = {}
    for p in ("1", "2", "3"):
        mapping = key[p][task_id]
        ratings_file = os.path.join(EXP, "blind_review",
                                    f"ratings_packet{p}.jsonl")
        with open(ratings_file, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r["task_id"] != task_id:
                    continue
                m = mapping[r["label"]]
                scores.setdefault(m, []).append(r["factual_correctness"])

    task = None
    with open(os.path.join(EXP, "tasks.jsonl"), encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["task_id"] == task_id:
                task = d
                break
    return gens, vers, scores, task


def figure4():
    gens, vers, scores, task = load_case()

    # The case study contrasts the narrative that blinded experts rated
    # factual_correctness = 1 (文本丁 -> B2_vector_rag per key.json) with
    # the proposed KG-grounded method B3.
    low_method = "B2_vector_rag"
    assert min(scores[low_method]) == 1, scores
    low_fc = sum(scores[low_method]) / len(scores[low_method])
    b3_fc = sum(scores["B3_kg_grounded"]) / len(scores["B3_kg_grounded"])
    g_low = vers[low_method]["grounding_rate"]
    g_b3 = vers["B3_kg_grounded"]["grounding_rate"]

    # fact-list excerpt from ground truth
    facts = task["ground_truth_facts"]
    f_visit = next(f for f in facts if f["predicate"] == "visit_count")
    f_dis = next(f for f in facts if f["predicate"] == "discharge_date"
                 and f["subject"] == "162693001")
    f_adm = next(f for f in facts if f["predicate"] == "admission_date"
                 and f["subject"] == "162693002")

    fig, ax = new_ax((14.5, 9.5))
    MAXU = 41          # CJK units per line
    FS = 10.5
    col_w = 0.465
    unit_w = col_w / (MAXU + 3)
    line_h = 0.0345

    # ---------------- left panel: low-grounding baseline ----------------
    x0, x1 = 0.015, 0.015 + col_w
    ax.add_patch(FancyBboxPatch((x0, 0.015), col_w, 0.955,
                 boxstyle="round,pad=0,rounding_size=0.015", fc="#FDF6F5",
                 ec=C_RED, lw=1.4, transform=ax.transAxes, zorder=0))
    ax.text(x0 + 0.012, 0.948,
            f"B2 Vector-RAG (grounding {g_low:.2f})",
            fontsize=13, weight="bold", color=C_RED, ha="left", va="top",
            transform=ax.transAxes)
    ax.text(x0 + 0.012, 0.912,
            f"blinded review (文本丁): factual correctness {low_fc:.1f} / 5",
            fontsize=9.5, color=C_GREY, ha="left", va="top", style="italic",
            transform=ax.transAxes)

    excerpt = ("患者（病案号162693，67岁）于2024年2月19日首次入院，主诉为恶性"
               "肿瘤终末期维持治疗需求，住院8天，期间接受艾司奥美拉唑钠粉针静"
               "脉用药以保护胃黏膜，")
    y = draw_rich_paragraph(ax, x0 + 0.018, 0.875, excerpt, MAXU, unit_w,
                            line_h, FS, base_color=C_DARK)

    fab = [
        ("“于2月27日出院”",
         f"与事实矛盾：实际出院日期为 {f_dis['object']}"),
        ("“第三次入院在3月下旬 …… 第九次入院在7月下旬”",
         "第 3–9 次住院全部虚构（KG 中仅 2 次住院记录）"),
        ("“行胸腔穿刺引流”“行姑息性放疗”",
         "无任何事实依据的治疗行为"),
        ("“患者共经历9次住院，累计住院79天”",
         "累计住院天数系编造，无法由事实核验"),
    ]
    y -= 0.010
    ax.text(x0 + 0.018, y, "Fabricated content（盲评指出）:", fontsize=10,
            weight="bold", color=C_RED, ha="left", va="top",
            transform=ax.transAxes)
    y -= line_h + 0.004
    for quote, note in fab:
        qlines = wrap_cjk("× " + quote, MAXU - 2)
        for i, ql in enumerate(qlines):
            ax.text(x0 + 0.022, y, ql, fontsize=FS, color=C_RED, ha="left",
                    va="top", transform=ax.transAxes,
                    bbox=dict(fc=C_RED_L, ec=C_RED, lw=0.9,
                              boxstyle="round,pad=0.22"))
            y -= line_h + 0.006
        for nl in wrap_cjk("    → " + note, MAXU - 2):
            ax.text(x0 + 0.022, y, nl, fontsize=9, color=C_DARK, ha="left",
                    va="top", style="italic", transform=ax.transAxes)
            y -= line_h * 0.88
        y -= 0.008

    # ---------------- right panel: B3 KG-grounded -----------------------
    x0b = 0.520
    ax.add_patch(FancyBboxPatch((x0b, 0.015), col_w, 0.955,
                 boxstyle="round,pad=0,rounding_size=0.015", fc="#F4F9F4",
                 ec=C_GREEN, lw=1.4, transform=ax.transAxes, zorder=0))
    ax.text(x0b + 0.012, 0.948,
            f"B3 KG-Grounded (grounding {g_b3:.2f})",
            fontsize=13, weight="bold", color=C_GREEN, ha="left", va="top",
            transform=ax.transAxes)
    ax.text(x0b + 0.012, 0.912,
            f"blinded review: factual correctness {b3_fc:.1f} / 5",
            fontsize=9.5, color=C_GREY, ha="left", va="top", style="italic",
            transform=ax.transAxes)

    b3_excerpt = ("患者为67岁男性，病案号162693，因右肺恶性肿瘤伴终末期疾病"
                  "状态，于2024年2月至3月期间先后9次住院治疗，病情复杂且呈持"
                  "续进展趋势 [F1,F2,F3]。首次住院始于2024年2月19日，为期8天 "
                  "[F5,F7]。本次入院明确诊断为右肺恶性肿瘤，同时合并放射性肺炎"
                  "、慢性乙型病毒性肝炎，中医辨证为“肺积-痰瘀互结证” "
                  "[F12,F13,F11,F14]。")
    yb = draw_rich_paragraph(ax, x0b + 0.018, 0.875, b3_excerpt, MAXU,
                             unit_w, line_h, FS)

    # fact list excerpt strip
    strip_top = 0.630
    ax.add_patch(FancyBboxPatch((x0b + 0.018, strip_top - 0.310), col_w - 0.036,
                 0.310, boxstyle="round,pad=0,rounding_size=0.01",
                 fc="white", ec=C_GREEN, lw=1.1, transform=ax.transAxes,
                 zorder=1))
    ax.text(x0b + 0.030, strip_top - 0.025,
            "Fact list excerpt (KG ground truth)",
            fontsize=10.5, weight="bold", color=C_GREEN, ha="left", va="top",
            transform=ax.transAxes, zorder=2)
    fact_lines = [
        f"[Fa] 就诊次数 visit_count = {f_visit['object']}",
        f"[Fb] 住院 {f_dis['subject']} 出院日期 discharge_date = "
        f"{f_dis['object']}",
        f"[Fc] 住院 {f_adm['subject']} 入院日期 admission_date = "
        f"{f_adm['object']}",
    ]
    yy = strip_top - 0.062
    for fl in fact_lines:
        ax.text(x0b + 0.030, yy, fl, fontsize=9.5, color=C_DARK, ha="left",
                va="top", family="Microsoft YaHei", transform=ax.transAxes,
                zorder=2)
        yy -= 0.038
    ax.text(x0b + 0.030, yy - 0.004,
            "Every [Fk] citation in the narrative resolves to one serialized\n"
            "KG fact, enabling deterministic claim-level verification.",
            fontsize=8.5, color=C_GREY, ha="left", va="top", style="italic",
            transform=ax.transAxes, zorder=2, linespacing=1.4)

    ax.text(0.5, 0.985,
            "Task patient_storyline-017 · patient 162693 · blinded label 文本丁 "
            "= B2 (key.json)",
            fontsize=9, color=C_GREY, ha="center", va="top", style="italic",
            transform=ax.transAxes)
    ax.set_title("Figure 4. Case study: ungrounded vs. KG-grounded narrative",
                 fontsize=14, weight="bold", color=C_DARK, pad=10)
    save(fig, "figure4_case_study")


if __name__ == "__main__":
    figure1()
    figure2()
    figure3()
    figure4()
