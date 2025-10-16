import random
from typing import Dict, List
from utils import word_count, truncate_words, estimate_duration_sec


CTA_BANK = [
    "Follow for part 2.",
    "Tap follow for daily drops.",
    "Save this before it disappears.",
    "Drop a 🔥 if you want more.",
]


EMOTION_TEMPLATES = {
    'hype': {
        'curiosity': "Wait till you see why this works.",
        'payoff': "It's the fastest path to {topic_word} momentum.",
    },
    'fear': {
        'curiosity': "Most people miss the warning sign.",
        'payoff': "Fix it now so {topic_word} doesn't collapse.",
    },
    'inspire': {
        'curiosity': "It sounds small but it compounds fast.",
        'payoff': "Do this and {topic_word} levels up by tonight.",
    },
    'default': {
        'curiosity': "You won't expect the reason.",
        'payoff': "Here is the quick fix for {topic_word}: do this today.",
    },
}


def _pick_template(emotion: str) -> Dict[str, str]:
    emo = (emotion or '').lower()
    if emo in EMOTION_TEMPLATES:
        return EMOTION_TEMPLATES[emo]
    for key in EMOTION_TEMPLATES:
        if key in emo:
            return EMOTION_TEMPLATES[key]
    return EMOTION_TEMPLATES['default']


def finalize_micro_script(topic: str, mutated_hooks: List[Dict], max_words: int = 50) -> Dict:
    topic_word = topic.split()[0]
    base_hook = mutated_hooks[0]['mutated_text'] if mutated_hooks else f"Watch: {topic_word} in 10s"
    emotion = mutated_hooks[0].get('emotion') if mutated_hooks else None
    tmpl = _pick_template(emotion or '')
    curiosity = tmpl['curiosity']
    payoff = tmpl['payoff'].format(topic_word=topic_word)
    cta = random.choice(CTA_BANK)

    parts = [base_hook, curiosity, payoff, cta]
    text = truncate_words(' '.join(parts), max_words)

    wc_total = max(1, word_count(text))
    base_dur = estimate_duration_sec(text, wpm=160)
    total = max(7.0, min(15.0, base_dur))

    seg_words = [word_count(base_hook), word_count(curiosity), word_count(payoff), word_count(cta)]
    seg_sum = sum(max(1, w) for w in seg_words)
    seg_durs = [total * (max(1, w) / seg_sum) for w in seg_words]

    segments = []
    t = 0.0
    labels = ['HOOK', 'CURIOSITY', 'PAYOFF', 'CTA']
    for label, seg_text, d in zip(labels, [base_hook, curiosity, payoff, cta], seg_durs):
        start = round(t, 2)
        end = round(t + d, 2)
        segments.append({'label': label, 'text': seg_text, 'start': start, 'end': end})
        t += d

    return {
        'ok': True,
        'script_text': text,
        'words': wc_total,
        'duration_sec': total,
        'segments': segments,
        'notes': {'target_sec': '7-15', 'wpm': 160, 'emotion': emotion},
    }
