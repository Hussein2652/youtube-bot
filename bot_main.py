from typing import List

from config import load_config
from utils import log, read_json
from db import (
    get_conn,
    init_db,
    get_queue_size,
    upsert_topic,
    insert_hook,
    insert_script,
    insert_video,
    video_has_queue_entry,
)
from hook_miner import discover_topics, mine_hooks
from relevance_filter import rank_hooks_for_topic
from hooks_bank import should_wake_llm, mutate_hooks
from scripts import finalize_micro_script
from shorts_generator import generate_short
from schedule_manager import propose_schedule, schedule_video
from uploader_service import attempt_uploads
from analytics_puller import pull_and_record
from learner import update_topic_weights


def _select_topic(conn, fallback: List[str]) -> str:
    cur = conn.execute("SELECT name FROM topics ORDER BY weight DESC, created_at DESC LIMIT 1")
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    return fallback[0]


def main() -> None:
    cfg = load_config()
    log("Loaded config and ensured directories.")
    conn = get_conn(cfg.db_path)
    init_db(conn)
    log("DB initialized.")

    topics = discover_topics(cfg.data_dir, max_topics=5)['topics']
    topic_ids = {t: upsert_topic(conn, t) for t in topics}
    log(f"Discovered topics: {len(topics)}")

    target_inventory = max(cfg.daily_target_min, cfg.daily_target_max)
    attempts = 0
    max_attempts = target_inventory * 3
    refresh_budget = 3
    hooks: List[dict] = []

    while get_queue_size(conn) < target_inventory and attempts < max_attempts:
        attempts += 1

        if not hooks or refresh_budget >= 0:
            mined = mine_hooks(
                cfg.data_dir,
                topics,
                per_topic=25,
                source_glob=cfg.miner_source_glob,
                cache_ttl=cfg.miner_cache_ttl,
                rate_limit=cfg.miner_rate_limit,
            )
            hooks = read_json(mined['hooks_dataset_path'], default=[]) or []
            refresh_budget -= 1
            log(f"Hooks mined: {len(hooks)}")

        current_topic = _select_topic(conn, topics)
        topic_hooks = [h for h in hooks if h.get('topic') == current_topic]
        if not topic_hooks:
            log(f"No hooks for {current_topic}; refreshing dataset.")
            hooks = []
            continue

        ranked = rank_hooks_for_topic(
            current_topic,
            topic_hooks,
            top_k=cfg.topk_hooks,
            data_dir=cfg.data_dir,
            embeddings_backend=cfg.embeddings_backend,
            embeddings_model_path=cfg.embeddings_model_path,
            embeddings_tokenizer_path=cfg.embeddings_tokenizer_path,
            emb_model_dir=cfg.emb_model_dir,
            sim_threshold=cfg.sim_threshold,
        )
        top_hooks = ranked['top_hooks']
        if not top_hooks:
            hooks = []
            continue

        for h in top_hooks:
            insert_hook(conn, topic_ids[current_topic], h['raw_text'], h.get('source_url'), h.get('score'))

        qsize = get_queue_size(conn)
        allow_llm = should_wake_llm(qsize, cfg.min_queue)
        mut = mutate_hooks(current_topic, top_hooks, cfg.llm_cmd, allow_llm, limit=10, data_dir=cfg.data_dir)
        log(f"Mutated hooks: {mut['count']} (llm_called={mut['llm_called']})")
        if not mut['mutated']:
            log("No unique mutations; refreshing hooks set.")
            used_texts = {h['raw_text'] for h in top_hooks}
            hooks = [h for h in hooks if h.get('raw_text') not in used_texts]
            continue

        fin = finalize_micro_script(current_topic, mut['mutated'])
        log(f"Script: {fin['words']} words, ~{fin['duration_sec']:.1f}s")
        meta = {**fin}
        if mut['mutated']:
            meta['emotion'] = mut['mutated'][0].get('emotion')
        script_id = insert_script(conn, topic_ids[current_topic], fin['script_text'], fin['words'], fin['duration_sec'], meta)

        gen = generate_short(
            cfg.ffmpeg_bin,
            cfg.piper_bin or '',
            cfg.piper_voice or '',
            cfg.data_dir,
            fin['script_text'],
            fin['duration_sec'],
            segments=fin.get('segments'),
            tts_cmd=cfg.tts_cmd,
            music_dir=cfg.music_dir,
            music_glob=cfg.bg_music_glob,
            music_vol_db=cfg.bg_music_vol_db,
            sd_bg_cmd=cfg.sd_bg_cmd,
            sd_thumb_cmd=cfg.sd_thumb_cmd,
        )
        if not gen.get('ok'):
            log(f"Generation failed: {gen}")
            continue

        video_id = insert_video(conn, script_id, gen['video_path'], gen['thumb_path'], gen['duration_sec'], status='ready')
        if video_has_queue_entry(conn, video_id):
            log(f"Video {video_id} already queued; skipping schedule.")
            continue
        log(f"Generated video: {gen['video_path']}")

        slots = propose_schedule(target_inventory)
        slot_index = get_queue_size(conn) % max(1, len(slots))
        slot_time = slots[slot_index]
        schedule_video(conn, video_id, slot_time)
        log(f"Scheduled video {video_id} at {slot_time}")

        used_texts = {h['raw_text'] for h in top_hooks}
        hooks = [h for h in hooks if h.get('raw_text') not in used_texts]

    up = attempt_uploads(conn, cfg.uploader_cmd, privacy_status=cfg.privacy_status, category_id=cfg.category_id)
    log(f"Uploader attempted: {up}")

    analytics = pull_and_record(conn, cfg.analytics_cmd)
    learner = update_topic_weights(conn)
    log(f"Analytics recorded: {analytics['recorded']}, Learner updates: {learner['updated']}")


if __name__ == '__main__':
    main()
