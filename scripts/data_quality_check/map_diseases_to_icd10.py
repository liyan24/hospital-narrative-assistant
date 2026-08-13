#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ICD-10 编码体系引入与西医病症标准化映射脚本

功能：
1. 从下载的 ICD-10 XLS 文件中提取编码体系，清洗后存储为 CSV/JSON。
2. 读取 `西医病症标准化列表.txt` 中的病症。
3. 使用“精确 → 子串 → 模糊”三级匹配策略，将病症映射到 ICD-10 编码。
4. 输出映射表、未匹配列表及统计摘要。

用法：
    python scripts/data_quality_check/map_diseases_to_icd10.py

依赖：
    pandas, rapidfuzz, xlrd（仅用于读取原始 xls）
"""

import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_output_dir() -> Path:
    return Path(__file__).resolve().parent


# ========== 1. ICD-10 编码体系导入与存储 ==========

def import_icd10_codes() -> pd.DataFrame:
    """读取原始 ICD-10 xls，清洗并返回 DataFrame"""
    raw_file = get_project_root() / "data" / "icd10_wuhan_raw.xls"
    if not raw_file.exists():
        raise FileNotFoundError(f"未找到 ICD-10 原始文件: {raw_file}")

    print(f"[读取] {raw_file.name}")
    df = pd.read_excel(raw_file)

    # 重命名列
    df = df.rename(columns={
        "ICD编码": "icd_code",
        "疾病名称（中文）": "disease_name",
        "167统计码": "stat_code",
        "疾病名称（拼音代码）": "pinyin_code",
    })

    # 清洗
    df["icd_code"] = df["icd_code"].astype(str).str.strip()
    df["disease_name"] = df["disease_name"].astype(str).str.strip()
    df["stat_code"] = df["stat_code"].astype(str).str.strip()
    df["pinyin_code"] = df["pinyin_code"].astype(str).str.strip()

    # 过滤空行与无效行
    df = df[df["icd_code"].notna() & (df["icd_code"] != "nan")]
    df = df[df["disease_name"].notna() & (df["disease_name"] != "nan")]

    # 去掉重复编码（保留第一个）
    df = df.drop_duplicates(subset=["icd_code"], keep="first")

    # 新增：章节分类
    df["chapter"] = df["icd_code"].apply(get_icd10_chapter)

    print(f"[信息] ICD-10 编码体系共 {len(df)} 条唯一编码")
    return df


def get_icd10_chapter(icd_code: str) -> str:
    """根据 ICD-10 编码判断所属章节"""
    # 取编码首字母
    letter = icd_code[0].upper() if icd_code else ""
    chapters = {
        "A": "第1章 某些传染病和寄生虫病 (A00-B99)",
        "B": "第1章 某些传染病和寄生虫病 (A00-B99)",
        "C": "第2章 肿瘤 (C00-D48)",
        "D": "第2章 肿瘤 (C00-D48)",
        "E": "第3章 血液及造血器官疾病和某些涉及免疫机制的疾患 (D50-D89)",
        "F": "第5章 精神和行为障碍 (F00-F99)",
        "G": "第6章 神经系统疾病 (G00-G99)",
        "H": "第7章 眼和附器疾病 (H00-H59) / 第8章 耳和乳突疾病 (H60-H95)",
        "I": "第9章 循环系统疾病 (I00-I99)",
        "J": "第10章 呼吸系统疾病 (J00-J99)",
        "K": "第11章 消化系统疾病 (K00-K93)",
        "L": "第12章 皮肤和皮下组织疾病 (L00-L99)",
        "M": "第13章 肌肉骨骼系统和结缔组织疾病 (M00-M99)",
        "N": "第14章 泌尿生殖系统疾病 (N00-N99)",
        "O": "第15章 妊娠、分娩和产褥期 (O00-O99)",
        "P": "第16章 起源于围生期的某些情况 (P00-P96)",
        "Q": "第17章 先天性畸形、变形和染色体异常 (Q00-Q99)",
        "R": "第18章 症状、体征和临床与实验室异常所见 (R00-R99)",
        "S": "第19章 损伤、中毒和外因的某些其他后果 (S00-T98)",
        "T": "第19章 损伤、中毒和外因的某些其他后果 (S00-T98)",
        "V": "第20章 疾病和死亡的外因 (V01-Y98)",
        "W": "第20章 疾病和死亡的外因 (V01-Y98)",
        "X": "第20章 疾病和死亡的外因 (V01-Y98)",
        "Y": "第20章 疾病和死亡的外因 (V01-Y98)",
        "Z": "第21章 影响健康状态的因素 (Z00-Z99)",
    }
    return chapters.get(letter, "其他")


def store_icd10_codes(df: pd.DataFrame) -> tuple[Path, Path]:
    """存储清洗后的 ICD-10 编码体系"""
    icd10_dir = get_project_root() / "data" / "icd10"
    icd10_dir.mkdir(parents=True, exist_ok=True)

    csv_path = icd10_dir / "icd10_codes.csv"
    json_path = icd10_dir / "icd10_codes.json"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    records = df.to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # 同时输出一份按章节汇总的统计
    chapter_stats = df.groupby("chapter").size().reset_index(name="count").sort_values("count", ascending=False)
    chapter_path = icd10_dir / "icd10_chapter_stats.csv"
    chapter_stats.to_csv(chapter_path, index=False, encoding="utf-8-sig")

    print(f"[存储] {csv_path.name}")
    print(f"[存储] {json_path.name}")
    print(f"[存储] {chapter_path.name}")
    return csv_path, json_path


# ========== 2. 西医病症读取 ==========

def load_standardized_diseases() -> list[dict]:
    """读取标准化后的西医病症列表"""
    file_path = get_output_dir() / "西医病症标准化列表.txt"
    diseases = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(" | ")
            if len(parts) == 2:
                diseases.append({
                    "standard_name": parts[0],
                    "frequency": int(parts[1]),
                })
    return diseases


# ========== 3. 匹配策略 ==========

# 人工覆盖映射：用于处理自动匹配易错的高频/关键病症
MANUAL_ICD10_MAPPING = {
    # 肿瘤
    "肺恶性肿瘤": ("C34.901", "支气管和肺恶性肿瘤"),
    "肺继发恶性肿瘤": ("C78.001", "肺继发性恶性肿瘤"),
    "淋巴结继发恶性肿瘤": ("C77.901", "淋巴结继发性恶性肿瘤"),
    "骨继发恶性肿瘤": ("C79.501", "骨继发性恶性肿瘤"),
    "脑继发恶性肿瘤": ("C79.301", "脑继发性恶性肿瘤"),
    "乳腺恶性肿瘤": ("C50.901", "乳房恶性肿瘤"),
    "肝恶性肿瘤": ("C22.901", "肝恶性肿瘤"),
    "胃恶性肿瘤": ("C16.901", "胃恶性肿瘤"),
    "结肠恶性肿瘤": ("C18.901", "结肠恶性肿瘤"),
    "直肠恶性肿瘤": ("C20.x01", "直肠恶性肿瘤"),
    "食管恶性肿瘤": ("C15.901", "食管恶性肿瘤"),
    "胰腺恶性肿瘤": ("C25.901", "胰腺恶性肿瘤"),
    "肾恶性肿瘤": ("C64.x01", "肾恶性肿瘤"),
    "膀胱恶性肿瘤": ("C67.901", "膀胱恶性肿瘤"),
    "前列腺恶性肿瘤": ("C61.x01", "前列腺恶性肿瘤"),
    "子宫颈恶性肿瘤": ("C53.901", "子宫颈恶性肿瘤"),
    "子宫内膜恶性肿瘤": ("C54.101", "子宫内膜恶性肿瘤"),
    "卵巢恶性肿瘤": ("C56.x01", "卵巢恶性肿瘤"),
    "甲状腺恶性肿瘤": ("C73.x01", "甲状腺恶性肿瘤"),
    "鼻咽恶性肿瘤": ("C11.901", "鼻咽恶性肿瘤"),
    "喉恶性肿瘤": ("C32.901", "喉恶性肿瘤"),
    "胆囊恶性肿瘤": ("C23.x01", "胆囊恶性肿瘤"),
    "胆管恶性肿瘤": ("C24.001", "胆管恶性肿瘤"),
    "贲门恶性肿瘤": ("C16.001", "贲门恶性肿瘤"),
    "多发性骨髓瘤": ("C90.002", "多发性骨髓瘤"),
    "非霍奇金淋巴瘤": ("C85.901", "非霍奇金淋巴瘤"),
    "弥漫大B细胞淋巴瘤": ("C83.301", "弥漫大B细胞淋巴瘤"),
    "霍奇金淋巴瘤": ("C81.901", "霍奇金淋巴瘤"),
    "急性髓系白血病": ("C92.001", "急性髓细胞白血病"),
    "急性淋巴细胞白血病": ("C91.001", "急性淋巴细胞白血病"),
    "慢性粒细胞白血病": ("C92.101", "慢性粒细胞白血病"),
    "慢性淋巴细胞白血病": ("C91.101", "慢性淋巴细胞白血病"),
    "骨髓增生异常综合征": ("D46.901", "骨髓增生异常综合征"),
    "骨髓增殖性肿瘤": ("D47.101", "慢性骨髓增殖性疾病"),
    "再生障碍性贫血": ("D61.901", "再生障碍性贫血"),
    "恶性肿瘤终末期": ("C80.x01", "恶性肿瘤"),
    "恶性肿瘤": ("C80.x01", "恶性肿瘤"),
    "恶性肿瘤化学治疗": ("Z51.101", "恶性肿瘤化学治疗"),
    "恶性肿瘤靶向治疗": ("Z51.801", "恶性肿瘤靶向治疗"),
    "恶性肿瘤免疫治疗": ("Z51.802", "恶性肿瘤免疫治疗"),
    "恶性肿瘤放射治疗": ("Z51.001", "恶性肿瘤放射治疗"),
    "恶性肿瘤内分泌治疗": ("Z51.803", "恶性肿瘤内分泌治疗"),

    # 心血管
    "高血压": ("I10.x02", "高血压"),
    "高血压1级": ("I10.x02", "高血压"),
    "高血压2级": ("I10.x02", "高血压"),
    "高血压3级": ("I10.x02", "高血压"),
    "高血压急症": ("I10.x03", "高血压急症"),
    "高血压性脑出血": ("I10.x04x001", "高血压性脑出血"),
    "冠状动脉粥样硬化性心脏病": ("I25.103", "冠状动脉粥样硬化性心脏病"),
    "心力衰竭": ("I50.907", "心力衰竭"),
    "心房颤动": ("I48.x01", "心房颤动"),
    "脑梗死": ("I63.901", "脑梗死"),
    "脑出血": ("I61.901", "脑出血"),
    "蛛网膜下腔出血": ("I60.901", "蛛网膜下腔出血"),
    "心律失常": ("I49.901", "心律失常"),
    "窦性心动过速": ("R00.001", "心动过速"),
    "窦性心动过缓": ("R00.101", "心动过缓"),
    "2型糖尿病": ("E11.901", "2型糖尿病"),

    # 消化
    "慢性胃炎": ("K29.501", "慢性胃炎"),
    "肝硬化": ("K74.601", "肝硬化"),
    "慢性乙型病毒性肝炎": ("K73.901", "慢性乙型病毒性肝炎"),
    "脂肪肝": ("K76.001", "脂肪肝"),
    "胆囊炎": ("K81.001", "胆囊炎"),
    "胆囊结石": ("K80.101", "胆囊结石"),

    # 呼吸
    "慢性阻塞性肺疾病": ("J44.901", "慢性阻塞性肺疾病"),
    "肺气肿": ("J43.901", "肺气肿"),
    "肺炎": ("J18.901", "肺炎"),
    "胸腔积液": ("J90.x01", "胸腔积液"),

    # 泌尿
    "肾囊肿": ("N28.101", "肾囊肿"),
    "肾结石": ("N20.001", "肾结石"),
    "肾功能不全": ("N19.x01", "肾功能不全"),

    # 其他
    "贫血": ("D64.901", "贫血"),
    "低蛋白血症": ("E46.x01", "低蛋白血症"),
    "发热": ("R50.901", "发热"),
    "疼痛": ("R52.901", "疼痛"),
    "死亡": ("R99.x01", "死亡"),
}


def build_icd_index(icd_df: pd.DataFrame) -> dict:
    """构建 ICD 名称索引，用于快速查找"""
    index = {}
    for _, row in icd_df.iterrows():
        name = row["disease_name"]
        code = row["icd_code"]
        if name not in index:
            index[name] = code
    return index


def match_disease_to_icd(disease_name: str, icd_index: dict, icd_names: list[str]) -> tuple[str, str, str, float]:
    """
    将单个病症匹配到 ICD-10 编码
    返回: (icd_code, icd_name, match_method, score)
    """
    # 0. 人工覆盖
    if disease_name in MANUAL_ICD10_MAPPING:
        code, icd_name = MANUAL_ICD10_MAPPING[disease_name]
        return code, icd_name, "人工覆盖", 100.0

    # 1. 精确匹配
    if disease_name in icd_index:
        return icd_index[disease_name], disease_name, "精确匹配", 100.0

    # 2. 子串匹配：ICD 名称包含病症名，且 ICD 名称长度不太长
    best_code, best_name, best_score = None, None, 0
    for icd_name in icd_names:
        if disease_name in icd_name and len(icd_name) <= len(disease_name) + 8:
            score = len(disease_name) / len(icd_name) * 100
            if score > best_score:
                best_code = icd_index[icd_name]
                best_name = icd_name
                best_score = score
    if best_code and best_score >= 60:
        return best_code, best_name, "子串匹配", best_score

    # 3. 子串匹配：病症名包含 ICD 名称，且 ICD 名称长度不太短
    best_code, best_name, best_score = None, None, 0
    for icd_name in icd_names:
        if icd_name in disease_name and len(icd_name) >= 4:
            score = len(icd_name) / len(disease_name) * 100
            if score > best_score:
                best_code = icd_index[icd_name]
                best_name = icd_name
                best_score = score
    if best_code and best_score >= 60:
        return best_code, best_name, "子串匹配", best_score

    # 4. 模糊匹配
    result = process.extractOne(disease_name, icd_names, scorer=fuzz.ratio)
    if result:
        matched_name, score, _ = result
        if score >= 85:
            return icd_index[matched_name], matched_name, "模糊匹配", score

    # 5. 未匹配
    return "", "", "未匹配", 0.0


def main():
    output_dir = get_output_dir()

    print("=" * 60)
    print("ICD-10 编码体系引入与西医病症标准化")
    print("=" * 60)

    # 1. 导入并存储 ICD-10 编码体系
    icd_df = import_icd10_codes()
    store_icd10_codes(icd_df)

    # 2. 读取西医病症
    diseases = load_standardized_diseases()
    print(f"[信息] 待映射西医病症数: {len(diseases)}")

    # 3. 构建索引
    icd_index = build_icd_index(icd_df)
    icd_names = list(icd_index.keys())

    # 4. 逐一匹配
    mapping_rows = []
    unmatched = []
    method_counts = defaultdict(int)

    for d in diseases:
        name = d["standard_name"]
        code, icd_name, method, score = match_disease_to_icd(name, icd_index, icd_names)
        mapping_rows.append({
            "standard_name": name,
            "frequency": d["frequency"],
            "icd10_code": code,
            "icd10_name": icd_name,
            "match_method": method,
            "match_score": round(score, 1),
        })
        method_counts[method] += 1
        if method == "未匹配":
            unmatched.append(name)

    # 5. 输出映射表
    mapping_df = pd.DataFrame(mapping_rows)
    mapping_df = mapping_df.sort_values(["match_method", "frequency"], ascending=[True, False])
    mapping_tsv = output_dir / "西医病症_ICD10映射.tsv"
    mapping_df.to_csv(mapping_tsv, sep="\t", index=False, encoding="utf-8-sig")

    # 6. 输出未匹配列表
    unmatched_file = output_dir / "西医病症_ICD10未匹配列表.txt"
    with open(unmatched_file, "w", encoding="utf-8") as f:
        f.write(f"# 西医病症 ICD-10 未匹配列表（共 {len(unmatched)} 条）\n")
        for name in sorted(unmatched):
            f.write(f"{name}\n")

    # 7. 输出统计摘要
    summary_file = output_dir / "西医病症_ICD10映射统计.md"
    summary = f"""# 西医病症 ICD-10 映射统计

