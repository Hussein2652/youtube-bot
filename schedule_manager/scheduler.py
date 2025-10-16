from datetime import datetime, timedelta, timezone
from typing import Dict, List


def _now_utc() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def propose_schedule(count: int) -> List[str]:
    # Spread evenly over next ~24h
    now = _now_utc()
    slots = []
    step = max(1, int(24 * 60 / max(1, count)))
    for i in range(count):
        ts = now + timedelta(minutes=i * step)
        slots.append(ts.strftime('%Y-%m-%d %H:%M:%S'))
    return slots


def schedule_video(conn, video_id: int, when_iso: str) -> Dict:
    cur = conn.execute(
        "INSERT INTO queue(video_id, scheduled_for, status) VALUES(?,?,?)",
        (video_id, when_iso, 'pending'),
    )
    conn.commit()
    return {'ok': True, 'queue_id': int(cur.lastrowid), 'video_id': video_id, 'scheduled_for': when_iso}

