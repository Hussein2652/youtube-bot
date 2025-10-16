import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    data_dir: str
    assets_dir: str
    db_path: str
    min_queue: int
    daily_target_min: int
    daily_target_max: int
    schedule_tz: str

    ffmpeg_bin: str
    piper_bin: Optional[str]
    tts_voice: Optional[str]

    sd_cmd: Optional[str]
    sd_bg_cmd: Optional[str]
    sd_thumb_cmd: Optional[str]
    llm_cmd: Optional[str]

    uploader_cmd: Optional[str]
    yt_api_key: Optional[str]
    yt_channel_id: Optional[str]

    embeddings_backend: str
    embeddings_model_path: Optional[str]
    embeddings_tokenizer_path: Optional[str]
    music_dir: Optional[str]
    miner_cache_ttl: int
    miner_rate_limit: int
    miner_source_glob: str
    analytics_cmd: Optional[str]

    def ensure_dirs(self) -> None:
        for d in [
            self.data_dir,
            os.path.join(self.data_dir, 'audio'),
            os.path.join(self.data_dir, 'video'),
            os.path.join(self.data_dir, 'thumbs'),
            os.path.join(self.data_dir, 'logs'),
            os.path.join(self.data_dir, 'seeds'),
        ]:
            os.makedirs(d, exist_ok=True)


def getenv_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except Exception:
        return default


def load_config() -> Config:
    data_dir = os.getenv('DATA_DIR', 'data').strip()
    assets_dir = os.getenv('ASSETS_DIR', 'assets').strip()

    cfg = Config(
        data_dir=data_dir,
        assets_dir=assets_dir,
        db_path=os.path.join(data_dir, 'bot.db'),
        min_queue=getenv_int('MIN_QUEUE', 6),
        daily_target_min=getenv_int('DAILY_TARGET_MIN', 10),
        daily_target_max=getenv_int('DAILY_TARGET_MAX', 20),
        schedule_tz=os.getenv('SCHEDULE_TIMEZONE', 'UTC'),
        ffmpeg_bin=os.getenv('FFMPEG_BIN', 'ffmpeg').strip(),
        piper_bin=(os.getenv('PIPER_BIN') or '').strip() or None,
        tts_voice=(os.getenv('TTS_VOICE') or '').strip() or None,
        sd_cmd=(os.getenv('SD_CMD') or '').strip() or None,  # legacy
        sd_bg_cmd=(os.getenv('SD_BG_CMD') or os.getenv('SD_CMD') or '').strip() or None,
        sd_thumb_cmd=(os.getenv('SD_THUMB_CMD') or '').strip() or None,
        llm_cmd=(os.getenv('LLM_CMD') or '').strip() or None,
        uploader_cmd=(os.getenv('YOUTUBE_UPLOADER_CMD') or '').strip() or None,
        yt_api_key=(os.getenv('YOUTUBE_API_KEY') or '').strip() or None,
        yt_channel_id=(os.getenv('YOUTUBE_CHANNEL_ID') or '').strip() or None,
        embeddings_backend=(os.getenv('EMBEDDINGS_BACKEND') or 'hash').strip(),
        embeddings_model_path=(os.getenv('EMBEDDINGS_MODEL_PATH') or '').strip() or None,
        embeddings_tokenizer_path=(os.getenv('EMBEDDINGS_TOKENIZER_PATH') or '').strip() or None,
        music_dir=(os.getenv('MUSIC_DIR') or '').strip() or None,
        miner_cache_ttl=getenv_int('MINER_CACHE_TTL_SEC', 6 * 3600),
        miner_rate_limit=getenv_int('MINER_RATE_PER_KEY_SEC', 5),
        miner_source_glob=(os.getenv('MINER_SOURCE_GLOB') or 'assets/sources/*').strip(),
        analytics_cmd=(os.getenv('ANALYTICS_CMD') or '').strip() or None,
    )
    cfg.ensure_dirs()
    return cfg
