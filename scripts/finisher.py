from typing import Dict, List
from utils import word_count, truncate_words, estimate_duration_sec


def finalize_micro_script(topic: str, mutated_hooks: List[Dict], max_words: int = 50) -> Dict:
    # Choose strongest (first), keep <= 50 words, target 7–15s
    base = mutated_hooks[0]['mutated_text'] if mutated_hooks else f"Watch this: {topic} in 10 seconds"
    # Add a concrete, action-oriented close
    closing = " Follow for part 2." if word_count(base) < 40 else ""
    text = truncate_words(base + closing, max_words)
    dur = estimate_duration_sec(text, wpm=160)
    return {
        'ok': True,
        'script_text': text,
        'words': word_count(text),
        'duration_sec': dur,
        'notes': {'target_sec': '7-15', 'wpm': 160},
    }

