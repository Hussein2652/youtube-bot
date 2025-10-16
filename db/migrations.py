import sqlite3


def _has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())


def run_migrations(conn: sqlite3.Connection) -> None:
    # scripts.script_hash
    if not _has_column(conn, 'scripts', 'script_hash'):
        conn.execute("ALTER TABLE scripts ADD COLUMN script_hash TEXT")
    # videos extra columns
    for col_sql in [
        (not _has_column(conn, 'videos', 'title'), "ALTER TABLE videos ADD COLUMN title TEXT"),
        (not _has_column(conn, 'videos', 'description'), "ALTER TABLE videos ADD COLUMN description TEXT"),
        (not _has_column(conn, 'videos', 'video_hash'), "ALTER TABLE videos ADD COLUMN video_hash TEXT"),
        (not _has_column(conn, 'videos', 'platform_video_id'), "ALTER TABLE videos ADD COLUMN platform_video_id TEXT"),
        (not _has_column(conn, 'videos', 'uploaded_at'), "ALTER TABLE videos ADD COLUMN uploaded_at TIMESTAMP"),
    ]:
        if col_sql[0]:
            conn.execute(col_sql[1])
    # queue.backoff
    if not _has_column(conn, 'queue', 'attempt_count'):
        conn.execute("ALTER TABLE queue ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0")
    if not _has_column(conn, 'queue', 'backoff_until'):
        conn.execute("ALTER TABLE queue ADD COLUMN backoff_until TIMESTAMP")

    # Indexes and uniqueness
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_scripts_hash ON scripts(script_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_videos_script ON videos(script_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_queue_status_time ON queue(status, scheduled_for)")
    conn.commit()

