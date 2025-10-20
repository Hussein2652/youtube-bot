youtube-bot — Local YouTube Shorts Automation (Skeleton)

Overview
- Local, Docker-friendly pipeline to discover topics, mine hooks, finalize micro-scripts, generate Shorts (voice + visuals), schedule, and upload.
- All config via env vars. SQLite persistence. Lightweight logs. Deterministic fallbacks when GPU tools unavailable.

Status
- This is a functional skeleton: modules, DB, env config, and an end-to-end supervisor loop. Heavy parts (LLM 20B, Stable Diffusion, Piper TTS, YouTube upload) are integrated via env-driven commands with safe fallbacks.

What’s New (pre-scale gaps closed)
- Hook miners: pluggable local adapters reading `assets/sources/*.json|*.ndjson`, with JSON cache + rate-limiter.
- Relevance filter: embedding-based ranking with local fallback (hash), bias-aware scoring from `assets/bias.json`, and per-topic selection persistence under `data/selections/`.
- LLM mutation policy: ≤12 words, preserve emotion/structure, change nouns/verbs, de-dupe vs seeds and across days via `data/state.json` hash set; LLM called only when `queue < MIN_QUEUE`.
- Script finisher: structured segments (HOOK → curiosity → payoff → CTA) and enforced 7–15s, ≤50 words.
- Shorts generator: caption safe-area with auto line-breaks, fallback overlay, optional SD1.5 backgrounds and SDXL thumbnails, optional background music mixed ~−18 dB under voice.
- Scheduler: Cairo cadence 18/day (11:00×5, 15:00×8, 19:30×5) with idempotent queue.
- Uploader: exponential backoff; store `platform_video_id` and timestamps; set `ready` when not uploaded.
- Analytics: 48h-after publish pull stub; compute score and update `assets/bias.json` (emotion + n‑gram weights) to bias next runs.
- Idempotency: unique hashes for scripts/videos, safe enqueues, persistent `data/bot.db` + `data/state.json`.
- Media CLIs: `llm_runner.py` (JSON mutator), `tools/youtube_uploader.py` (resumable uploads + thumbnail), `tools/analytics_puller.py` (post-48h metrics), and `tools/sd_bg.README` (SD command contract).

Quick Start
1) Copy `.env.example` to `.env` and adjust values.
2) Ensure `ffmpeg` is installed on host (or inside Docker).
3) Optional tools: Piper TTS (`PIPER_BIN`), Stable Diffusion generator (`SD_CMD`), uploader (`YOUTUBE_UPLOADER_CMD`).
4) Run: `python3 bot_main.py`

Operational Notes
- The fallback hook mutator now rotates vocabulary per attempt so the bot keeps producing fresh scripts even after the dedupe store (`data/state.json`) fills up.
- A successful generation run leaves new assets in `data/video/`, `data/audio/`, and `data/thumbs/`, plus queue rows in `data/bot.db` (check with `sqlite3 data/bot.db "select id,status,scheduled_for from queue order by id desc limit 5;"`).
- To enable uploads, point `YOUTUBE_UPLOADER_CMD` at your uploader CLI (see `.env.example`). The bot automatically respects privacy/category flags and exponential backoff if the command fails.
- If you want to retry uploads manually, run `python3 tools/youtube_uploader.py --file <mp4> --thumb <png> --title "..."`
- Drop vertical b-roll clips under `assets/footage/` (or adjust `FOOTAGE_DIR` / `FOOTAGE_GLOB`) to have renders crop, loop, and grade real footage. When no footage is available the generator falls back to animated fractal motion instead of static color blocks.
- Tag clips in `assets/footage/index.json` (see example below) so segments pull the most relevant b-roll before falling back to generic motion.
- Voiceovers now fall back to ffmpeg's flite voice (`FALLBACK_TTS_VOICE`) after checking your `TTS_CMD` or Piper config, so every short ships with narration before we ever consider silence.

Key Env Vars
- DATA_DIR: persistent working directory (default: data)
- MIN_QUEUE: wake LLM only when queue below this (default: 6)
- DAILY_TARGET_MIN/MAX: daily schedule range (default: 10–20)
- PIPER_BIN, PIPER_VOICE, TTS_CMD: Piper executable, voice model, and formatted command string
- FFMPEG_BIN: ffmpeg path (default: ffmpeg)
- SD_CMD: command to generate backgrounds/thumbnails via SD1.5/XL (optional)
- SD_BG_CMD: command for SD1.5 backgrounds (fast)
- SD_THUMB_CMD: command for SDXL thumbnails (quality)
- LLM_CMD / LLM_MODEL: command + model name for JSON mutate runner (invoked only when queue < MIN_QUEUE)
- YOUTUBE_UPLOADER_CMD: local uploader command (resumable uploads + thumbnail)
- YOUTUBE_CHANNEL_ID (if using native API client)
- PRIVACY_STATUS, CATEGORY_ID: default upload metadata
- EMBEDDINGS_BACKEND / EMB_MODEL_DIR / EMB_BATCH / EMB_DEVICE / TOPK_HOOKS / SIM_THRESHOLD: embedding backend, asset dir, batch size, device preference, ranking parameters
- MUSIC_DIR, BG_MUSIC_GLOB, BG_MUSIC_VOL_DB: background music folders, glob pattern, and target LUFS offset
- FOOTAGE_DIR / FOOTAGE_GLOB: optional local b-roll directory/glob for vertical background footage
- FOOTAGE_INDEX_PATH: optional JSON metadata file that maps clips to tags/topics for smarter b-roll matching
- FALLBACK_TTS_VOICE: ffmpeg flite voice name to use when custom TTS is unavailable
- MINER_CACHE_TTL_SEC / MINER_RATE_PER_KEY_SEC / MINER_SOURCE_GLOB: hook miner controls (cache + rate limit)
- ANALYTICS_CMD: analytics CLI (default `python3 tools/analytics_puller.py --since 2d --out data/metrics_latest.json`)

