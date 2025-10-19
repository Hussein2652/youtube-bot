#!/usr/bin/env python3
import argparse
import base64
import json
import os
from pathlib import Path
import sys

import requests
from PIL import Image, ImageDraw

SD_API = os.getenv("SD_API_BASE", "http://127.0.0.1:7860").rstrip("/")


def save_png(b64_png: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(base64.b64decode(b64_png))


def fallback(out: Path, text: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (720, 1280), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    draw.text((24, 24), text[:200], fill=(230, 230, 230))
    img.save(out)


def txt2img(prompt: str, out: Path, width: int, height: int, steps: int = 25) -> None:
    payload = {
        "prompt": prompt,
        "steps": steps,
        "width": width,
        "height": height,
        "cfg_scale": 7,
        "sampler_name": "DPM++ 2M Karras",
    }
    resp = requests.post(f"{SD_API}/sdapi/v1/txt2img", json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("images"):
        raise RuntimeError("txt2img returned no images")
    save_png(data["images"][0], out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["video_bg", "thumb"])
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_path = Path(args.out)
    prompt = args.prompt

    try:
        if args.mode == "thumb":
            txt2img(prompt + ", cinematic, high detail, vibrant thumbnail", out_path, width=1280, height=720, steps=30)
        else:
            txt2img(prompt + ", simple soft background, subtle bokeh", out_path, width=720, height=1280, steps=20)
        return 0
    except Exception as exc:
        fallback(out_path, prompt)
        print(json.dumps({"warning": "sd_fallback", "error": str(exc)}))
        return 0


+if __name__ == "__main__":
+    sys.exit(main())
