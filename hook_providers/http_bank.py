import csv
import json
from typing import Dict, Iterable

import requests

from .base import HookProvider


class HttpBank(HookProvider):
    def __init__(self, url: str):
        self.url = url

    def list(self) -> Iterable[Dict]:
        r = requests.get(self.url, timeout=30)
        ct = (r.headers.get("content-type") or "").lower()
        text = r.text
        if "json" in ct or self.url.endswith((".json", ".jsonl")):
            for line in text.splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                yield {
                    "text": payload.get("text") or payload.get("hook"),
                    "seconds": payload.get("seconds", 3),
                    "meta": payload,
                }
        elif "csv" in ct or self.url.endswith(".csv"):
            reader = csv.DictReader(text.splitlines())
            for row in reader:
                yield {
                    "text": row.get("text") or row.get("hook"),
                    "seconds": int(row.get("seconds") or 3),
                    "meta": row,
                }
