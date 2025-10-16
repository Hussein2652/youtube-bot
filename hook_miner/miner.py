import os
import random
from typing import Dict, List, Optional
from utils import write_json, read_json, ensure_dir, log


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


def mine_hooks(data_dir: str, topics: List[str], per_topic: int = 20) -> Dict:
    # Placeholder mining: generate synthetic but plausible hook patterns
    patterns = [
        "No one told you this about {topic}:",
        "The truth about {topic} in 5 seconds:",
        "Everyone gets {topic} wrong. Here's why:",
        "Stop doing this if you care about {topic}:",
        "I tested 100+ {topic} tips so you don't have to:",
        "This {topic} hack changes everything:",
        "New study just broke {topic}:",
        "The fastest way to improve at {topic}:",
    ]
    hooks: List[Dict] = []
    for t in topics:
        for i in range(per_topic):
            p = random.choice(patterns)
            text = p.format(topic=t)
            hooks.append({
                'topic': t,
                'raw_text': text,
                'source_url': None,
                'score': 0.0,
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

