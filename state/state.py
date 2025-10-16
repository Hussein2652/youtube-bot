import json
import os
from typing import Dict, Optional


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


def add_hash(data_dir: str, h: str, topic: Optional[str] = None) -> None:
    st = load_state(data_dir)
    hs = set(st.get('hashes') or [])
    updated = False
    if h not in hs:
        hs.add(h)
        st['hashes'] = list(hs)
        updated = True
    if topic:
        topic_map = st.setdefault('topic_hashes', {})
        topic_list = set(topic_map.get(topic, []))
        if h not in topic_list:
            topic_list.add(h)
            topic_map[topic] = list(topic_list)
            updated = True
    if updated:
        save_state(data_dir, st)


def has_hash(data_dir: str, h: str, topic: Optional[str] = None) -> bool:
    st = load_state(data_dir)
    if h in set(st.get('hashes') or []):
        return True
    if topic:
        topic_map = st.get('topic_hashes') or {}
        if h in set(topic_map.get(topic, []) or []):
            return True
    return False
