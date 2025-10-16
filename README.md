youtube-bot — Local YouTube Shorts Automation (Skeleton)

Overview
- Local, Docker-friendly pipeline to discover topics, mine hooks, finalize micro-scripts, generate Shorts (voice + visuals), schedule, and upload.
- All config via env vars. SQLite persistence. Lightweight logs. Deterministic fallbacks when GPU tools unavailable.

Status
- This is a functional skeleton: modules, DB, env config, and an end-to-end supervisor loop. Heavy parts (LLM 20B, Stable Diffusion, Piper TTS, YouTube upload) are integrated via env-driven commands with safe fallbacks.

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
- LLM_CMD: command to run local 20B LLM for hook mutation (optional; called only if inventory < MIN_QUEUE)
- YOUTUBE_UPLOADER_CMD: local uploader command (optional)

Data Layout
- `data/bot.db` — SQLite DB
- `data/hooks_dataset.json` — mined hook store
- `data/audio/`, `data/video/`, `data/thumbs/` — outputs
- `data/seeds/seed_topics.txt` — seed topics when offline

Supervisor Loop (bot_main.py)
- Discovers topics → mines hooks → filters relevant hooks → (conditionally) mutates via LLM → finalizes micro-script → generates short.mp4 + thumb.png → schedules jobs → optionally uploads pending jobs.
- Every ~48h: pulls analytics (stub) and updates learning weights.

Notes
- LLM is never called unless `queue_size < MIN_QUEUE`.
- If Piper/SD not configured, generator falls back to deterministic ffmpeg (solid background + text overlay + silent/tts audio) to keep pipeline functional.

