import os
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import settings


class VectorStore:
    def __init__(self):
        os.makedirs(settings.vector_db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=settings.vector_db_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def get_or_create_collection(self, name: str):
        return self.client.get_or_create_collection(name=name)

    def add_documents(self, collection_name: str, docs: list[str], ids: list[str], metadatas: list[dict] = None):
        collection = self.get_or_create_collection(collection_name)
        collection.add(
            documents=docs,
            ids=ids,
            metadatas=metadatas,
        )

    def query(self, collection_name: str, query_text: str, n_results: int = 5):
        collection = self.get_or_create_collection(collection_name)
        return collection.query(
            query_texts=[query_text],
            n_results=n_results,
        )

    def list_collections(self):
        return self.client.list_collections()


# 全局单例
vector_store = VectorStore()
