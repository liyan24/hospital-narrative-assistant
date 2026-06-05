"""
知识图谱数据清洗模块
对原始Excel数据进行清洗、归并、过滤，输出标准化的实体和关系数据
"""

import pandas as pd
import re
import json
import os
from typing import List, Dict, Set, Tuple, Optional
from collections import Counter, defaultdict


class KGDataCleaner:
    """医疗知识图谱数据清洗器"""

    # ========== 配置常量 ==========

    # 非疾病关键词黑名单（这些出现在诊断中但不是疾病）
    NON_DISEASE_KEYWORDS = [
        "病理学检查", "影像学检查", "心电图检查", "B超检查", "超声检查",
        "CT检查", "MRI检查", "核磁共振检查", "X线检查", "放射学检查",
        "实验室检查", "血常规检查", "尿常规检查", "粪常规检查",
        "术前检查", "术后检查", "入院检查", "出院检查",
        "产前检查", "产后检查", "婚前医学检查",
        "待查", "原因待查", "待排", "排除", "筛查",
        "随访", "复查", "观察", "监测", "评估",
        "健康查体", "健康体检", "体检",
    ]

    # 非药品关键词黑名单
    NON_DRUG_KEYWORDS = [
        # 护理
        "护理", "级护理", "特级护理", "一级护理", "二级护理", "三级护理",
        "护理常规", "专科护理", "基础护理",
        # 膳食
        "普食", "流质", "半流质", "软食", "禁食", "鼻饲", "肠内营养", "肠外营养",
        "糖尿病饮食", "低盐饮食", "低脂饮食", "高蛋白饮食",
        # 检查/检验
        "检查", "超声", "CT", "MRI", "核磁", "X线", "胸片", "拍片",
        "心电图", "动态心电图", "心电监护", "血压监测", "血氧监测",
        "血常规", "尿常规", "粪常规", "血生化", "肝功能", "肾功能",
        "电解质", "血糖", "血脂", "凝血", "D-二聚体", "肿瘤标志物",
        "细胞分析", "血细胞分析", "C反应蛋白", "降钙素原",
        # 操作/处置
        "静脉注射", "静脉采血", "静脉输液", "皮下注射", "肌肉注射",
        "留置针", "导尿", "灌肠", "吸氧", "雾化吸入", "胸腔穿刺",
        "腹腔穿刺", "腰椎穿刺", "骨髓穿刺", "气管切开", "心肺复苏",
        # 行政/其他
        "今日出院", "明日出院", "留陪", "陪护", "告病危", "告病重",
        "会诊", "转科", "转院", "死亡", "抢救",
    ]

    # 药品采购标记后缀
    DRUG_MARKERS = ["（中选）", "(中选)", "【中选】", "[中选]", "（国采）", "(国采)"]

    # 疾病同义词映射表（基于数据观察的人工规则）
    DISEASE_SYNONYMS = {
        # 血证相关
        "血证类": "血证",
        "血症": "血证",
        "血证病": "血证",
        # 积聚相关
        "积聚": "积聚类病",
        # 癌病相关
        "内科癌病": "癌病",
        "癌病": "癌病",
        # 白血病（细分保留，但统一写法）
        "急性白血病": "急性白血病",
        "慢性白血病": "慢性白血病",
        # 淋巴瘤
        "非霍奇金淋巴瘤": "非霍奇金淋巴瘤",
        "霍奇金淋巴瘤": "霍奇金淋巴瘤",
        "淋巴瘤": "淋巴瘤",
        # 贫血
        "缺铁性贫血": "缺铁性贫血",
        "巨幼细胞性贫血": "巨幼细胞性贫血",
        "溶血性贫血": "溶血性贫血",
        "再生障碍性贫血": "再生障碍性贫血",
        "肾性贫血": "肾性贫血",
        # 骨髓瘤
        "多发性骨髓瘤": "多发性骨髓瘤",
        # 高血压
        "高血压病": "高血压",
        "原发性高血压": "高血压",
        "继发性高血压": "继发性高血压",
        # 糖尿病
        "2型糖尿病": "2型糖尿病",
        "1型糖尿病": "1型糖尿病",
        "糖尿病": "糖尿病",
        # 冠心病
        "冠心病": "冠状动脉粥样硬化性心脏病",
        "缺血性心肌病": "缺血性心肌病",
        # 脑血管
        "脑梗塞": "脑梗死",
        "脑梗": "脑梗死",
        "脑出血": "脑出血",
        # 肺炎
        "肺部感染": "肺部感染",
        "肺炎": "肺炎",
        "支气管肺炎": "支气管肺炎",
        # 肝相关
        "肝硬化": "肝硬化",
        "乙肝肝硬化": "乙肝肝硬化",
        "丙肝肝硬化": "丙肝肝硬化",
        "酒精性肝硬化": "酒精性肝硬化",
        # 恶性肿瘤细分（保留部位细分，但统一写法）
        "肺癌": "肺恶性肿瘤",
        "右肺癌": "右肺恶性肿瘤",
        "左肺癌": "左肺恶性肿瘤",
        "肝癌": "肝恶性肿瘤",
        "胃癌": "胃恶性肿瘤",
        "食管癌": "食管恶性肿瘤",
        "肠癌": "结肠恶性肿瘤",
        "结肠癌": "结肠恶性肿瘤",
        "直肠癌": "直肠恶性肿瘤",
        "乳腺癌": "乳腺恶性肿瘤",
        "宫颈癌": "宫颈恶性肿瘤",
        "卵巢癌": "卵巢恶性肿瘤",
        "前列腺癌": "前列腺恶性肿瘤",
        "膀胱癌": "膀胱恶性肿瘤",
        "胰腺癌": "胰腺恶性肿瘤",
        "甲状腺癌": "甲状腺恶性肿瘤",
        "鼻咽癌": "鼻咽恶性肿瘤",
        "喉癌": "喉恶性肿瘤",
        "肾癌": "肾恶性肿瘤",
        # 其他常见映射
        "慢性胃炎": "慢性胃炎",
        "胃溃疡": "胃溃疡",
        "十二指肠溃疡": "十二指肠溃疡",
        "消化性溃疡": "消化性溃疡",
        "上消化道出血": "上消化道出血",
        "下消化道出血": "下消化道出血",
        "消化道出血": "消化道出血",
        "痔疮": "痔",
        "内痔": "内痔",
        "外痔": "外痔",
        "混合痔": "混合痔",
        # 证型统一
        "气虚证": "气虚证",
        "血虚证": "血虚证",
        "阴虚证": "阴虚证",
        "阳虚证": "阳虚证",
        "气阴两虚证": "气阴两虚证",
        "气血两虚证": "气血两虚证",
        "阴阳两虚证": "阴阳两虚证",
        "痰瘀互结证": "痰瘀互结证",
        "正虚毒结证": "正虚毒结证",
        "气滞血瘀证": "气滞血瘀证",
        "湿热蕴结证": "湿热蕴结证",
        "脾虚湿困证": "脾虚湿困证",
        "肝肾阴虚证": "肝肾阴虚证",
        "脾肾阳虚证": "脾肾阳虚证",
        "心脾两虚证": "心脾两虚证",
    }

    # 主诉治疗/后缀去除规则
    COMPLAINT_SUFFIX_PATTERNS = [
        r"，+下一?周期?化疗[。 ]*",
        r"，+入院治疗[。 ]*",
        r"，+入院[。 ]*",
        r"，+求诊[。 ]*",
        r"，+就诊[。 ]*",
        r"，+治疗[。 ]*",
        r"，+复查[。 ]*",
        r"，+随访[。 ]*",
        r"[。 ]*$",
    ]

    def __init__(self, cache_dir: str = "data/kg_cleaned"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    # ========== 通用清洗工具 ==========

    @staticmethod
    def basic_clean(text: str) -> Optional[str]:
        """基础文本清洗"""
        if pd.isna(text):
            return None
        s = str(text).strip()
        if not s or s in ("-", "nan", "None", "NULL", "未提及", "未说明"):
            return None
        # 规范化空格
        s = re.sub(r"\s+", " ", s)
        # 中文括号转英文括号
        s = s.replace("（", "(").replace("）", ")")
        # 去除常见无意义前缀
        s = re.sub(r"^(:|：)\s*", "", s)
        s = re.sub(r"^\d+[\.、]\s*", "", s)
        return s.strip()

    @classmethod
    def is_non_disease(cls, name: str) -> bool:
        """判断是否非疾病项"""
        if not name:
            return True
        for kw in cls.NON_DISEASE_KEYWORDS:
            if kw in name:
                return True
        # 以"检查"结尾且较短
        if name.endswith("检查") and len(name) <= 8:
            return True
        return False

    @classmethod
    def is_non_drug(cls, name: str, is_drug_flag: Optional[str] = None) -> bool:
        """判断是否非药品项"""
        if not name:
            return True
        # 如果原始数据明确标记不是药品
        if is_drug_flag and is_drug_flag in ("否", "0", "False", "否"):
            return True
        for kw in cls.NON_DRUG_KEYWORDS:
            if kw in name:
                return True
        return False

    @classmethod
    def clean_drug_name(cls, name: str) -> Optional[str]:
        """清洗药品名称，去除采购标记等"""
        if not name:
            return None
        # 去除采购标记
        for marker in cls.DRUG_MARKERS:
            name = name.replace(marker, "")
        # 去除规格后缀的常见模式 (如 "（0.5g）")
        name = re.sub(r"\s*\(\d+[\d\.]*[a-zA-Zμμ°℃%]+\)", "", name)
        name = re.sub(r"\s*（\d+[\d\.]*[a-zA-Zμμ°℃%]+）", "", name)
        return name.strip()

    @classmethod
    def split_combined_diagnosis(cls, name: str) -> List[str]:
        """拆分组合诊断，如 '肺积 痰瘀互结证' → ['肺积', '痰瘀互结证']"""
        parts = []
        # 模式1: 病名 + 证型（空格分隔）
        if " " in name and "证" in name:
            # 查找最后一个空格，如果在"证"之前
            idx = name.rfind(" ")
            if idx > 0:
                left = name[:idx].strip()
                right = name[idx + 1 :].strip()
                if right.endswith("证") and len(left) > 1 and len(right) > 2:
                    parts.extend(cls.split_combined_diagnosis(left))
                    parts.append(right)
                    return parts
        # 模式2: 顿号分隔的多个诊断
        if "、" in name and len(name) < 50:
            for p in name.split(")"):
                p = p.strip()
                if p and len(p) > 1:
                    parts.append(p)
            if len(parts) > 1:
                return parts
        # 不拆分
        return [name] if name else []

    @classmethod
    def normalize_disease(cls, name: str) -> Optional[str]:
        """疾病名称归一化"""
        if not name:
            return None
        # 基础清洗
        name = cls.basic_clean(name)
        if not name:
            return None
        # 过滤非疾病
        if cls.is_non_disease(name):
            return None
        # 同义词映射
        if name in cls.DISEASE_SYNONYMS:
            return cls.DISEASE_SYNONYMS[name]
        return name

    @classmethod
    def normalize_complaint(cls, text: str) -> Optional[str]:
        """主诉清洗"""
        if not text:
            return None
        text = cls.basic_clean(text)
        if not text:
            return None
        # 去除治疗后缀
        for pattern in cls.COMPLAINT_SUFFIX_PATTERNS:
            text = re.sub(pattern, "", text)
        # 去除句末标点
        text = text.rstrip("。，；;.,")
        return text.strip()

    # ========== 批量清洗方法 ==========

    def clean_diseases(self) -> Tuple[Dict, Dict]:
        """
        清洗所有疾病诊断数据
        返回: (disease_nodes, diagnosis_rels)
        disease_nodes: {normalized_name: {name, type, category, count}}
        diagnosis_rels: [(visit_id, disease_name, diagnosis_type, is_main)]
        """
        print("Cleaning diseases...")
        disease_nodes = defaultdict(lambda: {"count": 0, "types": set(), "categories": set()})
        diagnosis_rels = []

        # 入院诊断
        df = pd.read_excel("data/入院信息表_肿瘤血液科.xlsx")
        for _, row in df.iterrows():
            visit_id = self.basic_clean(row.get("就诊流水号"))
            if not visit_id:
                continue

            # 西医诊断
            for i in range(1, 24):
                col = f"入院西医主要诊断{i}"
                if col in df.columns:
                    raw = self.basic_clean(row.get(col))
                    if raw:
                        parts = self.split_combined_diagnosis(raw)
                        for part in parts:
                            norm = self.normalize_disease(part)
                            if norm:
                                key = (norm, "western")
                                disease_nodes[key]["count"] += 1
                                disease_nodes[key]["types"].add("western")
                                disease_nodes[key]["categories"].add("admission")
                                diagnosis_rels.append((visit_id, norm, "western", "admission", i == 1))

            # 中医诊断
            tcm_cols = [c for c in df.columns if "入院中医主要诊断" in c and "_" not in c]
            for col in tcm_cols:
                raw = self.basic_clean(row.get(col))
                if raw:
                    norm = self.normalize_disease(raw)
                    if norm:
                        key = (norm, "tcm")
                        disease_nodes[key]["count"] += 1
                        disease_nodes[key]["types"].add("tcm")
                        disease_nodes[key]["categories"].add("admission")
                        diagnosis_rels.append((visit_id, norm, "tcm", "admission", True))

            # 中医证型
            zhengxing_cols = [c for c in df.columns if "入院中医证型" in c and "_" not in c]
            for col in zhengxing_cols:
                raw = self.basic_clean(row.get(col))
                if raw:
                    norm = self.normalize_disease(raw)
                    if norm:
                        key = (norm, "tcm_syndrome")
                        disease_nodes[key]["count"] += 1
                        disease_nodes[key]["types"].add("tcm_syndrome")
                        disease_nodes[key]["categories"].add("admission")

        # 出院诊断
        df = pd.read_excel("data/出院信息表_肿瘤血液科.xlsx")
        for _, row in df.iterrows():
            visit_id = self.basic_clean(row.get("就诊流水号"))
            if not visit_id:
                continue

            for i in range(1, 8):
                col = f"出院西医主要诊断{i}"
                if col in df.columns:
                    raw = self.basic_clean(row.get(col))
                    if raw:
                        parts = self.split_combined_diagnosis(raw)
                        for part in parts:
                            norm = self.normalize_disease(part)
                            if norm:
                                key = (norm, "western")
                                disease_nodes[key]["count"] += 1
                                disease_nodes[key]["types"].add("western")
                                disease_nodes[key]["categories"].add("discharge")
                                diagnosis_rels.append((visit_id, norm, "western", "discharge", i == 1))

            raw = self.basic_clean(row.get("出院中医诊断"))
            if raw:
                norm = self.normalize_disease(raw)
                if norm:
                    key = (norm, "tcm")
                    disease_nodes[key]["count"] += 1
                    disease_nodes[key]["types"].add("tcm")
                    disease_nodes[key]["categories"].add("discharge")
                    diagnosis_rels.append((visit_id, norm, "tcm", "discharge", True))

        # 转换为标准格式
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

    def clean_drugs(self) -> Tuple[Dict, List]:
        """
        清洗药品数据
        返回: (drug_nodes, prescription_rels)
        drug_nodes: {cleaned_name: {name, ...}}
        prescription_rels: [(visit_id, drug_name, {...props})]
        """
        print("Cleaning drugs...")
        drug_nodes = {}
        prescription_rels = []
        total_orders = 0
        filtered_orders = 0

        for path in ["data/入出院交医嘱_肿瘤血液科1.xlsx", "data/入出院交医嘱_肿瘤血液科2.xlsx"]:
            df = pd.read_excel(path)
            for _, row in df.iterrows():
                total_orders += 1
                visit_id = self.basic_clean(row.get("就诊流水号"))
                raw_name = self.basic_clean(row.get("医嘱项目名称"))
                is_drug_flag = self.basic_clean(row.get("是否药品"))

                if not visit_id or not raw_name:
                    filtered_orders += 1
                    continue

                # 清洗药品名
                cleaned = self.clean_drug_name(raw_name)
                if not cleaned:
                    filtered_orders += 1
                    continue

                # 过滤非药品
                if self.is_non_drug(cleaned, is_drug_flag):
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
                        "dosage": self.basic_clean(row.get("单次剂量")),
                        "dosage_unit": self.basic_clean(row.get("单次剂量单位")),
                        "frequency": self.basic_clean(row.get("使用频率名称")),
                        "route": self.basic_clean(row.get("给药途径")),
                        "start_date": self._parse_date(row.get("医嘱开始时间")),
                        "end_date": self._parse_date(row.get("医嘱停止时间")),
                        "order_category": self.basic_clean(row.get("医嘱类别")),
                    }
                ))

        # 转换original_names为列表
        for name, info in drug_nodes.items():
            info["original_names"] = list(info["original_names"])

        print(f"  Orders: {total_orders}, Filtered non-drugs: {filtered_orders}, Unique drugs: {len(drug_nodes)}")
        return drug_nodes, prescription_rels

    def clean_complaints(self) -> Tuple[Dict, List]:
        """
        清洗主诉数据
        返回: (complaint_nodes, complaint_rels)
        """
        print("Cleaning complaints...")
        df = pd.read_excel("data/入院信息表_肿瘤血液科.xlsx")
        complaint_nodes = {}
        complaint_rels = []

        for _, row in df.iterrows():
            visit_id = self.basic_clean(row.get("就诊流水号"))
            raw = self.basic_clean(row.get("主诉"))
            if not visit_id or not raw:
                continue

            cleaned = self.normalize_complaint(raw)
            if not cleaned:
                continue

            if cleaned not in complaint_nodes:
                complaint_nodes[cleaned] = {"name": cleaned, "count": 0}
            complaint_nodes[cleaned]["count"] += 1
            complaint_rels.append((visit_id, cleaned))

        print(f"  Unique complaints after cleaning: {len(complaint_nodes)}")
        return complaint_nodes, complaint_rels

    def clean_exams(self) -> Tuple[Dict, List]:
        """清洗检查数据"""
        print("Cleaning exams...")
        df = pd.read_excel("data/入出院交检查_肿瘤血液科.xlsx")
        exam_nodes = {}
        exam_rels = []

        for _, row in df.iterrows():
            visit_id = self.basic_clean(row.get("就诊流水号"))
            name = self.basic_clean(row.get("标准化项目名称（匹配结果）"))
            if not visit_id or not name:
                continue

            # 清洗：去除多余空格
            name = re.sub(r"\s+", " ", name).strip()
            category = self.basic_clean(row.get("标准大类名称"))
            body_part = self.basic_clean(row.get("检查部位"))

            if name not in exam_nodes:
                exam_nodes[name] = {
                    "name": name,
                    "category": category,
                    "body_part": body_part,
                }

            exam_rels.append((
                visit_id,
                name,
                {
                    "exam_date": self._parse_date(row.get("检查日期")),
                    "report_date": self._parse_date(row.get("报告日期")),
                    "description": self.basic_clean(row.get("描述")),
                    "diagnosis": self.basic_clean(row.get("诊断")),
                }
            ))

        print(f"  Unique exams: {len(exam_nodes)}")
        return exam_nodes, exam_rels

    def clean_labs(self) -> Tuple[Dict, List]:
        """清洗检验数据"""
        print("Cleaning labs...")
        df = pd.read_excel("data/入出院交检验_肿瘤血液科.xlsx")
        lab_nodes = {}
        lab_rels = []

        for _, row in df.iterrows():
            visit_id = self.basic_clean(row.get("就诊流水号"))
            name = self.basic_clean(row.get("标准项目名称"))
            if not visit_id or not name:
                continue

            name = re.sub(r"\s+", " ", name).strip()
            unit = self.basic_clean(row.get("检验项目单位"))
            ref = self.basic_clean(row.get("参考范围"))

            if name not in lab_nodes:
                lab_nodes[name] = {
                    "name": name,
                    "unit": unit,
                    "reference_range": ref,
                }

            val = self._to_float(row.get("检验项目结果"))
            hint = self.basic_clean(row.get("检验项目提示"))
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

    def clean_surgeries(self) -> Tuple[Dict, List]:
        """清洗手术数据"""
        print("Cleaning surgeries...")
        df = pd.read_excel("data/入出院交手术_肿瘤血液科.xlsx")
        surgery_nodes = {}
        surgery_rels = []

        for _, row in df.iterrows():
            visit_id = self.basic_clean(row.get("就诊流水号"))
            name = self.basic_clean(row.get("手术名称"))
            if not visit_id or not name:
                continue

            name = re.sub(r"\s+", " ", name).strip()

            if name not in surgery_nodes:
                surgery_nodes[name] = {
                    "name": name,
                    "category": self.basic_clean(row.get("手术类别")),
                    "level": self.basic_clean(row.get("手术等级")),
                    "anesthesia_method": self.basic_clean(row.get("麻醉方式")),
                }

            surgery_rels.append((
                visit_id,
                name,
                {
                    "start_date": self._parse_date(row.get("手术开始时间")),
                    "end_date": self._parse_date(row.get("手术结束时间")),
                    "description": self.basic_clean(row.get("手术过程描述")),
                }
            ))

        print(f"  Unique surgeries: {len(surgery_nodes)}")
        return surgery_nodes, surgery_rels

    def clean_departments(self) -> Tuple[Set, List]:
        """清洗科室数据"""
        print("Cleaning departments...")
        departments = set()
        dept_rels = []

        for path, col, dept_col in [
            ("data/入出院交检查_肿瘤血液科.xlsx", "就诊流水号", "申请科室"),
            ("data/入出院交检验_肿瘤血液科.xlsx", "就诊流水号", "送检科室"),
            ("data/出院信息表_肿瘤血液科.xlsx", "就诊流水号", "出院科室"),
        ]:
            df = pd.read_excel(path)
            for _, row in df.iterrows():
                visit_id = self.basic_clean(row.get(col))
                dept = self.basic_clean(row.get(dept_col))
                if visit_id and dept:
                    dept = re.sub(r"\s+", " ", dept).strip()
                    departments.add(dept)
                    dept_rels.append((visit_id, dept))

        print(f"  Unique departments: {len(departments)}")
        return departments, dept_rels

    def clean_patients_and_visits(self) -> Tuple[Dict, Dict]:
        """清洗患者和就诊数据"""
        print("Cleaning patients and visits...")
        df = pd.read_excel("data/入院信息表_肿瘤血液科.xlsx")

        patients = {}
        visits = {}

        for _, row in df.iterrows():
            patient_id = self.basic_clean(row.get("患者ID"))
            mrn = self.basic_clean(row.get("病案号"))
            visit_id = self.basic_clean(row.get("就诊流水号"))

            if not patient_id or not visit_id:
                continue

            if patient_id not in patients:
                age = self._to_int(row.get("年龄"))
                if age and age > 1000:
                    age = age // 365
                patients[patient_id] = {
                    "patient_id": patient_id,
                    "medical_record_no": mrn,
                    "age": age,
                    "marital_status": self.basic_clean(row.get("婚姻")),
                    "occupation": self.basic_clean(row.get("职业")),
                    "allergy_history": self.basic_clean(row.get("过敏史")),
                }

            if visit_id not in visits:
                visits[visit_id] = {
                    "visit_id": visit_id,
                    "patient_id": patient_id,
                    "admission_date": self._parse_date(row.get("入院日期")),
                    "chief_complaint": self.normalize_complaint(row.get("主诉")),
                }

        # 补充出院信息
        try:
            df_dis = pd.read_excel("data/出院信息表_肿瘤血液科.xlsx")
            for _, row in df_dis.iterrows():
                visit_id = self.basic_clean(row.get("就诊流水号"))
                if visit_id and visit_id in visits:
                    visits[visit_id]["discharge_date"] = self._parse_date(row.get("出院日期"))
                    visits[visit_id]["length_of_stay"] = self._to_int(row.get("住院天数"))
        except Exception as e:
            print(f"  Warning: discharge enrichment failed: {e}")

        print(f"  Patients: {len(patients)}, Visits: {len(visits)}")
        return patients, visits

    # ========== 全量清洗并缓存 ==========

    def run_all(self, use_cache: bool = True) -> Dict:
        """执行全量清洗并缓存结果"""
        cache_file = os.path.join(self.cache_dir, "cleaned_data.json")

        if use_cache and os.path.exists(cache_file):
            print(f"Loading cached cleaned data from {cache_file}")
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        print("=" * 60)
        print("Running full data cleaning pipeline")
        print("=" * 60)

        patients, visits = self.clean_patients_and_visits()
        diseases, diag_rels = self.clean_diseases()
        complaints, complaint_rels = self.clean_complaints()
        exams, exam_rels = self.clean_exams()
        labs, lab_rels = self.clean_labs()
        drugs, drug_rels = self.clean_drugs()
        surgeries, surgery_rels = self.clean_surgeries()
        departments, dept_rels = self.clean_departments()

        # 构建清洗报告
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

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\nCleaned data cached to {cache_file}")
        print("=" * 60)
        print("Cleaning Summary:")
        for k, v in report["stats"].items():
            print(f"  {k}: {v}")
        print("=" * 60)

        return report

    # ========== 辅助方法 ==========

    @staticmethod
    def _parse_date(val) -> Optional[str]:
        if pd.isna(val):
            return None
        try:
            if isinstance(val, pd.Timestamp):
                return val.strftime("%Y-%m-%d")
            s = str(val).strip()
            if " " in s:
                s = s.split()[0]
            s = s.replace("/", "-")
            from datetime import datetime
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except:
            return None

    @staticmethod
    def _to_int(val) -> Optional[int]:
        if pd.isna(val):
            return None
        try:
            return int(float(val))
        except:
            return None

    @staticmethod
    def _to_float(val) -> Optional[float]:
        if pd.isna(val):
            return None
        try:
            return float(val)
        except:
            return None
