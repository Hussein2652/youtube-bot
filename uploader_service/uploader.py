import json
import os
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional


def _parse_video_id(output: str) -> Optional[str]:
    # Try JSON first
    try:
        obj = json.loads(output)
        if isinstance(obj, dict) and 'videoId' in obj:
            return str(obj['videoId'])
    except Exception:
        pass
    # Fallback: scan text
    for token in output.split():
        if token.startswith('videoId'):
            parts = token.split('=')
            if len(parts) == 2:
                return parts[1]
    return None


def _derive_title(script_text: Optional[str]) -> str:
    if not script_text:
        return 'New Short'
    first_line = script_text.strip().splitlines()[0]
    return first_line[:95]


def _derive_description(script_text: Optional[str]) -> str:
    if not script_text:
        return ''
    return script_text[:500]


def _call_uploader(cmd: str, *, video_path: str, thumb_path: str, title: str, description: str, tags: str, privacy: str, category: str) -> (bool, Optional[str]):
    try:
        template = os.path.expandvars(cmd)
        full = template.format(
            mp4=video_path,
            file=video_path,
            video=video_path,
            thumbnail=thumb_path,
            thumb=thumb_path,
            png=thumb_path,
            title=title,
            description=description,
            desc=description,
            tags=tags,
            csv_tags=tags,
            privacy=privacy,
            privacy_status=privacy,
            category=category,
            category_id=category,
        )
        proc = subprocess.run(full, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = proc.stdout.decode('utf-8', errors='ignore') if proc.stdout else ''
        vid = _parse_video_id(out)
        return (proc.returncode == 0, vid)
    except Exception:
        return (False, None)


def attempt_uploads(conn, uploader_cmd: Optional[str], *, privacy_status: str = 'public', category_id: str = '24') -> Dict:
    # Upload only items past schedule time
    cur = conn.execute(
        """
        SELECT q.id AS queue_id, q.attempt_count, q.backoff_until, v.id AS video_id, v.video_path, v.thumb_path, q.scheduled_for, s.text AS script_text
        FROM queue q
        JOIN videos v ON v.id = q.video_id
        JOIN scripts s ON s.id = v.script_id
        WHERE q.status IN ('pending','ready','scheduled')
          AND datetime(q.scheduled_for) <= datetime('now')
          AND (q.backoff_until IS NULL OR datetime(q.backoff_until) <= datetime('now'))
        ORDER BY q.scheduled_for ASC
        """
    )
    items = [dict(r) for r in cur.fetchall()]
    uploaded = []
    for it in items:
        ok = False
        video_id_str: Optional[str] = None
        if uploader_cmd:
            title = _derive_title(it.get('script_text'))
            description = _derive_description(it.get('script_text'))
            tags = ','.join((it.get('script_text') or '').split()[:5])
            ok, video_id_str = _call_uploader(
                uploader_cmd,
                video_path=it['video_path'],
                thumb_path=it['thumb_path'],
                title=title,
                description=description,
                tags=tags,
                privacy=privacy_status,
                category=category_id,
            )
        if ok:
            conn.execute("UPDATE queue SET status='uploaded' WHERE id=?", (it['queue_id'],))
            conn.execute("UPDATE videos SET status='uploaded', platform_video_id=?, uploaded_at=datetime('now') WHERE id=?", (video_id_str, it['video_id']))
            conn.commit()
            uploaded.append(it['queue_id'])
        else:
            # Exponential backoff
            attempts = int(it['attempt_count'] or 0) + 1
            delay_min = min(60, 2 ** min(6, attempts))  # cap at 64 -> 60
            conn.execute(
                "UPDATE queue SET status='ready', attempt_count=?, backoff_until=datetime('now', ?) WHERE id=?",
                (attempts, f"+{delay_min} minutes", it['queue_id'])
            )
            conn.commit()
    return {'ok': True, 'attempted': len(items), 'uploaded': len(uploaded), 'queue_ids': uploaded}
