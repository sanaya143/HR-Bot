"""Local Hugging Face models through fastembed (ONNX, CPU). No API key, no per-call cost."""
import math
import threading

from .models import Chunk


def sigmoid(x: float) -> float:
    """bge rerankers output raw logits; map them to 0..1 so one threshold makes sense."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class LocalEmbedder:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name=model_name)
        self._lock = threading.Lock()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            return [v.tolist() for v in self._model.embed(texts, batch_size=32)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class LocalReranker:
    def __init__(self, model_name: str):
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        self._model = TextCrossEncoder(model_name=model_name)
        self._lock = threading.Lock()

    def rerank(self, query: str, chunks: list[Chunk], top_n: int) -> list[Chunk]:
        if not chunks:
            return []
        with self._lock:
            scores = list(self._model.rerank(query, [c.text for c in chunks]))
        for c, s in zip(chunks, scores):
            c.score = sigmoid(float(s))
        return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_n]
