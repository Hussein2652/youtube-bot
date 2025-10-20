import requests
from typing import Dict, List

SUBS = ["AskReddit", "todayilearned", "worldnews", "technology", "videos"]


class RedditHot:
    def __init__(self, region: str):
        self.region = region

    def fetch(self, topn: int = 50) -> List[Dict]:
        out: List[Dict] = []
        for sub in SUBS:
            try:
                r = requests.get(
                    f"https://www.reddit.com/r/{sub}/hot.json?limit=50",
                    headers={"User-Agent": "ybot/1.0"},
                    timeout=20,
                )
                for it in r.json().get("data", {}).get("children", []):
                    title = it["data"].get("title", "")
                    if title:
                        out.append({"title": title, "sub": sub, "region": self.region, "source": "reddit_hot"})
            except Exception:
                continue
        return out[:topn]
