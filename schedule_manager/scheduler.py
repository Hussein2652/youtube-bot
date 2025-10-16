from datetime import datetime, timedelta
from typing import Dict, List
from zoneinfo import ZoneInfo


def _now_cairo() -> datetime:
    try:
        return datetime.now(ZoneInfo('Africa/Cairo'))
    except Exception:
        return datetime.utcnow()


def propose_schedule(count: int) -> List[str]:
    # Cadence: 18/day — 11:00×5, 15:00×8, 19:30×5 in Africa/Cairo
    # Small offsets (1-3 min) to avoid clumping exactly on the minute.
    now = _now_cairo()
    base_plan = [
        (11, 0, 5, 1),   # hour, minute, posts, spacing minutes
        (15, 0, 8, 1),
        (19, 30, 5, 1),
    ]
    out: List[datetime] = []
    day = now.date()
    # Build slots for today and tomorrow until we hit count
    while len(out) < count:
        for h, m, n, step in base_plan:
            start = datetime(day.year, day.month, day.day, h, m, tzinfo=now.tzinfo)
            for i in range(n):
                ts = start + timedelta(minutes=i * step)
                if ts > now:
                    out.append(ts)
                    if len(out) >= count:
                        break
            if len(out) >= count:
                break
        day = day + timedelta(days=1)
    return [ts.strftime('%Y-%m-%d %H:%M:%S') for ts in out]


def schedule_video(conn, video_id: int, when_iso: str) -> Dict:
    cur = conn.execute(
        "INSERT INTO queue(video_id, scheduled_for, status) VALUES(?,?,?)",
        (video_id, when_iso, 'pending'),
    )
    conn.commit()
    return {'ok': True, 'queue_id': int(cur.lastrowid), 'video_id': video_id, 'scheduled_for': when_iso}
