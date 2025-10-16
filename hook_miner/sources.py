import json
import os
from typing import Dict, List
from utils.cache import JsonCache, RateLimiter
from utils import ensure_dir, log


def _normalize(rec: Dict) -> Dict:
    return {
        'text': rec.get('text') or rec.get('title') or '',
        'emotion': rec.get('emotion'),
        'views': int(rec.get('views') or 0),
        'duration': float(rec.get('duration') or 0.0),
        'source': rec.get('source') or 'unknown',
        'url': rec.get('url'),
    }


class LocalFileAdapter:
    def __init__(self, path: str):
        self.path = path

    def fetch(self, cache: JsonCache, limiter: RateLimiter) -> List[Dict]:
        key = f"local:{self.path}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        # No network: read JSON/NDJSON from file if present
        if not os.path.exists(self.path):
            return []
        items: List[Dict] = []
        if self.path.endswith('.ndjson'):
            with open(self.path, 'r', encoding='utf-8') as f:
                for ln in f:
                    if ln.strip():
                        items.append(_normalize(json.loads(ln)))
        else:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for rec in (data if isinstance(data, list) else data.get('items', [])):
                    items.append(_normalize(rec))
        cache.set(key, items)
        return items


def collect_from_adapters(adapters: List[LocalFileAdapter], data_dir: str, cache_ttl: int = 3600) -> List[Dict]:
    cache = JsonCache(os.path.join(data_dir, 'cache', 'miner'), ttl_sec=cache_ttl)
    limiter = RateLimiter(os.path.join(data_dir, 'rate'), per_key_interval_sec=5)
    all_items: List[Dict] = []
    for ad in adapters:
        items = ad.fetch(cache, limiter)
        all_items.extend(items)
    # basic sanitization and 5-sec hook heuristic
    norm: List[Dict] = []
    for r in all_items:
        t = (r.get('text') or '').strip()
        if 3 <= len(t.split()) <= 20:
            d = r.get('duration') or 0.0
            # keep 3–5s preferentially; allow up to 7s
            if d == 0.0 or (3.0 <= d <= 7.0):
                norm.append(r)
    return norm

