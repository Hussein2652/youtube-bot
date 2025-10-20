from typing import Dict, List, Optional, Tuple

import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


def fake_embed(text: str) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(text)) % (2**32))
    return rng.standard_normal(768)


def pick_hook(
    trends: List[Dict],
    hooks: List[Dict],
    k_tr: int = 30,
    k_hk: int = 120,
    threshold: float = 0.78,
) -> Optional[Dict]:
    scores: List[Tuple[float, Dict, Dict]] = []
    for tr in trends[:k_tr]:
        e_tr = fake_embed(tr.get("title", ""))
        for hk in hooks[:k_hk]:
            e_hk = fake_embed(hk.get("text", ""))
            sc = cosine(e_tr, e_hk)
            scores.append((sc, tr, hk))
    scores.sort(key=lambda item: item[0], reverse=True)
    for sc, tr, hk in scores:
        if sc >= threshold:
            return {"score": sc, "trend": tr, "hook": hk}
    if scores:
        sc, tr, hk = scores[0]
        return {"score": sc, "trend": tr, "hook": hk}
    return None
