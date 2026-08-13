#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量核查输出脚本

功能：
1. 从入院信息表中提取原始数据（仅保留导入数据库所需的对应字段），输出为 Excel。
2. 整理数据清洗规则，输出为 Markdown 文档。
3. 从知识图谱清洗结果中提取病症/疾病（按西医、中医、中医证型拆分）和药品，
   分别输出为 txt 文件。

用法：
    python scripts/data_quality_check/generate_outputs.py
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_output_dir() -> Path:
    return Path(__file__).resolve().parent


# ========== 1. 入院信息表对应字段（与 import_data.py 中 admissions 映射保持一致）==========

ADMISSION_FIELD_MAPPING = {
    "患者ID": "patient_id",
    "病案号": "medical_record_no",
    "就诊流水号": "visit_no",
    "入院日期": "admission_date",
    "年龄": "age",
    "婚姻": "marriage",
    "职业": "occupation",
    "过敏史": "allergy_history",
    "入院记录": "admission_record",
    "入院次数": "admission_count",
    "主诉": "chief_complaint",
    "现病史": "present_illness",
    "既往史": "past_history",
    "个人史": "personal_history",
    "家族史": "family_history",
    "手术外伤史": "surgery_trauma_history",
    "输血史": "blood_transfusion_history",
    "婚育史": "marriage_childbirth_history",
    "医保付费方式": "payment_method",
    "体格检查": "physical_exam",
    "专科检查": "specialist_exam",
    "辅助检查": "auxiliary_exam",
    "发病节气": "onset_solar_term",
    "中医四诊": "tcm_four_diagnosis",
    "入院情况": "admission_condition",
    "西医治疗计划": "western_treatment_plan",
    "中医治疗计划": "tcm_treatment_plan",
    "门急诊诊断西医": "emergency_western_diagnosis",
    "门急诊诊断中医": "emergency_tcm_diagnosis",
    "入院西医诊断": "admission_western_diagnosis",
    "入院中医诊断": "admission_tcm_diagnosis",
    "诊断依据中医辨病辨证分析": "diagnosis_basis_analysis",
    "入院中医证型": "admission_tcm_syndrome",
    "入院症见": "admission_symptoms",
}


def export_raw_admission_data(output_dir: Path) -> Path:
    """输出入院信息表原始数据（仅保留对应字段）"""
    data_dir = get_project_root() / "data"
    file = data_dir / "入院信息表_肿瘤血液科.xlsx"
    output_path = output_dir / "入院信息表_原始对应字段.xlsx"

    print(f"[读取] {file.name}")
    df = pd.read_excel(file, dtype={"就诊流水号": str, "患者ID": str, "病案号": str})

    available_cols = [c for c in ADMISSION_FIELD_MAPPING.keys() if c in df.columns]
    missing_cols = [c for c in ADMISSION_FIELD_MAPPING.keys() if c not in df.columns]

    df_out = df[available_cols].copy()
    # 使用数据库字段名作为表头，便于核查
    df_out.rename(columns=ADMISSION_FIELD_MAPPING, inplace=True)

    df_out.to_excel(output_path, index=False, engine="openpyxl")
    print(f"[输出] {output_path.name}，共 {len(df_out)} 行，{len(df_out.columns)} 列")
    if missing_cols:
        print(f"[提示] 以下对应字段在原表中不存在，已跳过：{missing_cols}")

    return output_path


# ========== 2. 清洗规则 Markdown ==========

