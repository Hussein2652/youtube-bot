import json
import shlex
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


def _call_uploader(cmd: str, video_path: str, thumb_path: str, title: str, description: str) -> (bool, Optional[str]):
    try:
        full = f"{cmd} --title {shlex.quote(title)} --description {shlex.quote(description)} --file {shlex.quote(video_path)} --thumbnail {shlex.quote(thumb_path)}"
        proc = subprocess.run(full, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = proc.stdout.decode('utf-8', errors='ignore') if proc.stdout else ''
        vid = _parse_video_id(out)
        return (proc.returncode == 0, vid)
    except Exception:
        return (False, None)


def attempt_uploads(conn, uploader_cmd: Optional[str]) -> Dict:
    # Upload only items past schedule time
    cur = conn.execute(
        """
        SELECT q.id AS queue_id, q.attempt_count, q.backoff_until, v.id AS video_id, v.video_path, v.thumb_path, q.scheduled_for
        FROM queue q JOIN videos v ON v.id = q.video_id
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
            ok, video_id_str = _call_uploader(uploader_cmd, it['video_path'], it['thumb_path'], title='New Short', description='')
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
