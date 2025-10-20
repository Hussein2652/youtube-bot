import os, json, subprocess, shlex
from pathlib import Path

COMFY = os.getenv("COMFYUI_API_BASE","http://127.0.0.1:8188")

# ComfyUI REST — assumes a saved graph with __PROMPT__ and __OUT__ placeholders

def comfy_txt2vid(prompt: str, out_mp4: Path, graph_path: str):
    import requests
    with open(graph_path,"r") as f: graph=f.read()
    graph = graph.replace("__PROMPT__", prompt).replace("__OUT__", str(out_mp4))
    r = requests.post(f"{COMFY}/prompt", data=graph.encode("utf-8"), timeout=180)
    r.raise_for_status()
    return out_mp4.exists()

# Fallback: stock+FX (ffmpeg solid bg + animated text + optional music)

def stockfx_compose(hook_text: str, music_glob: str, out_mp4: Path):
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_mp4.with_suffix('.hook.mp4')
    cmd = f"ffmpeg -y -f lavfi -i color=c=black:s=720x1280:d=5 -vf \"drawtext=text='{hook_text}':fontcolor=white:fontsize=64:x=(w-tw)/2:y=h/3:enable='between(t,0,4)',fade=t=in:st=0:d=0.5\" -c:v libx264 -pix_fmt yuv420p {shlex.quote(str(tmp))}"
    subprocess.run(cmd, shell=True, check=True)
    import glob
    tracks = glob.glob(music_glob)
    if tracks:
        cmd2=f"ffmpeg -y -i {shlex.quote(str(tmp))} -stream_loop -1 -i {shlex.quote(tracks[0])} -shortest -c:v copy -c:a aac {shlex.quote(str(out_mp4))}"
    else:
        cmd2=f"ffmpeg -y -i {shlex.quote(str(tmp))} -c:v copy {shlex.quote(str(out_mp4))}"
    subprocess.run(cmd2, shell=True, check=True)
    return True


def generate_hook_clip(prompt: str, out_mp4: Path, mode_order=None):
    if mode_order is None:
        raw = os.getenv("VID_ENGINE_ORDER")
        if raw:
            mode_order = [m.strip() for m in raw.split(",") if m.strip()]
        else:
            mode_order = ("animatediff", "stockfx")
    graph = os.getenv("COMFYUI_GRAPH_HOOK","graphs/hook_3s_api.json")
    for mode in mode_order:
        try:
            if mode=="animatediff":
                if comfy_txt2vid(prompt, out_mp4, graph):
                    return out_mp4
            elif mode=="stockfx":
                if stockfx_compose(prompt, os.getenv("BG_MUSIC_GLOB","assets/music/*.mp3"), out_mp4):
                    return out_mp4
        except Exception as e:
            print(f"[{mode}] failed: {e}")
            continue
    raise RuntimeError("All video engines failed")
