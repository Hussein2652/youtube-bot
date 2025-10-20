import glob
import os
import random
import subprocess
from typing import Dict, List, Optional

from utils import ensure_dir, run_ffmpeg, synthesize_with_piper, synthesize_with_command, log
from .broll import load_broll_library, pick_broll_sequence


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


def _make_footage_bg(ffmpeg_bin: str, source_path: str, out_path: str, duration: float) -> int:
    # Loop and crop the footage into 9:16 with subtle motion filters
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=cover,"
        "crop=1080:1920,"
        "setsar=1:1,"
        "fps=30,"
        "eq=saturation=1.25:contrast=1.05"
    )
    args = [
        '-stream_loop', '-1',
        '-i', source_path,
        '-vf', vf,
        '-t', f'{duration:.2f}',
        '-an',
        out_path,
    ]
    return run_ffmpeg(ffmpeg_bin, args)


def _make_fractal_bg(ffmpeg_bin: str, out_path: str, duration: float) -> int:
    # Dynamic fractal fallback to avoid flat color screens
    start_x = random.uniform(-1.0, 0.5)
    start_y = random.uniform(-0.8, 0.8)
    start_scale = random.uniform(1.2, 2.8)
    end_scale = random.uniform(0.2, 0.6)
    morph = random.uniform(0.003, 0.02)
    mandelbrot = (
        f"mandelbrot=s=480x854:rate=30:start_x={start_x}:start_y={start_y}:start_scale={start_scale}:"
        f"end_scale={end_scale}:morphxf={morph}:morphyf={morph * 1.3}:outer=iteration_count"
    )
    vf = "scale=1080:1920,setsar=1:1,fps=30,hue=h='2*PI*t':s=1.4"
    args = [
        '-f', 'lavfi',
        '-i', mandelbrot,
        '-vf', vf,
        '-t', f'{duration:.2f}',
        out_path,
    ]
    return run_ffmpeg(ffmpeg_bin, args)


def _prep_broll_clip(ffmpeg_bin: str, source_path: str, out_path: str, duration: float) -> int:
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=cover,"
        "crop=1080:1920,"
        "setsar=1:1,"
        "fps=30,"
        "eq=saturation=1.15:contrast=1.05"
    )
    args = [
        '-stream_loop', '-1',
        '-i', source_path,
        '-vf', vf,
        '-an',
        '-t', f'{duration:.2f}',
        '-preset', 'veryfast',
        '-crf', '18',
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-r', '30',
        out_path,
    ]
    return run_ffmpeg(ffmpeg_bin, args)


def _render_broll_sequence(
    ffmpeg_bin: str,
    selections: List[Dict],
    tmp_bg: str,
    data_dir: str,
    base: str,
) -> int:
    prepped: List[str] = []
    for idx, sel in enumerate(selections):
        clip_out = os.path.join(data_dir, 'video', f'{base}_broll_{idx}.mp4')
        rc = _prep_broll_clip(ffmpeg_bin, sel['path'], clip_out, sel['duration'])
        if rc != 0:
            return rc
        prepped.append(clip_out)

    concat_path = os.path.join(data_dir, 'video', f'{base}_broll_concat.txt')
    with open(concat_path, 'w', encoding='utf-8') as fh:
        for clip in prepped:
            fh.write(f"file '{clip}'\n")

    return run_ffmpeg(ffmpeg_bin, [
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_path,
        '-c', 'copy',
        tmp_bg,
    ])


def _make_bg_video(ffmpeg_bin: str, out_path: str, duration: float) -> int:
    colors = ['#0ea5e9', '#ef4444', '#22c55e', '#a855f7', '#f59e0b']
    color = random.choice(colors)
    noise_seed = random.randint(0, 9999)
    vf = (
        f"noise=alls=1080x1920:all_seed={noise_seed}:all_strength=8:"
        "all_flags=u+t,format=yuv420p"
    )
    args = [
        '-f', 'lavfi',
        '-i', f"color=c={color}:s=1080x1920:d={duration:.2f}",
        '-vf', vf,
        '-r', '30',
        out_path,
    ]
    return run_ffmpeg(ffmpeg_bin, args)


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


def _mux_audio(
    ffmpeg_bin: str,
    in_video: str,
    voice_wav: str,
    out_video: str,
    music_path: Optional[str],
    music_vol_db: float,
    target_duration: float,
) -> int:
    if music_path and os.path.exists(music_path):
        filter_complex = (
            "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11:print_format=none[voice];"
            "[2:a]loudnorm=I={mv}:TP=-2.0:LRA=9:print_format=none[music_norm];"
            "[music_norm][voice]sidechaincompress=threshold=-30dB:ratio=8:attack=5:release=400:makeup=0[music_duck];"
            "[voice][music_duck]amix=inputs=2:weights=1 0.35:duration=first:dropout_transition=2[mix];"
            "[mix]volume=1.0,aresample=async=1,apad=pad_dur={dur}[a]"
        )
        filter_complex = filter_complex.format(mv=f"{music_vol_db}dB", dur=f"{target_duration:.2f}")
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
            '-filter_complex', f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=11:print_format=none,apad=pad_dur={target_duration:.2f}[a]",
            '-map', '0:v', '-map', '[a]',
            '-c:v', 'copy', '-c:a', 'aac', '-shortest', out_video
        ])


