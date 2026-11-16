"""Per-conversation memory, isolated per user. In-memory for v1 (clears on restart);
swap this class for Redis/Firestore to survive restarts and multiple instances."""
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class Turn:
    question: str
    answer: str
    ts: float


def new_conversation_id() -> str:
    return uuid.uuid4().hex


class ConversationStore:
    def __init__(self, max_turns: int = 10, ttl_seconds: int = 8 * 3600, max_conversations: int = 5000):
        self.max_turns, self.ttl, self.max_conv = max_turns, ttl_seconds, max_conversations
        self._data: OrderedDict[tuple[str, str], list[Turn]] = OrderedDict()
        self._lock = threading.Lock()

    def _expire(self) -> None:
        now = time.time()
        for k in [k for k, v in self._data.items() if v and now - v[-1].ts > self.ttl]:
            del self._data[k]

    def get(self, user: str, cid: str) -> list[Turn]:
        with self._lock:
            self._expire()
            return list(self._data.get((user, cid), []))

    def append(self, user: str, cid: str, question: str, answer: str) -> None:
        with self._lock:
            key = (user, cid)
            turns = self._data.setdefault(key, [])
            turns.append(Turn(question, answer, time.time()))
            del turns[:-self.max_turns]
            self._data.move_to_end(key)
            while len(self._data) > self.max_conv:
                self._data.popitem(last=False)

    def clear(self, user: str, cid: str) -> None:
        with self._lock:
            self._data.pop((user, cid), None)
