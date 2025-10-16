import subprocess
from typing import List
from .logs import log, err


def run_ffmpeg(ffmpeg_bin: str, args: List[str]) -> int:
    cmd = [ffmpeg_bin, '-y'] + args
    log(f"Running ffmpeg: {' '.join(cmd)}")
    try:
        return subprocess.run(cmd, check=False).returncode
    except Exception as e:
        err(f"ffmpeg failed to start: {e}")
        return 1

