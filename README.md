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

Quick Start
1) Copy `.env.example` to `.env` and adjust values.
2) Ensure `ffmpeg` is installed on host (or inside Docker).
3) Optional tools: Piper TTS (`PIPER_BIN`), Stable Diffusion generator (`SD_CMD`), uploader (`YOUTUBE_UPLOADER_CMD`).
4) Run: `python3 bot_main.py`

Key Env Vars
- DATA_DIR: persistent working directory (default: data)
- MIN_QUEUE: wake LLM only when queue below this (default: 6)
- DAILY_TARGET_MIN/MAX: daily schedule range (default: 10–20)
- PIPER_BIN, TTS_VOICE: Piper executable and voice model path
- FFMPEG_BIN: ffmpeg path (default: ffmpeg)
- SD_CMD: command to generate backgrounds/thumbnails via SD1.5/XL (optional)
- SD_BG_CMD: command for SD1.5 backgrounds (fast)
- SD_THUMB_CMD: command for SDXL thumbnails (quality)
- LLM_CMD: command to run local 20B LLM for hook mutation (optional; called only if inventory < MIN_QUEUE)
- YOUTUBE_UPLOADER_CMD: local uploader command (optional)
- YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID (if using native API client)
- EMBEDDINGS_BACKEND: `hash` (default) or `onnx` (requires local onnxruntime + compatible model wrapper)
- EMBEDDINGS_MODEL_PATH: local .onnx path (optional)
- MUSIC_DIR: folder with background music to mix (default: assets/music)

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

Supervisor Loop (bot_main.py)
- Discovers topics → mines hooks → filters relevant hooks → (conditionally) mutates via LLM → finalizes micro-script → generates short.mp4 + thumb.png → schedules jobs → optionally uploads pending jobs.
- Every ~48h: pulls analytics (stub) and updates learning weights.

Notes
- LLM is never called unless `queue_size < MIN_QUEUE`.
- If Piper/SD not configured, generator falls back to deterministic ffmpeg (solid background + text overlay + silent/tts audio) to keep pipeline functional.
 - Scheduler defaults to Cairo timezone; adjust cadence in `schedule_manager/scheduler.py` if needed.
