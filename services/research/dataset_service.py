"""
科研助手数据集服务：统一加载肿瘤血液科 Excel 数据并构建就诊级宽表。
所有表读取后用 pickle 缓存到 data/cache/research/，按源文件 mtime 失效。
"""
import re
import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from database.neo4j_client import neo4j_client

DATA_DIR = Path("data")
CACHE_DIR = DATA_DIR / "cache" / "research"

# 表名 -> 源文件列表（医嘱表由两个文件合并）
TABLE_FILES = {
    "admission": ["入院信息表_肿瘤血液科.xlsx"],
    "discharge": ["出院信息表_肿瘤血液科.xlsx"],
    "orders": ["入出院交医嘱_肿瘤血液科1.xlsx", "入出院交医嘱_肿瘤血液科2.xlsx"],
    "exam": ["入出院交检查_肿瘤血液科.xlsx"],
    "lab": ["入出院交检验_肿瘤血液科.xlsx"],
    "surgery": ["入出院交手术_肿瘤血液科.xlsx"],
}

TABLE_LABELS = {
    "admission": "入院信息表",
    "discharge": "出院信息表",
    "orders": "医嘱表（两文件合并）",
    "exam": "检查表",
    "lab": "检验表",
    "surgery": "手术表",
}

# 高频定量检验项候选（按实际存在的列取交集）
LAB_FEATURE_CANDIDATES = [
    "白细胞计数", "血红蛋白", "血红蛋白测定", "红细胞计数", "血小板计数",
    "中性粒细胞百分率", "淋巴细胞百分率", "单核细胞百分率",
    "血浆凝血酶原时间", "C反应蛋白",
]

# 诊断清洗时剔除的非诊断占位词
INVALID_DIAGNOSIS_PATTERNS = ["待查", "待诊", "随访", "？", "?", "原因待查", "无"]


