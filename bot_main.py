import os
from datetime import datetime
from typing import List

from config import load_config
from utils import log, read_json
from db import get_conn, init_db, get_queue_size, upsert_topic, insert_hook, insert_script, insert_video
from hook_miner import discover_topics, mine_hooks
from relevance_filter import rank_hooks_for_topic
from hooks_bank import should_wake_llm, mutate_hooks
from scripts import finalize_micro_script
from shorts_generator import generate_short
from schedule_manager import propose_schedule, schedule_video
from uploader_service import attempt_uploads
from analytics_puller import pull_and_record
from learner import update_topic_weights


def main() -> None:
    cfg = load_config()
    log("Loaded config and ensured directories.")
    conn = get_conn(cfg.db_path)
    init_db(conn)
    log("DB initialized.")

    # 1) Discover topics (seed-based offline)
    topics = discover_topics(cfg.data_dir, max_topics=5)['topics']
    topic_ids = {t: upsert_topic(conn, t) for t in topics}
    log(f"Discovered topics: {len(topics)}")

    # 2) Mine hooks (synthetic offline generator)
    mh = mine_hooks(cfg.data_dir, topics, per_topic=25)
    hooks = read_json(mh['hooks_dataset_path'], default=[])
    log(f"Hooks mined: {len(hooks)}")

    # 3) Select current topic (highest weight or first)
    current_topic = topics[0]

    # 4) Filter top-K hooks for topic
    rh = rank_hooks_for_topic(current_topic, hooks, top_k=30, data_dir=cfg.data_dir, embeddings_backend=cfg.embeddings_backend, embeddings_model_path=cfg.embeddings_model_path)
    top_hooks = rh['top_hooks']
    for h in top_hooks:
        insert_hook(conn, topic_ids[current_topic], h['raw_text'], h.get('source_url'), h.get('score'))

    # 5) Decide whether to wake LLM (gated by queue size)
    qsize = get_queue_size(conn)
    allow_llm = should_wake_llm(qsize, cfg.min_queue)
    mut = mutate_hooks(current_topic, top_hooks, cfg.llm_cmd, allow_llm, limit=10, data_dir=cfg.data_dir)
    log(f"Mutated hooks: {mut['count']} (llm_called={mut['llm_called']})")

    # 6) Finalize micro-script
    fin = finalize_micro_script(current_topic, mut['mutated'])
    log(f"Script: {fin['words']} words, ~{fin['duration_sec']:.1f}s")
    # Store emotion from first mutated hook if present
    meta = {**fin}
    if mut['mutated']:
        meta['emotion'] = mut['mutated'][0].get('emotion')
    script_id = insert_script(conn, topic_ids[current_topic], fin['script_text'], fin['words'], fin['duration_sec'], meta)

    # 7) Generate short (voice + visuals + captions)
    gen = generate_short(
        cfg.ffmpeg_bin,
        cfg.piper_bin or '',
        cfg.tts_voice or '',
        cfg.data_dir,
        fin['script_text'],
        fin['duration_sec'],
        segments=fin.get('segments'),
        music_dir=cfg.music_dir,
        sd_bg_cmd=cfg.sd_bg_cmd,
        sd_thumb_cmd=cfg.sd_thumb_cmd,
    )
    if not gen.get('ok'):
        log(f"Generation failed: {gen}")
        return
    video_id = insert_video(conn, script_id, gen['video_path'], gen['thumb_path'], gen['duration_sec'], status='ready')
    log(f"Generated video: {gen['video_path']}")

    # 8) Schedule
    day_target = max(cfg.daily_target_min, min(cfg.daily_target_max, cfg.daily_target_min))
    slots = propose_schedule(day_target)
    sched = schedule_video(conn, video_id, slots[0])
    log(f"Scheduled video {video_id} at {slots[0]}")

    # 9) Attempt uploads for due items (if uploader configured)
    up = attempt_uploads(conn, cfg.uploader_cmd)
    log(f"Uploader attempted: {up}")

    # 10) Pull analytics every ~48h and learn
    # Here we call stubbed analytics and learning unconditionally for demo purposes
    an = pull_and_record(conn)
    lr = update_topic_weights(conn)
    log(f"Analytics recorded: {an['recorded']}, Learner updates: {lr['updated']}")


if __name__ == '__main__':
    main()
