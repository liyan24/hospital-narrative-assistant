import os
import json
from pathlib import Path
from config import settings


class JSONStore:
    def __init__(self):
        self.base_path = Path(settings.json_store_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_path(self, doc_id: str) -> Path:
        return self.base_path / f"{doc_id}.json"

    def save(self, doc_id: str, data: dict):
        path = self._get_path(doc_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, doc_id: str) -> dict | None:
        path = self._get_path(doc_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete(self, doc_id: str) -> bool:
        path = self._get_path(doc_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_all(self) -> list[str]:
        return [p.stem for p in self.base_path.glob("*.json")]


# 全局单例
json_store = JSONStore()
