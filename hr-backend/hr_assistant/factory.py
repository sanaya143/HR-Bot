from .cache import SemanticCache
from .config import Settings
from .embeddings import LocalEmbedder, LocalReranker
from .guardrails import Guard
from .llm import OpenRouterLLM
from .memory import ConversationStore
from .pipeline import Pipeline
from .vector_store import PineconeIndex

url_for = lambda source, page: f"/api/documents/{source}" + (f"#page={page}" if page else "")


def build_pipeline(s: Settings) -> Pipeline:
    embedder = LocalEmbedder(s.embedding_model)      # loads the models at startup
    reranker = LocalReranker(s.reranker_model)
    llm = OpenRouterLLM(s)
    return Pipeline(
        s, embedder, reranker, PineconeIndex(s, embedder), llm, Guard(s, llm),
        SemanticCache(s.cache_threshold, s.cache_ttl_seconds, s.cache_max_entries),
        ConversationStore(s.memory_max_turns, s.conversation_ttl_seconds, s.max_conversations),
        url_for=url_for)
