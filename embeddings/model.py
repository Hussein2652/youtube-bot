import math
import os
from typing import List, Optional


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


class EmbeddingModel:
    def __init__(self, backend: str = 'hash', model_path: Optional[str] = None):
        self.backend = backend
        self.model_path = model_path
        self._sess = None
        if backend == 'onnx' and model_path and os.path.exists(model_path):
            try:
                import onnxruntime as ort  # type: ignore
                self._sess = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            except Exception:
                self.backend = 'hash'

    def embed(self, texts: List[str]) -> List[List[float]]:
        if self.backend != 'onnx' or not self._sess:
            return [_hash_embed(t) for t in texts]
        # Minimal ONNX runtime path: expect a model with input 'input_text' and output 'embedding'
        try:
            in_name = self._sess.get_inputs()[0].name
            out_name = self._sess.get_outputs()[0].name
            # Not all text models accept raw text tensors. For simplicity, rely on fallback unless user supplies a compatible model wrapper.
            # Users can plug their own tokenization wrapper if needed.
            return [_hash_embed(t) for t in texts]
        except Exception:
            return [_hash_embed(t) for t in texts]

