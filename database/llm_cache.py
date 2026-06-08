"""
大模型输出缓存存储层
命名格式: {namespace}_{content_hash}.json
便于按命名空间检索和清理
"""

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from config import settings


class LLMCacheStore:
    """LLM输出缓存存储，基于文件系统JSON存储"""

    def __init__(self):
        self.base_path = Path(getattr(settings, "llm_cache_path", "./data/llm_cache"))
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = getattr(settings, "llm_cache_ttl_hours", 24)
        self.enabled = getattr(settings, "llm_cache_enabled", True)

    def _get_path(self, cache_key: str) -> Path:
        return self.base_path / f"{cache_key}.json"

    @staticmethod
    def compute_content_hash(messages: list[dict], temperature: float, max_tokens: int, model: str) -> str:
        """基于输入参数计算内容哈希"""
        content = json.dumps({
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "model": model,
        }, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:16]

    def build_cache_key(self, namespace: str, content_hash: str) -> str:
        """构建缓存键: {namespace}_{content_hash}"""
        # 清理命名空间中的非法字符
        safe_ns = namespace.replace(":", "_").replace("/", "_").replace("\\", "_")
        return f"{safe_ns}_{content_hash}"

    def get(
        self,
        namespace: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> Optional[str]:
        """获取缓存的LLM输出，如果过期或不存在则返回None"""
        if not self.enabled:
            return None

        content_hash = self.compute_content_hash(messages, temperature, max_tokens, model)
        cache_key = self.build_cache_key(namespace, content_hash)
        path = self._get_path(cache_key)

        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

        # 检查是否过期
        expires_at = data.get("expires_at")
        if expires_at:
            try:
                # 处理ISO格式时间戳
                expires_dt = datetime.fromisoformat(expires_at)
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_dt:
                    # 已过期，删除
                    self.delete_by_key(cache_key)
                    return None
            except (ValueError, OSError):
                pass

        return data.get("content")

    def set(
        self,
        namespace: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        model: str,
        content: str,
        ttl_hours: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """存储LLM输出到缓存，返回缓存键"""
        content_hash = self.compute_content_hash(messages, temperature, max_tokens, model)
        cache_key = self.build_cache_key(namespace, content_hash)
        path = self._get_path(cache_key)

        ttl = ttl_hours if ttl_hours is not None else self.ttl_hours
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl)

        data = {
            "content": content,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "namespace": namespace,
            "metadata": metadata or {},
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return cache_key

    def delete_by_key(self, cache_key: str) -> bool:
        """通过缓存键删除"""
        path = self._get_path(cache_key)
        if path.exists():
            path.unlink()
            return True
        return False

    def delete_by_namespace(self, namespace: str) -> int:
        """删除指定命名空间的所有缓存，返回删除数量"""
        safe_ns = namespace.replace(":", "_").replace("/", "_").replace("\\", "_")
        count = 0
        for path in self.base_path.glob(f"{safe_ns}_*.json"):
            path.unlink()
            count += 1
        return count

    def delete_expired(self) -> int:
        """清理所有过期缓存，返回删除数量"""
        count = 0
        now = datetime.now(timezone.utc)
        for path in self.base_path.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                expires_at = data.get("expires_at")
                if expires_at:
                    expires_dt = datetime.fromisoformat(expires_at)
                    if expires_dt.tzinfo is None:
                        expires_dt = expires_dt.replace(tzinfo=timezone.utc)
                    if now > expires_dt:
                        path.unlink()
                        count += 1
            except (json.JSONDecodeError, OSError, ValueError):
                # 损坏的文件也删除
                path.unlink()
                count += 1
        return count

    def clear_all(self) -> int:
        """清空所有缓存，返回删除数量"""
        count = 0
        for path in self.base_path.glob("*.json"):
            path.unlink()
            count += 1
        return count

    def list_namespaces(self) -> dict[str, int]:
        """列出所有命名空间及其缓存数量"""
        namespaces: dict[str, int] = {}
        for path in self.base_path.glob("*.json"):
            stem = path.stem
            # 提取命名空间（最后一个下划线之前的部分）
            if "_" in stem:
                ns = stem.rsplit("_", 1)[0]
                namespaces[ns] = namespaces.get(ns, 0) + 1
        return namespaces

    def list_by_namespace(self, namespace: str) -> list[dict]:
        """列出指定命名空间的所有缓存元数据"""
        safe_ns = namespace.replace(":", "_").replace("/", "_").replace("\\", "_")
        results = []
        for path in self.base_path.glob(f"{safe_ns}_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append({
                    "cache_key": path.stem,
                    "created_at": data.get("created_at"),
                    "expires_at": data.get("expires_at"),
                    "namespace": data.get("namespace"),
                    "metadata": data.get("metadata"),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        total_files = 0
        total_size = 0
        namespaces = self.list_namespaces()

        for path in self.base_path.glob("*.json"):
            total_files += 1
            total_size += path.stat().st_size

        return {
            "total_entries": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "namespaces": namespaces,
            "ttl_hours": self.ttl_hours,
            "enabled": self.enabled,
        }


# 全局单例
llm_cache_store = LLMCacheStore()
