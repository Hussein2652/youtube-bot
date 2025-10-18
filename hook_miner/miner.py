import glob
import os
import random
from typing import Dict, List

from utils import write_json, read_json, ensure_dir, log, slugify
from .sources import (
    YouTubeShortsAdapter,
    RedditAdapter,
    TikTokAdapter,
    collect_from_adapters,
)


def _seed_topics_path(data_dir: str) -> str:
    return os.path.join(data_dir, 'seeds', 'seed_topics.txt')


def discover_topics(data_dir: str, max_topics: int = 5) -> Dict:
    ensure_dir(os.path.join(data_dir, 'seeds'))
    seed_path = _seed_topics_path(data_dir)
    if not os.path.exists(seed_path):
        # Provide some defaults if seeds not present
        seeds = [
            'AI productivity',
            'Fitness myths',
            'Crypto trends',
            'Life hacks',
            'Motivation',
        ]
    else:
        with open(seed_path, 'r', encoding='utf-8') as f:
            seeds = [ln.strip() for ln in f if ln.strip()]

    random.shuffle(seeds)
    topics = seeds[:max_topics]
    return {
        'ok': True,
        'topics': topics,
        'count': len(topics),
    }


def _adapter_for_path(path: str):
    lower = path.lower()
    if lower.endswith('.jsonl') or lower.endswith('.ndjson'):
        if 'youtube' in lower or 'short' in lower:
            return YouTubeShortsAdapter(path)
    if lower.endswith('.json'):
        if 'reddit' in lower:
            return RedditAdapter(path)
        if 'tiktok' in lower:
            return TikTokAdapter(path)
        if 'youtube' in lower or 'short' in lower:
            return YouTubeShortsAdapter(path)
    return None


def mine_hooks(data_dir: str, topics: List[str], *, per_topic: int = 200, source_glob: str = 'assets/sources/*', cache_ttl: int = 6 * 3600, rate_limit: int = 5) -> Dict:
    ensure_dir(os.path.join(data_dir, 'cache', 'miner'))
    ensure_dir(os.path.join('assets', 'sources'))

    adapters = []
    for path in glob.glob(source_glob):
        adapter = _adapter_for_path(path)
        if adapter:
            adapters.append(adapter)

    items = collect_from_adapters(adapters, data_dir, cache_ttl=cache_ttl, rate_limit=rate_limit) if adapters else []
    hooks: List[Dict] = []
    for it in items:
        text = it.get('text', '')
        tags = [tag.lower() for tag in (it.get('topic_tags') or [])]
        for t in topics:
            topic_key = slugify(t)
            topic_words = [w.lower() for w in t.split()]
            stemmed = [w.rstrip('s') for w in topic_words]
            text_lower = text.lower()
            tag_match = (
                topic_key in tags
                or any(word in tags for word in topic_words)
                or any(word in tags for word in stemmed)
                or any(word in tag for tag in tags for word in topic_words + stemmed)
            )
            text_match = any(word in text_lower for word in topic_words + stemmed)
            if tag_match or text_match:
                hooks.append({
                    'topic': t,
                    'raw_text': text,
                    'source_url': it.get('url'),
                    'score': float(it.get('views') or 0.0),
                    'emotion': it.get('emotion'),
                    'duration': float(it.get('duration') or 0.0),
                    'source': it.get('source'),
                    'topic_tags': it.get('topic_tags', []),
                })
                break

    patterns = [
        "No one told you this about {topic}",
        "The truth about {topic} in 5 seconds",
        "Most people get {topic} wrong. Here's why",
        "Stop doing this if you care about {topic}",
        "I tested 100+ {topic} tips so you don't have to",
        "This {topic} hack changes everything",
        "New study just broke {topic}",
        "The fastest way to improve at {topic}",
    ]

    from collections import Counter
    counts = Counter(h['topic'] for h in hooks)
    for t in topics:
        needed = max(0, per_topic - counts.get(t, 0))
        for _ in range(needed):
            p = random.choice(patterns)
            hooks.append({
                'topic': t,
                'raw_text': p.format(topic=t),
                'source_url': None,
                'score': 0.0,
                'emotion': None,
                'duration': 5.0,
                'source': 'synthetic',
                'topic_tags': [],
            })

    path = os.path.join(data_dir, 'hooks_dataset.json')
    write_json(path, hooks)
    log(f"Mined hooks: {len(hooks)} -> {path}")
    return {
        'ok': True,
        'hooks_dataset_path': path,
        'topics_count': len(topics),
        'hooks_count': len(hooks),
    }
