"""Semantic cache keyed by the employee's scope as well as meaning, so an
India answer can never be served to a US employee."""
import math
import threading
import time


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class SemanticCache:
    def __init__(self, threshold: float, ttl_seconds: int, max_entries: int):
        self.threshold, self.ttl, self.max = threshold, ttl_seconds, max_entries
        self._items: list[tuple[str, list[float], dict, float]] = []
        self._lock = threading.Lock()

    def get(self, scope_key: str, vector: list[float]) -> dict | None:
        now = time.time()
        with self._lock:
            self._items = [i for i in self._items if now - i[3] < self.ttl]
            best, best_score = None, 0.0
            for key, vec, payload, _ in self._items:
                if key != scope_key:
                    continue
                s = cosine(vector, vec)
                if s > best_score:
                    best, best_score = payload, s
            return best if best_score >= self.threshold else None

    def put(self, scope_key: str, vector: list[float], payload: dict) -> None:
        with self._lock:
            self._items.append((scope_key, vector, payload, time.time()))
            if len(self._items) > self.max:
                self._items.pop(0)
