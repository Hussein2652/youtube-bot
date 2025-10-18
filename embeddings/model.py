import json
import math
import os
from typing import List, Optional, Dict

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
    def __init__(
        self,
        backend: str = 'hash',
        model_path: Optional[str] = None,
        tokenizer_path: Optional[str] = None,
        model_dir: Optional[str] = None,
        max_length: int = 128,
        device: str = 'auto',
    ):
        self.backend = backend
        self.model_dir = model_dir
        if model_dir and not model_path:
            candidate = os.path.join(model_dir, 'model.onnx')
            model_path = candidate if os.path.exists(candidate) else None
        if model_dir and not tokenizer_path:
            candidate_tok = os.path.join(model_dir, 'tokenizer.json')
            tokenizer_path = candidate_tok if os.path.exists(candidate_tok) else None
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.max_length = max_length
        self.device = device
        self._sess = None
        self._tokenizer = None
        self._vocab_vectors = None

        if backend == 'onnx' and model_path and os.path.exists(model_path):
            try:
                import onnxruntime as ort  # type: ignore

                providers = ['CPUExecutionProvider']
                if device.lower() in ('cuda', 'gpu'):
                    providers.insert(0, 'CUDAExecutionProvider')
                self._sess = ort.InferenceSession(model_path, providers=providers)
                if tokenizer_path and Tokenizer:
                    self._tokenizer = Tokenizer.from_file(tokenizer_path)
                else:
                    self._load_basic_tokenizer()
            except Exception:
                self.backend = 'hash'
        else:
            self.backend = 'hash'

        if self.backend != 'onnx':
            self._load_basic_tokenizer()

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

    def _load_basic_tokenizer(self) -> None:
        """Fallback tokenization using plain whitespace word-level vocab."""
        if self._tokenizer is not None:
            return
        vocab_map = {}
        if self.model_dir:
            vocab_path = os.path.join(self.model_dir, 'vocab.txt')
            if os.path.exists(vocab_path):
                with open(vocab_path, 'r', encoding='utf-8') as vf:
                    for idx, line in enumerate(vf):
                        token = line.strip()
                        if token:
                            vocab_map[token] = idx + 1
        # Make simple struct to mimic tokenizers interface
        class SimpleEncoding:
            def __init__(self, ids, type_ids=None):
                self.ids = ids
                self.type_ids = type_ids or [1] * len(ids)

        class SimpleTokenizer:
            def __init__(self, vocab):
                self.vocab = vocab

            def encode_batch(self, texts):
                encodings = []
                for text in texts:
                    tokens = text.lower().split()
                    ids = [self.vocab.get(tok, (hash(tok) % 10000) + 1) for tok in tokens]
                    encodings.append(SimpleEncoding(ids))
                return encodings

        if vocab_map:
            self._tokenizer = SimpleTokenizer(vocab_map)  # type: ignore
        else:
            self._tokenizer = SimpleTokenizer({})  # type: ignore
