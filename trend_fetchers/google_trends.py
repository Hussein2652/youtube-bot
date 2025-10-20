import datetime as dt
from typing import Dict, List

try:
    from pytrends.request import TrendReq  # type: ignore
except Exception:  # pragma: no cover
    TrendReq = None  # type: ignore


class GoogleTrends:
    def __init__(self, region: str):
        self.region = region
        if TrendReq is None:
            self.tr = None
        else:
            self.tr = TrendReq(hl="en-US", tz=0)

    def fetch(self, topn: int = 50) -> List[Dict]:
        if self.tr is None:
            return []
        out: List[Dict] = []
        try:
            df = self.tr.trending_searches(pn=self.region.lower())
            for _, row in df.head(topn).iterrows():
                title = row[0]
                out.append({"title": title, "region": self.region, "source": "google_trends"})
        except Exception:
            pass
        return out
