import glob
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Iterable, Tuple

import requests

COMFY = os.getenv("COMFYUI_API_BASE", "http://127.0.0.1:8188")
RIFE = os.getenv("RIFE_BIN", "rife-ncnn-vulkan")
ESRGAN = os.getenv("ESRGAN_BIN", "realesrgan-ncnn-vulkan")


def _comfy_txt2vid(prompt: str, out_mp4: Path, graph_path: str) -> bool:
    graph_file = Path(graph_path)
    if not graph_file.exists():
        raise FileNotFoundError(f"Comfy graph not found: {graph_path}")
    graph = json.loads(graph_file.read_text())
    graph_str = json.dumps(graph).replace("__PROMPT__", prompt).replace("__OUT__", str(out_mp4))
    r = requests.post(f"{COMFY}/prompt", data=graph_str.encode("utf-8"), timeout=180)
    r.raise_for_status()
    return out_mp4.exists()


def _stockfx_compose(hook_text: str, music_glob: str, out_mp4: Path) -> bool:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_mp4.with_suffix(".hook.mp4")
    draw = (
        f"drawtext=text='{hook_text}':fontcolor=white:fontsize=64:"
        "x=(w-tw)/2:y=h/3:enable='between(t,0,4)',fade=t=in:st=0:d=0.5"
    )
    cmd = (
        f"ffmpeg -y -f lavfi -i color=c=black:s=720x1280:d=5 "
        f'-vf "{draw}" -c:v libx264 -pix_fmt yuv420p {shlex.quote(str(tmp))}'
    )
    subprocess.run(cmd, shell=True, check=True)
    tracks = glob.glob(music_glob) if music_glob else []
    if tracks:
        cmd2 = (
            f"ffmpeg -y -i {shlex.quote(str(tmp))} -stream_loop -1 -i {shlex.quote(tracks[0])} "
            f"-shortest -c:v copy -c:a aac {shlex.quote(str(out_mp4))}"
        )
    else:
        cmd2 = f"ffmpeg -y -i {shlex.quote(str(tmp))} -c:v copy {shlex.quote(str(out_mp4))}"
    subprocess.run(cmd2, shell=True, check=True)
    return True


def generate_hook_clip(
    prompt: str,
    out_mp4: Path,
    mode_order: Iterable[str] = None,
) -> Path:
    if mode_order is None:
        modes = os.getenv("VID_ENGINE_ORDER", "animatediff,cogvideox,stockfx").split(",")
        mode_order = [m.strip() for m in modes if m.strip()]

    graphs = {
        "animatediff": os.getenv("COMFYUI_GRAPH_HOOK", "graphs/hook_3s_api.json"),
    }

    for mode in mode_order:
        try:
            if mode == "animatediff":
                if _comfy_txt2vid(prompt, out_mp4, graphs["animatediff"]):
                    return out_mp4
            elif mode == "cogvideox":
                # Placeholder for local CogVideoX integration
                continue
            elif mode == "stockfx":
                music_glob = os.getenv("BG_MUSIC_GLOB", "assets/music/*.mp3")
                if _stockfx_compose(prompt, music_glob, out_mp4):
                    return out_mp4
        except Exception as exc:
            print(f"[video_gen] {mode} failed: {exc}")
            continue

    raise RuntimeError("All video engines failed")
