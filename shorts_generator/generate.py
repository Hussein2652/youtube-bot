import glob
import os
import random
from typing import Dict, List, Optional
import subprocess
from utils import ensure_dir, run_ffmpeg, synthesize_with_piper, synthesize_with_command, log


def _escape_text(text: str) -> str:
    return text.replace(':', '\\:').replace("'", "\\'").replace(',', '\\,').replace('\n', '\\n')


def _line_breaks(text: str, max_chars: int = 28, max_lines: int = 3) -> str:
    words = text.split()
    lines: List[str] = []
    cur = ''
    for w in words:
        if len(cur) + len(w) + 1 > max_chars:
            lines.append(cur.strip())
            cur = w
            if len(lines) >= max_lines:
                break
        else:
            cur = (cur + ' ' + w).strip()
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return '\n'.join(lines)


def _segment_text_filters(segments: List[Dict], safe_top: int = 200) -> str:
    # Draw each segment in safe area with enable between times; render up to 3 lines separately
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    filters: List[str] = []
    for seg in segments:
        lines = _line_breaks(seg['text']).split('\n')
        enable = f"between(t\,{seg['start']:.2f}\,{seg['end']:.2f})"
        for idx, line in enumerate(lines[:3]):
            esc = _escape_text(line)
            y = safe_top + idx * 110
            filters.append(
                f"drawtext=fontfile={font}:text='{esc}':fontcolor=white:fontsize=58:x=(w-text_w)/2:y={y}:"
                f"box=1:boxcolor=black@0.3:boxborderw=20:shadowcolor=black:shadowx=2:shadowy=2:enable='{enable}'"
            )
    return ','.join(filters)


def _make_bg_video(ffmpeg_bin: str, out_path: str, duration: float) -> int:
    # Solid background color (varies) for SD fallback
    colors = ['#0ea5e9', '#ef4444', '#22c55e', '#a855f7', '#f59e0b']
    color = random.choice(colors)
    return run_ffmpeg(ffmpeg_bin, [
        '-f', 'lavfi', '-i', f"color=c={color}:s=1080x1920:d={duration:.2f}",
        '-r', '30', out_path
    ])


def _burn_segments(ffmpeg_bin: str, in_video: str, segments: List[Dict], out_video: str) -> int:
    vf = _segment_text_filters(segments)
    return run_ffmpeg(ffmpeg_bin, ['-i', in_video, '-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', out_video])


def _burn_simple_text(ffmpeg_bin: str, in_video: str, text: str, out_video: str) -> int:
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    esc = _escape_text(_line_breaks(text))
    vf = (
        f"drawtext=fontfile={font}:text='{esc}':fontcolor=white:fontsize=58:x=(w-text_w)/2:y=200:"
        f"box=1:boxcolor=black@0.3:boxborderw=20:shadowcolor=black:shadowx=2:shadowy=2"
    )
    return run_ffmpeg(ffmpeg_bin, ['-i', in_video, '-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', out_video])


def _find_music(music_dir: Optional[str], music_glob: Optional[str]) -> Optional[str]:
    candidates: List[str] = []
    if music_glob:
        candidates.extend(glob.glob(os.path.expandvars(music_glob)))
    if music_dir and os.path.isdir(music_dir):
        for fn in os.listdir(music_dir):
            if fn.lower().endswith(('.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg')):
                candidates.append(os.path.join(music_dir, fn))
    if not candidates:
        return None
    return random.choice(candidates)


