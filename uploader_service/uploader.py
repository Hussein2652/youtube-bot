import shlex
import subprocess
from typing import Dict, List, Optional


def _call_uploader(cmd: str, video_path: str, thumb_path: str, title: str, description: str) -> bool:
    try:
        full = f"{cmd} --title {shlex.quote(title)} --description {shlex.quote(description)} --file {shlex.quote(video_path)} --thumbnail {shlex.quote(thumb_path)}"
        proc = subprocess.run(full, shell=True, check=False)
        return proc.returncode == 0
    except Exception:
        return False


def attempt_uploads(conn, uploader_cmd: Optional[str]) -> Dict:
    # Upload only items past schedule time
    cur = conn.execute(
        """
        SELECT q.id AS queue_id, v.id AS video_id, v.video_path, v.thumb_path, q.scheduled_for
        FROM queue q JOIN videos v ON v.id = q.video_id
        WHERE q.status IN ('pending','ready','scheduled') AND datetime(q.scheduled_for) <= datetime('now')
        ORDER BY q.scheduled_for ASC
        """
    )
    items = [dict(r) for r in cur.fetchall()]
    uploaded = []
    for it in items:
        ok = False
        if uploader_cmd:
            ok = _call_uploader(uploader_cmd, it['video_path'], it['thumb_path'], title='New Short', description='')
        if ok:
            conn.execute("UPDATE queue SET status='uploaded' WHERE id=?", (it['queue_id'],))
            conn.execute("UPDATE videos SET status='uploaded' WHERE id=?", (it['video_id'],))
            conn.commit()
            uploaded.append(it['queue_id'])
        else:
            # Leave as pending for external process
            conn.execute("UPDATE queue SET status='ready' WHERE id=?", (it['queue_id'],))
            conn.commit()
    return {'ok': True, 'attempted': len(items), 'uploaded': len(uploaded), 'queue_ids': uploaded}

