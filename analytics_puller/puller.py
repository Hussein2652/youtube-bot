import json
import os
from typing import Dict


def _eligible_videos(conn):
    # Uploaded at least 48h ago and no analytics yet
    cur = conn.execute(
        """
        SELECT v.id, v.platform_video_id
        FROM videos v
        WHERE v.status='uploaded' AND v.uploaded_at IS NOT NULL
          AND (julianday('now') - julianday(v.uploaded_at)) * 24.0 >= 48.0
          AND NOT EXISTS (SELECT 1 FROM analytics a WHERE a.video_id = v.id)
        ORDER BY v.uploaded_at ASC
        LIMIT 50
        """
    )
    return [dict(id=int(r[0]), platform_video_id=r[1]) for r in cur.fetchall()]


def _pull_metrics_for(video_id: str) -> Dict:
    # Placeholder: return typical baseline numbers; integrate your local YT client here.
    return {'impressions': 10000, 'ctr': 0.08, 'avg_view': 0.82, 'like_rate': 0.04}


def _update_bias(conn, bias_path: str) -> Dict:
    # Use last 200 analytics rows to adjust emotion and unigram weights
    cur = conn.execute(
        """
        SELECT a.ctr, a.avg_view, a.like_rate, s.text, s.metadata_json
        FROM analytics a
        JOIN videos v ON v.id = a.video_id
        JOIN scripts s ON s.id = v.script_id
        ORDER BY a.pulled_at DESC
        LIMIT 200
        """
    )
    em_counts = {}
    gram_scores = {}
    rows = cur.fetchall()
    for r in rows:
        ctr, av, lr = float(r[0]), float(r[1]), float(r[2])
        score = ctr * av * (1.0 + lr)
        meta = json.loads(r[4] or '{}')
        emotion = (meta.get('emotion') or '').lower()
        if emotion:
            em_counts[emotion] = em_counts.get(emotion, 0.0) + score
        for g in (r[3] or '').lower().split():
            gram_scores[g] = gram_scores.get(g, 0.0) + score
    # Normalize to weights around 1.0
    def normalize(d):
        if not d:
            return {}
        mx = max(d.values()) or 1.0
        out = {k: round(0.5 + 1.5 * (v / mx), 3) for k, v in d.items()}  # 0.5..2.0
        return out

    bias = {'emotion_weights': normalize(em_counts), 'ngram_weights': normalize(gram_scores)}
    os.makedirs(os.path.dirname(bias_path), exist_ok=True)
    with open(bias_path, 'w', encoding='utf-8') as f:
        json.dump(bias, f, ensure_ascii=False, indent=2)
    return {'ok': True, 'updated': len(bias['emotion_weights']) + len(bias['ngram_weights'])}


def pull_and_record(conn) -> Dict:
    vids = _eligible_videos(conn)
    count = 0
    for v in vids:
        m = _pull_metrics_for(v['platform_video_id'] or '')
        conn.execute(
            "INSERT INTO analytics(video_id, ctr, avg_view, like_rate) VALUES(?,?,?,?)",
            (int(v['id']), float(m['ctr']), float(m['avg_view']), float(m['like_rate'])),
        )
        conn.commit()
        count += 1
    bias_res = _update_bias(conn, os.path.join('assets', 'bias.json'))
    return {'ok': True, 'recorded': count, 'bias': bias_res}
