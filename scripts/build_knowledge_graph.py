#!/usr/bin/env python3
"""
知识图谱构建脚本
用法:
    python scripts/build_knowledge_graph.py
    python scripts/build_knowledge_graph.py --clear  # 清空后重建
    python scripts/build_knowledge_graph.py --test     # 仅测试连接
"""

import sys
import os

# 将项目根目录加入Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from services.knowledge_graph_service import KnowledgeGraphService
from database.neo4j_client import neo4j_client


def main():
    parser = argparse.ArgumentParser(description="Build hospital knowledge graph in Neo4j")
    parser.add_argument("--clear", action="store_true", help="Clear existing graph before building")
    parser.add_argument("--test", action="store_true", help="Test Neo4j connection only")
    parser.add_argument("--stats", action="store_true", help="Print graph statistics only")
    args = parser.parse_args()

    print("Connecting to Neo4j...")
    if not neo4j_client.test_connection():
        print("ERROR: Cannot connect to Neo4j. Please check:")
        print("  1. Neo4j is running (bolt://localhost:7687)")
        print("  2. Username/password are correct in .env or config.py")
        print("\nYou can update the password in .env file:")
        print("  NEO4J_PASSWORD=your_password")
        sys.exit(1)

    print("Neo4j connection OK.\n")

    kg = KnowledgeGraphService(neo4j_client)

    if args.test:
        print("Connection test passed.")
        return

    if args.stats:
        kg.print_stats()
        return

    kg.build_all(clear=args.clear)


if __name__ == "__main__":
    main()
