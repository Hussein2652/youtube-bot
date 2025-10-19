#!/usr/bin/env python3
import argparse
import json
import os
import sys
from typing import List, Dict

import requests


def read_payload() -> Dict:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload: {exc}")


def build_prompt(payload: Dict) -> str:
    topic = payload.get("topic", "")
    constraints = payload.get("constraints", {})
    seeds = payload.get("seeds", [])
    count = payload.get("count", 10)

    seed_lines = []
    for seed in seeds:
        txt = seed.get("text") or ""
        emo = seed.get("emotion") or ""
        if txt:
            seed_lines.append(f"- {txt} :: emotion={emo}")
    seed_block = "\n".join(seed_lines) or "- (none provided)"

    max_words = constraints.get("max_words", 12)
    instructions = (
        f"Topic: {topic}\n"
        f"Return {count} mutated hooks in JSON -> {{\"variants\":[{{\"text\":...,\"emotion\":...}},...]}}\n"
        f"Constraints:\n"
        f"- Keep emotion from the matching seed.\n"
        f"- Preserve hook structure and pacing.\n"
        f"- Swap nouns/verbs for fresh wording.\n"
        f"- Hard limit {max_words} words.\n"
        f"- No duplicates vs seeds or among variants.\n\n"
        f"Seeds:\n{seed_block}\n"
    )
    return instructions


def call_llm(host: str, port: int, model: str, prompt: str) -> str:
    url = f"http://{host}:{port}/v1/chat/completions"
    headers = {"Authorization": f"Bearer {os.getenv('VLLM_API_KEY', 'dummy')}"}
    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You mutate viral hooks. Reply with compact JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 200,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def parse_variants(text: str, fallback_emotion: str = None) -> List[Dict[str, str]]:
    variants: List[Dict[str, str]] = []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("variants"), list):
            for item in parsed["variants"]:
                if isinstance(item, dict):
                    txt = str(item.get("text", "")).strip()
                    emo = item.get("emotion") or fallback_emotion
                else:
                    txt = str(item).strip()
                    emo = fallback_emotion
                if txt:
                    variants.append({"text": txt, "emotion": emo})
            return variants
    except json.JSONDecodeError:
        pass

    # fallback: split by newline
    for line in text.splitlines():
        line = line.strip("- •\t ")
        if not line:
            continue
        parts = line.split("::", 1)
        txt = parts[0].strip()
        emo = fallback_emotion
        if len(parts) == 2 and "emotion=" in parts[1]:
            emo = parts[1].split("emotion=", 1)[1].strip()
        if txt:
            variants.append({"text": txt, "emotion": emo})
    return variants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.getenv("LLM_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("LLM_PORT", "8000")))
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", "meta-llama-3-8b-instruct"))
    args = parser.parse_args()

    try:
        payload = read_payload()
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        return 1

    try:
        prompt = build_prompt(payload)
        response = call_llm(args.host, args.port, args.model, prompt)
        seeds = payload.get("seeds") or []
        fallback_emotion = seeds[0].get("emotion") if seeds else None
        variants = parse_variants(response, fallback_emotion=fallback_emotion)
        if payload.get("count"):
            desired = int(payload["count"])
            variants = variants[:desired]
        print(json.dumps({"variants": variants}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
