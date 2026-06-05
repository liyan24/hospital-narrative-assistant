from neo4j import GraphDatabase
from config import settings


class Neo4jClient:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self):
        self.driver.close()

    def run(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return list(result)

    def test_connection(self):
        try:
            records = self.run("RETURN 1 AS num")
            return len(records) > 0 and records[0]["num"] == 1
        except Exception as e:
            print(f"Neo4j连接失败: {e}")
            return False


# 全局单例
neo4j_client = Neo4jClient()
