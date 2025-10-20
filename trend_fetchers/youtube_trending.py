import re
from typing import Dict, List

import requests


class YouTubeTrending:
    def __init__(self, region: str):
        self.region = region

    def fetch(self, topn: int = 50) -> List[Dict]:
        r = requests.get(f"https://www.youtube.com/feed/trending?gl={self.region}", timeout=20)
        titles = re.findall(r'"title":\{"runs":\[\{"text":"(.{1,120}?)"\}\]\}', r.text)
        return [{"title": t, "region": self.region, "source": "youtube_trending"} for t in titles[:topn]]
