import math
from typing import Dict, List, Tuple


def _tokenize(text: str) -> List[str]:
    return [t for t in text.lower().split() if t]


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def rank_hooks_for_topic(topic: str, hooks: List[Dict], top_k: int = 20) -> Dict:
    topic_toks = _tokenize(topic)
    scored: List[Tuple[float, Dict]] = []
    for h in hooks:
        hook_toks = _tokenize(h['raw_text'])
        s = _jaccard(topic_toks, hook_toks)
        scored.append((s, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [
        {**h, 'score': float(s)} for (s, h) in scored[:top_k]
    ]
    return {
        'ok': True,
        'topic': topic,
        'top_hooks': top,
        'count': len(top),
    }

