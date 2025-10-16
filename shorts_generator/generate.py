import os
import random
from typing import Dict
from utils import ensure_dir, run_ffmpeg, synthesize_with_piper, log


def _text_overlay_filter(text: str) -> str:
    # Simple, deterministic drawtext. Requires a font present in the image library.
    safe = text.replace(':', '\\:').replace("'", "\\'").replace(',', '\\,')
    # Scroll upwards slowly
    return (
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{safe}':"
        f"fontcolor=white:fontsize=60:x=(w-text_w)/2:y=h-50-30*t:shadowcolor=black:shadowx=2:shadowy=2"
    )


def _make_bg_video(ffmpeg_bin: str, out_path: str, duration: float) -> int:
    # Solid background color (varies) for SD fallback
    colors = ['#0ea5e9', '#ef4444', '#22c55e', '#a855f7', '#f59e0b']
    color = random.choice(colors)
    return run_ffmpeg(ffmpeg_bin, [
        '-f', 'lavfi', '-i', f"color=c={color}:s=1080x1920:d={duration:.2f}",
        '-r', '30', out_path
    ])


def _burn_text(ffmpeg_bin: str, in_video: str, text: str, out_video: str) -> int:
    return run_ffmpeg(ffmpeg_bin, [
        '-i', in_video,
        '-vf', _text_overlay_filter(text),
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18',
        out_video
    ])


def _mux_audio(ffmpeg_bin: str, in_video: str, in_audio: str, out_video: str) -> int:
    return run_ffmpeg(ffmpeg_bin, [
        '-i', in_video, '-i', in_audio,
        '-c:v', 'copy', '-c:a', 'aac', '-shortest', out_video
    ])


def _make_silence(ffmpeg_bin: str, out_wav: str, duration: float) -> int:
    return run_ffmpeg(ffmpeg_bin, [
        '-f', 'lavfi', '-i', f"anullsrc=r=48000:cl=stereo", '-t', f"{duration:.2f}", out_wav
    ])


def _extract_thumb(ffmpeg_bin: str, in_video: str, out_png: str) -> int:
    return run_ffmpeg(ffmpeg_bin, [
        '-ss', '00:00:01.000', '-i', in_video, '-vframes', '1', out_png
    ])


def generate_short(ffmpeg_bin: str, piper_bin: str, tts_voice: str, data_dir: str, script_text: str, duration_sec: float) -> Dict:
    ensure_dir(os.path.join(data_dir, 'video'))
    ensure_dir(os.path.join(data_dir, 'audio'))
    ensure_dir(os.path.join(data_dir, 'thumbs'))

    base = str(abs(hash(script_text)))
    tmp_bg = os.path.join(data_dir, 'video', f'{base}_bg.mp4')
    tmp_txt = os.path.join(data_dir, 'video', f'{base}_txt.mp4')
    out_mp4 = os.path.join(data_dir, 'video', f'{base}.mp4')
    out_wav = os.path.join(data_dir, 'audio', f'{base}.wav')
    out_png = os.path.join(data_dir, 'thumbs', f'{base}.png')

    # Background
    rc = _make_bg_video(ffmpeg_bin, tmp_bg, max(7.0, min(15.0, duration_sec)))
    if rc != 0:
        return {'ok': False, 'error': 'bg_video_failed'}

    # Text overlay video
    rc = _burn_text(ffmpeg_bin, tmp_bg, script_text, tmp_txt)
    if rc != 0:
        return {'ok': False, 'error': 'text_burn_failed'}

    # TTS or silence
    did_tts = synthesize_with_piper(piper_bin, tts_voice, script_text, out_wav)
    if not did_tts:
        _make_silence(ffmpeg_bin, out_wav, max(7.0, min(15.0, duration_sec)))

    # Mux
    rc = _mux_audio(ffmpeg_bin, tmp_txt, out_wav, out_mp4)
    if rc != 0:
        return {'ok': False, 'error': 'mux_failed'}

    # Thumb
    _extract_thumb(ffmpeg_bin, out_mp4, out_png)

    return {
        'ok': True,
        'video_path': out_mp4,
        'thumb_path': out_png,
        'audio_path': out_wav,
        'duration_sec': max(7.0, min(15.0, duration_sec)),
        'tts': did_tts,
    }

