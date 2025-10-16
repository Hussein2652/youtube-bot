import json
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from utils.cache import JsonCache, RateLimiter
from utils import log


Hook = Dict[str, Optional[str]]


def _normalize(raw: Dict, *, source: str) -> Dict:
    """Normalize hook records to the required schema."""
    text = (raw.get('text') or raw.get('title') or '').strip()
    if not text:
        return {}
    emotion = raw.get('emotion') or raw.get('mood')
    try:
        views = int(float(raw.get('views') or raw.get('view_count') or raw.get('viewCount') or 0))
    except (TypeError, ValueError):
        views = 0
    try:
        duration = float(raw.get('duration') or raw.get('length_seconds') or raw.get('lengthSeconds') or raw.get('duration_seconds') or 0.0)
    except (TypeError, ValueError):
        duration = 0.0

    return {
        'text': text,
        'emotion': emotion,
        'views': views,
        'duration': duration,
        'source': source,
        'url': raw.get('url') or raw.get('share_url') or raw.get('short_link'),
    }


@dataclass
class BaseAdapter:
    name: str
    cache_key: str

    def fetch(self, cache: JsonCache, limiter: RateLimiter) -> List[Dict]:  # pragma: no cover - abstract
        raise NotImplementedError


@dataclass
class YouTubeShortsAdapter(BaseAdapter):
    path: str

    def __init__(self, path: str):
        super().__init__(name='youtube_shorts', cache_key=f'youtube:{path}')
        self.path = path

    def fetch(self, cache: JsonCache, limiter: RateLimiter) -> List[Dict]:
        cached = cache.get(self.cache_key)
        if cached is not None:
            return cached
        if not os.path.exists(self.path):
            return []

        if not limiter.allow(self.cache_key):
            cached = cache.get(self.cache_key)
            return cached or []

        items: List[Dict] = []
        with open(self.path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                normal = _normalize(
                    {
                        'text': data.get('title'),
                        'emotion': data.get('emotion'),
                        'views': data.get('view_count') or data.get('viewCount'),
                        'duration': data.get('length_seconds') or data.get('lengthSeconds'),
                        'url': data.get('url') or data.get('webpage_url')
                    },
                    source='youtube_shorts'
                )
                if normal:
                    items.append(normal)
        cache.set(self.cache_key, items)
        log(f"YouTubeShortsAdapter fetched {len(items)} hooks from {self.path}")
        return items


@dataclass
class RedditAdapter(BaseAdapter):
    path: str

    def __init__(self, path: str):
        super().__init__(name='reddit', cache_key=f'reddit:{path}')
        self.path = path

    def fetch(self, cache: JsonCache, limiter: RateLimiter) -> List[Dict]:
        cached = cache.get(self.cache_key)
        if cached is not None:
            return cached
        if not os.path.exists(self.path):
            return []
        if not limiter.allow(self.cache_key):
            cached = cache.get(self.cache_key)
            return cached or []
        with open(self.path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        posts = data.get('posts') if isinstance(data, dict) else data
        items: List[Dict] = []
        if posts:
            for p in posts:
                normal = _normalize(
                    {
                        'text': p.get('title') or p.get('hook'),
                        'emotion': p.get('flair_text') or p.get('emotion'),
                        'views': p.get('upvotes') or p.get('score'),
                        'duration': p.get('duration'),
                        'url': p.get('url') or p.get('permalink'),
                    },
                    source='reddit'
                )
                if normal:
                    items.append(normal)
        cache.set(self.cache_key, items)
        log(f"RedditAdapter fetched {len(items)} hooks from {self.path}")
        return items


@dataclass
class TikTokAdapter(BaseAdapter):
    path: str

    def __init__(self, path: str):
        super().__init__(name='tiktok', cache_key=f'tiktok:{path}')
        self.path = path

    def fetch(self, cache: JsonCache, limiter: RateLimiter) -> List[Dict]:
        cached = cache.get(self.cache_key)
        if cached is not None:
            return cached
        if not os.path.exists(self.path):
            return []
        if not limiter.allow(self.cache_key):
            cached = cache.get(self.cache_key)
            return cached or []
        items: List[Dict] = []
        with open(self.path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        clips = data.get('clips') if isinstance(data, dict) else data
        if clips:
            for clip in clips:
                normal = _normalize(
                    {
                        'text': clip.get('caption') or clip.get('text'),
                        'emotion': clip.get('emotion'),
                        'views': clip.get('play_count') or clip.get('views'),
                        'duration': clip.get('duration_sec') or clip.get('duration'),
                        'url': clip.get('share_link') or clip.get('url'),
                    },
                    source='tiktok'
                )
                if normal:
                    items.append(normal)
        cache.set(self.cache_key, items)
        log(f"TikTokAdapter fetched {len(items)} hooks from {self.path}")
        return items


def collect_from_adapters(adapters: Iterable[BaseAdapter], data_dir: str, cache_ttl: int, rate_limit: int) -> List[Dict]:
    cache = JsonCache(os.path.join(data_dir, 'cache', 'miner'), ttl_sec=cache_ttl)
    limiter = RateLimiter(os.path.join(data_dir, 'rate'), per_key_interval_sec=rate_limit)
    results: List[Dict] = []
    for adapter in adapters:
        try:
            fetched = adapter.fetch(cache, limiter)
            results.extend(fetched)
        except Exception as exc:  # pragma: no cover
            log(f"Adapter {adapter.name} failed: {exc}")
    return results

