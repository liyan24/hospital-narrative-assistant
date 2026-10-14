# -*- coding: utf-8 -*-
"""执行 scripts/sql_insert/*.sql 增量导入到 MySQL hna 库（不 DROP 任何表）。

用法: .venv/Scripts/python.exe -X utf8 scripts/run_sql_insert.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.mysql_client import mysql_client

DIR = Path(__file__).resolve().parent / "sql_insert"
FILES = ["patients.sql", "visits.sql", "admissions.sql", "exams.sql", "labs.sql"]


def main():
    for name in FILES:
        path = DIR / name
        ok, fail = 0, 0
        for line in path.read_text(encoding="utf-8").splitlines():
            sql = line.strip()
            if not sql.startswith("INSERT"):
                continue
            try:
                mysql_client.execute(sql)
                ok += 1
            except Exception as e:
                fail += 1
                print(f"  [失败] {name}: {str(e)[:100]}")
        print(f"{name}: 成功 {ok} 条, 失败 {fail} 条")
    print("导入完成")


if __name__ == "__main__":
    main()