class ResearchDatasetService:
    """科研数据加载与就诊级宽表构建"""

    def __init__(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._tables: dict[str, pd.DataFrame] = {}
        self._visit_matrix: pd.DataFrame | None = None

    # ========== 基础表加载 ==========

    def _source_mtime(self, name: str) -> float:
        """源文件最新修改时间，文件缺失返回 -1"""
        mtimes = []
        for fname in TABLE_FILES[name]:
            fp = DATA_DIR / fname
            if fp.exists():
                mtimes.append(fp.stat().st_mtime)
        return max(mtimes) if mtimes else -1

    def _cache_path(self, name: str) -> Path:
        return CACHE_DIR / f"{name}.pkl"

    def _cache_valid(self, name: str) -> bool:
        cache = self._cache_path(name)
        if not cache.exists():
            return False
        src_mtime = self._source_mtime(name)
        return src_mtime >= 0 and cache.stat().st_mtime >= src_mtime

    def load_table(self, name: str) -> pd.DataFrame:
        """加载数据表（内存缓存 + pickle 磁盘缓存）"""
        if name in self._tables:
            return self._tables[name]
        if name not in TABLE_FILES:
            raise ValueError(f"未知数据表: {name}，可选: {list(TABLE_FILES.keys())}")

        if self._cache_valid(name):
            df = pd.read_pickle(self._cache_path(name))
        else:
            frames = []
            for fname in TABLE_FILES[name]:
                fp = DATA_DIR / fname
                if fp.exists():
                    frames.append(pd.read_excel(fp))
            if not frames:
                raise FileNotFoundError(f"数据表 {name} 的源文件均不存在")
            df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
            df.to_pickle(self._cache_path(name))

        self._tables[name] = df
        return df

    @staticmethod
    def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
        """按候选名找列，找不到返回 None（对列缺失容错）"""
        for c in candidates:
            if c in df.columns:
                return c
        return None

    # ========== 就诊级宽表 ==========

    def build_visit_matrix(self, use_cache: bool = True) -> pd.DataFrame:
        """
        构建就诊级宽表：每行一次就诊。
        列：visit_no, patient_id, age_years, length_of_stay, is_readmission,
        is_long_stay, outcome, diagnoses(list), drugs(list), lab_* 检验均值, had_surgery
        """
        if self._visit_matrix is not None:
            return self._visit_matrix

        cache = CACHE_DIR / "visit_matrix.pkl"
        if use_cache and cache.exists():
            # 依赖出院/医嘱/检验/手术四张表的 mtime
            dep_mtime = max(self._source_mtime(n) for n in ["discharge", "orders", "lab", "surgery"])
            if cache.stat().st_mtime >= dep_mtime:
                self._visit_matrix = pd.read_pickle(cache)
                return self._visit_matrix

        df = self._build_visit_matrix()
        df.to_pickle(cache)
        self._visit_matrix = df
        return df

    def _build_visit_matrix(self) -> pd.DataFrame:
        discharge = self.load_table("discharge")
        base = discharge.copy()

        visit_col = self._find_col(base, ["就诊流水号"])
        patient_col = self._find_col(base, ["患者ID"])
        base = base.rename(columns={visit_col: "visit_no", patient_col: "patient_id"})
        base["visit_no"] = base["visit_no"].astype(str)

        # 年龄：原始单位为天，换算为岁（若已是岁则不重复换算）
        age_col = self._find_col(base, ["年龄"])
        if age_col:
            age = pd.to_numeric(base[age_col], errors="coerce")
            base["age_years"] = age / 365.0 if age.median() > 130 else age
        else:
            base["age_years"] = np.nan

        # 住院天数 / 出院结局
        los_col = self._find_col(base, ["住院天数"])
        base["length_of_stay"] = pd.to_numeric(base[los_col], errors="coerce") if los_col else np.nan
        outcome_col = self._find_col(base, ["出院结局"])
        base["outcome"] = base[outcome_col].fillna("未记录") if outcome_col else "未记录"

        # 再入院：同一患者就诊次数 > 1
        visit_counts = base.groupby("patient_id")["visit_no"].transform("nunique")
        base["is_readmission"] = visit_counts > 1

        # 长住院：住院天数 > 全样本 P75
        p75 = base["length_of_stay"].quantile(0.75)
        base["is_long_stay"] = base["length_of_stay"] > p75

        # 出院西医诊断 1~7 合并去重 + 基本归一化
        diag_cols = [c for c in base.columns if re.fullmatch(r"出院西医主要诊断\d+", str(c))]
        base["diagnoses"] = base[diag_cols].apply(self._normalize_diagnoses, axis=1)

        # 药品清单（按就诊聚合）
        drug_map = self._build_visit_drugs()
        base["drugs"] = base["visit_no"].map(drug_map).apply(lambda x: x if isinstance(x, list) else [])

        # 高频定量检验项均值
        lab_features = self._build_lab_features()
        if lab_features is not None:
            base = base.merge(lab_features, on="visit_no", how="left")

        # 是否手术
        try:
            surgery = self.load_table("surgery")
            s_visit = self._find_col(surgery, ["就诊流水号"])
            surgery_visits = set(surgery[s_visit].astype(str)) if s_visit else set()
        except FileNotFoundError:
            surgery_visits = set()
        base["had_surgery"] = base["visit_no"].isin(surgery_visits)

        keep_cols = ["visit_no", "patient_id", "age_years", "length_of_stay",
                     "is_readmission", "is_long_stay", "outcome", "diagnoses", "drugs", "had_surgery"]
        lab_cols = [c for c in base.columns if c.startswith("lab_")]
        return base[keep_cols + lab_cols]

    @staticmethod
    def _normalize_diagnoses(row) -> list[str]:
        """合并出院诊断列：去空白、去'待查/随访'类占位、去重"""
        seen = []
        for val in row:
            if not isinstance(val, str):
                continue
            name = val.strip()
            if not name or name.lower() == "nan":
                continue
            if any(p in name for p in INVALID_DIAGNOSIS_PATTERNS):
                continue
            if name not in seen:
                seen.append(name)
        return seen

    def _build_visit_drugs(self) -> dict[str, list[str]]:
        """按就诊聚合药品名称（清洗：去规格后缀、去'（中选）'、剔除非药品）"""
        from services.kg_data_cleaner import KGDataCleaner

        try:
            orders = self.load_table("orders")
        except FileNotFoundError:
            return {}

        visit_col = self._find_col(orders, ["就诊流水号"])
        name_col = self._find_col(orders, ["医嘱项目名称"])
        flag_col = self._find_col(orders, ["是否药品"])
        if not visit_col or not name_col:
            return {}

        orders = orders[[c for c in [visit_col, name_col, flag_col] if c]].dropna(subset=[name_col])

        # 实际数据中"是否药品"整列为空，优先按标记过滤；标记缺失时退回关键词过滤
        flag_valid = orders[flag_col].astype(str).str.strip().isin(["是", "否"]).any() if flag_col else False

        @lru_cache(maxsize=None)
        def clean_drug(raw_name: str, flag: str) -> str | None:
            name = KGDataCleaner.clean_drug_name(raw_name)
            if not name:
                return None
            if flag_valid:
                if flag != "是":
                    return None
            elif KGDataCleaner.is_non_drug(name, flag or None):
                return None
            return name

        flags = orders[flag_col].fillna("").astype(str).str.strip() if flag_col else pd.Series([""] * len(orders))
        cleaned = [
            clean_drug(str(n).strip(), f)
            for n, f in zip(orders[name_col], flags)
        ]
        orders = orders.assign(_drug=cleaned).dropna(subset=["_drug"])

        drug_map: dict[str, list[str]] = {}
        for visit_no, grp in orders.groupby(orders[visit_col].astype(str))["_drug"]:
            # 保持出现顺序去重
            drug_map[visit_no] = list(dict.fromkeys(grp.tolist()))
        return drug_map

    def _build_lab_features(self) -> pd.DataFrame | None:
        """高频定量检验项按就诊取均值，覆盖不足的项跳过"""
        try:
            lab = self.load_table("lab")
        except FileNotFoundError:
            return None

        visit_col = self._find_col(lab, ["就诊流水号"])
        item_col = self._find_col(lab, ["标准项目名称"])
        value_col = self._find_col(lab, ["结果定量化", "检验项目结果"])
        if not visit_col or not item_col or not value_col:
            return None

        lab = lab[[visit_col, item_col, value_col]].copy()
        lab[visit_col] = lab[visit_col].astype(str)
        lab["_value"] = pd.to_numeric(lab[value_col], errors="coerce")
        lab = lab.dropna(subset=["_value"])

        available = set(lab[item_col].dropna().unique())
        chosen = [c for c in LAB_FEATURE_CANDIDATES if c in available]
        if not chosen:
            return None

        pivot = (
            lab[lab[item_col].isin(chosen)]
            .groupby([visit_col, item_col])["_value"]
            .mean()
            .unstack()
        )
        pivot.columns = [f"lab_{c}" for c in pivot.columns]
        pivot = pivot.reset_index().rename(columns={visit_col: "visit_no"})

        # 覆盖率不足 5% 的检验项列剔除
        min_cover = int(len(pivot) * 0.05)
        keep = ["visit_no"] + [c for c in pivot.columns if c != "visit_no" and pivot[c].notna().sum() >= min_cover]
        return pivot[keep]

    # ========== 数据资产清单 ==========

    def detect_data_assets(self) -> dict:
        """数据资产清单：表规模 / 图谱 / 文本数据 / 向量库"""
        assets = {"tables": [], "graph": {}, "text_data": {}, "vector_db": {}}

        key_columns_map = {
            "admission": ["患者ID", "就诊流水号", "入院日期", "年龄", "主诉", "现病史"],
            "discharge": ["患者ID", "就诊流水号", "住院天数", "出院结局", "出院科室"],
            "orders": ["患者ID", "就诊流水号", "医嘱项目名称", "是否药品", "给药途径"],
            "exam": ["患者ID", "就诊流水号", "标准化项目名称（匹配结果）", "描述", "诊断"],
            "lab": ["患者ID", "就诊流水号", "标准项目名称", "结果定量化", "参考范围"],
            "surgery": ["患者ID", "就诊流水号", "手术名称", "手术等级", "麻醉方式"],
        }
        coverage_notes = {
            "admission": "全量就诊均有入院记录；年龄原始单位为天，使用时需/365",
            "discharge": "全量就诊均有出院记录；出院结局大量缺失（仅少数死亡记录）",
            "orders": "百万级医嘱；'是否药品'列实际为空，药品需按名称关键词过滤",
            "exam": "含检查报告文本（描述/诊断字段），可做文本挖掘",
            "lab": "仅约 826 名患者有检验数据，覆盖率约 20%",
            "surgery": "仅约 85 名患者有手术记录，属小样本",
        }

        for name in TABLE_FILES:
            try:
                df = self.load_table(name)
                existing_keys = [c for c in key_columns_map.get(name, []) if c in df.columns]
                assets["tables"].append({
                    "name": name,
                    "label": TABLE_LABELS.get(name, name),
                    "rows": int(len(df)),
                    "cols": int(len(df.columns)),
                    "key_columns": existing_keys,
                    "coverage_note": coverage_notes.get(name, ""),
                })
            except FileNotFoundError:
                assets["tables"].append({
                    "name": name,
                    "label": TABLE_LABELS.get(name, name),
                    "rows": 0,
                    "cols": 0,
                    "key_columns": [],
                    "coverage_note": "源文件缺失",
                })

        # 知识图谱
        try:
            if neo4j_client.test_connection():
                node_records = neo4j_client.run(
                    "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY count DESC"
                )
                rel_records = neo4j_client.run(
                    "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY count DESC"
                )
                assets["graph"] = {
                    "available": True,
                    "node_stats": {r["label"]: r["count"] for r in node_records},
                    "rel_stats": {r["type"]: r["count"] for r in rel_records},
                }
            else:
                assets["graph"] = {"available": False, "error": "Neo4j 连接失败"}
        except Exception as e:
            assets["graph"] = {"available": False, "error": str(e)}

        # 文本数据规模
        text_stats = {}
        try:
            admission = self.load_table("admission")
            for col in ["主诉", "现病史"]:
                if col in admission.columns:
                    text_stats[f"入院表_{col}"] = int(admission[col].notna().sum())
        except FileNotFoundError:
            pass
        try:
            discharge = self.load_table("discharge")
            for col in ["住院治疗经过", "西医诊疗经过"]:
                if col in discharge.columns:
                    text_stats[f"出院表_{col}"] = int(discharge[col].notna().sum())
        except FileNotFoundError:
            pass
        try:
            exam = self.load_table("exam")
            for col in ["描述", "诊断"]:
                if col in exam.columns:
                    text_stats[f"检查表_{col}"] = int(exam[col].notna().sum())
        except FileNotFoundError:
            pass
        assets["text_data"] = text_stats

        # 向量库
        try:
            from database.vector_store import vector_store
            collections = vector_store.list_collections()
            assets["vector_db"] = {
                "available": True,
                "collections": [getattr(c, "name", str(c)) for c in collections],
            }
        except Exception as e:
            assets["vector_db"] = {"available": False, "error": str(e)}

        return assets


# 全局单例
dataset_service = ResearchDatasetService()
