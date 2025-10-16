import json
import os
from typing import Dict


def _path(data_dir: str) -> str:
    return os.path.join(data_dir, 'state.json')


def load_state(data_dir: str) -> Dict:
    p = _path(data_dir)
    if not os.path.exists(p):
        return {'hashes': [], 'counters': {}}
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_state(data_dir: str, state: Dict) -> None:
    p = _path(data_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def add_hash(data_dir: str, h: str) -> None:
    st = load_state(data_dir)
    hs = set(st.get('hashes') or [])
    if h not in hs:
        hs.add(h)
        st['hashes'] = list(hs)
        save_state(data_dir, st)


def has_hash(data_dir: str, h: str) -> bool:
    st = load_state(data_dir)
    return h in set(st.get('hashes') or [])

