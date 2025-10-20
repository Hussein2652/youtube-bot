import datetime as dt
import os
from typing import Dict, List

try:
    from pytrends.request import TrendReq  # type: ignore
except Exception as exc:  # pragma: no cover - optional dependency
    TrendReq = None  # type: ignore


class GoogleTrends:
    def __init__(self, region: str):
        self.region = region
        if TrendReq is None:
            raise RuntimeError("pytrends is not installed; install via pip to use GoogleTrends.")
        hl = os.getenv("GOOGLE_TRENDS_LANG", "en-US")
        tz = int(os.getenv("GOOGLE_TRENDS_TZ", "0"))
        self.tr = TrendReq(hl=hl, tz=tz)

    def fetch(self, topn: int = 50) -> List[Dict]:
        self.tr.build_payload(kw_list=["news"], geo=self.region)
        rising = None
        if len(self.region) == 2:
            try:
                rising = self.tr.trending_searches(pn=self.region.lower())
            except Exception:
                rising = None
        out: List[Dict] = []
        if rising is not None:
            for _, row in rising.head(topn).iterrows():
                out.append({
                    "title": row[0],
                    "region": self.region,
                    "source": "google_trends",
                    "fetched_at": dt.datetime.utcnow().isoformat(),
                })
        return out
