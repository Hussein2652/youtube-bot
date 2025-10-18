#!/usr/bin/env python3
"""Local JSON-in/JSON-out hook mutator for GPT-OSS 20B contract."""

import json
import os
import random
import sys
from typing import Dict, List, Set


REPLACEMENTS = {
    'hack': ['move', 'tactic', 'switch'],
    'money': ['cash', 'capital', 'stack'],
    'tools': ['systems', 'engines', 'kits'],
    'illegal': ['forbidden', 'taboo', 'off limits'],
    'secret': ['hidden', 'covert', 'quiet'],
    'habit': ['ritual', 'loop', 'pattern'],
    'side': ['shadow', 'stealth', 'quiet'],
    'hustle': ['grind', 'play', 'scheme'],
    'viral': ['explosive', 'trend ready', 'shareable'],
    'ai': ['machine', 'bot', 'neural'],
    'investors': ['backers', 'angels', 'funders'],
    'sleep': ['rest', 'dream', 'lights-out'],
    'five': ['5'],
}


def mutate_text(text: str, salt: int) -> str:
    words = text.split()
    random.seed(salt)
    mutated: List[str] = []
    for w in words:
        key = ''.join(ch for ch in w.lower() if ch.isalpha())
        if key in REPLACEMENTS:
            mutated.append(random.choice(REPLACEMENTS[key]))
        else:
            mutated.append(w)
    # tweak verbs by swapping order of first two words when possible
    if len(mutated) > 4:
        mutated[0], mutated[1] = mutated[1], mutated[0]
    text_out = ' '.join(mutated)
    tokens = text_out.split()
    if len(tokens) > 12:
        text_out = ' '.join(tokens[:12])
    return text_out.strip()


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({'error': 'empty input'}), file=sys.stderr)
        return 1
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({'error': f'invalid json: {exc}'}), file=sys.stderr)
        return 1

    if payload.get('task') != 'mutate_hooks':
        print(json.dumps({'error': 'unsupported task'}), file=sys.stderr)
        return 2

    requested_model = payload.get('model')
    env_model = os.getenv('LLM_MODEL', '').strip()
    if env_model and requested_model and requested_model != env_model:
        print(json.dumps({'error': f"model {requested_model} unavailable"}), file=sys.stderr)
        return 3
    if not env_model:
        print(json.dumps({'error': 'LLM_MODEL environment variable not set'}), file=sys.stderr)
        return 3

    count = int(payload.get('count') or 0) or 10
    seeds = payload.get('seeds') or []
    constraints: Dict = payload.get('constraints') or {}
    max_words = int(constraints.get('max_words') or 12)

    seed_texts: Set[str] = set()
    for seed in seeds:
        text = (seed.get('text') or '').strip()
        if text:
            seed_texts.add(text.lower())

    variants = []
    seen: Set[str] = set(seed_texts)
    base = seeds or [{'text': payload.get('topic', '')}]

    salt = 0
    while len(variants) < count and salt < count * 10:
        template = base[salt % len(base)]
        source_text = template.get('text', '')
        if not source_text:
            salt += 1
            continue
        mutated = mutate_text(source_text, salt)
        tokens = mutated.split()
        if len(tokens) > max_words:
            mutated = ' '.join(tokens[:max_words])
        if mutated.lower() in seen or not mutated:
            salt += 1
            continue
        seen.add(mutated.lower())
        variants.append({'text': mutated, 'emotion': template.get('emotion')})
        salt += 1

    fallback_topic = payload.get('topic', 'Viral idea')
    while len(variants) < count:
        filler = f"{fallback_topic.split()[0]} remix {len(variants)+1}"
        filler = ' '.join(filler.split()[:max_words])
        if filler.lower() in seen:
            filler = f"{fallback_topic.split()[0]} hook {len(variants)+1}"
        if filler.lower() not in seen:
            variants.append({'text': filler, 'emotion': seeds[0].get('emotion') if seeds else None})
            seen.add(filler.lower())

    print(json.dumps({'variants': variants[:count]}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
