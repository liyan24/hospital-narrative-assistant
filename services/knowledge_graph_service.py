"""
知识图谱构建服务（v2 - 基于清洗后数据）
"""

import json
import os
from typing import Dict, List, Any, Optional
from database.neo4j_client import Neo4jClient
from services.kg_data_cleaner import KGDataCleaner


class KnowledgeGraphService:
    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        self.client = neo4j_client or Neo4jClient()
        self.batch_size = 5000
        self.cleaner = KGDataCleaner()

    # ==================== Schema Setup ====================

    def setup_schema(self):
        """创建约束和索引"""
        constraints = [
            "CREATE CONSTRAINT patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.patient_id IS UNIQUE",
            "CREATE CONSTRAINT visit_id IF NOT EXISTS FOR (v:Visit) REQUIRE v.visit_id IS UNIQUE",
            "CREATE CONSTRAINT complaint_name IF NOT EXISTS FOR (c:ChiefComplaint) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT exam_name IF NOT EXISTS FOR (e:Exam) REQUIRE e.name IS UNIQUE",
            "CREATE CONSTRAINT labitem_name IF NOT EXISTS FOR (l:LabItem) REQUIRE l.name IS UNIQUE",
            "CREATE CONSTRAINT drug_name IF NOT EXISTS FOR (dr:Drug) REQUIRE dr.name IS UNIQUE",
            "CREATE CONSTRAINT surgery_name IF NOT EXISTS FOR (su:Surgery) REQUIRE su.name IS UNIQUE",
            "CREATE CONSTRAINT dept_name IF NOT EXISTS FOR (de:Department) REQUIRE de.name IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX patient_mrn IF NOT EXISTS FOR (p:Patient) ON (p.medical_record_no)",
            "CREATE INDEX visit_admission_date IF NOT EXISTS FOR (v:Visit) ON (v.admission_date)",
            "CREATE INDEX disease_name IF NOT EXISTS FOR (d:Disease) ON (d.name)",
            "CREATE INDEX disease_type IF NOT EXISTS FOR (d:Disease) ON (d.type)",
        ]
        for cql in constraints + indexes:
            try:
                self.client.run(cql)
            except Exception as e:
                print(f"  Schema warning: {e}")
        print("Schema setup completed.")

    def clear_graph(self, confirm: bool = False):
        if not confirm:
            print("Use clear_graph(confirm=True) to actually clear the graph.")
            return
        self.client.run("MATCH (n) DETACH DELETE n")
        print("Graph cleared.")

    # ==================== Batch Import Helpers ====================

    def _batch_merge_nodes(self, label: str, key_prop: str, nodes: List[Dict[str, Any]]):
        if not nodes:
            return 0
        # 全局去重
        seen = {}
        for n in nodes:
            key = n[key_prop]
            if key not in seen:
                seen[key] = n
        deduped = list(seen.values())
        for i in range(0, len(deduped), self.batch_size):
            batch = deduped[i : i + self.batch_size]
            cql = f"""
            UNWIND $batch AS row
            MERGE (n:{label} {{`{key_prop}`: row.`{key_prop}`}})
            SET n += row.props
            RETURN count(n) AS cnt
            """
            params = {"batch": [
                {key_prop: n[key_prop], "props": {k: v for k, v in n.items() if k != key_prop and v is not None}}
                for n in batch
            ]}
            with self.client.driver.session() as session:
                result = session.run(cql, params)
                list(result)  # consume within session
        return len(deduped)

    def _batch_create_rels_single_key(self, from_label: str, from_key: str, to_label: str, to_key: str, rel_type: str, rels: List[Dict]):
        if not rels:
            return 0
        # 全局去重
        seen = set()
        deduped = []
        for r in rels:
            key = (r["from_key"], r["to_key"])
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        for i in range(0, len(deduped), self.batch_size):
            batch = deduped[i : i + self.batch_size]
            cql = f"""
            UNWIND $batch AS row
            MATCH (a:{from_label} {{`{from_key}`: row.from_key}})
            MATCH (b:{to_label} {{`{to_key}`: row.to_key}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r += row.props
            RETURN count(r) AS cnt
            """
            params = {"batch": [
                {"from_key": r["from_key"], "to_key": r["to_key"],
                 "props": r.get("props", {k: v for k, v in r.items() if k not in ("from_key", "to_key", "props") and v is not None})}
                for r in batch
            ]}
            with self.client.driver.session() as session:
                result = session.run(cql, params)
                list(result)  # consume within session
        return len(deduped)

    # ==================== Import Methods ====================

    def import_patients(self, patients: List[Dict]):
        print("Importing patients...")
        self._batch_merge_nodes("Patient", "patient_id", patients)
        print(f"  {len(patients)} patients imported")

    def import_visits(self, visits: List[Dict]):
        print("Importing visits...")
        for i in range(0, len(visits), self.batch_size):
            batch = visits[i : i + self.batch_size]
            cql = """
            UNWIND $batch AS row
            MERGE (v:Visit {visit_id: row.visit_id})
            SET v.admission_date = row.admission_date,
                v.discharge_date = row.discharge_date,
                v.length_of_stay = row.length_of_stay,
                v.chief_complaint = row.chief_complaint
            RETURN count(v) AS cnt
            """
            self.client.run(cql, {"batch": batch})
        print(f"  {len(visits)} visits imported")

    def import_diseases(self, diseases: List[Dict]):
        print("Importing diseases...")
        # Disease按(name, type)去重，使用组合key作为name
        seen = {}
        for d in diseases:
            key = f"{d['name']}::{d['type']}"
            if key not in seen:
                d["display_name"] = d["name"]
                d["name"] = key
                seen[key] = d
        unique = list(seen.values())
        self._batch_merge_nodes("Disease", "name", unique)
        print(f"  {len(unique)} diseases imported")

    def import_complaints(self, complaints: List[Dict]):
        print("Importing chief complaints...")
        self._batch_merge_nodes("ChiefComplaint", "name", complaints)
        print(f"  {len(complaints)} complaints imported")

    def import_exams(self, exams: List[Dict]):
        print("Importing exams...")
        self._batch_merge_nodes("Exam", "name", exams)
        print(f"  {len(exams)} exams imported")

    def import_labs(self, labs: List[Dict]):
        print("Importing lab items...")
        self._batch_merge_nodes("LabItem", "name", labs)
        print(f"  {len(labs)} lab items imported")

    def import_drugs(self, drugs: List[Dict]):
        print("Importing drugs...")
        self._batch_merge_nodes("Drug", "name", drugs)
        print(f"  {len(drugs)} drugs imported")

    def import_surgeries(self, surgeries: List[Dict]):
        print("Importing surgeries...")
        self._batch_merge_nodes("Surgery", "name", surgeries)
        print(f"  {len(surgeries)} surgeries imported")

    def import_departments(self, departments: List[Dict]):
        print("Importing departments...")
        self._batch_merge_nodes("Department", "name", departments)
        print(f"  {len(departments)} departments imported")

    # ==================== Relationship Import ====================

    def import_has_visit(self, rels: List[tuple]):
        print("Importing HAS_VISIT relationships...")
        batch = [{"from_key": p[0], "to_key": p[1]} for p in rels]
        self._batch_create_rels_single_key("Patient", "patient_id", "Visit", "visit_id", "HAS_VISIT", batch)
        print(f"  {len(batch)} HAS_VISIT imported")

    def import_diagnosis(self, rels: List[Dict]):
        print("Importing diagnosis relationships...")
        self._batch_create_rels_single_key(
            "Visit", "visit_id", "Disease", "name", "DIAGNOSED_WITH",
            [{"from_key": r["visit_id"], "to_key": f"{r['disease_name']}::{r['type']}",
              "props": {"diagnosis_type": r["diagnosis_type"], "is_main": r["is_main"]}}
             for r in rels]
        )
        print(f"  {len(rels)} DIAGNOSED_WITH imported")

    def import_chief_complaint_rels(self, rels: List[Dict]):
        print("Importing CHIEF_COMPLAINT relationships...")
        self._batch_create_rels_single_key(
            "Visit", "visit_id", "ChiefComplaint", "name", "CHIEF_COMPLAINT",
            [{"from_key": r["visit_id"], "to_key": r["complaint"]} for r in rels]
        )
        print(f"  {len(rels)} CHIEF_COMPLAINT imported")

    def import_exam_rels(self, rels: List[Dict]):
        print("Importing PERFORMED_EXAM relationships...")
        self._batch_create_rels_single_key(
            "Visit", "visit_id", "Exam", "name", "PERFORMED_EXAM",
            [{"from_key": r["visit_id"], "to_key": r["exam_name"],
              "props": {k: v for k, v in r.items() if k not in ("visit_id", "exam_name")}}
             for r in rels]
        )
        print(f"  {len(rels)} PERFORMED_EXAM imported")

    def import_lab_rels(self, rels: List[Dict]):
        print("Importing HAS_LAB_RESULT relationships...")
        self._batch_create_rels_single_key(
            "Visit", "visit_id", "LabItem", "name", "HAS_LAB_RESULT",
            [{"from_key": r["visit_id"], "to_key": r["lab_name"],
              "props": {k: v for k, v in r.items() if k not in ("visit_id", "lab_name")}}
             for r in rels]
        )
        print(f"  {len(rels)} HAS_LAB_RESULT imported")

    def import_prescription_rels(self, rels: List[Dict]):
        print("Importing PRESCRIBED relationships...")
        self._batch_create_rels_single_key(
            "Visit", "visit_id", "Drug", "name", "PRESCRIBED",
            [{"from_key": r["visit_id"], "to_key": r["drug_name"],
              "props": {k: v for k, v in r.items() if k not in ("visit_id", "drug_name")}}
             for r in rels]
        )
        print(f"  {len(rels)} PRESCRIBED imported")

    def import_surgery_rels(self, rels: List[Dict]):
        print("Importing UNDERWENT relationships...")
        self._batch_create_rels_single_key(
            "Visit", "visit_id", "Surgery", "name", "UNDERWENT",
            [{"from_key": r["visit_id"], "to_key": r["surgery_name"],
              "props": {k: v for k, v in r.items() if k not in ("visit_id", "surgery_name")}}
             for r in rels]
        )
        print(f"  {len(rels)} UNDERWENT imported")

    def import_department_rels(self, rels: List[Dict]):
        print("Importing IN_DEPARTMENT relationships...")
        # 去重
        seen = set()
        unique = []
        for r in rels:
            key = (r["visit_id"], r["dept_name"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        self._batch_create_rels_single_key(
            "Visit", "visit_id", "Department", "name", "IN_DEPARTMENT",
            [{"from_key": r["visit_id"], "to_key": r["dept_name"]} for r in unique]
        )
        print(f"  {len(unique)} IN_DEPARTMENT imported")

    def build_treatment_rels(self):
        """构建 Drug-[:TREATS]->Disease 和 Surgery-[:TREATS]->Disease"""
        print("Building treatment relationships...")
        cql_drug = """
        MATCH (v:Visit)-[:PRESCRIBED]->(d:Drug)
        MATCH (v)-[:DIAGNOSED_WITH {diagnosis_type: 'discharge'}]->(dis:Disease)
        WITH d, dis, count(*) AS cnt
        MERGE (d)-[r:TREATS]->(dis)
        SET r.evidence = 'same_visit_prescription'
        RETURN count(r) AS cnt
        """
        try:
            records = self.client.run(cql_drug)
            print(f"  Drug-TREATS-Disease: {records[0]['cnt'] if records else 0}")
        except Exception as e:
            print(f"  Warning Drug-TREATS: {e}")

        cql_surgery = """
        MATCH (v:Visit)-[:UNDERWENT]->(s:Surgery)
        MATCH (v)-[:DIAGNOSED_WITH {diagnosis_type: 'discharge'}]->(dis:Disease)
        WITH s, dis, count(*) AS cnt
        MERGE (s)-[r:TREATS]->(dis)
        SET r.evidence = 'same_visit_surgery'
        RETURN count(r) AS cnt
        """
        try:
            records = self.client.run(cql_surgery)
            print(f"  Surgery-TREATS-Disease: {records[0]['cnt'] if records else 0}")
        except Exception as e:
            print(f"  Warning Surgery-TREATS: {e}")

    # ==================== Main Build ====================

    def build_all(self, clear: bool = False, use_cache: bool = True):
        print("=" * 60)
        print("Starting Knowledge Graph Build (Cleaned Data v2)")
        print("=" * 60)

        if clear:
            self.clear_graph(confirm=True)

        self.setup_schema()

        # Step 1: 清洗数据
        data = self.cleaner.run_all(use_cache=use_cache)
        rels = data["relations"]

        # Step 2: 导入节点
        self.import_patients(data["patients"])
        self.import_visits(data["visits"])
        self.import_diseases(data["diseases"])
        self.import_complaints(data["complaints"])
        self.import_exams(data["exams"])
        self.import_labs(data["labs"])
        self.import_drugs(data["drugs"])
        self.import_surgeries(data["surgeries"])
        self.import_departments(data["departments"])

        # Step 3: 导入关系
        self.import_has_visit(rels["has_visit"])
        self.import_diagnosis(rels["diagnosis"])
        self.import_chief_complaint_rels(rels["chief_complaint"])
        self.import_exam_rels(rels["exam"])
        self.import_lab_rels(rels["lab"])
        self.import_prescription_rels(rels["prescription"])
        self.import_surgery_rels(rels["surgery"])
        self.import_department_rels(rels["department"])
        self.build_treatment_rels()

        print("=" * 60)
        print("Knowledge Graph Build Completed")
        print("=" * 60)

        self.print_stats()

    def _count(self, cql: str) -> int:
        """安全执行计数查询"""
        try:
            records = self.client.run(cql)
            return records[0]["cnt"] if records else 0
        except Exception as e:
            print(f"    query error: {e}")
            return 0

    def print_stats(self):
        print("\n--- Node Statistics ---")
        for label in ["Patient", "Visit", "Disease", "ChiefComplaint", "Exam", "LabItem", "Drug", "Surgery", "Department"]:
            cnt = self._count(f"MATCH (n:{label}) RETURN count(n) AS cnt")
            print(f"  {label}: {cnt}")

        print("\n--- Relationship Statistics ---")
        for rel_type in ["HAS_VISIT", "DIAGNOSED_WITH", "CHIEF_COMPLAINT", "PERFORMED_EXAM",
                         "HAS_LAB_RESULT", "PRESCRIBED", "UNDERWENT", "IN_DEPARTMENT", "TREATS"]:
            cnt = self._count(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt")
            print(f"  {rel_type}: {cnt}")
