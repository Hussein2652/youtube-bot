import math
import os
from typing import List, Optional

import numpy as np


def _hash_embed(text: str, dim: int = 256) -> List[float]:
    # Simple hashed bag-of-words embedding, deterministic and fast
    vec = [0.0] * dim
    for tok in text.lower().split():
        h = abs(hash(tok)) % dim
        vec[h] += 1.0
    # l2 norm
    n = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / n for v in vec]


def cosine_sim(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


try:  # optional dependency for ONNX tokenization
    from tokenizers import Tokenizer  # type: ignore
except Exception:  # pragma: no cover
    Tokenizer = None  # type: ignore


class EmbeddingModel:
    def __init__(self, backend: str = 'hash', model_path: Optional[str] = None, tokenizer_path: Optional[str] = None, max_length: int = 128):
        self.backend = backend
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.max_length = max_length
        self._sess = None
        self._tokenizer = None
        if backend == 'onnx' and model_path and os.path.exists(model_path):
            try:
                import onnxruntime as ort  # type: ignore
                self._sess = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
                if tokenizer_path and Tokenizer:
                    self._tokenizer = Tokenizer.from_file(tokenizer_path)
            except Exception:
                self.backend = 'hash'

    def embed(self, texts: List[str]) -> List[List[float]]:
        if self.backend != 'onnx' or not self._sess:
            return [_hash_embed(t) for t in texts]
        if not self._tokenizer:
            return [_hash_embed(t) for t in texts]

        encodings = self._tokenizer.encode_batch(texts) if texts else []
        if not encodings:
            return [_hash_embed(t) for t in texts]

        max_len = min(self.max_length, max(len(enc.ids) for enc in encodings)) or 1
        input_ids = np.zeros((len(texts), max_len), dtype=np.int64)
        attention_mask = np.zeros_like(input_ids)
        token_type_ids = np.zeros_like(input_ids)
        for idx, enc in enumerate(encodings):
            ids = enc.ids[:max_len]
            mask = [1] * len(ids)
            input_ids[idx, :len(ids)] = np.array(ids, dtype=np.int64)
            attention_mask[idx, :len(ids)] = np.array(mask, dtype=np.int64)
            if enc.type_ids:
                token_type_ids[idx, :len(ids)] = np.array(enc.type_ids[:max_len], dtype=np.int64)

        inputs = {}
        session_inputs = self._sess.get_inputs()
        for inp in session_inputs:
            name = inp.name
            if 'input_ids' in name or name.endswith('input_ids'):
                inputs[name] = input_ids
            elif 'attention_mask' in name or name.endswith('attention_mask'):
                inputs[name] = attention_mask
            elif 'token_type_ids' in name or name.endswith('token_type_ids'):
                inputs[name] = token_type_ids
            else:
                # Provide zeros if unknown input expected length same as input_ids
                inputs[name] = input_ids

        outputs = self._sess.run(None, inputs)
        if not outputs:
            return [_hash_embed(t) for t in texts]
        emb = outputs[0]
        # Some models return tuple (pooler_output, last_hidden_state)
        if isinstance(emb, tuple):
            emb = emb[0]
        if hasattr(emb, 'tolist'):
            emb = emb.tolist()

        vectors: List[List[float]] = []
        for row in emb:
            if isinstance(row, (list, tuple)):
                vec = list(row)
            else:
                vec = list(row.tolist())  # type: ignore
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors
