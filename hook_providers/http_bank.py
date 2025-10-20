import csv
import io
import json
from typing import Dict, Iterable

import requests

from .base import HookProvider


class HttpBank(HookProvider):
    def __init__(self, url: str):
        self.url = url

    def list(self) -> Iterable[Dict]:
        if self.url.startswith("file://"):
            path = self.url[len("file://") :]
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            ct = "text/plain"
        else:
            r = requests.get(self.url, timeout=30)
            r.raise_for_status()
            text = r.text
            ct = r.headers.get("content-type", "")

        if "json" in ct or self.url.endswith((".json", ".jsonl")):
            for line in text.splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                yield {
                    "text": payload.get("text") or payload.get("hook"),
                    "seconds": int(payload.get("seconds") or 3),
                    "meta": payload,
                }
        elif "csv" in ct or self.url.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                yield {
                    "text": row.get("text") or row.get("hook"),
                    "seconds": int(row.get("seconds") or 3),
                    "meta": row,
                }
