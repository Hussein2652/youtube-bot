import json
import os
import shlex
import subprocess
import hashlib
from typing import Dict, List, Optional
from state import has_hash, add_hash
from utils import err


def should_wake_llm(queue_size: int, min_queue: int) -> bool:
    return queue_size < min_queue


def _local_mutate_rules(text: str) -> str:
    # Deterministic, emotion-preserving tweaks when LLM not available
    # - front-load urgency, tighten phrasing, add concrete framing
    t = text.strip()
    if t.endswith(':'):
        t = t[:-1]
    t = t.replace('everyone', 'most people').replace('No one', 'Almost no one')
    # Keep it short (<= 12 words), change some nouns/verbs simplisticly
    repl = {
        'hack': 'tactic', 'tips': 'moves', 'truth': 'signal', 'wrong': 'off', 'stop': 'ditch',
        'improve': 'level-up', 'study': 'data', 'told': 'revealed', 'fastest': 'quickest'
    }
    words = t.split()
    new = []
    for w in words:
        key = w.lower().strip(':,!.?')
        new.append(repl.get(key, w))
        if len(new) >= 12:
            break
    s = ' '.join(new)
    if not s.lower().startswith('watch'):
        s = 'Watch: ' + s
    return s


def _try_llm_call(cmd: Optional[str], topic: str, hooks: List[Dict]) -> Optional[List[Dict[str, str]]]:
    if not cmd:
        return None
    try:
        model = os.getenv('LLM_MODEL', '').strip() or 'gpt-oss-20b'
        prompt = {
            'task': 'mutate_hooks',
            'model': model,
            'topic': topic,
            'constraints': {
                'preserve_emotion': True,
                'preserve_structure': True,
                'change_nouns_verbs': True,
                'max_words': 12,
                'dedupe_against_seeds': True
            },
            'seeds': [
                {
                    'text': h['raw_text'],
                    'emotion': h.get('emotion')
                }
                for h in hooks
            ],
            'count': len(hooks)
        }
        payload = json.dumps(prompt, ensure_ascii=False)
        proc = subprocess.run(
            shlex.split(cmd),
            input=payload.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            return None
        out = proc.stdout.decode('utf-8', errors='ignore').strip()
        arr = json.loads(out)
        variants = []
        if isinstance(arr, dict) and isinstance(arr.get('variants'), list):
            items = arr['variants']
        elif isinstance(arr, dict) and isinstance(arr.get('mutations'), list):
            items = arr['mutations']
        elif isinstance(arr, list):
            items = arr
        else:
            return None
        for item in items:
            if isinstance(item, dict):
                text = str(item.get('text') or '').strip()
                emotion = item.get('emotion')
            else:
                text = str(item).strip()
                emotion = None
            if text:
                variants.append({'text': text, 'emotion': emotion})
        return variants or None
    except Exception as exc:
        err(f"LLM mutation command failed: {exc}")
        return None


def _norm_hash(s: str) -> str:
    return hashlib.sha256(' '.join(s.lower().split()).encode('utf-8')).hexdigest()


def mutate_hooks(topic: str, hooks: List[Dict], llm_cmd: Optional[str], allow_llm: bool, limit: int = 10, *, data_dir: Optional[str] = None) -> Dict:
    selected = hooks[:limit]
    mutated_texts: Optional[List[Dict[str, str]]] = None
    llm_called = False
    if allow_llm:
        mutated_texts = _try_llm_call(llm_cmd, topic, selected)
        llm_called = mutated_texts is not None

    if not mutated_texts:
        mutated_texts = [
            {
                'text': _local_mutate_rules(h['raw_text']),
                'emotion': h.get('emotion')
            }
            for h in selected
        ]

    seed_set = set(h['raw_text'].strip().lower() for h in selected)
    seen_hashes = set()
    mutated = []
    for i, h in enumerate(selected):
        entry = mutated_texts[i] if i < len(mutated_texts) else {
            'text': _local_mutate_rules(h['raw_text']),
            'emotion': h.get('emotion')
        }
        cand = entry.get('text') or _local_mutate_rules(h['raw_text'])
        # enforce <=12 words
        cand = ' '.join(cand.split()[:12])
        nh = _norm_hash(cand)
        # dedupe vs seeds and prior hash set
        if cand.strip().lower() in seed_set:
            continue
        if data_dir and has_hash(data_dir, nh, topic=topic):
            continue
        if nh in seen_hashes:
            continue
        seen_hashes.add(nh)
        if data_dir:
            add_hash(data_dir, nh, topic=topic)
        mutated.append({**h, 'mutated_text': cand, 'emotion': entry.get('emotion', h.get('emotion'))})
    return {
        'ok': True,
        'topic': topic,
        'mutated': mutated,
        'llm_called': llm_called,
        'count': len(mutated),
    }
