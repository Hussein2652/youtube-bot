from typing import Dict


def pull_and_record(conn) -> Dict:
    # Placeholder: in absence of YouTube API, mark a dummy analytics row
    cur = conn.execute("SELECT id FROM videos WHERE status='uploaded' ORDER BY created_at DESC LIMIT 20")
    vids = [int(r[0]) for r in cur.fetchall()]
    count = 0
    for vid in vids:
        conn.execute(
            "INSERT INTO analytics(video_id, ctr, avg_view, like_rate) VALUES(?,?,?,?)",
            (vid, 0.08, 0.8, 0.04),
        )
        conn.commit()
        count += 1
    return {'ok': True, 'recorded': count}

