import os
import subprocess
import tempfile
from typing import Optional

from .logs import log, err


def synthesize_with_command(tts_cmd: Optional[str], text: str, out_wav: str, *, piper_bin: Optional[str] = None, piper_voice: Optional[str] = None) -> bool:
    if not tts_cmd:
        return False
    template = os.path.expandvars(tts_cmd)
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
            tmp.write(text)
            tmp_path = tmp.name
        cmd = template.format(
            input_txt=tmp_path,
            text_file=tmp_path,
            infile=tmp_path,
            output_wav=out_wav,
            outfile=out_wav,
            output=out_wav,
            voice=piper_voice or '',
            piper_voice=piper_voice or '',
            piper_bin=piper_bin or '',
        )
        log(f"Running TTS command: {cmd}")
        proc = subprocess.run(cmd, shell=True, check=False)
        if proc.returncode != 0:
            err(f"TTS command failed with code {proc.returncode}")
            return False
        return os.path.exists(out_wav)
    except Exception as exc:  # pragma: no cover
        err(f"TTS command error: {exc}")
        return False
    finally:
        try:
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def synthesize_with_piper(piper_bin: Optional[str], voice: Optional[str], text: str, out_wav: str) -> bool:
    if not piper_bin or not voice:
        log("Piper not configured; skipping fallback TTS.")
        return False
    try:
        cmd = [piper_bin, '--model', voice, '--output_file', out_wav]
        log(f"Running Piper: {' '.join(cmd)}")
        proc = subprocess.run(cmd, input=text.encode('utf-8'), check=False)
        return proc.returncode == 0
    except Exception as e:
        err(f"Piper TTS error: {e}")
        return False
