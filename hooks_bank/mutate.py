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


def _local_mutate_rules(text: str, variant: int = 0) -> str:
    """Deterministic, low-resource hook mutations that rotate vocabulary for uniqueness."""
    # Normalize punctuation and build replacements with variant-aware cycling
    t = text.strip()
    if t.endswith(':'):
        t = t[:-1]
    t = t.replace('everyone', 'most people').replace('No one', 'Almost no one')

    replacements = {
        'hack': ['tactic', 'play', 'angle', 'move'],
        'tips': ['moves', 'plays', 'angles', 'fixes'],
        'truth': ['signal', 'intel', 'inside', 'fact'],
        'wrong': ['off', 'flawed', 'broken', 'misaligned'],
        'stop': ['ditch', 'drop', 'scrap', 'skip'],
        'improve': ['level-up', 'boost', 'sharpen', 'upgrade'],
        'study': ['data', 'research', 'report', 'science'],
        'told': ['revealed', 'shared', 'exposed', 'showed'],
        'fastest': ['quickest', 'speediest', 'shortest', 'fast-track'],
        'changes': ['shifts', 'flips', 'rewires', 'reshapes'],
        'everything': ['all', 'it all', 'the game', 'your day'],
    }

    seed = abs(hash(text))
    words = t.split()
    rotated: List[str] = []
    salt = variant
    for w in words:
        key = w.lower().strip(':,!.?')
        opts = replacements.get(key)
        if opts:
            idx = (seed + salt) % len(opts)
            repl = opts[idx]
            if w[:1].isupper():
                repl = repl.capitalize()
            rotated.append(repl)
            salt += 1
        else:
            rotated.append(w)
        if len(rotated) >= 16:  # allow extra words; caller trims to 12 later
            break

    core = ' '.join(rotated)
    prefixes = ['Watch', 'Heads up', 'Real talk', 'Listen up', 'Quick tip']
    prefix = prefixes[(seed + variant) % len(prefixes)]
    if not core.lower().startswith(prefix.lower()):
        core = f"{prefix}: {core}"

    suffixes = ['', 'now', 'today', 'tonight', 'fast']
    suffix = suffixes[(seed // 7 + variant) % len(suffixes)]
    if suffix and suffix not in core.lower():
        core = f"{core} {suffix}"

    return core.strip()


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
                'text': _local_mutate_rules(h['raw_text'], variant=i),
                'emotion': h.get('emotion')
            }
            for i, h in enumerate(selected)
        ]

    seed_set = set(h['raw_text'].strip().lower() for h in selected)
    seen_hashes = set()
    mutated = []
    for i, h in enumerate(selected):
        entry = mutated_texts[i] if i < len(mutated_texts) else None
        emotion = h.get('emotion')
        max_attempts = 6
        accepted = False
        for attempt in range(max_attempts):
            if attempt == 0 and entry:
                cand = entry.get('text') or ''
                emotion = entry.get('emotion', emotion)
            else:
                cand = _local_mutate_rules(h['raw_text'], variant=i + attempt)
                emotion = h.get('emotion')
            cand = ' '.join(cand.split()[:12]).strip()
            if not cand:
                continue
            nh = _norm_hash(cand)
            if cand.lower() in seed_set:
                continue
            if data_dir and has_hash(data_dir, nh, topic=topic):
                continue
            if nh in seen_hashes:
                continue
            seen_hashes.add(nh)
            if data_dir:
                add_hash(data_dir, nh, topic=topic)
            mutated.append({**h, 'mutated_text': cand, 'emotion': emotion})
            accepted = True
            break
        if not accepted:
            continue
    return {
        'ok': True,
        'topic': topic,
        'mutated': mutated,
        'llm_called': llm_called,
        'count': len(mutated),
    }