def write_cleaning_rules(output_dir: Path) -> Path:
    """输出数据清洗规则说明文档"""
    output_path = output_dir / "数据清洗规则.md"

    content = """# 数据清洗规则说明

本文档汇总了从原始 Excel 文件到数据库表，再到知识图谱实体所使用的主要清洗规则，
用于数据质量核查与口径对齐。

## 一、入院信息表 → 数据库 admissions 表

### 1.1 字段映射规则

原始 Excel 中的列按以下规则映射为数据库字段（仅保留以下对应字段）：

| 原始字段 | 数据库字段 | 说明 |
|---------|-----------|------|
"""
    for src, dst in ADMISSION_FIELD_MAPPING.items():
        content += f"| `{src}` | `{dst}` | - |\n"

    content += """
### 1.2 类型转换规则

- `入院日期`：使用 `pd.to_datetime(..., errors="coerce")` 转换为日期类型，无法解析的值置为 `NaT`。
- `就诊流水号`、`患者ID`、`病案号`：统一按字符串类型读取，避免前导零丢失。

## 二、通用文本清洗规则（`services/kg_data_cleaner.py`）

### 2.1 基础清洗 `basic_clean`

适用于所有文本字段：

1. 空值、`NaN`、`None`、`NULL`、`-`、`未提及`、`未说明` 等统一视为空值，返回 `None`。
2. 去除首尾空白字符。
3. 将连续空白字符（空格、制表符等）归约为单个空格。
4. 中文括号 `（）` 转换为英文括号 `()`。
5. 去除无意义前缀：如 `:`、`：`、数字编号 `1.`、`1、` 等。

### 2.2 日期解析 `_parse_date`

- 支持 `pd.Timestamp` 与常见 `YYYY-MM-DD` 格式。
- `/` 统一替换为 `-`。
- 无法解析的日期返回 `None`。

### 2.3 数值解析

- 整型 `_to_int`：通过 `int(float(val))` 转换，失败返回 `None`。
- 浮点 `_to_float`：通过 `float(val)` 转换，失败返回 `None`。
- 年龄异常处理：若年龄大于 1000，则按天数除以 365 转换为年。

## 三、疾病 / 病症清洗规则

### 3.1 数据来源

- 入院信息表：`入院西医主要诊断1~23`、`入院中医主要诊断*`、`入院中医证型*`。
- 出院信息表：`出院西医主要诊断1~7`、`出院中医诊断`。

### 3.2 疾病归一化 `normalize_disease`

1. 先执行基础文本清洗。
2. 过滤非疾病关键词：
"""
    # 引入 KGDataCleaner 中的黑名单与同义词，避免硬编码冗余
    sys.path.insert(0, str(get_project_root()))
    from services.kg_data_cleaner import KGDataCleaner

    content += "\n   - " + "\n   - ".join(f"`{kw}`" for kw in KGDataCleaner.NON_DISEASE_KEYWORDS) + "\n"

    content += """
3. 若名称以 `"检查"` 结尾且长度不超过 8 个字符，也视为非疾病。
4. 组合诊断拆分：
   - 若诊断中含空格且后半部分以 `"证"` 结尾（如 `"肺积 痰瘀互结证"`），拆分为病名和证型。
   - 若诊断以顿号分隔且总长小于 50，按顿号拆分。
5. 同义词映射：常见疾病写法统一，部分示例见下表（完整列表见 `services/kg_data_cleaner.py` 中 `DISEASE_SYNONYMS`）：

| 原始写法 | 归一后写法 |
|---------|-----------|
"""
    sample_synonyms = list(KGDataCleaner.DISEASE_SYNONYMS.items())[:30]
    for src, dst in sample_synonyms:
        content += f"| `{src}` | `{dst}` |\n"
    content += "| ... | ... |\n"

    content += """
### 3.3 输出字段

清洗后的疾病节点包含：

- `name`：归一化后的疾病/病症名称。
- `type`：类型，如 `western`（西医）、`tcm`（中医）、`tcm_syndrome`（中医证型）。
- `category`：来源类别，如 `admission`（入院）、`discharge`（出院）。
- `frequency`：出现频次。

## 四、药品清洗规则

### 4.1 数据来源

- 入出院交医嘱表：`入出院交医嘱_肿瘤血液科1.xlsx`、`入出院交医嘱_肿瘤血液科2.xlsx`。
- 关键字段：`就诊流水号`、`医嘱项目名称`、`是否药品`、`单次剂量`、`单次剂量单位`、
  `使用频率名称`、`给药途径`、`医嘱开始时间`、`医嘱停止时间`、`医嘱类别`。

### 4.2 药品名称清洗 `clean_drug_name`

1. 去除采购标记后缀：
"""
    content += "\n   - " + "\n   - ".join(f"`{m}`" for m in KGDataCleaner.DRUG_MARKERS) + "\n"
    content += """
2. 去除规格后缀（如 `"（0.5g）"`、`"(100ml)"` 等）。

### 4.3 非药品过滤 `is_non_drug`

满足以下任一条件即过滤：

1. 原始 `是否药品` 字段明确标记为 `"否"`、`"0"`、`"False"`、`"否"`。
2. 名称命中非药品关键词黑名单，包括护理、膳食、检查/检验、操作/处置、行政/其他等类别：
"""
    content += "\n   - " + "\n   - ".join(f"`{kw}`" for kw in KGDataCleaner.NON_DRUG_KEYWORDS[:30]) + "\n"
    content += "   - ...（完整列表见 `services/kg_data_cleaner.py` 中 `NON_DRUG_KEYWORDS`）\n"

    content += """
### 4.4 输出字段

清洗后的药品节点包含：

- `name`：清洗后的药品名称。
- `original_names`：该药品对应的所有原始医嘱项目名称集合。
- `count`：出现频次。

## 五、其他实体的简要清洗规则

| 实体 | 关键清洗规则 |
|------|-------------|
| 主诉 | 去除 `"，下一周期化疗"`、`"，入院治疗"`、`"，复查"`、`"，随访"` 等治疗后缀；去除句末标点。 |
| 检查 | 保留 `标准化项目名称（匹配结果）`、`标准大类名称`、`检查部位`；`描述`、`诊断` 做基础清洗。 |
| 检验 | 保留 `标准项目名称`、`检验项目单位`、`参考范围`；结果值转浮点，提示信息判定是否异常。 |
| 手术 | 保留 `手术名称`、`手术类别`、`手术等级`、`麻醉方式`；名称去多余空格。 |
| 科室 | 从检查、检验、出院信息表中提取；去除多余空格。 |
| 患者/就诊 | 从入院信息表提取，患者按 `患者ID` 去重；就诊按 `就诊流水号` 去重。 |

## 六、知识图谱构建规则（`services/knowledge_graph_service.py`）

1. 节点按唯一键去重后批量导入 Neo4j：
   - `Patient`：`patient_id`
   - `Visit`：`visit_id`
   - `Disease`：`name`（实际为 `名称::类型` 组合键）
   - `Drug`：`name`
   - `ChiefComplaint`、`Exam`、`LabItem`、`Surgery`、`Department`：`name`
2. 关系去重后导入，主要关系包括：
   - `HAS_VISIT`：患者 → 就诊
   - `DIAGNOSED_WITH`：就诊 → 疾病
   - `CHIEF_COMPLAINT`：就诊 → 主诉
   - `PERFORMED_EXAM`：就诊 → 检查
   - `HAS_LAB_RESULT`：就诊 → 检验
   - `PRESCRIBED`：就诊 → 药品
   - `UNDERWENT`：就诊 → 手术
   - `IN_DEPARTMENT`：就诊 → 科室
   - `TREATS`：药品/手术 → 疾病（按同一次就诊的出院诊断与医嘱/手术自动推断）
"""

    output_path.write_text(content, encoding="utf-8")
    print(f"[输出] {output_path.name}")
    return output_path