Data Layout
- `data/bot.db` — SQLite DB
- `data/hooks_dataset.json` — mined hook store
- `data/selections/*.json` — per-topic top-K selections for reproducibility
- `data/audio/`, `data/video/`, `data/thumbs/` — outputs
- `data/seeds/seed_topics.txt` — seed topics when offline
- `data/state.json` — global dedupe + counters
- `assets/bias.json` — emotion/ngram weights updated by analytics
- `assets/sources/` — drop your local scrapes here (miners read these)
- `assets/music/` — optional background music files
- `assets/footage/` — optional vertical b-roll library scanned for clips
- `assets/footage/index.json` — optional tag/weight metadata for b-roll selection
- `llm_runner.py` — local hook mutator CLI
- `tools/youtube_uploader.py` — resumable upload helper (OAuth required)
- `tools/analytics_puller.py` — metrics fetcher (YT Analytics API)
- `tools/sd_bg.README` — Stable Diffusion command contract

Supervisor Loop (bot_main.py)
- Discovers topics → mines hooks → filters relevant hooks → (conditionally) mutates via LLM → finalizes micro-script → generates short.mp4 + thumb.png → schedules jobs → optionally uploads pending jobs.
- Every ~48h: pulls analytics (stub) and updates learning weights.

Notes
- LLM is never called unless `queue_size < MIN_QUEUE`.
- If you skip Piper/SD, the generator still adds motion backgrounds (fractals) and synthesizes narration via flite so exports feel like real shorts out of the box.
- Scheduler defaults to Cairo timezone; adjust cadence in `schedule_manager/scheduler.py` if needed.
- Run `python3 tools/youtube_uploader.py --help` after placing OAuth secrets in `./credentials/client_secret.json`; tokens cache to `./credentials/token.json`.
- Run `python3 tools/analytics_puller.py --help` to confirm metrics fetch works; update `ANALYTICS_CMD` if you change arguments.

### B-Roll Index Format

Create `assets/footage/index.json` to steer how clips map to topics or keywords. Two supported shapes:

```json5
{
  "clips": [
    {"path": "ai/keyboard_closeup.mp4", "tags": ["ai", "workflow", "typing"], "weight": 1.2},
    {"path": "productivity/whiteboard.mp4", "tags": ["productivity", "planning"]}
  ]
}
```

Or group entries by tag key:

```json5
{
  "ai": [
    {"path": "ai/robot-arm.mp4"},
    {"path": "ai/desk-macro.mp4", "weight": 1.5}
  ],
  "default": [
    {"path": "generic/city-timelapse.mp4"}
  ]
}
```

Relative paths are resolved against `FOOTAGE_DIR` (or the index file). When the index is missing the bot still scans `FOOTAGE_DIR` / `FOOTAGE_GLOB` and randomly cycles through any footage before falling back to fractal motion.

### New: Trend→Hook→Video pipeline

1. Configure regions, sources, and hook banks in `.env`:
   ```
   TREND_REGIONS=US,GB
   TREND_SOURCES=google_trends,youtube_trending
   HOOK_PROVIDER_URLS=https://your-hook-bank/3s.jsonl,https://your-hook-bank/5s.csv
   ```
2. Run the orchestrator once to test the flow:
   ```
   python3 pipeline_trend_to_video.py
   ```
3. Inspect outputs under `data/video/` and `data/scripts/title.txt`.

**Quality ladder:** `video_gen.pipeline` tries AnimateDiff via ComfyUI first, then CogVideoX (placeholder hook), then a stock+FX ffmpeg compositor so the pipeline always returns a usable short even if the heavy engines are offline.

Go-Live Checklist
- Hook sources live under `assets/sources/` (`shorts_hooks.ndjson`, `shorts_hooks.json`) and feed the miner immediately.
- Drop your ONNX embedding assets in `/models/embeddings/e5-small/` (see `.env.example` keys `EMB_MODEL_DIR`, `EMB_BATCH`, `EMB_DEVICE`, `TOPK_HOOKS`, `SIM_THRESHOLD`).
- Configure media + LLM CLIs via `.env` (`TTS_CMD`, `SD_BG_CMD`, `SD_THUMB_CMD`, `LLM_CMD/LLM_MODEL`, `BG_MUSIC_*`).
- Provide YouTube OAuth secrets in `./credentials/`, then use `YOUTUBE_UPLOADER_CMD` and `ANALYTICS_CMD` for uploads + metrics.
- Run through `docs/SMOKE_TEST.md`; every command should succeed before scheduling daily runs.
