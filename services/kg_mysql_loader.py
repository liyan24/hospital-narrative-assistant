"""
知识图谱 MySQL 数据加载模块
从 MySQL 业务表读取数据，复用 KGDataCleaner 的纯函数做同样的归一化，
输出结构与 KGDataCleaner.run_all() 完全一致，供 KnowledgeGraphService.build_all 直接消费。
"""

import json
import os
import re
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from database.mysql_client import mysql_client
from services.kg_data_cleaner import KGDataCleaner


class KGMysqlLoader:
    """从 MySQL 加载并清洗知识图谱数据（口径与 Excel 版 KGDataCleaner 一致）"""

    def __init__(self, stats_dir: str = "data/kg_cleaned"):
        self.stats_dir = stats_dir
        os.makedirs(stats_dir, exist_ok=True)
        self.engine = mysql_client.engine

    def _read(self, sql: str) -> pd.DataFrame:
        return pd.read_sql(sql, self.engine)

    # ========== 患者与就诊 ==========

    def load_patients_and_visits(self) -> Tuple[Dict, Dict]:
        """对应 KGDataCleaner.clean_patients_and_visits"""
        print("Loading patients and visits from MySQL...")
        df = self._read(
            "SELECT patient_id, medical_record_no, age, marriage, occupation, allergy_history FROM patients"
        )
        patients = {}
        for _, row in df.iterrows():
            patient_id = KGDataCleaner.basic_clean(row.get("patient_id"))
            if not patient_id or patient_id in patients:
                continue
            # 实测 MySQL patients.age 仍是以天为单位（1460~36500），并未在导入时换算为岁，
            # 因此保留与 Excel 版清洗器一致的 age > 1000 -> //365 兜底换算
            age = KGDataCleaner._to_int(row.get("age"))
            if age and age > 1000:
                age = age // 365
            patients[patient_id] = {
                "patient_id": patient_id,
                "medical_record_no": KGDataCleaner.basic_clean(row.get("medical_record_no")),
                "age": age,
                "marital_status": KGDataCleaner.basic_clean(row.get("marriage")),
                "occupation": KGDataCleaner.basic_clean(row.get("occupation")),
                "allergy_history": KGDataCleaner.basic_clean(row.get("allergy_history")),
            }

        # 对应 Excel 版：入院信息表提供就诊基础信息+主诉，出院信息表补充出院日期/住院天数
        df_v = self._read(
            """
            SELECT a.visit_no, a.patient_id, a.admission_date, a.chief_complaint,
                   d.discharge_date, d.length_of_stay
            FROM admissions a
            LEFT JOIN discharges d ON a.visit_no = d.visit_no
            """
        )
        visits = {}
        for _, row in df_v.iterrows():
            visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
            patient_id = KGDataCleaner.basic_clean(row.get("patient_id"))
            if not visit_id or not patient_id or visit_id in visits:
                continue
            v = {
                "visit_id": visit_id,
                "patient_id": patient_id,
                "admission_date": KGDataCleaner._parse_date(row.get("admission_date")),
                "chief_complaint": KGDataCleaner.normalize_complaint(row.get("chief_complaint")),
            }
            discharge_date = KGDataCleaner._parse_date(row.get("discharge_date"))
            if discharge_date:
                v["discharge_date"] = discharge_date
            los = KGDataCleaner._to_int(row.get("length_of_stay"))
            if los is not None:
                v["length_of_stay"] = los
            visits[visit_id] = v

        print(f"  Patients: {len(patients)}, Visits: {len(visits)}")
        return patients, visits

    # ========== 疾病诊断 ==========

    def load_diseases(self) -> Tuple[Dict, List]:
        """对应 KGDataCleaner.clean_diseases"""
        print("Loading diseases from MySQL...")
        disease_nodes = defaultdict(lambda: {"count": 0, "types": set(), "categories": set()})
        diagnosis_rels = []

        # ---------- 入院诊断 ----------
        # 字段映射差异：Excel 入院信息表有「入院西医主要诊断1~23」「入院中医主要诊断*」
        # 「入院中医证型*」等结构化多列；MySQL admissions 裁剪为单文本字段
        # admission_western_diagnosis / admission_tcm_diagnosis / admission_tcm_syndrome。
        # 西医单字段视为原「主要诊断1」（is_main=True），仍走 split_combined_diagnosis 拆分组合诊断。
        df = self._read(
            "SELECT visit_no, admission_western_diagnosis, admission_tcm_diagnosis, admission_tcm_syndrome FROM admissions"
        )
        for _, row in df.iterrows():
            visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
            if not visit_id:
                continue

            raw = KGDataCleaner.basic_clean(row.get("admission_western_diagnosis"))
            if raw:
                for part in KGDataCleaner.split_combined_diagnosis(raw):
                    norm = KGDataCleaner.normalize_disease(part)
                    if norm:
                        key = (norm, "western")
                        disease_nodes[key]["count"] += 1
                        disease_nodes[key]["types"].add("western")
                        disease_nodes[key]["categories"].add("admission")
                        diagnosis_rels.append((visit_id, norm, "western", "admission", True))

            raw = KGDataCleaner.basic_clean(row.get("admission_tcm_diagnosis"))
            if raw:
                # 与 Excel 版一致：中医诊断不做组合拆分，直接归一化
                norm = KGDataCleaner.normalize_disease(raw)
                if norm:
                    key = (norm, "tcm")
                    disease_nodes[key]["count"] += 1
                    disease_nodes[key]["types"].add("tcm")
                    disease_nodes[key]["categories"].add("admission")
                    diagnosis_rels.append((visit_id, norm, "tcm", "admission", True))

            raw = KGDataCleaner.basic_clean(row.get("admission_tcm_syndrome"))
            if raw:
                # 与 Excel 版一致：入院中医证型只建 Disease 节点（type=tcm_syndrome），不产生诊断关系
                norm = KGDataCleaner.normalize_disease(raw)
                if norm:
                    key = (norm, "tcm_syndrome")
                    disease_nodes[key]["count"] += 1
                    disease_nodes[key]["types"].add("tcm_syndrome")
                    disease_nodes[key]["categories"].add("admission")

        # ---------- 出院诊断 ----------
        # discharges 保留了 discharge_western_diagnosis1~7 结构化列，与 Excel 一一对应
        diag_cols = ", ".join(f"discharge_western_diagnosis{i}" for i in range(1, 8))
        df = self._read(f"SELECT visit_no, {diag_cols}, discharge_tcm_diagnosis FROM discharges")
        for _, row in df.iterrows():
            visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
            if not visit_id:
                continue

            for i in range(1, 8):
                raw = KGDataCleaner.basic_clean(row.get(f"discharge_western_diagnosis{i}"))
                if raw:
                    for part in KGDataCleaner.split_combined_diagnosis(raw):
                        norm = KGDataCleaner.normalize_disease(part)
                        if norm:
                            key = (norm, "western")
                            disease_nodes[key]["count"] += 1
                            disease_nodes[key]["types"].add("western")
                            disease_nodes[key]["categories"].add("discharge")
                            diagnosis_rels.append((visit_id, norm, "western", "discharge", i == 1))

            raw = KGDataCleaner.basic_clean(row.get("discharge_tcm_diagnosis"))
            if raw:
                norm = KGDataCleaner.normalize_disease(raw)
                if norm:
                    key = (norm, "tcm")
                    disease_nodes[key]["count"] += 1
                    disease_nodes[key]["types"].add("tcm")
                    disease_nodes[key]["categories"].add("discharge")
                    diagnosis_rels.append((visit_id, norm, "tcm", "discharge", True))

        nodes = {}
        for (name, dtype), info in disease_nodes.items():
            nodes[name] = {
                "name": name,
                "type": dtype,
                "category": ",".join(sorted(info["categories"])),
                "frequency": info["count"],
            }

        print(f"  Raw disease entries cleaned to {len(nodes)} unique diseases")
        return nodes, diagnosis_rels

    # ========== 主诉 ==========

    def load_complaints(self) -> Tuple[Dict, List]:
        """对应 KGDataCleaner.clean_complaints"""
        print("Loading complaints from MySQL...")
        df = self._read("SELECT visit_no, chief_complaint FROM admissions")
        complaint_nodes = {}
        complaint_rels = []

        for _, row in df.iterrows():
            visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
            raw = KGDataCleaner.basic_clean(row.get("chief_complaint"))
            if not visit_id or not raw:
                continue
            cleaned = KGDataCleaner.normalize_complaint(raw)
            if not cleaned:
                continue
            if cleaned not in complaint_nodes:
                complaint_nodes[cleaned] = {"name": cleaned, "count": 0}
            complaint_nodes[cleaned]["count"] += 1
            complaint_rels.append((visit_id, cleaned))

        print(f"  Unique complaints after cleaning: {len(complaint_nodes)}")
        return complaint_nodes, complaint_rels

    # ========== 检查 ==========

    def load_exams(self) -> Tuple[Dict, List]:
        """对应 KGDataCleaner.clean_exams"""
        print("Loading exams from MySQL...")
        # 字段映射差异：MySQL exams 裁剪后只保留 diagnosis1~5 等列，
        # 但 KG 用到的 standard_name / standard_category / exam_part / 日期 / 描述 / 诊断 均完整保留
        df = self._read(
            "SELECT visit_no, standard_name, standard_category, exam_part, "
            "exam_date, report_date, description, diagnosis FROM exams"
        )
        exam_nodes = {}
        exam_rels = []

        for _, row in df.iterrows():
            visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
            name = KGDataCleaner.basic_clean(row.get("standard_name"))
            if not visit_id or not name:
                continue
            name = re.sub(r"\s+", " ", name).strip()

            if name not in exam_nodes:
                exam_nodes[name] = {
                    "name": name,
                    "category": KGDataCleaner.basic_clean(row.get("standard_category")),
                    "body_part": KGDataCleaner.basic_clean(row.get("exam_part")),
                }

            exam_rels.append((
                visit_id,
                name,
                {
                    "exam_date": KGDataCleaner._parse_date(row.get("exam_date")),
                    "report_date": KGDataCleaner._parse_date(row.get("report_date")),
                    "description": KGDataCleaner.basic_clean(row.get("description")),
                    "diagnosis": KGDataCleaner.basic_clean(row.get("diagnosis")),
                }
            ))

        print(f"  Unique exams: {len(exam_nodes)}")
        return exam_nodes, exam_rels

    # ========== 检验 ==========

    def load_labs(self) -> Tuple[Dict, List]:
        """对应 KGDataCleaner.clean_labs"""
        print("Loading labs from MySQL...")
        df = self._read(
            "SELECT visit_no, standard_name, item_name, result_unit, reference_range, "
            "result_value, result_hint FROM labs"
        )
        lab_nodes = {}
        lab_rels = []

        for _, row in df.iterrows():
            visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
            name = KGDataCleaner.basic_clean(row.get("standard_name"))
            if not name:
                # 标准项目名为空时（如外院导入数据未做标准化），回退用检验项目名称，
                # 去掉开头的 '*' 标记
                item = KGDataCleaner.basic_clean(row.get("item_name"))
                if item:
                    name = item.lstrip("*").strip()
            if not visit_id or not name:
                continue
            name = re.sub(r"\s+", " ", name).strip()
            unit = KGDataCleaner.basic_clean(row.get("result_unit"))
            ref = KGDataCleaner.basic_clean(row.get("reference_range"))

            if name not in lab_nodes:
                lab_nodes[name] = {
                    "name": name,
                    "unit": unit,
                    "reference_range": ref,
                }

            val = KGDataCleaner._to_float(row.get("result_value"))
            hint = KGDataCleaner.basic_clean(row.get("result_hint"))
            abnormal = None
            if hint:
                if any(k in hint for k in ["高", "低", "异常", "↑", "↓"]):
                    abnormal = True
                elif "正常" in hint:
                    abnormal = False

            lab_rels.append((
                visit_id,
                name,
                {
                    "value": val,
                    "unit": unit,
                    "reference_range": ref,
                    "abnormal_flag": abnormal,
                    "hint": hint,
                }
            ))

        print(f"  Unique lab items: {len(lab_nodes)}")
        return lab_nodes, lab_rels

    # ========== 药品医嘱 ==========

    def load_drugs(self) -> Tuple[Dict, List]:
        """对应 KGDataCleaner.clean_drugs"""
        print("Loading drugs from MySQL (orders table)...")
        # orders 表 114 万行，只 SELECT KG 需要的列以控制内存；
        # is_drug 列在 MySQL 中全为 NULL，与 Excel 版一致走 is_non_drug 关键词过滤兜底
        df = self._read(
            "SELECT visit_no, item_name, is_drug, single_dose, single_dose_unit, "
            "frequency_name, administration_route, start_time, stop_time, order_category "
            "FROM orders"
        )
        drug_nodes = {}
        prescription_rels = []
        total_orders = 0
        filtered_orders = 0

        for _, row in df.iterrows():
            total_orders += 1
            visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
            raw_name = KGDataCleaner.basic_clean(row.get("item_name"))
            # Excel 的「是否药品」为中文"是/否"，MySQL 为 TINYINT 0/1（实际全 NULL），转成相同口径的标记
            raw_flag = row.get("is_drug")
            if raw_flag is None or pd.isna(raw_flag):
                is_drug_flag = None
            else:
                is_drug_flag = "否" if int(raw_flag) == 0 else "是"

            if not visit_id or not raw_name:
                filtered_orders += 1
                continue

            cleaned = KGDataCleaner.clean_drug_name(raw_name)
            if not cleaned:
                filtered_orders += 1
                continue

            if KGDataCleaner.is_non_drug(cleaned, is_drug_flag):
                filtered_orders += 1
                continue

            if cleaned not in drug_nodes:
                drug_nodes[cleaned] = {
                    "name": cleaned,
                    "original_names": set(),
                    "count": 0,
                }
            drug_nodes[cleaned]["original_names"].add(raw_name)
            drug_nodes[cleaned]["count"] += 1

            prescription_rels.append((
                visit_id,
                cleaned,
                {
                    "dosage": KGDataCleaner.basic_clean(row.get("single_dose")),
                    "dosage_unit": KGDataCleaner.basic_clean(row.get("single_dose_unit")),
                    "frequency": KGDataCleaner.basic_clean(row.get("frequency_name")),
                    "route": KGDataCleaner.basic_clean(row.get("administration_route")),
                    "start_date": KGDataCleaner._parse_date(row.get("start_time")),
                    "end_date": KGDataCleaner._parse_date(row.get("stop_time")),
                    "order_category": KGDataCleaner.basic_clean(row.get("order_category")),
                }
            ))

        for name, info in drug_nodes.items():
            info["original_names"] = list(info["original_names"])

        print(f"  Orders: {total_orders}, Filtered non-drugs: {filtered_orders}, Unique drugs: {len(drug_nodes)}")
        return drug_nodes, prescription_rels

    # ========== 手术 ==========

    def load_surgeries(self) -> Tuple[Dict, List]:
        """对应 KGDataCleaner.clean_surgeries"""
        print("Loading surgeries from MySQL...")
        df = self._read(
            "SELECT visit_no, surgery_name, surgery_category, surgery_level, "
            "anesthesia_method, start_time, end_time, surgery_description FROM surgeries"
        )
        surgery_nodes = {}
        surgery_rels = []

        for _, row in df.iterrows():
            visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
            name = KGDataCleaner.basic_clean(row.get("surgery_name"))
            if not visit_id or not name:
                continue
            name = re.sub(r"\s+", " ", name).strip()

            if name not in surgery_nodes:
                surgery_nodes[name] = {
                    "name": name,
                    "category": KGDataCleaner.basic_clean(row.get("surgery_category")),
                    "level": KGDataCleaner.basic_clean(row.get("surgery_level")),
                    "anesthesia_method": KGDataCleaner.basic_clean(row.get("anesthesia_method")),
                }

            surgery_rels.append((
                visit_id,
                name,
                {
                    "start_date": KGDataCleaner._parse_date(row.get("start_time")),
                    "end_date": KGDataCleaner._parse_date(row.get("end_time")),
                    "description": KGDataCleaner.basic_clean(row.get("surgery_description")),
                }
            ))

        print(f"  Unique surgeries: {len(surgery_nodes)}")
        return surgery_nodes, surgery_rels

    # ========== 科室 ==========

    def load_departments(self) -> Tuple[Set, List]:
        """对应 KGDataCleaner.clean_departments"""
        print("Loading departments from MySQL...")
        departments = set()
        dept_rels = []

        # 与 Excel 版一致：科室来自 检查申请科室 / 检验送检科室 / 出院科室 三个来源
        for sql, dept_col in [
            ("SELECT visit_no, apply_dept AS dept FROM exams", "dept"),
            ("SELECT visit_no, submit_dept AS dept FROM labs", "dept"),
            ("SELECT visit_no, discharge_dept AS dept FROM discharges", "dept"),
        ]:
            df = self._read(sql)
            for _, row in df.iterrows():
                visit_id = KGDataCleaner.basic_clean(row.get("visit_no"))
                dept = KGDataCleaner.basic_clean(row.get(dept_col))
                if visit_id and dept:
                    dept = re.sub(r"\s+", " ", dept).strip()
                    departments.add(dept)
                    dept_rels.append((visit_id, dept))

        print(f"  Unique departments: {len(departments)}")
        return departments, dept_rels

    # ========== 全量加载 ==========

    def run_all(self) -> Dict:
        """执行全量加载，返回结构与 KGDataCleaner.run_all() 完全一致"""
        start = time.time()
        print("=" * 60)
        print("Running full KG data loading pipeline (MySQL source)")
        print("=" * 60)

        patients, visits = self.load_patients_and_visits()
        diseases, diag_rels = self.load_diseases()
        complaints, complaint_rels = self.load_complaints()
        exams, exam_rels = self.load_exams()
        labs, lab_rels = self.load_labs()
        drugs, drug_rels = self.load_drugs()
        surgeries, surgery_rels = self.load_surgeries()
        departments, dept_rels = self.load_departments()

        report = {
            "patients": list(patients.values()),
            "visits": list(visits.values()),
            "diseases": list(diseases.values()),
            "complaints": list(complaints.values()),
            "exams": list(exams.values()),
            "labs": list(labs.values()),
            "drugs": list(drugs.values()),
            "surgeries": list(surgeries.values()),
            "departments": [{"name": d} for d in departments],
            "relations": {
                "has_visit": [(v["patient_id"], v["visit_id"]) for v in visits.values()],
                "diagnosis": [{"visit_id": r[0], "disease_name": r[1], "type": r[2], "diagnosis_type": r[3], "is_main": r[4]} for r in diag_rels],
                "chief_complaint": [{"visit_id": r[0], "complaint": r[1]} for r in complaint_rels],
                "exam": [{"visit_id": r[0], "exam_name": r[1], **r[2]} for r in exam_rels],
                "lab": [{"visit_id": r[0], "lab_name": r[1], **r[2]} for r in lab_rels],
                "prescription": [{"visit_id": r[0], "drug_name": r[1], **r[2]} for r in drug_rels],
                "surgery": [{"visit_id": r[0], "surgery_name": r[1], **r[2]} for r in surgery_rels],
                "department": [{"visit_id": r[0], "dept_name": r[1]} for r in dept_rels],
            },
            "stats": {
                "patient_count": len(patients),
                "visit_count": len(visits),
                "disease_count": len(diseases),
                "complaint_count": len(complaints),
                "exam_count": len(exams),
                "lab_count": len(labs),
                "drug_count": len(drugs),
                "surgery_count": len(surgeries),
                "department_count": len(departments),
                "diagnosis_rel_count": len(diag_rels),
                "prescription_rel_count": len(drug_rels),
            }
        }

        elapsed = time.time() - start
        # MySQL 本身就是持久层，不写全量 json 缓存；仅记录本次加载统计
        stats_file = os.path.join(self.stats_dir, "mysql_build_stats.json")
        stats_payload = {"source": "mysql", "load_seconds": round(elapsed, 1), **report["stats"]}
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats_payload, f, ensure_ascii=False, indent=2)

        print("=" * 60)
        print("Loading Summary (MySQL):")
        for k, v in report["stats"].items():
            print(f"  {k}: {v}")
        print(f"  load_seconds: {elapsed:.1f}")
        print(f"  stats written to {stats_file}")
        print("=" * 60)

        return report
