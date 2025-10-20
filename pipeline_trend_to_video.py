#!/usr/bin/env python3
import os, json
from pathlib import Path
from trend_fetchers import REGISTRY as TF
from hook_providers.http_bank import HttpBank
from matcher.select_hook import pick_hook
from video_gen.pipeline import generate_hook_clip

REGIONS=[r.strip() for r in os.getenv("TREND_REGIONS","US").split(",") if r.strip()]
SOURCES=[s.strip() for s in os.getenv("TREND_SOURCES","google_trends").split(",") if s.strip()]
BANK_URLS=[u.strip() for u in os.getenv("HOOK_PROVIDER_URLS","" ).split(",") if u.strip()]

outdir = Path("data/video"); outdir.mkdir(parents=True, exist_ok=True)

# 1) collect trends
trends=[]
for region in REGIONS:
    for src in SOURCES:
        try:
            trends += TF[src](region).fetch(topn=int(os.getenv("MATCH_TOPK_TRENDS","30")))
        except Exception as e:
            print(f"trend fetch {src}/{region} failed: {e}")

# 2) collect hooks
hooks=[]
for url in BANK_URLS:
    try:
        hooks += list(HttpBank(url).list())
    except Exception as e:
        print(f"hook fetch {url} failed: {e}")

if not trends:
    trends = [{"title": "Sample trend insight", "region": REGIONS[0] if REGIONS else "US", "source": "fallback"}]

if not hooks:
    raise SystemExit("No trends or hooks; check env TREND_* and HOOK_PROVIDER_URLS")

sel = pick_hook(trends, hooks,
                k_tr=int(os.getenv("MATCH_TOPK_TRENDS","30")),
                k_hk=int(os.getenv("MATCH_TOPK_HOOKS","120")),
                threshold=float(os.getenv("MATCH_SIM_THRESHOLD","0.78")))
print("SELECTED:", json.dumps(sel, ensure_ascii=False))

# 3) video generate
prompt = sel[2]["text"] if isinstance(sel, tuple) else sel["hook"]["text"]
vid = outdir/"trend_hook_001.mp4"
clip = generate_hook_clip(prompt, vid)
print("VIDEO:", clip)

# 4) title/tags stub (wire to your llm_runner next)
title = f"{sel[2]['text']} — {sel[1]['title']}" if isinstance(sel, tuple) else f"{sel['hook']['text']} — {sel['trend']['title']}"
(Path("data/scripts")).mkdir(parents=True, exist_ok=True)
(Path("data/scripts/title.txt")).write_text(title)
print("TITLE:", title)
