#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医院叙事生成助手 - 业务数据导入脚本
用法: python scripts/import_data.py [--batch-size 2000] [--clear] [--mysql-password xxx]

功能: 将 data/ 目录下的 Excel 文件导入到 MySQL 的 hna 数据库
说明: 大文件（如医嘱）会按 batch-size 分块读取并插入，避免内存溢出
"""

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd
import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_db_config(password=None):
    project_root = get_project_root()
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv(project_root / ".env.example")

    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": password or os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "hna"),
    }


def get_engine(config):
    url = (
        f"mysql+pymysql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
        f"?charset=utf8mb4"
    )
    return create_engine(url, pool_pre_ping=True)


def safe_to_datetime(series):
    return pd.to_datetime(series, errors="coerce")


def safe_to_date(series):
    return pd.to_datetime(series, errors="coerce").dt.date


def clean_dataframe(df, column_mapping, date_columns=None, datetime_columns=None):
    """根据映射重命名列，并转换日期类型"""
    if date_columns is None:
        date_columns = []
    if datetime_columns is None:
        datetime_columns = []

    available_cols = {k: v for k, v in column_mapping.items() if k in df.columns}
    df = df[list(available_cols.keys())].copy()
    df.rename(columns=available_cols, inplace=True)

    for col in date_columns:
        if col in df.columns:
            df[col] = safe_to_date(df[col])

    for col in datetime_columns:
        if col in df.columns:
            df[col] = safe_to_datetime(df[col])

    return df


def batch_insert(conn, table_name, df, batch_size=2000):
    """分批插入数据"""
    if df.empty:
        print(f"  [跳过] {table_name}: 无数据", flush=True)
        return 0

    total = len(df)
    df = df.where(pd.notnull(df), None)

    for i in range(0, total, batch_size):
        batch = df.iloc[i : i + batch_size]
        batch.to_sql(table_name, con=conn, if_exists="append", index=False, method="multi")
        if (i // batch_size + 1) % 10 == 0 or i + batch_size >= total:
            print(f"  {table_name}: {min(i + batch_size, total)} / {total}", flush=True)

    return total


def import_orders(conn, data_dir: Path, batch_size: int):
    """导入医嘱数据（分块读取大文件）"""
    mapping = {
        "患者ID": "patient_id",
        "病案号": "medical_record_no",
        "就诊流水号": "visit_no",
        "医嘱流水号": "order_no",
        "类型": "order_type",
        "医嘱下达时间": "order_time",
        "医嘱确认时间": "confirm_time",
        "医嘱下达科室名称": "order_dept",
        "医嘱开始时间": "start_time",
        "医嘱停止时间": "stop_time",
        "医嘱类别": "order_category",
        "医嘱组号": "order_group_no",
        "医嘱项目代码": "item_code",
        "医嘱项目名称": "item_name",
        "单次剂量": "single_dose",
        "单次剂量单位": "single_dose_unit",
        "药品剂型": "drug_form",
        "使用频率代码": "frequency_code",
        "使用频率名称": "frequency_name",
        "给药途径": "administration_route",
        "总数量": "total_quantity",
        "总数量单位": "total_unit",
        "医嘱备注": "remark",
        "药物潜在副作用": "side_effects",
        "是否药品": "is_drug",
        "生产厂家": "manufacturer",
        "药品商品名": "trade_name",
        "医嘱状态": "order_status",
    }

    files = [
        data_dir / "入出院交医嘱_肿瘤血液科1.xlsx",
        data_dir / "入出院交医嘱_肿瘤血液科2.xlsx",
    ]

    total = 0
    for file in files:
        if not file.exists():
            print(f"  [跳过] 文件不存在: {file}", flush=True)
            continue
        print(f"\n[读取] {file.name}", flush=True)
        df = pd.read_excel(file, dtype={"就诊流水号": str, "医嘱流水号": str, "患者ID": str, "病案号": str})
        df = clean_dataframe(df, mapping, datetime_columns=["order_time", "confirm_time", "start_time", "stop_time"])
        if "is_drug" in df.columns:
            df["is_drug"] = df["is_drug"].map({"是": 1, "否": 0, "Y": 1, "N": 0, "1": 1, "0": 0}).astype("Int64")
        total += batch_insert(conn, "orders", df, batch_size)
    return total


def import_surgeries(conn, data_dir: Path, batch_size: int):
    mapping = {
        "患者ID": "patient_id",
        "病案号": "medical_record_no",
        "就诊流水号": "visit_no",
        "医嘱流水号": "order_no",
        "手术类别": "surgery_category",
        "手术等级": "surgery_level",
        "operation_number（icu）": "operation_number",
        "麻醉方式": "anesthesia_method",
        "手术编码": "surgery_code",
        "手术名称": "surgery_name",
        "手术过程描述": "surgery_description",
        "手术开始时间": "start_time",
        "手术结束时间": "end_time",
        "手术持续时间": "duration",
    }

    file = data_dir / "入出院交手术_肿瘤血液科.xlsx"
    if not file.exists():
        print(f"  [跳过] 文件不存在: {file}", flush=True)
        return 0

    print(f"\n[读取] {file.name}", flush=True)
    df = pd.read_excel(file, dtype={"就诊流水号": str, "医嘱流水号": str, "患者ID": str, "病案号": str})
    df = clean_dataframe(df, mapping, datetime_columns=["start_time", "end_time"])
    return batch_insert(conn, "surgeries", df, batch_size)


def import_exams(conn, data_dir: Path, batch_size: int):
    mapping = {
        "患者ID": "patient_id",
        "就诊流水号": "visit_no",
        "申请科室": "apply_dept",
        "检查部位": "exam_part",
        "检查编号": "exam_no",
        "描述": "description",
        "诊断": "diagnosis",
        "检查日期": "exam_date",
        "报告日期": "report_date",
        "病案号": "medical_record_no",
        "诊断1": "diagnosis1",
        "诊断2": "diagnosis2",
        "诊断3": "diagnosis3",
        "诊断4": "diagnosis4",
        "诊断5": "diagnosis5",
        "标准化项目名称（匹配结果）": "standard_name",
        "编码": "standard_code",
        "标准大类名称": "standard_category",
    }

    file = data_dir / "入出院交检查_肿瘤血液科.xlsx"
    if not file.exists():
        print(f"  [跳过] 文件不存在: {file}", flush=True)
        return 0

    print(f"\n[读取] {file.name}", flush=True)
    df = pd.read_excel(file, dtype={"就诊流水号": str, "患者ID": str, "病案号": str, "检查编号": str})
    df = clean_dataframe(df, mapping, date_columns=["exam_date", "report_date"])
    return batch_insert(conn, "exams", df, batch_size)


def import_labs(conn, data_dir: Path, batch_size: int):
    mapping = {
        "患者ID": "patient_id",
        "就诊流水号": "visit_no",
        "送检科室": "submit_dept",
        "样本种类": "sample_type",
        "样本编码": "sample_code",
        "送检时间": "submit_time",
        "检验时间": "test_time",
        "报告时间": "report_time",
        "检验项目结果": "result_value",
        "检验项目单位": "result_unit",
        "检验项目提示": "result_hint",
        "参考范围": "reference_range",
        "病案号": "medical_record_no",
        "检验结果名称": "result_name",
        "标准项目名称": "standard_name",
        "标准编码": "standard_code",
        "结果定量化": "quantitative_value",
        "检验项目名称": "item_name",
    }

    file = data_dir / "入出院交检验_肿瘤血液科.xlsx"
    if not file.exists():
        print(f"  [跳过] 文件不存在: {file}", flush=True)
        return 0

    print(f"\n[读取] {file.name}", flush=True)
    df = pd.read_excel(file, dtype={"就诊流水号": str, "患者ID": str, "病案号": str, "样本编码": str})
    df = clean_dataframe(df, mapping, datetime_columns=["submit_time", "test_time", "report_time"])
    if "quantitative_value" in df.columns:
        df["quantitative_value"] = pd.to_numeric(df["quantitative_value"], errors="coerce")
    return batch_insert(conn, "labs", df, batch_size)


def import_admissions(conn, data_dir: Path, batch_size: int):
    mapping = {
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

    file = data_dir / "入院信息表_肿瘤血液科.xlsx"
    if not file.exists():
        print(f"  [跳过] 文件不存在: {file}", flush=True)
        return 0

    print(f"\n[读取] {file.name}", flush=True)
    df = pd.read_excel(file, dtype={"就诊流水号": str, "患者ID": str, "病案号": str})
    df = clean_dataframe(df, mapping, date_columns=["admission_date"])
    return batch_insert(conn, "admissions", df, batch_size)


def import_discharges(conn, data_dir: Path, batch_size: int):
    mapping = {
        "患者ID": "patient_id",
        "病案号": "medical_record_no",
        "就诊流水号": "visit_no",
        "年龄": "age",
        "入院日期": "admission_date",
        "出院日期": "discharge_date",
        "住院天数": "length_of_stay",
        "入院情况": "admission_condition",
        "病情描述": "disease_description",
        "住院治疗经过": "hospital_course",
        "西医诊疗经过": "western_treatment_course",
        "中医诊疗经过": "tcm_treatment_course",
        "出院西医主要诊断1": "discharge_western_diagnosis1",
        "出院西医主要诊断2": "discharge_western_diagnosis2",
        "出院西医主要诊断3": "discharge_western_diagnosis3",
        "出院西医主要诊断4": "discharge_western_diagnosis4",
        "出院西医主要诊断5": "discharge_western_diagnosis5",
        "出院西医主要诊断6": "discharge_western_diagnosis6",
        "出院西医主要诊断7": "discharge_western_diagnosis7",
        "出院中医诊断": "discharge_tcm_diagnosis",
        "出院中医证型": "discharge_tcm_syndrome",
        "出院情况": "discharge_condition",
        "出院医嘱": "discharge_orders",
        "出院用药医嘱": "discharge_medication",
        "出院饮食医嘱": "discharge_diet",
        "出院其他医嘱": "discharge_other_orders",
        "出院结局": "discharge_outcome",
        "出院科室": "discharge_dept",
    }

    file = data_dir / "出院信息表_肿瘤血液科.xlsx"
    if not file.exists():
        print(f"  [跳过] 文件不存在: {file}", flush=True)
        return 0

    print(f"\n[读取] {file.name}", flush=True)
    df = pd.read_excel(file, dtype={"就诊流水号": str, "患者ID": str, "病案号": str})
    df = clean_dataframe(df, mapping, date_columns=["admission_date", "discharge_date"])
    return batch_insert(conn, "discharges", df, batch_size)


def rebuild_patients_and_visits(conn):
    """从入院/出院数据重建患者基础信息和就诊记录"""
    print("\n[重建] 患者基础信息表 patients", flush=True)
    conn.execute(text("TRUNCATE TABLE patients"))
    conn.execute(text("""
        INSERT INTO patients (patient_id, medical_record_no, age, marriage, occupation, allergy_history)
        SELECT patient_id, MAX(medical_record_no), MAX(age), MAX(marriage), MAX(occupation), MAX(allergy_history)
        FROM (
            SELECT patient_id, medical_record_no, age, marriage, occupation, allergy_history FROM admissions
            UNION ALL
            SELECT patient_id, medical_record_no, age, NULL, NULL, NULL FROM discharges
        ) t
        GROUP BY patient_id
    """))

    print("[重建] 就诊记录表 visits", flush=True)
    conn.execute(text("TRUNCATE TABLE visits"))
    conn.execute(text("""
        INSERT INTO visits (patient_id, medical_record_no, visit_no, admission_date, discharge_date, length_of_stay, admission_count)
        SELECT d.patient_id, d.medical_record_no, d.visit_no, d.admission_date, d.discharge_date, d.length_of_stay, a.admission_count
        FROM discharges d
        LEFT JOIN admissions a ON d.patient_id = a.patient_id AND d.visit_no = a.visit_no
        ON DUPLICATE KEY UPDATE
            discharge_date = VALUES(discharge_date),
            length_of_stay = VALUES(length_of_stay),
            admission_count = VALUES(admission_count)
    """))
    conn.execute(text("""
        INSERT IGNORE INTO visits (patient_id, medical_record_no, visit_no, admission_date, admission_count)
        SELECT patient_id, medical_record_no, visit_no, admission_date, admission_count FROM admissions
    """))


def main():
    parser = argparse.ArgumentParser(description="将 Excel 业务数据导入 MySQL")
    parser.add_argument("--batch-size", type=int, default=2000, help="每批插入行数，默认 2000")
    parser.add_argument("--clear", action="store_true", help="导入前清空业务表")
    parser.add_argument("--mysql-password", default=None, help="MySQL 密码（覆盖 .env 配置）")
    args = parser.parse_args()

    config = load_db_config(password=args.mysql_password)
    engine = get_engine(config)
    data_dir = get_project_root() / "data"

    print("=" * 60, flush=True)
    print("医院叙事生成助手 - 业务数据导入", flush=True)
    print("=" * 60, flush=True)
    print(f"数据库: {config['database']} @ {config['host']}:{config['port']}", flush=True)
    print(f"数据目录: {data_dir}", flush=True)
    print(f"批次大小: {args.batch_size}", flush=True)
    print("=" * 60, flush=True)

    start_time = time.time()
    stats = {}
    try:
        with engine.begin() as conn:
            if args.clear:
                print("\n[清空] 业务数据表", flush=True)
                for table in ["orders", "surgeries", "exams", "labs", "admissions", "discharges", "visits", "patients"]:
                    conn.execute(text(f"TRUNCATE TABLE {table}"))

            stats["orders"] = import_orders(conn, data_dir, args.batch_size)
            stats["surgeries"] = import_surgeries(conn, data_dir, args.batch_size)
            stats["exams"] = import_exams(conn, data_dir, args.batch_size)
            stats["labs"] = import_labs(conn, data_dir, args.batch_size)
            stats["admissions"] = import_admissions(conn, data_dir, args.batch_size)
            stats["discharges"] = import_discharges(conn, data_dir, args.batch_size)

            rebuild_patients_and_visits(conn)

        elapsed = time.time() - start_time
        print("\n" + "=" * 60, flush=True)
        print("导入统计", flush=True)
        print("=" * 60, flush=True)
        for table, count in stats.items():
            print(f"  {table}: {count} 条", flush=True)
        print(f"  耗时: {elapsed:.1f} 秒", flush=True)
        print("=" * 60, flush=True)
        print("[OK] 业务数据导入完成", flush=True)
    except Exception as e:
        print(f"\n[失败] 导入失败: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