# ========== 3. 知识图谱病症与药品输出 ==========

def load_cleaned_data() -> dict:
    """加载知识图谱清洗后的缓存数据"""
    cache_file = get_project_root() / "data" / "kg_cleaned" / "cleaned_data.json"
    if not cache_file.exists():
        print(f"[缓存不存在] {cache_file}，将执行全量清洗...")
        sys.path.insert(0, str(get_project_root()))
        from services.kg_data_cleaner import KGDataCleaner
        cleaner = KGDataCleaner()
        return cleaner.run_all(use_cache=False)

    print(f"[加载缓存] {cache_file}")
    with open(cache_file, "r", encoding="utf-8") as f:
        return json.load(f)


DISEASE_TYPE_CONFIG = {
    "western": ("知识图谱_病症_西医.txt", "西医"),
    "tcm": ("知识图谱_病症_中医.txt", "中医"),
    "tcm_syndrome": ("知识图谱_病症_中医证型.txt", "中医证型"),
}


def export_kg_diseases(data: dict, output_dir: Path) -> list[Path]:
    """按类型输出知识图谱中的疾病/病症列表（西医、中医、中医证型）"""
    diseases = data.get("diseases", [])
    output_paths = []

    for dtype, (filename, label) in DISEASE_TYPE_CONFIG.items():
        output_path = output_dir / filename
        subset = [d for d in diseases if d.get("type") == dtype]

        lines = []
        lines.append(f"# 知识图谱疾病/病症列表 - {label}（共 {len(subset)} 条）\n")
        lines.append("# 格式：名称 | 来源 | 频次\n")

        for d in sorted(subset, key=lambda x: (-x.get("frequency", 0), x.get("name", ""))):
            name = d.get("name", "")
            category = d.get("category", "")
            freq = d.get("frequency", 0)
            lines.append(f"{name} | {category} | {freq}\n")

        output_path.write_text("".join(lines), encoding="utf-8")
        print(f"[输出] {output_path.name}，共 {len(subset)} 条")
        output_paths.append(output_path)

    return output_paths


def export_kg_drugs(data: dict, output_dir: Path) -> Path:
    """输出知识图谱中的药品列表"""
    output_path = output_dir / "知识图谱_药品.txt"

    drugs = data.get("drugs", [])
    lines = []
    lines.append(f"# 知识图谱药品列表（共 {len(drugs)} 条）\n")
    lines.append("# 格式：药品名称 | 出现频次 | 原始名称数量\n")

    for d in sorted(drugs, key=lambda x: (-x.get("count", 0), x.get("name", ""))):
        name = d.get("name", "")
        count = d.get("count", 0)
        original_names = d.get("original_names", [])
        lines.append(f"{name} | {count} | {len(original_names)}\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    print(f"[输出] {output_path.name}，共 {len(drugs)} 条")
    return output_path


def main():
    output_dir = get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("数据质量核查输出")
    print("=" * 60)

    export_raw_admission_data(output_dir)
    write_cleaning_rules(output_dir)

    data = load_cleaned_data()
    export_kg_diseases(data, output_dir)
    export_kg_drugs(data, output_dir)

    # 清理旧版的合并病症文件（如存在）
    old_disease_file = output_dir / "知识图谱_病症.txt"
    if old_disease_file.exists():
        old_disease_file.unlink()

    print("=" * 60)
    print("[OK] 所有输出文件已生成，目录：", output_dir)
    print("=" * 60)


if __name__ == "__main__":
    main()
