from typing import Dict


def update_topic_weights(conn) -> Dict:
    # Very simple learner: boost topics whose latest videos had high avg_view
    cur = conn.execute(
        """
        SELECT t.id AS topic_id, t.name, AVG(a.avg_view) AS avgv
        FROM topics t
        JOIN scripts s ON s.topic_id = t.id
        JOIN videos v ON v.script_id = s.id
        JOIN analytics a ON a.video_id = v.id
        GROUP BY t.id, t.name
        """
    )
    changes = 0
    for r in cur.fetchall():
        avgv = float(r[2]) if r[2] is not None else 0.5
        new_w = max(0.1, min(3.0, avgv * 2.0))
        conn.execute("UPDATE topics SET weight=? WHERE id=?", (new_w, int(r[0])))
        changes += 1
    conn.commit()
    return {'ok': True, 'updated': changes}

