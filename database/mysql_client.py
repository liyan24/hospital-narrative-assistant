import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import settings


class _QueryResult:
    """统一 SQL 执行结果，兼容 SELECT / INSERT / UPDATE / DELETE"""

    def __init__(self, result, rows=None, lastrowid=None, rowcount=None):
        self._rows = rows
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self._result = result

    def fetchall(self):
        if self._rows is not None:
            return self._rows
        try:
            return self._result.fetchall()
        except Exception:
            return []

    def __iter__(self):
        return iter(self.fetchall())

    def __getitem__(self, index):
        return self.fetchall()[index]

    def __len__(self):
        return len(self.fetchall())


class MySQLClient:
    def __init__(self):
        self.connection_string = (
            f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
            f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}"
            f"?charset=utf8mb4"
        )
        self.engine = create_engine(self.connection_string, pool_pre_ping=True)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    def execute(self, sql: str, params=None):
        with self.get_session() as session:
            result = session.execute(text(sql), params or {})
            session.commit()
            try:
                rows = result.fetchall()
                return _QueryResult(result, rows=rows)
            except Exception:
                # INSERT / UPDATE / DELETE 等不返回行的语句
                return _QueryResult(
                    result,
                    rows=[],
                    lastrowid=getattr(result, 'lastrowid', None),
                    rowcount=getattr(result, 'rowcount', 0),
                )

    def get_tables(self):
        """获取数据库中所有表名"""
        rows = self.execute("SHOW TABLES")
        return [row[0] for row in rows]

    def get_table_schema(self, table_name: str):
        """获取指定表的列信息"""
        sql = "DESCRIBE `%s`" % table_name
        return self.execute(sql)


# 全局单例
mysql_client = MySQLClient()