def _mux_audio(ffmpeg_bin: str, in_video: str, voice_wav: str, out_video: str, music_path: Optional[str], music_vol_db: float) -> int:
    if music_path and os.path.exists(music_path):
        filter_complex = (
            "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11:print_format=none[voice];"
            "[2:a]loudnorm=I={mv}:TP=-2.0:LRA=9:print_format=none[music_norm];"
            "[music_norm][voice]sidechaincompress=threshold=-30dB:ratio=8:attack=5:release=400:makeup=0[music_duck];"
            "[voice][music_duck]amix=inputs=2:weights=1 0.35:duration=first:dropout_transition=2[mix];"
            "[mix]volume=1.0,aresample=async=1[a]"
        )
        filter_complex = filter_complex.format(mv=f"{music_vol_db}dB")
        return run_ffmpeg(ffmpeg_bin, [
            '-i', in_video,
            '-i', voice_wav,
            '-i', music_path,
            '-filter_complex', filter_complex,
            '-map', '0:v', '-map', '[a]',
            '-c:v', 'copy', '-c:a', 'aac', '-shortest', out_video
        ])
    else:
        return run_ffmpeg(ffmpeg_bin, [
            '-i', in_video,
            '-i', voice_wav,
            '-filter_complex', "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11:print_format=none[a]",
            '-map', '0:v', '-map', '[a]',
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


def _sd_make_image(cmd: Optional[str], prompt: str, out_path: str) -> bool:
    if not cmd:
        return False
    try:
        if "{" in cmd:
            formatted = cmd.format(
                prompt=prompt,
                outfile=out_path,
                out=out_path,
                output=out_path,
                output_png=out_path,
            )
            proc = subprocess.run(formatted, shell=True, check=False)
        else:
            proc = subprocess.run(f"{cmd} --prompt {prompt!r} --output {out_path!r}", shell=True, check=False)
        return proc.returncode == 0 and os.path.exists(out_path)
    except Exception:
        return False


def _ken_burns(ffmpeg_bin: str, image_path: str, out_path: str, duration: float) -> int:
    return run_ffmpeg(ffmpeg_bin, [
        '-loop', '1', '-i', image_path, '-t', f'{duration:.2f}', '-vf', "zoompan=z='min(zoom+0.0015,1.3)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',scale=1080:1920,setsar=1:1", '-r', '30', out_path
    ])


def generate_short(
    ffmpeg_bin: str,
    piper_bin: str,
    tts_voice: str,
    data_dir: str,
    script_text: str,
    duration_sec: float,
    *,
    segments: Optional[List[Dict]] = None,
    tts_cmd: Optional[str] = None,
    music_dir: Optional[str] = None,
    music_glob: Optional[str] = None,
    music_vol_db: float = -18.0,
    sd_bg_cmd: Optional[str] = None,
    sd_thumb_cmd: Optional[str] = None,
) -> Dict:
    ensure_dir(os.path.join(data_dir, 'video'))
    ensure_dir(os.path.join(data_dir, 'audio'))
    ensure_dir(os.path.join(data_dir, 'thumbs'))

    base = str(abs(hash(script_text)))
    tmp_bg = os.path.join(data_dir, 'video', f'{base}_bg.mp4')
    tmp_txt = os.path.join(data_dir, 'video', f'{base}_txt.mp4')
    out_mp4 = os.path.join(data_dir, 'video', f'{base}.mp4')
    out_wav = os.path.join(data_dir, 'audio', f'{base}.wav')
    out_png = os.path.join(data_dir, 'thumbs', f'{base}.png')

    # Background using SD1.5 if available, else color
    final_dur = max(7.0, min(15.0, duration_sec))
    sd_img = os.path.join(data_dir, 'video', f'{base}_bg.png')
    used_sd = False
    if sd_bg_cmd and _sd_make_image(sd_bg_cmd, prompt=script_text, out_path=sd_img):
        used_sd = True
        rc = _ken_burns(ffmpeg_bin, sd_img, tmp_bg, final_dur)
    else:
        rc = _make_bg_video(ffmpeg_bin, tmp_bg, final_dur)
    if rc != 0:
        return {'ok': False, 'error': 'bg_video_failed'}

    # Text overlay video (segment-aware with safe area)
    segs = segments or [{'text': script_text, 'start': 0.0, 'end': final_dur}]
    rc = _burn_segments(ffmpeg_bin, tmp_bg, segs, tmp_txt)
    if rc != 0:
        # Fallback to simple overlay if segmented captions fail
        rc2 = _burn_simple_text(ffmpeg_bin, tmp_bg, script_text, tmp_txt)
        if rc2 != 0:
            return {'ok': False, 'error': 'text_burn_failed'}

    # TTS or silence
    did_tts = synthesize_with_command(tts_cmd, script_text, out_wav, piper_bin=piper_bin, piper_voice=tts_voice)
    if not did_tts:
        did_tts = synthesize_with_piper(piper_bin, tts_voice, script_text, out_wav)
    if not did_tts:
        _make_silence(ffmpeg_bin, out_wav, final_dur)

    # Mux
    music = _find_music(music_dir, music_glob)
    rc = _mux_audio(ffmpeg_bin, tmp_txt, out_wav, out_mp4, music, music_vol_db)
    if rc != 0:
        return {'ok': False, 'error': 'mux_failed'}

    # Thumb
    if sd_thumb_cmd and _sd_make_image(sd_thumb_cmd, prompt=script_text, out_path=out_png):
        pass
    else:
        _extract_thumb(ffmpeg_bin, out_mp4, out_png)

    return {
        'ok': True,
        'video_path': out_mp4,
        'thumb_path': out_png,
        'audio_path': out_wav,
        'duration_sec': final_dur,
        'tts': did_tts,
        'sd_bg': used_sd,
    }
