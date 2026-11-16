import json
import re
import zlib

from hr_assistant.cache import SemanticCache
from hr_assistant.config import Settings
from hr_assistant.documents import chunk_processed, process_file
from hr_assistant.guardrails import Guard
from hr_assistant.memory import ConversationStore
from hr_assistant.models import Profile
from hr_assistant.pipeline import Pipeline


class FakeEmbedder:
    def embed_query(self, text):
        v = [0.0] * 64
        for w in re.findall(r"[a-z]+", text.lower()):
            v[zlib.crc32(w.encode()) % 64] += 1
        return v


class FakeIndex:
    """Applies the scope filter exactly like Qdrant would."""
    def __init__(self, chunks):
        self.chunks, self.last_query, self.last_scope = chunks, None, None

    def search(self, query, vector, scope, k):
        self.last_query, self.last_scope = query, scope
        out = []
        for c in self.chunks:
            ok = True
            for field, allowed in scope.items():
                val = c.metadata[field]
                vals = val if isinstance(val, list) else [val]
                if not any(v in allowed for v in vals):
                    ok = False
            if ok:
                out.append(c)
        return out[:k]


class FakeReranker:
    def rerank(self, query, chunks, top_n):
        words = [w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 3]
        for c in chunks:
            text = c.text.lower()
            c.score = sum(w in text for w in words) / max(len(words), 1)
        return sorted(chunks, key=lambda c: c.score, reverse=True)[:top_n]


class FakeLLM:
    def __init__(self):
        self.calls = []
        self.condensed = None
        self.answerable = True
        self.bad_json = False

    def chat(self, messages, model=None, **kw):
        self.calls.append(list(messages))
        system, last = messages[0]["content"], messages[-1]["content"]
        if "standalone question" in system:
            return self.condensed or last.split("Latest message:")[-1].strip()
        if "EXCERPTS" in last:
            if self.bad_json:
                return "no json here"
            m = re.search(r"\[1\][^\n]*\n(.*?)(?:\n\n\[|\n\nQUESTION)", last, re.S)
            return json.dumps({"answerable": self.answerable, "answer": (m.group(1) if m else ""), "sources": [1]})
        return "SAFE"

    def answer_calls(self):
        return [c for c in self.calls if "Answer ONLY" in c[0]["content"]]


DOCS = {
    "leave_in.txt": b"Policy Category: Leave\nCountry: India\n\nIndia: casual leave is 12 days per year.\nSick leave is 8 days per year.",
    "leave_us.txt": b"Policy Category: Leave\nCountry: US\n\nUS: paid time off is 15 days per year.",
    "notice.txt": b"Policy Category: Notice Period\n\nNotice period is 60 days for all employees.",
    "old_leave_in.txt": b"Policy Category: Leave\nCountry: India\nStatus: retired\n\nIndia old policy: casual leave was 6 days.",
}


def build(settings=None, llm=None):
    s = settings or Settings()
    chunks = []
    for name, data in DOCS.items():
        chunks += chunk_processed(process_file(name, data))
    llm = llm or FakeLLM()
    index = FakeIndex(chunks)
    pipe = Pipeline(s, FakeEmbedder(), FakeReranker(), index, llm, Guard(s, llm),
                    SemanticCache(s.cache_threshold, s.cache_ttl_seconds, s.cache_max_entries),
                    ConversationStore())
    return pipe, llm, index


PRIYA = Profile("priya@acme.com", "Priya", "India", "full_time", "employee")
JOHN = Profile("john@acme.com", "John", "US", "full_time", "manager")
