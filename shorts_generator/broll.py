import glob
import os
import random
import re
from typing import Dict, List, Optional

from utils import read_json


def _infer_tags_from_name(path: str) -> List[str]:
    stem = os.path.splitext(os.path.basename(path))[0]
    tokens = re.split(r'[^0-9a-zA-Z]+', stem.lower())
    return [tok for tok in tokens if tok and len(tok) >= 3]


def _normalize_path(path: str, base_dir: Optional[str]) -> str:
    if os.path.isabs(path):
        return path
    if base_dir:
        return os.path.normpath(os.path.join(base_dir, path))
    return os.path.abspath(path)


def _load_index(index_path: str, base_dir: Optional[str]) -> List[Dict]:
    data = read_json(index_path, default=None)
    if not data:
        return []

    entries: List[Dict] = []

    def _push(item: Dict, inherited_tags: Optional[List[str]] = None) -> None:
        if not isinstance(item, dict):
            return
        raw_path = item.get('path')
        if not raw_path:
            return
        full = _normalize_path(str(raw_path), base_dir)
        if not os.path.exists(full):
            return
        tags = []
        if inherited_tags:
            tags.extend(inherited_tags)
        item_tags = item.get('tags') or item.get('keywords')
        if isinstance(item_tags, (list, tuple)):
            tags.extend(str(t).lower() for t in item_tags if isinstance(t, str))
        weight = float(item.get('weight', 1.0) or 1.0)
        entries.append({
            'path': full,
            'tags': list(dict.fromkeys(tags)) or _infer_tags_from_name(full),
            'weight': weight,
        })

    if isinstance(data, list):
        for item in data:
            _push(item)
    elif isinstance(data, dict):
        if 'clips' in data and isinstance(data['clips'], list):
            for item in data['clips']:
                _push(item)
        else:
            for tag, items in data.items():
                if not isinstance(items, list):
                    continue
                inherited = [str(tag).lower()]
                for item in items:
                    _push(item, inherited_tags=inherited)

    return entries


def load_broll_library(
    footage_dir: Optional[str],
    footage_glob: Optional[str],
    index_path: Optional[str],
) -> Dict:
    clips: List[Dict] = []
    base_dir = footage_dir or (os.path.dirname(index_path) if index_path else None)

    if index_path and os.path.exists(index_path):
        clips.extend(_load_index(index_path, base_dir))

    discovered: List[str] = []
    if footage_glob:
        discovered.extend(glob.glob(os.path.expandvars(footage_glob), recursive=True))
    if footage_dir and os.path.isdir(footage_dir):
        for root, _dirs, files in os.walk(footage_dir):
            for fn in files:
                if fn.lower().endswith(('.mp4', '.mov', '.mkv', '.webm', '.m4v')):
                    discovered.append(os.path.join(root, fn))

    known_paths = {clip['path'] for clip in clips}
    for path in discovered:
        full = _normalize_path(path, None)
        if full in known_paths or not os.path.exists(full):
            continue
        clips.append({
            'path': full,
            'tags': _infer_tags_from_name(full),
            'weight': 1.0,
        })
        known_paths.add(full)

    return {'clips': clips}


def _keywords_from_text(text: str) -> List[str]:
    parts = re.findall(r"[A-Za-z0-9']+", text.lower())
    return [p for p in parts if len(p) >= 4]


def pick_broll_sequence(
    library: Dict,
    topic: Optional[str],
    script_text: str,
    segments: List[Dict],
) -> List[Dict]:
    clips: List[Dict] = library.get('clips') or []
    if not clips:
        return []

    keywords = set(_keywords_from_text(script_text or ''))
    if topic:
        keywords.update(_keywords_from_text(topic))
    if not keywords:
        keywords.update({'story', 'people', 'scene'})

    scored: List[Dict] = []
    for clip in clips:
        tags = {t.lower() for t in (clip.get('tags') or [])}
        matches = len(keywords & tags)
        bonus = clip.get('weight', 1.0) or 1.0
        score = matches * 2.0 + bonus * 0.25
        if matches == 0:
            score = 0.15 * bonus
        scored.append({'clip': clip, 'score': score + random.random() * 0.05})

    if not scored:
        return []

    scored.sort(key=lambda item: item['score'], reverse=True)
    ordered = [item['clip'] for item in scored]

    segs = segments or [{'start': 0.0, 'end': 4.0}]
    selections: List[Dict] = []
    for idx, seg in enumerate(segs):
        duration = float(seg.get('end', 0.0) - seg.get('start', 0.0))
        if not duration or duration <= 0:
            duration = 3.0
        clip = ordered[idx % len(ordered)]
        selections.append({
            'path': clip['path'],
            'tags': clip.get('tags') or [],
            'duration': max(1.5, duration),
        })

    return selections
