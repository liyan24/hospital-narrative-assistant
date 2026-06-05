import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import settings


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
            return result.fetchall()

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
