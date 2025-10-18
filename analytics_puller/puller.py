import json
import os
import shlex
import subprocess
from datetime import datetime, timedelta
from typing import Dict, Optional


def _eligible_videos(conn):
    cur = conn.execute(
        """
        SELECT v.id, v.platform_video_id, v.uploaded_at
        FROM videos v
        WHERE v.status='uploaded' AND v.uploaded_at IS NOT NULL
          AND (julianday('now') - julianday(v.uploaded_at)) * 24.0 >= 48.0
          AND NOT EXISTS (SELECT 1 FROM analytics a WHERE a.video_id = v.id)
        ORDER BY v.uploaded_at ASC
        LIMIT 50
        """
    )
    return [dict(id=int(r[0]), platform_video_id=r[1], uploaded_at=r[2]) for r in cur.fetchall()]


def _call_analytics(cmd: str, video_id: str, start_date: str, end_date: str) -> Optional[Dict]:
    full_cmd = f"{cmd} --video-id {video_id} --start-date {start_date} --end-date {end_date}"
    proc = subprocess.run(full_cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return None
    try:
        payload = proc.stdout.decode('utf-8').strip()
        return json.loads(payload)
    except Exception:
        return None


def _calculate_like_rate(likes: float, impressions: float) -> float:
    if impressions <= 0:
        return 0.0
    return likes / impressions


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


def _run_bulk_analytics(cmd: str) -> Dict[str, Dict]:
    out_path = None
    try:
        parts = shlex.split(cmd)
    except ValueError:
        parts = cmd.split()
    for idx, token in enumerate(parts):
        if token == '--out' and idx + 1 < len(parts):
            out_path = parts[idx + 1]
            break
    proc = subprocess.run(cmd, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    payload = proc.stdout.decode('utf-8', errors='ignore').strip()
    data: Dict[str, Dict] = {}
    if proc.returncode == 0:
        if payload:
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, list):
                    for row in parsed:
                        vid = row.get('videoId')
                        if vid:
                            data[str(vid)] = row
            except json.JSONDecodeError:
                pass
        if not data and out_path and os.path.exists(out_path):
            try:
                with open(out_path, 'r', encoding='utf-8') as f:
                    parsed = json.load(f)
                for row in parsed:
                    vid = row.get('videoId')
                    if vid:
                        data[str(vid)] = row
            except Exception:
                pass
    return data


def pull_and_record(conn, analytics_cmd: Optional[str] = None) -> Dict:
    vids = _eligible_videos(conn)
    count = 0
    bulk_results: Dict[str, Dict] = {}
    per_video = False
    if analytics_cmd:
        if '{video_id}' in analytics_cmd:
            per_video = True
        else:
            bulk_results = _run_bulk_analytics(analytics_cmd)
    for v in vids:
        if not v['platform_video_id']:
            continue
        metrics = {'impressions': 1000, 'ctr': 0.08, 'avg_view': 0.8, 'like_rate': 0.04}
        if analytics_cmd:
            if per_video:
                uploaded_at = datetime.fromisoformat(v['uploaded_at'])
                start_date = uploaded_at.date().isoformat()
                end_date = (uploaded_at + timedelta(days=3)).date().isoformat()
                res = _call_analytics(analytics_cmd, v['platform_video_id'], start_date, end_date) or {}
            else:
                res = bulk_results.get(v['platform_video_id'], {})
            impressions = float(res.get('impressions', metrics['impressions']))
            ctr = float(res.get('ctr', metrics['ctr']))
            avg_view_pct = float(res.get('avg_view_pct', res.get('avg_view_percent', metrics['avg_view'] * 100.0)))
            if avg_view_pct > 1.5:  # likely percent
                avg_view_pct = avg_view_pct / 100.0
            likes = float(res.get('likes', metrics['like_rate'] * impressions))
            like_rate = _calculate_like_rate(likes, impressions)
            metrics = {
                'impressions': impressions,
                'ctr': ctr,
                'avg_view': avg_view_pct,
                'like_rate': like_rate,
            }
        conn.execute(
            "INSERT INTO analytics(video_id, ctr, avg_view, like_rate) VALUES(?,?,?,?)",
            (int(v['id']), float(metrics['ctr']), float(metrics['avg_view']), float(metrics['like_rate'])),
        )
        conn.commit()
        count += 1
    bias_res = _update_bias(conn, os.path.join('assets', 'bias.json'))
    return {'ok': True, 'recorded': count, 'bias': bias_res}
