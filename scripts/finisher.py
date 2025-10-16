from typing import Dict, List
from utils import word_count, truncate_words, estimate_duration_sec


def finalize_micro_script(topic: str, mutated_hooks: List[Dict], max_words: int = 50) -> Dict:
    # Structured micro-script: HOOK (0–2s) → curiosity (2–5s) → payoff (5–10s) → micro-CTA (~1s)
    hook = mutated_hooks[0]['mutated_text'] if mutated_hooks else f"Watch: {topic} in 10s"
    curiosity = "You won't expect the reason."
    payoff = f"Here's the quick fix for {topic.split()[0]}: do this today."
    cta = "Follow for part 2."

    # Compose and enforce ≤ 50 words
    parts = [hook, curiosity, payoff, cta]
    text = truncate_words(' '.join(parts), max_words)

    # Approx durations by segment word share at 160 wpm, clipped to 7–15s total
    wc_total = max(1, word_count(text))
    base_dur = estimate_duration_sec(text, wpm=160)
    total = max(7.0, min(15.0, base_dur))
    # distribute per original part proportions
    seg_words = [word_count(hook), word_count(curiosity), word_count(payoff), word_count(cta)]
    seg_sum = sum(max(1, w) for w in seg_words)
    seg_durs = [total * (max(1, w) / seg_sum) for w in seg_words]

    # Build segments with cumulative times
    segments = []
    t = 0.0
    labels = ['HOOK', 'CURIOSITY', 'PAYOFF', 'CTA']
    for label, seg_text, d in zip(labels, [hook, curiosity, payoff, cta], seg_durs):
        start = t
        end = t + d
        segments.append({'label': label, 'text': seg_text, 'start': round(start, 2), 'end': round(end, 2)})
        t = end

    return {
        'ok': True,
        'script_text': text,
        'words': wc_total,
        'duration_sec': total,
        'segments': segments,
        'notes': {'target_sec': '7-15', 'wpm': 160},
    }
