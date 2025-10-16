import json
from typing import Any, Dict, List, Optional
import sqlite3


def upsert_topic(conn: sqlite3.Connection, name: str, weight: float = 1.0) -> int:
    cur = conn.execute(
        "INSERT INTO topics(name, weight) VALUES(?, ?) ON CONFLICT(name) DO UPDATE SET weight=excluded.weight RETURNING id",
        (name, weight),
    )
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def insert_hook(conn: sqlite3.Connection, topic_id: int, raw_text: str, source_url: Optional[str], score: Optional[float]) -> int:
    cur = conn.execute(
        "INSERT INTO hooks(topic_id, raw_text, source_url, score) VALUES(?,?,?,?)",
        (topic_id, raw_text, source_url, score),
    )
    conn.commit()
    return cur.lastrowid


def insert_script(conn: sqlite3.Connection, topic_id: int, text: str, words: int, duration_sec: float, metadata: Dict[str, Any]) -> int:
    cur = conn.execute(
        "INSERT INTO scripts(topic_id, text, words, duration_sec, metadata_json) VALUES(?,?,?,?,?)",
        (topic_id, text, words, duration_sec, json.dumps(metadata)),
    )
    conn.commit()
    return cur.lastrowid


def insert_video(conn: sqlite3.Connection, script_id: int, video_path: str, thumb_path: str, duration_sec: float, status: str = 'ready') -> int:
    cur = conn.execute(
        "INSERT INTO videos(script_id, video_path, thumb_path, duration_sec, status) VALUES(?,?,?,?,?)",
        (script_id, video_path, thumb_path, duration_sec, status),
    )
    conn.commit()
    return cur.lastrowid


def enqueue_video(conn: sqlite3.Connection, video_id: int, scheduled_for: str, platform: str = 'youtube', status: str = 'pending') -> int:
    cur = conn.execute(
        "INSERT INTO queue(video_id, scheduled_for, status, platform) VALUES(?,?,?,?)",
        (video_id, scheduled_for, status, platform),
    )
    conn.commit()
    return cur.lastrowid


def mark_video_status(conn: sqlite3.Connection, video_id: int, status: str) -> None:
    conn.execute("UPDATE videos SET status=? WHERE id=?", (status, video_id))
    conn.commit()


def list_pending_uploads(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    cur = conn.execute(
        """
        SELECT q.id AS queue_id, v.id AS video_id, v.video_path, v.thumb_path, q.scheduled_for, q.status
        FROM queue q JOIN videos v ON v.id = q.video_id
        WHERE q.status IN ('pending','ready','scheduled') AND datetime(q.scheduled_for) <= datetime('now')
        ORDER BY q.scheduled_for ASC
        """
    )
    return [dict(r) for r in cur.fetchall()]


def record_analytics(conn: sqlite3.Connection, video_id: int, ctr: float, avg_view: float, like_rate: float) -> int:
    cur = conn.execute(
        "INSERT INTO analytics(video_id, ctr, avg_view, like_rate) VALUES(?,?,?,?)",
        (video_id, ctr, avg_view, like_rate),
    )
    conn.commit()
    return cur.lastrowid


def recent_analytics_age_hours(conn: sqlite3.Connection) -> Optional[float]:
    cur = conn.execute(
        "SELECT (julianday('now') - julianday(MAX(pulled_at))) * 24.0 AS hours FROM analytics"
    )
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None