## 总体统计

| 指标 | 数值 |
|------|------|
| 待映射西医病症数 | {len(diseases)} |
| 成功映射数 | {len(diseases) - len(unmatched)} |
| 未匹配数 | {len(unmatched)} |
| 映射成功率 | {((len(diseases) - len(unmatched)) / len(diseases) * 100):.1f}% |

## 匹配方法分布

| 匹配方法 | 病症数 |
|---------|--------|
"""
    for method in ["人工覆盖", "精确匹配", "子串匹配", "模糊匹配", "未匹配"]:
        count = method_counts.get(method, 0)
        summary += f"| {method} | {count} |\n"

    summary += f"""
## 输出文件

- `西医病症_ICD10映射.tsv`：完整映射表（标准病症 → ICD-10 编码/名称）。
- `西医病症_ICD10未匹配列表.txt`：未匹配病症列表，建议人工补充。
- `data/icd10/icd10_codes.csv` / `data/icd10/icd10_codes.json`：清洗后的 ICD-10 编码体系。
- `data/icd10/icd10_chapter_stats.csv`：ICD-10 各章节编码数量统计。

## 说明

- ICD-10 编码来源：武汉协和医院公开的 ICD-10 编码表（国标 GB/T 14396-2016 扩展码）。
- 匹配优先级：人工覆盖 > 精确匹配 > 子串匹配 > 模糊匹配（阈值 85）。
- 对于组合诊断、术后状态、治疗状态等非标准疾病名称，部分可能无法直接匹配到 ICD-10，
  这些条目建议由医学编码人员进一步审核。
"""
    summary_file.write_text(summary, encoding="utf-8")

    print(f"[输出] {mapping_tsv.name}")
    print(f"[输出] {unmatched_file.name}")
    print(f"[输出] {summary_file.name}")
    print("=" * 60)
    print(f"[结果] 待映射病症: {len(diseases)}")
    print(f"[结果] 成功映射: {len(diseases) - len(unmatched)} ({((len(diseases) - len(unmatched)) / len(diseases) * 100):.1f}%)")
    print(f"[结果] 未匹配: {len(unmatched)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
