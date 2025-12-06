import hashlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .config import get_storage_dir


@dataclass
class CacheEntry:
    hash: str
    timestamp: float
    ttl: int
    data: dict

    def is_valid(self) -> bool:
        return (time.time() - self.timestamp) < self.ttl


class CacheManager:
    def __init__(self, project_path: str, ttl: int = 3600):
        self.project_path = project_path
        self.ttl = ttl
        self.cache_dir = get_storage_dir(project_path) / "cache"
        self.cache_dir.mkdir(exist_ok=True)

    def get_source_hash(self) -> str:
        """Hash all .cs files + ProjectVersion.txt"""
        hasher = hashlib.sha256()

        # Hash ProjectVersion.txt
        version_file = Path(self.project_path) / "ProjectSettings" / "ProjectVersion.txt"
        if version_file.exists():
            hasher.update(version_file.read_bytes())

        # Hash all .cs files (sorted for consistency)
        assets_path = Path(self.project_path) / "Assets"
        if assets_path.exists():
            cs_files = sorted(assets_path.rglob("*.cs"))
            for cs_file in cs_files:
                hasher.update(str(cs_file.relative_to(self.project_path)).encode())
                hasher.update(cs_file.read_bytes())

        return hasher.hexdigest()[:16]

    def _get_cache_path(self, cache_type: str, extra_key: str = "") -> Path:
        key = f"{cache_type}_{extra_key}" if extra_key else cache_type
        return self.cache_dir / f"{key}.json"

    def get(self, cache_type: str, extra_key: str = "") -> dict | None:
        """Get cached data if valid"""
        cache_path = self._get_cache_path(cache_type, extra_key)

        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text())
            entry = CacheEntry(**data)

            # Check hash match
            current_hash = self.get_source_hash()
            if entry.hash != current_hash:
                return None

            # Check TTL
            if not entry.is_valid():
                return None

            return entry.data

        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def set(self, cache_type: str, data: dict, extra_key: str = ""):
        """Save data to cache"""
        cache_path = self._get_cache_path(cache_type, extra_key)

        entry = CacheEntry(
            hash=self.get_source_hash(),
            timestamp=time.time(),
            ttl=self.ttl,
            data=data
        )

        cache_path.write_text(json.dumps(asdict(entry), indent=2))

    def invalidate(self, cache_type: str | None = None):
        """Invalidate cache (all or specific type)"""
        if cache_type:
            for f in self.cache_dir.glob(f"{cache_type}*.json"):
                f.unlink()
        else:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()

    def clear_all(self):
        """Clear entire cache directory"""
        for f in self.cache_dir.glob("*"):
            if f.is_file():
                f.unlink()


def get_cached_compile(project_path: str, ttl: int = 3600) -> dict | None:
    """Get cached compilation result"""
    cache = CacheManager(project_path, ttl)
    return cache.get("compile")


def set_cached_compile(project_path: str, success: bool, errors: list, ttl: int = 3600):
    """Cache compilation result"""
    cache = CacheManager(project_path, ttl)
    cache.set("compile", {
        "success": success,
        "errors": [asdict(e) if hasattr(e, '__dataclass_fields__') else e for e in errors]
    })


def invalidate_cache(project_path: str):
    """Invalidate all cache for project"""
    cache = CacheManager(project_path)
    cache.clear_all()
