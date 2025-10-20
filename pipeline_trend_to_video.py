#!/usr/bin/env python3
import json
import os
from pathlib import Path

from matcher import pick_hook
from trend_fetchers import REGISTRY as TREND_FETCHERS
from hook_providers.http_bank import HttpBank
from video_gen.pipeline import generate_hook_clip


def main() -> None:
    regions = [r.strip() for r in os.getenv("TREND_REGIONS", "US").split(",") if r.strip()]
    sources = [s.strip() for s in os.getenv("TREND_SOURCES", "google_trends").split(",") if s.strip()]
    bank_urls = [u.strip() for u in os.getenv("HOOK_PROVIDER_URLS", "").split(",") if u.strip()]

    out_dir = Path("data/video")
    out_dir.mkdir(parents=True, exist_ok=True)

    trends = []
    for region in regions:
        for src in sources:
            fetcher_cls = TREND_FETCHERS.get(src)
            if not fetcher_cls:
                print(f"Unknown trend source: {src}")
                continue
            try:
                trends.extend(
                    fetcher_cls(region).fetch(topn=int(os.getenv("MATCH_TOPK_TRENDS", "30")))
                )
            except Exception as exc:
                print(f"trend fetch {src}/{region} failed: {exc}")

    hooks = []
    for url in bank_urls:
        try:
            hooks.extend(list(HttpBank(url).list()))
        except Exception as exc:
            print(f"hook fetch {url} failed: {exc}")

    if not trends or not hooks:
        raise SystemExit("No trends or hooks; verify TREND_* and HOOK_PROVIDER_URLS env variables.")

    selection = pick_hook(
        trends,
        hooks,
        k_tr=int(os.getenv("MATCH_TOPK_TRENDS", "30")),
        k_hk=int(os.getenv("MATCH_TOPK_HOOKS", "120")),
        threshold=float(os.getenv("MATCH_SIM_THRESHOLD", "0.78")),
    )

    print("SELECTED:", json.dumps(selection, ensure_ascii=False))
    if not selection:
        raise SystemExit("Matcher returned no hook.")

    prompt = selection["hook"]["text"]
    vid_path = out_dir / "trend_hook_001.mp4"
    clip = generate_hook_clip(prompt, vid_path)
    print("VIDEO:", clip)

    title = f"{selection['hook']['text']} — {selection['trend']['title']}"
    scripts_dir = Path("data/scripts")
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "title.txt").write_text(title, encoding="utf-8")
    print("TITLE:", title)


if __name__ == "__main__":
    main()
