# Smoke Test — youtube-bot

Follow this checklist before letting the scheduler run unattended.

1. **Environment**
   - Copy `.env.example` to `.env` and populate the real values (`YOUTUBE_CHANNEL_ID`, `PIPER_BIN`, etc.).
   - Place OAuth credentials in `credentials/client_secret.json`.

2. **Seed Data**
   - Drop fresh hooks into `assets/sources/shorts_hooks.ndjson` / `.json` (see schema in README).
   - Add at least a few MP3 tracks under `assets/music/`.
   - Put an ONNX sentence embedding model under `models/embeddings/e5-small/`.

3. **Authenticate YouTube (one-time)**
   ```bash
   python3 tools/youtube_uploader.py --auth-only
   ```

4. **Spin up local services** (LLM + Stable Diffusion + bot container)
   ```bash
   docker compose up -d
   ```

5. **Generate a single short**
   ```bash
   python3 bot_main.py
   ```
   Confirm new files appear in `data/video/` and `data/thumbs/`.

6. **Manual upload smoke test** (optional before automation)
   ```bash
   python3 tools/youtube_uploader.py --file data/video/<id>.mp4 \
     --thumb data/thumbs/<id>.png --title "Smoke Test" --desc "Automated" --privacy unlisted
   ```

7. **Analytics sanity**
   ```bash
   python3 tools/analytics_puller.py --since 2d --out data/metrics_latest.json
   jq '.[0]' data/metrics_latest.json
   ```

If all commands complete successfully, the nightly cron or `docker compose up -d` run is safe to leave unattended.
