from typing import List


def word_count(text: str) -> int:
    return len([w for w in text.strip().split() if w])


def truncate_words(text: str, max_words: int) -> str:
    words = [w for w in text.strip().split() if w]
    if len(words) <= max_words:
        return text.strip()
    return ' '.join(words[:max_words])


def estimate_duration_sec(text: str, wpm: int = 160) -> float:
    # 160 wpm ≈ conversational TTS speed
    wc = max(1, word_count(text))
    return (wc / wpm) * 60.0

