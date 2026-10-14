# -*- coding: utf-8 -*-
"""将 scripts/sql_insert/*.sql（Navicat 导出，含 DROP/CREATE）改写为纯增量 INSERT。

- 去掉 DROP TABLE / CREATE TABLE，绝不动原始表
- INSERT 去掉首列 id（自增主键，避免与存量数据冲突），改为显式列名
- 输出覆盖原文件（git 可回溯）

用法: .venv/Scripts/python.exe -X utf8 scripts/transform_sql_insert.py
"""
import re
from pathlib import Path

DIR = Path(__file__).resolve().parent / "sql_insert"

# 各表的 INSERT 目标列（= 文件内 CREATE TABLE 的列去掉自增 id）
COLUMNS = {
    "patients": ["patient_id", "medical_record_no", "age", "gender", "marriage",
                 "occupation", "allergy_history", "created_at", "updated_at"],
    "visits": ["patient_id", "medical_record_no", "visit_no", "admission_date",
               "discharge_date", "length_of_stay", "department", "admission_count",
               "created_at", "updated_at"],
    "admissions": ["patient_id", "medical_record_no", "visit_no", "admission_date",
                   "age", "marriage", "occupation", "allergy_history",
                   "admission_record", "admission_count", "chief_complaint",
                   "present_illness", "past_history", "personal_history",
                   "family_history", "surgery_trauma_history",
                   "blood_transfusion_history", "marriage_childbirth_history",
                   "payment_method", "physical_exam", "specialist_exam",
                   "auxiliary_exam", "onset_solar_term", "tcm_four_diagnosis",
                   "admission_condition", "western_treatment_plan",
                   "tcm_treatment_plan", "emergency_western_diagnosis",
                   "emergency_tcm_diagnosis", "admission_western_diagnosis",
                   "admission_tcm_diagnosis", "diagnosis_basis_analysis",
                   "admission_tcm_syndrome", "admission_symptoms", "created_at"],
    "exams": ["patient_id", "visit_no", "apply_dept", "exam_part", "exam_no",
              "description", "diagnosis", "exam_date", "report_date",
              "medical_record_no", "diagnosis1", "diagnosis2", "diagnosis3",
              "diagnosis4", "diagnosis5", "standard_name", "standard_code",
              "standard_category", "created_at"],
    "labs": ["patient_id", "visit_no", "submit_dept", "sample_type", "sample_code",
             "submit_time", "test_time", "report_time", "result_value",
             "result_unit", "result_hint", "reference_range", "medical_record_no",
             "result_name", "standard_name", "standard_code", "quantitative_value",
             "item_name", "created_at"],
}

INSERT_RE = re.compile(r"INSERT INTO `(\w+)` VALUES \((.*)\);\s*$")


def split_values(body: str) -> list[str]:
    """按逗号切分 VALUES 元组（跳过单引号字符串内部）"""
    values, buf, in_str, i = [], [], False, 0
    while i < len(body):
        ch = body[i]
        if in_str:
            buf.append(ch)
            if ch == "\\" and i + 1 < len(body):  # 转义字符
                buf.append(body[i + 1])
                i += 2
                continue
            if ch == "'":
                in_str = False
        else:
            if ch == "'":
                in_str = True
                buf.append(ch)
            elif ch == ",":
                values.append("".join(buf).strip())
                buf = []
                i += 1
                continue
            else:
                buf.append(ch)
        i += 1
    values.append("".join(buf).strip())
    return values


def transform(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    out = [
        "/*",
        f" 增量数据导入（由 transform_sql_insert.py 从 Navicat 导出改写）",
        " 仅含 INSERT，不含 DROP/CREATE，不会破坏原有表结构与数据",
        " 目标库: hna    执行: python scripts/run_sql_insert.py",
        "*/",
        "",
        "SET FOREIGN_KEY_CHECKS=0;",
        "",
    ]
    n_insert = 0
    for line in lines:
        m = INSERT_RE.match(line.strip())
        if not m:
            continue
        table, body = m.group(1), m.group(2)
        cols = COLUMNS[table]
        values = split_values(body)
        assert len(values) == len(cols) + 1, \
            f"{path.name}: {table} 值数量({len(values)}) ≠ 列数量({len(cols)})+1"
        values = values[1:]  # 去掉自增 id
        col_sql = ", ".join(f"`{c}`" for c in cols)
        out.append(f"INSERT INTO `{table}` ({col_sql}) VALUES ({', '.join(values)});")
        n_insert += 1
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{path.name}: {n_insert} 条 INSERT")


if __name__ == "__main__":
    for f in ["patients.sql", "visits.sql", "admissions.sql", "exams.sql", "labs.sql"]:
        transform(DIR / f)
    print("全部改写完成")
