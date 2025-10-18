# Smoke Test Checklist

Run these commands from the repository root after filling in your `.env` (copy `.env.example` first). Each command must exit with status `0` and produce the noted artefacts.

```bash
# 1) Hook sources are in place
ls -lah assets/sources
head -n 3 assets/sources/shorts_hooks.ndjson
jq 'length' assets/sources/shorts_hooks.json

# 2) Embeddings → relevance selection
python - <<'PY'
import json
from relevance_filter import select
hooks=[
    {"text":"This AI tool feels illegal to use!"},
    {"text":"I asked an AI to do my job and it nailed it."}
]
sel = select("AI tools 2025", hooks, k=2)
open("data/hooks_selected.json", "w", encoding="utf-8").write(json.dumps(sel, indent=2))
print("OK", len(sel))
PY

# 3) LLM mutation CLI
cat > /tmp/llm_input.json <<'JSON'
{"task":"mutate_hooks","model":"gpt-oss-20b","topic":"AI tools that feel illegal in 2025",
"constraints":{"max_words":12,"preserve_emotion":true,"dedupe_against_seeds":true},
"seeds":[{"text":"This AI tool feels illegal to use!","emotion":"Shock"}],"count":3}
JSON
set -a; source .env; set +a
$LLM_CMD < /tmp/llm_input.json | tee /tmp/llm_output.json
jq '.variants | length' /tmp/llm_output.json

# 4) Piper TTS command
echo "Test TTS for the bot" > /tmp/tts.txt
eval "$(printf "%s" "$TTS_CMD" | sed "s|{input_txt}|/tmp/tts.txt|; s|{output_wav}|/tmp/tts.wav|")"
file /tmp/tts.wav

# 5) Stable Diffusion background + thumbnail commands
BG=$(mktemp -u /tmp/bg.XXXX.png); TH=$(mktemp -u /tmp/th.XXXX.png)
eval "$(printf "%s" "$SD_BG_CMD"   | sed "s|{prompt}|cinematic neon ai tech|; s|{output_png}|$BG|")"
eval "$(printf "%s" "$SD_THUMB_CMD"| sed "s|{prompt}|high-contrast thumbnail|; s|{output_png}|$TH|")"
ls -lah "$BG" "$TH"

# 6) Uploader OAuth + upload (requires valid credentials)
ffmpeg -f lavfi -i color=c=black:s=1280x720:d=2 -f lavfi -i anullsrc -shortest \
  -c:v libx264 -c:a aac /tmp/test.mp4 -y
convert -size 1280x720 xc:gray /tmp/test.png
TITLE="Bot Test $(date +%s)"
CMD=$(printf "%s" "$YOUTUBE_UPLOADER_CMD" |
  sed "s|{mp4}|/tmp/test.mp4|; s|{png}|/tmp/test.png|; s|{title}|$TITLE|; s|{description}|test upload|; s|{csv_tags}|ai,bot|; s|{privacy}|$PRIVACY_STATUS|; s|{category}|$CATEGORY_ID|")
bash -lc "$CMD" | tee /tmp/yt.json
jq -r '.videoId' /tmp/yt.json

# 7) Analytics pull
bash -lc "$ANALYTICS_CMD"
jq '.[0]' data/metrics_latest.json

# 8) Supervisor dry-run (set MIN_QUEUE=2, DAILY_TARGET_MIN=3, DAILY_TARGET_MAX=3 first)
python3 bot_main.py
sqlite3 data/bot.db 'SELECT id, script_id, status, platform_video_id FROM videos ORDER BY id DESC LIMIT 5;'
```

If all steps succeed, the bot is ready for day-to-day execution on this machine.
