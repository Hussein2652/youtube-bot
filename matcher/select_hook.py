from typing import Dict, List

import numpy as np


def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def fake_embed(s: str):
    rng = np.random.default_rng(abs(hash(s)) % (2**32))
    return rng.standard_normal(768)


def pick_hook(trends: List[Dict], hooks: List[Dict], k_tr=30, k_hk=120, threshold=0.78):
    scores = []
    for tr in trends[:k_tr]:
        e_tr = fake_embed(tr["title"])
        for hk in hooks[:k_hk]:
            e_hk = fake_embed(hk["text"])
            sc = cosine(e_tr, e_hk)
            scores.append((sc, tr, hk))
    scores.sort(key=lambda x: x[0], reverse=True)
    for sc, tr, hk in scores:
        if sc >= threshold:
            return {"score": sc, "trend": tr, "hook": hk}
    return scores[0] if scores else None