def _make_silence(ffmpeg_bin: str, out_wav: str, duration: float) -> int:
    return run_ffmpeg(ffmpeg_bin, [
        '-f', 'lavfi', '-i', f"anullsrc=r=48000:cl=stereo", '-t', f"{duration:.2f}", out_wav
    ])


def _escape_filter_text(text: str) -> str:
    return text.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'").replace(',', '\\,')


def _make_flite_voice(ffmpeg_bin: str, text: str, out_wav: str, voice: Optional[str]) -> int:
    safe = _escape_filter_text(text)
    flite = f"flite=text='{safe}'"
    if voice:
        flite += f":voice={voice}"
    return run_ffmpeg(ffmpeg_bin, [
        '-f', 'lavfi',
        '-i', flite,
        '-c:a', 'pcm_s16le',
        '-ar', '44100',
        out_wav,
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
    topic: Optional[str] = None,
    segments: Optional[List[Dict]] = None,
    tts_cmd: Optional[str] = None,
    music_dir: Optional[str] = None,
    music_glob: Optional[str] = None,
    music_vol_db: float = -18.0,
    sd_bg_cmd: Optional[str] = None,
    sd_thumb_cmd: Optional[str] = None,
    footage_dir: Optional[str] = None,
    footage_glob: Optional[str] = None,
    footage_index: Optional[str] = None,
    fallback_tts_voice: Optional[str] = 'slt',
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

    # Background preference: curated b-roll → SD → fractal → animated color
    final_dur = max(7.0, min(15.0, duration_sec))
    segs = segments or [{'text': script_text, 'start': 0.0, 'end': final_dur}]
    sd_img = os.path.join(data_dir, 'video', f'{base}_bg.png')
    used_sd = False
    bg_mode = 'color'
    rc = 1

    broll_library = load_broll_library(footage_dir, footage_glob, footage_index)
    selections = pick_broll_sequence(broll_library, topic, script_text, segs)
    used_broll = False

    if selections:
        rc = _render_broll_sequence(ffmpeg_bin, selections, tmp_bg, data_dir, base)
        if rc == 0:
            used_broll = True
            bg_mode = 'broll'
        else:
            log(f"B-roll render failed (rc={rc}); falling back to synthetic backgrounds.")

    if not used_broll:
        clip_pool = [clip['path'] for clip in (broll_library.get('clips') or [])]
        if clip_pool:
            fallback_clip = random.choice(clip_pool)
            rc = _make_footage_bg(ffmpeg_bin, fallback_clip, tmp_bg, final_dur)
            if rc == 0:
                used_broll = True
                bg_mode = 'footage'
            else:
                log(f"Footage fallback failed for {fallback_clip}; trying synthetic backgrounds.")
        else:
            rc = 1

    if not used_broll and sd_bg_cmd and _sd_make_image(sd_bg_cmd, prompt=script_text, out_path=sd_img):
        used_sd = True
        rc = _ken_burns(ffmpeg_bin, sd_img, tmp_bg, final_dur)
        if rc == 0:
            bg_mode = 'sd'
    if rc != 0 and not used_broll:
        rc = _make_fractal_bg(ffmpeg_bin, tmp_bg, final_dur)
        if rc == 0:
            bg_mode = 'fractal'
    if rc != 0:
        rc = _make_bg_video(ffmpeg_bin, tmp_bg, final_dur)
        if rc == 0:
            bg_mode = 'color'
    if rc != 0:
        return {'ok': False, 'error': 'bg_video_failed'}

    # Text overlay video (segment-aware with safe area)
    rc = _burn_segments(ffmpeg_bin, tmp_bg, segs, tmp_txt)
    if rc != 0:
        # Fallback to simple overlay if segmented captions fail
        rc2 = _burn_simple_text(ffmpeg_bin, tmp_bg, script_text, tmp_txt)
        if rc2 != 0:
            return {'ok': False, 'error': 'text_burn_failed'}

    # TTS or silence
    tts_source = None
    did_tts = synthesize_with_command(tts_cmd, script_text, out_wav, piper_bin=piper_bin, piper_voice=tts_voice)
    if did_tts:
        tts_source = 'custom_cmd'
    else:
        did_tts = synthesize_with_piper(piper_bin, tts_voice, script_text, out_wav)
        if did_tts:
            tts_source = 'piper'
    if not did_tts:
        if _make_flite_voice(ffmpeg_bin, script_text, out_wav, fallback_tts_voice) == 0:
            did_tts = True
            tts_source = 'flite'
        else:
            _make_silence(ffmpeg_bin, out_wav, final_dur)
            tts_source = 'silence'

    # Mux
    music = _find_music(music_dir, music_glob)
    rc = _mux_audio(ffmpeg_bin, tmp_txt, out_wav, out_mp4, music, music_vol_db, final_dur)
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
        'broll': used_broll,
        'bg_source': bg_mode,
        'tts_source': tts_source,
    }
