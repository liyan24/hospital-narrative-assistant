"""定位 .agents/skills 目录下的 skill 资源；目录缺失时返回 None 供上层降级。"""
from functools import lru_cache
from pathlib import Path

# 项目根目录（本文件位于 services/research/skill_packs/ 下）
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILLS_ROOT = PROJECT_ROOT / ".agents" / "skills"


@lru_cache(maxsize=None)
def skill_dir(name: str) -> Path | None:
    """返回指定 skill 的目录，不存在时返回 None"""
    d = SKILLS_ROOT / name
    return d if d.is_dir() else None


@lru_cache(maxsize=None)
def skill_file(skill: str, *rel: str) -> Path | None:
    """返回 skill 目录下的文件，不存在时返回 None"""
    d = skill_dir(skill)
    if d is None:
        return None
    f = d.joinpath(*rel)
    return f if f.is_file() else None
