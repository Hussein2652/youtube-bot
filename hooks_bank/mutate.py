import json
import shlex
import subprocess
from typing import Dict, List, Optional


def should_wake_llm(queue_size: int, min_queue: int) -> bool:
    return queue_size < min_queue


def _local_mutate_rules(text: str) -> str:
    # Deterministic, emotion-preserving tweaks when LLM not available
    # - front-load urgency, tighten phrasing, add concrete framing
    t = text.strip()
    if t.endswith(':'):
        t = t[:-1]
    t = t.replace('everyone', 'most people').replace('No one', 'Almost no one')
    if not t.lower().startswith('watch'):
        t = 'Watch this: ' + t
    return t


def _try_llm_call(cmd: Optional[str], topic: str, hooks: List[Dict]) -> Optional[List[str]]:
    if not cmd:
        return None
    try:
        payload = json.dumps({'topic': topic, 'hooks': [h['raw_text'] for h in hooks]}, ensure_ascii=False)
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
        if isinstance(arr, list):
            return [str(x) for x in arr]
        return None
    except Exception:
        return None


def mutate_hooks(topic: str, hooks: List[Dict], llm_cmd: Optional[str], allow_llm: bool, limit: int = 10) -> Dict:
    selected = hooks[:limit]
    mutated_texts: Optional[List[str]] = None
    llm_called = False
    if allow_llm:
        mutated_texts = _try_llm_call(llm_cmd, topic, selected)
        llm_called = mutated_texts is not None

    if not mutated_texts:
        mutated_texts = [_local_mutate_rules(h['raw_text']) for h in selected]

    mutated = []
    for i, h in enumerate(selected):
        mutated.append({
            **h,
            'mutated_text': mutated_texts[i] if i < len(mutated_texts) else _local_mutate_rules(h['raw_text']),
        })
    return {
        'ok': True,
        'topic': topic,
        'mutated': mutated,
        'llm_called': llm_called,
        'count': len(mutated),
    }

