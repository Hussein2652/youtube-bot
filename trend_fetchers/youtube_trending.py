import requests
from typing import Dict, List


class YouTubeTrending:
    def __init__(self, region: str):
        self.region = region

    def fetch(self, topn: int = 50) -> List[Dict]:
        url = f"https://www.youtube.com/feed/trending?gl={self.region}"
        r = requests.get(url, timeout=20)
        text = r.text
        needle = '"title":{"runs":[{"text":"'
        items: List[Dict] = []
        parts = text.split(needle)
        for tok in parts[1:topn + 1]:
            title = tok.split('"', 1)[0]
            if title and len(title) < 120:
                items.append({
                    "title": title,
                    "region": self.region,
                    "source": "youtube_trending",
                })
        return items[:topn]
