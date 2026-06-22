#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医院叙事生成助手 - 数据库初始化脚本
用法: python scripts/init_database.py [--create-only] [--seed-only] [--mysql-password xxx]

功能:
1. 执行 scripts/create_tables.sql 创建表
2. 执行 scripts/init_data.sql 插入默认角色、权限、用户、配置、功能开关
"""

import argparse
import os
import sys
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_db_config(password=None):
    """从 .env 加载数据库配置"""
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


def get_engine(config, database=None):
    db = database or config["database"]
    url = (
        f"mysql+pymysql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{db}"
        f"?charset=utf8mb4"
    )
    return create_engine(url, pool_pre_ping=True)


def execute_sql_file(engine, sql_file: Path):
    """执行 SQL 文件，按分号分割语句"""
    print(f"[执行] {sql_file}", flush=True)
    sql = sql_file.read_text(encoding="utf-8")

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.connect() as conn:
        for i, stmt in enumerate(statements, 1):
            try:
                conn.execute(text(stmt))
            except Exception as e:
                print(f"  [错误] 第 {i} 条语句执行失败: {e}", flush=True)
                print(f"  语句: {stmt[:200]}...", flush=True)
                raise
        conn.commit()
    print(f"  完成，共执行 {len(statements)} 条语句", flush=True)


def init_database(create_only: bool = False, seed_only: bool = False, password: str = None):
    config = load_db_config(password=password)
    project_root = get_project_root()

    print("=" * 60, flush=True)
    print("医院叙事生成助手 - 数据库初始化", flush=True)
    print("=" * 60, flush=True)
    print(f"数据库: {config['database']} @ {config['host']}:{config['port']}", flush=True)
    print(f"用户: {config['user']}", flush=True)
    print("=" * 60, flush=True)

    # 先连接 MySQL 不指定数据库，确保数据库存在
    db_name = config["database"]
    engine_no_db = get_engine(config, database="")
    with engine_no_db.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"))
        conn.commit()
    print(f"[OK] 数据库 `{db_name}` 已就绪", flush=True)

    # 连接指定数据库执行脚本
    engine = get_engine(config)
    try:
        if not seed_only:
            execute_sql_file(engine, project_root / "scripts" / "create_tables.sql")
        if not create_only:
            execute_sql_file(engine, project_root / "scripts" / "init_data.sql")
        print("\n[OK] 数据库初始化完成", flush=True)
    except Exception as e:
        print(f"\n[失败] 数据库初始化失败: {e}", flush=True)
        raise


def main():
    parser = argparse.ArgumentParser(description="初始化 hna 数据库")
    parser.add_argument("--create-only", action="store_true", help="仅创建表，不插入初始数据")
    parser.add_argument("--seed-only", action="store_true", help="仅插入初始数据，不创建表")
    parser.add_argument("--mysql-password", default=None, help="MySQL 密码（覆盖 .env 配置）")
    args = parser.parse_args()

    try:
        init_database(create_only=args.create_only, seed_only=args.seed_only, password=args.mysql_password)
    except Exception as e:
        print(f"\n[失败] 数据库初始化失败: {e}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
