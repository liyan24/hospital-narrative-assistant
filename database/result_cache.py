"""
通用计算结果缓存
用于缓存慢查询/重计算服务的完整输出，避免每次请求都重新执行。
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config import settings


class ResultCacheStore:
    """基于文件系统的通用结果缓存"""

    def __init__(self, subdir: str = "result_cache", ttl_hours: Optional[int] = None):
        self.base_path = Path(getattr(settings, "llm_cache_path", "./data/llm_cache")).parent / subdir
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours if ttl_hours is not None else getattr(settings, "llm_cache_ttl_hours", 240)

    def _path(self, key: str) -> Path:
        # 清理非法字符
        safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
        return self.base_path / f"{safe_key}.json"

    def get(self, key: str) -> Optional[dict]:
        """获取缓存结果，过期或不存在返回 None"""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            expires_at = data.get("expires_at")
            if expires_at:
                expires_dt = datetime.fromisoformat(expires_at)
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_dt:
                    path.unlink(missing_ok=True)
                    return None
            return data.get("result")
        except Exception:
            return None

    def set(self, key: str, result: dict, ttl_hours: Optional[int] = None) -> None:
        """写入缓存结果"""
        path = self._path(key)
        ttl = ttl_hours if ttl_hours is not None else self.ttl_hours
        now = datetime.now(timezone.utc)
        data = {
            "result": result,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=ttl)).isoformat(),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False


# 全局单例
result_cache_store = ResultCacheStore()
