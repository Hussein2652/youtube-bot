import math
import os
from typing import Dict, List, Tuple, Optional
from utils import ensure_dir, write_json, slugify, read_json
from embeddings import EmbeddingModel, cosine_sim


def _tokenize(text: str) -> List[str]:
    return [t for t in text.lower().split() if t]


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _bias_score(text: str, emotion: Optional[str], bias: Dict) -> float:
    score = 1.0
    emw = (bias.get('emotion_weights') or {}).get((emotion or '').lower(), 1.0)
    score *= float(emw)
    grams = text.lower().split()
    ngram_w = bias.get('ngram_weights') or {}
    for g in grams:
        score *= float(ngram_w.get(g, 1.0))
    return score


def _load_bias(path: str) -> Dict:
    b = read_json(path, default=None)
    if not b:
        return {'emotion_weights': {}, 'ngram_weights': {}}
    return b


def rank_hooks_for_topic(
    topic: str,
    hooks: List[Dict],
    top_k: int = 20,
    *,
    data_dir: Optional[str] = None,
    embeddings_backend: str = 'hash',
    embeddings_model_path: Optional[str] = None,
    embeddings_tokenizer_path: Optional[str] = None,
) -> Dict:
    # Embedding-based relevance with bias
    em = EmbeddingModel(
        backend=embeddings_backend,
        model_path=embeddings_model_path,
        tokenizer_path=embeddings_tokenizer_path,
    )
    topic_vec = em.embed([topic])[0]
    texts = [h['raw_text'] for h in hooks]
    hook_vecs = em.embed(texts)

    bias = _load_bias(os.path.join('assets', 'bias.json')) if os.path.exists(os.path.join('assets', 'bias.json')) else {'emotion_weights': {}, 'ngram_weights': {}}

    scored: List[Tuple[float, Dict]] = []
    for h, v in zip(hooks, hook_vecs):
        rel = cosine_sim(topic_vec, v)
        bscore = _bias_score(h.get('raw_text', ''), h.get('emotion'), bias)
        s = rel * bscore
        scored.append((s, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [{**h, 'score': float(s)} for (s, h) in scored[:top_k]]

    # Persist per-topic selections for reproducibility
    if data_dir:
        sel_dir = os.path.join(data_dir, 'selections')
        ensure_dir(sel_dir)
        outp = os.path.join(sel_dir, f"{slugify(topic)}.json")
        write_json(outp, top)

    return {'ok': True, 'topic': topic, 'top_hooks': top, 'count': len(top)}
