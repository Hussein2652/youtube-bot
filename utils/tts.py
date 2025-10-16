import subprocess
from typing import Optional
from .logs import log, err


def synthesize_with_piper(piper_bin: Optional[str], voice: Optional[str], text: str, out_wav: str) -> bool:
    if not piper_bin or not voice:
        log("Piper not configured; skipping TTS.")
        return False
    try:
        # Piper expects text on stdin, output wav via --output_file
        cmd = [piper_bin, '--model', voice, '--output_file', out_wav]
        log(f"Running Piper: {' '.join(cmd)}")
        proc = subprocess.run(cmd, input=text.encode('utf-8'), check=False)
        return proc.returncode == 0
    except Exception as e:
        err(f"Piper TTS error: {e}")
        return False

