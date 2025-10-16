import hashlib
import json
import os
import time
from typing import Any, Optional


def _safe_key(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:16]


class JsonCache:
    def __init__(self, base_dir: str, ttl_sec: int = 3600):
        self.base_dir = base_dir
        self.ttl = ttl_sec
        os.makedirs(base_dir, exist_ok=True)

    def path_for(self, key: str) -> str:
        return os.path.join(self.base_dir, f"{_safe_key(key)}.json")

    def get(self, key: str) -> Optional[Any]:
        p = self.path_for(key)
        try:
            st = os.stat(p)
            if time.time() - st.st_mtime > self.ttl:
                return None
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def set(self, key: str, value: Any) -> None:
        p = self.path_for(key)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)


class RateLimiter:
    def __init__(self, base_dir: str, per_key_interval_sec: int = 5):
        self.base_dir = base_dir
        self.interval = per_key_interval_sec
        os.makedirs(base_dir, exist_ok=True)

    def allow(self, key: str) -> bool:
        p = os.path.join(self.base_dir, f"{_safe_key(key)}.ts")
        now = time.time()
        try:
            with open(p, 'r', encoding='utf-8') as f:
                last = float(f.read().strip())
        except FileNotFoundError:
            last = 0.0
        if now - last >= self.interval:
            with open(p, 'w', encoding='utf-8') as f:
                f.write(str(now))
            return True
        return False

