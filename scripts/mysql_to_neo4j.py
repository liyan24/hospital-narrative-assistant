#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 MySQL 直接构建 Neo4j 知识图谱（独立直跑脚本）
数据源：MySQL hna 库的 8 张业务表（patients/visits/admissions/discharges/orders/exams/labs/surgeries）

用法:
    python scripts/mysql_to_neo4j.py            # 从 MySQL 全量导入 Neo4j
    python scripts/mysql_to_neo4j.py --clear    # 清空现有图谱后重建
    python scripts/mysql_to_neo4j.py --test     # 仅测试 MySQL/Neo4j 连接
    python scripts/mysql_to_neo4j.py --stats    # 仅打印当前图谱统计

说明:
    本脚本是 build_knowledge_graph.py --source mysql 的便捷直跑入口，
    数据加载与清洗逻辑在 services/kg_mysql_loader.py（口径与 Excel 清洗器一致）。
"""

import sys
import os

# 将项目根目录加入Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from services.knowledge_graph_service import KnowledgeGraphService
from database.neo4j_client import neo4j_client
from database.mysql_client import mysql_client


def main():
    parser = argparse.ArgumentParser(
        description="Build hospital knowledge graph in Neo4j directly from MySQL")
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing graph before building")
    parser.add_argument("--test", action="store_true",
                        help="Test MySQL/Neo4j connections only")
    parser.add_argument("--stats", action="store_true",
                        help="Print graph statistics only")
    args = parser.parse_args()

    # 1. 测试 MySQL 连接
    print("Connecting to MySQL...")
    try:
        row = mysql_client.execute("SELECT COUNT(*) FROM patients").fetchall()[0]
        print(f"MySQL connection OK. patients 表共 {row[0]} 行。")
    except Exception as e:
        print(f"ERROR: Cannot connect to MySQL: {e}")
        print("请检查 .env 中的 MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE")
        sys.exit(1)

    # 2. 测试 Neo4j 连接
    print("Connecting to Neo4j...")
    if not neo4j_client.test_connection():
        print("ERROR: Cannot connect to Neo4j. Please check:")
        print("  1. Neo4j is running (bolt://localhost:7687)")
        print("  2. Username/password are correct in .env or config.py")
        print("\nYou can update the password in .env file:")
        print("  NEO4J_PASSWORD=your_password")
        sys.exit(1)

    print("Neo4j connection OK.\n")

    if args.test:
        print("Connection test passed.")
        return

    kg = KnowledgeGraphService(neo4j_client)

    if args.stats:
        kg.print_stats()
        return

    # 3. 从 MySQL 全量构建
    kg.build_all(clear=args.clear, use_cache=False, source="mysql")


if __name__ == "__main__":
    main()
