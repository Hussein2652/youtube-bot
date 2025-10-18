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
    emb_model_dir: Optional[str] = None,
    sim_threshold: float = 0.0,
) -> Dict:
    # Embedding-based relevance with bias
    normalized_hooks: List[Dict] = []
    for h in hooks:
        raw_text = h.get('raw_text') or h.get('text') or ''
        if not raw_text:
            continue
        entry = dict(h)
        entry['raw_text'] = raw_text
        normalized_hooks.append(entry)

    if not normalized_hooks:
        return {'ok': True, 'topic': topic, 'top_hooks': [], 'count': 0}

    em = EmbeddingModel(
        backend=embeddings_backend,
        model_path=embeddings_model_path,
        tokenizer_path=embeddings_tokenizer_path,
        model_dir=emb_model_dir,
    )
    topic_vec = em.embed([topic])[0]
    texts = [h['raw_text'] for h in hooks]
    hook_vecs = em.embed(texts)

    bias = _load_bias(os.path.join('assets', 'bias.json')) if os.path.exists(os.path.join('assets', 'bias.json')) else {'emotion_weights': {}, 'ngram_weights': {}}

    scored: List[Tuple[float, Dict]] = []
    for h, v in zip(normalized_hooks, hook_vecs):
        rel = cosine_sim(topic_vec, v)
        bscore = _bias_score(h.get('raw_text', ''), h.get('emotion'), bias)
        s = rel * bscore
        scored.append((s, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    filtered = [(s, h) for (s, h) in scored if s >= sim_threshold]
    top = [{**h, 'score': float(s)} for (s, h) in filtered[:top_k]]

    # Persist per-topic selections for reproducibility
    if data_dir:
        sel_dir = os.path.join(data_dir, 'selections')
        ensure_dir(sel_dir)
        outp = os.path.join(sel_dir, f"{slugify(topic)}.json")
        write_json(outp, top)

        # also write cumulative selection snapshot
        snapshot_path = os.path.join(data_dir, 'hooks_selected.json')
        existing = read_json(snapshot_path, default={}) or {}
        existing[topic] = top
        write_json(snapshot_path, existing)

    return {'ok': True, 'topic': topic, 'top_hooks': top, 'count': len(top)}


def select(topic: str, hooks: List[Dict], k: int = 20, *, embeddings_backend: str = 'hash', model_dir: Optional[str] = None) -> List[Dict]:
    """Convenience wrapper returning a compact list of top hooks for quick scripts."""
    enriched = [{'raw_text': h.get('text') or h.get('raw_text', ''), **h} for h in hooks]
    res = rank_hooks_for_topic(
        topic,
        enriched,
        top_k=k,
        data_dir=None,
        embeddings_backend=embeddings_backend,
        embeddings_model_path=None,
        embeddings_tokenizer_path=None,
        emb_model_dir=model_dir,
        sim_threshold=0.0,
    )
    out = []
    for item in res['top_hooks']:
        out.append({'text': item['raw_text'], 'score': item['score']})
    return out
