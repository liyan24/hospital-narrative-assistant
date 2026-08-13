from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 大模型配置
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # 思考模式（DeepSeek 推理模型）：enabled / disabled
    # 思考模式下 temperature 等采样参数不生效，且思维链 token 与回答共用 max_tokens
    thinking_mode: str = "enabled"

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "root123"
    mysql_database: str = "hna"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # 向量数据库
    vector_db_path: str = "./data/vector_db"

    # JSON存储
    json_store_path: str = "./data/json_store"

    # LLM缓存配置
    llm_cache_path: str = "./data/llm_cache"
    llm_cache_ttl_hours: int = 240
    llm_cache_enabled: bool = True

    # 应用配置
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True

    # JWT 密钥（生产环境请务必修改）
    secret_key: str = "hospital-narrative-assistant-secret-key"

    # 前端配置
    frontend_port: int = 8501

    # 测试环境模拟日期（留空则使用系统今天）
    simulation_date: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
