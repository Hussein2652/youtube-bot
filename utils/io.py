import json
import os
import re
from typing import Any, Dict


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path: str, data: Any) -> None:
    ensure_dir(os.path.dirname(path) or '.')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_slug_re = re.compile(r"[^a-z0-9\-]+")


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"\s+", '-', s)
    s = _slug_re.sub('', s)
    return s[:80]

