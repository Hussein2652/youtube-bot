import requests
from typing import Dict, List

SUBS = ["AskReddit", "todayilearned", "worldnews", "technology", "videos"]


class RedditHot:
    def __init__(self, region: str):
        self.region = region

    def fetch(self, topn: int = 50) -> List[Dict]:
        out: List[Dict] = []
        headers = {"User-Agent": "ybot/1.0"}
        for sub in SUBS:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit=50"
            r = requests.get(url, headers=headers, timeout=20)
            data = r.json().get("data", {})
            for child in data.get("children", []):
                payload = child.get("data") or {}
                title = payload.get("title")
                if title:
                    out.append({
                        "title": title,
                        "sub": sub,
                        "region": self.region,
                        "source": "reddit_hot",
                    })
                if len(out) >= topn:
                    return out[:topn]
        return out[:topn]
